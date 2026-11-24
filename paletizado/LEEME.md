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

## Conectar a Google Sheets de la empresa
Cada tarima se manda también a una hoja de Google Sheets. Se configura una sola vez:

1. Abre la hoja de Google Sheets donde quieren las tarimas.
2. Menú **Extensiones → Apps Script**. Borra lo que haya y pega el contenido de `apps_script.gs`.
3. En la línea `const CLAVE = "cambia-esta-clave";` pon una palabra secreta.
4. Guarda y ve a **Implementar → Nueva implementación → Aplicación web**:
   - Ejecutar como: **Yo**
   - Quién tiene acceso: **Cualquier usuario**
5. Autoriza los permisos y copia la URL que termina en `/exec`.
6. En `config.py`:
   ```python
   SHEETS_URL = "https://script.google.com/macros/s/XXXX/exec"
   SHEETS_CLAVE = "la-misma-palabra-secreta"
   ```
7. Reinicia la app (`python app.py`).

Las tarimas se registran en una pestaña llamada **Tarimas** (se crea sola).
Las anuladas se marcan en rojo; un reenvío nunca duplica el folio.

**Si se cae el internet**: la etiqueta se imprime igual, la tarima queda guardada en la computadora
y se sube sola a Sheets cuando regresa la conexión (se revisa cada minuto).
En `/operador` se ve si hay tarimas "por subir".

> La computadora de la planta necesita salida a internet hacia `script.google.com`.
> Si la empresa usa Google Workspace, puede que TI deba permitir la "Aplicación web";
> en ese caso elige "Cualquier usuario de [tu empresa]" solo si la computadora entra con una cuenta de la empresa,
> si no, debe ser "Cualquier usuario" (la palabra secreta protege la hoja).

## Datos
Se guardan en la carpeta `datos/`:
- `registro_tarimas.csv`: registro principal (no se bloquea aunque alguien tenga el Excel abierto).
- `registro_tarimas.xlsx`: se regenera en cada tarima. Si alguien lo tiene abierto, se actualiza en la siguiente.

## Cambiar presentaciones, turnos o línea
Todo está en `config.py`.
