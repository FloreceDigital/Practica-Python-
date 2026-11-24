"""
Toda la lógica de tarimas, líneas y presentaciones sobre PostgreSQL.
"""

import io
from datetime import datetime, timedelta
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from psycopg.types.json import Jsonb

import config
import db

# Columnas que se exportan a Excel y se mandan a Google Sheets (en este orden)
COLUMNAS = [
    "folio", "fecha", "hora", "turno", "linea", "presentacion", "descripcion",
    "lote", "fardos", "bolsas", "libras", "completa", "estado", "registro_por",
]


# --- Turnos -----------------------------------------------------------------

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


# --- Utilidades ---------------------------------------------------------------

def numero_limpio(valor):
    """Decimal('2240.000') -> 2240 ; Decimal('2.500') -> 2.5"""
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral() else float(valor.normalize())
    return valor


def _formatear(fila):
    """Convierte una fila de la base de datos al formato de etiqueta/Excel/Sheets."""
    t = dict(fila)
    momento = t.pop("fecha_hora")
    t["fecha"] = momento.strftime("%Y-%m-%d")
    t["hora"] = momento.strftime("%H:%M:%S")
    t["libras"] = numero_limpio(t["libras"])
    t["completa"] = "SI" if t["completa"] else "NO"
    return t


_SELECT_TARIMA = """
    SELECT t.folio, t.fecha_hora, t.turno, l.nombre AS linea, l.codigo AS linea_codigo,
           t.presentacion, t.descripcion, t.lote, t.fardos, t.bolsas, t.libras,
           t.completa, t.estado, t.registro_por
    FROM tarimas t JOIN lineas l ON l.id = t.linea_id
"""


# --- Líneas -------------------------------------------------------------------

def lineas(solo_activas=True):
    with db.conectar() as con:
        filtro = "WHERE activa" if solo_activas else ""
        return con.execute(f"SELECT * FROM lineas {filtro} ORDER BY codigo").fetchall()


def linea_por_codigo(codigo):
    with db.conectar() as con:
        return con.execute(
            "SELECT * FROM lineas WHERE codigo = %s", (codigo,)
        ).fetchone()


def guardar_lote(codigo, lote):
    with db.conectar() as con:
        con.execute(
            "UPDATE lineas SET lote_actual = %s WHERE codigo = %s",
            (lote.strip().upper(), codigo),
        )


def guardar_linea(datos, linea_id=None):
    valores = (
        datos["codigo"].strip().upper(),
        datos["nombre"].strip(),
        datos.get("impresora_ip", "").strip() or None,
        bool(datos.get("activa")),
    )
    with db.conectar() as con:
        if linea_id:
            con.execute(
                "UPDATE lineas SET codigo=%s, nombre=%s, impresora_ip=%s, activa=%s WHERE id=%s",
                valores + (linea_id,),
            )
            return linea_id
        return con.execute(
            "INSERT INTO lineas (codigo, nombre, impresora_ip, activa) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            valores,
        ).fetchone()["id"]


# --- Presentaciones -----------------------------------------------------------

def presentaciones(solo_activas=True):
    with db.conectar() as con:
        filtro = "WHERE activa" if solo_activas else ""
        filas = con.execute(
            f"SELECT * FROM presentaciones {filtro} ORDER BY nombre, clave"
        ).fetchall()
    for p in filas:
        p["libras_por_bolsa"] = numero_limpio(p["libras_por_bolsa"])
    return filas


def presentaciones_de_linea(linea_id):
    with db.conectar() as con:
        filas = con.execute(
            """SELECT p.* FROM presentaciones p
               JOIN linea_presentacion lp ON lp.presentacion_id = p.id
               WHERE lp.linea_id = %s AND p.activa
               ORDER BY p.nombre, p.clave""",
            (linea_id,),
        ).fetchall()
    for p in filas:
        p["libras_por_bolsa"] = numero_limpio(p["libras_por_bolsa"])
    return filas


def asignaciones():
    """{linea_id: {presentacion_id, ...}}"""
    resultado = {}
    with db.conectar() as con:
        for fila in con.execute("SELECT * FROM linea_presentacion"):
            resultado.setdefault(fila["linea_id"], set()).add(fila["presentacion_id"])
    return resultado


def guardar_presentacion(datos, lineas_ids, presentacion_id=None):
    valores = (
        datos["clave"].strip().upper(),
        datos["nombre"].strip(),
        datos.get("descripcion", "").strip(),
        Decimal(str(datos["libras_por_bolsa"])),
        int(datos["bolsas_por_fardo"]),
        int(datos["fardos_por_tarima"]),
        bool(datos.get("activa")),
    )
    with db.conectar() as con:
        if presentacion_id:
            con.execute(
                """UPDATE presentaciones SET clave=%s, nombre=%s, descripcion=%s,
                   libras_por_bolsa=%s, bolsas_por_fardo=%s, fardos_por_tarima=%s, activa=%s
                   WHERE id=%s""",
                valores + (presentacion_id,),
            )
        else:
            presentacion_id = con.execute(
                """INSERT INTO presentaciones (clave, nombre, descripcion, libras_por_bolsa,
                   bolsas_por_fardo, fardos_por_tarima, activa)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                valores,
            ).fetchone()["id"]

        con.execute(
            "DELETE FROM linea_presentacion WHERE presentacion_id = %s", (presentacion_id,)
        )
        for linea_id in lineas_ids:
            con.execute(
                "INSERT INTO linea_presentacion VALUES (%s, %s)", (linea_id, presentacion_id)
            )
    return presentacion_id


# --- Tarimas ------------------------------------------------------------------

class ErrorRegistro(Exception):
    pass


def registrar_tarima(codigo_linea, presentacion_id, fardos=None, registro_por="Montacargas"):
    """Registra una tarima y regresa sus datos ya formateados.

    Todo pasa en una sola transacción:
    1. Se bloquea la fila de la línea (FOR UPDATE) para que dos tabletas no
       tomen el mismo folio al mismo tiempo.
    2. Se guarda la tarima.
    3. Se deja el envío a Google Sheets en la cola.
    """
    ahora = datetime.now().replace(microsecond=0)
    with db.conectar() as con:
        linea = con.execute(
            "SELECT * FROM lineas WHERE codigo = %s AND activa FOR UPDATE", (codigo_linea,)
        ).fetchone()
        if linea is None:
            raise ErrorRegistro("Línea no válida")

        p = con.execute(
            """SELECT p.* FROM presentaciones p
               JOIN linea_presentacion lp ON lp.presentacion_id = p.id
               WHERE p.id = %s AND lp.linea_id = %s AND p.activa""",
            (presentacion_id, linea["id"]),
        ).fetchone()
        if p is None:
            raise ErrorRegistro("Presentación no válida para esta línea")

        if fardos is None:
            fardos = p["fardos_por_tarima"]
        if not 1 <= fardos <= p["fardos_por_tarima"]:
            raise ErrorRegistro("Cantidad de fardos no válida")

        numero = linea["ultimo_folio"] + 1
        folio = f"{linea['codigo']}-{numero:06d}"
        bolsas = fardos * p["bolsas_por_fardo"]

        con.execute("UPDATE lineas SET ultimo_folio = %s WHERE id = %s", (numero, linea["id"]))
        con.execute(
            """INSERT INTO tarimas (folio, linea_id, numero, presentacion_id, presentacion,
                   descripcion, fecha_hora, turno, lote, fardos, bolsas, libras, completa,
                   registro_por)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                folio, linea["id"], numero, p["id"], p["nombre"], p["descripcion"],
                ahora, turno_actual(ahora), linea["lote_actual"] or "SIN LOTE",
                fardos, bolsas, bolsas * p["libras_por_bolsa"],
                fardos == p["fardos_por_tarima"], registro_por,
            ),
        )
        tarima = _formatear(
            con.execute(_SELECT_TARIMA + " WHERE t.folio = %s", (folio,)).fetchone()
        )
        if config.SHEETS_URL:
            con.execute(
                "INSERT INTO sheets_pendientes (mensaje) VALUES (%s)",
                (Jsonb({"accion": "agregar", "tarima": {c: tarima[c] for c in COLUMNAS}}),),
            )
    return tarima


def buscar_tarima(folio):
    with db.conectar() as con:
        fila = con.execute(_SELECT_TARIMA + " WHERE t.folio = %s", (folio,)).fetchone()
    return _formatear(fila) if fila else None


def impresora_de_tarima(folio):
    with db.conectar() as con:
        fila = con.execute(
            """SELECT l.impresora_ip FROM tarimas t JOIN lineas l ON l.id = t.linea_id
               WHERE t.folio = %s""",
            (folio,),
        ).fetchone()
    return fila["impresora_ip"] if fila else None


def anular_tarima(folio):
    """Marca la tarima como ANULADA (no se borra, para no perder el folio)."""
    with db.conectar() as con:
        cambio = con.execute(
            """UPDATE tarimas SET estado = 'ANULADA', anulada_en = now()
               WHERE folio = %s AND estado = 'OK'""",
            (folio,),
        ).rowcount
        if cambio and config.SHEETS_URL:
            con.execute(
                "INSERT INTO sheets_pendientes (mensaje) VALUES (%s)",
                (Jsonb({"accion": "anular", "folio": folio}),),
            )
    return cambio > 0


def ultimas(linea_id=None, cantidad=30):
    filtro, params = ("WHERE t.linea_id = %s", (linea_id,)) if linea_id else ("", ())
    with db.conectar() as con:
        filas = con.execute(
            _SELECT_TARIMA + f" {filtro} ORDER BY t.fecha_hora DESC, t.id DESC LIMIT %s",
            params + (cantidad,),
        ).fetchall()
    return [_formatear(f) for f in filas]


def resumen_turno():
    """Totales del turno en curso por línea: {linea_id: {...}} y el número de turno."""
    ahora = datetime.now()
    with db.conectar() as con:
        filas = con.execute(
            """SELECT linea_id, count(*) AS tarimas, sum(fardos) AS fardos, sum(libras) AS libras
               FROM tarimas WHERE estado = 'OK' AND fecha_hora >= %s
               GROUP BY linea_id""",
            (inicio_turno(ahora),),
        ).fetchall()
    por_linea = {
        f["linea_id"]: {
            "tarimas": f["tarimas"],
            "fardos": int(f["fardos"]),
            "libras": numero_limpio(f["libras"]),
        }
        for f in filas
    }
    return turno_actual(ahora), por_linea


# --- Excel --------------------------------------------------------------------

def exportar_excel(desde, hasta, linea_codigo=None):
    """Regresa un archivo Excel (en memoria) con las tarimas del rango de fechas."""
    filtro = "WHERE t.fecha_hora >= %s AND t.fecha_hora < %s"
    params = [desde, hasta + timedelta(days=1)]
    if linea_codigo:
        filtro += " AND l.codigo = %s"
        params.append(linea_codigo)

    with db.conectar() as con:
        filas = con.execute(
            _SELECT_TARIMA + f" {filtro} ORDER BY t.fecha_hora, t.id", params
        ).fetchall()

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Tarimas"
    hoja.append([c.replace("_", " ").upper() for c in COLUMNAS])
    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="1F4E78")

    rojo = PatternFill("solid", fgColor="F8CBAD")
    for fila in filas:
        t = _formatear(fila)
        hoja.append([t[c] for c in COLUMNAS])
        if t["estado"] == "ANULADA":
            for celda in hoja[hoja.max_row]:
                celda.fill = rojo

    anchos = [12, 12, 10, 7, 10, 13, 20, 14, 8, 8, 9, 10, 10, 14]
    for i, ancho in enumerate(anchos):
        hoja.column_dimensions[chr(65 + i)].width = ancho
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions

    archivo = io.BytesIO()
    libro.save(archivo)
    archivo.seek(0)
    return archivo
