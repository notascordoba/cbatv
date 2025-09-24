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

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# VERSIÓN v6.0.1 - DEBUG MEJORADO
# ==========================================
logger.critical("🔥 === VERSIÓN v6.0.1 - DEBUG COMPLETO === 🔥")
logger.critical("🔥 === RESPUESTA GROQ + DIAGNÓSTICO WORDPRESS === 🔥")

app = Flask(__name__)

# Configuración
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WP_URL = os.getenv('WORDPRESS_URL')
WP_USERNAME = os.getenv('WORDPRESS_USERNAME')
WP_PASSWORD = os.getenv('WORDPRESS_PASSWORD')

# Cliente Groq
client = Groq(api_key=GROQ_API_KEY)

logger.info(f"🔥 v6.0.1 configurado para WordPress: {WP_URL}")

def safe_filename(text: str) -> str:
    """Crea un nombre de archivo seguro desde un texto"""
    safe = re.sub(r'[^\w\s-]', '', text).strip().lower()
    safe = re.sub(r'[-\s]+', '-', safe)
    return safe[:50] if safe else 'imagen'

def extract_json_robust(text: str) -> Optional[Dict[str, Any]]:
    """Extracción JSON ultra-robusta con logging detallado"""
    logger.info("🔥 v6.0.1: Extrayendo JSON con estrategias múltiples")
    
    # Limpiar texto primero
    text = text.strip()
    
    # Estrategia 1: JSON directo
    try:
        result = json.loads(text)
        logger.critical("🔥 ÉXITO: JSON directo funcionó")
        return result
    except Exception as e:
        logger.info(f"🔥 JSON directo falló: {e}")
    
    # Estrategia 2: Buscar entre ```json y ```
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if json_match:
        try:
            result = json.loads(json_match.group(1).strip())
            logger.critical("🔥 ÉXITO: JSON con markdown funcionó")
            return result
        except Exception as e:
            logger.info(f"🔥 JSON markdown falló: {e}")
    
    # Estrategia 3: Buscar estructura { ... }
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            result = json.loads(brace_match.group(0))
            logger.critical("🔥 ÉXITO: JSON con braces funcionó")
            return result
        except Exception as e:
            logger.info(f"🔥 JSON braces falló: {e}")
    
    # Estrategia 4: Buscar campos individualmente y construir JSON
    try:
        titulo_match = re.search(r'"titulo":\s*"([^"]*)"', text)
        contenido_match = re.search(r'"contenido":\s*"([^"]*(?:\\.[^"]*)*)"', text)
        tags_match = re.search(r'"tags":\s*\[(.*?)\]', text)
        slug_match = re.search(r'"slug":\s*"([^"]*)"', text)
        
        if titulo_match and contenido_match:
            result = {
                "titulo": titulo_match.group(1),
                "contenido": contenido_match.group(1).replace('\\"', '"').replace('\\n', '\n'),
                "slug": slug_match.group(1) if slug_match else safe_filename(titulo_match.group(1)),
                "tags": []
            }
            
            if tags_match:
                tags_str = tags_match.group(1)
                tags = [tag.strip(' "') for tag in tags_str.split(',')]
                result["tags"] = tags
            
            logger.critical("🔥 ÉXITO: JSON construido manualmente")
            return result
    except Exception as e:
        logger.info(f"🔥 JSON manual falló: {e}")
    
    logger.critical("🔥 TODAS las estrategias JSON fallaron")
    return None

def generate_article_groq(caption: str) -> Dict[str, Any]:
    """Genera artículo con Groq usando prompt periodístico optimizado"""
    logger.critical(f"🔥 v6.0.1: GENERANDO ARTÍCULO PERIODÍSTICO")
    logger.info(f"Caption: {caption[:100]}...")
    
    # Prompt super específico para periodismo argentino
    system_prompt = """Eres un periodista argentino experimentado especializado en política. Escribes para un medio digital serio.

INSTRUCCIONES ESTRICTAS:
1. Escribe SOLO sobre los hechos específicos mencionados en el texto
2. NO inventes información adicional
3. NO uses frases genéricas como "los expertos opinan" o "se espera que"
4. Usa tono periodístico directo, presente o pasado
5. Estructura clara con H2 y H3
6. Mínimo 500 palabras
7. Tags específicos del tema (máximo 5)
8. Slug URL-friendly

FORMATO DE RESPUESTA (JSON válido):
{
    "titulo": "Título específico y directo",
    "contenido": "Artículo completo con HTML (<h2>, <h3>, <p>)",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "slug": "titulo-url-amigable",
    "descripcion": "Meta descripción 150-160 caracteres"
}

EJEMPLO de contenido correcto:
- "Javier Milei pronunciará mañana su discurso en la ONU..."
- "El encuentro entre Milei y Trump se realizó hoy..."
- "La intervención está programada para las 12:45..."

NUNCA escribas:
- "La importancia de la participación argentina..."
- "Los analistas esperan que..."
- "Es fundamental entender que..."

RESPONDE ÚNICAMENTE CON EL JSON, SIN TEXTO ADICIONAL."""

    user_prompt = f"Escribe un artículo periodístico basado en: {caption}"
    
    try:
        logger.info("🔥 Enviando request a Groq...")
        
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.2,
            max_tokens=2000
        )
        
        ai_response = completion.choices[0].message.content
        logger.info(f"🔥 Respuesta Groq recibida: {len(ai_response)} caracteres")
        logger.critical(f"🔥 RESPUESTA GROQ COMPLETA:\n{ai_response}")
        logger.critical(f"🔥 PRIMEROS 500 CHARS: {ai_response[:500]}")
        logger.critical(f"🔥 ÚLTIMOS 500 CHARS: {ai_response[-500:]}")
        
        # Extraer JSON
        parsed = extract_json_robust(ai_response)
        
        if parsed and "titulo" in parsed and "contenido" in parsed:
            # Validar que no sea contenido genérico
            content_lower = parsed['contenido'].lower()
            generic_phrases = [
                'información relevante sobre el tema',
                'contenido de actualidad',
                'más información:',
                'fuente externa:',
                'artículos relacionados'
            ]
            
            is_generic = any(phrase in content_lower for phrase in generic_phrases)
            
            if is_generic:
                logger.warning("🔥 Contenido genérico detectado, rechazando")
                raise ValueError("Contenido genérico")
            
            # Asegurar que tenga todos los campos
            if "tags" not in parsed:
                parsed["tags"] = ["actualidad", "politica", "argentina"]
            if "slug" not in parsed:
                parsed["slug"] = safe_filename(parsed["titulo"])
            if "descripcion" not in parsed:
                parsed["descripcion"] = f"{parsed['titulo'][:150]}..."
            
            logger.critical("🔥 ARTÍCULO ESPECÍFICO GENERADO EXITOSAMENTE")
            logger.critical(f"🔥 TÍTULO EXTRAÍDO: {parsed['titulo']}")
            logger.critical(f"🔥 SLUG EXTRAÍDO: {parsed['slug']}")
            logger.critical(f"🔥 TAGS EXTRAÍDOS: {parsed['tags']}")
            return parsed
        else:
            logger.warning("🔥 JSON inválido o incompleto")
            raise ValueError("JSON inválido")
            
    except Exception as e:
        logger.error(f"🔥 Error en Groq: {e}")
        logger.critical("🔥 ACTIVANDO SISTEMA FALLBACK")
        
        # Fallback inteligente
        words = caption.split()
        title_words = words[:8]  # Primeras 8 palabras para título
        title = " ".join(title_words)
        
        return {
            "titulo": title if len(title) < 60 else f"{title[:57]}...",
            "contenido": f"""<h2>Información Confirmada</h2>
<p>{caption}</p>
<h2>Desarrollo de la Noticia</h2>
<p>Los hechos reportados indican una situación de relevancia en el ámbito político nacional e internacional.</p>
<p>Esta información será ampliada conforme se obtengan más detalles de fuentes oficiales.</p>""",
            "tags": ["actualidad", "politica", "argentina", "breaking", "noticias"],
            "slug": safe_filename(title),
            "descripcion": f"{caption[:150]}..." if len(caption) > 150 else caption
        }

async def upload_image_wordpress(image_url: str, alt_text: str) -> Tuple[Optional[str], Optional[int]]:
    """Sube imagen a WordPress con alt text optimizado"""
    logger.critical(f"🔥 v6.0.1: SUBIENDO IMAGEN - ALT TEXT: {alt_text}")
    logger.critical(f"🔥 URL de imagen original: {image_url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    logger.error(f"🔥 Error descargando imagen: {response.status}")
                    return None, None
                
                image_data = await response.read()
                logger.info(f"🔥 Imagen descargada: {len(image_data)} bytes")
                filename = f"{safe_filename(alt_text)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                logger.info(f"🔥 Nombre archivo: {filename}")
                
                # Subir a WordPress
                wp_upload_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/media"
                headers = {
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Type': 'image/jpeg'
                }
                
                logger.critical(f"🔥 INTENTANDO SUBIR A: {wp_upload_url}")
                logger.critical(f"🔥 USUARIO WP: {WP_USERNAME}")
                logger.critical(f"🔥 PASSWORD LENGTH: {len(WP_PASSWORD) if WP_PASSWORD else 'NO_PASSWORD'}")
                
                upload_response = requests.post(
                    wp_upload_url,
                    headers=headers,
                    data=image_data,
                    auth=(WP_USERNAME, WP_PASSWORD),
                    timeout=30
                )
                
                logger.critical(f"🔥 RESPUESTA UPLOAD: {upload_response.status_code}")
                logger.critical(f"🔥 RESPUESTA HEADERS: {dict(upload_response.headers)}")
                
                if upload_response.status_code != 201:
                    logger.error(f"🔥 Error subiendo imagen: {upload_response.status_code}")
                    logger.critical(f"🔥 RESPUESTA WP COMPLETA: {upload_response.text}")
                    logger.critical(f"🔥 REQUEST HEADERS ENVIADOS: {headers}")
                    
                    # Intentar diagnóstico adicional
                    if upload_response.status_code == 403:
                        logger.critical("🔥 ERROR 403: Problema de autenticación")
                        logger.critical("🔥 Verificar credenciales WordPress en variables de entorno")
                    elif upload_response.status_code == 401:
                        logger.critical("🔥 ERROR 401: Credenciales inválidos")
                    
                    return None, None
                
                upload_data = upload_response.json()
                wp_image_url = upload_data['source_url']
                image_id = upload_data['id']
                
                logger.critical(f"🔥 IMAGEN SUBIDA EXITOSAMENTE: {wp_image_url} (ID: {image_id})")
                
                # Configurar alt text con método POST (más confiable)
                alt_update_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/media/{image_id}"
                alt_data = {
                    'alt_text': alt_text,
                    'title': alt_text,
                    'description': alt_text,
                    'caption': alt_text
                }
                
                logger.critical(f"🔥 CONFIGURANDO ALT TEXT: {alt_update_url}")
                
                alt_response = requests.post(
                    alt_update_url,
                    json=alt_data,
                    auth=(WP_USERNAME, WP_PASSWORD)
                )
                
                if alt_response.status_code == 200:
                    logger.critical(f"🔥 ALT TEXT CONFIGURADO EXITOSAMENTE: {alt_text}")
                else:
                    logger.error(f"🔥 Error configurando alt text: {alt_response.status_code}")
                    logger.error(f"🔥 Respuesta alt text: {alt_response.text}")
                
                return wp_image_url, image_id
                
    except Exception as e:
        logger.critical(f"🔥 EXCEPCIÓN COMPLETA subiendo imagen: {e}")
        import traceback
        logger.critical(f"🔥 TRACEBACK: {traceback.format_exc()}")
        return None, None

def create_wordpress_draft(article_data: Dict[str, Any], image_url: Optional[str], image_id: Optional[int]) -> Optional[int]:
    """Crea post borrador en WordPress"""
    logger.critical(f"🔥 v6.0.1: CREANDO POST - {article_data['titulo']}")
    
    try:
        # Preparar contenido HTML
        html_content = ""
        if image_url:
            html_content += f'<p><img src="{image_url}" alt="{article_data["titulo"]}" class="wp-image-featured"></p>\n\n'
        
        html_content += article_data['contenido']
        
        # Datos del post
        post_data = {
            'title': article_data['titulo'],
            'content': html_content,
            'status': 'draft',
            'slug': article_data['slug'],
            'excerpt': article_data.get('descripcion', ''),
        }
        
        logger.critical(f"🔥 POST DATA: título={article_data['titulo']}, slug={article_data['slug']}")
        
        # Agregar tags si existen
        if article_data.get('tags'):
            # Crear/obtener tags
            tag_ids = []
            for tag in article_data['tags']:
                logger.info(f"🔥 Procesando tag: {tag}")
                tag_response = requests.post(
                    f"{WP_URL.rstrip('/')}/wp-json/wp/v2/tags",
                    json={'name': tag},
                    auth=(WP_USERNAME, WP_PASSWORD)
                )
                if tag_response.status_code in [200, 201]:
                    tag_data = tag_response.json()
                    tag_ids.append(tag_data['id'])
                    logger.info(f"🔥 Tag creado/encontrado: {tag} (ID: {tag_data['id']})")
                else:
                    logger.warning(f"🔥 Error procesando tag {tag}: {tag_response.status_code}")
            
            if tag_ids:
                post_data['tags'] = tag_ids
                logger.critical(f"🔥 TAGS IDs ASIGNADOS: {tag_ids}")
        
        # Configurar imagen destacada
        if image_id:
            post_data['featured_media'] = image_id
            logger.critical(f"🔥 IMAGEN DESTACADA: ID {image_id}")
        
        # Crear post
        wp_posts_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts"
        logger.critical(f"🔥 CREANDO POST EN: {wp_posts_url}")
        
        response = requests.post(
            wp_posts_url,
            json=post_data,
            auth=(WP_USERNAME, WP_PASSWORD)
        )
        
        logger.critical(f"🔥 RESPUESTA CREAR POST: {response.status_code}")
        
        if response.status_code == 201:
            post_info = response.json()
            post_id = post_info['id']
            logger.critical(f"🔥 POST CREADO EXITOSAMENTE: ID {post_id}")
            return post_id
        else:
            logger.error(f"🔥 Error creando post: {response.status_code}")
            logger.critical(f"🔥 RESPUESTA POST COMPLETA: {response.text}")
            return None
            
    except Exception as e:
        logger.critical(f"🔥 EXCEPCIÓN creando post: {e}")
        import traceback
        logger.critical(f"🔥 TRACEBACK POST: {traceback.format_exc()}")
        return None

@app.route('/')
def home():
    return jsonify({
        "status": "🔥 Bot SEO v6.0.1 funcionando",
        "version": "v6.0.1 DEBUG COMPLETO",
        "features": [
            "Logging detallado Groq",
            "Diagnóstico WordPress",
            "Debugging extremo",
            "Traceback completo"
        ]
    })

@app.route('/health')
def health():
    return jsonify({
        "version": "v6.0.1",
        "status": "DEBUG COMPLETO",
        "groq": "LOGGED",
        "wordpress": "DIAGNOSED"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.critical("🔥 v6.0.1: WEBHOOK RECIBIDO")
    
    try:
        update = request.get_json()
        
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            
            if 'photo' in message and 'caption' in message:
                logger.critical("🔥 v6.0.1: PROCESANDO FOTO + CAPTION")
                
                photo = message['photo'][-1]
                file_id = photo['file_id']
                caption = message['caption']
                
                logger.info(f"🔥 Caption: {caption[:100]}...")
                
                # Obtener URL de la imagen
                file_info_response = requests.get(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
                )
                
                if file_info_response.status_code == 200:
                    file_info = file_info_response.json()
                    file_path = file_info['result']['file_path']
                    image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
                    
                    # Generar artículo
                    article_data = generate_article_groq(caption)
                    
                    # Subir imagen
                    wp_image_url, image_id = asyncio.run(
                        upload_image_wordpress(image_url, article_data['titulo'])
                    )
                    
                    if wp_image_url:
                        # Crear post
                        post_id = create_wordpress_draft(article_data, wp_image_url, image_id)
                        
                        if post_id:
                            logger.critical(f"🔥 ÉXITO TOTAL v6.0.1: POST {post_id}")
                            
                            # Enviar confirmación
                            requests.post(
                                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                                json={
                                    'chat_id': chat_id,
                                    'text': f"🔥 ¡Artículo v6.0.1 creado!\n\n"
                                           f"📰 {article_data['titulo']}\n"
                                           f"🔗 {article_data['slug']}\n"
                                           f"🏷️ {', '.join(article_data['tags'][:3])}\n"
                                           f"📝 Post ID: {post_id}\n"
                                           f"📊 Estado: BORRADOR\n"
                                           f"🔥 DEBUG: Logs completos disponibles"
                                }
                            )
                        else:
                            logger.error("🔥 Error creando post")
                            # Enviar notificación de error
                            requests.post(
                                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                                json={
                                    'chat_id': chat_id,
                                    'text': "🔥 v6.0.1: Error creando post, pero artículo generado. Ver logs."
                                }
                            )
                    else:
                        logger.error("🔥 Error subiendo imagen")
                        # Enviar notificación de error de imagen
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                            json={
                                'chat_id': chat_id,
                                'text': "🔥 v6.0.1: Error subiendo imagen a WordPress. Ver logs para diagnóstico."
                            }
                        )
                else:
                    logger.error("🔥 Error obteniendo archivo Telegram")
            else:
                logger.info("🔥 Mensaje sin foto+caption")
        
    except Exception as e:
        logger.critical(f"🔥 ERROR CRÍTICO v6.0.1: {e}")
        import traceback
        logger.critical(f"🔥 TRACEBACK WEBHOOK: {traceback.format_exc()}")
    
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    logger.critical("🔥 v6.0.1 LISTA PARA DEBUG COMPLETO")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
