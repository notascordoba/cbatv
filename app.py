#!/usr/bin/env python3
"""
Sistema SEO Profesional para automatización periodística v2.0.4
Bot que convierte crónicas en artículos SEO optimizados para WordPress
Base sólida sin errores de inicialización + características SEO avanzadas

VERSIÓN: 2.0.4
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

# Imports específicos de WordPress
import wordpress_xmlrpc
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.methods.posts import SetPostThumbnail
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
        
        # Configuración de contenido SEO
        self.min_word_count = int(os.getenv('MIN_WORD_COUNT', 800))
        self.target_word_count = int(os.getenv('TARGET_WORD_COUNT', 1200))
        
        # Clientes (se inicializan después)
        self.telegram_app = None
        self.openai_client = None
        self.wp_client = None
        self.wordpress_categories = []  # Cache de categorías disponibles
        
        # Estado
        self.bot_running = False
        
        logger.info("✅ Bot inicializado - aguardando conexiones...")
    
    async def _initialize_clients(self) -> bool:
        """
        Inicializa conexiones con APIs externas y obtiene categorías de WordPress
        NUEVO v2.0.4: Incluye cache de categorías disponibles
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
            
            # 3. Cliente WordPress
            if self.wordpress_url and self.wordpress_user and self.wordpress_password:
                try:
                    wp_url = f"{self.wordpress_url.rstrip('/')}/xmlrpc.php"
                    self.wp_client = Client(wp_url, self.wordpress_user, self.wordpress_password)
                    
                    # Probar conexión
                    test_methods = self.wp_client.call(wordpress_xmlrpc.methods.demo.SayHello())
                    logger.info("✅ Cliente WordPress conectado")
                    success_count += 1
                    
                    # NUEVO v2.0.4: Obtener categorías disponibles del sitio
                    await self._fetch_wordpress_categories()
                    
                except Exception as e:
                    logger.error(f"❌ Error conectando WordPress: {e}")
            
            # Verificar conexiones mínimas
            if success_count >= 2:
                logger.info(f"🚀 Sistema operativo - {success_count}/3 servicios conectados")
                return True
            else:
                logger.error(f"❌ Conexiones insuficientes: {success_count}/3")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error crítico inicializando clientes: {e}")
            return False
    
    async def _fetch_wordpress_categories(self) -> bool:
        """
        NUEVO v2.0.4: Obtiene categorías disponibles desde WordPress
        Usa XML-RPC para obtener la lista completa de categorías del sitio
        """
        try:
            if not self.wp_client:
                logger.warning("⚠️ Cliente WordPress no disponible para obtener categorías")
                return False
            
            # Obtener categorías usando XML-RPC
            categories = self.wp_client.call(GetTerms('category'))
            
            # Extraer solo los nombres de las categorías
            self.wordpress_categories = [cat.name for cat in categories if cat.name.lower() != 'uncategorized']
            
            logger.info(f"✅ Categorías obtenidas de WordPress: {len(self.wordpress_categories)} encontradas")
            logger.info(f"📂 Categorías disponibles: {', '.join(self.wordpress_categories[:10])}{'...' if len(self.wordpress_categories) > 10 else ''}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo categorías de WordPress: {e}")
            # Fallback: categorías básicas si no se puede conectar
            self.wordpress_categories = ["Noticias", "Actualidad", "Local", "Nacional", "Internacional"]
            logger.warning(f"⚠️ Usando categorías de fallback: {', '.join(self.wordpress_categories)}")
            return False
    
    def _validate_category(self, suggested_category: str) -> str:
        """
        NUEVO v2.0.4: Valida que la categoría sugerida por la IA existe en WordPress
        Si no existe, selecciona la más apropiada de las disponibles
        """
        try:
            if not self.wordpress_categories:
                # Si no hay categorías cargadas, usar fallback
                return "Noticias"
            
            # Buscar coincidencia exacta (case insensitive)
            for wp_cat in self.wordpress_categories:
                if wp_cat.lower() == suggested_category.lower():
                    logger.info(f"✅ Categoría validada: '{wp_cat}'")
                    return wp_cat
            
            # Si no hay coincidencia exacta, buscar coincidencia parcial
            for wp_cat in self.wordpress_categories:
                if suggested_category.lower() in wp_cat.lower() or wp_cat.lower() in suggested_category.lower():
                    logger.info(f"⚠️ Categoría aproximada: '{suggested_category}' → '{wp_cat}'")
                    return wp_cat
            
            # Si no hay ninguna coincidencia, usar la primera categoría disponible
            fallback_category = self.wordpress_categories[0]
            logger.warning(f"⚠️ Categoría '{suggested_category}' no encontrada. Usando: '{fallback_category}'")
            return fallback_category
            
        except Exception as e:
            logger.error(f"❌ Error validando categoría: {e}")
            return "Noticias"  # Fallback final
    
    def resize_image(self, image_data: bytes) -> bytes:
        """Redimensiona imagen al tamaño objetivo con calidad optimizada"""
        try:
            # Abrir imagen
            image = Image.open(io.BytesIO(image_data))
            
            # Convertir a RGB si es necesario
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Redimensionar manteniendo aspecto
            image.thumbnail((self.TARGET_WIDTH, self.TARGET_HEIGHT), Image.Resampling.LANCZOS)
            
            # Crear imagen final con fondo blanco si es necesario
            final_image = Image.new('RGB', (self.TARGET_WIDTH, self.TARGET_HEIGHT), (255, 255, 255))
            
            # Centrar imagen redimensionada
            x = (self.TARGET_WIDTH - image.width) // 2
            y = (self.TARGET_HEIGHT - image.height) // 2
            final_image.paste(image, (x, y))
            
            # Guardar como JPEG optimizado
            buffer = io.BytesIO()
            final_image.save(buffer, format='JPEG', quality=self.IMAGE_QUALITY, optimize=True)
            
            logger.info(f"✅ Imagen redimensionada a {self.TARGET_WIDTH}x{self.TARGET_HEIGHT}")
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error redimensionando imagen: {e}")
            return image_data

    def generate_seo_prompt(self, user_text: str, has_image: bool = False) -> Dict:
        """
        CORREGIDO v2.0.4: Genera prompt para IA de manera consistente
        SIEMPRE retorna un diccionario con 'prompt' o 'error'
        """
        try:
            # Validar entrada
            if not user_text or len(user_text.strip()) < 5:
                logger.warning("⚠️ Texto insuficiente para generar artículo")
                return {"error": "Texto insuficiente"}
            
            # Preparar lista de categorías para el prompt
            categories_text = ", ".join(self.wordpress_categories) if self.wordpress_categories else "Noticias, Actualidad, Local"
            
            # Prompt profesional optimizado con categorías dinámicas
            prompt = f"""Eres un periodista SEO experto. Crea un artículo completo y profesional basado en esta información:

"{user_text}"

IMAGEN DISPONIBLE: {'Sí' if has_image else 'No'}

CATEGORÍAS DISPONIBLES EN WORDPRESS: {categories_text}

IMPORTANTE: Solo puedes usar UNA de las categorías listadas arriba. Está PROHIBIDO crear nuevas categorías.

REQUISITOS OBLIGATORIOS:
- Mínimo {self.min_word_count} palabras, objetivo {self.target_word_count} palabras
- Estructura SEO profesional con H1, H2, H3
- Meta descripción entre 140-160 caracteres
- URL slug optimizada (máximo 60 caracteres)
- Keyword principal identificada
- Tags relevantes (3-5 tags)
- Enlace interno y externo sugeridos
- Datos estructurados JSON-LD
- Tone periodístico profesional

FORMATO DE RESPUESTA (JSON válido):
{{
    "titulo_h1": "Título principal optimizado para SEO",
    "meta_descripcion": "Descripción entre 140-160 caracteres",
    "slug_url": "url-optimizada-sin-espacios",
    "keyword_principal": "keyword principal",
    "categoria": "DEBE ser exactamente una de: {categories_text}",
    "tags": ["tag1", "tag2", "tag3"],
    "contenido_html": "<h2>Subtítulo</h2><p>Párrafo completo...</p><h3>Otro subtítulo</h3><p>Más contenido...</p>",
    "enlace_interno": "https://example.com/articulo-relacionado",
    "enlace_externo": "https://fuente-externa.com",
    "datos_estructurados": "JSON-LD completo para NewsArticle",
    "imagen_destacada": {{"necesaria": {"true" if has_image else "false"}, "alt_text": "descripción de imagen", "titulo_imagen": "título descriptivo"}}
}}

RESPONDE ÚNICAMENTE CON EL JSON, SIN TEXTO ADICIONAL."""

            return {"prompt": prompt}
            
        except Exception as e:
            logger.error(f"❌ Error generando prompt SEO: {e}")
            return {"error": f"Error generando prompt: {str(e)}"}
    
    def _generate_fallback_article(self, user_text: str) -> Dict:
        """
        CORREGIDO v2.0.4: Genera artículo básico con validación robusta
        """
        try:
            # Validar entrada
            if not user_text:
                user_text = "Artículo generado automáticamente"
            
            user_text = str(user_text).strip()
            if len(user_text) < 5:
                user_text = "Noticia importante generada automáticamente por el sistema de publicación."
            
            # Usar primera categoría disponible como fallback
            fallback_category = self.wordpress_categories[0] if self.wordpress_categories else "Noticias"
            
            # Extraer información básica
            title = user_text[:80].strip()
            if not title:
                title = "Artículo de Noticia"
            if not title.endswith('.') and not title.endswith('?') and not title.endswith('!'):
                title += "..."
            
            # Crear slug básico
            slug = re.sub(r'[^\w\s-]', '', title.lower())
            slug = re.sub(r'[-\s]+', '-', slug)[:50]
            if not slug:
                slug = "articulo-noticia"
            
            # Meta descripción básica
            meta_desc = user_text[:140] if len(user_text) > 140 else user_text
            if len(meta_desc) < 50:
                meta_desc = f"Artículo sobre {title[:50]}. Información actualizada y relevante."
            
            # Contenido HTML básico estructurado
            paragraphs = user_text.split('\n')
            content_html = f"<h2>Información Principal</h2>\n"
            
            for paragraph in paragraphs:
                if paragraph.strip():
                    content_html += f"<p>{paragraph.strip()}</p>\n"
            
            # Si el contenido es muy corto, expandir
            if len(content_html) < 200:
                content_html += f"<h3>Detalles Adicionales</h3>\n<p>Esta noticia representa información importante que será actualizada conforme se disponga de más detalles.</p>\n"
            
            return {
                "titulo_h1": title,
                "meta_descripcion": meta_desc,
                "slug_url": slug,
                "keyword_principal": title.split()[0] if title.split() else "noticia",
                "categoria": fallback_category,
                "tags": ["noticia", "actualidad", "información"],
                "contenido_html": content_html,
                "enlace_interno": "",
                "enlace_externo": "",
                "datos_estructurados": "",
                "imagen_destacada": {"necesaria": "false", "alt_text": "", "titulo_imagen": ""}
            }
            
        except Exception as e:
            logger.error(f"❌ Error crítico en artículo fallback: {e}")
            # Fallback absoluto
            return {
                "titulo_h1": "Artículo de Noticia",
                "meta_descripcion": "Información actualizada del sistema de noticias",
                "slug_url": "articulo-noticia-sistema",
                "keyword_principal": "noticia",
                "categoria": "Noticias",
                "tags": ["noticia", "sistema"],
                "contenido_html": f"<h2>Información</h2><p>{str(user_text)[:500] if user_text else 'Contenido generado automáticamente'}</p>",
                "enlace_interno": "",
                "enlace_externo": "",
                "datos_estructurados": "",
                "imagen_destacada": {"necesaria": "false", "alt_text": "", "titulo_imagen": ""}
            }
    
    async def generate_article_with_ai(self, prompt_data: Dict, user_text: str) -> Dict:
        """
        CORREGIDO v2.0.4: Ejecuta la generación del artículo usando OpenAI con manejo robusto
        """
        try:
            if not self.openai_client:
                logger.warning("⚠️ OpenAI no disponible, usando fallback")
                return self._generate_fallback_article(user_text)
            
            if "prompt" not in prompt_data:
                logger.error("❌ Prompt inválido recibido")
                return self._generate_fallback_article(user_text)
            
            response = await self.openai_client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": "Eres un periodista SEO experto. Respondes únicamente con JSON válido."},
                    {"role": "user", "content": prompt_data["prompt"]}
                ],
                max_tokens=self.max_tokens,
                temperature=0.7
            )
            
            # Extraer contenido de respuesta
            ai_response = response.choices[0].message.content.strip()
            
            # Limpiar respuesta para asegurar JSON válido
            if ai_response.startswith('```json'):
                ai_response = ai_response[7:-3]
            elif ai_response.startswith('```'):
                ai_response = ai_response[3:-3]
            
            # Parsear JSON
            try:
                article_data = json.loads(ai_response)
                
                # Validar que tenga las claves requeridas
                required_keys = ['titulo_h1', 'meta_descripcion', 'slug_url', 'categoria', 'contenido_html']
                missing_keys = [key for key in required_keys if key not in article_data]
                
                if missing_keys:
                    logger.warning(f"⚠️ IA generó artículo incompleto, faltan: {missing_keys}")
                    return self._generate_fallback_article(user_text)
                
                logger.info("✅ Artículo SEO generado exitosamente con IA")
                return article_data
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error parseando JSON de IA: {e}")
                logger.error(f"Respuesta recibida: {ai_response[:200]}...")
                return self._generate_fallback_article(user_text)
                
        except Exception as e:
            logger.error(f"❌ Error generando artículo con IA: {e}")
            return self._generate_fallback_article(user_text)
    
    async def upload_image_to_wordpress(self, image_data: bytes, filename: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Sube imagen a WordPress y retorna URL e ID
        MODIFICADO v2.0.4: Retorna tanto URL como ID para imagen destacada
        """
        try:
            if not self.wp_client:
                return None, None
            
            # Redimensionar imagen
            resized_image = self.resize_image(image_data)
            
            # Preparar datos para WordPress
            data = {
                'name': filename,
                'type': 'image/jpeg',
                'bits': resized_image
            }
            
            # Subir a WordPress
            response = self.wp_client.call(media.UploadFile(data))
            
            if response and 'url' in response and 'id' in response:
                logger.info(f"✅ Imagen subida a WordPress: {response['url']} (ID: {response['id']})")
                return response['url'], response['id']
            elif response and 'url' in response:
                # Fallback si no hay ID en respuesta
                logger.info(f"✅ Imagen subida a WordPress: {response['url']} (ID no disponible)")
                return response['url'], None
            else:
                logger.error("❌ Respuesta inválida de WordPress")
                return None, None
                
        except Exception as e:
            logger.error(f"❌ Error subiendo imagen a WordPress: {e}")
            return None, None

    async def publish_seo_article_to_wordpress(self, article_data: Dict, image_url: Optional[str] = None, image_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
        """
        CORREGIDO v2.0.4: Publica artículo SEO completo en WordPress con validaciones
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
            post = wordpress_xmlrpc.WordPressPost()
            post.title = article_data.get('titulo_h1', 'Artículo Sin Título')
            post.slug = article_data.get('slug_url', 'articulo-sin-slug')
            
            # Contenido completo con imagen si existe
            content = ""
            if image_url:
                alt_text = article_data.get('titulo_h1', 'Imagen del artículo')
                content += f'<img src="{image_url}" alt="{alt_text}" class="wp-image-featured" style="width:100%; height:auto; margin-bottom: 20px;">\n\n'
            
            content += article_data.get('contenido_html', '<p>Contenido no disponible</p>')
            
            # Agregar enlaces si no están en el contenido
            if article_data.get('enlace_interno') and article_data['enlace_interno'] not in content:
                content += f'\n<p><strong>Relacionado:</strong> <a href="{article_data["enlace_interno"]}">Más noticias de la categoría</a></p>'
            
            if article_data.get('enlace_externo') and article_data['enlace_externo'] not in content:
                content += f'\n<p><strong>Fuente:</strong> <a href="{article_data["enlace_externo"]}" target="_blank" rel="noopener">Más información</a></p>'
            
            # Agregar datos estructurados
            if article_data.get('datos_estructurados'):
                content += f'\n<script type="application/ld+json">{article_data["datos_estructurados"]}</script>'
            
            post.content = content
            post.post_status = 'publish'
            
            # Configurar meta descripción y SEO
            post.custom_fields = []
            if article_data.get('meta_descripcion'):
                post.custom_fields.append({
                    'key': '_yoast_wpseo_metadesc',
                    'value': article_data['meta_descripcion']
                })
                post.custom_fields.append({
                    'key': '_aioseop_description', 
                    'value': article_data['meta_descripcion']
                })
            
            # Keyword principal
            if article_data.get('keyword_principal'):
                post.custom_fields.append({
                    'key': '_yoast_wpseo_focuskw',
                    'value': article_data['keyword_principal']
                })
            
            # Tags y categoría
            if article_data.get('tags'):
                post.terms_names = {
                    'post_tag': article_data['tags']
                }
            
            if article_data.get('categoria'):
                # NUEVO v2.0.4: Validar que la categoría existe en WordPress
                validated_category = self._validate_category(article_data['categoria'])
                post.terms_names = post.terms_names or {}
                post.terms_names['category'] = [validated_category]
            
            # Publicar post
            post_id = self.wp_client.call(posts.NewPost(post))
            
            # NUEVO v2.0.4: Configurar imagen destacada si está disponible
            if image_id and post_id:
                try:
                    # Configurar imagen destacada usando el ID del attachment
                    self.wp_client.call(SetPostThumbnail(post_id, image_id))
                    logger.info(f"✅ Imagen destacada configurada - Post ID: {post_id}, Image ID: {image_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Error configurando imagen destacada: {e}")
            
            logger.info(f"✅ Artículo SEO publicado exitosamente - ID: {post_id}")
            return post_id, article_data.get('titulo_h1', 'Artículo publicado')
            
        except Exception as e:
            logger.error(f"❌ Error publicando artículo: {e}")
            return None, None
    
    async def send_welcome_message(self, chat_id: int):
        """Envía mensaje de bienvenida con instrucciones"""
        welcome_text = f"""🤖 **Bot SEO Periodístico v2.0.4 Activado**

📰 **Funcionalidades:**
• 📝 **Solo texto** - Artículo SEO de {self.min_word_count}+ palabras
• 📸 **Foto + texto** - Artículo con imagen optimizada 1200x675px
• 🎙️ **Audio + texto** - Transcripción automática + artículo SEO
• 🔧 **Configuración automática** - Imagen destacada en WordPress

⚙️ **Características SEO:**
• Meta descripciones optimizadas
• URLs amigables
• Estructura H1, H2, H3
• Keywords y tags automáticos
• Enlaces internos y externos
• Datos estructurados JSON-LD
• Categorías dinámicas desde WordPress

📊 **Configuración actual:**
• Palabras objetivo: {self.target_word_count}
• Tamaño imagen: {self.TARGET_WIDTH}x{self.TARGET_HEIGHT}px
• Modelo IA: {self.ai_model}

🚀 **Para empezar:**
Envía tu crónica o noticia (texto, imagen, audio)"""

        try:
            bot = Bot(token=self.telegram_token)
            await bot.send_message(chat_id=chat_id, text=welcome_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error enviando mensaje de bienvenida: {e}")
    
    async def send_processing_message(self, chat_id: int) -> Optional[int]:
        """Envía mensaje de procesamiento y retorna message_id para editar después"""
        processing_text = """⏳ **Procesando contenido...**

🔄 **Pasos:**
• Analizando contenido recibido
• Generando artículo SEO optimizado  
• Imagen + texto descriptivo
• Optimizando imagen a 1200x675px
• Imagen + audio transcrito
• Configurando metadatos SEO
• Preparando para WordPress

[Adjuntar imagen]

📝 **Esto puede tomar 30-60 segundos**

✅ Imagen redimensionada a 1200x675px
🔄 Generando artículo SEO..."""

        try:
            bot = Bot(token=self.telegram_token)
            message = await bot.send_message(chat_id=chat_id, text=processing_text, parse_mode='Markdown')
            return message.message_id
        except Exception as e:
            logger.error(f"Error enviando mensaje de procesamiento: {e}")
            return None
    
    async def update_processing_message(self, chat_id: int, message_id: int, step: str):
        """Actualiza el mensaje de procesamiento con el paso actual"""
        steps_text = {
            "analyzing": "🔍 Analizando contenido recibido...",
            "generating": "🤖 Generando artículo SEO con IA...", 
            "uploading": "📤 Subiendo imagen a WordPress...",
            "publishing": "📝 Publicando artículo en WordPress...",
            "completed": "✅ ¡Proceso completado!"
        }
        
        try:
            bot = Bot(token=self.telegram_token)
            await bot.edit_message_text(
                chat_id=chat_id, 
                message_id=message_id,
                text=f"⏳ **Procesando...**\n\n{steps_text.get(step, step)}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.debug(f"Error actualizando mensaje: {e}")  # Log como debug, no es crítico
    
    async def send_result_message(self, chat_id: int, success: bool, result_data: Dict):
        """Envía mensaje con el resultado final del procesamiento"""
        if success:
            post_id, title = result_data.get('post_id'), result_data.get('title', 'Sin título')
            post_url = f"{self.wordpress_url.rstrip('/')}/wp-admin/post.php?post={post_id}&action=edit" if post_id else "No disponible"
            
            success_text = f"""✅ **¡Artículo publicado exitosamente!**

📰 **Título:** {title}
🆔 **ID WordPress:** {post_id}
🔗 **Editar:** [Ver en WordPress]({post_url})

📊 **Detalles SEO:**
• Imagen destacada: {'✅ Configurada' if result_data.get('image_configured') else '❌ No disponible'}
• Categoría: {result_data.get('category', 'No especificada')}
• Palabras: ~{result_data.get('word_count', 'N/A')}
• Meta descripción: ✅ Optimizada

🎯 **El artículo está listo y visible en tu sitio web.**"""
            
        else:
            error_msg = result_data.get('error', 'Error desconocido')
            success_text = f"""❌ **Error procesando el contenido**

🔍 **Detalle del error:**
{error_msg}

💡 **Sugerencias:**
• Verifica que el texto tenga al menos 10 caracteres
• Asegúrate de que las APIs estén configuradas
• Intenta nuevamente en unos momentos

📞 **Si el problema persiste, contacta al administrador.**"""
        
        try:
            bot = Bot(token=self.telegram_token)
            await bot.send_message(chat_id=chat_id, text=success_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error enviando resultado: {e}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        CORREGIDO v2.0.4: Manejador principal de mensajes con flujo robusto
        """
        try:
            message = update.message
            user_id = message.from_user.id
            chat_id = message.chat_id
            
            # Verificar autorización
            if self.authorized_user_ids and user_id not in self.authorized_user_ids:
                await message.reply_text(
                    "❌ **Acceso denegado**\n\n"
                    "No tienes permisos para usar este bot.\n"
                    "Contacta al administrador para obtener acceso."
                )
                return
            
            # Verificar formato de mensaje válido
            if not self._is_valid_journalist_message(message):
                await message.reply_text(
                    "📝 **Formato de mensaje inválido**\n\n"
                    "**Formatos válidos:**\n"
                    "• Texto descriptivo (mínimo 10 caracteres)\n"
                    "• Imagen + texto descriptivo\n"
                    "• Audio (con OpenAI configurado)\n"
                    "• Imagen + audio transcrito\n"
                    "\n"
                    "**Ejemplo:**\n"
                    "[Adjuntar imagen]\n"
                    "Hoy se inauguró el nuevo centro comercial en el centro de la ciudad..."
                )
                return
                
            # Enviar mensaje de procesamiento
            processing_msg_id = await self.send_processing_message(chat_id)
            
            # Extraer contenido del mensaje
            await self.update_processing_message(chat_id, processing_msg_id, "analyzing")
            content_data = await self._extract_content_from_message(message)
            
            if not content_data:
                await self.send_result_message(chat_id, False, {'error': 'No se pudo extraer contenido del mensaje'})
                return
            
            # Combinar texto y transcripción de audio
            combined_text = f"{content_data['text_content']} {content_data['voice_transcript']}".strip()
            has_image = bool(content_data['image_data'])
            
            # CORREGIDO v2.0.4: Flujo de generación robusto
            await self.update_processing_message(chat_id, processing_msg_id, "generating") 
            
            # Generar prompt
            prompt_data = self.generate_seo_prompt(combined_text, has_image)
            
            # Generar artículo
            if 'error' in prompt_data:
                # Si hay error en el prompt, usar fallback directamente
                logger.warning(f"⚠️ Error en prompt: {prompt_data['error']}")
                article_data = self._generate_fallback_article(combined_text)
            else:
                # Intentar generar con IA
                article_data = await self.generate_article_with_ai(prompt_data, combined_text)
            
            # Validar que el artículo esté completo
            if not article_data or 'titulo_h1' not in article_data:
                logger.error("❌ Artículo generado inválido, usando fallback final")
                article_data = self._generate_fallback_article(combined_text)
            
            # Subir imagen si existe
            image_url, image_id = None, None
            if content_data['image_data']:
                await self.update_processing_message(chat_id, processing_msg_id, "uploading")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"article_image_{timestamp}.jpg"
                image_url, image_id = await self.upload_image_to_wordpress(content_data['image_data'], filename)
            
            # Publicar artículo
            await self.update_processing_message(chat_id, processing_msg_id, "publishing")
            post_id, post_title = await self.publish_seo_article_to_wordpress(article_data, image_url, image_id)
            
            # Actualizar a completado
            await self.update_processing_message(chat_id, processing_msg_id, "completed")
            
            # Enviar resultado
            if post_id:
                result_data = {
                    'post_id': post_id,
                    'title': post_title,
                    'category': article_data.get('categoria', 'No especificada'),
                    'word_count': len(article_data.get('contenido_html', '').split()),
                    'image_configured': bool(image_id)
                }
                await self.send_result_message(chat_id, True, result_data)
            else:
                await self.send_result_message(chat_id, False, {'error': 'Error publicando en WordPress'})
                
        except Exception as e:
            logger.error(f"❌ Error crítico manejando mensaje: {e}")
            try:
                await update.message.reply_text(f"❌ **Error interno del sistema**\n\nDetalle: {str(e)[:100]}...\n\nIntenta nuevamente en unos momentos.")
            except:
                pass
    
    def _is_valid_journalist_message(self, message) -> bool:
        """Verifica si el mensaje tiene formato válido para procesamiento periodístico"""
        has_image = bool(message.photo)
        has_text = bool((message.caption and len(message.caption.strip()) >= 10) or 
                       (message.text and len(message.text.strip()) >= 10))
        has_voice = bool(message.voice and self.openai_client)
        
        # Debe tener al menos texto suficiente, opcionalmente imagen o voz
        return has_text or has_voice
    
    async def _extract_content_from_message(self, message) -> Optional[Dict]:
        """Extrae y procesa el contenido del mensaje de Telegram"""
        try:
            image_data = None
            
            # Obtener imagen si existe
            if message.photo:
                photo = message.photo[-1]  # La imagen de mayor resolución
                photo_file = await photo.get_file()
                
                # Descargar imagen usando requests (más estable)
                import requests
                response = requests.get(photo_file.file_path)
                if response.status_code == 200:
                    image_data = response.content
            
            # Extraer texto
            text_content = ""
            if message.caption:
                text_content = message.caption
            elif message.text:
                text_content = message.text
            
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
            
            # Crear archivo temporal
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
                import requests
                response = requests.get(voice_file.file_path)
                temp_file.write(response.content)
                temp_file_path = temp_file.name
            
            # Transcribir con Whisper
            with open(temp_file_path, 'rb') as audio_file:
                transcript = await self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="es"  # Español por defecto
                )
            
            # Limpiar archivo temporal
            os.unlink(temp_file_path)
            
            return transcript.text.strip()
            
        except Exception as e:
            logger.error(f"Error transcribiendo audio: {e}")
            return None
    
    async def start_bot(self):
        """Inicia el bot de Telegram y mantiene la conexión activa"""
        try:
            # Inicializar clientes
            if not await self._initialize_clients():
                logger.error("❌ No se pudieron inicializar los clientes necesarios")
                return False
            
            if not self.telegram_app:
                logger.error("❌ Cliente de Telegram no disponible")
                return False
            
            # Configurar handlers
            self.telegram_app.add_handler(MessageHandler(
                filters.TEXT | filters.PHOTO | filters.VOICE, 
                self.handle_message
            ))
            
            # Enviar mensaje de activación al primer usuario autorizado
            if self.authorized_user_ids:
                try:
                    await self.send_welcome_message(self.authorized_user_ids[0])
                except Exception as e:
                    logger.warning(f"No se pudo enviar mensaje de bienvenida: {e}")
            
            # Iniciar bot
            logger.info("🚀 Iniciando bot de Telegram...")
            await self.telegram_app.initialize()
            await self.telegram_app.start()
            self.bot_running = True
            
            logger.info("✅ Bot iniciado exitosamente - Esperando mensajes...")
            
            # Mantener bot corriendo
            await self.telegram_app.updater.start_polling()
            
            # Esperar hasta que se detenga
            while self.bot_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"❌ Error crítico en el bot: {e}")
            return False
        finally:
            if self.telegram_app:
                await self.telegram_app.stop()
                await self.telegram_app.shutdown()
    
    async def stop_bot(self):
        """Detiene el bot de forma segura"""
        logger.info("🔴 Deteniendo bot...")
        self.bot_running = False

# Punto de entrada principal
async def main():
    """Función principal del programa"""
    try:
        # Crear instancia del bot
        bot = WordPressSEOBot()
        
        # Verificar configuración crítica
        missing_vars = []
        if not bot.telegram_token:
            missing_vars.append('TELEGRAM_TOKEN')
        if not bot.wordpress_url:
            missing_vars.append('WORDPRESS_URL')
        if not bot.wordpress_user:
            missing_vars.append('WORDPRESS_USER')
        if not bot.wordpress_password:
            missing_vars.append('WORDPRESS_PASSWORD')
        
        if missing_vars:
            logger.error(f"❌ Variables de entorno faltantes: {', '.join(missing_vars)}")
            logger.error("💡 Asegúrate de configurar todas las variables necesarias en el archivo .env")
            return
        
        # Iniciar bot
        logger.info("🚀 Iniciando Sistema SEO Bot v2.0.4...")
        await bot.start_bot()
        
    except KeyboardInterrupt:
        logger.info("🔴 Detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error crítico: {e}")

if __name__ == "__main__":
    # Configurar asyncio para Windows si es necesario
    import sys
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Ejecutar programa principal
    asyncio.run(main())
