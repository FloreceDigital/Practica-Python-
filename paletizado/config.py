"""
Configuración general del sistema de registro de tarimas.

Las LÍNEAS y PRESENTACIONES ya no van aquí: se administran desde la página
/admin y se guardan en la base de datos.
"""

import os

# --- Base de datos PostgreSQL ------------------------------------------------
# Formato: postgresql://USUARIO:CONTRASEÑA@SERVIDOR:5432/BASE
# Se puede cambiar sin tocar este archivo con la variable de entorno DATABASE_URL.
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://tarimas:tarimas@localhost:5432/tarimas"
)

# --- Página de administración (/admin) --------------------------------------
# Usuario y contraseña para dar de alta líneas, presentaciones e impresoras.
ADMIN_USUARIO = os.environ.get("ADMIN_USUARIO", "admin")
ADMIN_CONTRASENA = os.environ.get("ADMIN_CONTRASENA", "cambia-esta-contrasena")

# --- Turnos: (número, hora de inicio, hora de fin) en formato 24 h ----------
TURNOS = [
    (1, 6, 14),
    (2, 14, 22),
    (3, 22, 6),  # cruza la medianoche
]

# --- Impresoras de etiquetas ------------------------------------------------
# La IP de cada impresora se captura por línea en /admin.
# Si una línea no tiene IP, la tablet abre la etiqueta para imprimirla
# con cualquier impresora.
IMPRESORA_PUERTO = 9100    # puerto estándar de impresoras Zebra
IMPRESORA_DPI = 203        # 203 o 300, según el modelo

# --- Google Sheets ----------------------------------------------------------
# URL de la "Aplicación web" del Apps Script (ver apps_script.gs y LEEME.md).
# Si se deja en None, no se manda nada a Sheets.
SHEETS_URL = os.environ.get("SHEETS_URL") or None
SHEETS_CLAVE = os.environ.get("SHEETS_CLAVE", "cambia-esta-clave")
