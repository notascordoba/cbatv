# 🔧 Configuración de Variables en Render

## 📋 Variables Obligatorias

### 1. TELEGRAM_BOT_TOKEN
- Ve a [@BotFather](https://t.me/botfather) en Telegram
- Crear nuevo bot: `/newbot`
- Copiar token generado
- Valor: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`

### 2. GROQ_API_KEY  
- Ve a [Groq Console](https://console.groq.com)
- Crear cuenta gratuita
- Generar API key
- Valor: `gsk_tu_api_key_aqui`

### 3. WORDPRESS_URL
- URL de tu WordPress + `/xmlrpc.php`
- Valor: `https://tusitio.com/xmlrpc.php`

### 4. WORDPRESS_USERNAME
- Usuario de WordPress con permisos de Editor+
- Valor: `tu_usuario_wordpress`

### 5. WORDPRESS_PASSWORD
- Contraseña del usuario (o App Password si usas 2FA)
- Valor: `tu_password_wordpress`

## 📋 Variables Opcionales

### OPENAI_API_KEY (para transcripción de audio)
- Ve a [OpenAI](https://platform.openai.com)
- Crear API key
- Valor: `sk-tu_openai_key_aqui`

### AUTHORIZED_USER_IDS (control de acceso)
- IDs de usuarios de Telegram autorizados
- Separados por comas
- Valor: `123456789,987654321`

### IMAGE_WIDTH / IMAGE_HEIGHT / IMAGE_QUALITY
- Configuración de procesamiento de imágenes
- Valores por defecto: `1200`, `675`, `85`

## 🔧 Cómo configurar en Render

1. Ve a tu proyecto en Render
2. Click en "Environment"
3. Add Environment Variable
4. Agregar cada variable una por una
5. Click "Save Changes"

El servicio se reiniciará automáticamente.
