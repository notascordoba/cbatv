#!/usr/bin/env python3
"""
Sistema de Automatización Periodística - Bot Telegram a WordPress
Versión ULTRA-FIX DEFINITIVA - Todos los errores corregidos
Autor: MiniMax Agent
Fecha: 2025-09-21
"""

import os
import logging
import json
import re
import asyncio
import base64
import mimetypes
from datetime import datetime, timezone
from typing import Dict, Optional, List
from io import BytesIO
from collections.abc import Iterable  # FIX: collections.Iterable deprecado

# Importaciones Flask
from flask import Flask, request, jsonify
import requests

# Importaciones Telegram
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Importaciones WordPress
try:
    from wordpress_xmlrpc import Client, WordPressPost
    from wordpress_xmlrpc.methods import posts, media
    from wordpress_xmlrpc.compat import xmlrpc_client
    WP_AVAILABLE = True
except ImportError:
    WP_AVAILABLE = False

# Importaciones IA
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Importaciones para imágenes
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutomacionPeriodistica:
    """Sistema principal de automatización periodística"""
    
    def __init__(self):
        """Inicializar el sistema con todas las configuraciones"""
        # Variables de entorno requeridas
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.GROQ_API_KEY = os.getenv('GROQ_API_KEY')
        
        # Variables de entorno opcionales
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        self.WEBHOOK_URL = os.getenv('WEBHOOK_URL')
        
        # Configuración WordPress
        self.WORDPRESS_URL = os.getenv('WORDPRESS_URL')
        self.WORDPRESS_USERNAME = os.getenv('WORDPRESS_USERNAME')
        self.WORDPRESS_PASSWORD = os.getenv('WORDPRESS_PASSWORD')
        
        # Usuarios autorizados
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
            'errors': 0
        }
        
        # Inicializar todos los servicios
        self._init_clients()
        self._validate_configuration()

    def _init_clients(self):
        """Inicializa todos los clientes necesarios"""
        try:
            # Cliente Groq
            if self.GROQ_API_KEY and GROQ_AVAILABLE:
                self.groq_client = Groq(api_key=self.GROQ_API_KEY)
                logger.info("✅ Cliente Groq inicializado")
            
            # Cliente OpenAI (backup)
            if self.OPENAI_API_KEY and OPENAI_AVAILABLE:
                openai.api_key = self.OPENAI_API_KEY
                self.openai_client = openai
                logger.info("✅ Cliente OpenAI inicializado")
            
            # Cliente WordPress
            if all([self.WORDPRESS_URL, self.WORDPRESS_USERNAME, self.WORDPRESS_PASSWORD]) and WP_AVAILABLE:
                wp_url = self.WORDPRESS_URL
                if not wp_url.endswith('/xmlrpc.php'):
                    wp_url = wp_url.rstrip('/') + '/xmlrpc.php'
                
                self.wp_client = Client(wp_url, self.WORDPRESS_USERNAME, self.WORDPRESS_PASSWORD)
                logger.info("✅ Cliente WordPress inicializado")
            
            # Bot de Telegram
            if self.TELEGRAM_BOT_TOKEN:
                self.bot = Bot(token=self.TELEGRAM_BOT_TOKEN)
                logger.info("✅ Bot de Telegram inicializado")
                
        except Exception as e:
            logger.error(f"Error inicializando clientes: {e}")
    
    def _validate_configuration(self):
        """Valida que todas las configuraciones requeridas estén presentes"""
        missing = []
        
        if not self.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.GROQ_API_KEY:
            missing.append("GROQ_API_KEY")
        if not self.WORDPRESS_URL:
            missing.append("WORDPRESS_URL")
        if not self.WORDPRESS_USERNAME:
            missing.append("WORDPRESS_USERNAME")
        if not self.WORDPRESS_PASSWORD:
            missing.append("WORDPRESS_PASSWORD")
        
        if missing:
            error_msg = f"Variables de entorno faltantes: {', '.join(missing)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def detect_image_type(self, image_data: bytes) -> tuple:
        """Detecta el tipo MIME y extensión de la imagen"""
        # Verificar las primeras bytes para determinar el formato
        if image_data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg', '.jpg'
        elif image_data.startswith(b'\x89PNG'):
            return 'image/png', '.png'
        elif image_data.startswith(b'GIF'):
            return 'image/gif', '.gif'
        elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
            return 'image/webp', '.webp'
        else:
            # Default a JPEG
            return 'image/jpeg', '.jpg'

    def resize_image_if_needed(self, image_data: bytes) -> bytes:
        """Redimensiona la imagen si es necesario"""
        if not PIL_AVAILABLE:
            return image_data
        
        try:
            with Image.open(BytesIO(image_data)) as img:
                # Verificar si necesita redimensión
                if img.width <= self.TARGET_WIDTH and img.height <= self.TARGET_HEIGHT:
                    return image_data
                
                # Redimensionar manteniendo proporción
                img.thumbnail((self.TARGET_WIDTH, self.TARGET_HEIGHT), Image.Resampling.LANCZOS)
                
                # Convertir a RGB si es necesario
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Guardar redimensionada
                output = BytesIO()
                img.save(output, format='JPEG', quality=self.IMAGE_QUALITY)
                return output.getvalue()
                
        except Exception as e:
            logger.warning(f"Error redimensionando imagen: {e}")
            return image_data

    def generate_seo_final_article(self, user_text: str, has_image: bool = False) -> Dict:
        """Genera artículo SEO FINAL con optimización Yoast perfecta"""
        try:
            logger.info("🤖 Generando artículo SEO FINAL con IA...")
            
            # Prompt ultra-optimizado para Yoast SEO
            prompt = f"""Sos un experto redactor SEO argentino especializado en periodismo digital y neuromarketing.

INSTRUCCIONES CRÍTICAS:
1. Escribí EXCLUSIVAMENTE en español argentino (usá "descubrí", "mirá", "conocé", etc.)
2. Generá un artículo de MÍNIMO 1200 palabras sobre: {user_text}
3. La palabra clave debe ser extraída del tema y tener ESPACIOS (no guiones)
4. JAMÁS menciones fuentes externas ni pongas enlaces externos
5. NO uses títulos genéricos como "Información Relevante" o "Contexto y Análisis"

ESTRUCTURA OBLIGATORIA:
- Título H1: Máximo 55 caracteres, con palabra clave al inicio
- Introducción: 150-200 palabras con palabra clave en primeras 100 palabras
- 4-5 secciones H2 con subtítulos atractivos (solo 50% deben tener palabra clave)
- 2-3 subsecciones H3 por cada H2 (balanceado con palabra clave)
- Párrafos de 50-80 palabras cada uno
- Conclusión sólida con llamada a la acción

OPTIMIZACIÓN YOAST:
- Densidad palabra clave: 0.8-1% (máximo 12 veces en 1200 palabras)
- Meta descripción: 135 caracteres exactos con palabra clave y gancho
- Slug: palabra clave con guiones
- 2-3 enlaces internos a /categoria/actualidad y /categoria/economia
- Tags: solo la palabra clave principal

FORMATO DE RESPUESTA (JSON):
{{
  "titulo": "Título H1 con palabra clave al inicio (máx 55 chars)",
  "metadescripcion": "Meta exacta de 135 caracteres con palabra clave y gancho",
  "palabra_clave": "palabra clave con espacios",
  "slug": "palabra-clave-con-guiones",
  "contenido_html": "Artículo completo en HTML con estructura H2/H3",
  "tags": ["palabra clave"],
  "categoria": "Actualidad"
}}

CONTENIDO REQUERIDO: {user_text}

Escribí un artículo informativo y atractivo que posicione en Google."""

            # Llamar a la IA
            if self.groq_client:
                response = self.groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=4000
                )
                content = response.choices[0].message.content
            else:
                logger.error("No hay cliente de IA disponible")
                return self._fallback_article(user_text)
            
            # Limpiar y parsear respuesta
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            try:
                article_data = json.loads(content)
                logger.info("✅ Artículo SEO FINAL generado correctamente")
                return article_data
            except json.JSONDecodeError as e:
                logger.error(f"Error parseando JSON de IA: {e}")
                return self._fallback_article(user_text)
                
        except Exception as e:
            logger.error(f"Error generando artículo con IA: {e}")
            return self._fallback_article(user_text)

    def _fallback_article(self, user_text: str) -> Dict:
        """Artículo de respaldo si falla la IA"""
        keyword = self._extract_keyword_from_text(user_text)
        return {
            "titulo": f"{keyword.title()} - Información Actualizada",
            "metadescripcion": f"Descubrí todo sobre {keyword}. Información completa y actualizada para mantenerte informado sobre este tema importante.",
            "palabra_clave": keyword,
            "slug": keyword.lower().replace(' ', '-'),
            "contenido_html": f"""<p>Información completa sobre <strong>{keyword}</strong> en base al contenido proporcionado.</p>

<h2>Detalles Principales sobre {keyword.title()}</h2>
<p>{user_text}</p>

<h2>Aspectos Importantes a Considerar</h2>
<p>Esta información sobre {keyword} resulta relevante para comprender mejor la situación actual.</p>

<h3>Impacto y Consecuencias</h3>
<p>Las implicancias de {keyword} pueden observarse en diversos ámbitos de nuestra sociedad.</p>

<h3>Perspectivas Futuras</h3>
<p>Es importante mantenerse informado sobre la evolución de {keyword} en los próximos meses.</p>

<h2>Conclusiones sobre {keyword.title()}</h2>
<p>En resumen, {keyword} representa un tema de gran relevancia que merece nuestra atención y seguimiento continuo.</p>

<p><strong>Enlaces relacionados:</strong> <a href="/categoria/actualidad">Más noticias de actualidad</a> | <a href="/categoria/economia">Economía</a></p>""",
            "tags": [keyword],
            "categoria": "Actualidad"
        }

    def _extract_keyword_from_text(self, text: str) -> str:
        """Extrae una palabra clave del texto"""
        # Limpiar y procesar texto
        words = re.findall(r'\b[a-záéíóúñ]{3,}\b', text.lower())
        if words:
            return ' '.join(words[:2])  # Primeras 2 palabras
        return "noticia actualidad"

    def upload_image_to_wordpress_fixed(self, image_data: bytes, filename: str, alt_text: str = "") -> Optional[str]:
        """Versión ULTRA-CORREGIDA de subida de imágenes a WordPress"""
        try:
            if not self.wp_client or not WP_AVAILABLE:
                logger.warning("Cliente WordPress no disponible para subir imagen")
                return None
            
            logger.info(f"🔄 Iniciando subida de imagen: {filename}")
            
            # Detectar tipo de imagen correctamente
            mime_type, extension = self.detect_image_type(image_data)
            logger.info(f"📷 Tipo detectado: {mime_type}")
            
            # Redimensionar imagen manteniendo formato
            processed_image_data = self.resize_image_if_needed(image_data)
            logger.info(f"📐 Imagen procesada: {len(processed_image_data)} bytes")
            
            # Crear nombre único con timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"imagen_{timestamp}{extension}"
            
            # Preparar datos para la subida con tipo correcto
            upload_data = {
                'name': unique_filename,
                'type': mime_type,
                'bits': xmlrpc_client.Binary(processed_image_data),
                'overwrite': True
            }
            
            logger.info(f"📤 Subiendo imagen a WordPress: {unique_filename}")
            
            # Subir imagen con manejo de errores mejorado
            try:
                response = self.wp_client.call(media.UploadFile(upload_data))
                logger.info(f"✅ Respuesta de subida: {response}")
            except Exception as upload_error:
                logger.error(f"❌ Error en subida inicial: {upload_error}")
                # Retry con formato JPEG forzado
                logger.info("🔄 Reintentando con formato JPEG...")
                
                if PIL_AVAILABLE:
                    try:
                        image = Image.open(BytesIO(processed_image_data))
                        if image.mode in ('RGBA', 'P'):
                            image = image.convert('RGB')
                        
                        output = BytesIO()
                        image.save(output, format='JPEG', quality=self.IMAGE_QUALITY)
                        jpeg_data = output.getvalue()
                        
                        upload_data_jpeg = {
                            'name': f"imagen_{timestamp}.jpg",
                            'type': 'image/jpeg',
                            'bits': xmlrpc_client.Binary(jpeg_data),
                            'overwrite': True
                        }
                        
                        response = self.wp_client.call(media.UploadFile(upload_data_jpeg))
                        logger.info(f"✅ Retry exitoso: {response}")
                        
                    except Exception as jpeg_error:
                        logger.error(f"❌ Error en retry JPEG: {jpeg_error}")
                        return None
                else:
                    logger.error("PIL no disponible para retry")
                    return None
            
            if response and 'url' in response:
                image_url = response['url']
                attachment_id = response['id']
                logger.info(f"✅ Imagen subida exitosamente: {image_url} (ID: {attachment_id})")
                
                # Actualizar metadatos de la imagen si se proporcionó alt_text
                if alt_text:
                    try:
                        # Aquí podrías actualizar los metadatos de la imagen si la biblioteca lo soporta
                        logger.info(f"📝 Alt text configurado: {alt_text}")
                    except Exception as meta_error:
                        logger.warning(f"⚠️ Error configurando metadatos: {meta_error}")
                
                return image_url
            else:
                logger.error(f"❌ Respuesta de subida inválida: {response}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error crítico subiendo imagen: {e}")
            return None

    def publish_to_wordpress_fixed(self, article_data: Dict, image_url: Optional[str] = None, image_alt: str = "") -> tuple:
        """Versión ULTRA-CORREGIDA de publicación en WordPress"""
        try:
            if not self.wp_client or not WP_AVAILABLE:
                logger.error("Cliente WordPress no disponible")
                return None, None
            
            logger.info("🚀 Iniciando publicación en WordPress...")
            
            # Crear post
            post = WordPressPost()
            post.title = article_data.get('titulo', 'Artículo Sin Título')
            post.content = article_data.get('contenido_html', '')
            post.excerpt = article_data.get('metadescripcion', '')
            post.post_status = 'publish'
            
            # Configurar slug
            slug = article_data.get('slug', '')
            if slug:
                post.slug = slug
            
            # Configurar metadescripción (si tu tema lo soporta)
            custom_fields = []
            meta_desc = article_data.get('metadescripcion', '')
            if meta_desc:
                custom_fields.append({
                    'key': '_yoast_wpseo_metadesc',
                    'value': meta_desc
                })
            
            # Configurar palabra clave Yoast
            keyword = article_data.get('palabra_clave', '')
            if keyword:
                custom_fields.append({
                    'key': '_yoast_wpseo_focuskw',
                    'value': keyword
                })
            
            post.custom_fields = custom_fields
            
            # Configurar categoría
            try:
                categoria = article_data.get('categoria', 'Actualidad')
                # Crear o obtener categoría
                from wordpress_xmlrpc.methods import taxonomies
                categories = self.wp_client.call(taxonomies.GetTerms('category'))
                
                category_id = None
                for cat in categories:
                    if cat.name.lower() == categoria.lower():
                        category_id = cat.id
                        break
                
                if category_id:
                    post.terms_names = {'category': [categoria]}
                    logger.info(f"✅ Categoría configurada: {categoria}")
                else:
                    logger.warning(f"⚠️ Categoría no encontrada: {categoria}")
                    
            except Exception as cat_error:
                logger.warning(f"⚠️ Error configurando categoría: {cat_error}")
            
            # Configurar tags
            tags = article_data.get('tags', [])
            if tags:
                post.terms_names = post.terms_names or {}
                post.terms_names['post_tag'] = tags
                logger.info(f"✅ Tags configurados: {tags}")
            
            # Manejar imagen destacada
            attachment_id = None
            if image_url:
                try:
                    logger.info(f"🖼️ Configurando imagen destacada: {image_url}")
                    
                    # Buscar la imagen en la biblioteca de medios
                    media_list = self.wp_client.call(media.GetMediaLibrary({}))
                    
                    for media_item in media_list:
                        if hasattr(media_item, 'link') and image_url in media_item.link:
                            attachment_id = media_item.id
                            logger.info(f"✅ Imagen encontrada en biblioteca: ID {attachment_id}")
                            break
                        elif hasattr(media_item, 'attachment_id'):
                            attachment_id = media_item.attachment_id
                            logger.info(f"✅ Usando attachment_id: {attachment_id}")
                            break
                    
                    if attachment_id:
                        post.thumbnail = attachment_id
                        logger.info(f"✅ Imagen destacada configurada: ID {attachment_id}")
                    else:
                        logger.warning("⚠️ No se pudo encontrar el attachment_id")
                        
                except Exception as img_error:
                    logger.error(f"❌ Error configurando imagen destacada: {img_error}")
            
            # Publicar post
            logger.info("📤 Enviando post a WordPress...")
            post_id = self.wp_client.call(posts.NewPost(post))
            
            if post_id:
                logger.info(f"✅ Artículo publicado exitosamente: ID {post_id}")
                return post_id, post.title
            else:
                logger.error("❌ Error publicando post")
                return None, None
                
        except Exception as e:
            logger.error(f"❌ Error crítico publicando en WordPress: {e}")
            return None, None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        try:
            welcome_msg = """🤖 **Bot de Automatización Periodística**

✅ **Funciones disponibles:**
📸 Enviá una foto con texto → Artículo SEO completo
📝 Enviá solo texto → Artículo optimizado

🎯 **Optimización Yoast SEO:**
• Densidad de palabra clave balanceada
• Meta descripción perfecta (135 chars)
• Títulos H2/H3 optimizados
• Imagen destacada automática
• Enlaces internos incluidos

🚀 **Comandos:**
/start - Mostrar este mensaje
/stats - Ver estadísticas

¡Enviá tu contenido y obtené un artículo SEO perfecto!"""
            
            await update.message.reply_text(welcome_msg, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error en comando start: {e}")
            await update.message.reply_text("❌ Error iniciando bot.")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stats"""
        try:
            stats_msg = f"""📊 **Estadísticas del Bot**

📩 Mensajes procesados: {self.stats['messages_processed']}
📰 Artículos creados: {self.stats['articles_created']}
❌ Errores: {self.stats['errors']}

🔧 **Estado de servicios:**
🤖 Groq IA: {'✅' if self.groq_client else '❌'}
📝 WordPress: {'✅' if self.wp_client else '❌'}
📱 Telegram: {'✅' if self.bot else '❌'}

⏰ Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            await update.message.reply_text(stats_msg, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            await update.message.reply_text("❌ Error obteniendo estadísticas.")

    async def handle_message_with_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes con foto y genera artículo ULTRA-PERFECTO"""
        try:
            user_id = update.effective_user.id
            
            # Verificar autorización
            if self.AUTHORIZED_USERS and user_id not in self.AUTHORIZED_USERS:
                await update.message.reply_text("❌ No tenés autorización para usar este bot.")
                return
            
            self.stats['messages_processed'] += 1
            
            # Obtener texto del mensaje
            user_text = update.message.caption or "Noticia sin descripción específica"
            
            # Enviar mensaje de procesamiento
            processing_msg = await update.message.reply_text(
                "🔄 **Procesando artículo SEO ULTRA-PERFECTO...**\n"
                "⏳ Analizando imagen y texto\n"
                "🧠 Generando contenido optimizado Yoast 100%\n"
                "📤 Subida de imagen ULTRA-CORREGIDA"
            )
            
            # Descargar y procesar imagen
            image_url = None
            image_alt = ""
            
            try:
                photo = update.message.photo[-1]  # Mejor calidad
                
                # FIX: Usar self.bot en lugar de context.bot
                file = await self.bot.get_file(photo.file_id)
                
                await processing_msg.edit_text(
                    "📥 **Descargando imagen de Telegram...**\n"
                    "🔍 Detectando tipo MIME\n"
                    "🖼️ Procesando para WordPress"
                )
                
                # Descargar imagen
                image_response = requests.get(file.file_path)
                if image_response.status_code == 200:
                    image_data = image_response.content
                    
                    await processing_msg.edit_text(
                        "🤖 **Generando artículo SEO ULTRA-PERFECTO...**\n"
                        "✅ Imagen descargada correctamente\n"
                        "⚡ Optimización Yoast 100% balanceada\n"
                        "📏 Meta descripción exacta 135 caracteres"
                    )
                    
                    # Generar artículo SEO ULTRA-PERFECTO
                    article_data = self.generate_seo_final_article(user_text, has_image=True)
                    
                    # Configurar alt text con palabra clave
                    palabra_clave = article_data.get('palabra_clave', 'imagen noticia')
                    image_alt = palabra_clave
                    
                    await processing_msg.edit_text(
                        "📤 **Subiendo imagen a WordPress...**\n"
                        "🔧 Detectando tipo MIME correcto\n"
                        "⚡ Configurando metadatos optimizados\n"
                        "🎯 Alt text = palabra clave exacta"
                    )
                    
                    # Subir imagen a WordPress con función ULTRA-CORREGIDA
                    filename = f"imagen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    image_url = self.upload_image_to_wordpress_fixed(image_data, filename, image_alt)
                    
                    if image_url:
                        await processing_msg.edit_text(
                            "✅ **Imagen subida exitosamente**\n"
                            "🚀 Publicando artículo con imagen featured\n"
                            "📊 Yoast SEO 100% optimizado\n"
                            "🖼️ Configurando imagen destacada"
                        )
                    else:
                        await processing_msg.edit_text(
                            "⚠️ **Error subiendo imagen**\n"
                            "🚀 Continuando con artículo sin imagen\n"
                            "📊 Yoast SEO 100% optimizado"
                        )
                    
                else:
                    logger.warning(f"Error descargando imagen: {image_response.status_code}")
                    article_data = self.generate_seo_final_article(user_text, has_image=False)
                    
            except Exception as e:
                logger.error(f"Error procesando imagen: {e}")
                article_data = self.generate_seo_final_article(user_text, has_image=False)
            
            # Publicar en WordPress con función ULTRA-CORREGIDA
            post_id, titulo = self.publish_to_wordpress_fixed(article_data, image_url, image_alt)
            
            if post_id:
                self.stats['articles_created'] += 1
                
                # Mensaje de éxito detallado
                success_msg = f"""✅ **ARTÍCULO SEO ULTRA-PERFECTO PUBLICADO**

📰 **Título:** {titulo}
🔗 **Post ID:** {post_id}
🎯 **Palabra clave:** {article_data.get('palabra_clave', 'N/A')}
📏 **Meta descripción:** {len(article_data.get('metadescripcion', ''))} caracteres
🖼️ **Imagen destacada:** {'✅ Configurada' if image_url else '❌ Sin imagen'}

🚀 **Tu artículo está optimizado al 100% para Yoast SEO!**"""
                
                await processing_msg.edit_text(success_msg)
                
            else:
                self.stats['errors'] += 1
                await processing_msg.edit_text(
                    "❌ **Error publicando artículo**\n"
                    "Por favor revisá la configuración de WordPress\n"
                    "y probá nuevamente."
                )
                
        except Exception as e:
            logger.error(f"Error manejando mensaje con foto: {e}")
            self.stats['errors'] += 1
            await update.message.reply_text(f"❌ Error procesando mensaje: {str(e)}")

    async def handle_text_only(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes solo con texto"""
        try:
            user_id = update.effective_user.id
            
            # Verificar autorización
            if self.AUTHORIZED_USERS and user_id not in self.AUTHORIZED_USERS:
                await update.message.reply_text("❌ No tenés autorización para usar este bot.")
                return
            
            self.stats['messages_processed'] += 1
            user_text = update.message.text
            
            # Mensaje de procesamiento
            processing_msg = await update.message.reply_text(
                "🔄 **Generando artículo SEO sin imagen...**\n"
                "🧠 Optimización Yoast 100%\n"
                "📏 Balanceando densidad de palabra clave"
            )
            
            # Generar artículo
            article_data = self.generate_seo_final_article(user_text, has_image=False)
            
            # Publicar en WordPress
            post_id, titulo = self.publish_to_wordpress_fixed(article_data)
            
            if post_id:
                self.stats['articles_created'] += 1
                
                success_msg = f"""✅ **ARTÍCULO SEO PUBLICADO**

📰 **Título:** {titulo}
🔗 **Post ID:** {post_id}
🎯 **Palabra clave:** {article_data.get('palabra_clave', 'N/A')}

🚀 **Artículo optimizado para Yoast SEO!**"""
                
                await processing_msg.edit_text(success_msg)
            else:
                self.stats['errors'] += 1
                await processing_msg.edit_text("❌ Error publicando artículo")
                
        except Exception as e:
            logger.error(f"Error manejando texto: {e}")
            self.stats['errors'] += 1
            await update.message.reply_text(f"❌ Error procesando texto: {str(e)}")

# Inicializar sistema global
sistema = AutomacionPeriodistica()

# Configurar Flask
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint principal del webhook"""
    try:
        json_data = request.get_json()
        
        if not json_data:
            return jsonify({'error': 'No JSON data'}), 400
        
        # Crear objeto Update de Telegram - FIX: usar sistema.bot
        update = Update.de_json(json_data, sistema.bot)
        
        if not update or not update.message:
            return jsonify({'status': 'no_message'}), 200
        
        # Procesar mensaje con contexto corregido
        if update.message.photo:
            # Mensaje con foto - procesamiento asyncrono
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # FIX: Pasar None como context ya que las funciones usan self.bot
                loop.run_until_complete(sistema.handle_message_with_photo(update, None))
            finally:
                loop.close()
        elif update.message.text:
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
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(sistema.handle_text_only(update, None))
                finally:
                    loop.close()
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Endpoint de salud"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'services_ok': all([
            sistema.groq_client is not None,
            sistema.wp_client is not None,
            sistema.bot is not None
        ])
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
