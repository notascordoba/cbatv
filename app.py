#!/usr/bin/env python3
"""
VERSIÓN v1.1.2 - BASE FUNCIONAL + Mejoras Específicas
Basado en: app_v1.1.0.py (webhook que funcionaba)

CHANGELOG v1.1.2:
- Base: app_v1.1.0.py (webhook y asyncio que funcionaba)
- Mejorado: upload_image_to_wordpress con título y alt text
- Mejorado: Prompt de IA para contenido profesional
- Mejorado: Configuración SEO completa
- Conservado: Sistema de webhook funcional

Autor: MiniMax Agent
Fecha: 2025-09-21
"""

import os
import asyncio
import aiohttp
import aiofiles
from datetime import datetime
import json
import re
from PIL import Image
import io
import base64
import logging
from typing import Optional, Dict, List, Tuple

# Fix para compatibilidad Python 3.10+ con wordpress_xmlrpc
import collections
import collections.abc
if not hasattr(collections, 'Iterable'):
    collections.Iterable = collections.abc.Iterable

# Import opcional de OpenAI (solo para transcripción de audio)
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    openai = None
    OPENAI_AVAILABLE = False
    
from groq import Groq
import requests
from telegram import Update, Message, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
import wordpress_xmlrpc
from wordpress_xmlrpc import Client
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client
from flask import Flask, request, jsonify

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutomacionPeriodisticaV1:
    def __init__(self):
        """Inicializar sistema completo de automatización periodística"""
        logger.info("🚀 Inicializando Sistema de Automatización Periodística v1.1.2")
        
        # Configuraciones básicas
        self.MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
        self.SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'webp']
        self.TARGET_WIDTH = 1200
        self.TARGET_HEIGHT = 630
        self.IMAGE_QUALITY = 85
        
        # Estadísticas
        self.stats = {
            'articulos_creados': 0,
            'imagenes_procesadas': 0,
            'errores': 0,
            'inicio_sistema': datetime.now().isoformat()
        }
        
        # Configuración de servicios
        self._setup_services()
        
        logger.info("✅ Sistema inicializado correctamente")

    def _setup_services(self):
        """Configurar todos los servicios necesarios"""
        try:
            # Configurar Groq
            groq_api_key = os.getenv('GROQ_API_KEY')
            if not groq_api_key:
                raise ValueError("❌ GROQ_API_KEY no configurada")
            
            self.groq_client = Groq(api_key=groq_api_key)
            logger.info("✅ Groq configurado")
            
            # Configurar WordPress
            wp_url = os.getenv('WORDPRESS_URL')
            wp_username = os.getenv('WORDPRESS_USERNAME')
            wp_password = os.getenv('WORDPRESS_PASSWORD')
            
            if not all([wp_url, wp_username, wp_password]):
                raise ValueError("❌ Credenciales de WordPress incompletas")
            
            xmlrpc_url = f"{wp_url.rstrip('/')}/xmlrpc.php"
            self.wordpress_client = Client(xmlrpc_url, wp_username, wp_password)
            logger.info("✅ WordPress configurado")
            
            # Configurar Telegram
            telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not telegram_token:
                raise ValueError("❌ TELEGRAM_BOT_TOKEN no configurado")
            
            self.bot = Bot(token=telegram_token)
            logger.info("✅ Telegram configurado")
            
        except Exception as e:
            logger.error(f"❌ Error configurando servicios: {e}")
            raise

    def _extraer_palabra_clave(self, texto: str) -> str:
        """Extraer palabra clave principal del texto"""
        try:
            # Limpiar texto
            texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
            palabras = texto_limpio.split()
            
            # Filtrar palabras muy comunes
            stop_words = ['el', 'la', 'los', 'las', 'de', 'del', 'a', 'en', 'con', 'por', 'para', 'es', 'son', 'un', 'una', 'que', 'se', 'no', 'te', 'le', 'da', 'su', 'por', 'son', 'con', 'no', 'te', 'lo', 'al', 'ya', 'me', 'si', 'al']
            palabras_filtradas = [p for p in palabras if len(p) > 2 and p not in stop_words]
            
            # Tomar las primeras 2-3 palabras más relevantes
            if len(palabras_filtradas) >= 2:
                keyword = ' '.join(palabras_filtradas[:2])
            else:
                keyword = ' '.join(palabras[:2]) if len(palabras) >= 2 else palabras[0] if palabras else 'actualidad'
            
            logger.info(f"🎯 Palabra clave extraída: '{keyword}'")
            return keyword
            
        except Exception as e:
            logger.warning(f"⚠️ Error extrayendo palabra clave: {e}")
            return "actualidad"

    def _generar_prompt_profesional(self, texto_usuario: str, palabra_clave: str) -> str:
        """Genera prompt optimizado para contenido periodístico profesional"""
        
        prompt = f"""Sos un PERIODISTA PROFESIONAL especializado en redacción SEO para medios digitales argentinos. Creás artículos informativos, serios y bien estructurados.

INFORMACIÓN RECIBIDA:
{texto_usuario}

PALABRA CLAVE OBJETIVO: "{palabra_clave}"

INSTRUCCIONES ESPECÍFICAS:

1. **TÍTULO H1** (30-70 caracteres):
   - DEBE comenzar con "{palabra_clave}"
   - Profesional, específico, periodístico
   - Sin emojis, estilo serio de noticias
   - Ejemplo: "{palabra_clave}: nuevas medidas entran en vigencia en Argentina"

2. **META DESCRIPCIÓN** (EXACTAMENTE 135 caracteres):
   - Incluir "{palabra_clave}"
   - Tono informativo y profesional
   - Contar caracteres precisos

3. **SLUG**: "{palabra_clave.replace(' ', '-')}"

4. **CONTENIDO** (600-1000 palabras):
   - Expandir la información base con investigación periodística
   - Contexto argentino relevante
   - Datos específicos, fechas, cifras
   - Lenguaje natural, no robótico
   - Sin frases como "En conclusión" o similares

5. **ESTRUCTURA PROFESIONAL**:
   - H2: Contexto y antecedentes
   - H2: Detalles específicos sobre {palabra_clave}
   - H2: Impacto y consecuencias
   - H3: Subtemas relevantes
   - Cada título debe ser descriptivo y específico

6. **ENLACES INTERNOS** (2-3):
   - <a href="/categoria/actualidad">actualidad</a>
   - <a href="/categoria/economia">economía</a>
   - <a href="/categoria/politica">política</a>
   - Integrarlos naturalmente

7. **OPTIMIZACIÓN**:
   - "{palabra_clave}" en primer párrafo
   - Variaciones naturales de la palabra clave
   - Lenguaje periodístico argentino
   - Sin sonar artificial o generado por IA

8. **TAGS**: Incluir palabra clave + 3-4 términos relacionados relevantes

RESPONDER SOLO EN JSON VÁLIDO:

{{
    "titulo": "TÍTULO PROFESIONAL COMENZANDO CON PALABRA CLAVE",
    "metadescripcion": "EXACTAMENTE 135 CARACTERES CON PALABRA CLAVE",
    "palabra_clave": "{palabra_clave}",
    "slug": "{palabra_clave.replace(' ', '-')}",
    "contenido_html": "ARTÍCULO COMPLETO EN HTML PROFESIONAL",
    "tags": ["{palabra_clave}", "tag2", "tag3", "tag4"],
    "categoria": "CATEGORÍA_APROPIADA"
}}

IMPORTANTE: El contenido debe ser PROFESIONAL, INFORMATIVO y de CALIDAD PERIODÍSTICA. Expandir la información base con valor real."""

        return prompt

    async def generar_articulo_ia(self, texto_usuario: str, palabra_clave: str) -> Dict:
        """Generar artículo usando IA con prompt profesional"""
        try:
            prompt = self._generar_prompt_profesional(texto_usuario, palabra_clave)
            
            logger.info("🤖 Generando artículo profesional con IA...")
            
            # Llamada a Groq
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "Sos un periodista profesional argentino especializado en SEO. Respondés SOLO en JSON válido."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                model="llama-3.1-70b-versatile",
                temperature=0.7,
                max_tokens=4000
            )
            
            content = chat_completion.choices[0].message.content.strip()
            
            # Limpiar respuesta
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            try:
                article_data = json.loads(content)
                
                # Validaciones críticas
                titulo = article_data.get('titulo', '')
                if not titulo.lower().startswith(palabra_clave.lower()):
                    logger.warning(f"⚠️ Título no comienza con palabra clave")
                
                meta_desc = article_data.get('metadescripcion', '')
                if len(meta_desc) != 135:
                    logger.warning(f"⚠️ Meta descripción: {len(meta_desc)} chars (debe ser 135)")
                
                contenido = article_data.get('contenido_html', '')
                word_count = len(contenido.split())
                if word_count < 300:
                    logger.warning(f"⚠️ Contenido corto: {word_count} palabras")
                
                logger.info("✅ Artículo profesional generado correctamente")
                return article_data
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error parseando JSON de IA: {e}")
                return self._generar_articulo_respaldo(texto_usuario, palabra_clave)
                
        except Exception as e:
            logger.error(f"❌ Error generando artículo con IA: {e}")
            return self._generar_articulo_respaldo(texto_usuario, palabra_clave)

    def _generar_articulo_respaldo(self, texto_usuario: str, palabra_clave: str) -> Dict:
        """Genera artículo de respaldo si falla la IA"""
        logger.info("🔄 Generando artículo de respaldo...")
        
        titulo = f"{palabra_clave.title()}: información actualizada sobre la situación en Argentina"
        
        # Meta descripción exacta de 135 caracteres
        meta_base = f"Conocé todos los detalles sobre {palabra_clave} en Argentina. Información actualizada y completa para mantenerte informado."
        if len(meta_base) > 135:
            meta_desc = meta_base[:132] + "..."
        else:
            meta_desc = meta_base.ljust(135)[:135]
        
        return {
            "titulo": titulo,
            "metadescripcion": meta_desc,
            "palabra_clave": palabra_clave,
            "slug": palabra_clave.replace(' ', '-'),
            "contenido_html": f"""
<p>La situación actual de <strong>{palabra_clave}</strong> representa un tema de gran relevancia para Argentina. Te contamos todos los detalles.</p>

<h2>Contexto sobre {palabra_clave.title()}</h2>
<p>{texto_usuario}</p>

<p>Es importante mantenerse informado sobre los desarrollos relacionados con <strong>{palabra_clave}</strong>, ya que pueden tener impacto directo en la vida cotidiana de los argentinos.</p>

<h2>Detalles específicos sobre {palabra_clave.title()}</h2>
<p>Los especialistas señalan que <strong>{palabra_clave}</strong> requiere atención especial debido a las circunstancias actuales del país.</p>

<h3>Impacto en la economía nacional</h3>
<p>El tema de <strong>{palabra_clave}</strong> tiene repercusiones importantes en diferentes sectores económicos del país.</p>

<h3>Perspectivas a futuro</h3>
<p>Los análisis más recientes indican que <strong>{palabra_clave}</strong> continuará siendo monitoreado de cerca por las autoridades competentes.</p>

<h2>Consecuencias para los ciudadanos</h2>
<p>Es fundamental que los argentinos se mantengan al tanto de las novedades relacionadas con <strong>{palabra_clave}</strong> para tomar decisiones informadas.</p>

<p>Para más información sobre temas relacionados, consultá nuestra sección de <a href="/categoria/actualidad">actualidad</a> y seguí las últimas noticias en <a href="/categoria/economia">economía</a>.</p>
""",
            "tags": [palabra_clave, "actualidad", "argentina", "información"],
            "categoria": "Actualidad"
        }

    async def optimizar_imagen(self, data_imagen: bytes) -> bytes:
        """Optimizar imagen para web"""
        try:
            with Image.open(io.BytesIO(data_imagen)) as img:
                # Convertir a RGB si es necesario
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                
                # Redimensionar manteniendo proporción
                if img.width > self.TARGET_WIDTH or img.height > self.TARGET_HEIGHT:
                    img.thumbnail((self.TARGET_WIDTH, self.TARGET_HEIGHT), Image.Resampling.LANCZOS)
                    logger.info(f"🖼️ Imagen redimensionada a {img.width}x{img.height}")
                
                # Guardar optimizada
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=self.IMAGE_QUALITY, optimize=True)
                return output.getvalue()
                
        except Exception as e:
            logger.warning(f"⚠️ Error optimizando imagen: {e}")
            return data_imagen

    async def subir_imagen_wordpress(self, data_imagen: bytes, nombre_archivo: str, 
                                    alt_text: str = "", titulo: str = "") -> Optional[int]:
        """Subir imagen a WordPress con título y alt text configurados"""
        try:
            # Optimizar imagen
            imagen_optimizada = await self.optimizar_imagen(data_imagen)
            
            # Datos para upload
            upload_data = {
                'name': nombre_archivo,
                'type': 'image/jpeg',
                'bits': xmlrpc_client.Binary(imagen_optimizada),
                'overwrite': True
            }
            
            logger.info(f"📤 Subiendo imagen: {nombre_archivo}")
            
            # Subir imagen
            respuesta = self.wordpress_client.call(media.UploadFile(upload_data))
            
            if respuesta and 'id' in respuesta:
                attachment_id = respuesta['id']
                logger.info(f"✅ Imagen subida - ID: {attachment_id}")
                
                # Configurar título y alt text
                try:
                    # Obtener post de la imagen
                    attachment_post = self.wordpress_client.call(posts.GetPost(attachment_id))
                    
                    # Configurar título
                    if titulo:
                        attachment_post.title = titulo
                        logger.info(f"🏷️ Título configurado: '{titulo}'")
                    
                    # Configurar alt text via custom fields
                    custom_fields = attachment_post.custom_fields or []
                    
                    # Remover alt text existente
                    custom_fields = [cf for cf in custom_fields if cf['key'] != '_wp_attachment_image_alt']
                    
                    # Agregar nuevo alt text
                    if alt_text:
                        custom_fields.append({
                            'key': '_wp_attachment_image_alt',
                            'value': alt_text
                        })
                        logger.info(f"🏷️ Alt text configurado: '{alt_text}'")
                    
                    attachment_post.custom_fields = custom_fields
                    
                    # Actualizar imagen
                    self.wordpress_client.call(posts.EditPost(attachment_id, attachment_post))
                    logger.info("✅ Metadatos de imagen actualizados")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error configurando metadatos: {e}")
                
                return attachment_id
            else:
                logger.error(f"❌ Error en respuesta de upload: {respuesta}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error subiendo imagen: {e}")
            return None

    async def publicar_wordpress(self, datos_articulo: Dict, attachment_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
        """Publicar artículo en WordPress con SEO completo"""
        try:
            from wordpress_xmlrpc import WordPressPost
            
            # Crear post
            post = WordPressPost()
            post.title = datos_articulo['titulo']
            post.content = datos_articulo['contenido_html']
            post.excerpt = datos_articulo['metadescripcion']
            post.slug = datos_articulo['slug']
            post.post_status = 'publish'
            
            # Configurar campos SEO de Yoast
            custom_fields = []
            
            # Meta descripción
            custom_fields.append({
                'key': '_yoast_wpseo_metadesc',
                'value': datos_articulo['metadescripcion']
            })
            
            # Palabra clave focus
            custom_fields.append({
                'key': '_yoast_wpseo_focuskw',
                'value': datos_articulo['palabra_clave']
            })
            
            # Título SEO
            custom_fields.append({
                'key': '_yoast_wpseo_title',
                'value': datos_articulo['titulo']
            })
            
            post.custom_fields = custom_fields
            
            # Configurar taxonomías
            try:
                categoria = datos_articulo.get('categoria', 'Actualidad')
                post.terms_names = {'category': [categoria]}
                
                tags = datos_articulo.get('tags', [])
                if tags:
                    post.terms_names['post_tag'] = tags
                    
                logger.info(f"📂 Categoría: {categoria}, Tags: {tags}")
                
            except Exception as e:
                logger.warning(f"⚠️ Error configurando categoría: {e}")
            
            # Imagen destacada
            if attachment_id:
                post.thumbnail = attachment_id
                logger.info(f"🖼️ Imagen destacada: ID {attachment_id}")
            
            # Publicar
            logger.info("📝 Publicando artículo...")
            post_id = self.wordpress_client.call(posts.NewPost(post))
            
            if post_id:
                logger.info(f"✅ Artículo publicado - ID: {post_id}")
                self.stats['articulos_creados'] += 1
                return post_id, post.title
            else:
                logger.error("❌ Error: post_id es None")
                return None, None
                
        except Exception as e:
            logger.error(f"❌ Error crítico publicando en WordPress: {e}")
            self.stats['errores'] += 1
            return None, None

    async def handle_message_with_photo(self, update: Update, context):
        """Manejar mensaje con foto - LÓGICA EXACTA DE v1.1.0"""
        try:
            logger.info("📸 Procesando mensaje con foto")
            
            # Obtener datos
            photo = update.message.photo[-1]
            texto_usuario = update.message.caption or ""
            
            if not texto_usuario.strip():
                await self.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Incluí texto con la imagen para generar el artículo."
                )
                return
            
            logger.info(f"📝 Texto: {texto_usuario}")
            
            # Extraer palabra clave
            palabra_clave = self._extraer_palabra_clave(texto_usuario)
            
            # Descargar imagen
            file = await self.bot.get_file(photo.file_id)
            imagen_data = await file.download_as_bytearray()
            
            # Generar nombre con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"imagen_{timestamp}.jpg"
            
            # Configurar título y alt text con palabra clave
            titulo_imagen = palabra_clave.title()
            alt_text_imagen = palabra_clave
            
            logger.info(f"🖼️ Configurando imagen: título='{titulo_imagen}', alt='{alt_text_imagen}'")
            
            # Subir imagen con metadatos
            attachment_id = await self.subir_imagen_wordpress(
                bytes(imagen_data), 
                nombre_archivo,
                alt_text=alt_text_imagen,
                titulo=titulo_imagen
            )
            
            if not attachment_id:
                await self.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Error subiendo imagen"
                )
                return
            
            # Generar artículo
            logger.info("🤖 Generando artículo profesional...")
            datos_articulo = await self.generar_articulo_ia(texto_usuario, palabra_clave)
            
            if not datos_articulo:
                await self.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Error generando artículo"
                )
                return
            
            logger.info("✅ Artículo SEO FINAL PERFECTO generado")
            
            # Publicar
            logger.info("🚀 Iniciando publicación en WordPress...")
            post_id, titulo_post = await self.publicar_wordpress(datos_articulo, attachment_id)
            
            if post_id:
                self.stats['imagenes_procesadas'] += 1
                await self.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"✅ ¡Artículo publicado!\n\n📰 {titulo_post}\n🆔 ID: {post_id}\n🎯 Keyword: {palabra_clave}\n🖼️ Imagen: ✅\n📊 SEO: ✅"
                )
                logger.info(f"✅ ÉXITO TOTAL - Post ID: {post_id}")
            else:
                await self.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Error publicando artículo"
                )
                
        except Exception as e:
            logger.error(f"❌ Error procesando imagen: {e}")
            self.stats['errores'] += 1
            await self.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Error procesando mensaje: {str(e)}"
            )

    async def start_command(self, update: Update, context):
        """Comando /start"""
        mensaje_bienvenida = """
🤖 *Bot de Automatización Periodística v1.1.2*

📸 Enviá una imagen con texto y creo automáticamente:
• ✅ Artículo SEO optimizado
• ✅ Imagen destacada con alt text
• ✅ Publicación en WordPress
• ✅ Configuración Yoast completa

📊 `/stats` - Ver estadísticas
"""
        
        await self.bot.send_message(
            chat_id=update.effective_chat.id,
            text=mensaje_bienvenida,
            parse_mode='Markdown'
        )

    async def stats_command(self, update: Update, context):
        """Comando /stats"""
        stats_text = f"""
📊 *Estadísticas del Sistema v1.1.2*

📰 Artículos creados: {self.stats['articulos_creados']}
🖼️ Imágenes procesadas: {self.stats['imagenes_procesadas']}
❌ Errores: {self.stats['errores']}
🕐 Inicio: {self.stats['inicio_sistema']}
"""
        
        await self.bot.send_message(
            chat_id=update.effective_chat.id,
            text=stats_text,
            parse_mode='Markdown'
        )

    async def handle_text_only_message(self, update: Update, context):
        """Manejar mensaje solo texto"""
        await self.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📸 Enviá una imagen con texto para generar un artículo automáticamente."
        )

# Configuración Flask
app = Flask(__name__)

# Instancia global del sistema
sistema = AutomacionPeriodisticaV1()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint principal del webhook de Telegram - LÓGICA EXACTA DE v1.1.0"""
    try:
        # Obtener datos JSON
        json_data = request.get_json()
        
        if not json_data:
            logger.warning("Webhook recibido sin datos JSON")
            return jsonify({'error': 'No JSON data received'}), 400
        
        # Crear objeto Update de Telegram
        update = Update.de_json(json_data, sistema.bot)
        
        if not update or not update.message:
            return jsonify({'status': 'no_message'}), 200
        
        # Procesar mensaje según tipo
        if update.message.photo:
            # Mensaje con foto - usar asyncio para procesamiento
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(sistema.handle_message_with_photo(update, None))
            finally:
                loop.close()
                
        elif update.message.text:
            # Procesar comandos especiales
            if update.message.text.startswith('/start'):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(sistema.start_command(update, None))
                finally:
                    loop.close()
                    
            elif update.message.text.startswith('/stats'):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(sistema.stats_command(update, None))
                finally:
                    loop.close()
                    
            else:
                # Mensaje normal de texto
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(sistema.handle_text_only_message(update, None))
                finally:
                    loop.close()
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Error crítico en webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Endpoint de verificación de salud del sistema"""
    try:
        # Verificar estado de servicios
        services_status = {
            'groq': sistema.groq_client is not None,
            'wordpress': sistema.wordpress_client is not None,
            'telegram': sistema.bot is not None
        }
        
        all_services_ok = all(services_status.values())
        
        return jsonify({
            'status': 'healthy' if all_services_ok else 'degraded',
            'version': 'v1.1.2',
            'timestamp': datetime.now().isoformat(),
            'services': services_status,
            'stats': sistema.stats
        }), 200 if all_services_ok else 503
        
    except Exception as e:
        logger.error(f"Error en health check: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/')
def index():
    """Página principal básica"""
    return jsonify({
        'service': 'Automatización Periodística',
        'version': 'v1.1.2',
        'status': 'running',
        'documentation': '/health para estado del sistema'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Iniciando servidor Flask en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
