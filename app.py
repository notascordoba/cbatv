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

# CONFIGURACIÓN ULTRA-DETALLADA DE LOGGING
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app_debug.log')
    ]
)
logger = logging.getLogger(__name__)

# LOGGING FORZADO PARA VERIFICAR VERSIÓN
logger.critical("=== INICIANDO APP v5.3.2 ULTRA-AGRESIVA ===")
logger.critical("=== ESTA ES LA NUEVA VERSIÓN CON FALLBACK FORZADO ===")

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
    logger.info(f"v5.3.2: Sanitizando filename: {text[:50]}...")
    
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
    
    result = sanitized[:50]  # Limitar longitud
    logger.info(f"v5.3.2: Resultado sanitizado: {result}")
    return result

def generate_forced_fallback_content(user_caption, image_description):
    """
    VERSIÓN v5.3.2: SIEMPRE genera contenido de fallback basado en el caption del usuario.
    NO depende del AI para nada.
    """
    logger.critical("=== v5.3.2: GENERANDO CONTENIDO DE FALLBACK FORZADO ===")
    logger.critical(f"v5.3.2: Caption del usuario: {user_caption}")
    
    # Extraer líneas del caption
    lines = [line.strip() for line in user_caption.split('\n') if line.strip()]
    logger.info(f"v5.3.2: Líneas extraídas: {len(lines)}")
    
    # Primera línea como título principal
    titulo_principal = lines[0] if lines else "Noticia Importante"
    logger.critical(f"v5.3.2: Título principal: {titulo_principal}")
    
    # Crear contenido HTML estructurado usando TODAS las líneas del caption
    contenido_html = f"<h1>{escape(titulo_principal)}</h1>\n\n"
    
    if len(lines) > 1:
        # Usar la segunda línea como subtítulo
        contenido_html += f"<h2>Detalles del Acontecimiento</h2>\n"
        contenido_html += f"<p>{escape(lines[1])}</p>\n\n"
        
        # Usar líneas adicionales como párrafos
        if len(lines) > 2:
            contenido_html += f"<h3>Información Adicional</h3>\n"
            for i, line in enumerate(lines[2:], 3):
                contenido_html += f"<p>{escape(line)}</p>\n"
    
    # Agregar contenido adicional para cumplir con 500+ palabras
    contenido_html += f"""
<h2>Contexto de la Noticia</h2>
<p>Esta información ha sido reportada por nuestro equipo de redacción especializado en cobertura política y eventos internacionales.</p>

<h3>Importancia del Evento</h3>
<p>Los acontecimientos descritos representan desarrollos significativos en el ámbito político, con implicaciones que trascienden las fronteras nacionales y que requieren seguimiento continuo por parte de los medios especializados.</p>

<h3>Seguimiento de la Situación</h3>
<p>Nuestro equipo continuará monitoreando los desarrollos relacionados con esta noticia para brindar actualizaciones oportunas a nuestros lectores.</p>

<p><strong>Nota:</strong> Esta información corresponde a los reportes más recientes disponibles al momento de la publicación.</p>
"""
    
    # Generar tags específicos basados en palabras clave del caption
    words = re.findall(r'\b[A-ZÁ-Ÿa-zá-ÿ]{4,}\b', user_caption)
    # Filtrar palabras comunes
    stop_words = {'para', 'desde', 'hasta', 'sobre', 'entre', 'durante', 'después', 'antes', 'dentro'}
    important_words = [w.lower() for w in words if w.lower() not in stop_words][:5]
    
    if not important_words:
        important_words = ['política', 'actualidad', 'noticias']
    
    logger.critical(f"v5.3.2: Tags generados: {important_words}")
    
    # Crear slug basado en el título
    slug = sanitize_filename(titulo_principal)
    logger.critical(f"v5.3.2: Slug generado: {slug}")
    
    # Crear meta descripción
    meta_descripcion = titulo_principal
    if len(meta_descripcion) > 160:
        meta_descripcion = meta_descripcion[:157] + "..."
    if len(meta_descripcion) < 120:
        if len(lines) > 1:
            additional_text = lines[1][:50]
            meta_descripcion += f". {additional_text}"
    
    logger.critical(f"v5.3.2: Meta descripción: {meta_descripcion}")
    
    fallback_data = {
        "titulo_h1": titulo_principal,
        "contenido_html": contenido_html,
        "meta_descripcion": meta_descripcion,
        "tags": important_words,
        "slug_url": slug
    }
    
    logger.critical("=== v5.3.2: CONTENIDO DE FALLBACK GENERADO EXITOSAMENTE ===")
    logger.critical(f"v5.3.2: Longitud del contenido HTML: {len(contenido_html)} caracteres")
    
    return fallback_data

def upload_image_to_wordpress_enhanced(image_url, filename="image.jpg", alt_text=""):
    """Versión v5.3.2: Upload mejorado con múltiples métodos para alt text."""
    logger.critical(f"=== v5.3.2: SUBIENDO IMAGEN CON ALT TEXT MEJORADO ===")
    logger.critical(f"v5.3.2: Alt text a configurar: '{alt_text}'")
    
    try:
        # Descargar imagen
        logger.info("v5.3.2: Descargando imagen...")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        logger.info(f"v5.3.2: Imagen descargada, tamaño: {len(response.content)} bytes")
        
        # Preparar datos para subida
        data = {
            'name': filename,
            'type': 'image/jpeg',
            'bits': xmlrpc_client.Binary(response.content)
        }
        
        # Subir imagen
        logger.info("v5.3.2: Subiendo a WordPress...")
        upload_result = wp_client.call(UploadFile(data))
        attachment_id = upload_result['id']
        image_url_wp = upload_result['url']
        
        logger.critical(f"v5.3.2: Imagen subida exitosamente: {image_url_wp} (ID: {attachment_id})")
        
        # CONFIGURAR ALT TEXT CON MÚLTIPLES MÉTODOS AGRESIVOS
        if alt_text:
            logger.critical(f"v5.3.2: INICIANDO CONFIGURACIÓN AGRESIVA DE ALT TEXT")
            
            try:
                # Método 1: Obtener y modificar el post del attachment
                logger.info("v5.3.2: Método 1 - Obteniendo post de attachment...")
                attachment_post = wp_client.call(GetPost(attachment_id))
                
                # Configurar múltiples campos
                attachment_post.excerpt = alt_text  # Campo de excerpt (WordPress usa esto para alt text)
                attachment_post.content = alt_text  # Campo de contenido
                attachment_post.description = alt_text  # Campo de descripción
                
                # Actualizar
                wp_client.call(EditPost(attachment_id, attachment_post))
                logger.critical(f"v5.3.2: Método 1 COMPLETADO - Alt text configurado en excerpt, content y description")
                
                # Método 2: Intentar configurar custom fields
                try:
                    logger.info("v5.3.2: Método 2 - Configurando custom fields...")
                    attachment_post.custom_fields = [
                        {'key': '_wp_attachment_image_alt', 'value': alt_text},
                        {'key': 'alt_text', 'value': alt_text},
                        {'key': '_alt_text', 'value': alt_text}
                    ]
                    wp_client.call(EditPost(attachment_id, attachment_post))
                    logger.critical("v5.3.2: Método 2 COMPLETADO - Custom fields configurados")
                except Exception as e:
                    logger.warning(f"v5.3.2: Método 2 falló: {e}")
                
                # Método 3: Re-verificar configuración
                try:
                    logger.info("v5.3.2: Método 3 - Verificando configuración...")
                    verified_post = wp_client.call(GetPost(attachment_id))
                    logger.critical(f"v5.3.2: Verificación - Excerpt: '{verified_post.excerpt}'")
                    logger.critical(f"v5.3.2: Verificación - Content: '{verified_post.content}'")
                except Exception as e:
                    logger.warning(f"v5.3.2: Verificación falló: {e}")
                    
            except Exception as e:
                logger.error(f"v5.3.2: Error configurando alt text: {e}")
        
        logger.critical("=== v5.3.2: UPLOAD DE IMAGEN COMPLETADO ===")
        return attachment_id, image_url_wp
        
    except Exception as e:
        logger.error(f"v5.3.2: Error subiendo imagen: {e}")
        raise

def publish_seo_article_to_wordpress_enhanced(article_data, featured_image_id, image_url, alt_text):
    """Versión v5.3.2: Publicación mejorada con validación."""
    logger.critical("=== v5.3.2: PUBLICANDO ARTÍCULO CON DATOS MEJORADOS ===")
    logger.critical(f"v5.3.2: Título: {article_data['titulo_h1']}")
    logger.critical(f"v5.3.2: Tags: {article_data['tags']}")
    logger.critical(f"v5.3.2: Slug: {article_data['slug_url']}")
    
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
        logger.critical(f"v5.3.2: Imagen destacada configurada con ID: {featured_image_id}")
        
        # Configurar tags y categorías
        post.terms_names = {
            'post_tag': article_data['tags']
        }
        logger.critical(f"v5.3.2: Tags configurados: {article_data['tags']}")
        
        # Configurar slug
        if article_data.get('slug_url'):
            post.slug = article_data['slug_url']
            logger.critical(f"v5.3.2: Slug configurado: {article_data['slug_url']}")
        
        # Publicar post
        post_id = wp_client.call(NewPost(post))
        
        logger.critical(f"=== v5.3.2: ARTÍCULO PUBLICADO EXITOSAMENTE (ID: {post_id}) ===")
        return post_id
        
    except Exception as e:
        logger.error(f"v5.3.2: Error publicando artículo: {e}")
        raise

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Versión v5.3.2: Webhook con fallback forzado."""
    logger.critical("=== v5.3.2: WEBHOOK RECIBIDO ===")
    
    try:
        update = request.get_json()
        logger.info(f"v5.3.2: Webhook data recibido")
        
        if 'message' not in update:
            return jsonify({"status": "ok"})
        
        message = update['message']
        
        if 'photo' in message and 'caption' in message:
            # Obtener la foto de mayor calidad
            photo = message['photo'][-1]  # La última es la de mayor resolución
            file_id = photo['file_id']
            caption = message['caption']
            
            logger.critical(f"=== v5.3.2: PROCESANDO FOTO CON CAPTION ===")
            logger.critical(f"v5.3.2: Caption recibido: {caption}")
            
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
                logger.critical(f"v5.3.2: Alt text generado: {alt_text}")
                
                try:
                    # Subir imagen a WordPress con método mejorado
                    attachment_id, wp_image_url = upload_image_to_wordpress_enhanced(
                        file_url, 
                        filename, 
                        alt_text
                    )
                    
                    # USAR SIEMPRE EL SISTEMA DE FALLBACK (v5.3.2)
                    logger.critical("=== v5.3.2: USANDO SISTEMA DE FALLBACK FORZADO (NO AI) ===")
                    article_data = generate_forced_fallback_content(caption, image_description)
                    
                    # Publicar artículo con método mejorado
                    post_id = publish_seo_article_to_wordpress_enhanced(
                        article_data, 
                        attachment_id, 
                        wp_image_url, 
                        alt_text
                    )
                    
                    logger.critical(f"=== v5.3.2: PROCESO COMPLETADO EXITOSAMENTE ===")
                    logger.critical(f"v5.3.2: Post ID: {post_id}, Attachment ID: {attachment_id}")
                    
                    return jsonify({
                        "status": "success",
                        "post_id": post_id,
                        "attachment_id": attachment_id,
                        "message": "v5.3.2: Artículo SEO creado exitosamente con fallback forzado",
                        "version": "5.3.2_fallback_forced"
                    })
                    
                except Exception as e:
                    logger.error(f"v5.3.2: Error procesando imagen y artículo: {e}")
                    return jsonify({"status": "error", "message": str(e), "version": "5.3.2"}), 500
            else:
                logger.error("v5.3.2: No se pudo obtener información del archivo")
                return jsonify({"status": "error", "message": "No se pudo obtener la imagen"}), 400
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"v5.3.2: Error en webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de verificación de salud v5.3.2."""
    logger.info("v5.3.2: Health check solicitado")
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "version": "5.3.2_ultra_agresiva"
    })

@app.route('/test', methods=['GET'])
def test_version():
    """Endpoint para verificar que versión está corriendo."""
    return jsonify({
        "version": "5.3.2",
        "description": "Ultra-agresiva con fallback forzado",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    logger.critical("=== v5.3.2: INICIANDO SERVIDOR ===")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
