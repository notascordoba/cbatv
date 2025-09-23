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
    if len(title) > 50:
        title = title[:50].rstrip('-')
    
    return title

def generate_seo_article(caption, image_description):
    """Genera un artículo SEO optimizado usando Groq"""
    try:
        prompt = f"""
Eres un periodista experto en SEO y marketing de contenidos. Tu tarea es crear un artículo periodístico completo y profesional basado en esta información original y exclusiva:

INFORMACIÓN PROPORCIONADA (FUENTE ORIGINAL):
- Descripción del periodista: {caption}
- Descripción de la imagen: {image_description}

INSTRUCCIONES CRÍTICAS:
1. Esta es información EXCLUSIVA proporcionada por un periodista - NO agregues enlaces externos a otras fuentes
2. Crea contenido ORIGINAL de mínimo 500 palabras
3. Analiza y extrae la palabra clave principal del contenido
4. Genera tags ESPECÍFICOS basados en nombres, lugares, temas concretos del artículo
5. El slug debe ser una frase descriptiva con la palabra clave
6. Estructura el contenido con H2, H3, y listas cuando sea apropiado
7. Incluye interlinking interno únicamente

ESTRUCTURA REQUERIDA:
- Introducción atractiva
- Desarrollo del tema principal con subtemas
- Análisis y contexto
- Conclusión
- Usar H2 para secciones principales, H3 para subsecciones
- Incluir listas numeradas o con viñetas cuando sea apropiado

RESPONDE ÚNICAMENTE CON UN JSON VÁLIDO CON ESTA ESTRUCTURA EXACTA:
{{
    "keyword_principal": "palabra clave específica extraída del contenido",
    "titulo_h1": "Título periodístico atractivo de 30-70 caracteres con keyword",
    "meta_descripcion": "Meta descripción periodística de máximo 130 caracteres con keyword",
    "slug_url": "frase-descriptiva-con-palabra-clave-principal",
    "contenido_html": "Artículo completo en HTML de MÍNIMO 500 palabras con estructura H2, H3, listas. Incluye introducción, desarrollo del tema, análisis, contexto y conclusión. Solo interlinking interno con enlaces como /categoria/politica o /tag/economia. NO enlaces externos.",
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

EJEMPLOS DE TAGS ESPECÍFICOS (NO usar genéricos como "actualidad" o "noticias"):
- Si habla de Milei: "javier-milei", "presidente-argentina", "la-libertad-avanza"
- Si habla de fútbol: "boca-juniors", "lionel-messi", "copa-argentina"
- Si habla de economía: "inflacion-argentina", "dolar-blue", "banco-central"

IMPORTANTE: Responde SOLO con el JSON, sin texto adicional antes o después.
"""

        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Eres un periodista experto en SEO. Respondes únicamente con JSON válido. Creas contenido original extenso sin enlaces externos."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=3000  # Aumentado para contenido más extenso
        )
        
        content = response.choices[0].message.content.strip()
        
        # Limpiar el contenido para asegurar que sea JSON válido
        if content.startswith('```json'):
            content = content[7:]
        if content.endswith('```'):
            content = content[:-3]
        
        return json.loads(content)
        
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
            'bits': response.content
        }
        
        # Subir a WordPress
        response = wp_client.call(UploadFile(data))
        attachment_id = response['id']
        image_url_uploaded = response['url']
        
        # Establecer el texto alternativo como metadata del attachment en WordPress
        if alt_text and attachment_id:
            try:
                # Obtener el post del attachment
                attachment_post = wp_client.call(GetPost(attachment_id))
                
                # Establecer el alt text (en WordPress se guarda como excerpt para attachments)
                attachment_post.excerpt = alt_text
                
                # Actualizar el attachment con el alt text
                wp_client.call(EditPost(attachment_id, attachment_post))
                
                print(f"✅ Alt text establecido: {alt_text}")
                
            except Exception as alt_error:
                print(f"⚠️ Error estableciendo alt text: {alt_error}")
                # No fallar por esto, la imagen ya se subió correctamente
        
        return image_url_uploaded, attachment_id
        
    except Exception as e:
        print(f"Error subiendo imagen: {e}")
        return None, None

def publish_seo_article_to_wordpress(article_data, image_url, image_alt_text):
    """Publica el artículo SEO en WordPress con imagen destacada"""
    try:
        # Generar nombre de archivo SEO-friendly
        filename = f"{sanitize_filename(article_data['titulo_h1'])}.jpg"
        
        # Subir imagen, establecer alt text y obtener attachment_id
        uploaded_image_url, attachment_id = upload_image_to_wordpress(image_url, filename, image_alt_text)
        
        if not uploaded_image_url:
            return False
        
        # Crear el contenido del post con la imagen y alt text
        content_with_image = f"""
<img src="{uploaded_image_url}" alt="{image_alt_text}" style="width: 100%; height: auto; margin-bottom: 20px;" />

{article_data['contenido_html']}

<!-- Datos Estructurados JSON-LD -->
<script type="application/ld+json">
{json.dumps(article_data['datos_estructurados'], ensure_ascii=False, indent=2)}
</script>
"""
        
        # Crear el post
        post = WordPressPost()
        post.title = article_data['titulo_h1']
        post.content = content_with_image
        post.post_status = 'draft'  # Cambiar a borrador
        post.excerpt = article_data['meta_descripcion']
        post.slug = article_data['slug_url']  # Establecer slug personalizado
        post.terms_names = {
            'post_tag': article_data['tags'],
            'category': [article_data['categoria']]
        }
        
        # CRÍTICO: Asignar imagen destacada usando attachment_id (NO TOCAR)
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
        
        # Generar descripción de la imagen (simulada)
        image_description = f"Imagen enviada por Telegram con caption: {caption}"
        
        # Primero generar el artículo para obtener el título
        article_data = generate_seo_article(caption, image_description)
        
        if not article_data:
            await update.message.reply_text("❌ Error generando el artículo SEO")
            return
        
        # Usar el título del artículo como alt text
        image_alt_text = article_data['titulo_h1']
        
        # Publicar en WordPress
        result = publish_seo_article_to_wordpress(article_data, file.file_path, image_alt_text)
        
        if result:
            response_message = f"""
✅ **ARTÍCULO SEO v5.2.0 PUBLICADO** ✅

📝 **Título:** {article_data['titulo_h1']}
🔑 **Keyword:** {article_data['keyword_principal']}
🔗 **Slug:** {article_data['slug_url']}
📄 **Meta Descripción:** {article_data['meta_descripcion']}
🏷️ **Tags Específicos:** {', '.join(article_data['tags'])}
📂 **Categoría:** {article_data['categoria']}
🖼️ **Imagen:** {image_alt_text}
📊 **Estado:** Borrador (pendiente de revisión)
📝 **Extensión:** Artículo extenso (+500 palabras)

{result}
"""
        else:
            response_message = "❌ Error publicando el artículo en WordPress"
            
        await update.message.reply_text(response_message)
        
    except Exception as e:
        print(f"Error procesando mensaje: {e}")
        await update.message.reply_text(f"❌ Error procesando la imagen: {str(e)}")

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint para recibir webhooks de Telegram"""
    try:
        update_data = request.get_json()
        update = Update.de_json(update_data, telegram_app.bot)
        
        # Verificar si el mensaje tiene foto
        if update.message and update.message.photo:
            # Crear un nuevo event loop para manejar la función async
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Inicializar la aplicación antes de procesar
            loop.run_until_complete(initialize_application())
            
            # Procesar el mensaje
            loop.run_until_complete(process_message_with_photo(update))
            
            # Cerrar el loop
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
    return jsonify({"status": "healthy", "version": "5.2.0"})

if __name__ == '__main__':
    print("🚀 Bot SEO v5.2.0 iniciado...")
    print("📸 Funcionalidades: SEO profesional + Contenido extenso + Tags específicos + Interlinking")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
