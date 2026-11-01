"""Comunicación con Meta: verificar firmas, leer mensajes entrantes y enviar respuestas."""

import hashlib
import hmac
import logging
from dataclasses import dataclass

import requests

import config

log = logging.getLogger(__name__)

# Límites de longitud de un mensaje de texto en cada canal.
LIMITE_WHATSAPP = 4096
LIMITE_MESSENGER = 2000


@dataclass
class MensajeEntrante:
    canal: str  # "whatsapp" o "messenger"
    remitente: str  # número de WhatsApp o PSID de Messenger
    id_mensaje: str
    texto: str | None  # None si no es texto (foto, audio, sticker...)
    id_telefono: str | None = None  # phone_number_id de WhatsApp que recibió el mensaje

    @property
    def usuario(self) -> str:
        return f"{self.canal}:{self.remitente}"


def firma_valida(cuerpo: bytes, firma_header: str | None) -> bool:
    """Comprueba la cabecera X-Hub-Signature-256 que Meta añade a cada webhook."""
    if not config.APP_SECRET:
        log.warning("META_APP_SECRET no está configurado: no se verifican las firmas")
        return True
    if not firma_header or not firma_header.startswith("sha256="):
        return False
    esperada = hmac.new(config.APP_SECRET.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma_header.removeprefix("sha256="))


def extraer_mensajes(payload: dict) -> list[MensajeEntrante]:
    """Convierte el JSON del webhook en una lista de mensajes, sea de WhatsApp o de Messenger."""
    objeto = payload.get("object")
    mensajes: list[MensajeEntrante] = []

    if objeto == "whatsapp_business_account":
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                id_telefono = value.get("metadata", {}).get("phone_number_id")
                # Los avisos de estado (enviado, leído...) llegan sin "messages" y se ignoran.
                for m in value.get("messages", []):
                    texto = m.get("text", {}).get("body") if m.get("type") == "text" else None
                    mensajes.append(
                        MensajeEntrante("whatsapp", m["from"], m["id"], texto, id_telefono)
                    )

    elif objeto == "page":
        for entry in payload.get("entry", []):
            for evento in entry.get("messaging", []):
                message = evento.get("message")
                # Ignora lecturas, entregas y los "ecos" de los mensajes que envía la propia página.
                if not message or message.get("is_echo"):
                    continue
                mensajes.append(
                    MensajeEntrante(
                        "messenger", evento["sender"]["id"], message["mid"], message.get("text")
                    )
                )

    return mensajes


def _partir(texto: str, limite: int) -> list[str]:
    """Divide un texto largo en trozos que quepan en un mensaje, cortando en saltos de línea."""
    trozos = []
    while len(texto) > limite:
        corte = texto.rfind("\n", 0, limite)
        if corte <= 0:
            corte = texto.rfind(" ", 0, limite)
        if corte <= 0:
            corte = limite
        trozos.append(texto[:corte].strip())
        texto = texto[corte:].strip()
    if texto:
        trozos.append(texto)
    return trozos


def _post(url: str, token: str, json: dict) -> None:
    resp = requests.post(
        url, json=json, headers={"Authorization": f"Bearer {token}"}, timeout=15
    )
    if resp.status_code >= 400:
        log.error("Error de Meta (%s): %s", resp.status_code, resp.text)


def enviar_whatsapp(id_telefono: str, destino: str, texto: str) -> None:
    url = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{id_telefono}/messages"
    for trozo in _partir(texto, LIMITE_WHATSAPP):
        _post(
            url,
            config.WHATSAPP_TOKEN,
            {
                "messaging_product": "whatsapp",
                "to": destino,
                "type": "text",
                "text": {"body": trozo},
            },
        )


def enviar_messenger(psid: str, texto: str) -> None:
    url = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/me/messages"
    for trozo in _partir(texto, LIMITE_MESSENGER):
        _post(
            url,
            config.MESSENGER_PAGE_TOKEN,
            {
                "recipient": {"id": psid},
                "messaging_type": "RESPONSE",
                "message": {"text": trozo},
            },
        )


def enviar(mensaje: MensajeEntrante, texto: str) -> None:
    """Responde por el mismo canal por el que llegó el mensaje."""
    if mensaje.canal == "whatsapp":
        enviar_whatsapp(mensaje.id_telefono, mensaje.remitente, texto)
    else:
        enviar_messenger(mensaje.remitente, texto)
