"""
Configuración del sistema de registro de tarimas.

Aquí se cambia todo lo que puede variar en planta, sin tocar el resto del código.
"""

# Nombre de la línea (sale en la etiqueta y en el Excel)
LINEA = "Línea 4"
PREFIJO_FOLIO = "L4"  # El folio queda así: L4-000001

# Presentaciones que el montacarguista puede elegir en la tablet.
# Para agregar otra, copia un bloque y cambia los datos.
PRESENTACIONES = [
    {
        "clave": "4LB-F10",
        "nombre": "4 lb",
        "descripcion": "Fardo de 10 bolsas",
        "libras_por_bolsa": 4,
        "bolsas_por_fardo": 10,
        "fardos_por_tarima": 56,
    },
    # Ejemplo de otra presentación (quita el # para activarla):
    # {
    #     "clave": "2LB-F20",
    #     "nombre": "2 lb",
    #     "descripcion": "Fardo de 20 bolsas",
    #     "libras_por_bolsa": 2,
    #     "bolsas_por_fardo": 20,
    #     "fardos_por_tarima": 56,
    # },
]

# Turnos: (número de turno, hora de inicio, hora de fin) en formato 24 h.
TURNOS = [
    (1, 6, 14),
    (2, 14, 22),
    (3, 22, 6),  # cruza la medianoche
]

# --- Impresora -------------------------------------------------------------
# Si tienen una impresora de etiquetas con red (Zebra o compatible con ZPL),
# pon aquí su IP y la etiqueta sale directo, sin ventanas ni preguntas.
# Si se deja en None, se abre la etiqueta en el navegador para imprimirla
# con cualquier impresora.
IMPRESORA_IP = None        # ejemplo: "192.168.1.50"
IMPRESORA_PUERTO = 9100    # puerto estándar de impresoras Zebra
IMPRESORA_DPI = 203        # 203 o 300, según el modelo

# --- Archivos ---------------------------------------------------------------
CARPETA_DATOS = "datos"
ARCHIVO_CSV = "registro_tarimas.csv"     # respaldo que nunca se bloquea
ARCHIVO_EXCEL = "registro_tarimas.xlsx"  # el que abren en oficina
