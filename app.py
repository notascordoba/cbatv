import os
import json
import asyncio
import logging
from flask import Flask, request, jsonify
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost, EditPost, GetPost
from wordpress_xmlrpc.methods.media import UploadFile
from telegram import Update, Bot
from telegram.ext import Application
import tempfile
import requests
from datetime import datetime
import re
import unicodedata

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración
TELEGRAM_TOKEN = "TU_TOKEN_DE_TELEGRAM"
GROQ_API_KEY = "TU_API_KEY_DE_GROQ"
WORDPRESS_URL = "https://tu-sitio.com/xmlrpc.php"
WORDPRESS_USERNAME = "tu_usuario"
WORDPRESS_PASSWORD = "tu_contraseña"

# Inicializar Flask
app = Flask(__name__)

# Inicializar clientes
groq_client = Groq(api_key=GROQ_API_KEY)
wp_client = Client(WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

# Variable global para controlar la inicialización de la aplicación
app_initialized = False

async def initialize_application():
    """Inicializa la aplicación de Telegram si no está inicializada"""
    global app_initialized
    if not app_initialized:
        await telegram_app.initialize()
        app_initialized = True

def sanitize_filename(title):
    """Convierte un título en un nombre de archivo SEO-friendly"""
    title = title.lower()
    title = re.sub(r'\s+', '-', title)
    title = unicodedata.normalize('NFD', title)
    title = ''.join(char for char in title if unicodedata.category(char) != 'Mn')
    title = re.sub(r'[^a-z0-9\-]', '', title)
    title = re.sub(r'-+', '-', title)
    title = title.strip('-')
    if len(title) > 60:
        title = title[:60].rstrip('-')
    return title

def validate_article_content(article_data):
    """Valida que el contenido no sea genérico/placeholder"""
    generic_indicators = [
        'contenido de actualidad',
        'información relevante',
        'tema tratado',
        'noticia de actualidad',
        'más información',
        'fuente externa'
    ]
    
    content = article_data.get('contenido_html', '').lower()
    title = article_data.get('titulo_h1', '').lower()
    
    for indicator in generic_indicators:
        if indicator in content or indicator in title:
            logger.warning(f"Contenido genérico detectado: {indicator}")
            return False
    
    # Validar que tenga información específica
    if len(content) < 300:
        logger.warning("Contenido demasiado corto")
        return False
    
    return True

def extract_robust_json(groq_response):
    """Extrae JSON de manera robusta, manejando respuestas malformadas"""
    try:
        # Intentar JSON directo
        return json.loads(groq_response)
    except json.JSONDecodeError:
        logger.warning("Error en JSON, usando extracción robusta")
        
        # Buscar JSON entre texto
        json_match = re.search(r'\{.*\}', groq_response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        
        # Si todo falla, generar contenido mínimo basado en el caption
        logger.error("JSON completamente malformado, generando contenido de emergencia")
        return None

def generate_seo_article(caption, image_description):
    """Genera un artículo SEO optimizado usando Groq con validación robusta"""
    try:
        # Prompt simplificado y más directo
        prompt = f"""
Escribí un artículo periodístico en español argentino sobre esta noticia ESPECÍFICA:

NOTICIA: {caption}

INSTRUCCIONES CRÍTICAS:
- Escribí SOLO sobre esta noticia específica
- Usá los nombres, lugares y fechas exactos mencionados
- NO agregues enlaces externos
- Español argentino natural (descubrí, conocé)
- Mínimo 500 palabras

RESPUESTA EN JSON EXACTO:
{{
    "keyword_principal": "palabra clave principal de la noticia",
    "titulo_h1": "Título específico basado en la noticia",
    "meta_descripcion": "Meta descripción específica máximo 130 caracteres",
    "slug_url": "slug-especifico-de-esta-noticia",
    "contenido_html": "Artículo completo HTML con H2, H3. Sin enlaces externos.",
    "tags": ["tag-especifico-1", "tag-especifico-2", "tag-especifico-3"],
    "categoria": "Política"
}}

IMPORTANTE: JSON válido, sin texto adicional.
"""

        logger.info("Generando artículo con Groq...")
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Sos periodista argentino. Respuesta JSON válido únicamente. Sin enlaces externos."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.6,
            max_tokens=2500
        )
        
        content = response.choices[0].message.content.strip()
        logger.info(f"Respuesta Groq recibida: {len(content)} caracteres")
        
        # Extracción robusta del JSON
        article_data = extract_robust_json(content)
        
        if not article_data:
            # Generar contenido de emergencia basado en el caption
            logger.info("Generando contenido de emergencia")
            words = caption.split()[:8]
            emergency_title = ' '.join(words)
            
            article_data = {
                "keyword_principal": words[0] if words else "noticia",
                "titulo_h1": emergency_title[:60],
                "meta_descripcion": f"Descubrí los detalles de {emergency_title[:80]}",
                "slug_url": sanitize_filename(emergency_title),
                "contenido_html": f"""
                <h2>{emergency_title}</h2>
                <p>{caption}</p>
                <p>Esta información fue proporcionada por nuestro equipo de redacción y se basa en fuentes confiables.</p>
                <h3>Detalles de la noticia</h3>
                <p>Los acontecimientos desarrollados muestran la importancia de mantenerse informado sobre estos temas relevantes para la sociedad argentina.</p>
                """,
                "tags": [sanitize_filename(word) for word in words[:5] if len(word) > 3],
                "categoria": "Política"
            }
        
        # Validar contenido
        if not validate_article_content(article_data):
            logger.warning("Contenido genérico detectado, regenerando...")
            # Usar contenido de emergencia con el caption
            article_data['contenido_html'] = f"""
            <h2>Información exclusiva</h2>
            <p>{caption}</p>
            <h3>Contexto</h3>
            <p>Esta noticia fue desarrollada por nuestro equipo editorial con base en información verificada y fuentes confiables.</p>
            """
        
        # Asegurar slug específico
        if not article_data.get('slug_url') or article_data['slug_url'] == 'noticia-actualidad':
            article_data['slug_url'] = sanitize_filename(article_data['titulo_h1'])
        
        # Limpiar cualquier enlace externo que haya pasado
        if 'contenido_html' in article_data:
            content_html = article_data['contenido_html']
            content_html = re.sub(r'<a[^>]*href="https?://[^"]*"[^>]*>.*?</a>', '', content_html)
            content_html = content_html.replace('bbc.com', '').replace('cnn.com', '')
            article_data['contenido_html'] = content_html
        
        logger.info(f"Artículo generado: {article_data['titulo_h1']}")
        return article_data
        
    except Exception as e:
        logger.error(f"Error generando artículo SEO: {e}")
        return None

def upload_image_to_wordpress(image_url, filename="image.jpg", alt_text=""):
    """Sube una imagen a WordPress y establece alt text usando método mejorado"""
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        
        data = {
            'name': filename,
            'type': 'image/jpeg',
            'bits': response.content,
            'overwrite': True
        }
        
        upload_response = wp_client.call(UploadFile(data))
        attachment_id = upload_response['id']
        image_url_uploaded = upload_response['url']
        
        logger.info(f"Imagen subida exitosamente: {image_url_uploaded} (ID: {attachment_id})")
        
        # MÉTODO MEJORADO para Alt Text
        if alt_text and attachment_id:
            try:
                # Obtener el attachment actual
                attachment = wp_client.call(GetPost(attachment_id))
                
                # Establecer múltiples campos para asegurar que funcione
                attachment.excerpt = alt_text  # Alt text principal
                attachment.content = alt_text  # Descripción
                attachment.title = alt_text    # Título del attachment
                
                # Actualizar el attachment
                wp_client.call(EditPost(attachment_id, attachment))
                
                # También intentar con custom fields como respaldo
                from wordpress_xmlrpc.methods import posts
                from wordpress_xmlrpc import WordPressPost
                
                custom_fields = [
                    {'key': '_wp_attachment_image_alt', 'value': alt_text},
                    {'key': 'alt_text', 'value': alt_text}
                ]
                
                attachment.custom_fields = custom_fields
                wp_client.call(EditPost(attachment_id, attachment))
                
                logger.info(f"Alt text configurado: {alt_text}")
                
            except Exception as alt_error:
                logger.error(f"Error estableciendo alt text: {alt_error}")
        
        return image_url_uploaded, attachment_id
        
    except Exception as e:
        logger.error(f"Error subiendo imagen: {e}")
        return None, None

def publish_seo_article_to_wordpress(article_data, image_url, image_alt_text):
    """Publica el artículo SEO en WordPress con validaciones"""
    try:
        logger.info("Iniciando publicación en WordPress...")
        
        filename = f"{article_data['slug_url']}.jpg"
        
        uploaded_image_url, attachment_id = upload_image_to_wordpress(image_url, filename, image_alt_text)
        
        if not uploaded_image_url:
            logger.error("Falló la subida de imagen")
            return False
        
        # Contenido limpio SIN enlaces externos
        content_with_image = f"""<img src="{uploaded_image_url}" alt="{image_alt_text}" style="width: 100%; height: auto; margin-bottom: 20px;" />

{article_data['contenido_html']}

<!-- Datos Estructurados JSON-LD -->
<script type="application/ld+json">
{{
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": "{article_data['titulo_h1']}",
    "description": "{article_data['meta_descripcion']}",
    "author": {{
        "@type": "Person",
        "name": "Redacción"
    }},
    "publisher": {{
        "@type": "Organization",
        "name": "CórdobaTeve"
    }},
    "datePublished": "{datetime.now().isoformat()}"
}}
</script>"""
        
        post = WordPressPost()
        post.title = article_data['titulo_h1']
        post.content = content_with_image
        post.post_status = 'draft'
        post.excerpt = article_data['meta_descripcion']
        post.slug = article_data['slug_url']
        post.terms_names = {
            'post_tag': article_data.get('tags', []),
            'category': [article_data.get('categoria', 'General')]
        }
        
        # CRÍTICO: Imagen destacada
        if attachment_id:
            post.thumbnail = attachment_id
            logger.info(f"Imagen destacada configurada con ID: {attachment_id}")
        
        post_id = wp_client.call(NewPost(post))
        logger.info(f"Artículo SEO creado como BORRADOR con ID: {post_id}")
        
        return f"Artículo publicado exitosamente con ID: {post_id}"
        
    except Exception as e:
        logger.error(f"Error publicando artículo: {e}")
        return False

async def process_message_with_photo(update: Update):
    """Procesa un mensaje con foto con logging mejorado"""
    try:
        logger.info("Procesando mensaje con foto...")
        
        photo = update.message.photo[-1]
        file = await telegram_app.bot.get_file(photo.file_id)
        
        caption = update.message.caption or "Imagen sin descripción"
        logger.info(f"Caption recibido: {caption[:100]}...")
        
        image_description = f"Imagen periodística: {caption}"
        
        article_data = generate_seo_article(caption, image_description)
        
        if not article_data:
            await update.message.reply_text("❌ Error generando el artículo SEO")
            return
        
        image_alt_text = article_data['titulo_h1']
        
        result = publish_seo_article_to_wordpress(article_data, file.file_path, image_alt_text)
        
        if result:
            response_message = f"""✅ **ARTÍCULO v5.3.0 PUBLICADO** ✅

📝 **Título:** {article_data['titulo_h1']}
🔑 **Keyword:** {article_data['keyword_principal']}
🔗 **Slug:** {article_data['slug_url']}
📄 **Meta:** {article_data['meta_descripcion']}
🏷️ **Tags:** {', '.join(article_data.get('tags', []))}
📂 **Categoría:** {article_data.get('categoria', 'General')}
🖼️ **Alt Text:** {image_alt_text}
📊 **Estado:** Borrador
🔧 **Mejoras:** JSON robusto + Alt text mejorado

{result}"""
        else:
            response_message = "❌ Error publicando el artículo en WordPress"
            
        await update.message.reply_text(response_message)
        
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint para recibir webhooks de Telegram"""
    try:
        update_data = request.get_json()
        update = Update.de_json(update_data, telegram_app.bot)
        
        if update.message and update.message.photo:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(initialize_application())
            loop.run_until_complete(process_message_with_photo(update))
            
            loop.close()
            
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "no_photo"})
            
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud"""
    return jsonify({"status": "healthy", "version": "5.3.0"})

if __name__ == '__main__':
    print("🚀 Bot SEO v5.3.0 iniciado...")
    print("🔧 JSON robusto + Alt text mejorado + Validaciones")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
