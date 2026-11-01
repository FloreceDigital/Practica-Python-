"""Configuración del chatbot, leída de variables de entorno (o de un archivo .env)."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _cargar_env(ruta: Path) -> None:
    """Carga un archivo .env sencillo (CLAVE=valor) sin dependencias extra."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env(BASE_DIR / ".env")

# --- Meta (Facebook / WhatsApp) ---
# Token que tú inventas y pegas también en el panel de Meta al registrar el webhook.
VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "")
# "Clave secreta de la app" (App Secret). Se usa para comprobar que los mensajes vienen de Meta.
APP_SECRET = os.environ.get("META_APP_SECRET", "")
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v23.0")

# WhatsApp Cloud API: token de acceso (de un usuario del sistema, idealmente permanente).
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
# Messenger: token de acceso de la página de Facebook.
MESSENGER_PAGE_TOKEN = os.environ.get("MESSENGER_PAGE_TOKEN", "")

# --- Claude ---
CLAUDE_MODEL = os.environ.get("CHATBOT_MODEL", "claude-opus-5-5")
# low | medium | high | xhigh | max. Para un chat de atención, "low" suele bastar y es más rápido.
CLAUDE_EFFORT = os.environ.get("CHATBOT_EFFORT", "low")
CLAUDE_MAX_TOKENS = int(os.environ.get("CHATBOT_MAX_TOKENS", "8000"))
# Si Claude rechaza una petición, la API la reintenta automáticamente con otro modelo.
CLAUDE_FALLBACKS = os.environ.get("CHATBOT_FALLBACKS", "1") not in ("0", "false", "no")

# --- Comportamiento del bot ---
NOMBRE_NEGOCIO = os.environ.get("NOMBRE_NEGOCIO", "nuestro negocio")
# Cuántos mensajes previos (usuario + bot) recuerda por cada persona.
MAX_MENSAJES_HISTORIAL = int(os.environ.get("MAX_MENSAJES_HISTORIAL", "20"))
INFO_NEGOCIO_PATH = Path(os.environ.get("INFO_NEGOCIO_PATH", BASE_DIR / "info_negocio.md"))
