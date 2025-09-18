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
import openai
from groq import Groq
import requests
from telegram import Update, Message
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
import wordpress_xmlrpc
from wordpress_xmlrpc import Client
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client
from dotenv import load_dotenv
import time
from functools import wraps

# Cargar variables de entorno
load_dotenv()

# Configuración de logging mejorada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
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
            
            if self.OPENAI_API_KEY:
                self.openai_client = openai.OpenAI(api_key=self.OPENAI_API_KEY)
                logger.info("✅ Cliente OpenAI inicializado")
            
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
    
    @rate_limit(max_calls=10, period=60)
    async def process_telegram_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesa mensajes entrantes de Telegram con rate limiting"""
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
            processed_image = await self._process_image(content_data.get('image_data'))
            
            # Actualizar estado
            await processing_msg.edit_text(
                "📝 **Procesando tu crónica...**\n"
                "📤 Publicando en WordPress...",
                parse_mode='Markdown'
            )
            
            # Publicar en WordPress
            post_result = await self._publish_to_wordpress(article_data, processed_image)
            
            if post_result:
                # Actualizar estadísticas
                self.stats['articles_created'] += 1
                
                # Mensaje de éxito
                success_message = f"""
✅ **¡Artículo creado exitosamente!**

📰 **Título:** {article_data['title'][:50]}{'...' if len(article_data['title']) > 50 else ''}
🔗 **Estado:** {post_result['status'].title()}
📊 **Palabras:** {len(article_data['content'].split())}
👤 **Periodista:** {username}
🕐 **Hora:** {datetime.now().strftime('%H:%M')}

{'📝 El artículo está en borradores para revisión.' if post_result['status'] == 'draft' else '🚀 Artículo publicado directamente.'}
                """
                await processing_msg.edit_text(success_message, parse_mode='Markdown')
                
                logger.info(f"Artículo creado exitosamente por {username} (ID: {user_id})")
                
            else:
                await processing_msg.edit_text("❌ Error al publicar en WordPress.")
                self.stats['errors'] += 1
                
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            self.stats['errors'] += 1
            await message.reply_text("❌ Error interno del sistema. Intenta nuevamente.")
    
    def _is_valid_journalist_message(self, message: Message) -> bool:
        """Valida formato del mensaje de periodista"""
        has_photo = bool(message.photo)
        has_text = bool(message.caption or message.text)
        has_audio = bool(message.voice or message.audio)
        
        return has_photo and (has_text or has_audio)
    
    async def _extract_content_from_message(self, message: Message) -> Optional[Dict]:
        """Extrae y procesa contenido del mensaje"""
        try:
            content = {}
            
            # Extraer texto
            if message.caption:
                content['text'] = message.caption.strip()
            elif message.text:
                content['text'] = message.text.strip()
            else:
                content['text'] = ''
            
            # Procesar audio si existe
            if message.voice and self.openai_client:
                try:
                    audio_text = await self._transcribe_audio(message.voice)
                    if audio_text:
                        content['text'] += f"\n\nTranscripción de audio: {audio_text}"
                        logger.info("Audio transcrito exitosamente")
                except Exception as e:
                    logger.warning(f"Error transcribiendo audio: {e}")
            
            # Extraer imagen (mayor resolución disponible)
            if message.photo:
                photo = message.photo[-1]
                file = await message.bot.get_file(photo.file_id)
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(file.file_path) as response:
                        if response.status == 200:
                            content['image_data'] = await response.read()
                            content['image_format'] = 'JPEG'
                        else:
                            logger.error(f"Error descargando imagen: HTTP {response.status}")
                            return None
            
            # Metadatos
            content.update({
                'timestamp': datetime.now().isoformat(),
                'user_id': message.from_user.id,
                'username': message.from_user.username or message.from_user.first_name,
                'chat_id': message.chat_id,
                'message_id': message.message_id
            })
            
            # Validar contenido mínimo
            if len(content.get('text', '')) < 10:
                logger.warning("Texto muy corto para generar artículo")
                return None
            
            return content
            
        except Exception as e:
            logger.error(f"Error extrayendo contenido: {e}")
            return None
    
    async def _transcribe_audio(self, voice) -> Optional[str]:
        """Transcribe audio usando Whisper de OpenAI"""
        try:
            if not self.openai_client:
                return None
            
            # Obtener archivo de audio
            file = await voice.get_file()
            
            # Descargar audio
            async with aiohttp.ClientSession() as session:
                async with session.get(file.file_path) as response:
                    audio_data = await response.read()
            
            # Crear archivo temporal
            temp_audio_path = f"/tmp/voice_{datetime.now().timestamp()}.ogg"
            async with aiofiles.open(temp_audio_path, 'wb') as f:
                await f.write(audio_data)
            
            # Transcribir con Whisper
            with open(temp_audio_path, 'rb') as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="es"  # Español por defecto
                )
            
            # Limpiar archivo temporal
            os.remove(temp_audio_path)
            
            return transcript.text
            
        except Exception as e:
            logger.error(f"Error transcribiendo audio: {e}")
            return None
    
    async def _generate_article_with_ai(self, content_data: Dict) -> Optional[Dict]:
        """Genera artículo periodístico usando Groq"""
        try:
            if not self.groq_client:
                logger.error("Cliente Groq no disponible")
                return None
            
            prompt = self._create_enhanced_prompt(content_data)
            
            completion = self.groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {
                        "role": "system",
                        "content": """Eres un periodista senior especializado en noticias de último momento. 
                        Creas artículos SEO-optimizados siguiendo estándares profesionales.
                        
                        ESPECIFICACIONES TÉCNICAS:
                        - Mínimo 500 palabras
                        - Título H1 atractivo y SEO-friendly
                        - Estructura clara con H2 y H3
                        - Meta descripción 150-160 caracteres
                        - 4 tags relevantes
                        - Alt text descriptivo para imagen
                        
                        ESTILO PERIODÍSTICO:
                        - Pirámide invertida (más importante primero)
                        - Párrafos cortos y claros
                        - Lenguaje objetivo y profesional
                        - Datos específicos cuando estén disponibles
                        
                        RESPONDE ÚNICAMENTE EN JSON con esta estructura exacta:
                        {
                            "title": "Título principal del artículo",
                            "meta_description": "Meta descripción SEO de 150-160 caracteres",
                            "keywords": "palabra, clave, principal",
                            "tags": ["tag1", "tag2", "tag3", "tag4"],
                            "content": "Contenido HTML completo con <h2>, <h3>, <p>, etc.",
                            "excerpt": "Resumen ejecutivo de 2-3 líneas",
                            "alt_text": "Descripción de la imagen para alt text",
                            "category": "Categoría sugerida para WordPress"
                        }"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2500
            )
            
            # Parsear y validar JSON
            response_text = completion.choices[0].message.content.strip()
            
            # Limpiar respuesta si hay texto extra
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            article_data = json.loads(response_text)
            
            # Validaciones
            word_count = len(article_data['content'].split())
            if word_count < 500:
                logger.warning(f"Artículo con solo {word_count} palabras")
            
            # Validar estructura JSON
            required_fields = ['title', 'meta_description', 'keywords', 'tags', 'content', 'excerpt', 'alt_text']
            missing_fields = [field for field in required_fields if field not in article_data]
            if missing_fields:
                logger.error(f"Campos faltantes en respuesta de IA: {missing_fields}")
                return None
            
            logger.info(f"Artículo generado: {word_count} palabras")
            return article_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando JSON de IA: {e}")
            logger.error(f"Respuesta recibida: {response_text[:200]}...")
            return None
        except Exception as e:
            logger.error(f"Error generando artículo: {e}")
            return None
    
    def _create_enhanced_prompt(self, content_data: Dict) -> str:
        """Crea prompt mejorado para la IA"""
        text = content_data.get('text', '')
        username = content_data.get('username', 'Periodista')
        timestamp = content_data.get('timestamp', '')
        
        # Detectar tipo de noticia basado en palabras clave
        news_type = self._detect_news_type(text)
        
        prompt = f"""
CRÓNICA RECIBIDA:
📰 Periodista: {username}
🕐 Fecha/Hora: {timestamp}
📝 Tipo detectado: {news_type}

CONTENIDO ORIGINAL:
{text}

INSTRUCCIONES ESPECÍFICAS:
1. Crear artículo de "último momento" expandiendo la información
2. Mantener los hechos originales como base
3. Agregar contexto periodístico relevante
4. Usar estructura de pirámide invertida
5. Incluir elementos SEO optimizados
6. Longitud: 500-800 palabras óptimas
7. Tono: Profesional e informativo

CONTEXTO ADICIONAL:
- La imagen adjunta documenta la situación descrita
- Priorizar inmediatez y relevancia noticiosa
- Incluir llamadas a la acción cuando sea apropiado

FORMATO DE SALIDA:
JSON válido con todos los campos requeridos.
        """
        
        return prompt
    
    def _detect_news_type(self, text: str) -> str:
        """Detecta tipo de noticia basado en palabras clave"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['accidente', 'choque', 'atropello', 'colisión']):
            return "Accidente de tránsito"
        elif any(word in text_lower for word in ['manifestación', 'protesta', 'marcha', 'concentración']):
            return "Manifestación/Protesta"
        elif any(word in text_lower for word in ['incendio', 'fuego', 'bomberos', 'humo']):
            return "Emergencia/Incendio"
        elif any(word in text_lower for word in ['política', 'alcalde', 'concejo', 'municipio']):
            return "Política local"
        elif any(word in text_lower for word in ['deporte', 'fútbol', 'partido', 'campeonato']):
            return "Deportes"
        else:
            return "Noticia general"
    
    async def _process_image(self, image_data: Optional[bytes]) -> Optional[bytes]:
        """Procesa imagen con optimizaciones avanzadas"""
        try:
            if not image_data:
                return None
            
            image = Image.open(io.BytesIO(image_data))
            
            # Información original
            original_size = len(image_data)
            original_dimensions = image.size
            
            # Convertir a RGB
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Redimensionar manteniendo proporción
            image.thumbnail((self.TARGET_WIDTH, self.TARGET_HEIGHT), Image.Resampling.LANCZOS)
            
            # Crear imagen final con dimensiones exactas
            final_image = Image.new('RGB', (self.TARGET_WIDTH, self.TARGET_HEIGHT), (255, 255, 255))
            
            # Centrar imagen
            x = (self.TARGET_WIDTH - image.width) // 2
            y = (self.TARGET_HEIGHT - image.height) // 2
            final_image.paste(image, (x, y))
            
            # Comprimir con calidad optimizada
            output_buffer = io.BytesIO()
            final_image.save(
                output_buffer,
                format='JPEG',
                quality=self.IMAGE_QUALITY,
                optimize=True,
                progressive=True
            )
            
            processed_data = output_buffer.getvalue()
            processed_size = len(processed_data)
            compression_ratio = (1 - processed_size / original_size) * 100
            
            logger.info(f"Imagen procesada: {original_dimensions} -> {final_image.size}, "
                       f"Tamaño: {original_size//1024}KB -> {processed_size//1024}KB "
                       f"({compression_ratio:.1f}% compresión)")
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Error procesando imagen: {e}")
            return None
    
    async def _publish_to_wordpress(self, article_data: Dict, image_data: Optional[bytes]) -> Optional[Dict]:
        """Publica artículo en WordPress con manejo robusto de errores"""
        try:
            if not self.wp_client:
                logger.error("Cliente WordPress no disponible")
                return None
            
            # Subir imagen
            featured_image_id = None
            if image_data:
                featured_image_id = await self._upload_image_to_wordpress(
                    image_data,
                    article_data.get('alt_text', 'Imagen de noticia')
                )
                if featured_image_id:
                    logger.info(f"Imagen subida con ID: {featured_image_id}")
            
            # Crear post
            post = wordpress_xmlrpc.WordPressPost()
            post.title = article_data['title']
            post.content = article_data['content']
            post.excerpt = article_data.get('excerpt', '')
            post.post_status = 'draft'  # Cambiar a 'publish' para publicar directamente
            
            # SEO y metadatos
            post.custom_fields = [
                {'key': '_yoast_wpseo_metadesc', 'value': article_data.get('meta_description', '')},
                {'key': '_yoast_wpseo_focuskw', 'value': article_data.get('keywords', '')},
                {'key': 'periodista_autor', 'value': article_data.get('author', 'Sistema automático')},
                {'key': 'fecha_cronica', 'value': datetime.now().isoformat()}
            ]
            
            # Tags y categorías
            if 'tags' in article_data and article_data['tags']:
                post.terms_names = {
                    'post_tag': article_data['tags']
                }
            
            # Categoría si está especificada
            if 'category' in article_data and article_data['category']:
                if 'terms_names' not in post.__dict__:
                    post.terms_names = {}
                post.terms_names['category'] = [article_data['category']]
            
            # Imagen destacada
            if featured_image_id:
                post.thumbnail = featured_image_id
            
            # Publicar post
            post_id = self.wp_client.call(posts.NewPost(post))
            
            logger.info(f"Post creado con ID: {post_id}")
            
            return {
                'post_id': post_id,
                'status': 'draft',
                'title': article_data['title'],
                'url': f"{self.WORDPRESS_URL.replace('/xmlrpc.php', '')}/?p={post_id}"
            }
            
        except Exception as e:
            logger.error(f"Error publicando en WordPress: {e}")
            return None
    
    async def _upload_image_to_wordpress(self, image_data: bytes, alt_text: str) -> Optional[int]:
        """Sube imagen a WordPress con retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                filename = f'noticia_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{attempt}.jpg'
                
                data = {
                    'name': filename,
                    'type': 'image/jpeg',
                    'bits': xmlrpc_client.Binary(image_data)
                }
                
                response = self.wp_client.call(media.UploadFile(data))
                
                if response and 'id' in response:
                    media_id = response['id']
                    
                    # Actualizar alt text
                    try:
                        media_item = self.wp_client.call(media.GetMediaItem(media_id))
                        media_item.description = alt_text
                        self.wp_client.call(media.EditMediaItem(media_id, media_item))
                    except Exception as e:
                        logger.warning(f"No se pudo actualizar alt text: {e}")
                    
                    return media_id
                
            except Exception as e:
                logger.warning(f"Intento {attempt + 1} falló: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Backoff exponencial
        
        logger.error("Falló la subida de imagen después de todos los intentos")
        return None
    
    def run(self):
        """Inicia el bot con configuración robusta"""
        if not self.TELEGRAM_TOKEN:
            logger.error("❌ Token de Telegram no configurado")
            return
        
        if not self.groq_client:
            logger.error("❌ Cliente Groq no inicializado")
            return
        
        if not self.wp_client:
            logger.error("❌ Cliente WordPress no inicializado")
            return
        
        # Crear directorio de logs si no existe
        os.makedirs('logs', exist_ok=True)
        
        try:
            # Configurar aplicación
            application = Application.builder().token(self.TELEGRAM_TOKEN).build()
            
            # Comandos
            application.add_handler(CommandHandler("start", self.start_command))
            application.add_handler(CommandHandler("help", self.help_command))
            application.add_handler(CommandHandler("stats", self.stats_command))
            
            # Manejador de mensajes con contenido multimedia
            application.add_handler(
                MessageHandler(
                    filters.PHOTO | filters.VOICE | filters.AUDIO,
                    self.process_telegram_message
                )
            )
            
            logger.info("🚀 Bot iniciado exitosamente")
            logger.info("📡 Esperando mensajes de periodistas...")
            
            # Ejecutar bot
            application.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            logger.error(f"❌ Error crítico al iniciar bot: {e}")


if __name__ == "__main__":
    try:
        bot = TelegramToWordPressBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("🛑 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"💥 Error fatal: {e}")

# Health check endpoint para Render
from flask import Flask
import threading
import os

# Solo agregar Flask si no existe ya
if 'app' not in locals():
    flask_app = Flask(__name__)
    
    @flask_app.route('/')
    @flask_app.route('/health')
    def health_check():
        return "Bot de automatización periodística funcionando ✅", 200
    
    @flask_app.route('/status')
    def status():
        return {
            "status": "running",
            "service": "telegram-wordpress-bot",
            "version": "1.0.0"
        }
    
    def run_flask():
        port = int(os.environ.get('PORT', 10000))
        flask_app.run(host='0.0.0.0', port=port, debug=False)
    
    # Iniciar Flask en hilo separado
    if __name__ == "__main__":
        # Iniciar bot en hilo principal
        bot = TelegramToWordPressBot()
        
        # Iniciar Flask en hilo separado para health checks
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Ejecutar bot
        bot.run()
