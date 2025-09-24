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

# WordPress XML-RPC - FIX CRÍTICO Python 3.10+ compatibility
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
# VERSIÓN v6.5.2 - ULTRA ESTABLE CON TODAS LAS MEJORAS
# ==========================================
logger.critical("🏆 === VERSIÓN v6.5.2 - ULTRA ESTABLE + SEO COMPLETO === 🏆")
logger.critical("🏆 === IMAGEN DESTACADA + ALT TEXT + SEO + TELEGRAM === 🏆")

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
        
        logger.critical(f"🏆 Conectando a XML-RPC: {xmlrpc_url}")
        logger.critical(f"🏆 Usuario: {WP_USERNAME}")
        
        wp_client = Client(xmlrpc_url, WP_USERNAME, WP_PASSWORD)
        logger.critical("🏆 ✅ Cliente WordPress XML-RPC configurado correctamente")
    except Exception as e:
        logger.error(f"🏆 ❌ Error configurando WordPress: {e}")

def send_telegram_message(chat_id: int, text: str) -> bool:
    """Envía respuesta a Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("🏆 ❌ TELEGRAM_BOT_TOKEN no configurado")
        return False
        
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.critical(f"🏆 ✅ RESPUESTA TELEGRAM ENVIADA chat {chat_id}")
            return True
        else:
            logger.error(f"🏆 ❌ Error respuesta Telegram: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"🏆 ❌ Error respuesta Telegram: {e}")
        return False

def safe_filename(text: str) -> str:
    """Crea un nombre de archivo seguro desde un texto"""
    safe = re.sub(r'[^\w\s-]', '', text).strip().lower()
    safe = re.sub(r'[-\s]+', '-', safe)
    return safe[:50] if safe else 'imagen'

def extract_json_robust(text: str) -> Optional[Dict[str, Any]]:
    """Extracción JSON ultra-robusta con manejo de HTML escapado"""
    logger.critical(f"🏆 Extrayendo JSON de {len(text)} caracteres...")
    
    text = text.strip()
    
    # Estrategia 1: JSON directo
    try:
        result = json.loads(text)
        logger.critical("🏆 ✅ JSON directo exitoso")
        return result
    except Exception as e:
        logger.info(f"🏆 JSON directo falló: {str(e)[:100]}")
    
    # Estrategia 2: Buscar entre ```json y ```
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if json_match:
        json_content = json_match.group(1).strip()
        logger.critical(f"🏆 JSON extraído del markdown: {len(json_content)} chars")
        try:
            result = json.loads(json_content)
            logger.critical("🏆 ✅ JSON con markdown exitoso")
            return result
        except Exception as e:
            logger.critical(f"🏆 JSON markdown falló: {str(e)[:100]}")
            logger.critical(f"🏆 JSON problemático: {json_content[:200]}...")
    
    # Estrategia 3: Buscar estructura { ... } con mejor regex
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        json_content = brace_match.group(0)
        logger.critical(f"🏆 JSON con braces encontrado: {len(json_content)} chars")
        try:
            result = json.loads(json_content)
            logger.critical("🏆 ✅ JSON con braces exitoso")
            return result
        except Exception as e:
            logger.critical(f"🏆 JSON braces falló: {str(e)[:100]}")
    
    # Estrategia 4: Limpiar HTML escapado y reintentar
    try:
        # Reemplazar entidades HTML comunes
        cleaned_text = text.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        
        # Buscar JSON después de limpiar
        json_match = re.search(r'```json\s*(.*?)\s*```', cleaned_text, re.DOTALL | re.IGNORECASE)
        if json_match:
            result = json.loads(json_match.group(1).strip())
            logger.critical("🏆 ✅ JSON con HTML limpio exitoso")
            return result
    except Exception as e:
        logger.critical(f"🏆 HTML limpio falló: {str(e)[:100]}")
    
    logger.error("🏆 ❌ Todas las estrategias JSON fallaron")
    logger.critical(f"🏆 Texto completo para debug: {text[:500]}...")
    return None

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
            temperature=0.3
        )
        
        ai_response = completion.choices[0].message.content
        logger.critical(f"🏆 ✅ Respuesta Groq recibida: {len(ai_response)} caracteres")
        
        # Extraer JSON usando estrategia robusta
        article_data = extract_json_robust(ai_response)
        
        if article_data:
            # Validaciones y defaults
            if "tags" not in article_data:
                article_data["tags"] = ["actualidad", "noticias", "argentina"]
            if "slug" not in article_data:
                article_data["slug"] = safe_filename(article_data.get("titulo", "articulo"))
            if "meta_descripcion" not in article_data:
                article_data["meta_descripcion"] = f"{article_data.get('titulo', 'Artículo de actualidad')[:150]}..."
            if "frase_clave" not in article_data:
                title_words = article_data.get("titulo", "actualidad").lower().split()[:3]
                article_data["frase_clave"] = " ".join(title_words)
            if "alt_text" not in article_data:
                article_data["alt_text"] = f"Imagen sobre {article_data.get('titulo', 'actualidad')[:30]}"
            if "categoria" not in article_data:
                article_data["categoria"] = "General"
            
            # Validar longitudes
            if len(article_data["meta_descripcion"]) > 160:
                article_data["meta_descripcion"] = article_data["meta_descripcion"][:157] + "..."
            
            if len(article_data["alt_text"]) > 50:
                article_data["alt_text"] = article_data["alt_text"][:47] + "..."
            
            logger.critical("🏆 ✅ Artículo generado exitosamente")
            logger.critical(f"🏆 Título: {article_data['titulo']}")
            logger.critical(f"🏆 🎯 Frase clave SEO: {article_data['frase_clave']}")
            logger.critical(f"🏆 📝 Meta descripción: {article_data['meta_descripcion']}")
            logger.critical(f"🏆 🖼️ Alt text: {article_data['alt_text']}")
            
            return article_data
        else:
            logger.error("🏆 ❌ JSON inválido, usando fallback")
            return create_fallback_article(caption)
            
    except Exception as e:
        logger.error(f"🏆 ❌ Error en Groq: {e}")
        return create_fallback_article(caption)

def create_fallback_article(caption: str) -> Dict[str, Any]:
    """Crea artículo de emergencia con SEO"""
    words = caption.split()[:8]
    title = " ".join(words) if words else "Noticia de Actualidad"
    
    return {
        "titulo": title[:60],
        "slug": safe_filename(title),
        "contenido_html": f"<h2>Información Reportada</h2><p>{caption}</p><h3>Contexto</h3><p>Esta información requiere seguimiento de fuentes oficiales.</p>",
        "tags": ["actualidad", "noticias", "argentina", "breaking", "info"],
        "meta_descripcion": caption[:150] + "..." if len(caption) > 150 else caption,
        "frase_clave": " ".join(words[:3]) if len(words) >= 3 else "actualidad",
        "alt_text": f"Imagen sobre {' '.join(words[:4])}" if words else "Imagen de actualidad",
        "categoria": "General"
    }

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
                    logger.critical(f"🏆 🔧 CONFIGURANDO ALT TEXT: {alt_text}")
                    
                    # Crear post del attachment para actualizar alt text
                    attachment_post = wordpress_xmlrpc.WordPressPost()
                    attachment_post.id = attachment_id
                    
                    # Configurar custom fields para alt text
                    attachment_post.custom_fields = [
                        {'key': '_wp_attachment_image_alt', 'value': alt_text}
                    ]
                    
                    # Actualizar attachment
                    wp_client.call(posts.EditPost(attachment_id, attachment_post))
                    
                    logger.critical(f"🏆 ✅ ALT TEXT CONFIGURADO EN ATTACHMENT: {alt_text}")
                    
                except Exception as e:
                    logger.warning(f"🏆 ⚠️ Error configurando alt text: {e}")
            
            return wp_image_url, attachment_id
        else:
            logger.error("🏆 ❌ Respuesta inválida de WordPress XML-RPC")
            return None, None
            
    except Exception as e:
        logger.error(f"🏆 ❌ Error subiendo imagen: {e}")
        return None, None

async def create_wordpress_post(article_data: Dict[str, Any], image_url: str, attachment_id: int, chat_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
    """Crea post en WordPress CON TODAS LAS MEJORAS: imagen destacada + SEO + alt text"""
    logger.critical("🏆 Creando post en WordPress vía XML-RPC CON SEO COMPLETO")
    
    if not wp_client:
        logger.error("🏆 ❌ Cliente WordPress no disponible")
        if chat_id:
            send_telegram_message(chat_id, "🏆 ❌ Error: Cliente WordPress no disponible")
        return None, None
    
    try:
        # Crear el post
        post = wordpress_xmlrpc.WordPressPost()
        post.title = article_data['titulo']
        post.slug = article_data['slug']
        
        # Contenido con imagen CON ALT TEXT
        content = f'<p><img src="{image_url}" alt="{article_data["alt_text"]}" class="wp-image-featured" style="width:100%; height:auto; margin-bottom: 20px;"></p>\n\n'
        content += article_data['contenido_html']
        
        post.content = content
        post.excerpt = article_data.get('meta_descripcion', '')
        
        # Tags y categoría
        post.terms_names = {
            'post_tag': article_data.get('tags', []),
            'category': [article_data.get('categoria', 'General')]
        }
        
        # 🏆 CRÍTICO 1: IMAGEN DESTACADA
        if attachment_id:
            post.thumbnail = attachment_id
            logger.critical(f"🏆 ✅ IMAGEN DESTACADA CONFIGURADA: ID {attachment_id}")
        
        # 🏆 CRÍTICO 2 y 3: CAMPOS SEO
        post.custom_fields = []
        
        # Meta descripción para SEO
        if article_data.get('meta_descripcion'):
            post.custom_fields.append({
                'key': '_yoast_wpseo_metadesc',
                'value': article_data['meta_descripcion']
            })
            logger.critical(f"🏆 ✅ META DESCRIPCIÓN SEO: {article_data['meta_descripcion']}")
        
        # Frase clave objetivo para SEO  
        if article_data.get('frase_clave'):
            post.custom_fields.append({
                'key': '_yoast_wpseo_focuskw',
                'value': article_data['frase_clave']
            })
            logger.critical(f"🏆 ✅ FRASE CLAVE OBJETIVO: {article_data['frase_clave']}")
        
        # Publicar
        post.post_status = 'publish'
        
        logger.critical("🏆 Publicando post...")
        logger.critical(f"🏆 Título: {post.title}")
        logger.critical(f"🏆 Slug: {post.slug}")
        logger.critical(f"🏆 Tags: {article_data.get('tags', [])}")
        logger.critical(f"🏆 🖼️ Alt text: {article_data['alt_text']}")
        
        post_id = wp_client.call(posts.NewPost(post))
        
        if post_id:
            post_url = f"{WP_URL.rstrip('/')}/wp-admin/post.php?post={post_id}&action=edit"
            public_url = f"{WP_URL.rstrip('/')}/{post.slug}"
            
            logger.critical(f"🏆 ✅ POST CREADO EXITOSAMENTE: ID {post_id}")
            logger.critical(f"🏆 ✅ URL EDICIÓN: {post_url}")
            logger.critical(f"🏆 ✅ URL PÚBLICA: {public_url}")
            logger.critical("🏆 ✅ 🎯 SEO COMPLETO: Imagen destacada + Alt text + Meta descripción + Frase clave")
            
            # 🏆 RESPUESTA TELEGRAM
            if chat_id:
                success_message = f"""🏆 <b>¡Artículo publicado exitosamente!</b>

📰 <b>{article_data['titulo']}</b>
🔗 <code>{article_data['slug']}</code>
🏷️ {', '.join(article_data['tags'][:3])}

📝 <b>Post ID:</b> {post_id}
📊 <b>Estado:</b> PUBLICADO
🎯 <b>SEO:</b> ✅ Imagen destacada ✅ Alt text ✅ Meta descripción ✅ Frase clave

🖼️ <b>Alt text:</b> {article_data['alt_text']}
🎯 <b>Frase clave:</b> {article_data['frase_clave']}

🌐 <a href="{public_url}">Ver artículo público</a>
⚙️ <a href="{post_url}">Editar en WordPress</a>"""

                send_telegram_message(chat_id, success_message)
            
            return post_id, post_url
        else:
            logger.error("🏆 ❌ Error creando post")
            if chat_id:
                send_telegram_message(chat_id, "🏆 ❌ Error: No se pudo crear el post")
            return None, None
            
    except Exception as e:
        logger.error(f"🏆 ❌ Error creando post: {e}")
        if chat_id:
            send_telegram_message(chat_id, f"🏆 ❌ Error creando post: {str(e)[:100]}")
        return None, None

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
        post_id, edit_url = await create_wordpress_post(
            article_data,
            wp_image_url, 
            attachment_id,
            chat_id
        )
        
        if post_id:
            logger.critical("🏆 ✅ ¡¡¡ PROCESO COMPLETADO EXITOSAMENTE !!!")
            logger.critical(f"🏆 ✅ Post ID: {post_id}")
            logger.critical(f"🏆 ✅ Alt text: {article_data['alt_text']}")
            logger.critical("🏆 ✅ ¡¡¡ BOT 100% FUNCIONAL CON TODAS LAS MEJORAS !!!")
            
            return {
                "status": "success",
                "post_id": post_id,
                "edit_url": edit_url,
                "image_url": wp_image_url,
                "alt_text": article_data['alt_text']
            }
        else:
            return {"status": "error", "message": "Error creating post"}
            
    except Exception as e:
        logger.error(f"🏆 ❌ Error procesando mensaje: {e}")
        if chat_id:
            send_telegram_message(chat_id, f"🏆 ❌ Error crítico: {str(e)[:100]}")
        return {"status": "error", "message": str(e)}

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook de Telegram v6.5.2"""
    logger.critical("🏆 v6.5.2: WEBHOOK RECIBIDO")
    
    try:
        data = request.get_json()
        
        if 'message' in data:
            message = data['message']
            logger.critical("🏆 Procesando mensaje...")
            
            if 'photo' in message:
                # Procesar en background
                asyncio.create_task(process_telegram_image_message(message))
                return jsonify({"status": "processing"})
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"🏆 ❌ Error en webhook: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "version": "6.5.2",
        "wordpress_url": WP_URL,
        "features": {
            "xml_rpc": True,
            "featured_image": True,
            "alt_text_attachment": True,
            "seo_meta_description": True, 
            "seo_focus_keyword": True,
            "yoast_seo": True,
            "telegram_response": True,
            "groq_model": "llama-3.3-70b-versatile",
            "python_compatibility_fix": True
        }
    })

if __name__ == '__main__':
    logger.critical("🏆 === INICIANDO BOT v6.5.2 - ULTRA ESTABLE + SEO COMPLETO === 🏆")
    logger.critical("🏆 ✅ IMAGEN DESTACADA: Configurada")
    logger.critical("🏆 ✅ ALT TEXT ATTACHMENT: Configurado")
    logger.critical("🏆 ✅ META DESCRIPCIÓN: Configurada")
    logger.critical("🏆 ✅ FRASE CLAVE OBJETIVO: Configurada")
    logger.critical("🏆 ✅ RESPUESTA TELEGRAM: Activada")
    logger.critical("🏆 ✅ PYTHON 3.10+ COMPATIBILITY: Fix aplicado")
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
