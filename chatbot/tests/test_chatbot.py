import hashlib
import hmac
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import meta  # noqa: E402
from app import crear_app  # noqa: E402
from bot import MENSAJE_RECHAZO, MENSAJE_REINICIO, Bot  # noqa: E402

SECRETO = "secreto-de-prueba"


class ClaudeFalso:
    """Imita al cliente de Anthropic y guarda lo que se le pidió."""

    def __init__(self, respuestas=None, stop_reason="end_turn"):
        self.llamadas = []
        self.respuestas = list(respuestas or [])
        self.stop_reason = stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        # Copia los mensajes, como si se enviaran por la red en ese momento.
        kwargs["messages"] = [dict(m) for m in kwargs["messages"]]
        self.llamadas.append(kwargs)
        texto = self.respuestas.pop(0) if self.respuestas else "respuesta"
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            stop_details=None,
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text=texto),
            ],
        )


@pytest.fixture(autouse=True)
def configuracion(monkeypatch):
    monkeypatch.setattr(config, "APP_SECRET", SECRETO)
    monkeypatch.setattr(config, "VERIFY_TOKEN", "token-verificacion")
    monkeypatch.setattr(config, "MAX_MENSAJES_HISTORIAL", 4)


def firmar(cuerpo: bytes) -> str:
    return "sha256=" + hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()


def cliente_flask(bot):
    enviados = []
    app = crear_app(bot=bot, enviar=lambda m, t: enviados.append((m, t)), en_segundo_plano=False)
    return app.test_client(), enviados


def post_webhook(cliente, payload, firma=None):
    cuerpo = json.dumps(payload).encode()
    return cliente.post(
        "/webhook",
        data=cuerpo,
        content_type="application/json",
        headers={"X-Hub-Signature-256": firma or firmar(cuerpo)},
    )


def payload_whatsapp(texto="hola", id_mensaje="wamid.1", tipo="text"):
    mensaje = {"from": "5215512345678", "id": id_mensaje, "type": tipo}
    if tipo == "text":
        mensaje["text"] = {"body": texto}
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {"metadata": {"phone_number_id": "111"}, "messages": [mensaje]},
                    }
                ]
            }
        ],
    }


def payload_messenger(texto="hola", mid="m.1", echo=False):
    message = {"mid": mid, "text": texto}
    if echo:
        message["is_echo"] = True
    return {
        "object": "page",
        "entry": [{"messaging": [{"sender": {"id": "PSID9"}, "recipient": {"id": "PAGE"}, "message": message}]}],
    }


def test_verificacion_del_webhook():
    cliente, _ = cliente_flask(Bot(client=ClaudeFalso()))
    ok = cliente.get("/webhook?hub.mode=subscribe&hub.verify_token=token-verificacion&hub.challenge=123")
    assert ok.status_code == 200 and ok.data == b"123"
    mal = cliente.get("/webhook?hub.mode=subscribe&hub.verify_token=otro&hub.challenge=123")
    assert mal.status_code == 403


def test_rechaza_firma_invalida():
    claude = ClaudeFalso()
    cliente, enviados = cliente_flask(Bot(client=claude))
    resp = post_webhook(cliente, payload_whatsapp(), firma="sha256=falsa")
    assert resp.status_code == 401
    assert enviados == [] and claude.llamadas == []


def test_responde_por_whatsapp():
    claude = ClaudeFalso(["¡Hola! ¿En qué te ayudo?"])
    cliente, enviados = cliente_flask(Bot(client=claude))
    assert post_webhook(cliente, payload_whatsapp("hola")).status_code == 200

    (mensaje, texto), = enviados
    assert mensaje.canal == "whatsapp"
    assert mensaje.remitente == "5215512345678" and mensaje.id_telefono == "111"
    assert texto == "¡Hola! ¿En qué te ayudo?"
    llamada = claude.llamadas[0]
    assert llamada["messages"] == [{"role": "user", "content": "hola"}]
    assert llamada["model"] == config.CLAUDE_MODEL
    assert llamada["fallbacks"] == "default"


def test_responde_por_messenger_e_ignora_ecos():
    claude = ClaudeFalso(["hola desde messenger"])
    cliente, enviados = cliente_flask(Bot(client=claude))
    post_webhook(cliente, payload_messenger(echo=True))
    assert enviados == []
    post_webhook(cliente, payload_messenger("hola"))
    (mensaje, texto), = enviados
    assert mensaje.canal == "messenger" and mensaje.remitente == "PSID9"
    assert texto == "hola desde messenger"


def test_no_responde_dos_veces_al_mismo_mensaje():
    claude = ClaudeFalso()
    cliente, enviados = cliente_flask(Bot(client=claude))
    post_webhook(cliente, payload_whatsapp(id_mensaje="wamid.X"))
    post_webhook(cliente, payload_whatsapp(id_mensaje="wamid.X"))
    assert len(enviados) == 1 and len(claude.llamadas) == 1


def test_mensaje_que_no_es_texto():
    claude = ClaudeFalso()
    cliente, enviados = cliente_flask(Bot(client=claude))
    post_webhook(cliente, payload_whatsapp(tipo="image"))
    assert "solo puedo leer mensajes de texto" in enviados[0][1]
    assert claude.llamadas == []


def test_historial_por_usuario_y_recorte():
    claude = ClaudeFalso(["r1", "r2", "r3", "otro"])
    bot = Bot(client=claude)
    bot.responder("whatsapp:1", "m1")
    bot.responder("whatsapp:1", "m2")
    bot.responder("whatsapp:1", "m3")
    # Máximo 4 mensajes guardados: los dos últimos intercambios.
    assert [m["content"] for m in bot.historial("whatsapp:1")] == ["m2", "r2", "m3", "r3"]
    assert [m["content"] for m in claude.llamadas[2]["messages"]] == ["m1", "r1", "m2", "r2", "m3"]

    # Otra persona empieza con el historial vacío.
    bot.responder("messenger:2", "hola")
    assert claude.llamadas[3]["messages"] == [{"role": "user", "content": "hola"}]


def test_reiniciar_conversacion():
    claude = ClaudeFalso()
    bot = Bot(client=claude)
    bot.responder("whatsapp:1", "hola")
    assert bot.responder("whatsapp:1", "/reiniciar") == MENSAJE_REINICIO
    assert bot.historial("whatsapp:1") == []


def test_rechazo_de_claude_no_se_guarda():
    bot = Bot(client=ClaudeFalso(stop_reason="refusal"))
    assert bot.responder("whatsapp:1", "algo") == MENSAJE_RECHAZO
    assert bot.historial("whatsapp:1") == []


def test_partir_mensajes_largos():
    texto = ("palabra " * 600).strip()  # ~4800 caracteres
    trozos = meta._partir(texto, meta.LIMITE_MESSENGER)
    assert all(len(t) <= meta.LIMITE_MESSENGER for t in trozos)
    assert " ".join(trozos) == texto
