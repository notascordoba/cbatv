#!/bin/bash
# 🤖 AUTOMATIZACIÓN COMPLETA - DEPLOY BOT PERIODISMO
# Para notascordoba/cbatv - Todo en uno

echo "🤖 AUTOMATIZACIÓN COMPLETA DEL BOT"
echo "=================================="
echo "Usuario: notascordoba"
echo "Repositorio: cbatv"
echo ""

# Verificar directorio
if [ ! -f "app.py" ]; then
    echo "❌ ERROR: Ejecutar desde render_deploy/"
    echo "Comando: cd render_deploy && ./automatizar_todo.sh"
    exit 1
fi

echo "📋 PROCESO COMPLETO:"
echo "1️⃣ Subir código a GitHub"
echo "2️⃣ Instrucciones para Render"
echo "3️⃣ Configuración de variables"
echo ""

read -p "🚀 ¿Continuar? (s/N): " continue_process

if [[ ! $continue_process =~ ^[Ss]$ ]]; then
    echo "❌ Proceso cancelado"
    exit 0
fi

echo ""
echo "🚀 PASO 1: SUBIENDO A GITHUB"
echo "=========================="

# Conectar con GitHub
echo "📡 Conectando con repositorio..."
git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/notascordoba/cbatv.git

# Cambiar a rama main
echo "🌳 Configurando rama main..."
git branch -M main

# Subir código
echo "📤 Subiendo archivos..."
if git push -u origin main; then
    echo "✅ Código subido exitosamente a GitHub"
else
    echo "❌ Error al subir. Verifica credenciales GitHub"
    echo "💡 Puede necesitar Personal Access Token"
    exit 1
fi

echo ""
echo "🌐 PASO 2: CONFIGURAR RENDER"
echo "==========================="
echo ""
echo "📝 INSTRUCCIONES AUTOMÁTICAS:"
echo ""
echo "1️⃣ Ve a: https://render.com"
echo "2️⃣ Sign up con GitHub (gratis)"
echo "3️⃣ New + → Web Service"
echo "4️⃣ Connect GitHub → Autorizar"
echo "5️⃣ Seleccionar: notascordoba/cbatv"
echo ""
echo "6️⃣ CONFIGURACIÓN AUTOMÁTICA:"
echo "   • Name: cbatv-bot"
echo "   • Environment: Python 3"
echo "   • Build Command: pip install -r requirements.txt"
echo "   • Start Command: python app.py"
echo "   • Plan: Free"
echo ""
echo "7️⃣ VARIABLES DE ENTORNO (Advanced):"

# Mostrar variables requeridas
echo ""
echo "🔑 VARIABLES OBLIGATORIAS:"
cat << EOF

┌─────────────────────────────────────────────────────────────┐
│ Variable                │ Dónde obtenerla                   │
├─────────────────────────────────────────────────────────────┤
│ TELEGRAM_BOT_TOKEN      │ @BotFather en Telegram            │
│ GROQ_API_KEY           │ console.groq.com (gratis)         │
│ WORDPRESS_URL          │ https://tusitio.com/xmlrpc.php    │
│ WORDPRESS_USERNAME     │ Usuario con permisos Editor+      │
│ WORDPRESS_PASSWORD     │ Contraseña del usuario            │
└─────────────────────────────────────────────────────────────┘

EOF

echo "8️⃣ Click 'Create Web Service'"
echo "9️⃣ ¡Render construye automáticamente!"
echo ""

echo "✅ RESULTADO FINAL:"
echo "• Bot online 24/7"
echo "• URL: https://cbatv-bot.onrender.com"
echo "• Logs: Panel Render → Logs"
echo "• Health: https://cbatv-bot.onrender.com/health"
echo ""

echo "📊 LIMITACIONES GRATIS:"
echo "• 750 horas/mes (suficiente para periodismo)"
echo "• Duerme tras 15 min inactividad"
echo "• Se despierta automáticamente"
echo ""

echo "🎯 PRÓXIMOS PASOS:"
echo "1. Configurar bot en @BotFather"
echo "2. Obtener API key de Groq"
echo "3. Configurar variables en Render"
echo "4. ¡Probar el bot!"
echo ""

# Crear archivo de seguimiento
cat > ../estado_deploy.txt << EOF
✅ Código subido a GitHub: https://github.com/notascordoba/cbatv
⏳ Pendiente: Configurar en Render
⏳ Pendiente: Variables de entorno
⏳ Pendiente: Pruebas del bot

ENLACES:
- GitHub: https://github.com/notascordoba/cbatv
- Render: https://render.com
- Groq: https://console.groq.com
- BotFather: https://t.me/botfather

ARCHIVOS IMPORTANTES:
- configurar_variables.md (guía completa)
- README.md (documentación)
EOF

echo "📁 Archivo creado: ../estado_deploy.txt"
echo ""
echo "🎉 ¡AUTOMATIZACIÓN COMPLETADA!"
echo "Sigue las instrucciones de arriba para completar el deploy"
