"""
Envía las tarimas a Google Sheets (la hoja de la empresa).

Las tarimas nuevas y las anulaciones se dejan en la tabla `sheets_pendientes`
en la misma transacción que la tarima. Este módulo las va mandando en orden
al Apps Script de la hoja. Si no hay internet, se quedan en la tabla y se
reintentan cada minuto. Nunca se pierde un envío ni se detiene la impresión.
"""

import json
import threading
import time
import urllib.request

import config
import db


def activo():
    return bool(config.SHEETS_URL)


def _enviar(mensaje):
    """Manda un mensaje al Apps Script. Regresa True si Google lo aceptó."""
    datos = json.dumps({**mensaje, "clave": config.SHEETS_CLAVE}).encode("utf-8")
    peticion = urllib.request.Request(
        config.SHEETS_URL, data=datos, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            return json.loads(respuesta.read().decode("utf-8")).get("ok") is True
    except (OSError, ValueError):
        return False


def vaciar_cola():
    """Manda todo lo pendiente, en orden. Se detiene al primer fallo."""
    if not activo():
        return
    while True:
        with db.conectar() as con:
            # SKIP LOCKED: si otro proceso ya está mandando ese registro, no se repite.
            pendiente = con.execute(
                """SELECT id, mensaje FROM sheets_pendientes
                   ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED"""
            ).fetchone()
            if pendiente is None:
                return
            if _enviar(pendiente["mensaje"]):
                con.execute("DELETE FROM sheets_pendientes WHERE id = %s", (pendiente["id"],))
            else:
                con.execute(
                    "UPDATE sheets_pendientes SET intentos = intentos + 1 WHERE id = %s",
                    (pendiente["id"],),
                )
                return


def avisar():
    """Se llama después de registrar o anular: manda en segundo plano."""
    if activo():
        threading.Thread(target=vaciar_cola, daemon=True).start()


def pendientes():
    if not activo():
        return 0
    with db.conectar() as con:
        return con.execute("SELECT count(*) AS n FROM sheets_pendientes").fetchone()["n"]


def iniciar_reintentos(cada_segundos=60):
    """Revisa la cola cada minuto por si regresó el internet."""
    if not activo():
        return

    def ciclo():
        while True:
            try:
                vaciar_cola()
            except Exception as error:  # la base de datos podría reiniciarse
                print("Sheets: error al reintentar:", error)
            time.sleep(cada_segundos)

    threading.Thread(target=ciclo, daemon=True).start()
