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

# Configuración de logging mejorada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# VERSIÓN v5.3.5 - SOLUCIÓN DEFINITIVA
# ==========================================
logger.critical("=== INICIANDO APP v5.3.5 - SOLUCIÓN DEFINITIVA ===")
logger.critical("=== NUEVO PROMPT PERIODÍSTICO + METADATOS CORRECTOS ===")

app = Flask(__name__)

# Verificar variables de entorno requeridas
required_vars = ['GROQ_API_KEY', 'TELEGRAM_BOT_TOKEN', 'WP_URL', 'WP_USERNAME', 'WP_PASSWORD']
for var in required_vars:
    if not os.getenv(var):
        logger.error(f"Variable de entorno faltante: {var}")
        raise ValueError(f"Variable de entorno faltante: {var}")

# Configuración
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WP_URL = os.getenv('WP_URL')
WP_USERNAME = os.getenv('WP_USERNAME')
WP_PASSWORD = os.getenv('WP_PASSWORD')

# Cliente Groq
client = Groq(api_key=GROQ_API_KEY)

logger.info(f"Bot configurado para WordPress: {WP_URL}")
logger.critical("=== v5.3.5 CARGADA CORRECTAMENTE ===")

def safe_filename(text: str) -> str:
    """Crea un nombre de archivo seguro desde un texto"""
    # Eliminar caracteres especiales y convertir a minúsculas
    safe = re.sub(r'[^\w\s-]', '', text).strip().lower()
    # Reemplazar espacios con guiones
    safe = re.sub(r'[-\s]+', '-', safe)
    # Limitar longitud
    return safe[:50] if safe else 'imagen'

def extract_json_content(text: str) -> Optional[Dict[str, Any]]:
    """Extrae contenido JSON del texto con múltiples estrategias"""
    logger.info("=== v5.3.5: EXTRAYENDO JSON CON ESTRATEGIAS MÚLTIPLES ===")
    
    # Estrategia 1: JSON directo
    try:
        return json.loads(text.strip())
    except:
        pass
    
    # Estrategia 2: Buscar JSON entre ```json y ```
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except:
            pass
    
    # Estrategia 3: Buscar JSON entre { y }
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except:
            pass
    
    # Estrategia 4: Buscar cualquier estructura que parezca JSON
    try:
        # Limpiar texto y buscar patrones
        cleaned = re.sub(r'[^\x20-\x7E]', '', text)  # Solo ASCII imprimible
        json_pattern = r'(\{[^{}]*"titulo"[^{}]*\})'
        match = re.search(json_pattern, cleaned, re.IGNORECASE)
        if match:
            return json.loads(match.group(1))
    except:
        pass
    
    logger.warning("=== v5.3.5: TODAS LAS ESTRATEGIAS JSON FALLARON ===")
    return None

def generate_seo_article(caption: str) -> Dict[str, Any]:
    """Genera artículo SEO usando Groq con prompt periodístico mejorado"""
    logger.critical(f"=== v5.3.5: GENERANDO ARTÍCULO PERIODÍSTICO ===")
    logger.info(f"Caption recibido: {caption[:100]}...")
    
    # Prompt ultra-específico para periodismo argentino
    system_prompt = """Sos un periodista político argentino con 15 años de experiencia. Escribís para un medio digital serio y tu estilo es directo, informativo y basado en hechos concretos.

REGLAS FUNDAMENTALES:
1. Escribí SOLO sobre los hechos mencionados en el texto del usuario
2. NO inventes información que no esté en el texto original
3. NO uses frases genéricas como "los expertos opinan", "se espera que", "la importancia de"
4. Escribí en presente o pasado, nunca en futuro especulativo
5. Usá un tono periodístico directo, no educativo ni instructivo
6. El artículo debe tener MÍNIMO 500 palabras
7. Estructura: H1 (título), varios H2 (subtemas), H3 si es necesario

RESPUESTA EN JSON:
{
    "titulo": "Título periodístico directo y específico",
    "contenido": "Artículo completo con estructura HTML (h2, h3, p)",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "slug": "url-amigable-del-titulo",
    "descripcion": "Meta descripción de 150-160 caracteres"
}

Ejemplo de contenido correcto:
- "Javier Milei pronunciará su discurso en la Asamblea General de la ONU..."
- "El presidente argentino llegó ayer a Nueva York para participar..."
- "Durante su intervención, Milei abordará temas como..."

Ejemplo de contenido INCORRECTO (evitar):
- "La importancia de la participación argentina en organismos internacionales..."
- "Los analistas esperan que el discurso incluya..."
- "Es fundamental entender que..."
"""

    user_prompt = f"Escribí un artículo periodístico basado únicamente en esta información: {caption}"
    
    try:
        logger.info("=== v5.3.5: ENVIANDO REQUEST A GROQ ===")
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.3,
            max_tokens=2000
        )
        
        ai_response = completion.choices[0].message.content
        logger.info(f"=== v5.3.5: RESPUESTA GROQ RECIBIDA ===")
        logger.info(f"Primeros 200 chars: {ai_response[:200]}...")
        
        # Extraer JSON del contenido
        parsed_content = extract_json_content(ai_response)
        
        if parsed_content and all(key in parsed_content for key in ['titulo', 'contenido', 'tags', 'slug']):
            logger.critical("=== v5.3.5: JSON VÁLIDO EXTRAÍDO ===")
            
            # Validar que el contenido no sea genérico
            content_lower = parsed_content['contenido'].lower()
            generic_phrases = [
                'información relevante sobre el tema',
                'contenido de actualidad',
                'más información:',
                'los expertos opinan',
                'se espera que',
                'la importancia de'
            ]
            
            is_generic = any(phrase in content_lower for phrase in generic_phrases)
            if is_generic:
                logger.warning("=== v5.3.5: CONTENIDO GENÉRICO DETECTADO, USANDO FALLBACK ===")
                raise ValueError("Contenido genérico detectado")
            
            logger.critical("=== v5.3.5: CONTENIDO ESPECÍFICO VALIDADO ===")
            return parsed_content
        else:
            logger.warning("=== v5.3.5: JSON INVÁLIDO O INCOMPLETO ===")
            raise ValueError("JSON inválido")
        
    except Exception as e:
        logger.error(f"=== v5.3.5: ERROR EN GROQ: {e} ===")
        logger.critical("=== v5.3.5: ACTIVANDO SISTEMA FALLBACK ===")
        
        # Fallback mejorado basado en el caption
        return {
            "titulo": f"Noticia: {caption[:50]}..." if len(caption) > 50 else caption,
            "contenido": f"""<h2>Información Confirmada</h2>
<p>Según la información proporcionada: {caption}</p>
<p>Los detalles de este evento serán ampliados conforme se obtenga más información oficial.</p>
<h2>Contexto</h2>
<p>Esta noticia se desarrolla en el marco de los acontecimientos políticos actuales, donde cada declaración y acción tiene repercusión en el ámbito nacional e internacional.</p>
<p>Se continuará informando sobre los desarrollos de esta situación conforme estén disponibles fuentes oficiales verificadas.</p>""",
            "tags": ["actualidad", "politica", "argentina", "noticias", "breaking"],
            "slug": safe_filename(caption[:50]),
            "descripcion": f"{caption[:150]}..." if len(caption) > 150 else caption
        }

async def upload_image_to_wp(image_url: str, alt_text: str) -> Tuple[Optional[str], Optional[int]]:
    """Sube imagen a WordPress y configura alt text"""
    logger.critical(f"=== v5.3.5: SUBIENDO IMAGEN CON ALT TEXT: {alt_text} ===")
    
    try:
        # Descargar imagen
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    
                    # Determinar nombre del archivo
                    filename = f"{safe_filename(alt_text)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    
                    # Subir a WordPress
                    wp_upload_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/media"
                    headers = {
                        'Content-Disposition': f'attachment; filename="{filename}"',
                        'Content-Type': 'image/jpeg'
                    }
                    
                    upload_response = requests.post(
                        wp_upload_url,
                        headers=headers,
                        data=image_data,
                        auth=(WP_USERNAME, WP_PASSWORD)
                    )
                    
                    if upload_response.status_code == 201:
                        upload_data = upload_response.json()
                        wp_image_url = upload_data['source_url']
                        image_id = upload_data['id']
                        
                        logger.info(f"=== v5.3.5: IMAGEN SUBIDA: {wp_image_url} (ID: {image_id}) ===")
                        
                        # Configurar alt text - MÉTODO MEJORADO
                        alt_update_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/media/{image_id}"
                        alt_data = {
                            'alt_text': alt_text,
                            'title': alt_text,
                            'description': alt_text
                        }
                        
                        alt_response = requests.post(
                            alt_update_url,
                            json=alt_data,
                            auth=(WP_USERNAME, WP_PASSWORD)
                        )
                        
                        if alt_response.status_code == 200:
                            logger.critical(f"=== v5.3.5: ALT TEXT CONFIGURADO EXITOSAMENTE: {alt_text} ===")
                        else:
                            logger.error(f"=== v5.3.5: FALLO AL CONFIGURAR ALT TEXT: {alt_response.status_code} ===")
                            logger.error(f"Response: {alt_response.text}")
                        
                        return wp_image_url, image_id
                    else:
                        logger.error(f"=== v5.3.5: ERROR SUBIENDO IMAGEN: {upload_response.status_code} ===")
                        return None, None
                else:
                    logger.error(f"=== v5.3.5: ERROR DESCARGANDO IMAGEN: {response.status} ===")
                    return None, None
                    
    except Exception as e:
        logger.error(f"=== v5.3.5: EXCEPCIÓN SUBIENDO IMAGEN: {e} ===")
        return None, None

def create_wordpress_post(seo_content: Dict[str, Any], image_url: Optional[str], image_id: Optional[int]) -> Optional[int]:
    """Crea post en WordPress como borrador"""
    logger.critical(f"=== v5.3.5: CREANDO POST CON TÍTULO: {seo_content['titulo']} ===")
    
    try:
        # Preparar contenido HTML con imagen destacada
        html_content = ""
        if image_url:
            html_content += f'<p><img src="{image_url}" alt="{seo_content["titulo"]}" class="wp-image-featured"></p>\n'
        
        html_content += seo_content['contenido']
        
        # Datos del post
        post_data = {
            'title': seo_content['titulo'],
            'content': html_content,
            'status': 'draft',
            'slug': seo_content['slug'],
            'excerpt': seo_content.get('descripcion', ''),
            'tags': seo_content.get('tags', [])
        }
        
        # Configurar imagen destacada si existe
        if image_id:
            post_data['featured_media'] = image_id
            logger.info(f"=== v5.3.5: IMAGEN DESTACADA CONFIGURADA: ID {image_id} ===")
        
        # Crear post
        wp_posts_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts"
        
        logger.info(f"=== v5.3.5: ENVIANDO POST A: {wp_posts_url} ===")
        logger.info(f"Slug: {post_data['slug']}")
        logger.info(f"Tags: {post_data['tags']}")
        
        response = requests.post(
            wp_posts_url,
            json=post_data,
            auth=(WP_USERNAME, WP_PASSWORD)
        )
        
        if response.status_code == 201:
            post_info = response.json()
            post_id = post_info['id']
            logger.critical(f"=== v5.3.5: POST CREADO EXITOSAMENTE: ID {post_id} ===")
            return post_id
        else:
            logger.error(f"=== v5.3.5: ERROR CREANDO POST: {response.status_code} ===")
            logger.error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"=== v5.3.5: EXCEPCIÓN CREANDO POST: {e} ===")
        return None

@app.route('/')
def home():
    return jsonify({
        "status": "Bot SEO funcionando correctamente",
        "version": "v5.3.5 - SOLUCIÓN DEFINITIVA",
        "features": [
            "Prompt periodístico real",
            "Metadatos correctos (slug/tags)",
            "Alt text funcional",
            "Contenido no genérico"
        ]
    })

@app.route('/health')
def health():
    return jsonify({
        "version": "v5.3.5",
        "status": "running",
        "description": "SOLUCIÓN DEFINITIVA - Periodismo real + metadatos correctos"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.critical("=== v5.3.5: WEBHOOK RECIBIDO ===")
    
    try:
        update = request.get_json()
        
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            
            # Verificar si hay foto y caption
            if 'photo' in message and 'caption' in message:
                logger.critical("=== v5.3.5: PROCESANDO FOTO + CAPTION ===")
                
                photo = message['photo'][-1]  # Imagen de mejor calidad
                file_id = photo['file_id']
                caption = message['caption']
                
                logger.info(f"Caption recibido: {caption}")
                
                # Obtener URL del archivo
                file_info_response = requests.get(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
                )
                
                if file_info_response.status_code == 200:
                    file_info = file_info_response.json()
                    file_path = file_info['result']['file_path']
                    image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
                    
                    # Generar contenido SEO
                    logger.critical("=== v5.3.5: INICIANDO GENERACIÓN SEO ===")
                    seo_content = generate_seo_article(caption)
                    
                    # Subir imagen con alt text correcto
                    wp_image_url, image_id = asyncio.run(
                        upload_image_to_wp(image_url, seo_content['titulo'])
                    )
                    
                    # Crear post
                    if wp_image_url:
                        post_id = create_wordpress_post(seo_content, wp_image_url, image_id)
                        
                        if post_id:
                            logger.critical(f"=== v5.3.5: ÉXITO TOTAL - POST {post_id} CREADO ===")
                            
                            # Enviar confirmación
                            requests.post(
                                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                                json={
                                    'chat_id': chat_id,
                                    'text': f"✅ v5.3.5 - Artículo SEO creado exitosamente!\n\n"
                                           f"📰 Título: {seo_content['titulo']}\n"
                                           f"🔗 Slug: {seo_content['slug']}\n"
                                           f"🏷️ Tags: {', '.join(seo_content['tags'])}\n"
                                           f"📝 Post ID: {post_id}\n"
                                           f"📊 Estado: BORRADOR para revisión"
                                }
                            )
                        else:
                            logger.error("=== v5.3.5: FALLO CREANDO POST ===")
                    else:
                        logger.error("=== v5.3.5: FALLO SUBIENDO IMAGEN ===")
                else:
                    logger.error("=== v5.3.5: FALLO OBTENIENDO INFO ARCHIVO ===")
            else:
                logger.info("=== v5.3.5: MENSAJE SIN FOTO+CAPTION ===")
        else:
            logger.info("=== v5.3.5: UPDATE SIN MESSAGE ===")
            
    except Exception as e:
        logger.critical(f"=== v5.3.5: ERROR CRÍTICO EN WEBHOOK: {e} ===")
        
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    logger.critical("=== v5.3.5 LISTA PARA FUNCIONAR ===")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
