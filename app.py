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

def extract_json_content_robust(text):
    """
    Extrae contenido JSON usando múltiples estrategias de parsing.
    """
    logger.info("Iniciando extracción robusta de JSON")
    
    # Estrategia 1: JSON directo
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Estrategia 1 falló: JSON directo")
    
    # Estrategia 2: Buscar JSON entre llaves {}
    json_pattern = r'\{.*\}'
    matches = re.findall(json_pattern, text, re.DOTALL)
    
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    logger.warning("Estrategia 2 falló: Buscar entre llaves")
    
    # Estrategia 3: Buscar por patrones de campos específicos
    try:
        # Buscar campos individuales con regex
        titulo_match = re.search(r'"titulo_h1"\s*:\s*"([^"]*)"', text)
        contenido_match = re.search(r'"contenido_html"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        metadesc_match = re.search(r'"meta_descripcion"\s*:\s*"([^"]*)"', text)
        tags_match = re.search(r'"tags"\s*:\s*\[(.*?)\]', text)
        slug_match = re.search(r'"slug_url"\s*:\s*"([^"]*)"', text)
        
        if titulo_match and contenido_match:
            # Construir JSON manualmente
            extracted_data = {
                "titulo_h1": titulo_match.group(1),
                "contenido_html": contenido_match.group(1).replace('\\"', '"').replace('\\n', '\n'),
                "meta_descripcion": metadesc_match.group(1) if metadesc_match else "",
                "tags": [],
                "slug_url": slug_match.group(1) if slug_match else ""
            }
            
            # Procesar tags
            if tags_match:
                tags_str = tags_match.group(1)
                tags = re.findall(r'"([^"]*)"', tags_str)
                extracted_data["tags"] = tags
            
            logger.info("Estrategia 3 exitosa: Extracción por campos individuales")
            return extracted_data
    except Exception as e:
        logger.error(f"Error en estrategia 3: {e}")
    
    logger.error("Todas las estrategias de extracción fallaron")
    return None

def validate_content_quality(article_data, user_caption):
    """
    Valida que el contenido no sea genérico y esté relacionado con el caption del usuario.
    """
    logger.info("Validando calidad del contenido")
    
    # Lista de contenidos genéricos que debemos rechazar
    generic_patterns = [
        "contenido de actualidad",
        "información relevante sobre el tema tratado",
        "noticia de actualidad",
        "más detalles",
        "artículos relacionados"
    ]
    
    titulo = article_data.get('titulo_h1', '').lower()
    contenido = article_data.get('contenido_html', '').lower()
    slug = article_data.get('slug_url', '').lower()
    
    # Verificar patrones genéricos en el contenido
    for pattern in generic_patterns:
        if pattern in contenido or pattern in titulo:
            logger.warning(f"Contenido genérico detectado: {pattern}")
            return False
    
    # Verificar que el slug no sea genérico
    generic_slugs = ['noticia-actualidad', 'contenido-actualidad', 'articulo-generico']
    if slug in generic_slugs:
        logger.warning(f"Slug genérico detectado: {slug}")
        return False
    
    # Verificar longitud mínima del contenido
    contenido_texto = re.sub(r'<[^>]+>', '', contenido)  # Remover HTML
    if len(contenido_texto.split()) < 100:  # Menos de 100 palabras
        logger.warning("Contenido demasiado corto")
        return False
    
    # Verificar que contenga palabras del caption del usuario
    caption_words = set(user_caption.lower().split())
    titulo_words = set(titulo.split())
    
    # Al menos 2 palabras del caption deben estar en el título
    common_words = caption_words.intersection(titulo_words)
    if len(common_words) < 2:
        logger.warning("Título no relacionado con el caption del usuario")
        return False
    
    logger.info("Validación de contenido exitosa")
    return True

def generate_fallback_content(user_caption, image_description):
    """
    Genera contenido de fallback usando directamente el caption del usuario.
    """
    logger.info("Generando contenido de fallback")
    
    # Extraer título principal (primera línea o hasta 100 caracteres)
    lines = user_caption.split('\n')
    titulo_principal = lines[0][:100] if lines[0] else "Noticia Importante"
    
    # Crear contenido básico usando el caption completo
    contenido_html = f"""<h1>{escape(titulo_principal)}</h1>
<p>{escape(user_caption.replace(chr(10), '</p><p>'))}</p>
<h2>Detalles de la Noticia</h2>
<p>Esta información corresponde a los últimos desarrollos reportados por nuestro equipo de redacción.</p>"""
    
    # Generar tags basados en palabras clave del caption
    words = re.findall(r'\b[A-Za-zÁ-ÿ]{4,}\b', user_caption)
    important_words = [w.lower() for w in words[:5]]  # Primeras 5 palabras importantes
    
    # Crear slug basado en el título
    slug = sanitize_filename(titulo_principal)
    
    fallback_data = {
        "titulo_h1": titulo_principal,
        "contenido_html": contenido_html,
        "meta_descripcion": f"Descubrí los detalles sobre {titulo_principal[:80]}..." if len(titulo_principal) > 80 else f"Descubrí los detalles sobre {titulo_principal}.",
        "tags": important_words,
        "slug_url": slug
    }
    
    logger.info("Contenido de fallback generado exitosamente")
    return fallback_data

def generate_seo_article(image_description, user_caption):
    """Genera artículo SEO usando Groq con múltiples intentos y validación."""
    logger.info("Generando artículo SEO")
    
    prompt = f"""Creá un artículo periodístico completo en español argentino basado ESTRICTAMENTE en esta información:

INFORMACIÓN DEL USUARIO: {user_caption}
DESCRIPCIÓN DE LA IMAGEN: {image_description}

INSTRUCCIONES CRÍTICAS:
1. EXTENSIÓN: Mínimo 500 palabras, máximo 800
2. ESTILO: Español de Argentina (usá "descubrí" no "descubre", etc.)
3. ESTRUCTURA: H1 principal, H2, H3 según corresponda, listas si es pertinente
4. TAGS: 3-5 palabras clave ESPECÍFICAS del contenido, NO genéricas
5. SLUG: Basado en el título principal, formato URL amigable
6. SIN ENLACES EXTERNOS: Prohibido incluir enlaces a sitios externos
7. NATURALIDAD: Que suene como escrito por periodista humano argentino
8. CONTENIDO ORIGINAL: Basarse únicamente en la información proporcionada

Respondé ÚNICAMENTE con este formato JSON válido:
{
  "titulo_h1": "Título principal específico y descriptivo",
  "contenido_html": "HTML completo con h1, h2, h3, párrafos, listas si corresponde",
  "meta_descripcion": "Descripción de 150-160 caracteres en argentino",
  "tags": ["palabra1", "palabra2", "palabra3"],
  "slug_url": "slug-basado-en-titulo"
}"""

    max_attempts = 3
    
    for attempt in range(max_attempts):
        try:
            logger.info(f"Intento {attempt + 1} de {max_attempts}")
            
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            logger.info(f"Respuesta cruda del AI (primeros 200 chars): {content[:200]}")
            
            # Intentar extraer JSON con estrategias múltiples
            article_data = extract_json_content_robust(content)
            
            if article_data is None:
                logger.error(f"No se pudo extraer JSON válido en intento {attempt + 1}")
                if attempt == max_attempts - 1:
                    logger.error("Todos los intentos fallaron, usando fallback")
                    return generate_fallback_content(user_caption, image_description)
                continue
            
            # Validar calidad del contenido
            if not validate_content_quality(article_data, user_caption):
                logger.warning(f"Contenido de baja calidad en intento {attempt + 1}")
                if attempt == max_attempts - 1:
                    logger.error("Contenido de baja calidad en todos los intentos, usando fallback")
                    return generate_fallback_content(user_caption, image_description)
                continue
            
            # Limpiar enlaces externos del contenido
            article_data['contenido_html'] = re.sub(
                r'<a[^>]*href=["\']https?://[^"\']*["\'][^>]*>([^<]*)</a>',
                r'\1',
                article_data['contenido_html']
            )
            
            logger.info("Artículo SEO generado exitosamente")
            return article_data
            
        except Exception as e:
            logger.error(f"Error en intento {attempt + 1}: {str(e)}")
            if attempt == max_attempts - 1:
                logger.error("Todos los intentos fallaron, usando fallback")
                return generate_fallback_content(user_caption, image_description)
            
            time.sleep(2)  # Esperar antes del siguiente intento

def upload_image_to_wordpress(image_url, filename="image.jpg", alt_text=""):
    """Sube imagen a WordPress y configura alt text usando múltiples métodos."""
    logger.info(f"Subiendo imagen: {filename}")
    
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
        
        # Configurar alt text usando múltiples métodos
        if alt_text:
            try:
                # Método 1: Actualizar post de attachment
                attachment_post = wp_client.call(GetPost(attachment_id))
                attachment_post.excerpt = alt_text
                attachment_post.content = alt_text
                wp_client.call(EditPost(attachment_id, attachment_post))
                logger.info(f"Alt text configurado vía excerpt: {alt_text}")
                
                # Método 2: Intentar usar custom field (requiere plugin o función personalizada)
                try:
                    # Esto podría no funcionar sin configuración adicional en WordPress
                    attachment_post.custom_fields = [
                        {'key': '_wp_attachment_image_alt', 'value': alt_text}
                    ]
                    wp_client.call(EditPost(attachment_id, attachment_post))
                    logger.info(f"Alt text configurado vía custom field: {alt_text}")
                except Exception as e:
                    logger.warning(f"No se pudo configurar custom field para alt text: {e}")
                
            except Exception as e:
                logger.error(f"Error configurando alt text: {e}")
        
        return attachment_id, image_url_wp
        
    except Exception as e:
        logger.error(f"Error subiendo imagen: {e}")
        raise

def publish_seo_article_to_wordpress(article_data, featured_image_id, image_url, alt_text):
    """Publica artículo SEO en WordPress como borrador."""
    logger.info("Publicando artículo SEO en WordPress")
    
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
        
        # Configurar tags y categorías
        post.terms_names = {
            'post_tag': article_data['tags']
        }
        
        # Configurar slug
        if article_data.get('slug_url'):
            post.slug = article_data['slug_url']
        
        # Publicar post
        post_id = wp_client.call(NewPost(post))
        
        logger.info(f"Artículo SEO creado como BORRADOR con ID: {post_id}")
        return post_id
        
    except Exception as e:
        logger.error(f"Error publicando artículo: {e}")
        raise

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Maneja webhooks de Telegram."""
    try:
        update = request.get_json()
        logger.info(f"Webhook recibido: {json.dumps(update, indent=2)}")
        
        if 'message' not in update:
            return jsonify({"status": "ok"})
        
        message = update['message']
        
        if 'photo' in message and 'caption' in message:
            # Obtener la foto de mayor calidad
            photo = message['photo'][-1]  # La última es la de mayor resolución
            file_id = photo['file_id']
            caption = message['caption']
            
            logger.info(f"Foto recibida con caption: {caption}")
            
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
                
                # Generar descripción de la imagen usando el caption
                image_description = f"Imagen relacionada con: {caption}"
                
                # Generar alt text descriptivo
                alt_text = caption[:100] if len(caption) <= 100 else caption[:97] + "..."
                
                try:
                    # Subir imagen a WordPress
                    attachment_id, wp_image_url = upload_image_to_wordpress(
                        file_url, 
                        filename, 
                        alt_text
                    )
                    
                    # Generar artículo SEO
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
                        "message": "Artículo SEO creado exitosamente como borrador"
                    })
                    
                except Exception as e:
                    logger.error(f"Error procesando imagen y artículo: {e}")
                    return jsonify({"status": "error", "message": str(e)}), 500
            else:
                logger.error("No se pudo obtener información del archivo")
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
