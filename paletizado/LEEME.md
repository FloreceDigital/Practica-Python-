# Registro de tarimas – Línea 4

El montacarguista, en el flejado, toca la presentación en la tablet, confirma, y **sale la etiqueta**.
El registro se guarda solo en Excel. El operador de línea ve el avance del turno sin moverse de su puesto.

## Flujo
1. **Operador** (una vez por corrida): abre `/operador` y captura el **lote**.
2. **Montacarguista** (cada tarima): en la tablet toca **4 lb** → **IMPRIMIR ETIQUETA**.
3. Sale la etiqueta con folio consecutivo, QR, fecha, hora, turno, lote, fardos, bolsas y libras.
4. Se pega en la tarima ya flejada y se la lleva.

Extras en la tablet: **Tarima incompleta** (eliges cuántos fardos), **Reimprimir** y **Anular**.
Las tarimas anuladas no se borran: quedan en rojo en el Excel para no perder el folio.

## Instalación (en una computadora o mini PC de la planta)
```bash
pip install -r requirements.txt
python app.py
```
En la tablet, abrir en el navegador: `http://IP-DE-LA-COMPUTADORA:5000`
(la tablet y la computadora deben estar en la misma red WiFi).

| Dirección | Para quién |
|---|---|
| `/` | Tablet del montacargas |
| `/operador` | Operador de línea: lote, resumen del turno, últimas tarimas |
| `/excel` | Descargar el Excel |

## Impresora
- **Sin impresora de etiquetas**: la tablet abre la etiqueta (4×6") y se imprime con la impresora que tengan.
- **Con impresora de etiquetas en red (Zebra o compatible ZPL)**: poner su IP en `config.py`
  (`IMPRESORA_IP = "192.168.1.50"`). La etiqueta sale **directo, sin ventanas**.

## Datos
Se guardan en la carpeta `datos/`:
- `registro_tarimas.csv`: registro principal (no se bloquea aunque alguien tenga el Excel abierto).
- `registro_tarimas.xlsx`: se regenera en cada tarima. Si alguien lo tiene abierto, se actualiza en la siguiente.

## Cambiar presentaciones, turnos o línea
Todo está en `config.py`.
