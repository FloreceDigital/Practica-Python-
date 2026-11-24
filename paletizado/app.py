"""
Registro de tarimas - Línea 4

Pantallas:
  /           -> Tablet del montacargas: elige presentación y sale la etiqueta.
  /operador   -> Operador de línea: define el lote y ve el resumen del turno.
  /excel      -> Descarga el Excel con todas las tarimas.

Si SHEETS_URL está configurado en config.py, cada tarima también se manda
a la hoja de Google Sheets de la empresa.

Para arrancar:  python app.py
Luego en la tablet abrir:  http://IP-DE-ESTA-COMPUTADORA:5000
"""

import json
import os

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

import config
import etiquetas
import registro
import sheets

app = Flask(__name__)
ARCHIVO_CORRIDA = os.path.join(config.CARPETA_DATOS, "corrida.json")


# --- Lote de la corrida (lo define el operador una vez) ---------------------

def leer_lote():
    try:
        with open(ARCHIVO_CORRIDA, encoding="utf-8") as f:
            return json.load(f).get("lote", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def guardar_lote(lote):
    os.makedirs(config.CARPETA_DATOS, exist_ok=True)
    with open(ARCHIVO_CORRIDA, "w", encoding="utf-8") as f:
        json.dump({"lote": lote}, f)


# --- Pantallas --------------------------------------------------------------

@app.route("/")
def montacargas():
    return render_template(
        "montacargas.html",
        presentaciones=config.PRESENTACIONES,
        lote=leer_lote(),
        linea=config.LINEA,
        impresora_red=bool(config.IMPRESORA_IP),
        resumen=registro.resumen_turno(),
    )


@app.route("/operador", methods=["GET", "POST"])
def operador():
    if request.method == "POST":
        guardar_lote(request.form.get("lote", "").strip().upper())
        return redirect(url_for("operador"))

    ultimas = list(reversed(registro.leer_todas()))[:30]
    return render_template(
        "operador.html",
        lote=leer_lote(),
        linea=config.LINEA,
        resumen=registro.resumen_turno(),
        ultimas=ultimas,
        sheets_activo=sheets.activo(),
        sheets_pendientes=sheets.pendientes(),
    )


@app.route("/etiqueta/<folio>")
def etiqueta(folio):
    tarima = registro.buscar_tarima(folio)
    if tarima is None:
        return "Tarima no encontrada", 404
    return render_template(
        "etiqueta.html",
        t=tarima,
        qr=etiquetas.qr_base64(tarima),
        auto=request.args.get("auto") == "1",
    )


@app.route("/excel")
def descargar_excel():
    registro.actualizar_excel()
    ruta = os.path.join(config.CARPETA_DATOS, config.ARCHIVO_EXCEL)
    return send_file(os.path.abspath(ruta), as_attachment=True)


# --- Acciones (las llama la tablet) -----------------------------------------

def _imprimir(tarima):
    """Imprime directo si hay impresora de red; si no, la tablet abrirá la etiqueta."""
    if config.IMPRESORA_IP:
        ok, mensaje = etiquetas.imprimir_directo(tarima)
        return {"impreso": ok, "mensaje": mensaje}
    return {"impreso": False, "mensaje": "abrir_etiqueta"}


@app.post("/api/tarima")
def api_registrar():
    datos = request.get_json(force=True)
    presentacion = registro.buscar_presentacion(datos.get("clave"))
    if presentacion is None:
        return jsonify(error="Presentación no válida"), 400

    fardos = datos.get("fardos")
    if fardos is not None:
        fardos = int(fardos)
        if not 1 <= fardos <= presentacion["fardos_por_tarima"]:
            return jsonify(error="Cantidad de fardos no válida"), 400

    tarima = registro.registrar_tarima(presentacion, leer_lote() or "SIN LOTE", fardos)
    sheets.agregar(tarima)
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
        sheets.anular(folio)
        return jsonify(ok=True)
    return jsonify(error="Tarima no encontrada"), 404


if __name__ == "__main__":
    sheets.iniciar_reintentos()
    # host="0.0.0.0" permite que la tablet se conecte por la red de la planta.
    app.run(host="0.0.0.0", port=5000, debug=False)
