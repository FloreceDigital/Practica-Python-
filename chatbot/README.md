# Chatbot para WhatsApp y Facebook Messenger

Un solo servidor en Python (Flask) recibe los mensajes de **WhatsApp** y de **Facebook Messenger**, le pide la respuesta a **Claude** y contesta por el mismo canal. Recuerda la conversación de cada persona y solo da datos del negocio (precios, horarios...) que aparezcan en `info_negocio.md`.

```
Cliente ──► WhatsApp / Messenger ──► Meta ──► /webhook (este servidor) ──► Claude
   ▲                                                    │
   └────────────────── respuesta ◄──────────────────────┘
```

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Servidor web: recibe el webhook de Meta |
| `bot.py` | Habla con Claude y guarda el historial de cada persona |
| `meta.py` | Lee los mensajes de Meta y envía las respuestas |
| `config.py` | Lee la configuración (claves y opciones) |
| `info_negocio.md` | **Edítalo:** todo lo que el bot debe saber de tu negocio |
| `.env.example` | Plantilla de claves; cópiala como `.env` |

## 1. Preparar el proyecto

```bash
cd chatbot
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # y rellena los valores
```

Después edita `info_negocio.md` con los datos reales de tu negocio.

## 2. Conseguir las claves

**Claude:** crea una API key en <https://platform.claude.com> y ponla en `ANTHROPIC_API_KEY`.

**Meta:**
1. Entra a <https://developers.facebook.com>, ve a *Mis apps* y crea una app de tipo **Negocios**.
2. En *Configuración > Básica* copia la **Clave secreta de la app** y ponla en `META_APP_SECRET`.
3. Inventa una clave cualquiera para `META_VERIFY_TOKEN` (por ejemplo, una frase larga).

**WhatsApp:** añade el producto **WhatsApp** a la app. En *Configuración de la API* verás un número de prueba y un token temporal, que dura 24 h. Ponlo en `WHATSAPP_TOKEN`. Para producción, crea un token permanente con un *usuario del sistema* en el Business Manager y registra tu número real.

**Messenger:** añade el producto **Messenger**, conecta tu página de Facebook, genera el **token de la página** y ponlo en `MESSENGER_PAGE_TOKEN`.

## 3. Ponerlo en marcha

En local, para pruebas:

```bash
python app.py                    # escucha en http://localhost:5000
```

Meta necesita una URL pública con HTTPS. Para probar desde tu computadora puedes usar [ngrok](https://ngrok.com):

```bash
ngrok http 5000                  # te da algo como https://abcd.ngrok-free.app
```

En producción, súbelo a un servicio como Render, Railway o un VPS y arráncalo con:

```bash
gunicorn "app:crear_app()" --bind 0.0.0.0:$PORT --workers 1 --threads 8
```

> Usa **un solo worker** (`--workers 1`): el historial de las conversaciones se guarda en memoria.

## 4. Conectar el webhook en Meta

En el panel de tu app, tanto en **WhatsApp > Configuración** como en **Messenger > Configuración**:

- **URL de devolución de llamada:** `https://TU-DOMINIO/webhook`
- **Token de verificación:** el mismo texto que pusiste en `META_VERIFY_TOKEN`
- **Suscripciones:** en WhatsApp marca `messages`. En Messenger, suscribe tu página a `messages`.

Listo. Escríbele al número de WhatsApp o a tu página de Facebook.

## Uso

- El bot responde en el idioma en que le escriban.
- Si alguien escribe `/reiniciar`, su conversación empieza de cero.
- Por ahora solo entiende texto. Si recibe fotos o audios, pide que se lo escriban.

## Opciones (en `.env`)

| Variable | Por defecto | Qué hace |
|---|---|---|
| `NOMBRE_NEGOCIO` | `nuestro negocio` | Cómo se presenta el bot |
| `CHATBOT_MODEL` | `claude-opus-5-5` | Modelo de Claude. Para gastar menos con mucho volumen puedes probar `claude-haiku-5-5` |
| `CHATBOT_EFFORT` | `low` | Cuánto "piensa" Claude: `low`, `medium` o `high` |
| `CHATBOT_FALLBACKS` | `1` | Si Claude rechaza una petición, la API la reintenta con otro modelo. Pon `0` para desactivarlo |
| `MAX_MENSAJES_HISTORIAL` | `20` | Cuántos mensajes recuerda por persona |
| `GRAPH_API_VERSION` | `v23.0` | Versión de la API de Meta |

## Pruebas

```bash
pip install pytest
python -m pytest tests
```

Las pruebas no gastan dinero porque simulan a Claude y a Meta.

## Limitaciones y siguientes pasos

- **El historial vive en memoria:** se borra si el servidor se reinicia. Para guardarlo de forma permanente habría que usar una base de datos (SQLite o Redis).
- **Regla de las 24 horas de WhatsApp:** solo puedes responder libremente durante las 24 h siguientes al último mensaje del cliente. Para escribirle tú primero necesitas *plantillas* aprobadas por Meta.
- **Pasar a una persona:** cuando hace falta, el bot avisa de que alguien del equipo dará seguimiento, pero no notifica a nadie. Un buen siguiente paso es mandarte un correo o un aviso en esos casos.
