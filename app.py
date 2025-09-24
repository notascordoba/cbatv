import os
import logging
import requests
from flask import Flask, request, jsonify

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# VERSIÓN DEBUG EXTREMO - SOLO PARA CONFIRMAR QUÉ CÓDIGO CORRE
# ==========================================
logger.critical("🚨🚨🚨 EJECUTANDO VERSIÓN DEBUG EXTREMO 🚨🚨🚨")
logger.critical("🚨🚨🚨 ESTA VERSIÓN NO HACE NADA ÚTIL 🚨🚨🚨")
logger.critical("🚨🚨🚨 SOLO RESPONDE 'DEBUG EXTREMO FUNCIONANDO' 🚨🚨🚨")

app = Flask(__name__)

# Configuración mínima
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

@app.route('/')
def home():
    return jsonify({
        "status": "🚨 DEBUG EXTREMO FUNCIONANDO 🚨",
        "version": "DEBUG_EXTREMO",
        "message": "Si ves esto, el nuevo código SÍ está corriendo"
    })

@app.route('/health')
def health():
    return jsonify({
        "version": "DEBUG_EXTREMO",
        "status": "🚨 NUEVO CÓDIGO CONFIRMADO 🚨"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.critical("🚨🚨🚨 WEBHOOK DEBUG EXTREMO RECIBIDO 🚨🚨🚨")
    
    try:
        update = request.get_json()
        
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            
            # RESPUESTA IMPOSIBLE DE CONFUNDIR
            if 'photo' in message and 'caption' in message:
                logger.critical("🚨🚨🚨 PROCESANDO FOTO EN DEBUG EXTREMO 🚨🚨🚨")
                
                # Responder con mensaje único
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        'chat_id': chat_id,
                        'text': "🚨🚨🚨 DEBUG EXTREMO FUNCIONANDO 🚨🚨🚨\n\n"
                               "Si ves este mensaje, significa que:\n"
                               "✅ El nuevo código SÍ está corriendo\n"
                               "✅ El problema está en la lógica, no en el deployment\n\n"
                               "Caption recibido: " + message.get('caption', 'Sin caption')
                    }
                )
            else:
                # Responder a cualquier otro mensaje
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        'chat_id': chat_id,
                        'text': "🚨 DEBUG EXTREMO: Envía una foto con caption para confirmar funcionamiento 🚨"
                    }
                )
    except Exception as e:
        logger.critical(f"🚨🚨🚨 ERROR EN DEBUG EXTREMO: {e} 🚨🚨🚨")
    
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    logger.critical("🚨🚨🚨 DEBUG EXTREMO INICIANDO EN PUERTO 🚨🚨🚨")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
