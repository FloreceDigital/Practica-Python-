"""
Arranca la app para uso diario (producción) con Waitress.

    python servidor.py

A diferencia de `python app.py` (servidor de pruebas de Flask), Waitress
aguanta varias tabletas a la vez y funciona igual en Windows y en Linux.
"""

import logging
import os

from waitress import serve

import sheets
from app import app

PUERTO = int(os.environ.get("PUERTO", "5000"))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sheets.iniciar_reintentos()
    print(f"Registro de tarimas escuchando en el puerto {PUERTO}")
    # host="0.0.0.0" permite que las tabletas se conecten por la red de la planta.
    serve(app, host="0.0.0.0", port=PUERTO, threads=8)
