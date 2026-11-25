# Registro de tarimas – todas las líneas

El montacarguista toca en la tablet la línea y la presentación, confirma, y **sale la etiqueta**.
Todo se guarda en **PostgreSQL**. El operador de cada línea ve su avance sin moverse, y la
oficina puede descargar el Excel o verlo en Google Sheets.

## Flujo
1. **Operador de línea** (una vez por corrida): abre `/operador/L4` y captura el **lote**.
2. **Montacarguista** (cada tarima):
   - Tablet fija en una línea: abre `/linea/L4` → toca la presentación → **IMPRIMIR ETIQUETA**.
   - Tablet que atiende varias líneas (flejado compartido): abre `/` → toca la línea → la presentación → **IMPRIMIR**.
     Al terminar regresa sola a la lista de líneas.
3. Sale la etiqueta con folio consecutivo **por línea** (L1-000001, L4-000001…), QR, fecha, hora, turno, lote y cantidades.

En la tablet también hay botones para **tarima incompleta** (eliges cuántos fardos lleva), **reimprimir** y **anular**.
Las tarimas anuladas no se borran: quedan marcadas para no perder el folio.

## Pantallas
| Dirección | Para quién |
|---|---|
| `/` | Tablet que atiende varias líneas: elegir línea |
| `/linea/L4` | Tablet del montacargas de la Línea 4 |
| `/operador/L4` | Operador de la Línea 4: lote, resumen del turno, últimas tarimas |
| `/resumen` | Supervisión: todas las líneas del turno y descarga de Excel por fechas y línea |
| `/admin` | Líneas, presentaciones, qué presentación va en qué línea e impresoras (pide contraseña) |

## Arquitectura
```
Tabletas (6 líneas) ──WiFi──► Servidor con la app (python app.py) ──► PostgreSQL
                                     │                                   
                                     ├─► Impresora de etiquetas de cada línea (por red)
                                     └─► Google Sheets (copia para oficina, opcional)
```
Una sola app y una sola base de datos atienden las 6 líneas.

## Instalación

**En Windows (la PC de la planta):** doble clic en `instalacion/instalar.cmd`. Instala todo y deja la app arrancando sola. Ver `instalacion/GUIA_WINDOWS.md`.

Instalación manual (Linux o para desarrollo):

### 1. PostgreSQL
Lo ideal es que TI lo instale en un servidor de la empresa. Para una prueba se puede instalar en la misma
computadora (en Windows: instalador de postgresql.org; en Linux: `sudo apt install postgresql`).

Crear el usuario y la base (en la consola `psql` como administrador):
```sql
CREATE USER tarimas WITH PASSWORD 'una-contrasena-segura';
CREATE DATABASE tarimas OWNER tarimas;
```

### 2. La app
```bash
pip install -r requirements.txt
```
Configurar la conexión, ya sea en `config.py` o con variables de entorno (recomendado para no dejar contraseñas en el código):
```bash
export DATABASE_URL="postgresql://tarimas:una-contrasena-segura@SERVIDOR:5432/tarimas"
export ADMIN_CONTRASENA="contrasena-para-admin"
```
Crear las tablas (da de alta las líneas L1–L6 y la presentación de 4 lb):
```bash
python init_db.py
```
Si usaban la versión anterior con CSV, pasar esos registros:
```bash
python init_db.py --importar datos/registro_tarimas.csv
```
Arrancar (uso diario):
```bash
python servidor.py
```
(`python app.py` es el servidor de pruebas.)
En cada tablet abrir `http://IP-DEL-SERVIDOR:5000/linea/L4` (o la línea que corresponda) y guardarla como acceso directo.

### 3. Dar de alta las presentaciones
Entrar a `/admin` (usuario `admin` y la contraseña configurada) y por cada presentación capturar:
clave, nombre, descripción, libras por bolsa, bolsas por fardo, fardos por tarima y **en qué líneas se produce**.
Cada tablet solo muestra las presentaciones de su línea.

Si una presentación se modifica después, las tarimas ya registradas conservan los datos con que se imprimieron.
Si se deja de producir, se marca como inactiva (no se borra).

## Impresoras
En `/admin`, al editar cada línea, se captura la IP de su impresora de etiquetas (Zebra o compatible ZPL).
- **Con IP**: la etiqueta sale directo, sin ventanas.
- **Sin IP**: la tablet abre la etiqueta (4×6") y se imprime con cualquier impresora.

## Google Sheets (opcional)
Cada tarima se manda también a una hoja de Google Sheets. Se configura una sola vez:

1. Abre la hoja de Google Sheets donde quieren las tarimas.
2. Menú **Extensiones → Apps Script**. Borra lo que haya y pega el contenido de `apps_script.gs`.
3. En la línea `const CLAVE = "cambia-esta-clave";` pon una palabra secreta.
4. **Implementar → Nueva implementación → Aplicación web**: ejecutar como **Yo**, acceso **Cualquier usuario**.
5. Copia la URL que termina en `/exec` y configúrala:
   ```bash
   export SHEETS_URL="https://script.google.com/macros/s/XXXX/exec"
   export SHEETS_CLAVE="la-misma-palabra-secreta"
   ```

Las tarimas llegan a la pestaña **Tarimas** (se crea sola); las anuladas se marcan en rojo; nunca se duplica un folio.

**Si se cae el internet**: la etiqueta se imprime igual y la tarima queda en PostgreSQL. Los envíos pendientes
se guardan en la tabla `sheets_pendientes` y se suben solos cuando regresa la conexión (se revisa cada minuto).
En `/resumen` y `/operador` se ve si hay tarimas "por subir".

> El acceso debe ser "Cualquier usuario" porque la app no inicia sesión en Google; la palabra secreta impide que otros
> escriban en la hoja. Si en Google Workspace de la empresa no aparece esa opción, hay que pedir permiso a TI.

## Respaldos
Toda la información está en PostgreSQL. Para un respaldo:
```bash
pg_dump -U tarimas -h SERVIDOR tarimas > respaldo_tarimas.sql
```
Conviene programarlo diario (TI normalmente ya lo hace con sus bases de datos).

## Turnos
Los horarios de los turnos están en `config.py` (`TURNOS`).
