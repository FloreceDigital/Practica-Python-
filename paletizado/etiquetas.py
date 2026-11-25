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
        for c in ("folio", "codigo_sap", "lote", "numero_pallet", "fardos", "libras", "fecha", "turno")
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

    incompleta = "" if t["completa"] == "SI" else (
        f"^FO{p(40)},{p(520)}^A0N,{p(40)},{p(40)}^FR^GB{p(732)},{p(50)},{p(50)}^FS"
        f"^FO{p(60)},{p(526)}^A0N,{p(40)},{p(40)}^FR^FDTARIMA INCOMPLETA^FS"
    )
    return f"""^XA
^CI28
^PW{p(812)}
^LL{p(1218)}
^FO{p(40)},{p(40)}^A0N,{p(36)},{p(36)}^FD{t['linea']}^FS
^FO{p(560)},{p(40)}^A0N,{p(36)},{p(36)}^FDTurno {t['turno']}^FS
^FO{p(40)},{p(100)}^A0N,{p(36)},{p(36)}^FDPALLET^FS
^FO{p(200)},{p(80)}^A0N,{p(190)},{p(170)}^FD{t['numero_pallet']}^FS
^FO{p(40)},{p(290)}^A0N,{p(36)},{p(36)}^FDLOT^FS
^FO{p(140)},{p(270)}^A0N,{p(90)},{p(80)}^FD{t['lote']}^FS
^FO{p(40)},{p(380)}^GB{p(732)},4,4^FS
^FO{p(40)},{p(410)}^A0N,{p(40)},{p(36)}^FB{p(732)},2,0,L^FD{t['codigo_sap']} {t['descripcion']}^FS
{incompleta}
^FO{p(40)},{p(600)}^A0N,{p(42)},{p(42)}^FDFardos: {t['fardos']}^FS
^FO{p(420)},{p(600)}^A0N,{p(42)},{p(42)}^FDColor: {t['color'] or '-'}^FS
^FO{p(40)},{p(660)}^A0N,{p(42)},{p(42)}^FDLibras: {t['libras']}^FS
^FO{p(420)},{p(660)}^A0N,{p(42)},{p(42)}^FDBolsas: {t['bolsas']}^FS
^FO{p(40)},{p(1000)}^A0N,{p(34)},{p(34)}^FD{t['fecha']} {t['hora'][:5]}^FS
^FO{p(40)},{p(1045)}^A0N,{p(34)},{p(34)}^FD{t['folio']}^FS
^FO{p(500)},{p(860)}^BQN,2,{p(7)}^FDLA,{_sin_acentos(texto_qr(tarima))}^FS
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
