"""
Prepara la base de datos PostgreSQL.

    python init_db.py                          crea las tablas y datos iniciales
    python init_db.py --importar archivo.csv   además pasa tarimas de la versión anterior (CSV)

Se puede correr las veces que sea: no borra ni duplica nada.
"""

import argparse
import csv
import os
from datetime import datetime
from decimal import Decimal

import db

CARPETA = os.path.dirname(os.path.abspath(__file__))


def crear_tablas(con):
    with open(os.path.join(CARPETA, "esquema.sql"), encoding="utf-8") as f:
        con.execute(f.read())
    print("Tablas listas.")


def datos_iniciales(con):
    """Si la base está vacía, da de alta las 6 líneas y la presentación 10/4 lb."""
    if con.execute("SELECT count(*) AS n FROM lineas").fetchone()["n"] == 0:
        for n in range(1, 7):
            con.execute(
                "INSERT INTO lineas (codigo, nombre) VALUES (%s, %s)", (f"L{n}", f"Línea {n}")
            )
        print("Se dieron de alta las líneas L1 a L6.")

    if con.execute("SELECT count(*) AS n FROM presentaciones").fetchone()["n"] == 0:
        pid = con.execute(
            """INSERT INTO presentaciones (clave, nombre, descripcion, codigo_sap,
                   libras_por_bolsa, bolsas_por_fardo, fardos_por_tarima)
               VALUES ('25000307', '10/4 lb', 'ZULKA PURE CANE SUGAR 10/4 LBS', '25000307',
                       4, 10, 56) RETURNING id"""
        ).fetchone()["id"]
        con.execute(
            """INSERT INTO linea_presentacion (linea_id, presentacion_id)
               SELECT id, %s FROM lineas WHERE codigo = 'L4'""",
            (pid,),
        )
        print("Se dio de alta la presentación 25000307 ZULKA PURE CANE SUGAR 10/4 LBS (asignada a L4).")
        print("Las demás presentaciones se dan de alta en /admin.")


def importar_csv(con, ruta):
    """Pasa las tarimas del CSV de la versión anterior (una sola línea)."""
    importadas = 0
    with open(ruta, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            if con.execute(
                "SELECT 1 FROM tarimas WHERE folio = %s", (fila["folio"],)
            ).fetchone():
                continue  # ya estaba

            codigo = fila["folio"].split("-")[0]
            linea = con.execute(
                "SELECT id FROM lineas WHERE codigo = %s", (codigo,)
            ).fetchone()
            if linea is None:
                linea = con.execute(
                    "INSERT INTO lineas (codigo, nombre) VALUES (%s, %s) RETURNING id",
                    (codigo, fila["linea"]),
                ).fetchone()

            fardos, bolsas = int(fila["fardos"]), int(fila["bolsas"])
            pres = con.execute(
                "SELECT id FROM presentaciones WHERE nombre = %s AND descripcion = %s",
                (fila["presentacion"], fila["descripcion"]),
            ).fetchone()
            if pres is None:
                print(f"  Se omite {fila['folio']}: no existe la presentación "
                      f"'{fila['presentacion']} - {fila['descripcion']}'. Dala de alta y vuelve a importar.")
                continue

            numero = int(fila["folio"].split("-")[-1])
            con.execute(
                """INSERT INTO tarimas (folio, linea_id, numero, presentacion_id, presentacion,
                       descripcion, fecha_hora, turno, lote, fardos, bolsas, libras, completa,
                       estado, registro_por)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    fila["folio"], linea["id"], numero, pres["id"], fila["presentacion"],
                    fila["descripcion"],
                    datetime.strptime(f"{fila['fecha']} {fila['hora']}", "%Y-%m-%d %H:%M:%S"),
                    int(fila["turno"]), fila["lote"], fardos, bolsas, Decimal(fila["libras"]),
                    fila["completa"] == "SI", fila["estado"], fila.get("registro_por") or "Montacargas",
                ),
            )
            # Que el consecutivo siga después del folio más alto importado
            con.execute(
                "UPDATE lineas SET ultimo_folio = GREATEST(ultimo_folio, %s) WHERE id = %s",
                (numero, linea["id"]),
            )
            importadas += 1
    print(f"Tarimas importadas del CSV: {importadas}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepara la base de datos de tarimas")
    parser.add_argument("--importar", metavar="CSV", help="CSV de la versión anterior")
    args = parser.parse_args()

    with db.conectar() as con:
        crear_tablas(con)
        datos_iniciales(con)
        if args.importar:
            importar_csv(con, args.importar)
    print("Base de datos lista.")
