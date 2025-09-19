#!/usr/bin/env python3
"""
Sistema mejorado para automatización periodística
Incluye validaciones adicionales, logging mejorado y configuraciones flexibles
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
from dotenv import load_dotenv
import time
from functools import wraps
from flask import Flask, request, jsonify
import threading

# Cargar variables de entorno
load_dotenv()

# Configuración de logging mejorada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramToWordPressBot:
    """Bot mejorado con validaciones y características adicionales"""
    
    def __init__(self):
        # Configuraciones desde variables de entorno
        self.TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.GROQ_API_KEY = os.getenv('GROQ_API_KEY')
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        self.WORDPRESS_URL = os.getenv('WORDPRESS_URL')
        self.WORDPRESS_USERNAME = os.getenv('WORDPRESS_USERNAME')
        self.WORDPRESS_PASSWORD = os.getenv('WORDPRESS_PASSWORD')
        
        # Usuarios autorizados (opcional)
        authorized_ids = os.getenv('AUTHORIZED_USER_IDS', '')
        self.AUTHORIZED_USERS = [int(id.strip()) for id in authorized_ids.split(',') if id.strip()]
        
        # Configuración de imagen
        self.TARGET_WIDTH = int(os.getenv('IMAGE_WIDTH', 1200))
        self.TARGET_HEIGHT = int(os.getenv('IMAGE_HEIGHT', 675))
        self.IMAGE_QUALITY = int(os.getenv('IMAGE_QUALITY', 85))
        
        # Inicializar clientes
        self.groq_client = None
        self.openai_client = None
        self.wp_client = None
        self.bot = None
        
        # Estadísticas simples
        self.stats = {
            'messages_processed': 0,
            'articles_created': 0,
            'errors': 0,
            'start_time': datetime.now()
        }
        
        self._initialize_clients()
        self._validate_configuration()
    
    def _initialize_clients(self):
        """Inicializa todos los clientes necesarios"""
        try:
            if self.GROQ_API_KEY:
                self.groq_client = Groq(api_key=self.GROQ_API_KEY)
                logger.info("✅ Cliente Groq inicializado")
            
            if self.OPENAI_API_KEY and OPENAI_AVAILABLE:
                self.openai_client = openai.OpenAI(api_key=self.OPENAI_API_KEY)
                logger.info("✅ Cliente OpenAI inicializado")
            elif self.OPENAI_API_KEY and not OPENAI_AVAILABLE:
                logger.warning("⚠️  API Key de OpenAI configurada pero librería no instalada. Transcripción de audio deshabilitada.")
            
            if self.TELEGRAM_TOKEN:
                self.bot = Bot(token=self.TELEGRAM_TOKEN)
                logger.info("✅ Cliente Telegram inicializado")
            
            if all([self.WORDPRESS_URL, self.WORDPRESS_USERNAME, self.WORDPRESS_PASSWORD]):
                self.wp_client = Client(
                    self.WORDPRESS_URL,
                    self.WORDPRESS_USERNAME,
                    self.WORDPRESS_PASSWORD
                )
                # Probar conexión
                try:
                    self.wp_client.call(posts.GetPosts({'number': 1}))
                    logger.info("✅ Conexión a WordPress exitosa")
                except Exception as e:
                    logger.error(f"❌ Error conectando a WordPress: {e}")
                    self.wp_client = None
            
        except Exception as e:
            logger.error(f"Error inicializando clientes: {e}")
    
    def _validate_configuration(self):
        """Valida que la configuración sea correcta"""
        issues = []
        
        if not self.TELEGRAM_TOKEN:
            issues.append("TELEGRAM_BOT_TOKEN no configurado")
        
        if not self.groq_client:
            issues.append("GROQ_API_KEY no configurado o inválido")
        
        if not self.wp_client:
            issues.append("Configuración de WordPress incompleta o inválida")
        
        if issues:
            logger.error("❌ Problemas de configuración:")
            for issue in issues:
                logger.error(f"  - {issue}")
            logger.error("Revisa el archivo .env")
        else:
            logger.info("✅ Configuración validada correctamente")
    
    def rate_limit(max_calls=30, period=60):
        """Decorador para limitar velocidad de procesamiento"""
        def decorator(func):
            calls = []
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                now = time.time()
                calls_in_period = [call for call in calls if now - call < period]
                
                if len(calls_in_period) >= max_calls:
                    sleep_time = period - (now - calls_in_period[0])
                    logger.warning(f"Rate limit alcanzado. Esperando {sleep_time:.1f}s")
                    await asyncio.sleep(sleep_time)
                
                calls.append(now)
                calls[:] = calls[-max_calls:]  # Mantener solo las últimas llamadas
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start del bot"""
        welcome_message = """
🤖 **Bot de Automatización Periodística**

📝 **Cómo usar:**
1. Envía una imagen con texto descriptivo
2. O envía imagen + nota de voz
3. El bot creará un artículo automáticamente

⚙️ **Comandos:**
/start - Este mensaje
/stats - Estadísticas del sistema
/help - Ayuda detallada

📊 **Estado:** Sistema activo ✅
        """
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stats para ver estadísticas"""
        uptime = datetime.now() - self.stats['start_time']
        
        stats_message = f"""
📊 **Estadísticas del Sistema**

⏱️ **Tiempo activo:** {uptime.days}d {uptime.seconds//3600}h {(uptime.seconds%3600)//60}m
📨 **Mensajes procesados:** {self.stats['messages_processed']}
📰 **Artículos creados:** {self.stats['articles_created']}
❌ **Errores:** {self.stats['errors']}
📈 **Tasa de éxito:** {(self.stats['articles_created']/max(1,self.stats['messages_processed'])*100):.1f}%

🔧 **Estado servicios:**
{'✅' if self.groq_client else '❌'} Groq AI
{'✅' if self.wp_client else '❌'} WordPress
{'✅' if self.openai_client else '❌'} OpenAI (Audio)
        """
        await update.message.reply_text(stats_message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help con ayuda detallada"""
        help_message = """
📖 **Guía de Uso Detallada**

**🎯 Formatos aceptados:**
• Imagen + texto en caption
• Imagen + nota de voz
• Imagen + texto + nota de voz

**📝 Ejemplo de mensaje:**
[Adjuntar imagen]
Caption: "Manifestación en plaza central. 200 personas aprox. Ambiente pacífico. Reclaman por salarios."

**🤖 El bot procesará:**
✅ Análisis con IA
✅ Artículo de 500+ palabras  
✅ Optimización SEO
✅ Imagen redimensionada
✅ Publicación en WordPress

**⚠️ Consejos:**
• Sé descriptivo en el texto
• Incluye detalles relevantes
• La imagen será redimensionada automáticamente
• El artículo se publica como borrador para revisión

**🆘 Soporte:**
Si hay problemas, contacta al administrador del sistema.
        """
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    def _is_authorized_user(self, user_id: int) -> bool:
        """Verifica si el usuario está autorizado"""
        if not self.AUTHORIZED_USERS:
            return True  # Si no hay lista, todos están autorizados
        return user_id in self.AUTHORIZED_USERS
    
    async def process_telegram_message(self, update: Update):
        """Procesa mensajes entrantes de Telegram"""
        try:
            message = update.message
            user_id = message.from_user.id
            username = message.from_user.username or message.from_user.first_name
            
            # Verificar autorización
            if not self._is_authorized_user(user_id):
                await message.reply_text("❌ No estás autorizado para usar este bot.")
                return
            
            # Actualizar estadísticas
            self.stats['messages_processed'] += 1
            
            # Verificar formato válido
            if not self._is_valid_journalist_message(message):
                await message.reply_text(
                    "❌ **Formato no válido**\n\n"
                    "Envía una imagen con texto o nota de voz.\n"
                    "Usa /help para ver ejemplos.",
                    parse_mode='Markdown'
                )
                return
            
            # Mensaje de inicio de procesamiento
            processing_msg = await message.reply_text(
                "📝 **Procesando tu crónica...**\n"
                "⏳ Esto puede tomar 30-60 segundos",
                parse_mode='Markdown'
            )
            
            # Extraer contenido
            content_data = await self._extract_content_from_message(message)
            if not content_data:
                await processing_msg.edit_text("❌ Error al extraer contenido del mensaje.")
                self.stats['errors'] += 1
                return
            
            # Actualizar estado
            await processing_msg.edit_text(
                "📝 **Procesando tu crónica...**\n"
                "🤖 Generando artículo con IA...",
                parse_mode='Markdown'
            )
            
            # Generar artículo
            article_data = await self._generate_article_with_ai(content_data)
            if not article_data:
                await processing_msg.edit_text("❌ Error al generar artículo con IA.")
                self.stats['errors'] += 1
                return
            
            # Actualizar estado
            await processing_msg.edit_text(
                "📝 **Procesando tu crónica...**\n"
                "🖼️ Optimizando imagen...",
                parse_mode='Markdown'
            )
            
            # Procesar imagen
            image_data = await self._process_image(content_data['image_data'])
            if not image_data:
                await processing_msg.edit_text("❌ Error al procesar imagen.")
                self.stats['errors'] += 1
                return
            
            # Actualizar estado
            await processing_msg.edit_text(
                "📝 **Procesando tu crónica...**\n"
                "📰 Publicando en WordPress...",
                parse_mode='Markdown'
            )
            
            # Publicar en WordPress
            result = await self._publish_to_wordpress(article_data, image_data)
            
            if result['success']:
                success_message = f"""
✅ **¡Artículo creado exitosamente!**

📰 **Título:** {article_data['title']}
🔗 **URL:** {result['url']}
📊 **Palabras:** {len(article_data['content'].split())}
⭐ **Estado:** Borrador (para revisión)

El artículo está listo para su revisión y publicación.
                """
                await processing_msg.edit_text(success_message, parse_mode='Markdown')
                self.stats['articles_created'] += 1
                
                # Log para administración
                logger.info(f"✅ Artículo creado por {username} (ID: {user_id}): {article_data['title']}")
                
            else:
                await processing_msg.edit_text(f"❌ Error al publicar: {result['error']}")
                self.stats['errors'] += 1
                
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            self.stats['errors'] += 1
            try:
                await message.reply_text("❌ Error interno del sistema. Intenta nuevamente.")
            except:
                pass
    
    def _is_valid_journalist_message(self, message: Message) -> bool:
        """Verifica si el mensaje tiene formato válido para procesamiento periodístico"""
        has_image = bool(message.photo)
        has_text = bool(message.caption and message.caption.strip())
        has_voice = bool(message.voice and self.openai_client)
        
        # Debe tener imagen y al menos texto o voz
        return has_image and (has_text or has_voice)
    
    async def _extract_content_from_message(self, message: Message) -> Optional[Dict]:
        """Extrae y procesa el contenido del mensaje de Telegram"""
        try:
            # Obtener imagen
            if not message.photo:
                return None
            
            photo = message.photo[-1]  # La imagen de mayor resolución
            photo_file = await photo.get_file()
            
            # Descargar imagen
            async with aiohttp.ClientSession() as session:
                async with session.get(photo_file.file_path) as response:
                    if response.status == 200:
                        image_data = await response.read()
                    else:
                        return None
            
            # Extraer texto
            text_content = message.caption if message.caption else ""
            
            # Procesar audio si existe
            voice_transcript = ""
            if message.voice and self.openai_client:
                try:
                    voice_transcript = await self._transcribe_voice_message(message.voice)
                    if voice_transcript:
                        logger.info("✅ Audio transcrito exitosamente")
                except Exception as e:
                    logger.warning(f"Error transcribiendo audio: {e}")
            
            return {
                'image_data': image_data,
                'text_content': text_content,
                'voice_transcript': voice_transcript,
                'user_info': {
                    'id': message.from_user.id,
                    'username': message.from_user.username or message.from_user.first_name,
                    'timestamp': datetime.now()
                }
            }
            
        except Exception as e:
            logger.error(f"Error extrayendo contenido: {e}")
            return None
    
    async def _transcribe_voice_message(self, voice_message) -> Optional[str]:
        """Transcribe audio usando Whisper de OpenAI"""
        try:
            if not self.openai_client:
                return None
            
            # Descargar archivo de voz
            voice_file = await voice_message.get_file()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(voice_file.file_path) as response:
                    if response.status == 200:
                        voice_data = await response.read()
                    else:
                        return None
            
            # Crear archivo temporal en memoria
            voice_file_obj = io.BytesIO(voice_data)
            voice_file_obj.name = "voice_message.ogg"
            
            # Transcribir con OpenAI Whisper
            transcript = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=voice_file_obj,
                language="es"  # Español por defecto
            )
            
            return transcript.text if transcript.text else None
            
        except Exception as e:
            logger.error(f"Error transcribiendo audio: {e}")
            return None
    
    async def _generate_article_with_ai(self, content_data: Dict) -> Optional[Dict]:
        """Genera artículo periodístico usando IA"""
        try:
            if not self.groq_client:
                return None
            
            # Combinar todo el contenido disponible
            combined_content = []
            
            if content_data['text_content']:
                combined_content.append(f"Descripción: {content_data['text_content']}")
            
            if content_data['voice_transcript']:
                combined_content.append(f"Transcripción de audio: {content_data['voice_transcript']}")
            
            source_content = "\n".join(combined_content)
            
            if not source_content.strip():
                return None
            
            # Prompt mejorado para generación de artículo
            prompt = f"""
Eres un periodista profesional especializado en crear artículos informativos de alta calidad.

CONTENIDO FUENTE:
{source_content}

INSTRUCCIONES:
1. Crea un artículo periodístico completo de mínimo 500 palabras
2. Usa un estilo informativo, claro y profesional
3. Estructura con titular, subtítulos y párrafos bien organizados
4. Incluye contexto relevante cuando sea posible
5. Mantén objetividad periodística
6. Optimiza para SEO con palabras clave naturales

FORMATO REQUERIDO:
- Título principal (H1)
- 3-4 subtítulos (H2) 
- Párrafos de 2-3 oraciones
- Conclusión que cierre el tema
- Meta descripción (150 caracteres max)

RESPONDE EN FORMATO JSON:
{{
    "title": "Título principal del artículo",
    "meta_description": "Descripción para SEO (máx 150 caracteres)",
    "content": "Contenido completo del artículo en HTML con etiquetas H2, H3, p, etc.",
    "tags": ["tag1", "tag2", "tag3"],
    "category": "Categoría principal"
}}
            """
            
            # Llamada a Groq con modelo actualizado
            response = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Eres un periodista profesional experto en crear artículos informativos de calidad."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.1-8b-instant",  # Modelo actualizado que está disponible
                temperature=0.7,
                max_tokens=2048
            )
            
            # Procesar respuesta
            ai_response = response.choices[0].message.content
            
            # Intentar parsear JSON
            try:
                article_data = json.loads(ai_response)
                
                # Validar campos requeridos
                required_fields = ['title', 'content', 'meta_description']
                if all(field in article_data for field in required_fields):
                    return article_data
                else:
                    logger.error("Respuesta de IA incompleta")
                    return None
                    
            except json.JSONDecodeError:
                logger.error("Error parsing JSON de respuesta IA")
                return None
            
        except Exception as e:
            logger.error(f"Error generando artículo con IA: {e}")
            return None
    
    async def _process_image(self, image_data: bytes) -> Optional[Dict]:
        """Procesa y optimiza la imagen"""
        try:
            # Abrir imagen con PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Convertir a RGB si es necesario
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')
            
            # Redimensionar manteniendo aspecto
            image.thumbnail((self.TARGET_WIDTH, self.TARGET_HEIGHT), Image.Resampling.LANCZOS)
            
            # Si es más pequeña que el target, crear nueva con el tamaño exacto
            if image.size != (self.TARGET_WIDTH, self.TARGET_HEIGHT):
                new_image = Image.new('RGB', (self.TARGET_WIDTH, self.TARGET_HEIGHT), (255, 255, 255))
                
                # Centrar la imagen
                x = (self.TARGET_WIDTH - image.width) // 2
                y = (self.TARGET_HEIGHT - image.height) // 2
                new_image.paste(image, (x, y))
                image = new_image
            
            # Guardar imagen optimizada
            output_buffer = io.BytesIO()
            image.save(output_buffer, format='JPEG', quality=self.IMAGE_QUALITY, optimize=True)
            processed_image_data = output_buffer.getvalue()
            
            return {
                'data': processed_image_data,
                'format': 'JPEG',
                'size': len(processed_image_data),
                'dimensions': (self.TARGET_WIDTH, self.TARGET_HEIGHT)
            }
            
        except Exception as e:
            logger.error(f"Error procesando imagen: {e}")
            return None
    
    async def _publish_to_wordpress(self, article_data: Dict, image_data: Dict) -> Dict:
        """Publica el artículo en WordPress"""
        try:
            if not self.wp_client:
                return {'success': False, 'error': 'Cliente WordPress no disponible'}
            
            # Subir imagen primero
            image_filename = f"article_image_{int(datetime.now().timestamp())}.jpg"
            
            # Preparar datos de imagen para WordPress
            image_bits = xmlrpc_client.Binary(image_data['data'])
            image_struct = {
                'name': image_filename,
                'type': 'image/jpeg',
                'bits': image_bits,
                'overwrite': True
            }
            
            # Subir imagen
            try:
                uploaded_image = self.wp_client.call(media.UploadFile(image_struct))
                featured_image_id = uploaded_image['id']
                logger.info(f"✅ Imagen subida a WordPress: {uploaded_image['url']}")
            except Exception as e:
                logger.error(f"Error subiendo imagen: {e}")
                featured_image_id = None
            
            # Crear post
            post = wordpress_xmlrpc.WordPressPost()
            post.title = article_data['title']
            post.content = article_data['content']
            post.post_status = 'draft'  # Publicar como borrador
            post.excerpt = article_data.get('meta_description', '')
            
            # Asignar imagen destacada si se subió correctamente
            if featured_image_id:
                post.thumbnail = featured_image_id
            
            # Asignar categorías y tags si están disponibles
            if 'category' in article_data and article_data['category']:
                post.terms_names = {
                    'category': [article_data['category']]
                }
            
            if 'tags' in article_data and article_data['tags']:
                post.terms_names = post.terms_names or {}
                post.terms_names['post_tag'] = article_data['tags']
            
            # Publicar post
            post_id = self.wp_client.call(posts.NewPost(post))
            
            # Obtener URL del post
            published_post = self.wp_client.call(posts.GetPost(post_id))
            post_url = published_post.link
            
            logger.info(f"✅ Artículo publicado en WordPress: {post_url}")
            
            return {
                'success': True,
                'post_id': post_id,
                'url': post_url,
                'featured_image_id': featured_image_id
            }
            
        except Exception as e:
            logger.error(f"Error publicando en WordPress: {e}")
            return {'success': False, 'error': str(e)}

# Instancia global del bot
bot_instance = None

def create_flask_app():
    """Crea y configura la aplicación Flask"""
    app = Flask(__name__)
    
    @app.route('/')
    def health_check():
        global bot_instance
        if bot_instance:
            return {
                'status': 'healthy',
                'service': 'telegram-wordpress-bot',
                'uptime_seconds': (datetime.now() - bot_instance.stats['start_time']).total_seconds(),
                'stats': bot_instance.stats
            }
        return {'status': 'starting'}
    
    @app.route('/webhook', methods=['POST'])
    def webhook():
        """Endpoint para webhook de Telegram"""
        global bot_instance
        try:
            if not bot_instance or not bot_instance.bot:
                logger.error("Bot no inicializado")
                return jsonify({'error': 'Bot not initialized'}), 500
            
            # Obtener datos del webhook
            update_data = request.get_json()
            
            if not update_data:
                logger.warning("Webhook recibido sin datos")
                return jsonify({'status': 'no_data'}), 400
            
            # Crear objeto Update de Telegram
            update = Update.de_json(update_data, bot_instance.bot)
            
            # Procesar en background sin bloquear la respuesta
            if update.message:
                logger.info(f"Mensaje recibido de {update.message.from_user.first_name}")
                
                # Ejecutar procesamiento asíncrono
                def run_async_processing():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # Determinar tipo de procesamiento
                        message = update.message
                        if message.text and message.text.startswith('/'):
                            # Es un comando
                            if message.text == '/start':
                                loop.run_until_complete(bot_instance.start_command(update, None))
                            elif message.text == '/help':
                                loop.run_until_complete(bot_instance.help_command(update, None))
                            elif message.text == '/stats':
                                loop.run_until_complete(bot_instance.stats_command(update, None))
                        else:
                            # Es un mensaje regular
                            loop.run_until_complete(bot_instance.process_telegram_message(update))
                        
                        loop.close()
                    except Exception as e:
                        logger.error(f"Error procesando mensaje: {e}")
                
                # Ejecutar en hilo separado
                thread = threading.Thread(target=run_async_processing)
                thread.daemon = True
                thread.start()
                
            return jsonify({'status': 'ok'}), 200
            
        except Exception as e:
            logger.error(f"Error en webhook: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/stats')
    def get_stats():
        global bot_instance
        if bot_instance:
            return jsonify(bot_instance.stats)
        return jsonify({'error': 'Bot not initialized'})
    
    return app

def main():
    """Función principal del bot"""
    global bot_instance
    
    try:
        # Inicializar bot
        bot_instance = TelegramToWordPressBot()
        
        # Verificar configuración crítica
        if not bot_instance.TELEGRAM_TOKEN:
            logger.error("❌ TELEGRAM_BOT_TOKEN no configurado")
            return
        
        if not bot_instance.groq_client:
            logger.error("❌ GROQ_API_KEY no configurado")
            return
        
        if not bot_instance.wp_client:
            logger.error("❌ Configuración de WordPress incompleta")
            return
        
        logger.info("🚀 Bot inicializado correctamente")
        logger.info(f"📊 Configuración activa:")
        logger.info(f"  - Groq AI: {'✅' if bot_instance.groq_client else '❌'}")
        logger.info(f"  - OpenAI: {'✅' if bot_instance.openai_client else '❌'}")
        logger.info(f"  - WordPress: {'✅' if bot_instance.wp_client else '❌'}")
        logger.info(f"  - Usuarios autorizados: {len(bot_instance.AUTHORIZED_USERS) if bot_instance.AUTHORIZED_USERS else 'Todos'}")
        
        # Crear y ejecutar aplicación Flask
        app = create_flask_app()
        
        port = int(os.getenv('PORT', 8080))
        logger.info(f"✅ Servidor iniciado en puerto {port}")
        logger.info("🔗 Webhook URL: https://periodismo-bot.onrender.com/webhook")
        
        # Ejecutar Flask
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
        
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        raise

if __name__ == "__main__":
    main()
