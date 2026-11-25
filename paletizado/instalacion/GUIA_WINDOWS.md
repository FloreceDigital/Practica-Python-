# Guía de instalación en Windows

Esta guía es para instalar el Registro de tarimas en la PC con Windows de la planta.
Toma unos 30 minutos la primera vez.

## Cómo se conecta todo

```
                 Red WiFi de la planta (el mismo módem / router)
        ┌──────────────────────┼──────────────────────┐
   Tablet del flejado     PC con Windows         Impresora Zebra
   (navegador)            (app + PostgreSQL)     (cable de red)
```

- La **PC** es el servidor: ahí corren la app y la base de datos.
- Las **tabletas** no se conectan directo a la PC: se conectan **a la misma red WiFi** que la PC,
  y abren la dirección de la PC en el navegador (por ejemplo `http://192.168.1.20:5000/linea/L4`).
- La **impresora** también está en la misma red. La PC le manda las etiquetas.
- La PC puede estar conectada a la red por cable o por WiFi; con cable es más estable.

## Antes de empezar

1. La PC debe tener **Windows 10 o 11** y una cuenta con permiso de **Administrador**.
2. La PC debe quedarse **prendida siempre** y conectada a un **no-break (UPS)** si es posible.
3. Conecta la PC a internet (para descargar Python y PostgreSQL).
4. Pide en el módem o router una **IP fija** para la PC y otra para la impresora.
   Si no sabes cómo, busca el modelo del módem + "reservar IP" o "DHCP reservation".
   Sin IP fija, la dirección de la PC puede cambiar y las tabletas dejarían de encontrarla.

## Instalar

1. Descarga el proyecto de GitHub (botón **Code → Download ZIP**) y descomprímelo,
   por ejemplo en `C:\Users\TU_USUARIO\Downloads\Practica-Python-`.
2. Entra a la carpeta `paletizado\instalacion`.
3. Da **doble clic en `instalar.cmd`** y acepta el permiso de Administrador.
4. Espera a que termine. Al final muestra las direcciones para las tabletas, por ejemplo:
   ```
   Tablet Linea 4:  http://192.168.1.20:5000/linea/L4
   Operador:        http://192.168.1.20:5000/operador/L4
   Resumen/Excel:   http://192.168.1.20:5000/resumen
   Administracion:  http://192.168.1.20:5000/admin
   ```
5. Abre `C:\Tarimas\CONTRASENAS.txt`, **guarda las contraseñas en un lugar seguro**
   (por ejemplo, una copia impresa con tu jefe).

Si algo falla, el instalador dice en qué paso. Se puede volver a correr sin perder datos.

## Configurar (una sola vez)

1. En la PC abre `http://localhost:5000/admin` (usuario `admin`, contraseña `CLAVE_ADMIN`).
2. **Personal**: da de alta los nombres de montacargas, operadores, supervisores y estibadores.
3. **Líneas → Línea 4**: escribe la IP de la impresora Zebra.
4. En la tablet del flejado abre la dirección de la Línea 4 y **agrégala a la pantalla de inicio**.

## Mantenimiento

| Cada cuándo | Qué hacer |
|---|---|
| Cada semana | Copia la carpeta `C:\Tarimas\respaldos` a una memoria USB o a Google Drive. |
| Cada mes | Instala las actualizaciones de Windows y reinicia la PC fuera del turno. |
| Al actualizar la app | Descarga la versión nueva del proyecto y vuelve a correr `instalar.cmd`. |

Lo que queda en la PC:

| Dónde | Qué es |
|---|---|
| `C:\Tarimas\app` | La app |
| `C:\Tarimas\CONTRASENAS.txt` | Las contraseñas |
| `C:\Tarimas\respaldos` | Un respaldo por día (se guardan 30 días) |
| `C:\Tarimas\logs\servidor.log` | Registro de lo que hace la app (útil si algo falla) |
| Programador de tareas → `Tarimas - Servidor` | Arranca la app al prender la PC |
| Programador de tareas → `Tarimas - Respaldo` | Hace el respaldo diario |

## Si algo falla

**La tablet no abre la página**
1. Revisa que la tablet esté en el **mismo WiFi** que la PC.
2. En la PC abre `http://localhost:5000/resumen`. Si ahí sí abre, el problema es la red o el firewall.
3. Revisa que la IP de la PC no haya cambiado (en la PC: `ipconfig`).

**No abre ni en la PC**
1. Abre el **Programador de tareas**, busca `Tarimas - Servidor` y dale **Ejecutar**.
2. Revisa `C:\Tarimas\logs\servidor.log` para ver el error.
3. Revisa que el servicio de PostgreSQL esté corriendo (en **Servicios**, `postgresql-x64-16`).

**No imprime**
1. Revisa que la impresora esté prendida, con etiquetas y ribbon, y en la misma red.
2. Revisa que la IP de la impresora en `/admin` sea la correcta (la impresora puede imprimir
   una hoja de configuración con su IP).
3. Mientras se arregla, la tablet puede imprimir la etiqueta desde el navegador con cualquier impresora:
   borra la IP de la impresora en `/admin`.

**Restaurar un respaldo** (solo si se perdió la base de datos)
```
"C:\Program Files\PostgreSQL\16\bin\pg_restore.exe" -U tarimas -h localhost -d tarimas --clean C:\Tarimas\respaldos\tarimas_AAAA-MM-DD.dump
```
Pide la contraseña `CLAVE_BASE_DATOS`.
