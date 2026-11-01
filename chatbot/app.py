"""Servidor web del chatbot. Meta envía aquí los mensajes de WhatsApp y de Messenger.

Ejecutar en local:  python app.py
"""

import logging
import os
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, abort, request

import config
import meta
from bot import Bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("chatbot")

MENSAJE_NO_TEXTO = "Por ahora solo puedo leer mensajes de texto. ¿Me lo puedes escribir?"


class IdsVistos:
    """Recuerda los últimos IDs de mensaje para no responder dos veces si Meta reintenta."""

    def __init__(self, maximo: int = 5000):
        self._ids: OrderedDict[str, None] = OrderedDict()
        self._maximo = maximo
        self._lock = threading.Lock()

    def es_nuevo(self, id_mensaje: str) -> bool:
        with self._lock:
            if id_mensaje in self._ids:
                return False
            self._ids[id_mensaje] = None
            if len(self._ids) > self._maximo:
                self._ids.popitem(last=False)
            return True


def crear_app(bot: Bot | None = None, enviar=meta.enviar, en_segundo_plano: bool = True) -> Flask:
    app = Flask(__name__)
    bot = bot or Bot()
    vistos = IdsVistos()
    trabajadores = ThreadPoolExecutor(max_workers=8)

    def atender(mensaje: meta.MensajeEntrante) -> None:
        try:
            if mensaje.texto is None:
                respuesta = MENSAJE_NO_TEXTO
            else:
                respuesta = bot.responder(mensaje.usuario, mensaje.texto)
            enviar(mensaje, respuesta)
        except Exception:
            log.exception("Error atendiendo el mensaje %s", mensaje.id_mensaje)

    @app.get("/")
    def inicio():
        return "Chatbot activo"

    @app.get("/webhook")
    def verificar_webhook():
        """Meta llama aquí una sola vez, al registrar el webhook, para comprobar que es tuyo."""
        if (
            request.args.get("hub.mode") == "subscribe"
            and config.VERIFY_TOKEN
            and request.args.get("hub.verify_token") == config.VERIFY_TOKEN
        ):
            return request.args.get("hub.challenge", ""), 200
        abort(403)

    @app.post("/webhook")
    def recibir_webhook():
        if not meta.firma_valida(request.get_data(), request.headers.get("X-Hub-Signature-256")):
            abort(401)

        for mensaje in meta.extraer_mensajes(request.get_json(silent=True) or {}):
            if not vistos.es_nuevo(mensaje.id_mensaje):
                continue
            log.info("Mensaje de %s", mensaje.usuario)
            # Meta exige responder rápido al webhook; Claude contesta en segundo plano.
            if en_segundo_plano:
                trabajadores.submit(atender, mensaje)
            else:
                atender(mensaje)

        return "OK", 200

    return app


if __name__ == "__main__":
    crear_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
