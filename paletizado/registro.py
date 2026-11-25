"""
Toda la lógica de tarimas, líneas, presentaciones y personal sobre PostgreSQL.
"""

import io
from datetime import datetime, timedelta
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from psycopg.types.json import Jsonb

import config
import db

# Columnas que se exportan a Excel y se mandan a Google Sheets, en este orden.
# Las primeras son las mismas del formulario de Google que usaban antes.
ENCABEZADOS = [
    ("fecha", "Fecha"),
    ("turno", "Shift"),
    ("producto", "Product"),
    ("color", "Color"),
    ("lote", "Lot No."),
    ("numero_pallet", "Finished Pallet No."),
    ("fardos", "Count of bales per Pallet"),
    ("libras", "Weight (Lb)"),
    ("lote_film", "Lot Packaging Material / Bag film"),
    ("lote_bale", "Lot Packaging Material / Bale"),
    ("operador_produccion", "Production Operator"),
    ("montacarguista", "Forklift Operator"),
    ("supervisor", "Shift Supervisor"),
    ("estibadores", "Estibador"),
    ("comentarios", "Comentarios"),
    ("hora", "Hora"),
    ("linea", "Línea"),
    ("folio", "Folio"),
    ("bolsas", "Bolsas"),
    ("completa", "Completa"),
    ("estado", "Estado"),
]
COLUMNAS = [clave for clave, _ in ENCABEZADOS]

ROLES = {
    "montacargas": "Montacargas (Forklift Operator)",
    "operador": "Operador de producción",
    "supervisor": "Supervisor de turno",
    "estibador": "Estibador",
}


# --- Turnos y lote ------------------------------------------------------------

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


def lote_automatico(momento):
    """Planta + día juliano + año. 16/nov/2026 -> 0232026."""
    dia = momento if config.LOTE_CAMBIA == "medianoche" else inicio_turno(momento)
    return f"{config.CODIGO_PLANTA}{dia.timetuple().tm_yday:03d}{dia:%y}"


def lote_de_linea(linea, momento=None):
    """El lote manual de la línea si lo capturaron; si no, el automático."""
    return linea["lote_actual"] or lote_automatico(momento or datetime.now())


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
    t["numero_pallet"] = t["numero_pallet"] if t["numero_pallet"] is not None else ""
    t["producto"] = f"{t['codigo_sap']} {t['descripcion']}".strip()
    return t


_SELECT_TARIMA = """
    SELECT t.folio, t.fecha_hora, t.turno, l.nombre AS linea, l.codigo AS linea_codigo,
           t.presentacion, t.descripcion, t.codigo_sap, t.lote, t.numero_pallet,
           t.fardos, t.bolsas, t.libras, t.completa, t.estado, t.color,
           t.lote_film, t.lote_bale, t.operador_produccion, t.montacarguista,
           t.supervisor, t.estibadores, t.comentarios, t.registro_por
    FROM tarimas t JOIN lineas l ON l.id = t.linea_id
"""


# --- Líneas y corrida -----------------------------------------------------------

def lineas(solo_activas=True):
    with db.conectar() as con:
        filtro = "WHERE activa" if solo_activas else ""
        return con.execute(f"SELECT * FROM lineas {filtro} ORDER BY codigo").fetchall()


def linea_por_codigo(codigo):
    with db.conectar() as con:
        return con.execute(
            "SELECT * FROM lineas WHERE codigo = %s", (codigo,)
        ).fetchone()


def guardar_corrida(codigo, datos, estibadores):
    """Datos que el operador captura una vez y se copian a cada tarima."""
    with db.conectar() as con:
        con.execute(
            """UPDATE lineas SET lote_actual = %s, color_actual = %s, lote_film = %s,
                   lote_bale = %s, operador_produccion = %s, supervisor = %s, estibadores = %s
               WHERE codigo = %s""",
            (
                datos.get("lote_manual", "").strip().upper(),
                datos.get("color", "").strip(),
                datos.get("lote_film", "").strip(),
                datos.get("lote_bale", "").strip(),
                datos.get("operador_produccion", "").strip(),
                datos.get("supervisor", "").strip(),
                ", ".join(e.strip() for e in estibadores if e.strip()),
                codigo,
            ),
        )


def lotes_material_recientes(columna, dias=60):
    """Lotes de film o de bale usados últimamente, para sugerirlos en la pantalla."""
    if columna not in ("lote_film", "lote_bale"):
        raise ValueError(columna)
    with db.conectar() as con:
        filas = con.execute(
            f"""SELECT {columna} AS valor, max(fecha_hora) AS ultimo FROM tarimas
                WHERE {columna} <> '' AND fecha_hora > now() - %s * interval '1 day'
                GROUP BY {columna} ORDER BY ultimo DESC LIMIT 15""",
            (dias,),
        ).fetchall()
    return [f["valor"] for f in filas]


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


# --- Personal -------------------------------------------------------------------

def personas(rol=None, solo_activas=True):
    condiciones, params = [], []
    if rol:
        condiciones.append("rol = %s")
        params.append(rol)
    if solo_activas:
        condiciones.append("activa")
    filtro = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with db.conectar() as con:
        return con.execute(
            f"SELECT * FROM personas {filtro} ORDER BY rol, nombre", params
        ).fetchall()


def agregar_persona(nombre, rol):
    nombre = " ".join(nombre.split())
    if not nombre or rol not in ROLES:
        raise ValueError("Nombre o puesto no válido")
    with db.conectar() as con:
        con.execute(
            """INSERT INTO personas (nombre, rol) VALUES (%s, %s)
               ON CONFLICT (nombre, rol) DO UPDATE SET activa = TRUE""",
            (nombre, rol),
        )


def cambiar_persona_activa(persona_id, activa):
    with db.conectar() as con:
        con.execute("UPDATE personas SET activa = %s WHERE id = %s", (activa, persona_id))


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
        datos.get("codigo_sap", "").strip(),
        Decimal(str(datos["libras_por_bolsa"])),
        int(datos["bolsas_por_fardo"]),
        int(datos["fardos_por_tarima"]),
        bool(datos.get("activa")),
    )
    with db.conectar() as con:
        if presentacion_id:
            con.execute(
                """UPDATE presentaciones SET clave=%s, nombre=%s, descripcion=%s, codigo_sap=%s,
                   libras_por_bolsa=%s, bolsas_por_fardo=%s, fardos_por_tarima=%s, activa=%s
                   WHERE id=%s""",
                valores + (presentacion_id,),
            )
        else:
            presentacion_id = con.execute(
                """INSERT INTO presentaciones (clave, nombre, descripcion, codigo_sap,
                   libras_por_bolsa, bolsas_por_fardo, fardos_por_tarima, activa)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
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


def registrar_tarima(codigo_linea, presentacion_id, fardos=None,
                     montacarguista="", comentarios=""):
    """Registra una tarima y regresa sus datos ya formateados.

    Todo pasa en una sola transacción:
    1. Se bloquea la fila de la línea (FOR UPDATE) para que dos tabletas no
       tomen el mismo número al mismo tiempo.
    2. Se calcula el número de tarima del turno (1, 2, 3…) y el lote.
    3. Se guarda la tarima con los datos de la corrida (color, lotes de
       material, operador, supervisor, estibadores).
    4. Se deja el envío a Google Sheets en la cola.
    """
    ahora = datetime.now().replace(microsecond=0)
    turno = turno_actual(ahora)
    fecha_turno = inicio_turno(ahora).date()

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

        # Número de tarima del turno: el más alto del turno + 1.
        # Las anuladas cuentan, para que nunca se repita un número ya impreso.
        numero_pallet = con.execute(
            """SELECT coalesce(max(numero_pallet), 0) + 1 AS n FROM tarimas
               WHERE linea_id = %s AND fecha_turno = %s AND turno = %s""",
            (linea["id"], fecha_turno, turno),
        ).fetchone()["n"]

        numero = linea["ultimo_folio"] + 1
        folio = f"{linea['codigo']}-{numero:06d}"
        bolsas = fardos * p["bolsas_por_fardo"]
        montacarguista = " ".join(montacarguista.split())

        con.execute("UPDATE lineas SET ultimo_folio = %s WHERE id = %s", (numero, linea["id"]))
        con.execute(
            """INSERT INTO tarimas (folio, linea_id, numero, presentacion_id, presentacion,
                   descripcion, codigo_sap, fecha_hora, fecha_turno, turno, numero_pallet,
                   lote, fardos, bolsas, libras, completa, color, lote_film, lote_bale,
                   operador_produccion, montacarguista, supervisor, estibadores,
                   comentarios, registro_por)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                folio, linea["id"], numero, p["id"], p["nombre"], p["descripcion"],
                p["codigo_sap"], ahora, fecha_turno, turno, numero_pallet,
                lote_de_linea(linea, ahora), fardos, bolsas, bolsas * p["libras_por_bolsa"],
                fardos == p["fardos_por_tarima"], linea["color_actual"], linea["lote_film"],
                linea["lote_bale"], linea["operador_produccion"], montacarguista,
                linea["supervisor"], linea["estibadores"], comentarios.strip()[:500],
                montacarguista or "Montacargas",
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


# --- Resumen por turno -------------------------------------------------------

LB_TON_METRICA = 2204.62   # libras en una tonelada métrica

ENCABEZADOS_TURNO = [
    ("fecha", "Fecha"), ("turno", "Turno"), ("linea", "Línea"), ("tarimas", "Tarimas"),
    ("incompletas", "Tarimas incompletas"), ("fardos", "Fardos"), ("libras", "Libras"),
    ("ton_metricas", "Toneladas métricas"),
    ("anuladas", "Tarimas anuladas"),
]


def resumen_por_turno(desde, hasta, linea_codigo=None):
    """Tarimas y toneladas de cada turno (por el día en que empezó el turno).
    Las anuladas no cuentan en las cantidades; se reportan aparte."""
    filtro = "WHERE t.fecha_turno >= %s AND t.fecha_turno <= %s"
    params = [desde, hasta]
    if linea_codigo:
        filtro += " AND l.codigo = %s"
        params.append(linea_codigo)
    with db.conectar() as con:
        filas = con.execute(
            f"""SELECT t.fecha_turno, t.turno, l.nombre AS linea,
                       count(*) FILTER (WHERE t.estado = 'OK') AS tarimas,
                       count(*) FILTER (WHERE t.estado = 'OK' AND NOT t.completa) AS incompletas,
                       coalesce(sum(t.fardos) FILTER (WHERE t.estado = 'OK'), 0) AS fardos,
                       coalesce(sum(t.libras) FILTER (WHERE t.estado = 'OK'), 0) AS libras,
                       count(*) FILTER (WHERE t.estado = 'ANULADA') AS anuladas
                FROM tarimas t JOIN lineas l ON l.id = t.linea_id
                {filtro}
                GROUP BY t.fecha_turno, t.turno, l.nombre
                ORDER BY t.fecha_turno DESC, t.turno DESC, l.nombre""",
            params,
        ).fetchall()
    resultado = []
    for f in filas:
        libras = numero_limpio(f["libras"])
        resultado.append({
            "fecha": f["fecha_turno"].strftime("%Y-%m-%d"), "turno": f["turno"], "linea": f["linea"],
            "tarimas": f["tarimas"], "incompletas": f["incompletas"], "fardos": int(f["fardos"]),
            "libras": libras,
            "ton_metricas": round(float(libras) / LB_TON_METRICA, 2),
            "anuladas": f["anuladas"],
        })
    return resultado


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
    hoja.append([titulo for _, titulo in ENCABEZADOS])
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

    for columna in hoja.columns:
        letra = columna[0].column_letter
        largo = max(len(str(c.value or "")) for c in columna)
        hoja.column_dimensions[letra].width = min(max(10, largo + 2), 45)
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions

    # Segunda hoja: tarimas y toneladas por turno
    turnos = libro.create_sheet("Resumen por turno")
    turnos.append([titulo for _, titulo in ENCABEZADOS_TURNO])
    for celda in turnos[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="1F4E78")
    for r in resumen_por_turno(desde.date(), hasta.date(), linea_codigo):
        turnos.append([r[c] for c, _ in ENCABEZADOS_TURNO])
    for columna in turnos.columns:
        largo = max(len(str(c.value or "")) for c in columna)
        turnos.column_dimensions[columna[0].column_letter].width = min(max(10, largo + 2), 32)
    turnos.freeze_panes = "A2"

    archivo = io.BytesIO()
    libro.save(archivo)
    archivo.seek(0)
    return archivo
