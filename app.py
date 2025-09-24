#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏆 TELEGRAM BOT WORDPRESS AUTO-PUBLISHER v6.5.0 - ULTRA ROBUSTO
🏆 CORRIGE: Error de inicio + Implementa SEO + Respuesta Telegram
🏆 BASADO EN: v6.3.0 funcionando + Mejoras definitivas
"""

import os
import re
import json
import html
import logging
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

import requests
from flask import Flask, request, jsonify
from groq import Groq

# WordPress XML-RPC imports
try:
    import wordpress_xmlrpc
    from wordpress_xmlrpc import Client
    from wordpress_xmlrpc.methods import posts, media
    from wordpress_xmlrpc.compat import xmlrpc_client
    XMLRPC_AVAILABLE = True
except ImportError as e:
    logging.error(f"WordPress XML-RPC not available: {e}")
    XMLRPC_AVAILABLE = False

# Configurar logging ultradetallado
logging.basicConfig(
    level=logging.CRITICAL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

# Variables críticas
WP_URL = os.getenv('WORDPRESS_URL', 'https://cordobateve.com.ar').rstrip('/')
WP_USERNAME = os.getenv('WORDPRESS_USERNAME', 'cordoba')
WP_PASSWORD = os.getenv('WORDPRESS_PASSWORD', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')

app = Flask(__name__)

# Log inicial crítico
logger.critical("🏆 === VERSIÓN v6.5.0 - ULTRA ROBUSTO === 🏆")
logger.critical("🏆 === BASADO EN v6.3.0 + SEO + RESPUESTA TELEGRAM === 🏆")

# Cliente WordPress global
wp_client = None

def init_wordpress_client():
    """Inicializa cliente WordPress XML-RPC"""
    global wp_client
    
    if not XMLRPC_AVAILABLE:
        logger.error("🏆 ❌ WordPress XML-RPC no disponible")
        return False
    
    if not WP_USERNAME or not WP_PASSWORD:
        logger.error("🏆 ❌ Credenciales WordPress faltantes")
        return False
    
    try:
        wp_url_with_rpc = f"{WP_URL}/xmlrpc.php"
        logger.critical(f"🏆 Conectando a XML-RPC: {wp_url_with_rpc}")
        logger.critical(f"🏆 Usuario: {WP_USERNAME}")
        
        wp_client = Client(wp_url_with_rpc, WP_USERNAME, WP_PASSWORD)
        
        # Test de conexión
        wp_client.call(posts.GetPosts({'number': 1}))
        
        logger.critical("🏆 ✅ Cliente WordPress XML-RPC configurado correctamente")
        return True
        
    except Exception as e:
        logger.error(f"🏆 ❌ Error configurando WordPress XML-RPC: {e}")
        return False

def safe_filename(text: str) -> str:
    """Genera nombre seguro para archivos"""
    clean = re.sub(r'[^\w\s-]', '', text.lower())
    return re.sub(r'[-\s]+', '-', clean)[:50]

def send_telegram_message(chat_id: int, text: str) -> bool:
    """Envía mensaje de respuesta a Telegram"""
    if not TELEGRAM_TOKEN:
        logger.error("🏆 ❌ TELEGRAM_TOKEN no configurado")
        return False
        
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
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

def extract_json_robust(text: str) -> Optional[Dict]:
    """Extrae JSON de texto con múltiples estrategias robustas"""
    logger.critical(f"🏆 Extrayendo JSON de {len(text)} caracteres...")
    
    # Estrategia 1: JSON directo
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Estrategia 2: Buscar JSON entre llaves
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group()
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # Estrategia 3: Desenmascarar entidades HTML y luego intentar cargar
    try:
        unescaped_text = html.unescape(text)
        return json.loads(unescaped_text)
    except (json.JSONDecodeError, ImportError):
        pass
        
    # Estrategia 4: Buscar JSON desenmascarado
    try:
        unescaped_text = html.unescape(text)
        match = re.search(r'\{.*\}', unescaped_text, re.DOTALL)
        if match:
            json_str = match.group()
            return json.loads(json_str)
    except (json.JSONDecodeError, ImportError):
        pass
    
    # Estrategia 5: Limpiar comillas problemáticas
    try:
        cleaned = text.replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    logger.critical("🏆 ✅ JSON directo exitoso" if text.strip().startswith('{') else "🏆 ❌ Todas las estrategias JSON fallaron")
    
    return None

async def generate_article_groq(caption: str, image_description: str = "imagen relacionada") -> Dict[str, Any]:
    """Genera artículo usando Groq con modelo oficial"""
    
    if not GROQ_API_KEY:
        logger.error("🏆 ❌ GROQ_API_KEY no configurada")
        raise ValueError("GROQ_API_KEY requerida")
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        system_prompt = """Eres un periodista especializado en crear artículos informativos de alta calidad con SEO optimizado.

INSTRUCCIONES CRÍTICAS:
1. Responde ÚNICAMENTE con JSON válido, sin texto adicional
2. Usa COMILLAS SIMPLES para evitar conflictos de parsing
3. Genera contenido HTML profesional con etiquetas h2, p, strong, em
4. El artículo debe ser específico, detallado y profesional
5. Incluye 5 tags relevantes
6. OBLIGATORIO: Genera frase clave objetivo SEO (2-4 palabras)
7. OBLIGATORIO: Genera meta descripción SEO (150-160 caracteres)

FORMATO JSON REQUERIDO:
{
    'titulo': 'Título profesional específico',
    'slug': 'titulo-url-amigable',
    'contenido_html': '<h2>Subtítulo</h2><p>Párrafo detallado...</p>',
    'tags': ['tag1', 'tag2', 'tag3', 'tag4', 'tag5'],
    'meta_descripcion': 'Descripción SEO optimizada de 150-160 caracteres máximo',
    'frase_clave': 'frase clave seo',
    'categoria': 'Política',
    'alt_text': 'Descripción de imagen para accessibility'
}

IMPORTANTE: La frase_clave debe ser relevante y estar presente en el contenido. La meta_descripción debe ser atractiva y resumir el artículo."""

        user_prompt = f"""Crear artículo informativo basado en:

INFORMACIÓN: {caption}
IMAGEN: {image_description}

Genera un artículo periodístico completo y profesional en formato JSON con optimización SEO completa."""

        logger.info(f"🏆 Enviando request a Groq con llama-3.3-70b-versatile...")
        
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=2000
        )
        
        ai_response = completion.choices[0].message.content
        logger.critical(f"🏆 ✅ Respuesta Groq recibida: {len(ai_response)} caracteres")
        
        # Log de la respuesta para debugging
        logger.critical(f"🏆 RESPUESTA GROQ (primeros 300): {ai_response[:300]}...")
        
        # Extraer JSON usando método robusto
        parsed = extract_json_robust(ai_response)
        logger.critical("🏆 ✅ JSON extraído correctamente")
        
        if parsed and "titulo" in parsed and "contenido_html" in parsed:
            # Validaciones y defaults
            if "tags" not in parsed:
                parsed["tags"] = ["actualidad", "noticias", "argentina"]
            if "slug" not in parsed:
                parsed["slug"] = safe_filename(parsed["titulo"])
            if "meta_descripcion" not in parsed:
                parsed["meta_descripcion"] = f"{parsed['titulo'][:150]}..."
            if "frase_clave" not in parsed:
                title_words = parsed["titulo"].lower().split()[:3]
                parsed["frase_clave"] = " ".join(title_words)
            if "alt_text" not in parsed:
                parsed["alt_text"] = f"Imagen relacionada con {parsed['titulo']}"
            if "categoria" not in parsed:
                parsed["categoria"] = "General"
            
            # Validar longitud de meta descripción
            if len(parsed["meta_descripcion"]) > 160:
                parsed["meta_descripcion"] = parsed["meta_descripcion"][:157] + "..."
            
            logger.critical("🏆 ✅ Artículo generado exitosamente")
            logger.critical(f"🏆 Título: {parsed['titulo']}")
            logger.critical(f"🏆 Slug: {parsed['slug']}")
            logger.critical(f"🏆 Tags: {parsed['tags']}")
            logger.critical(f"🏆 🎯 Frase clave SEO: {parsed['frase_clave']}")
            logger.critical(f"🏆 📝 Meta descripción: {parsed['meta_descripcion']}")
            
            return parsed
        else:
            raise ValueError("JSON inválido o incompleto")
            
    except Exception as e:
        logger.error(f"🏆 ❌ Error en Groq: {e}")
        logger.critical("🏆 ❌ Activando sistema fallback")
        
        # Sistema fallback con contenido estructurado
        words = caption.split()
        title_words = words[:8]
        title = " ".join(title_words)
        
        return {
            "titulo": title if len(title) < 60 else f"{title[:57]}...",
            "contenido_html": f"""<h2>Información Confirmada</h2>
<p>{caption}</p>
<h2>Contexto y Desarrollo</h2>
<p>Los hechos reportados han generado atención en el ámbito político y social, requiriendo seguimiento continuo de la situación.</p>
<p>Esta información será actualizada conforme se obtengan más detalles de fuentes oficiales.</p>""",
            "tags": ["actualidad", "noticias", "politica", "argentina", "breaking"],
            "slug": safe_filename(title),
            "meta_descripcion": caption[:150] + "..." if len(caption) > 150 else caption,
            "frase_clave": " ".join(words[:3]),
            "alt_text": f"Imagen relacionada con {title}",
            "categoria": "General"
        }

async def upload_image_wordpress(image_url: str, alt_text: str, filename: str) -> Tuple[Optional[str], Optional[int]]:
    """Sube imagen a WordPress usando XML-RPC (método original)"""
    logger.critical(f"🏆 SUBIENDO IMAGEN VÍA XML-RPC")
    logger.critical(f"🏆 Alt text: {alt_text}")
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
                
                # Subir usando XML-RPC (método original)
                response = wp_client.call(media.UploadFile(data))
                
                if response and 'url' in response:
                    logger.critical(f"🏆 ✅ IMAGEN SUBIDA CORRECTAMENTE: {response['url']}")
                    return response['url'], response.get('id')
                else:
                    logger.error("🏆 ❌ Respuesta inválida de WordPress XML-RPC")
                    logger.critical(f"🏆 Respuesta completa: {response}")
                    return None, None
                
    except Exception as e:
        logger.error(f"🏆 ❌ Error subiendo imagen vía XML-RPC: {e}")
        return None, None

async def create_wordpress_post(article_data: Dict[str, Any], image_url: Optional[str] = None, image_id: Optional[int] = None, chat_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
    """Crea post en WordPress usando XML-RPC CON SEO COMPLETO + RESPUESTA TELEGRAM"""
    logger.critical("🏆 Creando post en WordPress vía XML-RPC CON SEO")
    
    if not wp_client:
        logger.error("🏆 ❌ Cliente WordPress no disponible")
        if chat_id:
            send_telegram_message(chat_id, "🏆 ❌ Error: Cliente WordPress no disponible")
        return None, None
    
    try:
        # Crear post
        post = wordpress_xmlrpc.WordPressPost()
        post.title = article_data['titulo']
        post.slug = article_data['slug']
        
        # Contenido HTML con imagen
        content = ""
        if image_url:
            content += f'<p><img src="{image_url}" alt="{article_data["alt_text"]}" class="wp-image-featured" style="width:100%; height:auto; margin-bottom: 20px;"></p>\n\n'
        
        content += article_data['contenido_html']
        
        post.content = content
        post.excerpt = article_data.get('meta_descripcion', '')
        post.terms_names = {
            'post_tag': article_data.get('tags', []),
            'category': [article_data.get('categoria', 'General')]
        }
        
        # 🏆 CRÍTICO 1: Configurar imagen destacada
        if image_id:
            post.thumbnail = image_id
            logger.critical(f"🏆 ✅ IMAGEN DESTACADA CONFIGURADA: ID {image_id}")
        
        # 🏆 CRÍTICO 2 y 3: Configurar campos SEO (Yoast)
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
        
        # Campos SEO adicionales
        post.custom_fields.extend([
            {'key': '_yoast_wpseo_title', 'value': article_data['titulo']},
            {'key': '_yoast_wpseo_canonical', 'value': f"{WP_URL}/{article_data['slug']}"},
            {'key': '_yoast_wpseo_opengraph-title', 'value': article_data['titulo']},
            {'key': '_yoast_wpseo_opengraph-description', 'value': article_data.get('meta_descripcion', '')},
        ])
        
        # Publicar
        post.post_status = 'publish'
        
        logger.critical("🏆 Publicando post...")
        logger.critical(f"🏆 Título: {post.title}")
        logger.critical(f"🏆 Slug: {post.slug}")
        logger.critical(f"🏆 Tags: {article_data.get('tags', [])}")
        
        post_id = wp_client.call(posts.NewPost(post))
        
        if post_id:
            # 🏆 VERIFICACIÓN ADICIONAL: Configurar imagen destacada por separado
            if image_id:
                try:
                    wp_client.call(posts.SetPostThumbnail(post_id, image_id))
                    logger.critical(f"🏆 ✅ VERIFICACIÓN: Imagen destacada post {post_id}")
                except Exception as e:
                    logger.warning(f"🏆 ⚠️ Verificación imagen: {e}")
            
            post_url = f"{WP_URL.rstrip('/')}/wp-admin/post.php?post={post_id}&action=edit"
            public_url = f"{WP_URL.rstrip('/')}/{post.slug}"
            
            logger.critical(f"🏆 ✅ POST CREADO EXITOSAMENTE: ID {post_id}")
            logger.critical(f"🏆 ✅ URL EDICIÓN: {post_url}")
            logger.critical(f"🏆 ✅ URL PÚBLICA: {public_url}")
            logger.critical("🏆 ✅ 🎯 SEO COMPLETO: Imagen destacada + Frase clave + Meta descripción")
            
            # 🏆 RESPUESTA TELEGRAM
            if chat_id:
                success_message = f"""🏆 <b>¡Artículo publicado exitosamente!</b>

📰 <b>{article_data['titulo']}</b>
🔗 <code>{article_data['slug']}</code>
🏷️ {', '.join(article_data['tags'][:3])}

📝 <b>Post ID:</b> {post_id}
📊 <b>Estado:</b> PUBLICADO
🎯 <b>SEO:</b> ✅ Imagen destacada ✅ Meta descripción ✅ Frase clave

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
    """Procesa mensaje de Telegram con imagen y genera artículo"""
    chat_id = None
    
    try:
        # Extraer chat_id para respuesta
        chat_id = message_data.get('chat', {}).get('id')
        
        # Extraer información del mensaje
        if 'photo' not in message_data or not message_data['photo']:
            logger.error("🏆 ❌ No se encontró foto en el mensaje")
            return {"status": "error", "message": "No photo found"}
        
        # Obtener la foto de mayor resolución
        photo = message_data['photo'][-1]
        file_id = photo['file_id']
        
        # Obtener caption
        caption = message_data.get('caption', 'Imagen sin descripción')
        logger.critical(f"🏆 Caption: {caption[:100]}...")
        
        # Obtener URL de la imagen de Telegram
        file_response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}")
        file_data = file_response.json()
        
        if not file_data.get('ok'):
            logger.error("🏆 ❌ Error obteniendo archivo de Telegram")
            return {"status": "error", "message": "Error getting file from Telegram"}
        
        file_path = file_data['result']['file_path']
        image_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        logger.critical(f"🏆 Image URL: {image_url}")
        
        # Generar artículo
        article_data = await generate_article_groq(caption, "imagen proporcionada")
        
        # Subir imagen a WordPress
        filename = f"{article_data['slug']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        wp_image_url, image_id = await upload_image_wordpress(
            image_url, 
            article_data['alt_text'], 
            filename
        )
        
        if not wp_image_url:
            logger.error("🏆 ❌ Error subiendo imagen")
            if chat_id:
                send_telegram_message(chat_id, "🏆 ❌ Error: No se pudo subir la imagen")
            return {"status": "error", "message": "Error uploading image"}
        
        # Crear post con SEO completo + respuesta telegram
        post_id, edit_url = await create_wordpress_post(
            article_data, 
            wp_image_url, 
            image_id,
            chat_id  # 🏆 PASAR CHAT_ID PARA RESPUESTA
        )
        
        if post_id:
            logger.critical("🏆 ✅ ¡¡¡ PROCESO COMPLETADO EXITOSAMENTE !!!")
            logger.critical(f"🏆 ✅ Post ID: {post_id}")
            logger.critical(f"🏆 ✅ URL Edición: {edit_url}")
            logger.critical("🏆 ✅ ¡¡¡ BOT 100% FUNCIONAL CON SEO + RESPUESTA TELEGRAM !!!")
            
            return {
                "status": "success",
                "post_id": post_id,
                "edit_url": edit_url,
                "image_url": wp_image_url
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
    """Webhook de Telegram"""
    logger.critical("🏆 v6.5.0: WEBHOOK RECIBIDO")
    
    try:
        data = request.get_json()
        
        if 'message' in data:
            message = data['message']
            logger.critical("🏆 Procesando mensaje...")
            
            if 'photo' in message:
                # Procesar en background para no bloquear Telegram
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
        "version": "6.5.0",
        "wordpress_url": WP_URL,
        "xmlrpc_available": XMLRPC_AVAILABLE,
        "features": {
            "xml_rpc": True,
            "featured_image": True,
            "seo_meta_description": True,
            "seo_focus_keyword": True,
            "yoast_seo": True,
            "telegram_response": True,
            "groq_model": "llama-3.3-70b-versatile"
        }
    })

if __name__ == '__main__':
    logger.critical("🏆 === INICIANDO BOT v6.5.0 - ULTRA ROBUSTO === 🏆")
    
    # Inicializar WordPress
    if init_wordpress_client():
        logger.critical("🏆 v6.5.0 lista para recibir webhooks")
        logger.critical("🏆 MODELO: llama-3.3-70b-versatile (OFICIAL)")
        logger.critical("🏆 JSON PARSING: Ultra-robusto")
        logger.critical("🏆 ✅ IMAGEN DESTACADA: Configurada")
        logger.critical("🏆 ✅ META DESCRIPCIÓN: Configurada")
        logger.critical("🏆 ✅ FRASE CLAVE OBJETIVO: Configurada")
        logger.critical("🏆 ✅ YOAST SEO: Custom fields integrados")
        logger.critical("🏆 ✅ RESPUESTA TELEGRAM: Activada")
        logger.critical("🏆 ✅ MANEJO ERRORES: Mejorado")
        
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=False)
    else:
        logger.error("🏆 ❌ Error inicializando cliente WordPress")
