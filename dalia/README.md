# Dalia: asistente de ventas de Florece Digital

Dalia es el chatbot con IA de https://florecedigital.com. Recomienda el paquete correcto a cada visitante y lo manda a WhatsApp listo para comprar.

## Archivos

| Archivo | Qué es |
|---|---|
| `conocimiento.md` | Paquetes, precios, promoción y preguntas frecuentes. Es lo único que Dalia "sabe". |
| `instrucciones.md` | Personalidad, guion de ventas y reglas de Dalia (el system prompt). |

## Cómo se va a instalar (sitio en Hostinger)

1. **`dalia.php`**: archivo en el servidor de Hostinger. Guarda la clave de la IA en secreto y habla con Claude. Mismo dominio, sin servicios extra.
2. **`dalia.js` + `dalia.css`**: la ventana de chat con los colores de Florece (fondo oscuro, rosa, tipografía de la marca).
3. **Una línea** que se agrega al final del HTML del sitio para cargar el chat.

## Avance

- [x] Nombre: **Dalia**
- [x] Paquetes y precios cargados (Presencia, Impulso, Insignia, Buen Fin)
- [x] Borrador de personalidad y guion de ventas
- [ ] Completar los datos **[PENDIENTE]** de `conocimiento.md`
- [ ] Servidor (`dalia.php`)
- [ ] Ventana de chat
- [ ] Pruebas: 40 a 60 conversaciones simuladas
- [ ] Lanzamiento y aviso de privacidad
