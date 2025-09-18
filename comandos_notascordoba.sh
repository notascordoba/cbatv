#!/bin/bash
# 🚀 COMANDOS ESPECÍFICOS PARA notascordoba/cbatv
# Usuario: notascordoba
# Repositorio: cbatv

echo "🚀 SUBIENDO CÓDIGO A GITHUB"
echo "Usuario: notascordoba"
echo "Repositorio: cbatv"
echo "URL: https://github.com/notascordoba/cbatv.git"
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "app.py" ]; then
    echo "❌ ERROR: No se encuentra app.py"
    echo "🔍 Ejecutar desde el directorio render_deploy/"
    echo "Comando: cd render_deploy && ./comandos_notascordoba.sh"
    exit 1
fi

echo "✅ Archivos encontrados, procediendo..."
echo ""

# Conectar con GitHub
echo "📡 Conectando con GitHub..."
git remote add origin https://github.com/notascordoba/cbatv.git

# Cambiar a rama main
echo "🌳 Cambiando a rama main..."
git branch -M main

# Subir código
echo "📤 Subiendo código..."
git push -u origin main

echo ""
echo "✅ ¡CÓDIGO SUBIDO EXITOSAMENTE!"
echo "📍 Tu repositorio: https://github.com/notascordoba/cbatv"
echo ""
echo "🎯 PRÓXIMO PASO:"
echo "Ve a https://render.com para conectar el repositorio"
echo ""
echo "🔗 ENLACES IMPORTANTES:"
echo "• GitHub: https://github.com/notascordoba/cbatv"
echo "• Render: https://render.com (para deploy)"
echo "• Documentación: https://github.com/notascordoba/cbatv/blob/main/README.md"
