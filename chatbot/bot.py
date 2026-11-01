"""Lógica de conversación: genera respuestas con Claude y recuerda el historial de cada persona."""

import logging
import threading
from collections import defaultdict

import anthropic

import config

log = logging.getLogger(__name__)

MENSAJE_ERROR = (
    "Perdón, tuve un problema técnico y no pude responder. "
    "¿Puedes intentarlo de nuevo en un momento?"
)
MENSAJE_RECHAZO = (
    "Lo siento, no puedo ayudarte con eso. ¿Hay algo más en lo que te pueda ayudar?"
)
MENSAJE_REINICIO = "Listo, empecemos de nuevo. ¿En qué te puedo ayudar?"
COMANDOS_REINICIO = {"/reiniciar", "/reset", "reiniciar"}


def construir_system_prompt() -> str:
    info = ""
    if config.INFO_NEGOCIO_PATH.exists():
        info = config.INFO_NEGOCIO_PATH.read_text(encoding="utf-8").strip()

    prompt = f"""Eres el asistente virtual de {config.NOMBRE_NEGOCIO}. Atiendes a clientes por \
WhatsApp y Facebook Messenger.

Cómo responder:
- Responde en el idioma en que te escriban (por defecto, español).
- Sé amable, claro y breve: son mensajes de chat en el celular. Usa párrafos cortos y evita \
tablas, títulos y formato Markdown complejo.
- Usa solo la información del negocio que aparece abajo para datos concretos como precios, \
horarios, direcciones o políticas. Si no tienes un dato, dilo con honestidad y ofrece que una \
persona del equipo le dé seguimiento; no inventes nada.
- Si el cliente pide hablar con una persona, o tiene una queja o un caso delicado, dile que \
alguien del equipo lo contactará pronto."""

    if info:
        prompt += f"\n\n<informacion_del_negocio>\n{info}\n</informacion_del_negocio>"
    return prompt


class Bot:
    """Mantiene una conversación por usuario y le pide las respuestas a Claude."""

    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()
        self.system_prompt = construir_system_prompt()
        self._historial: dict[str, list[dict]] = defaultdict(list)
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._locks_lock = threading.Lock()

    def _lock_de(self, usuario: str) -> threading.Lock:
        with self._locks_lock:
            return self._locks[usuario]

    def reiniciar(self, usuario: str) -> None:
        self._historial.pop(usuario, None)

    def historial(self, usuario: str) -> list[dict]:
        return list(self._historial.get(usuario, []))

    def responder(self, usuario: str, texto: str) -> str:
        """Devuelve la respuesta del bot para `texto`, enviado por `usuario`.

        `usuario` debe identificar a la persona en su canal, p. ej. "whatsapp:5215512345678".
        """
        if texto.strip().lower() in COMANDOS_REINICIO:
            self.reiniciar(usuario)
            return MENSAJE_REINICIO

        # Un lock por usuario: si alguien manda varios mensajes seguidos, se responden en orden.
        with self._lock_de(usuario):
            mensajes = self._historial[usuario] + [{"role": "user", "content": texto}]
            respuesta = self._pedir_a_claude(mensajes)
            if respuesta is None:
                return MENSAJE_ERROR
            if respuesta == "":
                return MENSAJE_RECHAZO

            # Se guarda solo el texto de cada turno; así podemos recortar el historial libremente.
            mensajes.append({"role": "assistant", "content": respuesta})
            self._historial[usuario] = self._recortar(mensajes)
            return respuesta

    @staticmethod
    def _recortar(mensajes: list[dict]) -> list[dict]:
        recortados = mensajes[-config.MAX_MENSAJES_HISTORIAL :]
        # La conversación enviada a Claude debe empezar con un mensaje del usuario.
        while recortados and recortados[0]["role"] != "user":
            recortados = recortados[1:]
        return recortados

    def _pedir_a_claude(self, mensajes: list[dict]) -> str | None:
        """Devuelve el texto de la respuesta, "" si Claude la rechazó, o None si hubo un error."""
        extra = {}
        if config.CLAUDE_FALLBACKS:
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

        try:
            response = self.client.beta.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                system=self.system_prompt,
                messages=mensajes,
                output_config={"effort": config.CLAUDE_EFFORT},
                cache_control={"type": "ephemeral"},
                **extra,
            )
        except anthropic.RateLimitError:
            log.warning("Claude: límite de uso alcanzado (429)")
            return None
        except anthropic.APIStatusError as e:
            log.error("Claude: error %s: %s", e.status_code, e.message)
            return None
        except anthropic.APIConnectionError:
            log.error("Claude: no se pudo conectar con la API")
            return None

        if response.stop_reason == "refusal":
            log.info("Claude rechazó la petición: %s", response.stop_details)
            return ""

        texto = "\n".join(b.text for b in response.content if b.type == "text").strip()
        return texto or None
