import os
import logging
import requests
import re
import json
import asyncio
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse, quote
import aiohttp
from flask import Flask, request, jsonify
from groq import Groq

# WordPress XML-RPC
import collections
import collections.abc
if not hasattr(collections, 'Iterable'):
    collections.Iterable = collections.abc.Iterable

import wordpress_xmlrpc
from wordpress_xmlrpc import Client
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# VERSIÓN v6.2.0 - MODELO GROQ CORRECTO OFICIAL
# ==========================================
logger.critical("🎯 === VERSIÓN v6.2.0 - MODELO OFICIAL CORRECTO === 🎯")
logger.critical("🎯 === LLAMA-3.3-70B-VERSATILE - DEFINITIVO === 🎯")

app = Flask(__name__)

# Configuración
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WP_URL = os.getenv('WORDPRESS_URL')
WP_USERNAME = os.getenv('WORDPRESS_USERNAME')
WP_PASSWORD = os.getenv('WORDPRESS_PASSWORD')

# Cliente Groq
client = Groq(api_key=GROQ_API_KEY)

# Configurar WordPress XML-RPC Client
wp_client = None
if WP_URL and WP_USERNAME and WP_PASSWORD:
    try:
        # Construir URL XML-RPC (como en el código original)
        xmlrpc_url = WP_URL.rstrip('/')
        if not xmlrpc_url.endswith('/xmlrpc.php'):
            xmlrpc_url = f"{xmlrpc_url}/xmlrpc.php"
        
        logger.critical(f"🎯 Conectando a XML-RPC: {xmlrpc_url}")
        logger.critical(f"🎯 Usuario: {WP_USERNAME}")
        
        wp_client = Client(xmlrpc_url, WP_USERNAME, WP_PASSWORD)
        logger.critical("🎯 ✅ Cliente WordPress XML-RPC configurado correctamente")
    except Exception as e:
        logger.error(f"🎯 ❌ Error configurando WordPress: {e}")

def safe_filename(text: str) -> str:
    """Crea un nombre de archivo seguro desde un texto"""
    safe = re.sub(r'[^\w\s-]', '', text).strip().lower()
    safe = re.sub(r'[-\s]+', '-', safe)
    return safe[:50] if safe else 'imagen'

def extract_json_robust(text: str) -> Optional[Dict[str, Any]]:
    """Extracción JSON robusta"""
    logger.info("🎯 Extrayendo JSON con estrategias múltiples")
    
    text = text.strip()
    
    # Estrategia 1: JSON directo
    try:
        result = json.loads(text)
        logger.critical("🎯 ✅ JSON directo exitoso")
        return result
    except:
        pass
    
    # Estrategia 2: Buscar entre ```json y ```
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if json_match:
        try:
            result = json.loads(json_match.group(1).strip())
            logger.critical("🎯 ✅ JSON con markdown exitoso")
            return result
        except:
            pass
    
    # Estrategia 3: Buscar estructura { ... }
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            result = json.loads(brace_match.group(0))
            logger.critical("🎯 ✅ JSON con braces exitoso")
            return result
        except:
            pass
    
    logger.error("🎯 ❌ Todas las estrategias JSON fallaron")
    return None

async def generate_seo_content(caption: str, image_url: str) -> Optional[Dict[str, Any]]:
    """Genera contenido SEO optimizado usando Groq"""
    prompt = f"""
Eres un periodista argentino experto en SEO. Convierte esta información en un artículo periodístico completo y optimizado:

INFORMACIÓN: {caption}

Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:
{{
    "titulo": "Título periodístico llamativo (máximo 60 caracteres)",
    "slug": "titulo-optimizado-seo-sin-espacios",
    "contenido_html": "Artículo completo en HTML con <h2>, <p>, <strong>, etc. Mínimo 300 palabras",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "meta_descripcion": "Descripción SEO (máximo 160 caracteres)",
    "alt_text": "Descripción de la imagen para SEO",
    "categoria": "Categoría apropiada"
}}

IMPORTANTE:
- Escribe como periodista argentino serio
- Usa HTML semántico correcto
- El contenido debe ser informativo y completo
- Los tags deben ser relevantes al tema
- El slug debe ser SEO-friendly
"""

    try:
        logger.info("🎯 Enviando request a Groq con llama-3.3-70b-versatile...")
        
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048
        )
        
        response_text = completion.choices[0].message.content
        logger.critical(f"🎯 ✅ Respuesta Groq recibida: {len(response_text)} caracteres")
        logger.critical(f"🎯 RESPUESTA GROQ COMPLETA: {response_text[:500]}...")
        
        # Extraer JSON
        json_data = extract_json_robust(response_text)
        
        if json_data:
            logger.critical("🎯 ✅ JSON extraído correctamente")
            logger.critical(f"🎯 Título generado: {json_data.get('titulo', 'NO_TITULO')}")
            logger.critical(f"🎯 Slug generado: {json_data.get('slug', 'NO_SLUG')}")
            logger.critical(f"🎯 Tags generados: {json_data.get('tags', [])}")
            return json_data
        else:
            logger.error("🎯 ❌ No se pudo extraer JSON válido")
            return None
            
    except Exception as e:
        logger.error(f"🎯 ❌ Error con Groq: {e}")
        return None

async def upload_image_wordpress_xmlrpc(image_url: str, alt_text: str, filename: str) -> Tuple[Optional[str], Optional[int]]:
    """Sube imagen a WordPress usando XML-RPC (método original)"""
    logger.critical(f"🎯 SUBIENDO IMAGEN VÍA XML-RPC")
    logger.critical(f"🎯 Alt text: {alt_text}")
    logger.critical(f"🎯 Filename: {filename}")
    
    if not wp_client:
        logger.error("🎯 ❌ Cliente WordPress no disponible")
        return None, None
    
    try:
        # Descargar imagen
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    logger.error(f"🎯 ❌ Error descargando imagen: {response.status}")
                    return None, None
                
                image_data = await response.read()
                logger.critical(f"🎯 ✅ Imagen descargada: {len(image_data)} bytes")
                
                # Preparar datos para WordPress XML-RPC
                data = {
                    'name': filename,
                    'type': 'image/jpeg',
                    'bits': image_data
                }
                
                logger.critical("🎯 Subiendo vía XML-RPC...")
                
                # Subir usando XML-RPC (método original)
                response = wp_client.call(media.UploadFile(data))
                
                if response and 'url' in response:
                    logger.critical(f"🎯 ✅ IMAGEN SUBIDA CORRECTAMENTE: {response['url']}")
                    return response['url'], response.get('id')
                else:
                    logger.error("🎯 ❌ Respuesta inválida de WordPress XML-RPC")
                    logger.critical(f"🎯 Respuesta completa: {response}")
                    return None, None
                
    except Exception as e:
        logger.error(f"🎯 ❌ Error subiendo imagen vía XML-RPC: {e}")
        return None, None

async def create_wordpress_post(article_data: Dict[str, Any], image_url: Optional[str] = None) -> Tuple[Optional[int], Optional[str]]:
    """Crea post en WordPress usando XML-RPC"""
    logger.critical("🎯 Creando post en WordPress vía XML-RPC")
    
    if not wp_client:
        logger.error("🎯 ❌ Cliente WordPress no disponible")
        return None, None
    
    try:
        # Crear post
        post = wordpress_xmlrpc.WordPressPost()
        post.title = article_data['titulo']
        post.slug = article_data['slug']
        
        # Contenido HTML con imagen
        content = ""
        if image_url:
            content += f'<img src="{image_url}" alt="{article_data["alt_text"]}" class="wp-image-featured" style="width:100%; height:auto; margin-bottom: 20px;">\n\n'
        
        content += article_data['contenido_html']
        
        post.content = content
        post.excerpt = article_data.get('meta_descripcion', '')
        post.terms_names = {
            'post_tag': article_data.get('tags', []),
            'category': [article_data.get('categoria', 'General')]
        }
        
        # Publicar
        post.post_status = 'publish'
        
        logger.critical("🎯 Publicando post...")
        logger.critical(f"🎯 Título: {post.title}")
        logger.critical(f"🎯 Slug: {post.slug}")
        logger.critical(f"🎯 Tags: {article_data.get('tags', [])}")
        
        post_id = wp_client.call(posts.NewPost(post))
        
        if post_id:
            post_url = f"{WP_URL.rstrip('/')}/wp-admin/post.php?post={post_id}&action=edit"
            public_url = f"{WP_URL.rstrip('/')}/{post.slug}"
            logger.critical(f"🎯 ✅ POST CREADO EXITOSAMENTE: ID {post_id}")
            logger.critical(f"🎯 ✅ URL EDICIÓN: {post_url}")
            logger.critical(f"🎯 ✅ URL PÚBLICA: {public_url}")
            return post_id, post_url
        else:
            logger.error("🎯 ❌ Error creando post")
            return None, None
            
    except Exception as e:
        logger.error(f"🎯 ❌ Error creando post: {e}")
        return None, None

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook de Telegram mejorado"""
    logger.critical("🎯 v6.2.0: WEBHOOK RECIBIDO")
    
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'status': 'no_message'}), 200
        
        message = data['message']
        
        # Solo procesar mensajes con foto y caption
        if 'photo' not in message or 'caption' not in message:
            return jsonify({'status': 'no_photo_caption'}), 200
        
        # Ejecutar procesamiento asíncrono
        asyncio.run(process_message(message))
        
        return jsonify({'status': 'processing'}), 200
        
    except Exception as e:
        logger.error(f"🎯 ❌ Error en webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

async def process_message(message):
    """Procesa mensaje de Telegram"""
    logger.critical("🎯 Procesando mensaje...")
    
    try:
        caption = message['caption']
        photo = message['photo'][-1]  # Mejor calidad
        
        # Obtener URL de la imagen
        bot_token = TELEGRAM_BOT_TOKEN
        file_id = photo['file_id']
        
        file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        file_response = requests.get(file_info_url)
        file_data = file_response.json()
        
        if not file_data['ok']:
            logger.error("🎯 ❌ Error obteniendo info del archivo")
            return
        
        file_path = file_data['result']['file_path']
        image_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        
        logger.critical(f"🎯 Caption: {caption[:100]}...")
        logger.critical(f"🎯 Image URL: {image_url}")
        
        # Generar contenido SEO
        article_data = await generate_seo_content(caption, image_url)
        
        if not article_data:
            logger.error("🎯 ❌ No se pudo generar contenido")
            return
        
        # Subir imagen
        filename = f"{safe_filename(article_data['titulo'])}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        wp_image_url, image_id = await upload_image_wordpress_xmlrpc(
            image_url, 
            article_data['alt_text'], 
            filename
        )
        
        if not wp_image_url:
            logger.error("🎯 ❌ Error subiendo imagen")
            return
        
        # Crear post
        post_id, post_url = await create_wordpress_post(article_data, wp_image_url)
        
        if post_id:
            logger.critical("🎯 ✅ ¡¡¡ PROCESO COMPLETADO EXITOSAMENTE !!!")
            logger.critical(f"🎯 ✅ Post ID: {post_id}")
            logger.critical(f"🎯 ✅ URL Edición: {post_url}")
            logger.critical("🎯 ✅ ¡¡¡ BOT FUNCIONANDO AL 100% !!!")
        else:
            logger.error("🎯 ❌ Error creando post")
            
    except Exception as e:
        logger.error(f"🎯 ❌ Error procesando mensaje: {e}")

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'running',
        'version': '6.2.0',
        'method': 'XML-RPC',
        'wp_connected': wp_client is not None,
        'groq_model': 'llama-3.3-70b-versatile'
    })

if __name__ == '__main__':
    logger.critical("🎯 v6.2.0 lista para recibir webhooks")
    logger.critical("🎯 MODELO: llama-3.3-70b-versatile (OFICIAL)")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
