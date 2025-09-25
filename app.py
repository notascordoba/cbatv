"""
TELEGRAM BOT SEO PROFESIONAL - VERSIÓN 6.5.17
===============================================
FECHA: 2025-09-26
ESTADO: CORREGIDO — Se corrige error de sintaxis y se mantienen mejoras anteriores
MEJORAS:
✅ Se corrige error de sintaxis en create_wordpress_post
✅ Se corrige alt text de imagen destacada
✅ Se limitan los tags a 3
✅ Se limita la meta descripción a 150 caracteres
✅ Se reduce la densidad de keyword a 6-8 veces
✅ Se incluye keyword en el alt text de la imagen
✅ Se coloca la keyword al inicio del título
✅ Se eliminan enlaces salientes del contenido HTML
✅ Se mantiene logging mejorado
✅ Se corrige error de sintaxis en webhook
✅ Se mejora extract_json_robust
"""
import os
import logging
import re
import json
import asyncio
from datetime import datetime
from typing import Optional, List
from urllib.parse import quote
import collections
import collections.abc

if not hasattr(collections, 'Iterable'):
    collections.Iterable = collections.abc.Iterable

from flask import Flask, request, jsonify
from telegram import Bot
import requests
import aiohttp
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
from wordpress_xmlrpc.methods.media import UploadFile
from wordpress_xmlrpc.methods import taxonomies

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuración desde variables de entorno
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
WORDPRESS_URL = os.getenv('WORDPRESS_URL')
WORDPRESS_USERNAME = os.getenv('WORDPRESS_USERNAME')
WORDPRESS_PASSWORD = os.getenv('WORDPRESS_PASSWORD')

# Inicializar clientes
groq_client = Groq(api_key=GROQ_API_KEY)
wp_client = None
existing_categories = []

# Conectar a WordPress
def init_wordpress():
    global wp_client, existing_categories
    try:
        xmlrpc_url = f"{WORDPRESS_URL.rstrip('/')}/xmlrpc.php"
        wp_client = Client(xmlrpc_url, WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
        # Obtener categorías existentes
        cats = wp_client.call(taxonomies.GetTerms('category'))
        existing_categories = [cat.name for cat in cats]
        logger.info(f"✅ WordPress conectado. Categorías: {existing_categories}")
    except Exception as e:
        logger.error(f"❌ Error al conectar a WordPress: {e}")

# Sanitizar nombre de archivo
def safe_filename(text: str) -> str:
    text = re.sub(r'[^\w\s-]', '', text.lower()).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text[:50] or 'imagen'

# Extracción robusta de JSON - MEJORADA
def extract_json_robust(text: str) -> Optional[dict]:
    text = text.strip()
    # Estrategia 1: JSON directo
    try:
        return json.loads(text)
    except:
        pass

    # Estrategia 2: ```json ... ```
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        json_text = match.group(1).strip()
        # Limpiar saltos de línea y tabulaciones dentro de cadenas JSON
        json_text = re.sub(r'(?<=")([^"]*?)\n([^"]*?)(?=")', lambda m: m.group(1).replace('\n', '\\n') + m.group(2).replace('\n', '\\n'), json_text)
        json_text = re.sub(r'(?<=")([^"]*?)\t([^"]*?)(?=")', lambda m: m.group(1).replace('\t', '\\t') + m.group(2).replace('\t', '\\t'), json_text)

        try:
            return json.loads(json_text)
        except:
            pass

    # Estrategia 3: buscar {...}
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        json_text = match.group(0)
        # Aplicar limpieza similar
        json_text = re.sub(r'(?<=")([^"]*?)\n([^"]*?)(?=")', lambda m: m.group(1).replace('\n', '\\n') + m.group(2).replace('\n', '\\n'), json_text)
        json_text = re.sub(r'(?<=")([^"]*?)\t([^"]*?)(?=")', lambda m: m.group(1).replace('\t', '\\t') + m.group(2).replace('\t', '\\t'), json_text)
        try:
            return json.loads(json_text)
        except:
            pass
    return None

# Generar contenido SEO con Groq (prompt optimizado para Yoast y sin enlaces salientes)
async def generate_seo_content(caption: str) -> Optional[dict]:
    prompt = f"""Eres un periodista argentino experto en SEO. Convierte esta información en un artículo periodístico completo y optimizado:
INFORMACIÓN: {caption}
Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:
{{
    "keyword_principal": "frase clave objetivo (2-3 palabras)",
    "titulo": "Keyword Principal: Título periodístico llamativo (30-70 caracteres)",
    "slug": "titulo-seo-amigable",
    "meta_descripcion": "Meta descripción de máximo 150 caracteres con la keyword y buen gancho",
    "contenido_html": "Artículo en HTML con <h1>, <h2>, <h3>, <p>, <strong>, <ul>, <li>. Mínimo 600 palabras. Incluye 1 enlace interno (elige entre: {', '.join(existing_categories) if existing_categories else 'actualidad'}). NO incluyas enlaces salientes a otros medios. Usa comillas simples. Repite la keyword 6-8 veces.",
    "tags": ["keyword_principal", "tag2", "tag3"],
    "alt_text": "Descripción SEO de la imagen (máx. 120 caracteres) que incluye la keyword principal",
    "categoria": "Categoría principal (elige entre: {', '.join(existing_categories) if existing_categories else 'Actualidad, Internacional, Política'})"
}}
REGLAS:
- keyword_principal: específica y relevante
- titulo: debe comenzar con la keyword_principal
- meta_descripcion: máximo 150 caracteres
- contenido_html: mínimo 600 palabras, sin comillas dobles, sin &quot;, repite keyword 6-8 veces, NO enlaces salientes
- categoría: NO inventes, usa solo las permitidas
- tags: incluye keyword_principal como primer tag, solo 3 tags
- alt_text: debe incluir la keyword principal
"""
    try:
        logger.info("🔍 Enviando solicitud a Groq...")
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=3000
        )
        raw = completion.choices[0].message.content
        logger.info("✅ Respuesta recibida de Groq. Procesando JSON...")
        logger.info(f"Respuesta cruda de Groq: {raw[:1000]}...")  # Loguea los primeros 1000 caracteres como INFO
        result = extract_json_robust(raw)
        if result:
            logger.info("✅ JSON extraído correctamente.")
            return result
        else:
            logger.error("❌ No se pudo extraer un JSON válido de la respuesta de Groq.")
            logger.info(f"Respuesta cruda de Groq: {raw[:1000]}...")  # Loguea de nuevo en caso de error
            return None
    except Exception as e:
        logger.error(f"❌ Error con Groq: {e}")
        return None

# Subir imagen a WordPress
async def upload_image_to_wp(image_url: str, alt_text: str, filename: str) -> tuple[Optional[str], Optional[int]]:
    if not wp_client:
        return None, None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    return None, None
                image_data = await resp.read()

        data = {
            'name': filename,
            'type': 'image/jpeg',
            'bits': image_data,
            'overwrite': True
        }
        response = wp_client.call(UploadFile(data))
        # Actualizar el 'alt' del archivo adjunto
        attachment_id = response['id']
        # Crear un nuevo objeto WordPressPost solo para actualizar el alt
        from wordpress_xmlrpc.methods.posts import GetPost, EditPost
        attachment_post = wp_client.call(GetPost(attachment_id))
        attachment_post.title = filename
        attachment_post.post_excerpt = alt_text  # Este campo a veces se usa como alt
        attachment_post.post_content = alt_text  # Este campo a veces se usa como alt
        wp_client.call(EditPost(attachment_id, attachment_post))
        return response['url'], attachment_id
    except Exception as e:
        logger.error(f"Error subiendo imagen: {e}")
        return None, None

# Crear post en WordPress
async def create_wordpress_post(article_ dict, image_url: Optional[str], attachment_id: Optional[int]) -> tuple[Optional[int], Optional[str]]:
    if not wp_client:
        return None, None

    post = WordPressPost()
    post.title = article_data['titulo']
    post.slug = article_data['slug']

    # Validar categoría
    categoria = article_data.get('categoria', 'Actualidad')
    if categoria not in existing_categories:
        categoria = 'Actualidad'

    # Contenido
    content = ""
    if image_url:
        content += f"<img src='{image_url}' alt='{article_data['alt_text']}' class='wp-image-featured' style='width:100%; margin-bottom:20px;'>\n"
    # Eliminar enlaces salientes del contenido HTML
    contenido_html = article_data['contenido_html']
    # Expresión regular para encontrar enlaces <a> que no apunten al dominio local
    # Esta expresión busca <a href="...">...</a> donde el href NO empieza con el dominio o es relativo
    dominio = WORDPRESS_URL.split('/')[2]  # Extrae el dominio del WORDPRESS_URL
    enlace_saliente_pattern = re.compile(r'<a\s+href="(?!https?://' + re.escape(dominio) + r'[/\w]*|/)[^"]*"[^>]*>.*?</a>', re.IGNORECASE)
    contenido_html = enlace_saliente_pattern.sub(lambda match: match.group(0).split('>')[1].split('<')[0], contenido_html) # Reemplaza el enlace con solo el texto interno
    content += contenido_html

    post.content = content

    # SEO
    post.custom_fields = [
        {'key': '_yoast_wpseo_metadesc', 'value': article_data['meta_descripcion']},
        {'key': '_aioseop_description', 'value': article_data['meta_descripcion']},
        {'key': '_yoast_wpseo_focuskw', 'value': article_data['keyword_principal']}
    ]

    # Taxonomía
    post.terms_names = {
        'post_tag': article_data['tags'],
        'category': [categoria]
    }

    # Imagen destacada
    if attachment_id:
        post.thumbnail = attachment_id

    post.post_status = 'draft'  # ← BORRADOR
    post_id = wp_client.call(NewPost(post))
    edit_url = f"{WORDPRESS_URL.rstrip('/')}/wp-admin/post.php?post={post_id}&action=edit"

    return post_id, edit_url

# Procesar mensaje de Telegram
async def process_telegram_message(message: dict):
    try:
        caption = message.get('caption', 'Contenido de actualidad')
        photo = message['photo'][-1]  # ← Índice correcto
        file_id = photo['file_id']
        chat_id = message['chat']['id']

        file_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
        file_resp = requests.get(file_info_url).json()
        if not file_resp.get('ok'):
            logger.error("❌ No se pudo obtener la info del archivo de Telegram.")
            return

        file_path = file_resp['result']['file_path']
        image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"

        # Generar contenido
        article = await generate_seo_content(caption)
        if not article:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(chat_id=chat_id, text="❌ Error: no se pudo generar el artículo.")
            return

        # Subir imagen
        filename = f"{safe_filename(article['titulo'])}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        wp_img_url, att_id = await upload_image_to_wp(image_url, article['alt_text'], filename)

        if not wp_img_url:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(chat_id=chat_id, text="❌ Error: no se pudo subir la imagen.")
            return

        # Crear post
        post_id, edit_url = await create_wordpress_post(article, wp_img_url, att_id)

        if post_id:
            response = f"""✅ **Artículo SEO creado como BORRADOR**
📝 **Título**: {article['titulo']}
🎯 **Keyword**: {article['keyword_principal']}
📊 **Meta descripción**: {len(article['meta_descripcion'])} caracteres
🏷️ **Tags**: {', '.join(article['tags'])}
📁 **Categoría**: {article.get('categoria', 'N/A')}
🖼️ **Imagen destacada**: ✅ Configurada
📄 **Nombre archivo**: {filename}
📝 **Estado**: BORRADOR
🔗 **Editar**: {edit_url}
⚠️ **Revísalo y publícalo desde WordPress**
"""
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(chat_id=chat_id, text=response, parse_mode='Markdown')
        else:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(chat_id=chat_id, text="❌ Error al crear el artículo en WordPress.")
    except KeyError as e:
        logger.error(f"❌ Error de clave faltante en mensaje de Telegram: {e}")
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=chat_id, text="❌ Error: mensaje incompleto.")
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")

# Flask app
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data or 'message' not in data:  # ← CORREGIDO AQUÍ
            return jsonify({'ok': True})

        message = data['message']
        if 'photo' not in message or 'caption' not in message:
            return jsonify({'ok': True})

        asyncio.run(process_telegram_message(message))
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'ok': False}), 500

@app.route('/', methods=['GET'])
def health():
    return jsonify({
        'status': 'running',
        'version': '6.5.17',
        'wp_connected': wp_client is not None,
        'categories': existing_categories
    })

if __name__ == '__main__':
    init_wordpress()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
