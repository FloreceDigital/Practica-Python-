"""
Guarda cada tarima registrada.

- El archivo CSV es el registro principal: se puede escribir aunque alguien
  tenga el Excel abierto.
- Después de cada registro se regenera el Excel a partir del CSV. Si el Excel
  está abierto en otra computadora y no se puede guardar, no se pierde nada:
  se actualizará en el siguiente registro.
"""

import csv
import os
from datetime import datetime, timedelta

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

import config

COLUMNAS = [
    "folio",
    "fecha",
    "hora",
    "turno",
    "linea",
    "presentacion",
    "descripcion",
    "lote",
    "fardos",
    "bolsas",
    "libras",
    "completa",
    "estado",
    "registro_por",
]


def _ruta(nombre):
    os.makedirs(config.CARPETA_DATOS, exist_ok=True)
    return os.path.join(config.CARPETA_DATOS, nombre)


def turno_actual(momento):
    hora = momento.hour
    for numero, inicio, fin in config.TURNOS:
        if inicio < fin and inicio <= hora < fin:
            return numero
        if inicio > fin and (hora >= inicio or hora < fin):
            return numero
    return 0


def inicio_turno(momento):
    """Fecha y hora en que empezó el turno que está corriendo."""
    numero = turno_actual(momento)
    for n, inicio, _fin in config.TURNOS:
        if n == numero:
            comienzo = momento.replace(hour=inicio, minute=0, second=0, microsecond=0)
            if comienzo > momento:  # turno que empezó ayer (cruza medianoche)
                comienzo -= timedelta(days=1)
            return comienzo
    return momento.replace(hour=0, minute=0, second=0, microsecond=0)


def leer_todas():
    ruta = _ruta(config.ARCHIVO_CSV)
    if not os.path.exists(ruta):
        return []
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _escribir_todas(filas):
    ruta = _ruta(config.ARCHIVO_CSV)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)


def siguiente_folio(filas):
    numero = 0
    for fila in filas:
        try:
            numero = max(numero, int(fila["folio"].split("-")[-1]))
        except (ValueError, KeyError):
            pass
    return f"{config.PREFIJO_FOLIO}-{numero + 1:06d}"


def buscar_presentacion(clave):
    for p in config.PRESENTACIONES:
        if p["clave"] == clave:
            return p
    return None


def registrar_tarima(presentacion, lote, fardos=None, registro_por="Montacargas"):
    """Crea una tarima nueva y la guarda. Regresa el diccionario de la tarima."""
    completa = fardos is None or fardos == presentacion["fardos_por_tarima"]
    if fardos is None:
        fardos = presentacion["fardos_por_tarima"]

    ahora = datetime.now()
    filas = leer_todas()
    bolsas = fardos * presentacion["bolsas_por_fardo"]

    tarima = {
        "folio": siguiente_folio(filas),
        "fecha": ahora.strftime("%Y-%m-%d"),
        "hora": ahora.strftime("%H:%M:%S"),
        "turno": turno_actual(ahora),
        "linea": config.LINEA,
        "presentacion": presentacion["nombre"],
        "descripcion": presentacion["descripcion"],
        "lote": lote,
        "fardos": fardos,
        "bolsas": bolsas,
        "libras": bolsas * presentacion["libras_por_bolsa"],
        "completa": "SI" if completa else "NO",
        "estado": "OK",
        "registro_por": registro_por,
    }

    filas.append(tarima)
    _escribir_todas(filas)
    actualizar_excel(filas)
    return tarima


def buscar_tarima(folio):
    for fila in leer_todas():
        if fila["folio"] == folio:
            return fila
    return None


def anular_tarima(folio):
    """Marca la tarima como ANULADA (no se borra, para no perder el folio)."""
    filas = leer_todas()
    encontrada = False
    for fila in filas:
        if fila["folio"] == folio:
            fila["estado"] = "ANULADA"
            encontrada = True
    if encontrada:
        _escribir_todas(filas)
        actualizar_excel(filas)
    return encontrada


def resumen_turno():
    """Tarimas válidas del turno en curso (de hoy o de anoche si es turno 3)."""
    ahora = datetime.now()
    inicio = inicio_turno(ahora)
    del_turno = []
    for f in leer_todas():
        momento = datetime.strptime(f"{f['fecha']} {f['hora']}", "%Y-%m-%d %H:%M:%S")
        if f["estado"] == "OK" and momento >= inicio:
            del_turno.append(f)
    turno = turno_actual(ahora)

    return {
        "turno": turno,
        "tarimas": len(del_turno),
        "fardos": sum(int(f["fardos"]) for f in del_turno),
        "libras": sum(int(f["libras"]) for f in del_turno),
    }


def actualizar_excel(filas=None):
    """Regenera el Excel. Regresa True si se pudo guardar."""
    if filas is None:
        filas = leer_todas()

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Tarimas"

    titulos = [c.replace("_", " ").upper() for c in COLUMNAS]
    hoja.append(titulos)
    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="1F4E78")

    numericas = {"turno", "fardos", "bolsas", "libras"}
    rojo = PatternFill("solid", fgColor="F8CBAD")
    for fila in filas:
        valores = []
        for c in COLUMNAS:
            v = fila.get(c, "")
            if c in numericas and str(v).isdigit():
                v = int(v)
            valores.append(v)
        hoja.append(valores)
        if fila.get("estado") == "ANULADA":
            for celda in hoja[hoja.max_row]:
                celda.fill = rojo

    anchos = [12, 12, 10, 7, 10, 13, 20, 14, 8, 8, 9, 10, 10, 14]
    for i, ancho in enumerate(anchos):
        hoja.column_dimensions[chr(65 + i)].width = ancho
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions

    try:
        libro.save(_ruta(config.ARCHIVO_EXCEL))
        return True
    except PermissionError:
        # El Excel está abierto en otra parte; se actualizará en el próximo registro.
        return False
