"""
Genera e imprime la etiqueta (papeleta) de cada tarima.

Dos formas de imprimir:
1. Impresora de etiquetas con red (Zebra o compatible ZPL): se manda directo,
   sin ventanas. La IP de cada línea se captura en /admin.
2. Cualquier impresora: la tablet abre la etiqueta en el navegador y se imprime.
"""

import base64
import io
import socket

import qrcode

import config


def texto_qr(tarima):
    """Lo que lleva el código QR. Separado por | para leerlo fácil con un escáner."""
    return "|".join(
        str(tarima[c])
        for c in ("folio", "fecha", "hora", "linea", "presentacion", "lote", "fardos")
    )


def qr_base64(tarima):
    """Imagen PNG del QR en base64, para mostrarla en la etiqueta HTML."""
    imagen = qrcode.make(texto_qr(tarima), box_size=8, border=1)
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _sin_acentos(texto):
    # Las fuentes básicas de las impresoras Zebra no siempre traen acentos.
    cambios = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")
    return str(texto).translate(cambios)


def zpl(tarima):
    """Etiqueta de 4 x 6 pulgadas en lenguaje ZPL (impresoras Zebra)."""
    t = {k: _sin_acentos(v) for k, v in tarima.items()}
    puntos = config.IMPRESORA_DPI / 203  # escala para impresoras de 300 dpi
    def p(n):
        return int(n * puntos)

    estado = "TARIMA COMPLETA" if t["completa"] == "SI" else "TARIMA INCOMPLETA"
    return f"""^XA
^CI28
^PW{p(812)}
^LL{p(1218)}
^FO{p(40)},{p(40)}^A0N,{p(50)},{p(50)}^FD{t['linea']}^FS
^FO{p(40)},{p(100)}^A0N,{p(110)},{p(100)}^FD{t['folio']}^FS
^FO{p(40)},{p(230)}^GB{p(732)},4,4^FS
^FO{p(40)},{p(260)}^A0N,{p(70)},{p(70)}^FD{t['presentacion']} - {t['descripcion']}^FS
^FO{p(40)},{p(350)}^A0N,{p(55)},{p(55)}^FD{estado}^FS
^FO{p(40)},{p(430)}^A0N,{p(45)},{p(45)}^FDFardos: {t['fardos']}^FS
^FO{p(40)},{p(490)}^A0N,{p(45)},{p(45)}^FDBolsas: {t['bolsas']}^FS
^FO{p(40)},{p(550)}^A0N,{p(45)},{p(45)}^FDLibras: {t['libras']}^FS
^FO{p(40)},{p(630)}^A0N,{p(45)},{p(45)}^FDLote: {t['lote']}^FS
^FO{p(40)},{p(690)}^A0N,{p(40)},{p(40)}^FD{t['fecha']}  {t['hora']}  Turno {t['turno']}^FS
^FO{p(500)},{p(760)}^BQN,2,{p(9)}^FDLA,{_sin_acentos(texto_qr(tarima))}^FS
^XZ"""


def imprimir_directo(tarima, impresora_ip):
    """Manda la etiqueta a la impresora de red. Regresa (ok, mensaje)."""
    if not impresora_ip:
        return False, "No hay impresora de red configurada"
    try:
        with socket.create_connection(
            (impresora_ip, config.IMPRESORA_PUERTO), timeout=5
        ) as conexion:
            conexion.sendall(zpl(tarima).encode("utf-8"))
        return True, "Etiqueta enviada a la impresora"
    except OSError as error:
        return False, f"No se pudo imprimir: {error}"
