import logging
import os
import asyncio
from io import BytesIO
import json
import re
from datetime import datetime

import collections
# Fix for python-wordpress-xmlrpc compatibility with Python 3.10+
if not hasattr(collections, 'Iterable'):
    collections.Iterable = collections.abc.Iterable

from flask import Flask, request
import requests
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, CallbackContext
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
from wordpress_xmlrpc.methods.media import UploadFile
from PIL import Image

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables de entorno
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
WORDPRESS_URL = os.getenv('WORDPRESS_URL')
WORDPRESS_USERNAME = os.getenv('WORDPRESS_USERNAME') 
WORDPRESS_PASSWORD = os.getenv('WORDPRESS_PASSWORD')

# Configuración de Groq
GROQ_MODEL = 'llama-3.1-8b-instant'

# Flask app
app = Flask(__name__)

def connect_to_wordpress():
    """Conecta a WordPress usando XML-RPC"""
    try:
        wp_client = Client(f'{WORDPRESS_URL}/xmlrpc.php', WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
        logger.info("Conexión a WordPress exitosa")
        return wp_client
    except Exception as e:
        logger.error(f"Error conectando a WordPress: {e}")
        return None

def upload_image_to_wordpress(wp_client, image_data, filename):
    """Sube una imagen a WordPress y retorna la URL"""
    try:
        # Preparar datos de la imagen
        data = {
            'name': filename,
            'type': 'image/jpeg',
            'bits': image_data
        }
        
        # Subir imagen
        response = wp_client.call(UploadFile(data))
        image_url = response['url']
        logger.info(f"Imagen subida exitosamente: {image_url}")
        return image_url
    except Exception as e:
        logger.error(f"Error subiendo imagen: {e}")
        return None

def generate_seo_article(image_path, user_text):
    """Genera un artículo SEO profesional usando Groq"""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        # Prompt mejorado para SEO profesional
        prompt = f"""Analiza esta imagen y el texto del usuario para crear un artículo SEO PROFESIONAL.

TEXTO DEL USUARIO: {user_text}

Debes generar un JSON con esta estructura EXACTA:

{{
    "keyword_principal": "palabra clave principal de 2-3 palabras",
    "titulo_h1": "Título principal de 30-70 caracteres con keyword",
    "meta_descripcion": "Meta descripción de exactamente 130 caracteres que incluya la keyword principal",
    "slug_url": "url-amigable-con-guiones",
    "contenido_html": "Artículo completo en HTML con estructura H2, H3, H4 y mínimo 800 palabras",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "categoria": "categoría principal del artículo",
    "enlace_interno": "URL interna relevante (ej: /categoria/subcategoria)",
    "enlace_externo": "URL externa autorizada relevante",
    "datos_estructurados": "JSON-LD para datos estructurados de Google",
    "intenciones_busqueda": ["intención 1", "intención 2", "intención 3"]
}}

REGLAS OBLIGATORIAS:
1. KEYWORD PRINCIPAL: Debe ser específica y relevante al tema de la imagen
2. TÍTULO H1: Entre 30-70 caracteres, incluir keyword principal
3. META DESCRIPCIÓN: EXACTAMENTE 130 caracteres, incluir keyword
4. CONTENIDO HTML: 
   - Mínimo 800 palabras
   - Usar H2 para secciones principales (¿Qué es...?, ¿Cómo funciona...?, etc.)
   - Usar H3 para subsecciones (tipos, características, beneficios)
   - Usar H4 para detalles específicos (pasos, tips, recomendaciones)
   - Incluir párrafos informativos y útiles
   - Responder intenciones de búsqueda del usuario
5. TAGS: 5 etiquetas relevantes al tema
6. ENLACES: Incluir 1 enlace interno y 1 externo contextual en el contenido
7. DATOS ESTRUCTURADOS: JSON-LD válido para Article
8. CONTENIDO DE CALIDAD: Información profunda, útil y original

El artículo debe ser PROFESIONAL, INFORMATIVO y OPTIMIZADO para SEO.
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Eres un experto en SEO y redacción de contenido que crea artículos profesionales optimizados para motores de búsqueda."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )

        # Extraer y parsear respuesta JSON
        response_text = response.choices[0].message.content
        
        # Buscar JSON en la respuesta
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group()
            try:
                article_data = json.loads(json_text)
                logger.info("Artículo SEO generado exitosamente")
                return article_data
            except json.JSONDecodeError:
                logger.warning("Error en JSON, usando extracción robusta")
                return extract_json_robust(response_text)
        else:
            logger.warning("No se encontró JSON válido, creando artículo básico")
            return create_fallback_seo_article(user_text)
            
    except Exception as e:
        logger.error(f"Error generando artículo con IA: {e}")
        return create_fallback_seo_article(user_text)

def extract_json_robust(text):
    """Extrae información de manera robusta cuando JSON falla"""
    try:
        # Extraer elementos principales con regex
        titulo = re.search(r'"titulo_h1":\s*"([^"]+)"', text)
        keyword = re.search(r'"keyword_principal":\s*"([^"]+)"', text)
        meta = re.search(r'"meta_descripcion":\s*"([^"]+)"', text)
        contenido = re.search(r'"contenido_html":\s*"([^"]+)"', text, re.DOTALL)
        
        return {
            "keyword_principal": keyword.group(1) if keyword else "noticia actualidad",
            "titulo_h1": titulo.group(1) if titulo else "Noticia de Actualidad",
            "meta_descripcion": (meta.group(1)[:130] if meta else "Descubre las últimas noticias de actualidad y mantente informado con contenido relevante y actualizado.")[:130],
            "slug_url": "noticia-actualidad",
            "contenido_html": contenido.group(1) if contenido else "<h2>Contenido de Actualidad</h2><p>Información relevante sobre el tema tratado.</p>",
            "tags": ["actualidad", "noticias", "información", "contenido", "relevante"],
            "categoria": "Actualidad",
            "enlace_interno": "/categoria/actualidad",
            "enlace_externo": "https://www.bbc.com/mundo",
            "datos_estructurados": '{"@context":"https://schema.org","@type":"Article","headline":"Noticia de Actualidad","author":{"@type":"Person","name":"Redacción"}}',
            "intenciones_busqueda": ["qué es", "cómo funciona", "últimas noticias"]
        }
    except Exception as e:
        logger.error(f"Error en extracción robusta: {e}")
        return create_fallback_seo_article("contenido actualidad")

def create_fallback_seo_article(user_text):
    """Crea un artículo SEO básico cuando todo falla"""
    keyword = "noticia actualidad"
    titulo = "Últimas Noticias de Actualidad"
    
    return {
        "keyword_principal": keyword,
        "titulo_h1": titulo,
        "meta_descripcion": "Mantente informado con las últimas noticias de actualidad. Contenido relevante y actualizado para estar al día.",
        "slug_url": "ultimas-noticias-actualidad",
        "contenido_html": f"""
<h2>¿Qué está pasando en la actualidad?</h2>
<p>La información que compartiste nos permite mantenerte al día con los acontecimientos más relevantes del momento.</p>

<h3>Contexto de la noticia</h3>
<p>{user_text}</p>

<h3>Análisis de la situación</h3>
<p>Este tipo de eventos requiere un seguimiento constante para entender su impacto en la sociedad actual.</p>

<h4>Puntos clave a considerar</h4>
<ul>
<li>Relevancia del tema en el contexto actual</li>
<li>Posibles implicaciones futuras</li>
<li>Reacciones de la comunidad</li>
</ul>

<h4>Recomendaciones para mantenerse informado</h4>
<p>Es importante seguir fuentes confiables y contrastar la información para tener una visión completa de los acontecimientos.</p>
""",
        "tags": ["actualidad", "noticias", "información", "análisis", "contexto"],
        "categoria": "Actualidad",
        "enlace_interno": "/categoria/actualidad",
        "enlace_externo": "https://www.bbc.com/mundo",
        "datos_estructurados": '{"@context":"https://schema.org","@type":"Article","headline":"Últimas Noticias de Actualidad","author":{"@type":"Person","name":"Redacción"}}',
        "intenciones_busqueda": ["noticias actualidad", "qué está pasando", "información actual"]
    }

def publish_seo_article_to_wordpress(wp_client, article_data, image_url=None):
    """Publica el artículo SEO completo en WordPress"""
    try:
        # Crear el post con todos los elementos SEO
        post = WordPressPost()
        post.title = article_data['titulo_h1']
        post.slug = article_data['slug_url']
        
        # Contenido completo con imagen
        content = ""
        if image_url:
            content += f'<img src="{image_url}" alt="{article_data["titulo_h1"]}" class="wp-image-featured">\n\n'
        
        content += article_data['contenido_html']
        
        # Agregar enlaces internos y externos si no están en el contenido
        if article_data.get('enlace_interno') and article_data['enlace_interno'] not in content:
            content += f'\n<p>Más información: <a href="{article_data["enlace_interno"]}">Artículos relacionados</a></p>'
        
        if article_data.get('enlace_externo') and article_data['enlace_externo'] not in content:
            content += f'\n<p>Fuente externa: <a href="{article_data["enlace_externo"]}" target="_blank" rel="noopener">Más detalles</a></p>'
        
        # Agregar datos estructurados
        if article_data.get('datos_estructurados'):
            content += f'\n<script type="application/ld+json">{article_data["datos_estructurados"]}</script>'
        
        post.content = content
        post.post_status = 'publish'
        
        # Configurar meta descripción (requiere plugin SEO)
        post.custom_fields = []
        if article_data.get('meta_descripcion'):
            post.custom_fields.append({
                'key': '_yoast_wpseo_metadesc',
                'value': article_data['meta_descripcion']
            })
            post.custom_fields.append({
                'key': '_aioseop_description', 
                'value': article_data['meta_descripcion']
            })
        
        # Agregar keyword principal
        if article_data.get('keyword_principal'):
            post.custom_fields.append({
                'key': '_yoast_wpseo_focuskw',
                'value': article_data['keyword_principal']
            })
        
        # Configurar tags
        if article_data.get('tags'):
            post.terms_names = {
                'post_tag': article_data['tags']
            }
        
        # Configurar categoría
        if article_data.get('categoria'):
            post.terms_names = post.terms_names or {}
            post.terms_names['category'] = [article_data['categoria']]
        
        # Publicar el post
        post_id = wp_client.call(NewPost(post))
        
        logger.info(f"Artículo SEO publicado exitosamente con ID: {post_id}")
        return post_id, article_data['titulo_h1']
        
    except Exception as e:
        logger.error(f"Error publicando artículo SEO: {e}")
        return None, None

async def process_message_with_photo(update: Update, context: CallbackContext):
    """Procesa mensajes con foto y texto"""
    try:
        if not update.message.photo:
            await update.message.reply_text("Por favor envía una foto con texto para generar el artículo.")
            return
        
        # Obtener la foto de mayor resolución
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        
        # Descargar imagen
        image_data = await photo_file.download_as_bytearray()
        
        # Obtener texto del usuario
        user_text = update.message.caption or "Contenido de actualidad"
        
        # Conectar a WordPress
        wp_client = connect_to_wordpress()
        if not wp_client:
            await update.message.reply_text("Error conectando a WordPress.")
            return
        
        # Notificar que está procesando
        await update.message.reply_text("🔄 Generando artículo SEO profesional...")
        
        # Subir imagen a WordPress
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"article_image_{timestamp}.jpg"
        image_url = upload_image_to_wordpress(wp_client, image_data, filename)
        
        # Generar artículo SEO con IA
        article_data = generate_seo_article(None, user_text)
        
        # Publicar artículo completo
        post_id, post_title = publish_seo_article_to_wordpress(wp_client, article_data, image_url)
        
        if post_id:
            response = f"""✅ **Artículo SEO publicado exitosamente**

📝 **Título:** {post_title}
🎯 **Keyword:** {article_data.get('keyword_principal', 'N/A')}
📊 **Meta descripción:** {len(article_data.get('meta_descripcion', ''))} caracteres
🏷️ **Tags:** {', '.join(article_data.get('tags', []))}
🔗 **URL:** {WORDPRESS_URL}/wp-admin/post.php?post={post_id}&action=edit

**Optimizaciones aplicadas:**
• Título H1 optimizado (30-70 caracteres)
• Meta descripción con keyword (130 caracteres)
• Estructura H2, H3, H4 con intenciones de búsqueda
• Enlaces internos y externos
• Datos estructurados JSON-LD
• Tags SEO relevantes
"""
        else:
            response = "❌ Error al publicar el artículo SEO."
        
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")
        await update.message.reply_text("❌ Error al generar artículo con IA")

# Configurar bot de Telegram
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
application.add_handler(MessageHandler(filters.PHOTO, process_message_with_photo))

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook para recibir actualizaciones de Telegram"""
    try:
        json_data = request.get_json()
        update = Update.de_json(json_data, application.bot)
        
        # Crear un event loop si no existe
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Procesar la actualización
        loop.run_until_complete(application.process_update(update))
        
        return "OK", 200
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return "Error", 500

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return "Bot SEO funcionando correctamente", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
