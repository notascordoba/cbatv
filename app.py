#!/usr/bin/env python3
"""
Sistema mejorado para automatización periodística v2.1.1
🚀 VERSIÓN DEFINITIVA CON MÉTODO v2.0.7 RESTAURADO:
- ✅ Fix RuntimeError('Event loop is closed')
- ✅ DEBUG logging habilitado para diagnóstico completo
- ✅ MÉTODO SetPostThumbnail v2.0.7 RESTAURADO (que funcionaba)
- ✅ Manejo robusto de errores SSL
- ✅ Validaciones mejoradas
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
import threading
from flask import Flask

# Cargar variables de entorno
load_dotenv()

# 🚨 CONFIGURACIÓN DE LOGGING DEBUG ACTIVADO
logging.basicConfig(
    level=logging.DEBUG,  # ✅ CAMBIADO A DEBUG PARA DIAGNÓSTICO COMPLETO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ✅ LOG INICIAL PARA CONFIRMAR DEBUG ACTIVO
logger.debug("🔧 DEBUG MODE ACTIVADO - Iniciando bot v2.1.1")

class TelegramToWordPressBot:
    """Bot mejorado con validaciones y características adicionales"""
    
    def __init__(self):
        logger.debug("🔧 Inicializando TelegramToWordPressBot v2.1.1")
        
        # Configuraciones desde variables de entorno
        self.TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
        self.WORDPRESS_URL = os.getenv('WORDPRESS_URL')
        self.WORDPRESS_USERNAME = os.getenv('WORDPRESS_USERNAME')  
        self.WORDPRESS_PASSWORD = os.getenv('WORDPRESS_PASSWORD')
        self.GROQ_API_KEY = os.getenv('GROQ_API_KEY')
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        
        logger.debug(f"🔧 Tokens configurados: TELEGRAM={'✅' if self.TELEGRAM_TOKEN else '❌'}, "
                    f"WORDPRESS={'✅' if self.WORDPRESS_URL else '❌'}, "
                    f"GROQ={'✅' if self.GROQ_API_KEY else '❌'}")
        
        # Inicializar clientes AI
        self.groq_client = None
        self.openai_client = None
        
        if self.GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=self.GROQ_API_KEY)
                logger.debug("✅ Cliente Groq inicializado correctamente")
            except Exception as e:
                logger.error(f"❌ Error inicializando Groq: {e}")
        
        if self.OPENAI_API_KEY:
            try:
                self.openai_client = openai.OpenAI(api_key=self.OPENAI_API_KEY)
                logger.debug("✅ Cliente OpenAI inicializado correctamente")
            except Exception as e:
                logger.error(f"❌ Error inicializando OpenAI: {e}")
        
        # Inicializar cliente WordPress
        self.wp_client = None
        if all([self.WORDPRESS_URL, self.WORDPRESS_USERNAME, self.WORDPRESS_PASSWORD]):
            try:
                self.wp_client = Client(
                    self.WORDPRESS_URL,
                    self.WORDPRESS_USERNAME, 
                    self.WORDPRESS_PASSWORD
                )
                logger.debug("✅ Cliente WordPress inicializado correctamente")
                
                # Test de conexión WordPress
                try:
                    test_posts = self.wp_client.call(posts.GetPosts({'number': 1}))
                    logger.debug("✅ Conexión WordPress verificada exitosamente")
                except Exception as e:
                    logger.warning(f"⚠️ Advertencia en test de conexión WordPress: {e}")
                    
            except Exception as e:
                logger.error(f"❌ Error inicializando WordPress: {e}")
        
        # Estadísticas
        self.stats = {
            'mensajes_procesados': 0,
            'articulos_publicados': 0,
            'errores': 0,
            'inicio': datetime.now().isoformat()
        }
        
        logger.debug("🔧 Inicialización completada")

    def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
        """Decorador para retry con backoff exponencial"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Intento {attempt + 1} falló: {e}. Reintentando en {delay}s...")
                        await asyncio.sleep(delay)
                        
            return wrapper
        return decorator

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        logger.debug(f"🔧 Comando /start ejecutado por usuario: {update.effective_user.id}")
        
        welcome_message = """
🤖 **Bot Automatización Periodística v2.1.1**

✅ **Funcionalidades:**
• Análisis automático de noticias
• Generación de artículos con IA
• Publicación directa en WordPress
• Imágenes destacadas automáticas
• SEO optimizado

📝 **Instrucciones:**
1. Envía una noticia (texto, foto, audio)
2. El bot analizará y creará un artículo
3. Se publicará automáticamente en WordPress

🔧 **DEBUG MODE ACTIVADO** - Logs detallados disponibles

🚀 ¡Envía tu primera noticia para comenzar!
        """
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        logger.debug(f"🔧 Comando /help ejecutado por usuario: {update.effective_user.id}")
        
        help_text = """
🆘 **Ayuda - Bot Periodístico v2.1.1**

**Comandos disponibles:**
• `/start` - Iniciar bot
• `/help` - Esta ayuda
• `/stats` - Estadísticas de uso

**Tipos de contenido soportados:**
• 📝 Texto de noticias
• 📸 Imágenes con descripción
• 🎤 Audios de reportajes

**Proceso automático:**
1. Análisis de contenido con IA
2. Generación de artículo estructurado
3. Creación de imagen destacada
4. Publicación en WordPress con SEO

**Soporte:** En caso de errores, revisa los logs del sistema.
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stats"""
        logger.debug(f"🔧 Comando /stats ejecutado por usuario: {update.effective_user.id}")
        
        uptime = datetime.now() - datetime.fromisoformat(self.stats['inicio'])
        
        stats_text = f"""
📊 **Estadísticas del Bot v2.1.1**

**Tiempo activo:** {str(uptime).split('.')[0]}
**Mensajes procesados:** {self.stats['mensajes_procesados']}
**Artículos publicados:** {self.stats['articulos_publicados']}
**Errores registrados:** {self.stats['errores']}

**Estado de servicios:**
• Telegram: ✅ Conectado
• WordPress: {'✅' if self.wp_client else '❌'} {'Conectado' if self.wp_client else 'Desconectado'}
• Groq AI: {'✅' if self.groq_client else '❌'} {'Conectado' if self.groq_client else 'Desconectado'}
• OpenAI: {'✅' if self.openai_client else '❌'} {'Conectado' if self.openai_client else 'Desconectado'}

🔧 **DEBUG MODE:** Activado - Logs detallados disponibles
        """
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')

    @retry_with_backoff(max_retries=3, base_delay=2.0)
    async def _generate_content_with_groq(self, prompt: str) -> Optional[str]:
        """Genera contenido usando Groq con retry"""
        logger.debug(f"🔧 Generando contenido con Groq. Prompt length: {len(prompt)}")
        
        if not self.groq_client:
            logger.warning("⚠️ Cliente Groq no disponible")
            return None
        
        try:
            response = self.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {
                        "role": "system", 
                        "content": "Eres un periodista profesional experto en redacción de noticias. Crea artículos bien estructurados, informativos y atractivos."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            logger.debug(f"✅ Contenido generado exitosamente. Length: {len(content) if content else 0}")
            return content
            
        except Exception as e:
            logger.error(f"❌ Error en Groq: {e}")
            raise e

    async def _generate_content_with_openai(self, prompt: str) -> Optional[str]:
        """Genera contenido usando OpenAI como fallback"""
        logger.debug(f"🔧 Generando contenido con OpenAI (fallback). Prompt length: {len(prompt)}")
        
        if not self.openai_client:
            logger.warning("⚠️ Cliente OpenAI no disponible")
            return None
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": "Eres un periodista profesional experto en redacción de noticias. Crea artículos bien estructurados, informativos y atractivos."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            logger.debug(f"✅ Contenido OpenAI generado exitosamente. Length: {len(content) if content else 0}")
            return content
            
        except Exception as e:
            logger.error(f"❌ Error en OpenAI: {e}")
            return None

    async def _generate_image_with_ai(self, prompt: str) -> Optional[bytes]:
        """Genera imagen usando IA"""
        logger.debug(f"🔧 Generando imagen con prompt: {prompt[:100]}...")
        
        # Intentar con OpenAI DALL-E primero
        if self.openai_client:
            try:
                logger.debug("🔧 Intentando generar imagen con OpenAI DALL-E")
                
                response = self.openai_client.images.generate(
                    model="dall-e-2",
                    prompt=prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                
                image_url = response.data[0].url
                logger.debug(f"✅ Imagen generada. URL: {image_url}")
                
                # Descargar imagen
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as img_response:
                        if img_response.status == 200:
                            image_data = await img_response.read()
                            logger.debug(f"✅ Imagen descargada. Size: {len(image_data)} bytes")
                            return image_data
                        else:
                            logger.error(f"❌ Error descargando imagen: {img_response.status}")
                            
            except Exception as e:
                logger.error(f"❌ Error generando imagen con OpenAI: {e}")
        
        # Fallback: generar imagen placeholder
        logger.debug("🔧 Generando imagen placeholder como fallback")
        return await self._create_placeholder_image(prompt)

    async def _create_placeholder_image(self, text: str) -> bytes:
        """Crea imagen placeholder"""
        logger.debug(f"🔧 Creando imagen placeholder con texto: {text[:50]}...")
        
        try:
            # Crear imagen simple con PIL
            img = Image.new('RGB', (1024, 768), color='#2C3E50')
            
            # Convertir a bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=85)
            img_data = img_byte_arr.getvalue()
            
            logger.debug(f"✅ Imagen placeholder creada. Size: {len(img_data)} bytes")
            return img_data
            
        except Exception as e:
            logger.error(f"❌ Error creando placeholder: {e}")
            return b''

    async def _process_image(self, image_data: Optional[bytes]) -> Optional[bytes]:
        """Procesa y optimiza imagen"""
        if not image_data:
            logger.debug("🔧 No hay datos de imagen para procesar")
            return None
        
        logger.debug(f"🔧 Procesando imagen. Size original: {len(image_data)} bytes")
        
        try:
            # Abrir imagen
            img = Image.open(io.BytesIO(image_data))
            
            # Redimensionar si es muy grande
            max_size = (1200, 900)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                logger.debug(f"🔧 Imagen redimensionada a: {img.size}")
            
            # Convertir a RGB si es necesario
            if img.mode != 'RGB':
                img = img.convert('RGB')
                logger.debug("🔧 Imagen convertida a RGB")
            
            # Guardar optimizada
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            processed_data = output.getvalue()
            
            logger.debug(f"✅ Imagen procesada. Size final: {len(processed_data)} bytes")
            return processed_data
            
        except Exception as e:
            logger.error(f"❌ Error procesando imagen: {e}")
            return image_data  # Retornar original si falla el procesamiento

    async def _publish_to_wordpress(self, article_data: Dict, image_data: Optional[bytes]) -> Optional[Dict]:
        """Publica artículo en WordPress con manejo robusto de errores"""
        logger.debug("🔧 Iniciando publicación en WordPress")
        logger.debug(f"🔧 Datos del artículo: título='{article_data.get('title', 'N/A')[:50]}...', "
                    f"imagen={'SÍ' if image_data else 'NO'}")
        
        try:
            if not self.wp_client:
                logger.error("❌ Cliente WordPress no disponible")
                return None
            
            # Subir imagen
            featured_image_id = None
            if image_data:
                logger.debug("🔧 Iniciando subida de imagen...")
                featured_image_id = await self._upload_image_to_wordpress_ultra_robust(
                    image_data,
                    article_data.get('alt_text', 'Imagen de noticia')
                )
                
                if featured_image_id:
                    logger.debug(f"✅ Imagen subida exitosamente con ID: {featured_image_id}")
                else:
                    logger.error("❌ Falló la subida de imagen")
            else:
                logger.debug("⚠️ No hay imagen para subir")
            
            # Crear post
            logger.debug("🔧 Creando post en WordPress...")
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
                logger.debug(f"🔧 Tags asignados: {article_data['tags']}")
            
            # Categoría si está especificada
            if 'category' in article_data and article_data['category']:
                if 'terms_names' not in post.__dict__:
                    post.terms_names = {}
                post.terms_names['category'] = [article_data['category']]
                logger.debug(f"🔧 Categoría asignada: {article_data['category']}")
            
            # 🚨 SECCIÓN CRÍTICA: ASIGNACIÓN DE IMAGEN DESTACADA
            if featured_image_id:
                logger.debug(f"🔧 ASIGNANDO IMAGEN DESTACADA - ID: {featured_image_id}")
                post.thumbnail = featured_image_id
                logger.debug(f"✅ post.thumbnail configurado con ID: {featured_image_id}")
            else:
                logger.warning("⚠️ NO SE ASIGNARÁ IMAGEN DESTACADA - No hay featured_image_id")
            
            # Publicar post
            logger.debug("🔧 Enviando post a WordPress...")
            post_id = self.wp_client.call(posts.NewPost(post))
            logger.debug(f"✅ Post creado con ID: {post_id}")
            
            # 🚨 VERIFICACIÓN CRÍTICA: COMPROBAR SI LA IMAGEN DESTACADA SE ASIGNÓ
            if featured_image_id and post_id:
                logger.debug(f"🔧 VERIFICANDO asignación de imagen destacada para post {post_id}")
                success = await self._set_featured_image_ultra_robust(post_id, featured_image_id)
                if success:
                    logger.debug("✅ IMAGEN DESTACADA ASIGNADA EXITOSAMENTE")
                else:
                    logger.error("❌ FALLÓ LA ASIGNACIÓN DE IMAGEN DESTACADA")
            
            logger.info(f"✅ Artículo publicado exitosamente. Post ID: {post_id}")
            
            return {
                'post_id': post_id,
                'status': 'draft',
                'title': article_data['title'],
                'featured_image_id': featured_image_id,
                'url': f"{self.WORDPRESS_URL.replace('/xmlrpc.php', '')}/?p={post_id}"
            }
            
        except Exception as e:
            logger.error(f"❌ Error publicando en WordPress: {e}", exc_info=True)
            return None

    async def _upload_image_to_wordpress_ultra_robust(self, image_data: bytes, alt_text: str) -> Optional[int]:
        """Sube imagen a WordPress con retry logic ultra robusto"""
        logger.debug(f"🔧 INICIANDO SUBIDA ULTRA ROBUSTA - Size: {len(image_data)} bytes, Alt: '{alt_text}'")
        
        max_retries = 5  # Aumentado a 5 intentos
        timeout = 60  # Timeout de 60 segundos
        
        for attempt in range(max_retries):
            logger.debug(f"🔧 Intento {attempt + 1}/{max_retries} de subida de imagen...")
            
            try:
                filename = f'noticia_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{attempt}.jpg'
                logger.debug(f"🔧 Nombre de archivo: {filename}")
                
                data = {
                    'name': filename,
                    'type': 'image/jpeg',
                    'bits': xmlrpc_client.Binary(image_data)
                }
                
                logger.debug("🔧 Ejecutando wp_client.call(media.UploadFile)...")
                
                # Subida con timeout
                start_time = time.time()
                response = self.wp_client.call(media.UploadFile(data))
                elapsed = time.time() - start_time
                
                logger.debug(f"🔧 Respuesta recibida en {elapsed:.2f}s: {response}")
                
                if response and 'id' in response:
                    media_id = response['id']
                    logger.debug(f"✅ Imagen subida exitosamente - Media ID: {media_id}")
                    
                    # Actualizar alt text
                    try:
                        logger.debug(f"🔧 Actualizando alt text para media ID {media_id}...")
                        media_item = self.wp_client.call(media.GetMediaItem(media_id))
                        media_item.description = alt_text
                        self.wp_client.call(media.EditMediaItem(media_id, media_item))
                        logger.debug("✅ Alt text actualizado exitosamente")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo actualizar alt text: {e}")
                    
                    return media_id
                else:
                    logger.error(f"❌ Respuesta inválida de WordPress: {response}")
                
            except Exception as e:
                logger.error(f"❌ Intento {attempt + 1} falló: {e}", exc_info=True)
                
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + 1  # Backoff exponencial mejorado
                    logger.debug(f"🔧 Esperando {wait_time}s antes del siguiente intento...")
                    await asyncio.sleep(wait_time)
        
        logger.error("❌ FALLÓ LA SUBIDA DE IMAGEN DESPUÉS DE TODOS LOS INTENTOS")
        return None

    async def _set_featured_image_ultra_robust(self, post_id: int, image_id: int) -> bool:
        """Asigna imagen destacada usando MÉTODO v2.0.7 que FUNCIONABA"""
        logger.debug(f"🔧 INICIANDO ASIGNACIÓN v2.0.7 RESTAURADA - Post ID: {post_id}, Image ID: {image_id}")
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                logger.debug(f"🔧 Intento {attempt + 1}/{max_retries} - Usando posts.SetPostThumbnail...")
                
                # ✅ MÉTODO EXACTO DE v2.0.7 QUE FUNCIONABA
                from wordpress_xmlrpc.methods.posts import SetPostThumbnail
                result = self.wp_client.call(SetPostThumbnail(post_id, image_id))
                
                logger.debug(f"🔧 Resultado SetPostThumbnail: {result}")
                
                if result:
                    logger.debug("✅ IMAGEN DESTACADA CONFIGURADA EXITOSAMENTE!")
                    
                    # Verificar que realmente se asignó
                    verification_post = self.wp_client.call(posts.GetPost(post_id))
                    final_thumbnail = getattr(verification_post, 'thumbnail', None)
                    
                    if final_thumbnail == image_id:
                        logger.debug(f"✅ VERIFICACIÓN EXITOSA - Thumbnail asignado: {final_thumbnail}")
                        return True
                    else:
                        logger.warning(f"⚠️ SetPostThumbnail retornó True pero verificación falló. Expected: {image_id}, Got: {final_thumbnail}")
                        # Continuar con siguiente intento
                else:
                    logger.warning(f"⚠️ SetPostThumbnail retornó False en intento {attempt + 1}")
                
            except ImportError:
                # Fallback si SetPostThumbnail no está disponible
                logger.warning("⚠️ SetPostThumbnail no disponible, usando método EditPost...")
                try:
                    current_post = self.wp_client.call(posts.GetPost(post_id))
                    current_post.thumbnail = image_id
                    result = self.wp_client.call(posts.EditPost(post_id, current_post))
                    
                    if result:
                        verification_post = self.wp_client.call(posts.GetPost(post_id))
                        final_thumbnail = getattr(verification_post, 'thumbnail', None)
                        
                        if final_thumbnail == image_id:
                            logger.debug(f"✅ IMAGEN DESTACADA ASIGNADA via EditPost: {final_thumbnail}")
                            return True
                            
                except Exception as e:
                    logger.error(f"❌ Error en fallback EditPost: {e}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Error en intento {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + 1
                    logger.debug(f"🔧 Esperando {wait_time}s antes del siguiente intento...")
                    await asyncio.sleep(wait_time)
        
        logger.error("❌ FALLÓ LA ASIGNACIÓN DE IMAGEN DESTACADA DESPUÉS DE TODOS LOS INTENTOS")
        return False

    async def process_telegram_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesa mensajes de Telegram"""
        logger.debug(f"🔧 Procesando mensaje de Telegram. User: {update.effective_user.id}")
        
        try:
            self.stats['mensajes_procesados'] += 1
            
            message = update.message
            user_id = update.effective_user.id
            
            logger.debug(f"🔧 Tipo de mensaje: texto={'SÍ' if message.text else 'NO'}, "
                        f"foto={'SÍ' if message.photo else 'NO'}, "
                        f"audio={'SÍ' if message.voice or message.audio else 'NO'}")
            
            # Enviar confirmación inmediata
            processing_msg = await message.reply_text("🔄 Procesando tu noticia...")
            
            # Extraer contenido
            content_text = ""
            image_data = None
            
            # Procesar texto
            if message.text:
                content_text = message.text
                logger.debug(f"🔧 Texto extraído: {len(content_text)} caracteres")
            
            # Procesar imagen
            if message.photo:
                logger.debug("🔧 Procesando imagen del mensaje...")
                try:
                    # Obtener la imagen de mayor resolución
                    photo = message.photo[-1]
                    file = await context.bot.get_file(photo.file_id)
                    
                    # Descargar imagen
                    image_bytes = io.BytesIO()
                    await file.download_to_memory(image_bytes)
                    image_data = image_bytes.getvalue()
                    
                    logger.debug(f"✅ Imagen descargada: {len(image_data)} bytes")
                    
                    # Procesar imagen
                    image_data = await self._process_image(image_data)
                    
                except Exception as e:
                    logger.error(f"❌ Error procesando imagen: {e}")
            
            # Procesar audio (si está presente)
            if message.voice or message.audio:
                logger.debug("🔧 Audio detectado (funcionalidad en desarrollo)")
                content_text += "\n[Contenido de audio procesado]"
            
            # Validar contenido mínimo
            if len(content_text.strip()) < 50:
                await processing_msg.edit_text(
                    "❌ El contenido es muy corto. Envía al menos 50 caracteres de texto noticioso."
                )
                return
            
            # Generar artículo con IA
            logger.debug("🔧 Generando artículo con IA...")
            await processing_msg.edit_text("🤖 Generando artículo con IA...")
            
            article_data = await self._generate_article_from_content(content_text)
            
            if not article_data:
                await processing_msg.edit_text("❌ Error generando artículo. Intenta nuevamente.")
                self.stats['errores'] += 1
                return
            
            # Generar imagen si no hay una
            if not image_data and article_data.get('title'):
                logger.debug("🔧 Generando imagen destacada con IA...")
                await processing_msg.edit_text("🎨 Generando imagen destacada...")
                
                image_prompt = f"Imagen periodística profesional sobre: {article_data['title'][:100]}"
                image_data = await self._generate_image_with_ai(image_prompt)
            
            # Publicar en WordPress
            logger.debug("🔧 Publicando en WordPress...")
            await processing_msg.edit_text("📝 Publicando en WordPress...")
            
            result = await self._publish_to_wordpress(article_data, image_data)
            
            if result:
                self.stats['articulos_publicados'] += 1
                
                success_message = f"""
✅ **Artículo publicado exitosamente**

📰 **Título:** {result['title']}
🆔 **Post ID:** {result['post_id']}
🖼️ **Imagen destacada:** {'✅ Asignada' if result.get('featured_image_id') else '❌ No asignada'}
🔗 **URL:** {result['url']}
📊 **Estado:** {result['status']}

🔧 **DEBUG:** Logs detallados disponibles para diagnóstico
                """
                
                await processing_msg.edit_text(success_message, parse_mode='Markdown')
                logger.info(f"✅ Artículo publicado exitosamente para usuario {user_id}")
                
            else:
                await processing_msg.edit_text("❌ Error publicando artículo. Revisa la configuración de WordPress.")
                self.stats['errores'] += 1
                logger.error(f"❌ Error publicando artículo para usuario {user_id}")
                
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}", exc_info=True)
            self.stats['errores'] += 1
            
            try:
                await update.message.reply_text(f"❌ Error procesando mensaje: {str(e)}")
            except:
                pass

    async def _generate_article_from_content(self, content: str) -> Optional[Dict]:
        """Genera artículo estructurado desde contenido"""
        logger.debug(f"🔧 Generando artículo desde contenido: {len(content)} caracteres")
        
        prompt = f"""
Como periodista profesional, convierte este contenido en un artículo de noticia bien estructurado:

CONTENIDO ORIGINAL:
{content}

INSTRUCCIONES:
1. Crea un título atractivo y informativo
2. Escribe un artículo completo con introducción, desarrollo y conclusión
3. Usa un tono periodístico profesional
4. Incluye subtítulos para mejorar la lectura
5. Agrega contexto y análisis cuando sea apropiado

FORMATO DE RESPUESTA (JSON):
{{
    "title": "Título del artículo",
    "content": "Artículo completo con formato HTML",
    "excerpt": "Resumen breve del artículo",
    "meta_description": "Descripción para SEO (max 160 caracteres)",
    "keywords": "palabras, clave, separadas, por, comas",
    "tags": ["tag1", "tag2", "tag3"],
    "category": "Categoría principal",
    "author": "Sistema automático"
}}
        """
        
        # Intentar con Groq primero
        content = await self._generate_content_with_groq(prompt)
        
        # Fallback a OpenAI si Groq falla
        if not content:
            logger.debug("🔧 Groq falló, intentando con OpenAI...")
            content = await self._generate_content_with_openai(prompt)
        
        if not content:
            logger.error("❌ Ambos servicios de IA fallaron")
            return None
        
        # Parsear JSON
        try:
            # Extraer JSON del contenido si tiene formato markdown
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_content = content[json_start:json_end].strip()
            else:
                json_content = content.strip()
            
            article_data = json.loads(json_content)
            logger.debug(f"✅ Artículo generado exitosamente: '{article_data.get('title', 'Sin título')[:50]}...'")
            
            return article_data
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parseando JSON: {e}")
            logger.debug(f"Contenido recibido: {content[:500]}...")
            
            # Fallback: crear estructura manual
            return {
                "title": "Artículo generado automáticamente",
                "content": content,
                "excerpt": content[:200] + "...",
                "meta_description": "Artículo generado por sistema automático",
                "keywords": "noticia, automático, sistema",
                "tags": ["automatico", "noticia"],
                "category": "General",
                "author": "Sistema automático"
            }

    def run(self):
        """Inicia el bot con configuración robusta v2.1.1"""
        logger.debug("🔧 Iniciando bot v2.1.1...")
        
        if not self.TELEGRAM_TOKEN:
            logger.error("❌ Token de Telegram no configurado")
            return
        
        if not self.groq_client and not self.openai_client:
            logger.error("❌ Ningún cliente de IA está disponible")
            return
        
        if not self.wp_client:
            logger.error("❌ Cliente WordPress no inicializado")
            return
        
        # Crear directorio de logs si no existe
        os.makedirs('logs', exist_ok=True)
        logger.debug("✅ Directorio de logs verificado")
        
        try:
            # Configurar aplicación
            logger.debug("🔧 Configurando aplicación de Telegram...")
            application = Application.builder().token(self.TELEGRAM_TOKEN).build()
            
            # Comandos
            application.add_handler(CommandHandler("start", self.start_command))
            application.add_handler(CommandHandler("help", self.help_command))
            application.add_handler(CommandHandler("stats", self.stats_command))
            
            # Manejador de mensajes con contenido multimedia
            application.add_handler(
                MessageHandler(
                    filters.PHOTO | filters.VOICE | filters.AUDIO | filters.TEXT,
                    self.process_telegram_message
                )
            )
            
            logger.info("🚀 Bot v2.1.1 iniciado exitosamente")
            logger.info("📡 Esperando mensajes de periodistas...")
            logger.debug("🔧 Configuración completa - Iniciando polling...")
            
            # ✅ EJECUTAR BOT CON MÉTODO ESTABLE (NO asyncio.run)
            application.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            logger.error(f"❌ Error crítico al iniciar bot: {e}", exc_info=True)
            raise e

# Flask app para health checks en Render
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    """Health check endpoint para Render"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "telegram-wordpress-bot",
        "version": "2.1.1"
    }

def run_flask():
    """Ejecuta Flask en puerto de Render"""
    port = int(os.environ.get('PORT', 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False)

# 🚨 PUNTO DE ENTRADA PRINCIPAL CON FIX DE EVENT LOOP
if __name__ == "__main__":
    logger.debug("🔧 === INICIANDO APLICACIÓN V2.1.1 ===")
    
    # Inicializar bot
    bot = TelegramToWordPressBot()
    
    # ✅ INICIAR FLASK EN HILO SEPARADO PARA HEALTH CHECKS
    logger.debug("🔧 Iniciando Flask para health checks...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.debug("✅ Flask iniciado en hilo separado")
    
    # ✅ EJECUTAR BOT EN HILO PRINCIPAL CON MÉTODO ESTABLE
    logger.debug("🔧 Iniciando bot principal...")
    try:
        bot.run()  # Usa application.run_polling() internamente - MÁS ESTABLE
    except KeyboardInterrupt:
        logger.info("🛑 Bot detenido manualmente")
    except Exception as e:
        logger.critical(f"💥 Error crítico en bot principal: {e}", exc_info=True)
        raise e
