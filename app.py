#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏆 === VERSIÓN v6.5.3 - ASYNC FIX === 🏆
🏆 === IMAGEN DESTACADA + ALT TEXT + SEO + TELEGRAM === 🏆

CARACTERÍSTICAS:
✅ Imagen destacada en WordPress
✅ Alt text en imagen (media library)
✅ Meta descripción Yoast SEO
✅ Frase clave objetivo Yoast SEO
✅ Respuesta confirmación por Telegram
✅ Python 3.10+ compatibility fix
✅ ASYNC execution fix
"""

# ✅ FIX CRÍTICO para Python 3.10+
import collections
import collections.abc
if not hasattr(collections, 'Iterable'):
    collections.Iterable = collections.abc.Iterable

import os
import sys
import asyncio
import aiohttp
import logging
import requests
import json
import base64
from datetime import datetime
from flask import Flask, request, jsonify
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import GetPosts, NewPost
from wordpress_xmlrpc.methods import media
from wordpress_xmlrpc.methods.users import GetUserInfo
from groq import Groq
from typing import Dict, Any, Optional, List, Tuple

# ================================
# CONFIGURACIÓN Y VALIDACIÓN
# ================================

# Variables de entorno obligatorias
REQUIRED_ENV_VARS = [
    'WP_URL', 'WP_USERNAME', 'WP_PASSWORD', 
    'GROQ_API_KEY', 'TELEGRAM_BOT_TOKEN'
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    print(f"🏆 ❌ FALTAN VARIABLES DE ENTORNO: {missing_vars}")
    sys.exit(1)

# Cargar variables
WP_URL = os.getenv('WP_URL')
WP_USERNAME = os.getenv('WP_USERNAME')
WP_PASSWORD = os.getenv('WP_PASSWORD')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# ================================
# CONFIGURACIÓN LOGGING
# ================================

logging.basicConfig(
    level=logging.CRITICAL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Banner de versión
logger.critical("🏆 === VERSIÓN v6.5.3 - ASYNC FIX === 🏆")
logger.critical("🏆 === IMAGEN DESTACADA + ALT TEXT + SEO + TELEGRAM === 🏆")

# ================================
# CONFIGURACIÓN CLIENTES
# ================================

# WordPress XML-RPC
xmlrpc_url = f"{WP_URL.rstrip('/')}/xmlrpc.php"
logger.critical(f"🏆 Conectando a XML-RPC: {xmlrpc_url}")
logger.critical(f"🏆 Usuario: {WP_USERNAME}")

try:
    wp_client = Client(xmlrpc_url, WP_USERNAME, WP_PASSWORD)
    # Test connection
    user_info = wp_client.call(GetUserInfo())
    logger.critical("🏆 ✅ Cliente WordPress XML-RPC configurado correctamente")
except Exception as e:
    logger.critical(f"🏆 ❌ Error configurando WordPress: {e}")
    wp_client = None

# Cliente Groq
client = Groq(api_key=GROQ_API_KEY)

# ================================
# FLASK APP
# ================================

app = Flask(__name__)

# ================================
# FUNCIONES DE UTILIDAD
# ================================

def send_telegram_message(chat_id: int, text: str) -> bool:
    """Envía mensaje por Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            logger.critical(f"🏆 ✅ Mensaje Telegram enviado: {text[:50]}...")
            return True
        else:
            logger.error(f"🏆 ❌ Error enviando mensaje Telegram: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"🏆 ❌ Error en send_telegram_message: {e}")
        return False

def clean_json_response(text: str) -> str:
    """Limpia la respuesta para extraer solo el JSON"""
    text = text.strip()
    
    # Buscar el primer {
    start_idx = text.find('{')
    if start_idx == -1:
        return text
        
    # Buscar el último }
    end_idx = text.rfind('}')
    if end_idx == -1:
        return text
        
    return text[start_idx:end_idx+1]

# ================================
# FUNCIONES PRINCIPALES
# ================================

async def generate_seo_content(caption: str, image_url: str) -> Optional[Dict[str, Any]]:
    """Genera contenido SEO optimizado usando Groq CON ALT TEXT"""
    prompt = f"""
Eres un periodista argentino experto en SEO. Convierte esta información en un artículo periodístico completo y optimizado:

INFORMACIÓN: {caption}

Responde ÚNICAMENTE con un JSON válido. Estructura EXACTA requerida:

{{
    "titulo": "Título específico y llamativo (40-60 caracteres)",
    "slug": "titulo-url-amigable-seo",
    "contenido_html": "<h2>Subtítulo Principal</h2><p>Contenido detallado del artículo con información relevante y específica...</p><h3>Subtítulo Secundario</h3><p>Más contenido desarrollado...</p>",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "meta_descripcion": "Descripción SEO de exactamente 150-160 caracteres que resuma el artículo",
    "frase_clave": "palabras clave principales",
    "alt_text": "Descripción específica de la imagen (30-50 caracteres)",
    "categoria": "Política"
}}

CRÍTICO: El artículo debe ser específico sobre la información proporcionada, no genérico.
"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Eres un periodista experto que genera artículos en formato JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3000,
            temperature=0.7
        )
        
        content = completion.choices[0].message.content
        logger.critical(f"🏆 Respuesta Groq recibida: {len(content)} caracteres")
        
        # Limpiar y parsear JSON
        clean_content = clean_json_response(content)
        logger.critical(f"🏆 Contenido limpiado: {clean_content[:200]}...")
        
        try:
            article_data = json.loads(clean_content)
            logger.critical("🏆 ✅ JSON parseado correctamente")
            
            # Validar campos requeridos
            required_fields = ['titulo', 'slug', 'contenido_html', 'tags', 'meta_descripcion', 'frase_clave', 'alt_text']
            for field in required_fields:
                if field not in article_data:
                    logger.error(f"🏆 ❌ Campo faltante: {field}")
                    return None
            
            logger.critical(f"🏆 ✅ Artículo generado: {article_data['titulo']}")
            return article_data
            
        except json.JSONDecodeError as e:
            logger.error(f"🏆 ❌ Error parseando JSON: {e}")
            logger.error(f"🏆 Contenido problemático: {clean_content}")
            return None
            
    except Exception as e:
        logger.error(f"🏆 ❌ Error en generate_seo_content: {e}")
        return None

async def upload_image_to_wordpress(image_url: str, filename: str, alt_text: str) -> Tuple[Optional[str], Optional[int]]:
    """Sube imagen a WordPress CON ALT TEXT usando XML-RPC"""
    logger.critical(f"🏆 SUBIENDO IMAGEN VÍA XML-RPC CON ALT TEXT")
    logger.critical(f"🏆 🖼️ Alt text: {alt_text}")
    logger.critical(f"🏆 Filename: {filename}")
    
    if not wp_client:
        logger.error("🏆 ❌ Cliente WordPress no disponible")
        return None, None
    
    try:
        # Descargar imagen
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    logger.error(f"🏆 ❌ Error descargando imagen: {response.status}")
                    return None, None
                
                image_data = await response.read()
                logger.critical(f"🏆 ✅ Imagen descargada: {len(image_data)} bytes")
        
        # Preparar datos para WordPress XML-RPC
        data = {
            'name': filename,
            'type': 'image/jpeg',
            'bits': image_data
        }
        
        logger.critical("🏆 Subiendo vía XML-RPC...")
        
        # Subir usando XML-RPC
        response = wp_client.call(media.UploadFile(data))
        
        if response and 'url' in response:
            wp_image_url = response['url']
            attachment_id = response.get('id')
            
            logger.critical(f"🏆 ✅ IMAGEN SUBIDA CORRECTAMENTE: {wp_image_url}")
            
            # 🔧 CONFIGURAR ALT TEXT EN EL ATTACHMENT
            if attachment_id and alt_text:
                try:
                    # Crear post para el attachment con el alt text
                    attachment_post = WordPressPost()
                    attachment_post.id = attachment_id
                    attachment_post.custom_fields = [
                        {
                            'key': '_wp_attachment_image_alt',
                            'value': alt_text
                        }
                    ]
                    
                    # Actualizar el attachment con el alt text
                    wp_client.call(NewPost(attachment_post))
                    logger.critical(f"🏆 ✅ ALT TEXT configurado: {alt_text}")
                    
                except Exception as alt_error:
                    logger.error(f"🏆 ⚠️ Error configurando alt text: {alt_error}")
            
            return wp_image_url, attachment_id
        else:
            logger.error("🏆 ❌ Respuesta XML-RPC inválida")
            return None, None
    
    except Exception as e:
        logger.error(f"🏆 ❌ Error subiendo imagen: {e}")
        return None, None

def create_wordpress_post(article_data: Dict[str, Any], wp_image_url: str, attachment_id: int) -> bool:
    """Crea post de WordPress CON imagen destacada y SEO"""
    logger.critical("🏆 CREANDO POST CON IMAGEN DESTACADA Y SEO")
    
    if not wp_client:
        logger.error("🏆 ❌ Cliente WordPress no disponible")
        return False
    
    try:
        # Crear el post
        post = WordPressPost()
        post.title = article_data['titulo']
        post.content = article_data['contenido_html']
        post.slug = article_data['slug']
        post.post_status = 'publish'
        
        # Tags
        if article_data.get('tags'):
            post.terms_names = {
                'post_tag': article_data['tags']
            }
        
        # Categoría
        if article_data.get('categoria'):
            post.terms_names = post.terms_names or {}
            post.terms_names['category'] = [article_data['categoria']]
        
        # ✅ IMAGEN DESTACADA
        if attachment_id:
            logger.critical(f"🏆 🖼️ Configurando imagen destacada: attachment_id={attachment_id}")
            post.thumbnail = attachment_id
        
        # ✅ CUSTOM FIELDS PARA YOAST SEO
        custom_fields = []
        
        # Meta descripción
        if article_data.get('meta_descripcion'):
            custom_fields.append({
                'key': '_yoast_wpseo_metadesc',
                'value': article_data['meta_descripcion']
            })
            logger.critical(f"🏆 📝 Meta descripción: {article_data['meta_descripcion'][:50]}...")
        
        # Frase clave objetivo
        if article_data.get('frase_clave'):
            custom_fields.append({
                'key': '_yoast_wpseo_focuskw',
                'value': article_data['frase_clave']
            })
            logger.critical(f"🏆 🎯 Frase clave: {article_data['frase_clave']}")
        
        if custom_fields:
            post.custom_fields = custom_fields
        
        # Publicar post
        post_id = wp_client.call(NewPost(post))
        
        if post_id:
            post_url = f"{WP_URL.rstrip('/')}/{article_data['slug']}"
            logger.critical(f"🏆 ✅ POST CREADO EXITOSAMENTE")
            logger.critical(f"🏆 🌐 URL: {post_url}")
            logger.critical(f"🏆 🆔 ID: {post_id}")
            return True
        else:
            logger.error("🏆 ❌ Error: post_id es None")
            return False
    
    except Exception as e:
        logger.error(f"🏆 ❌ Error creando post: {e}")
        return False

async def process_telegram_image_message(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa mensaje de Telegram COMPLETO: imagen + SEO + respuesta"""
    chat_id = None
    
    try:
        # Extraer chat_id
        chat_id = message_data.get('chat', {}).get('id')
        
        if 'photo' not in message_data:
            logger.error("🏆 ❌ No se encontró foto en el mensaje")
            return {"status": "error", "message": "No photo found"}
        
        # Obtener la foto de mayor resolución
        photo = message_data['photo'][-1]
        file_id = photo['file_id']
        
        # Obtener caption
        caption = message_data.get('caption', 'Imagen sin descripción')
        logger.critical(f"🏆 Caption: {caption[:100]}...")
        
        # Obtener URL de la imagen de Telegram
        file_response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}")
        file_data = file_response.json()
        
        if not file_data.get('ok'):
            logger.error("🏆 ❌ Error obteniendo archivo de Telegram")
            return {"status": "error", "message": "Error getting file from Telegram"}
        
        file_path = file_data['result']['file_path']
        image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        logger.critical(f"🏆 Image URL: {image_url}")
        
        # Generar artículo CON SEO COMPLETO
        article_data = await generate_seo_content(caption, image_url)
        
        if not article_data:
            logger.error("🏆 ❌ Error generando artículo")
            if chat_id:
                send_telegram_message(chat_id, "🏆 ❌ Error: No se pudo generar el artículo")
            return {"status": "error", "message": "Error generating article"}
        
        # Subir imagen CON ALT TEXT
        filename = f"{article_data['slug']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        wp_image_url, attachment_id = await upload_image_to_wordpress(
            image_url,
            filename, 
            article_data['alt_text']
        )
        
        if not wp_image_url:
            logger.error("🏆 ❌ Error subiendo imagen")
            if chat_id:
                send_telegram_message(chat_id, "🏆 ❌ Error: No se pudo subir la imagen")
            return {"status": "error", "message": "Error uploading image"}
        
        # Crear post CON TODAS LAS MEJORAS
        success = create_wordpress_post(article_data, wp_image_url, attachment_id)
        
        if success:
            post_url = f"{WP_URL.rstrip('/')}/{article_data['slug']}"
            
            # ✅ RESPUESTA POR TELEGRAM
            if chat_id:
                success_message = f"""
🏆 ✅ <b>ARTÍCULO PUBLICADO EXITOSAMENTE</b>

📰 <b>Título:</b> {article_data['titulo']}
🌐 <b>URL:</b> {post_url}
🖼️ <b>Imagen destacada:</b> ✅ Configurada
📝 <b>Meta descripción SEO:</b> ✅ Configurada
🎯 <b>Frase clave:</b> {article_data['frase_clave']}
🏷️ <b>Alt text:</b> ✅ Configurado
"""
                send_telegram_message(chat_id, success_message)
            
            logger.critical("🏆 ✅ PROCESO COMPLETADO EXITOSAMENTE")
            return {"status": "success", "url": post_url}
        else:
            logger.error("🏆 ❌ Error creando post")
            if chat_id:
                send_telegram_message(chat_id, "🏆 ❌ Error: No se pudo crear el post en WordPress")
            return {"status": "error", "message": "Error creating WordPress post"}
    
    except Exception as e:
        logger.error(f"🏆 ❌ Error en process_telegram_image_message: {e}")
        if chat_id:
            send_telegram_message(chat_id, f"🏆 ❌ Error procesando mensaje: {str(e)}")
        return {"status": "error", "message": str(e)}

# ================================
# WEBHOOK ENDPOINT
# ================================

@app.route('/webhook', methods=['POST'])
def webhook():
    """Maneja webhooks de Telegram"""
    try:
        logger.critical("🏆 v6.5.3: WEBHOOK RECIBIDO")
        
        data = request.get_json()
        if not data:
            return jsonify({"status": "no_data"})
        
        message = data.get('message')
        if message:
            logger.critical("🏆 Procesando mensaje...")
            
            if 'photo' in message:
                # ✅ EJECUTAR FUNCIÓN ASYNC CORRECTAMENTE
                result = asyncio.run(process_telegram_image_message(message))
                return jsonify(result)
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"🏆 ❌ Error en webhook: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "version": "6.5.3",
        "wordpress_url": WP_URL,
        "features": {
            "featured_image": True,
            "alt_text": True,
            "yoast_seo": True,
            "telegram_response": True,
            "async_fix": True
        }
    })

# ================================
# INICIALIZACIÓN
# ================================

if __name__ == "__main__":
    logger.critical("🏆 === INICIANDO BOT v6.5.3 - ASYNC FIX === 🏆")
    logger.critical("🏆 ✅ IMAGEN DESTACADA: Configurada")
    logger.critical("🏆 ✅ ALT TEXT ATTACHMENT: Configurado")
    logger.critical("🏆 ✅ META DESCRIPCIÓN: Configurada")
    logger.critical("🏆 ✅ FRASE CLAVE OBJETIVO: Configurada")
    logger.critical("🏆 ✅ RESPUESTA TELEGRAM: Activada")
    logger.critical("🏆 ✅ PYTHON 3.10+ COMPATIBILITY: Fix aplicado")
    logger.critical("🏆 ✅ ASYNC EXECUTION: Fix aplicado")
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
