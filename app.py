import os
import json
import re
import requests
from flask import Flask, request, jsonify
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost, GetPost, EditPost
from wordpress_xmlrpc.methods.media import UploadFile
from wordpress_xmlrpc.compat import xmlrpc_client
from wordpress_xmlrpc.methods import media
import logging
from datetime import datetime
import time
import urllib.parse
from html import escape

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.critical("=== v5.3.4: PROMPT PERIODÍSTICO REAL ===")

# Configuración
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WP_URL = os.environ.get('WP_URL')
WP_USERNAME = os.environ.get('WP_USERNAME')
WP_PASSWORD = os.environ.get('WP_PASSWORD')

# Verificación de variables de entorno
required_env_vars = ['GROQ_API_KEY', 'TELEGRAM_BOT_TOKEN', 'WP_URL', 'WP_USERNAME', 'WP_PASSWORD']
for var in required_env_vars:
    if not os.environ.get(var):
        logger.error(f"Variable de entorno faltante: {var}")
        raise ValueError(f"Variable de entorno faltante: {var}")

# Inicialización de clientes
groq_client = Groq(api_key=GROQ_API_KEY)
wp_client = Client(f'{WP_URL}/xmlrpc.php', WP_USERNAME, WP_PASSWORD)

app = Flask(__name__)

def sanitize_filename(text):
    """Sanitiza texto para crear nombres de archivo válidos y URLs amigables."""
    # Convertir a minúsculas y reemplazar caracteres especiales
    sanitized = text.lower()
    # Reemplazar caracteres acentuados
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ñ': 'n', 'ü': 'u', 'ç': 'c'
    }
    for old, new in replacements.items():
        sanitized = sanitized.replace(old, new)
    
    # Remover caracteres especiales y espacios
    sanitized = re.sub(r'[^a-z0-9\s-]', '', sanitized)
    # Reemplazar espacios y múltiples guiones con guiones simples
    sanitized = re.sub(r'[\s-]+', '-', sanitized)
    # Limpiar guiones al inicio y final
    sanitized = sanitized.strip('-')
    
    return sanitized[:50]  # Limitar longitud

def extract_json_robust(content):
    """Extrae JSON de manera robusta, manejando malformaciones."""
    try:
        # Intento 1: JSON directo
        return json.loads(content)
    except:
        logger.warning("Error en JSON, usando extracción robusta")
        
        try:
            # Intento 2: Buscar entre llaves
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        # Intento 3: Extraer campos manualmente
        try:
            titulo = re.search(r'"titulo_h1"\s*:\s*"([^"]*)"', content)
            contenido = re.search(r'"contenido_html"\s*:\s*"((?:[^"\\]|\\.)*)"', content)
            meta = re.search(r'"meta_descripcion"\s*:\s*"([^"]*)"', content)
            tags = re.search(r'"tags"\s*:\s*\[(.*?)\]', content)
            slug = re.search(r'"slug_url"\s*:\s*"([^"]*)"', content)
            
            if titulo and contenido:
                result = {
                    "titulo_h1": titulo.group(1),
                    "contenido_html": contenido.group(1).replace('\\"', '"'),
                    "meta_descripcion": meta.group(1) if meta else "",
                    "tags": [],
                    "slug_url": slug.group(1) if slug else ""
                }
                
                if tags:
                    tag_matches = re.findall(r'"([^"]*)"', tags.group(1))
                    result["tags"] = tag_matches
                
                return result
        except:
            pass
        
        return None

def generate_specific_tags(user_caption):
    """Genera tags específicos basados en el caption del usuario."""
    logger.critical("v5.3.4: Generando tags específicos desde caption")
    
    # Extraer palabras clave importantes (4+ caracteres, no comunes)
    words = re.findall(r'\b[A-ZÁ-ÿa-zá-ÿ]{4,}\b', user_caption.lower())
    
    # Palabras a excluir (muy comunes)
    stop_words = {
        'para', 'desde', 'hasta', 'sobre', 'entre', 'durante', 
        'después', 'antes', 'dentro', 'contra', 'hacia', 'según',
        'mientras', 'aunque', 'porque', 'cuando', 'donde', 'como',
        'este', 'esta', 'estos', 'estas', 'aquel', 'aquella',
        'será', 'serán', 'está', 'están', 'tiene', 'tienen',
        'hacer', 'hace', 'hizo', 'sido', 'estar', 'tener',
        'edición', 'número', 'ciudad', 'país', 'presidente'
    }
    
    # Filtrar palabras importantes
    keywords = []
    for word in words:
        if word not in stop_words and len(word) >= 4:
            keywords.append(word)
    
    # Tomar las 5 primeras palabras únicas
    unique_keywords = list(dict.fromkeys(keywords))[:5]
    
    # Si no hay suficientes, agregar algunas genéricas relevantes
    if len(unique_keywords) < 3:
        additional = ['política', 'actualidad', 'argentina']
        for add_word in additional:
            if add_word not in unique_keywords:
                unique_keywords.append(add_word)
                if len(unique_keywords) >= 3:
                    break
    
    logger.critical(f"v5.3.4: Tags generados: {unique_keywords}")
    return unique_keywords

def generate_slug_from_caption(user_caption):
    """Genera slug específico basado en la primera línea del caption."""
    logger.critical("v5.3.4: Generando slug específico desde caption")
    
    # Tomar la primera línea como base para el slug
    first_line = user_caption.split('\n')[0].strip()
    
    # Si es muy larga, tomar solo las primeras palabras importantes
    words = first_line.split()
    if len(words) > 8:
        first_line = ' '.join(words[:8])
    
    slug = sanitize_filename(first_line)
    logger.critical(f"v5.3.4: Slug generado: {slug}")
    return slug

def generate_seo_article(image_description, user_caption):
    """Genera artículo SEO con prompt periodístico real."""
    logger.info("v5.3.4: Generando artículo con prompt periodístico mejorado")
    
    prompt = f"""Sos un periodista político argentino experimentado. Escribí un artículo periodístico sobre estos hechos ESPECÍFICOS:

{user_caption}

ESCRIBÍ COMO PERIODISTA ARGENTINO:
- Lenguaje directo, concreto, periodístico
- Concentrate en los HECHOS reales mencionados
- Evitá frases genéricas sobre "cooperación internacional"
- Usá "descubrí", "conocé", "enterate" (argentino)
- SIN enlaces externos ni fuentes externas
- Mínimo 500 palabras sobre los hechos concretos

ESTRUCTURA PERIODÍSTICA:
H1: Título directo sobre el hecho principal
H2: Detalles del encuentro entre Milei y Trump
H3: Lo que se conversó en la reunión
H3: El discurso que dará mañana
H2: El contexto político actual
H3: Qué significa esto para Argentina

IMPORTANTE: Escribí SOLO sobre los hechos mencionados, sin agregar información no proporcionada.

JSON únicamente:
{
  "titulo_h1": "Título periodístico directo sobre el hecho",
  "contenido_html": "HTML con hechos específicos, lenguaje periodístico argentino",
  "meta_descripcion": "Descripción directa en argentino sobre el hecho",
  "tags": ["tag1", "tag2", "tag3"], 
  "slug_url": "slug-directo-sobre-el-hecho"
}"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,  # Menos temperatura para más consistencia
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        logger.info(f"v5.3.4: Respuesta AI generada, primeros 200 chars: {content[:200]}")
        
        # Extraer datos del JSON
        article_data = extract_json_robust(content)
        
        if article_data:
            # FORZAR tags y slug específicos (v5.3.4)
            article_data['tags'] = generate_specific_tags(user_caption)
            article_data['slug_url'] = generate_slug_from_caption(user_caption)
            
            # Limpiar cualquier enlace externo del contenido
            article_data['contenido_html'] = re.sub(
                r'<a[^>]*href=["\']https?://[^"\']*["\'][^>]*>([^<]*)</a>',
                r'\1',
                article_data['contenido_html']
            )
            
            # Eliminar referencias a fuentes externas
            article_data['contenido_html'] = re.sub(
                r'<p[^>]*>Fuente externa:.*?</p>',
                '',
                article_data['contenido_html']
            )
            
            # Eliminar referencias genéricas a BBC y similares
            article_data['contenido_html'] = re.sub(
                r'<p[^>]*>Más información:.*?</p>',
                '',
                article_data['contenido_html']
            )
            
            logger.critical(f"v5.3.4: Artículo generado exitosamente")
            logger.critical(f"v5.3.4: Título: {article_data['titulo_h1']}")
            return article_data
        else:
            raise Exception("No se pudo extraer datos válidos del AI")
            
    except Exception as e:
        logger.error(f"v5.3.4: Error generando artículo: {e}")
        raise

def upload_image_to_wordpress_alt_fixed(image_url, filename="image.jpg", alt_text=""):
    """Subida de imagen con ALT TEXT FORZADO (v5.3.4)."""
    logger.critical(f"v5.3.4: CONFIGURANDO ALT TEXT FORZADO: '{alt_text}'")
    
    try:
        # Descargar imagen
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Preparar datos para subida
        data = {
            'name': filename,
            'type': 'image/jpeg',
            'bits': xmlrpc_client.Binary(response.content)
        }
        
        # Subir imagen
        upload_result = wp_client.call(UploadFile(data))
        attachment_id = upload_result['id']
        image_url_wp = upload_result['url']
        
        logger.info(f"Imagen subida exitosamente: {image_url_wp} (ID: {attachment_id})")
        
        # CONFIGURACIÓN AGRESIVA DE ALT TEXT (v5.3.4)
        if alt_text:
            try:
                logger.critical(f"v5.3.4: INICIANDO CONFIGURACIÓN MÚLTIPLE DE ALT TEXT")
                
                # Obtener el post del attachment
                attachment_post = wp_client.call(GetPost(attachment_id))
                
                # Configurar TODOS los campos posibles
                attachment_post.excerpt = alt_text
                attachment_post.content = alt_text
                attachment_post.description = alt_text
                
                # Configurar custom fields para alt text
                custom_fields = [
                    {'key': '_wp_attachment_image_alt', 'value': alt_text},
                    {'key': 'alt_text', 'value': alt_text},
                    {'key': '_alt_text', 'value': alt_text}
                ]
                attachment_post.custom_fields = custom_fields
                
                # Actualizar el post
                wp_client.call(EditPost(attachment_id, attachment_post))
                
                logger.critical(f"v5.3.4: ALT TEXT CONFIGURADO EN MÚLTIPLES CAMPOS")
                logger.critical(f"Alt text configurado: {alt_text}")
                
            except Exception as e:
                logger.error(f"v5.3.4: Error configurando alt text: {e}")
        
        return attachment_id, image_url_wp
        
    except Exception as e:
        logger.error(f"Error subiendo imagen: {e}")
        raise

def publish_seo_article_to_wordpress(article_data, featured_image_id, image_url, alt_text):
    """Publica artículo con configuración forzada (v5.3.4)."""
    logger.critical(f"v5.3.4: PUBLICANDO CON DATOS FORZADOS")
    logger.critical(f"v5.3.4: Tags: {article_data['tags']}")
    logger.critical(f"v5.3.4: Slug: {article_data['slug_url']}")
    
    try:
        # Crear nuevo post
        post = WordPressPost()
        post.title = article_data['titulo_h1']
        
        # Crear contenido con imagen destacada
        content_html = f'<p><img src="{image_url}" alt="{alt_text}" class="wp-image-featured"></p>\n'
        content_html += article_data['contenido_html']
        
        post.content = content_html
        post.excerpt = article_data['meta_descripcion']
        post.post_status = 'draft'
        
        # Configurar imagen destacada
        post.thumbnail = featured_image_id
        logger.critical(f"Imagen destacada configurada con ID: {featured_image_id}")
        
        # FORZAR configuración de tags (v5.3.4)
        post.terms_names = {
            'post_tag': article_data['tags']
        }
        logger.critical(f"v5.3.4: TAGS FORZADOS: {article_data['tags']}")
        
        # FORZAR configuración de slug (v5.3.4)  
        if article_data.get('slug_url'):
            post.slug = article_data['slug_url']
            logger.critical(f"v5.3.4: SLUG FORZADO: {article_data['slug_url']}")
        
        # Publicar post
        post_id = wp_client.call(NewPost(post))
        
        logger.critical(f"Artículo SEO creado como BORRADOR con ID: {post_id}")
        return post_id
        
    except Exception as e:
        logger.error(f"Error publicando artículo: {e}")
        raise

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Maneja webhooks de Telegram con prompt periodístico mejorado v5.3.4."""
    try:
        update = request.get_json()
        logger.info(f"Webhook recibido")
        
        if 'message' not in update:
            return jsonify({"status": "ok"})
        
        message = update['message']
        
        if 'photo' in message and 'caption' in message:
            photo = message['photo'][-1]
            file_id = photo['file_id']
            caption = message['caption']
            
            logger.critical(f"v5.3.4: PROCESANDO CAPTION CON PROMPT PERIODÍSTICO")
            logger.critical(f"v5.3.4: Caption: {caption[:100]}...")
            
            # Obtener URL del archivo
            file_info_response = requests.get(f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}')
            file_info = file_info_response.json()
            
            if file_info['ok']:
                file_path = file_info['result']['file_path']
                file_url = f'https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}'
                
                # Generar nombre de archivo único
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_caption = sanitize_filename(caption[:50])
                filename = f"{safe_caption}_{timestamp}.jpg"
                
                # Generar alt text específico
                alt_text = caption.split('\n')[0][:100]  # Primera línea, máximo 100 chars
                if len(alt_text) > 97:
                    alt_text = alt_text[:97] + "..."
                
                logger.critical(f"v5.3.4: ALT TEXT PREPARADO: '{alt_text}'")
                
                try:
                    # Subir imagen con alt text forzado
                    attachment_id, wp_image_url = upload_image_to_wordpress_alt_fixed(
                        file_url, 
                        filename, 
                        alt_text
                    )
                    
                    # Generar artículo SEO con prompt periodístico
                    image_description = f"Imagen relacionada con: {caption}"
                    article_data = generate_seo_article(image_description, caption)
                    
                    # Publicar artículo
                    post_id = publish_seo_article_to_wordpress(
                        article_data, 
                        attachment_id, 
                        wp_image_url, 
                        alt_text
                    )
                    
                    return jsonify({
                        "status": "success",
                        "post_id": post_id,
                        "attachment_id": attachment_id,
                        "message": "v5.3.4: Artículo creado con prompt periodístico mejorado",
                        "version": "5.3.4"
                    })
                    
                except Exception as e:
                    logger.error(f"Error procesando: {e}")
                    return jsonify({"status": "error", "message": str(e)}), 500
            else:
                return jsonify({"status": "error", "message": "No se pudo obtener la imagen"}), 400
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de verificación de salud."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
