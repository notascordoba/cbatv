# 📰 Bot de Automatización Periodística

Sistema que convierte crónicas de Telegram en artículos SEO-optimizados para WordPress.

## 🚀 Deploy en Render (Gratis)

Este proyecto está configurado para deploy automático en Render.com

### Variables de entorno requeridas:

```
TELEGRAM_BOT_TOKEN=tu_token_de_telegram
GROQ_API_KEY=tu_api_key_de_groq  
WORDPRESS_URL=https://tusitio.com/xmlrpc.php
WORDPRESS_USERNAME=tu_usuario
WORDPRESS_PASSWORD=tu_password
```

### Variables opcionales:

```
OPENAI_API_KEY=sk-...  # Para transcripción de audio
AUTHORIZED_USER_IDS=123456789,987654321  # Control de acceso
```

## 📱 Uso

1. Envía imagen + texto al bot de Telegram
2. El sistema genera artículo automáticamente  
3. Se publica en WordPress como borrador

## 🔧 Comandos del bot

- `/start` - Información del bot
- `/help` - Guía de uso
- `/stats` - Estadísticas del sistema

## 📊 Características

- ✅ Generación automática de artículos 500+ palabras
- ✅ SEO optimizado (H1, H2, H3, meta descripción)
- ✅ Procesamiento de imágenes (1200×675px)
- ✅ Transcripción de audio opcional
- ✅ Control de usuarios autorizados
- ✅ Monitoreo y logs integrados

