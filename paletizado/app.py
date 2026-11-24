"""
Registro de tarimas - todas las líneas.

Pantallas:
  /                    -> Tablet: elegir línea (si una tablet atiende varias líneas).
  /linea/L4            -> Tablet del montacargas para la Línea 4.
  /operador/L4         -> Operador de la Línea 4: lote, resumen del turno, últimas tarimas.
  /resumen             -> Todas las líneas del turno + descarga de Excel.
  /admin               -> Líneas, presentaciones e impresoras (pide usuario y contraseña).

Para arrancar:  python app.py
Luego en la tablet abrir:  http://IP-DEL-SERVIDOR:5000
"""

import hmac
from datetime import date, datetime

from flask import (
    Flask, Response, abort, jsonify, redirect, render_template, request, send_file, url_for,
)

import config
import etiquetas
import registro
import sheets

app = Flask(__name__)


# --- Pantallas de la tablet ---------------------------------------------------

@app.route("/")
def inicio():
    activas = registro.lineas()
    if len(activas) == 1:
        return redirect(url_for("montacargas", codigo=activas[0]["codigo"]))
    turno, totales = registro.resumen_turno()
    return render_template("inicio.html", lineas=activas, turno=turno, totales=totales)


@app.route("/linea/<codigo>")
def montacargas(codigo):
    linea = registro.linea_por_codigo(codigo)
    if linea is None or not linea["activa"]:
        abort(404)
    turno, totales = registro.resumen_turno()
    return render_template(
        "montacargas.html",
        linea=linea,
        presentaciones=registro.presentaciones_de_linea(linea["id"]),
        turno=turno,
        total=totales.get(linea["id"], {}).get("tarimas", 0),
        varias_lineas=len(registro.lineas()) > 1,
    )


# --- Operador y supervisión ---------------------------------------------------

@app.route("/operador/<codigo>", methods=["GET", "POST"])
def operador(codigo):
    linea = registro.linea_por_codigo(codigo)
    if linea is None:
        abort(404)
    if request.method == "POST":
        registro.guardar_lote(codigo, request.form.get("lote", ""))
        return redirect(url_for("operador", codigo=codigo))

    turno, totales = registro.resumen_turno()
    return render_template(
        "operador.html",
        linea=linea,
        turno=turno,
        resumen=totales.get(linea["id"], {"tarimas": 0, "fardos": 0, "libras": 0}),
        ultimas=registro.ultimas(linea["id"]),
        sheets_activo=sheets.activo(),
        sheets_pendientes=sheets.pendientes(),
    )


@app.route("/operador")
def operador_sin_linea():
    return redirect(url_for("resumen"))


@app.route("/resumen")
def resumen():
    turno, totales = registro.resumen_turno()
    todas = registro.lineas()
    general = {
        "tarimas": sum(t["tarimas"] for t in totales.values()),
        "fardos": sum(t["fardos"] for t in totales.values()),
        "libras": sum(t["libras"] for t in totales.values()),
    }
    return render_template(
        "resumen.html",
        lineas=todas,
        turno=turno,
        totales=totales,
        general=general,
        hoy=date.today().isoformat(),
        sheets_activo=sheets.activo(),
        sheets_pendientes=sheets.pendientes(),
    )


@app.route("/excel")
def descargar_excel():
    try:
        desde = datetime.strptime(request.args.get("desde", ""), "%Y-%m-%d")
        hasta = datetime.strptime(request.args.get("hasta", ""), "%Y-%m-%d")
    except ValueError:
        desde = hasta = datetime.combine(date.today(), datetime.min.time())
    linea = request.args.get("linea") or None
    archivo = registro.exportar_excel(desde, hasta, linea)
    nombre = f"tarimas_{linea or 'todas'}_{desde:%Y%m%d}_{hasta:%Y%m%d}.xlsx"
    return send_file(archivo, as_attachment=True, download_name=nombre)


@app.route("/etiqueta/<folio>")
def etiqueta(folio):
    tarima = registro.buscar_tarima(folio)
    if tarima is None:
        abort(404)
    return render_template(
        "etiqueta.html",
        t=tarima,
        qr=etiquetas.qr_base64(tarima),
        auto=request.args.get("auto") == "1",
        volver=request.args.get("volver", ""),
    )


# --- Acciones (las llama la tablet) -----------------------------------------

def _imprimir(tarima):
    """Imprime directo si la línea tiene impresora de red; si no, la tablet abre la etiqueta."""
    ip = registro.impresora_de_tarima(tarima["folio"])
    if ip:
        ok, mensaje = etiquetas.imprimir_directo(tarima, ip)
        return {"impreso": ok, "mensaje": mensaje}
    return {"impreso": False, "mensaje": "abrir_etiqueta"}


@app.post("/api/tarima")
def api_registrar():
    datos = request.get_json(force=True)
    fardos = datos.get("fardos")
    try:
        tarima = registro.registrar_tarima(
            datos.get("linea", ""),
            int(datos.get("presentacion_id", 0)),
            int(fardos) if fardos is not None else None,
        )
    except (registro.ErrorRegistro, ValueError) as error:
        return jsonify(error=str(error)), 400
    sheets.avisar()
    return jsonify(tarima=tarima, **_imprimir(tarima))


@app.post("/api/reimprimir/<folio>")
def api_reimprimir(folio):
    tarima = registro.buscar_tarima(folio)
    if tarima is None:
        return jsonify(error="Tarima no encontrada"), 404
    return jsonify(tarima=tarima, **_imprimir(tarima))


@app.post("/api/anular/<folio>")
def api_anular(folio):
    if registro.anular_tarima(folio):
        sheets.avisar()
        return jsonify(ok=True)
    return jsonify(error="Tarima no encontrada o ya anulada"), 404


# --- Administración -----------------------------------------------------------

@app.before_request
def proteger_admin():
    if not request.path.startswith("/admin"):
        return None
    auth = request.authorization
    if (
        auth
        and hmac.compare_digest(auth.username or "", config.ADMIN_USUARIO)
        and hmac.compare_digest(auth.password or "", config.ADMIN_CONTRASENA)
    ):
        return None
    return Response(
        "Se necesita usuario y contraseña", 401,
        {"WWW-Authenticate": 'Basic realm="Administracion de tarimas"'},
    )


@app.route("/admin")
def admin():
    return render_template(
        "admin.html",
        lineas=registro.lineas(solo_activas=False),
        presentaciones=registro.presentaciones(solo_activas=False),
        asignaciones=registro.asignaciones(),
        mensaje=request.args.get("mensaje", ""),
    )


@app.route("/admin/linea", methods=["GET", "POST"])
@app.route("/admin/linea/<int:linea_id>", methods=["GET", "POST"])
def admin_linea(linea_id=None):
    if request.method == "POST":
        try:
            registro.guardar_linea(request.form, linea_id)
        except Exception as error:
            return redirect(url_for("admin", mensaje=f"No se guardó la línea: {error}"))
        return redirect(url_for("admin", mensaje="Línea guardada"))
    linea = None
    if linea_id:
        linea = next((l for l in registro.lineas(False) if l["id"] == linea_id), None)
    return render_template("admin_linea.html", linea=linea)


@app.route("/admin/presentacion", methods=["GET", "POST"])
@app.route("/admin/presentacion/<int:presentacion_id>", methods=["GET", "POST"])
def admin_presentacion(presentacion_id=None):
    if request.method == "POST":
        lineas_ids = [int(x) for x in request.form.getlist("lineas")]
        try:
            registro.guardar_presentacion(request.form, lineas_ids, presentacion_id)
        except Exception as error:
            return redirect(url_for("admin", mensaje=f"No se guardó la presentación: {error}"))
        return redirect(url_for("admin", mensaje="Presentación guardada"))

    presentacion = None
    if presentacion_id:
        presentacion = next(
            (p for p in registro.presentaciones(False) if p["id"] == presentacion_id), None
        )
    asignadas = {
        lid for lid, pids in registro.asignaciones().items() if presentacion_id in pids
    }
    return render_template(
        "admin_presentacion.html",
        p=presentacion,
        lineas=registro.lineas(solo_activas=False),
        asignadas=asignadas,
    )


if __name__ == "__main__":
    sheets.iniciar_reintentos()
    # host="0.0.0.0" permite que las tabletas se conecten por la red de la planta.
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
