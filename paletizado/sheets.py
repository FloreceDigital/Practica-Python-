"""
Envía las tarimas a Google Sheets (la hoja de la empresa).

Funciona con un Apps Script pegado en la hoja (ver apps_script.gs y LEEME.md).
Si no hay internet o Google no responde, el envío se guarda en una cola
(datos/pendientes_sheets.json) y se reintenta en el siguiente registro o
cada minuto. Así nunca se pierde una tarima ni se detiene la impresión.
"""

import json
import os
import threading
import time
import urllib.request

import config

ARCHIVO_PENDIENTES = os.path.join(config.CARPETA_DATOS, "pendientes_sheets.json")
_candado = threading.Lock()


def activo():
    return bool(config.SHEETS_URL)


def _leer_pendientes():
    try:
        with open(ARCHIVO_PENDIENTES, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _guardar_pendientes(pendientes):
    os.makedirs(config.CARPETA_DATOS, exist_ok=True)
    with open(ARCHIVO_PENDIENTES, "w", encoding="utf-8") as f:
        json.dump(pendientes, f, ensure_ascii=False)


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


def _vaciar_cola():
    """Intenta mandar todo lo pendiente, en orden. Se detiene al primer fallo."""
    with _candado:
        pendientes = _leer_pendientes()
        while pendientes:
            if not _enviar(pendientes[0]):
                break
            pendientes.pop(0)
            _guardar_pendientes(pendientes)


def _encolar(mensaje):
    with _candado:
        pendientes = _leer_pendientes()
        pendientes.append(mensaje)
        _guardar_pendientes(pendientes)
    # Se manda en segundo plano para que la tablet no espere a Google.
    threading.Thread(target=_vaciar_cola, daemon=True).start()


def agregar(tarima):
    if activo():
        _encolar({"accion": "agregar", "tarima": tarima})


def anular(folio):
    if activo():
        _encolar({"accion": "anular", "folio": folio})


def pendientes():
    return len(_leer_pendientes()) if activo() else 0


def iniciar_reintentos(cada_segundos=60):
    """Revisa la cola cada minuto por si regresó el internet."""
    if not activo():
        return

    def ciclo():
        while True:
            _vaciar_cola()
            time.sleep(cada_segundos)

    threading.Thread(target=ciclo, daemon=True).start()
