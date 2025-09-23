import os
import json
import asyncio
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
    # Eliminar caracteres especiales y convertir a minúsculas
    title = title.lower()
    # Reemplazar espacios por guiones
    title = re.sub(r'\s+', '-', title)
    # Remover acentos y caracteres especiales
    title = unicodedata.normalize('NFD', title)
    title = ''.join(char for char in title if unicodedata.category(char) != 'Mn')
    # Mantener solo letras, números y guiones
    title = re.sub(r'[^a-z0-9\-]', '', title)
    # Eliminar guiones múltiples
    title = re.sub(r'-+', '-', title)
    # Eliminar guiones al inicio y final
    title = title.strip('-')
    # Limitar longitud
    if len(title) > 60:
        title = title[:60].rstrip('-')
    
    return title

def generate_seo_article(caption, image_description):
    """Genera un artículo SEO optimizado usando Groq"""
    try:
        prompt = f"""
Sos un redactor SEO experto especializado en periodismo argentino. Tu tarea es crear un artículo periodístico completo y profesional en español rioplatense basado en esta información EXCLUSIVA:

INFORMACIÓN PROPORCIONADA (FUENTE ORIGINAL):
- Descripción del periodista: {caption}
- Descripción de la imagen: {image_description}

INSTRUCCIONES CRÍTICAS:
1. Esta es información EXCLUSIVA de un periodista argentino - NO agregues enlaces externos
2. Redactá en español argentino, tono periodístico profesional
3. Contenido ORIGINAL de mínimo 500 palabras
4. Identificá la palabra clave principal del tema específico
5. Generá tags ESPECÍFICOS del contenido (nombres propios, lugares, temas exactos)
6. El slug debe ser el título sanitizado para URL
7. Estructura con H2, H3, listas cuando corresponda
8. SIN enlaces externos - solo contenido propio

ESTRUCTURA PERIODÍSTICA:
- Lead atractivo con los datos más importantes
- Desarrollo del tema con subtemas específicos
- Contexto y análisis argentino
- Cierre contundente
- H2 para secciones principales, H3 para detalles
- Listas cuando sea apropiado para organizar información

RESPONDE ÚNICAMENTE CON UN JSON VÁLIDO:
{{
    "keyword_principal": "palabra clave específica del tema principal",
    "titulo_h1": "Título periodístico argentino de 30-70 caracteres con keyword",
    "meta_descripcion": "Meta descripción periodística de máximo 130 caracteres con keyword",
    "slug_url": "titulo-sanitizado-para-url",
    "contenido_html": "Artículo completo en HTML de MÍNIMO 500 palabras con estructura H2, H3, listas. Estilo periodístico argentino. SOLO contenido propio, SIN enlaces externos de ningún tipo.",
    "tags": ["tag-especifico-1", "tag-especifico-2", "tag-especifico-3", "tag-especifico-4", "tag-especifico-5"],
    "categoria": "Categoría específica del artículo",
    "datos_estructurados": {{
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "título del artículo",
        "description": "descripción del artículo",
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
}}

EJEMPLOS DE TAGS ESPECÍFICOS (extraídos del contenido real):
- Si es sobre Milei: "javier-milei", "casa-rosada", "la-libertad-avanza"
- Si es deportes: "talleres-cordoba", "mario-kempes", "liga-profesional"
- Si es economía: "inflacion-argentina", "banco-central", "luis-caputo"

IMPORTANTE: 
- Responde SOLO con el JSON válido
- SIN enlaces externos en el contenido HTML
- Tags específicos del tema, NO genéricos
- Slug = título sanitizado
"""

        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Sos un redactor SEO argentino experto en periodismo. Respondes únicamente con JSON válido. Creás contenido original sin enlaces externos."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=3000
        )
        
        content = response.choices[0].message.content.strip()
        
        # Limpiar el contenido para asegurar que sea JSON válido
        if content.startswith('```json'):
            content = content[7:]
        if content.endswith('```'):
            content = content[:-3]
        
        article_data = json.loads(content)
        
        # FORZAR slug como título sanitizado
        article_data['slug_url'] = sanitize_filename(article_data['titulo_h1'])
        
        return article_data
        
    except Exception as e:
        print(f"Error generando artículo SEO: {e}")
        return None

def upload_image_to_wordpress(image_url, filename="image.jpg", alt_text=""):
    """Sube una imagen a WordPress, establece alt text y retorna la URL y el attachment_id"""
    try:
        # Descargar la imagen
        response = requests.get(image_url)
        response.raise_for_status()
        
        # Preparar el archivo para WordPress
        data = {
            'name': filename,
            'type': 'image/jpeg',
            'bits': response.content,
            'overwrite': True
        }
        
        # Subir a WordPress
        upload_response = wp_client.call(UploadFile(data))
        attachment_id = upload_response['id']
        image_url_uploaded = upload_response['url']
        
        # MEJORADO: Establecer el texto alternativo correctamente
        if alt_text and attachment_id:
            try:
                from wordpress_xmlrpc.methods import media
                from wordpress_xmlrpc import WordPressPost
                
                # Crear un post para el attachment con alt text
                attachment_post = WordPressPost()
                attachment_post.id = attachment_id
                attachment_post.post_excerpt = alt_text  # Alt text en WordPress
                attachment_post.post_content = alt_text  # Descripción
                
                # Actualizar usando EditPost
                wp_client.call(EditPost(attachment_id, attachment_post))
                
                print(f"✅ Alt text establecido correctamente: {alt_text}")
                
            except Exception as alt_error:
                print(f"⚠️ Error estableciendo alt text: {alt_error}")
        
        return image_url_uploaded, attachment_id
        
    except Exception as e:
        print(f"Error subiendo imagen: {e}")
        return None, None

def publish_seo_article_to_wordpress(article_data, image_url, image_alt_text):
    """Publica el artículo SEO en WordPress con imagen destacada"""
    try:
        # Generar nombre de archivo SEO-friendly
        filename = f"{article_data['slug_url']}.jpg"
        
        # Subir imagen, establecer alt text y obtener attachment_id
        uploaded_image_url, attachment_id = upload_image_to_wordpress(image_url, filename, image_alt_text)
        
        if not uploaded_image_url:
            return False
        
        # Crear el contenido del post con la imagen y alt text
        content_with_image = f"""<img src="{uploaded_image_url}" alt="{image_alt_text}" style="width: 100%; height: auto; margin-bottom: 20px;" />

{article_data['contenido_html']}

<!-- Datos Estructurados JSON-LD -->
<script type="application/ld+json">
{json.dumps(article_data['datos_estructurados'], ensure_ascii=False, indent=2)}
</script>"""
        
        # Crear el post
        post = WordPressPost()
        post.title = article_data['titulo_h1']
        post.content = content_with_image
        post.post_status = 'draft'
        post.excerpt = article_data['meta_descripcion']
        post.slug = article_data['slug_url']
        post.terms_names = {
            'post_tag': article_data['tags'],
            'category': [article_data['categoria']]
        }
        
        # CRÍTICO: Asignar imagen destacada (NO TOCAR)
        if attachment_id:
            post.thumbnail = attachment_id
        
        # Publicar el post
        post_id = wp_client.call(NewPost(post))
        
        return f"Artículo publicado exitosamente con ID: {post_id}"
        
    except Exception as e:
        print(f"Error publicando artículo: {e}")
        return False

async def process_message_with_photo(update: Update):
    """Procesa un mensaje con foto"""
    try:
        # Obtener la imagen de mayor resolución
        photo = update.message.photo[-1]
        file = await telegram_app.bot.get_file(photo.file_id)
        
        # Obtener el caption si existe
        caption = update.message.caption or "Imagen sin descripción"
        
        # Generar descripción de la imagen
        image_description = f"Imagen periodística con descripción: {caption}"
        
        # Generar el artículo
        article_data = generate_seo_article(caption, image_description)
        
        if not article_data:
            await update.message.reply_text("❌ Error generando el artículo SEO")
            return
        
        # Usar el título del artículo como alt text
        image_alt_text = article_data['titulo_h1']
        
        # Publicar en WordPress
        result = publish_seo_article_to_wordpress(article_data, file.file_path, image_alt_text)
        
        if result:
            response_message = f"""✅ **ARTÍCULO SEO v5.2.1 PUBLICADO** ✅

📝 **Título:** {article_data['titulo_h1']}
🔑 **Keyword:** {article_data['keyword_principal']}
🔗 **Slug:** {article_data['slug_url']}
📄 **Meta:** {article_data['meta_descripcion']}
🏷️ **Tags:** {', '.join(article_data['tags'])}
📂 **Categoría:** {article_data['categoria']}
🖼️ **Alt Text:** {image_alt_text}
📊 **Estado:** Borrador
📝 **Estilo:** Periodismo argentino

{result}"""
        else:
            response_message = "❌ Error publicando el artículo en WordPress"
            
        await update.message.reply_text(response_message)
        
    except Exception as e:
        print(f"Error procesando mensaje: {e}")
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
        print(f"Error en webhook: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud"""
    return jsonify({"status": "healthy", "version": "5.2.1"})

if __name__ == '__main__':
    print("🚀 Bot SEO v5.2.1 iniciado...")
    print("📰 Redacción SEO profesional argentina")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
