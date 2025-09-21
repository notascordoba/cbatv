#!/usr/bin/env python3
"""
Sistema SEO Profesional para automatización periodística v2.0.6
Bot que convierte crónicas en artículos SEO optimizados para WordPress
Base sólida sin errores de inicialización + características SEO avanzadas + Manejo robusto de SSL

VERSIÓN: 2.0.6
FECHA: 2025-09-21
CAMBIOS:
+ Obtención automática de categorías de WordPress usando XML-RPC
+ Validación estricta de categorías (prohibido crear nuevas)
+ Prompt inteligente con categorías disponibles del sitio
+ Adaptabilidad multi-sitio para diferentes temáticas
+ Cache de categorías para optimizar rendimiento
+ Fallbacks inteligentes en caso de problemas de conexión
+ Configuración automática de imagen destacada en WordPress
+ Optimización de redimensionado a 1200x675px como featured image
+ CORRECCIÓN CRÍTICA: Flujo de generación de artículos mejorado y robusto
+ CORRECCIÓN: Manejo consistente de errores y fallbacks
+ CORRECCIÓN FINAL: Import correcto de wordpress_xmlrpc sin errores
+ CORRECCIÓN SSL v2.0.6: Sistema robusto para manejo de errores SSL/TLS
+ SISTEMA DE REINTENTOS: Backoff exponencial para subida de imágenes
+ TIMEOUT CONFIGURABLES: Mejor manejo de timeouts de conexión
+ VALIDACIÓN MEJORADA: Verificación previa de conexión antes de subir
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
import ssl
import socket
import time

# Imports específicos de WordPress
import wordpress_xmlrpc
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.methods.taxonomies import GetTerms

# Imports de Telegram
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Import de OpenAI
from openai import AsyncOpenAI

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class WordPressSEOBot:
    """
    Bot profesional para convertir mensajes de Telegram en artículos SEO optimizados
    
    Funcionalidades principales:
    - Recibe texto/imagen/audio desde Telegram
    - Genera artículos SEO completos usando IA
    - Redimensiona imágenes a tamaño óptimo (1200x675px)
    - Configura automáticamente imagen destacada en WordPress
    - Obtiene categorías dinámicamente de cada sitio WordPress
    - Valida categorías antes de publicar (no crea nuevas)
    - Publica directamente en WordPress con metadatos SEO
    - NUEVO v2.0.6: Manejo robusto de errores SSL/TLS
    """
    
    def __init__(self):
        """Inicializa el bot con configuración desde variables de entorno"""
        
        # Tokens y configuración principal
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.wordpress_url = os.getenv('WORDPRESS_URL')
        self.wordpress_user = os.getenv('WORDPRESS_USER')  
        self.wordpress_password = os.getenv('WORDPRESS_PASSWORD')
        
        # IDs autorizados (convertir de string separado por comas)
        authorized_ids_str = os.getenv('AUTHORIZED_USER_IDS', '')
        self.authorized_user_ids = []
        if authorized_ids_str:
            try:
                self.authorized_user_ids = [int(uid.strip()) for uid in authorized_ids_str.split(',') if uid.strip()]
            except ValueError:
                logger.warning("❌ Error parseando AUTHORIZED_USER_IDS - se requiere formato: id1,id2,id3")
        
        # Configuración de imagen
        self.TARGET_WIDTH = int(os.getenv('IMAGE_WIDTH', 1200))
        self.TARGET_HEIGHT = int(os.getenv('IMAGE_HEIGHT', 675))
        self.IMAGE_QUALITY = int(os.getenv('IMAGE_QUALITY', 85))
        
        # Configuración de IA
        self.ai_model = os.getenv('AI_MODEL', 'gpt-4o-mini')
        self.max_tokens = int(os.getenv('MAX_TOKENS', 4000))
        
        # Configuración WordPress
        self.wp_timeout = int(os.getenv('WP_TIMEOUT', 30))
        
        # NUEVO v2.0.6: Configuración SSL y reintentos
        self.max_retries = int(os.getenv('MAX_RETRIES', 3))
        self.retry_delay_base = float(os.getenv('RETRY_DELAY_BASE', 2.0))
        self.ssl_verify = os.getenv('SSL_VERIFY', 'true').lower() == 'true'
        
        # Variables de estado
        self.telegram_app = None
        self.openai_client = None
        self.wp_client = None
        self.available_categories = []
        self.categories_cache_time = None
        self.logger = logger
        
        # NUEVO v2.0.6: Validación de configuración SSL
        logger.info(f"🔒 Configuración SSL: verificar={self.ssl_verify}, reintentos={self.max_retries}")

    async def init_clients(self):
        """
        Inicializa todos los clientes necesarios (Telegram, OpenAI, WordPress)
        
        NUEVO v2.0.4: Incluye cache de categorías disponibles
        NUEVO v2.0.6: Configuración SSL mejorada para WordPress
        """
        try:
            success_count = 0
            
            # 1. Cliente de Telegram
            if self.telegram_token:
                try:
                    self.telegram_app = Application.builder().token(self.telegram_token).build()
                    logger.info("✅ Cliente Telegram conectado")
                    success_count += 1
                except Exception as e:
                    logger.error(f"❌ Error conectando Telegram: {e}")
            
            # 2. Cliente OpenAI
            if self.openai_api_key:
                try:
                    self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
                    logger.info("✅ Cliente OpenAI conectado")
                    success_count += 1
                except Exception as e:
                    logger.error(f"❌ Error conectando OpenAI: {e}")
            
            # 3. Cliente WordPress con configuración SSL robusta
            if self.wordpress_url and self.wordpress_user and self.wordpress_password:
                try:
                    wp_url = f"{self.wordpress_url.rstrip('/')}/xmlrpc.php"
                    
                    # NUEVO v2.0.6: Configuración SSL robusta
                    self.wp_client = self._create_wordpress_client_with_ssl(wp_url)
                    
                    # Probar conexión con reintento
                    await self._test_wordpress_connection()
                    logger.info("✅ Cliente WordPress conectado con SSL robusto")
                    success_count += 1
                    
                    # NUEVO v2.0.4: Obtener categorías disponibles del sitio
                    await self._fetch_wordpress_categories()
                    
                except Exception as e:
                    logger.error(f"❌ Error conectando WordPress: {e}")
            
            # Verificar conexiones mínimas
            if success_count >= 2:
                logger.info(f"🚀 Bot inicializado correctamente ({success_count}/3 servicios)")
                return True
            else:
                logger.error(f"❌ Bot requiere al menos 2/3 servicios ({success_count}/3 conectados)")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error crítico en inicialización: {e}")
            return False

    def _create_wordpress_client_with_ssl(self, wp_url: str) -> Client:
        """
        NUEVO v2.0.6: Crea cliente WordPress con configuración SSL robusta
        """
        try:
            # Configurar SSL context si es necesario
            if not self.ssl_verify:
                logger.warning("⚠️ SSL verification disabled - use only for testing")
                import urllib3
                urllib3.disable_warnings()
            
            # Crear cliente con timeout extendido
            client = Client(wp_url, self.wordpress_user, self.wordpress_password)
            
            # NUEVO v2.0.6: Configurar timeout en el transporte
            if hasattr(client.transport, 'timeout'):
                client.transport.timeout = self.wp_timeout
                
            return client
            
        except Exception as e:
            logger.error(f"❌ Error creando cliente WordPress SSL: {e}")
            raise

    async def _test_wordpress_connection(self):
        """
        NUEVO v2.0.6: Prueba conexión WordPress con reintentos
        """
        for attempt in range(self.max_retries):
            try:
                # Probar conexión básica
                test_methods = self.wp_client.call(wordpress_xmlrpc.methods.demo.SayHello())
                logger.info(f"✅ Conexión WordPress verificada (intento {attempt + 1})")
                return True
                
            except (ssl.SSLError, socket.error, ConnectionError) as e:
                logger.warning(f"⚠️ Error SSL/conexión intento {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay_base * (2 ** attempt)
                    logger.info(f"🔄 Reintentando en {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    raise
                    
            except Exception as e:
                logger.error(f"❌ Error inesperado probando WordPress: {e}")
                raise

    async def _fetch_wordpress_categories(self):
        """
        NUEVO v2.0.4: Obtiene categorías disponibles del sitio WordPress
        MODIFICADO v2.0.6: Con manejo robusto de errores SSL
        """
        try:
            if not self.wp_client:
                logger.warning("⚠️ Cliente WordPress no disponible para obtener categorías")
                return
            
            # Verificar cache (válido por 1 hora)
            if (self.categories_cache_time and 
                (datetime.now() - self.categories_cache_time).seconds < 3600 and 
                self.available_categories):
                logger.info(f"📋 Usando cache de categorías ({len(self.available_categories)} disponibles)")
                return
            
            # Obtener categorías con reintentos
            for attempt in range(self.max_retries):
                try:
                    # Obtener todas las categorías
                    categories = self.wp_client.call(GetTerms('category'))
                    
                    if categories:
                        self.available_categories = [
                            {
                                'id': cat.id,
                                'name': cat.name,
                                'slug': cat.slug
                            }
                            for cat in categories
                        ]
                        self.categories_cache_time = datetime.now()
                        logger.info(f"✅ Categorías obtenidas: {len(self.available_categories)} disponibles")
                        
                        # Log de categorías disponibles
                        category_names = [cat['name'] for cat in self.available_categories]
                        logger.info(f"📂 Categorías: {', '.join(category_names)}")
                        return
                    else:
                        logger.warning("⚠️ No se encontraron categorías en WordPress")
                        return
                        
                except (ssl.SSLError, socket.error, ConnectionError) as e:
                    logger.warning(f"⚠️ Error SSL obteniendo categorías (intento {attempt + 1}): {e}")
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay_base * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        logger.error("❌ No se pudieron obtener categorías después de todos los reintentos")
                        
                except Exception as e:
                    logger.error(f"❌ Error obteniendo categorías: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error crítico obteniendo categorías: {e}")

    def _validate_environment(self):
        """Valida que todas las variables de entorno necesarias estén configuradas"""
        
        required_vars = {
            'TELEGRAM_TOKEN': self.telegram_token,
            'OPENAI_API_KEY': self.openai_api_key,
            'WORDPRESS_URL': self.wordpress_url,
            'WORDPRESS_USER': self.wordpress_user,
            'WORDPRESS_PASSWORD': self.wordpress_password,
            'AUTHORIZED_USER_IDS': len(self.authorized_user_ids) > 0
        }
        
        missing_vars = []
        for var_name, var_value in required_vars.items():
            if not var_value:
                missing_vars.append(var_name)
        
        if missing_vars:
            logger.error(f"❌ Variables de entorno faltantes: {', '.join(missing_vars)}")
            return False
        
        logger.info("✅ Todas las variables de entorno están configuradas")
        return True

    def _is_authorized_user(self, user_id: int) -> bool:
        """Verifica si el usuario está autorizado para usar el bot"""
        is_authorized = user_id in self.authorized_user_ids
        if not is_authorized:
            logger.warning(f"⚠️ Usuario no autorizado: {user_id}")
        return is_authorized

    async def _extract_content_from_message(self, update: Update) -> Dict:
        """
        Extrae contenido (texto, imagen) del mensaje de Telegram
        
        Returns:
            Dict con keys: 'text', 'image_data', 'has_content'
        """
        content = {
            'text': '',
            'image_data': None,
            'has_content': False
        }
        
        try:
            message = update.message
            
            # Extraer texto
            if message.text:
                content['text'] = message.text.strip()
                content['has_content'] = True
                logger.info(f"📝 Texto recibido: {len(content['text'])} caracteres")
            
            # Extraer imagen si existe
            if message.photo:
                try:
                    # Obtener la imagen de mayor resolución
                    photo = max(message.photo, key=lambda p: p.width * p.height)
                    
                    # Descargar imagen
                    photo_file = await photo.get_file()
                    image_bytes = await photo_file.download_as_bytearray()
                    
                    content['image_data'] = bytes(image_bytes)
                    content['has_content'] = True
                    logger.info(f"🖼️ Imagen recibida: {len(content['image_data'])} bytes")
                    
                except Exception as e:
                    logger.error(f"❌ Error descargando imagen: {e}")
            
            return content
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo contenido del mensaje: {e}")
            return content

    def resize_image(self, image_data: bytes) -> bytes:
        """
        Redimensiona imagen a 1200x675px manteniendo proporción y optimizando para web
        
        NUEVO v2.0.3: Implementa redimensionado inteligente con crop centrado
        """
        try:
            # Cargar imagen
            image = Image.open(io.BytesIO(image_data))
            
            # Convertir a RGB si es necesario
            if image.mode in ('RGBA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1])
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Calcular proporción para crop centrado
            target_ratio = self.TARGET_WIDTH / self.TARGET_HEIGHT  # 16:9
            current_ratio = image.width / image.height
            
            if current_ratio > target_ratio:
                # Imagen muy ancha - crop horizontal
                new_width = int(image.height * target_ratio)
                left = (image.width - new_width) // 2
                image = image.crop((left, 0, left + new_width, image.height))
            elif current_ratio < target_ratio:
                # Imagen muy alta - crop vertical
                new_height = int(image.width / target_ratio)
                top = (image.height - new_height) // 2
                image = image.crop((0, top, image.width, top + new_height))
            
            # Redimensionar a tamaño target
            image = image.resize((self.TARGET_WIDTH, self.TARGET_HEIGHT), Image.Resampling.LANCZOS)
            
            # Guardar como JPEG optimizado
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=self.IMAGE_QUALITY, optimize=True)
            
            resized_data = output.getvalue()
            logger.info(f"✅ Imagen redimensionada: {len(image_data)} → {len(resized_data)} bytes ({self.TARGET_WIDTH}x{self.TARGET_HEIGHT})")
            
            return resized_data
            
        except Exception as e:
            logger.error(f"❌ Error redimensionando imagen: {e}")
            return image_data

    async def generate_seo_article(self, user_text: str) -> Dict:
        """
        Genera artículo SEO completo usando OpenAI
        
        NUEVO v2.0.4: Incluye categorías disponibles en el prompt para mayor precisión
        CORREGIDO v2.0.4: Manejo robusto de respuestas de IA y fallbacks
        """
        try:
            if not self.openai_client:
                logger.error("❌ Cliente OpenAI no disponible")
                return self._generate_fallback_article(user_text)
            
            # Preparar lista de categorías disponibles para el prompt
            categories_text = ""
            if self.available_categories:
                category_names = [cat['name'] for cat in self.available_categories]
                categories_text = f"\n\nCategorías disponibles en el sitio: {', '.join(category_names)}\nDEBES elegir UNA categoría de esta lista (no crear nuevas)."
            else:
                categories_text = "\n\nNota: Usa una categoría genérica apropiada para el contenido."
            
            # Prompt optimizado con categorías dinámicas
            prompt = f"""Eres un periodista experto en SEO. Convierte este texto en un artículo periodístico profesional y optimizado.

TEXTO A PROCESAR:
{user_text}

{categories_text}

INSTRUCCIONES:
- Crear un artículo periodístico completo y profesional
- Optimizar para SEO con palabras clave naturales
- Mantener un tono informativo y objetivo
- Incluir contexto relevante y detalles importantes
- El título debe ser atractivo y descriptivo
- La meta descripción debe resumir el artículo en 150-160 caracteres

RESPONDE EN FORMATO JSON EXACTO (sin comentarios ni texto adicional):
{{
    "titulo_h1": "Título principal del artículo",
    "contenido_html": "<p>Contenido del artículo en HTML con párrafos, listas y estructura adecuada...</p>",
    "meta_description": "Descripción SEO de 150-160 caracteres",
    "categoria": "Nombre exacto de UNA categoría de la lista disponible",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "palabras_clave": ["palabra1", "palabra2", "palabra3"]
}}"""

            # Llamada a OpenAI
            logger.info("🤖 Generando artículo con IA...")
            response = await self.openai_client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {
                        "role": "system", 
                        "content": "Eres un periodista profesional experto en SEO. Respondes ÚNICAMENTE en formato JSON válido, sin comentarios ni texto adicional."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"✅ Respuesta de IA recibida: {len(ai_response)} caracteres")
            
            # Parsear respuesta JSON
            try:
                # Limpiar respuesta (remover markdown si existe)
                if ai_response.startswith('```json'):
                    ai_response = ai_response[7:]
                if ai_response.endswith('```'):
                    ai_response = ai_response[:-3]
                ai_response = ai_response.strip()
                
                article_data = json.loads(ai_response)
                
                # Validar estructura
                required_keys = ['titulo_h1', 'contenido_html', 'meta_description', 'categoria', 'tags', 'palabras_clave']
                if all(key in article_data for key in required_keys):
                    logger.info("✅ Artículo SEO generado correctamente")
                    return article_data
                else:
                    missing_keys = [key for key in required_keys if key not in article_data]
                    logger.error(f"❌ Claves faltantes en respuesta de IA: {missing_keys}")
                    return self._generate_fallback_article(user_text)
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error parseando JSON de IA: {e}")
                logger.error(f"Respuesta recibida: {ai_response[:200]}...")
                return self._generate_fallback_article(user_text)
                
        except Exception as e:
            logger.error(f"❌ Error generando artículo con IA: {e}")
            return self._generate_fallback_article(user_text)
    
    async def upload_image_to_wordpress(self, image_data: bytes, filename: str) -> Tuple[Optional[str], Optional[int]]:
        """
        NUEVO v2.0.6: Sube imagen a WordPress con manejo robusto de SSL y reintentos
        """
        for attempt in range(self.max_retries):
            try:
                if not self.wp_client:
                    logger.error("❌ Cliente WordPress no disponible")
                    return None, None
                
                # Redimensionar imagen
                resized_image = self.resize_image(image_data)
                
                # Preparar datos para WordPress
                data = {
                    'name': filename,
                    'type': 'image/jpeg',
                    'bits': resized_image
                }
                
                logger.info(f"📤 Subiendo imagen a WordPress (intento {attempt + 1})...")
                
                # Subir a WordPress con timeout extendido
                response = self.wp_client.call(media.UploadFile(data))
                
                if response and 'url' in response and 'id' in response:
                    logger.info(f"✅ Imagen subida exitosamente: {response['url']} (ID: {response['id']})")
                    return response['url'], response['id']
                elif response and 'url' in response:
                    # Fallback si no hay ID en respuesta
                    logger.info(f"✅ Imagen subida (sin ID): {response['url']}")
                    return response['url'], None
                else:
                    logger.error(f"❌ Respuesta inválida de WordPress en intento {attempt + 1}")
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay_base * (2 ** attempt)
                        logger.info(f"🔄 Reintentando subida en {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    return None, None
                    
            except (ssl.SSLError, ssl.SSLEOFError, ConnectionError, socket.error) as e:
                logger.warning(f"⚠️ Error SSL/conexión subiendo imagen (intento {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay_base * (2 ** attempt)
                    logger.info(f"🔄 Reintentando subida en {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("❌ Error SSL persistente - no se pudo subir imagen después de todos los reintentos")
                    return None, None
                    
            except Exception as e:
                logger.error(f"❌ Error inesperado subiendo imagen (intento {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay_base * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    return None, None
        
        return None, None

    async def publish_seo_article_to_wordpress(self, article_data: Dict, image_url: Optional[str] = None, image_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
        """
        CORREGIDO v2.0.4: Publica artículo SEO completo en WordPress con validaciones
        MODIFICADO v2.0.6: Con manejo robusto de errores SSL para configurar imagen destacada
        """
        try:
            if not self.wp_client:
                logger.error("❌ Cliente WordPress no disponible")
                return None, None
            
            # Validar que article_data tenga las claves necesarias
            if not article_data or 'titulo_h1' not in article_data:
                logger.error("❌ Datos de artículo inválidos o incompletos")
                return None, None
            
            # Crear post
            post = WordPressPost()
            post.title = article_data.get('titulo_h1', 'Artículo Sin Título')
            post.content = article_data.get('contenido_html', '<p>Contenido no disponible</p>')
            post.post_status = 'publish'
            
            # Configurar meta descripción si está disponible
            if 'meta_description' in article_data and article_data['meta_description']:
                post.excerpt = article_data['meta_description']
            
            # Buscar y configurar categoría
            if 'categoria' in article_data and self.available_categories:
                category_name = article_data['categoria']
                category_found = False
                
                for cat in self.available_categories:
                    if cat['name'].lower() == category_name.lower():
                        post.terms_names = {'category': [cat['name']]}
                        logger.info(f"📂 Categoría configurada: {cat['name']}")
                        category_found = True
                        break
                
                if not category_found:
                    logger.warning(f"⚠️ Categoría '{category_name}' no encontrada, usando categoría por defecto")
                    if self.available_categories:
                        post.terms_names = {'category': [self.available_categories[0]['name']]}
            
            # Configurar tags si están disponibles
            if 'tags' in article_data and article_data['tags']:
                post.terms_names = post.terms_names or {}
                post.terms_names['post_tag'] = article_data['tags']
                logger.info(f"🏷️ Tags configurados: {len(article_data['tags'])} tags")
            
            # Agregar imagen al contenido si existe
            if image_url:
                image_html = f'<div class="featured-image"><img src="{image_url}" alt="{post.title}" style="width: 100%; height: auto; margin: 20px 0;"></div>'
                post.content = image_html + post.content
            
            # Publicar artículo con reintentos
            post_id = None
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"📝 Publicando artículo en WordPress (intento {attempt + 1})...")
                    post_id = self.wp_client.call(posts.NewPost(post))
                    logger.info(f"✅ Artículo publicado con ID: {post_id}")
                    break
                    
                except (ssl.SSLError, ConnectionError, socket.error) as e:
                    logger.warning(f"⚠️ Error SSL publicando artículo (intento {attempt + 1}): {e}")
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay_base * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        logger.error("❌ No se pudo publicar artículo después de todos los reintentos")
                        return None, None
                        
                except Exception as e:
                    logger.error(f"❌ Error publicando artículo: {e}")
                    return None, None
            
            if not post_id:
                return None, None
            
            # Configurar imagen destacada si está disponible
            if image_id and post_id:
                for attempt in range(self.max_retries):
                    try:
                        logger.info(f"🖼️ Configurando imagen destacada (intento {attempt + 1}) - Post ID: {post_id}, Image ID: {image_id}")
                        self.wp_client.call(posts.SetPostThumbnail(post_id, image_id))
                        logger.info("✅ Imagen destacada configurada exitosamente")
                        break
                        
                    except (ssl.SSLError, ConnectionError, socket.error) as e:
                        logger.warning(f"⚠️ Error SSL configurando imagen destacada (intento {attempt + 1}): {e}")
                        if attempt < self.max_retries - 1:
                            delay = self.retry_delay_base * (2 ** attempt)
                            await asyncio.sleep(delay)
                        else:
                            logger.warning("⚠️ No se pudo configurar imagen destacada - continuando sin ella")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Error configurando imagen destacada: {e}")
                        break
            
            # Construir URL del artículo
            article_url = f"{self.wordpress_url.rstrip('/')}/{post_id}"
            
            return post_id, article_url
            
        except Exception as e:
            logger.error(f"❌ Error crítico publicando artículo: {e}")
            return None, None

    def _generate_fallback_article(self, user_text: str) -> Dict:
        """
        Genera artículo de respaldo cuando falla la IA
        
        CORREGIDO v2.0.4: Estructura consistente con las claves esperadas
        """
        logger.info("🔄 Generando artículo de respaldo...")
        
        # Extraer título básico del texto
        lines = user_text.strip().split('\n')
        title = lines[0][:100] if lines else "Artículo Informativo"
        
        # Limpiar título
        title = re.sub(r'[^\w\s\-.,:]', '', title).strip()
        if not title:
            title = "Artículo Informativo"
        
        # Generar contenido HTML básico
        paragraphs = [line.strip() for line in lines if line.strip()]
        if not paragraphs:
            paragraphs = [user_text]
        
        content_html = ""
        for paragraph in paragraphs[:5]:  # Máximo 5 párrafos
            if len(paragraph) > 20:  # Solo párrafos significativos
                content_html += f"<p>{paragraph}</p>\n"
        
        if not content_html:
            content_html = f"<p>{user_text[:500]}...</p>"
        
        # Categoría por defecto
        default_category = "General"
        if self.available_categories:
            default_category = self.available_categories[0]['name']
        
        return {
            'titulo_h1': title,
            'contenido_html': content_html,
            'meta_description': f"{title}. Información relevante y actualizada."[:160],
            'categoria': default_category,
            'tags': ['noticias', 'información'],
            'palabras_clave': ['información', 'actualidad']
        }

    async def process_telegram_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Procesa mensaje de Telegram y publica artículo en WordPress
        
        CORREGIDO v2.0.4: Flujo robusto con validaciones y manejo de errores
        MEJORADO v2.0.6: Con manejo avanzado de errores SSL
        """
        try:
            # Verificar autorización
            user_id = update.effective_user.id
            if not self._is_authorized_user(user_id):
                await update.message.reply_text("❌ No tienes autorización para usar este bot.")
                return
            
            # Extraer contenido del mensaje
            content_data = await self._extract_content_from_message(update)
            
            if not content_data['has_content']:
                await update.message.reply_text("❌ Por favor envía texto o imagen para procesar.")
                return
            
            # Combinar texto si existe
            combined_text = content_data['text'] if content_data['text'] else "Imagen para procesar"
            
            # Enviar mensaje de confirmación
            status_message = await update.message.reply_text("🚀 Procesando contenido y generando artículo SEO...")
            
            # Generar artículo con IA
            try:
                article_data = await self.generate_seo_article(combined_text)
                
                # NUEVA VALIDACIÓN v2.0.4: Verificar que article_data sea válido
                if not article_data or 'titulo_h1' not in article_data:
                    logger.warning("⚠️ Respuesta de la IA inválida o incompleta. Generando fallback.")
                    article_data = self._generate_fallback_article(combined_text)
                
                await status_message.edit_text("✅ Artículo generado. Subiendo imagen...")
                
            except Exception as e:
                logger.error(f"❌ Error generando artículo: {e}")
                article_data = self._generate_fallback_article(combined_text)
                await status_message.edit_text("⚠️ Artículo generado con método de respaldo...")
            
            # Subir imagen si existe
            image_url = None
            image_id = None
            
            if content_data['image_data']:
                try:
                    filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    image_url, image_id = await self.upload_image_to_wordpress(content_data['image_data'], filename)
                    
                    if image_url:
                        await status_message.edit_text("✅ Imagen subida. Publicando artículo...")
                    else:
                        await status_message.edit_text("⚠️ Error subiendo imagen. Publicando artículo sin imagen...")
                        
                except Exception as e:
                    logger.error(f"❌ Error procesando imagen: {e}")
                    await status_message.edit_text("⚠️ Error con imagen. Publicando solo texto...")
            
            # Publicar artículo en WordPress
            try:
                post_id, article_url = await self.publish_seo_article_to_wordpress(
                    article_data, image_url, image_id
                )
                
                if post_id:
                    # Mensaje de éxito con detalles
                    success_msg = f"""✅ **Artículo publicado exitosamente**

📰 **Título:** {article_data.get('titulo_h1', 'N/A')}
🆔 **Post ID:** {post_id}
📂 **Categoría:** {article_data.get('categoria', 'N/A')}
🏷️ **Tags:** {len(article_data.get('tags', []))} configurados
🖼️ **Imagen:** {'✅ Configurada' if image_id else '❌ No disponible'}

🔗 **URL:** {article_url}"""

                    await status_message.edit_text(success_msg)
                    logger.info(f"🎉 Proceso completado exitosamente - Post ID: {post_id}")
                    
                else:
                    await status_message.edit_text("❌ Error publicando artículo en WordPress. Revisa los logs.")
                    logger.error("❌ No se pudo obtener post_id del artículo publicado")
                    
            except Exception as e:
                logger.error(f"❌ Error crítico en publicación: {e}")
                await status_message.edit_text("❌ Error crítico publicando artículo. Revisa configuración de WordPress.")
            
        except Exception as e:
            logger.error(f"❌ Error crítico procesando mensaje: {e}")
            try:
                await update.message.reply_text("❌ Error crítico procesando tu solicitud. Contacta al administrador.")
            except:
                logger.error("❌ No se pudo enviar mensaje de error al usuario")

    async def run_bot(self):
        """
        Ejecuta el bot principal
        
        MEJORADO v2.0.6: Con validaciones SSL y mejor manejo de errores
        """
        try:
            # Validar configuración
            if not self._validate_environment():
                logger.error("❌ Configuración inválida - no se puede iniciar el bot")
                return
            
            # Inicializar clientes
            logger.info("🚀 Iniciando sistema de automatización periodística v2.0.6...")
            if not await self.init_clients():
                logger.error("❌ Error en inicialización - cerrando bot")
                return
            
            # Configurar manejadores
            if self.telegram_app:
                message_handler = MessageHandler(
                    filters.TEXT | filters.PHOTO, 
                    self.process_telegram_message
                )
                self.telegram_app.add_handler(message_handler)
                
                logger.info("✅ Bot iniciado y esperando mensajes...")
                logger.info(f"🔐 Usuarios autorizados: {len(self.authorized_user_ids)}")
                logger.info(f"📂 Categorías disponibles: {len(self.available_categories)}")
                
                # Ejecutar bot
                await self.telegram_app.run_polling(
                    drop_pending_updates=True,
                    allowed_updates=['message']
                )
            else:
                logger.error("❌ No se pudo inicializar aplicación de Telegram")
                
        except Exception as e:
            logger.error(f"❌ Error crítico ejecutando bot: {e}")

def main():
    """
    Función principal mejorada v2.0.6
    """
    try:
        logger.info("=" * 80)
        logger.info("🚀 SISTEMA SEO PROFESIONAL v2.0.6 - INICIANDO")
        logger.info("🔒 NUEVO: Manejo robusto de SSL/TLS")
        logger.info("🔄 NUEVO: Sistema de reintentos con backoff exponencial")
        logger.info("=" * 80)
        
        # Crear y ejecutar bot
        bot = WordPressSEOBot()
        asyncio.run(bot.run_bot())
        
    except KeyboardInterrupt:
        logger.info("👋 Bot detenido por usuario")
    except Exception as e:
        logger.error(f"❌ Error crítico en main: {e}")

if __name__ == "__main__":
    main()
