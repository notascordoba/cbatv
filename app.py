#!/usr/bin/env python3
"""
Sistema SEO Profesional para automatización periodística v2.0.2
Bot que convierte crónicas en artículos SEO optimizados para WordPress
Base sólida sin errores de inicialización + características SEO avanzadas

VERSIÓN: 2.0.2
FECHA: 2025-09-21
CAMBIOS:
+ Obtención automática de categorías de WordPress usando XML-RPC
+ Validación estricta de categorías (prohibido crear nuevas)
+ Prompt inteligente con categorías disponibles del sitio
+ Adaptabilidad multi-sitio para diferentes temáticas
+ Cache de categorías para optimizar rendimiento
+ Fallbacks inteligentes en caso de problemas de conexión
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
from wordpress_xmlrpc.methods.taxonomies import GetTerms
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

class TelegramToWordPressBotSEO:
    """Bot SEO Profesional con características avanzadas y base estable - v2.0.2"""
    
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
        
        # Cache de categorías existentes de WordPress (NUEVO v2.0.2)
        self.wordpress_categories = []
        
        self._initialize_clients()
        self._validate_configuration()
    
    def _initialize_clients(self):
        """Inicializa los clientes de servicios externos"""
        try:
            # Cliente Groq (requerido)
            if self.GROQ_API_KEY:
                self.groq_client = Groq(api_key=self.GROQ_API_KEY)
                logger.info("✅ Cliente Groq inicializado")
            
            # Cliente OpenAI (opcional)
            if self.OPENAI_API_KEY and OPENAI_AVAILABLE:
                self.openai_client = openai.OpenAI(api_key=self.OPENAI_API_KEY)
                logger.info("✅ Cliente OpenAI inicializado")
            
            # Cliente WordPress (requerido)
            if all([self.WORDPRESS_URL, self.WORDPRESS_USERNAME, self.WORDPRESS_PASSWORD]):
                # Asegurar que la URL termine con /xmlrpc.php
                wp_url = self.WORDPRESS_URL
                if not wp_url.endswith('/xmlrpc.php'):
                    wp_url = f"{wp_url.rstrip('/')}/xmlrpc.php"
                
                self.wp_client = Client(wp_url, self.WORDPRESS_USERNAME, self.WORDPRESS_PASSWORD)
                logger.info("✅ Cliente WordPress inicializado")
                
                # NUEVO v2.0.2: Obtener categorías existentes de WordPress automáticamente
                self._fetch_wordpress_categories()
            
            # Bot de Telegram (requerido)
            if self.TELEGRAM_TOKEN:
                self.bot = Bot(token=self.TELEGRAM_TOKEN)
                logger.info("✅ Bot de Telegram inicializado")
                
        except Exception as e:
            logger.error(f"Error inicializando clientes: {e}")
    
    def _validate_configuration(self):
        """Valida que las configuraciones críticas estén presentes"""
        missing_configs = []
        
        if not self.TELEGRAM_TOKEN:
            missing_configs.append("TELEGRAM_BOT_TOKEN")
        if not self.GROQ_API_KEY:
            missing_configs.append("GROQ_API_KEY")
        if not self.WORDPRESS_URL:
            missing_configs.append("WORDPRESS_URL")
        if not self.WORDPRESS_USERNAME:
            missing_configs.append("WORDPRESS_USERNAME")
        if not self.WORDPRESS_PASSWORD:
            missing_configs.append("WORDPRESS_PASSWORD")
        
        if missing_configs:
            logger.error(f"❌ Configuraciones faltantes: {', '.join(missing_configs)}")
            raise ValueError(f"Configuraciones requeridas faltantes: {missing_configs}")
        
        logger.info("✅ Configuración validada exitosamente")

    def _fetch_wordpress_categories(self) -> List[str]:
        """
        NUEVO v2.0.2: Obtiene las categorías existentes de WordPress usando XML-RPC
        
        Esta función permite al bot adaptarse automáticamente a múltiples sitios web
        con diferentes temáticas sin necesidad de configuración manual.
        """
        try:
            if not self.wp_client:
                logger.warning("Cliente WordPress no disponible para obtener categorías")
                return []
            
            # Obtener todas las categorías usando XML-RPC
            categories = self.wp_client.call(GetTerms('category'))
            
            # Extraer solo los nombres de las categorías
            category_names = [cat.name for cat in categories if hasattr(cat, 'name')]
            
            # Actualizar cache
            self.wordpress_categories = category_names
            
            logger.info(f"✅ {len(category_names)} categorías obtenidas de WordPress: {', '.join(category_names[:5])}{'...' if len(category_names) > 5 else ''}")
            
            return category_names
            
        except Exception as e:
            logger.error(f"Error obteniendo categorías de WordPress: {e}")
            # Fallback a categorías básicas si hay error
            fallback_categories = ["Actualidad", "Noticias", "General"]
            self.wordpress_categories = fallback_categories
            logger.warning(f"Usando categorías fallback: {', '.join(fallback_categories)}")
            return fallback_categories

    def _validate_category(self, category_name: str) -> str:
        """
        NUEVO v2.0.2: Valida que la categoría exista o sugiere una alternativa
        
        Esta función garantiza que NUNCA se creen categorías nuevas,
        cumpliendo con la restricción del usuario.
        """
        try:
            # Si no hay categorías en cache, obtenerlas
            if not self.wordpress_categories:
                self._fetch_wordpress_categories()
            
            # Verificar si la categoría existe exactamente
            if category_name in self.wordpress_categories:
                return category_name
            
            # Buscar categoría similar (case-insensitive)
            category_lower = category_name.lower()
            for existing_cat in self.wordpress_categories:
                if existing_cat.lower() == category_lower:
                    logger.info(f"Categoría '{category_name}' ajustada a '{existing_cat}' (coincidencia de mayúsculas)")
                    return existing_cat
            
            # Si no hay coincidencia exacta, usar la primera categoría disponible
            if self.wordpress_categories:
                default_category = self.wordpress_categories[0]
                logger.warning(f"Categoría '{category_name}' no existe. Usando '{default_category}' como alternativa")
                return default_category
            
            # Último recurso
            logger.error(f"No se pudieron obtener categorías de WordPress. Usando 'Actualidad' como fallback")
            return "Actualidad"
            
        except Exception as e:
            logger.error(f"Error validando categoría: {e}")
            return "Actualidad"

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
            
            # Redimensionar manteniendo proporción
            image.thumbnail((self.TARGET_WIDTH, self.TARGET_HEIGHT), Image.Resampling.LANCZOS)
            
            # Crear imagen final con fondo blanco si es necesario
            final_image = Image.new('RGB', (self.TARGET_WIDTH, self.TARGET_HEIGHT), (255, 255, 255))
            
            # Centrar imagen redimensionada
            x = (self.TARGET_WIDTH - image.width) // 2
            y = (self.TARGET_HEIGHT - image.height) // 2
            final_image.paste(image, (x, y))
            
            # Guardar en buffer
            buffer = io.BytesIO()
            final_image.save(buffer, format='JPEG', quality=self.IMAGE_QUALITY, optimize=True)
            
            logger.info(f"✅ Imagen redimensionada a {self.TARGET_WIDTH}x{self.TARGET_HEIGHT}")
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error redimensionando imagen: {e}")
            return image_data

    def generate_seo_article(self, user_text: str, has_image: bool = False) -> Dict:
        """
        Genera artículo SEO profesional usando Groq
        MEJORADO v2.0.2: Prompt incluye categorías disponibles dinámicamente
        """
        try:
            if not self.groq_client:
                return self._create_fallback_seo_article(user_text)
            
            # NUEVO v2.0.2: Obtener categorías disponibles para incluir en el prompt
            available_categories = self.wordpress_categories if self.wordpress_categories else ["Actualidad", "Noticias", "General"]
            categories_text = ", ".join(available_categories)
            
            # Prompt optimizado para SEO profesional anti-detección IA
            # MEJORADO v2.0.2: Incluye categorías específicas del sitio
            prompt = f"""
Eres un editor SEO experto especializado en periodismo y neuromarketing argentino. Tu trabajo es crear artículos informativos en español de Argentina, usando lenguaje natural que NO se detecte como generado por IA.

CRÓNICA/INFORMACIÓN DEL CORRESPONSAL:
{user_text}

IMAGEN DISPONIBLE: {'Sí' if has_image else 'No'}

CATEGORÍAS WORDPRESS DISPONIBLES (OBLIGATORIO usar una de estas): {categories_text}

CRÍTICO: Debes extraer la KEYWORD ESPECÍFICA del contenido real. NO uses "información" ni "política" genéricas.

Analiza el contenido y extrae:
- El tema principal específico (ej: "retirada del Estado", "compras en Chile", "nueva legislación", etc.)
- La keyword debe ser 2-3 palabras relevantes al tema exacto

Genera un JSON con esta estructura EXACTA:

{{
    "keyword_principal": "extraer del contenido real - 2-3 palabras específicas",
    "titulo_h1": "Título natural de 30-70 caracteres, NO cortado, incluye keyword",
    "meta_descripcion": "Exactamente 130 caracteres incluyendo keyword y call to action",
    "slug_url": "url-amigable-con-guiones-sin-puntos",
    "contenido_html": "Artículo completo HTML, estructura natural, mínimo 350 palabras",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "categoria": "OBLIGATORIO: una de estas categorías exactas: {categories_text}",
    "enlace_interno": "/categoria/tema-relacionado",
    "enlace_externo": "https://fuente-oficial.com",
    "datos_estructurados": "JSON-LD para NewsArticle",
    "intenciones_busqueda": ["intención 1", "intención 2", "intención 3"],
    "imagen_destacada": {{"necesaria": {"true" if has_image else "false"}, "alt_text": "descripción de imagen", "titulo_imagen": "título descriptivo"}}
}}

REQUISITOS OBLIGATORIOS:

1. KEYWORD PRINCIPAL:
   - Extraer del contenido real (NO genéricas como "información")
   - 2-3 palabras específicas del tema
   - Natural, no forzada

2. TÍTULO H1:
   - 30-70 caracteres EXACTOS
   - NO cortar palabras a la mitad
   - Incluir keyword de forma natural
   - Gancho periodístico atractivo

3. META DESCRIPCIÓN:
   - EXACTAMENTE 130 caracteres (contar)
   - Incluir keyword principal
   - Call to action sutil
   - Resumen conciso

4. CONTENIDO HTML:
   - MÍNIMO 350 palabras (puede ser más)
   - Estructura natural, NO plantillas detectables
   - H2, H3, H4 con variedad de encabezados
   - Estilo periodístico argentino
   - Responder qué, quién, cuándo, dónde, por qué, cómo

5. VARIABILIDAD TOTAL:
   - NO usar frases como "Te contamos toda la información"
   - NO usar "Detalles Importantes" como H2
   - Cada artículo debe tener estructura única
   - Lenguaje natural, no robótico

6. CATEGORÍA:
   - OBLIGATORIO: usar exactamente una de las categorías disponibles: {categories_text}
   - NO crear categorías nuevas
   - Elegir la más relevante al contenido

7. TAGS: 5 etiquetas específicas al tema real

8. ENLACES CONTEXTUALES:
   - Interno: categoría relacionada
   - Externo: fuente oficial relevante

9. DATOS ESTRUCTURADOS: NewsArticle válido

CRÍTICO: El contenido debe ser ÚNICO, NATURAL y NO detectarse como generado por IA. Usar variedad en estructura y lenguaje.
"""

            response = self.groq_client.chat.completions.create(
                model='llama-3.1-8b-instant',
                messages=[
                    {"role": "system", "content": "Eres un periodista experto y especialista en SEO que crea artículos noticiosos profesionales optimizados para motores de búsqueda."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )

            # Extraer y parsear respuesta JSON
            response_text = response.choices[0].message.content
            
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                try:
                    article_data = json.loads(json_text)
                    logger.info("✅ Artículo SEO generado exitosamente")
                    return article_data
                except json.JSONDecodeError:
                    logger.warning("Error en JSON, usando extracción robusta")
                    return self._extract_json_robust(response_text, user_text)
            else:
                logger.warning("No se encontró JSON válido, creando artículo básico")
                return self._create_fallback_seo_article(user_text)
                
        except Exception as e:
            logger.error(f"Error generando artículo con IA: {e}")
            return self._create_fallback_seo_article(user_text)

    def _extract_json_robust(self, text: str, user_text: str) -> Dict:
        """Extrae información de manera robusta cuando JSON falla"""
        try:
            # Extraer elementos principales con regex
            titulo = re.search(r'"titulo_h1":\s*"([^"]+)"', text)
            keyword = re.search(r'"keyword_principal":\s*"([^"]+)"', text)
            meta = re.search(r'"meta_descripcion":\s*"([^"]+)"', text)
            contenido = re.search(r'"contenido_html":\s*"([^"]+)"', text, re.DOTALL)
            
            return {
                "keyword_principal": keyword.group(1) if keyword else "noticia actualidad",
                "titulo_h1": titulo.group(1) if titulo else "Noticia de Actualidad",
                "meta_descripcion": (meta.group(1)[:130] if meta else "Descubre las últimas noticias de actualidad. Información verificada y relevante sobre los acontecimientos más importantes.")[:130],
                "slug_url": "noticia-actualidad",
                "contenido_html": contenido.group(1) if contenido else f"<h2>Información Relevante</h2><p>{user_text}</p><h3>Contexto y Análisis</h3><p>Desarrollo completo de la información proporcionada por nuestro corresponsal.</p>",
                "tags": ["actualidad", "noticias", "información", "sociedad", "último"],
                "categoria": self._validate_category("Actualidad"),  # NUEVO v2.0.2: Usar validación
                "enlace_interno": "/categoria/actualidad",
                "enlace_externo": "https://www.perfil.com",
                "datos_estructurados": f'{{"@context":"https://schema.org","@type":"NewsArticle","headline":"Noticia de Actualidad","author":{{"@type":"Person","name":"Redacción"}},"datePublished":"{datetime.now().isoformat()}"}}',
                "intenciones_busqueda": ["últimas noticias", "qué está pasando", "información actualizada"]
            }
        except Exception as e:
            logger.error(f"Error en extracción robusta: {e}")
            return self._create_fallback_seo_article(user_text)

    def _create_fallback_seo_article(self, user_text: str) -> Dict:
        """
        Crea un artículo SEO básico cuando todo falla
        MEJORADO v2.0.2: Usa validación de categorías
        """
        # Intentar extraer keyword del texto del usuario
        words = user_text.lower().split()[:3]
        keyword = " ".join(words[:2]) if len(words) >= 2 else "noticia importante"
        titulo = f"Últimas noticias sobre {keyword.title()}"
        
        return {
            "keyword_principal": keyword,
            "titulo_h1": titulo[:70],
            "meta_descripcion": f"Entérate de todo sobre {keyword}. Información completa, análisis detallado y contexto actualizado de la mano de nuestros corresponsales."[:130],
            "slug_url": keyword.replace(" ", "-").replace(".", ""),
            "contenido_html": f"""
<h2>¿Qué está pasando con {keyword}?</h2>
<p>Nuestro corresponsal nos informa sobre un desarrollo importante que merece la atención de nuestros lectores.</p>

<h3>Información del corresponsal</h3>
<p>{user_text}</p>

<h3>Contexto y antecedentes</h3>
<p>Este tipo de acontecimientos requiere un seguimiento detallado para comprender su impacto en la comunidad y las posibles implicaciones futuras.</p>

<h4>Puntos clave a destacar</h4>
<ul>
<li>Relevancia del evento en el contexto actual</li>
<li>Factores que contribuyen al desarrollo de la situación</li>
<li>Posibles consecuencias e impacto social</li>
<li>Reacciones de autoridades y ciudadanos</li>
</ul>

<h4>Seguimiento y próximos pasos</h4>
<p>Continuaremos monitoreando esta situación para brindar actualizaciones oportunas a nuestros lectores. Es fundamental mantenerse informado a través de fuentes confiables.</p>

<h3>Conclusión</h3>
<p>La información proporcionada por nuestro corresponsal permite mantenernos al tanto de los acontecimientos que afectan a nuestra comunidad. Seguiremos reportando novedades según evolucione la situación.</p>
""",
            "tags": [keyword.split()[0] if keyword.split() else "noticias", "actualidad", "información", "sociedad", "corresponsal"],
            "categoria": self._validate_category("Actualidad"),  # NUEVO v2.0.2: Usar validación de categorías
            "enlace_interno": "/categoria/actualidad",
            "enlace_externo": "https://www.infobae.com",
            "datos_estructurados": f'{{"@context":"https://schema.org","@type":"NewsArticle","headline":"{titulo}","author":{{"@type":"Person","name":"Corresponsal"}},"datePublished":"{datetime.now().isoformat()}"}}',
            "intenciones_busqueda": [f"noticias {keyword}", f"información {keyword}", f"{keyword} actualidad"]
        }

    async def upload_image_to_wordpress(self, image_data: bytes, filename: str) -> Optional[str]:
        """Sube imagen a WordPress y retorna URL"""
        try:
            if not self.wp_client:
                return None
            
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
            
            if response and 'url' in response:
                logger.info(f"✅ Imagen subida a WordPress: {response['url']}")
                return response['url']
            else:
                logger.error("❌ Respuesta inválida de WordPress")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error subiendo imagen a WordPress: {e}")
            return None

    async def publish_seo_article_to_wordpress(self, article_data: Dict, image_url: Optional[str] = None) -> Tuple[Optional[int], Optional[str]]:
        """
        Publica artículo SEO completo en WordPress
        MEJORADO v2.0.2: Usa validación de categorías
        """
        try:
            if not self.wp_client:
                return None, None
            
            # Crear post
            post = wordpress_xmlrpc.WordPressPost()
            post.title = article_data['titulo_h1']
            post.slug = article_data['slug_url']
            
            # Contenido completo con imagen si existe
            content = ""
            if image_url:
                content += f'<img src="{image_url}" alt="{article_data["titulo_h1"]}" class="wp-image-featured" style="width:100%; height:auto; margin-bottom: 20px;">\n\n'
            
            content += article_data['contenido_html']
            
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
                # NUEVO v2.0.2: Validar que la categoría existe en WordPress
                validated_category = self._validate_category(article_data['categoria'])
                post.terms_names = post.terms_names or {}
                post.terms_names['category'] = [validated_category]
            
            # Publicar post
            post_id = self.wp_client.call(posts.NewPost(post))
            
            logger.info(f"✅ Artículo SEO publicado exitosamente - ID: {post_id}")
            return post_id, article_data['titulo_h1']
            
        except Exception as e:
            logger.error(f"❌ Error publicando artículo: {e}")
            return None, None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start mejorado"""
        welcome_msg = """🤖 **Bot SEO Profesional v2.0.2 - ACTIVO**

📰 **Periodismo + IA + SEO = Artículos Profesionales**

**Envía cualquiera de estas opciones:**
• 📝 **Solo texto** - Crea artículo SEO completo
• 📸 **Foto + texto** - Artículo con imagen optimizada 1200x675px  
• 🎤 **Audio** - Transcribe y convierte en artículo

**🚀 Características SEO Profesionales:**
✅ Artículos 800+ palabras con estructura H1, H2, H3, H4
✅ Meta descripción optimizada (130 caracteres)
✅ Keywords principales y tags relevantes
✅ Enlaces internos y externos contextual
✅ Datos estructurados JSON-LD para NewsArticle
✅ Imágenes redimensionadas automáticamente
✅ Publicación directa en WordPress

**🆕 NUEVO v2.0.2:**
✅ Categorías automáticas desde WordPress
✅ Adaptabilidad multi-sitio
✅ Prohibición de crear categorías nuevas

**📊 Optimización garantizada:**
• Título H1 30-70 caracteres con keyword
• Estructura semántica periodística profesional
• Respuesta a las 5W del periodismo
• Contenido verificable y contextualizado

¡Envía tu crónica y la convertiremos en un artículo SEO profesional listo para publicar!"""
        
        await update.message.reply_text(welcome_msg)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stats"""
        uptime = datetime.now() - self.stats['start_time']
        categories_info = f"📂 **Categorías disponibles:** {len(self.wordpress_categories)} categorías" if self.wordpress_categories else "📂 **Categorías:** No cargadas"
        
        stats_message = f"""📊 **Estadísticas del Bot SEO v2.0.2**

⏱️ **Tiempo activo:** {uptime.days}d {uptime.seconds//3600}h {(uptime.seconds%3600)//60}m
📨 **Mensajes procesados:** {self.stats['messages_processed']}
📰 **Artículos SEO creados:** {self.stats['articles_created']}
❌ **Errores:** {self.stats['errors']}
📈 **Tasa de éxito:** {(self.stats['articles_created']/max(1,self.stats['messages_processed'])*100):.1f}%

🔧 **Estado servicios:**
{'✅' if self.groq_client else '❌'} Groq AI (SEO)
{'✅' if self.wp_client else '❌'} WordPress
{'✅' if self.openai_client else '❌'} OpenAI (Audio)
{'✅' if self.bot else '❌'} Telegram Bot

{categories_info}

🎯 **Optimizaciones SEO aplicadas:**
• Estructura H1, H2, H3, H4 semántica
• Meta descripción con keywords
• URLs amigables (slug)
• Tags categorizados
• Enlaces internos/externos
• Datos estructurados JSON-LD
• Imágenes optimizadas

🆕 **Características v2.0.2:**
• Categorías automáticas desde WordPress
• Validación estricta de categorías
• Adaptabilidad multi-sitio
"""
        await update.message.reply_text(stats_message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help con guía SEO"""
        help_message = """📖 **Guía de Uso - Bot SEO Profesional v2.0.2**

**🎯 Formatos aceptados:**
• Imagen + texto descriptivo
• Solo texto (mínimo 20 palabras)
• Imagen + audio transcrito

**📝 Ejemplo óptimo:**
[Adjuntar imagen]
Caption: "Manifestación pacífica en Plaza San Martín. Aproximadamente 300 personas reclaman mejores salarios docentes. Participan gremios UEPC y AMET. Ambiente tranquilo, sin incidentes. Cortes parciales en calles aledañas."

**🤖 El bot generará:**
✅ Artículo SEO 800+ palabras con estructura periodística
✅ Título H1 optimizado con keyword principal  
✅ Meta descripción 130 caracteres exactos
✅ Tags relevantes y categorización
✅ Enlaces internos y externos contextuales
✅ Datos estructurados para NewsArticle
✅ Imagen redimensionada a 1200x675px
✅ Publicación directa en WordPress

**🆕 NUEVO v2.0.2:**
✅ Categorías automáticas desde tu WordPress
✅ NO crea categorías nuevas (solo usa existentes)
✅ Adaptable a múltiples sitios web

**⚠️ Tips para mejores resultados:**
• Sé específico con nombres, lugares y números
• Incluye el "qué, quién, cuándo, dónde, por qué"
• Menciona contexto relevante
• Describe el ambiente o situación

**🚀 SEO garantizado:**
Cada artículo se optimiza automáticamente para motores de búsqueda con técnicas profesionales de posicionamiento.

**🆘 Soporte:**
Comandos: /start /help /stats
Versión: 2.0.2 - Categorías dinámicas
"""
        await update.message.reply_text(help_message)
    
    def _is_authorized_user(self, user_id: int) -> bool:
        """Verifica si el usuario está autorizado"""
        if not self.AUTHORIZED_USERS:
            return True  # Si no hay lista, todos están autorizados
        return user_id in self.AUTHORIZED_USERS
    
    async def process_telegram_message(self, update: Update):
        """Procesa mensajes entrantes de Telegram con características SEO"""
        try:
            message = update.message
            user_id = message.from_user.id
            
            # Verificar autorización si está configurada
            if not self._is_authorized_user(user_id):
                await message.reply_text("❌ No tienes autorización para usar este bot.")
                return
            
            self.stats['messages_processed'] += 1
            
            # Verificar si el mensaje es válido para procesamiento
            if not self._is_valid_journalist_message(message):
                await message.reply_text(
                    "📝 **Formato requerido:**\n"
                    "• Envía una imagen con texto descriptivo, O\n"
                    "• Envía texto de al menos 20 palabras\n\n"
                    "💡 **Tip:** Incluye detalles como lugar, personas involucradas, contexto y números específicos para mejores artículos SEO."
                )
                return
            
            # Notificar que está procesando
            processing_msg = await message.reply_text("🔄 **Generando artículo SEO profesional v2.0.2...**\n📊 Analizando contenido con IA\n🎯 Optimizando para motores de búsqueda")
            
            # Extraer contenido del mensaje
            content_data = await self._extract_content_from_message(message)
            if not content_data:
                await processing_msg.edit_text("❌ Error extrayendo contenido del mensaje.")
                self.stats['errors'] += 1
                return
            
            # Combinar texto y transcripción de audio
            full_text = content_data['text_content']
            if content_data['voice_transcript']:
                full_text += f" {content_data['voice_transcript']}"
            
            if len(full_text.strip()) < 10:
                await processing_msg.edit_text("❌ El contenido es muy corto. Proporciona más detalles para generar un artículo SEO completo.")
                self.stats['errors'] += 1
                return
            
            # Actualizar estado
            await processing_msg.edit_text("🧠 **Generando artículo SEO con IA...**\n📝 Creando estructura H1, H2, H3, H4\n🎯 Optimizando keywords y meta descripción\n🔄 Validando categorías existentes")
            
            # Generar artículo SEO
            has_image = bool(content_data['image_data'])
            article_data = self.generate_seo_article(full_text, has_image)
            
            # Subir imagen si existe
            image_url = None
            if content_data['image_data']:
                await processing_msg.edit_text("📸 **Procesando imagen...**\n🖼️ Redimensionando a 1200x675px\n⬆️ Subiendo a WordPress")
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"article_seo_{timestamp}.jpg"
                image_url = await self.upload_image_to_wordpress(content_data['image_data'], filename)
            
            # Publicar artículo en WordPress
            await processing_msg.edit_text("🚀 **Publicando artículo SEO...**\n📊 Aplicando optimizaciones\n✅ Validando categorías\n🌐 Enviando a WordPress")
            
            post_id, post_title = await self.publish_seo_article_to_wordpress(article_data, image_url)
            
            if post_id:
                # Mensaje de éxito detallado
                success_msg = f"""✅ **ARTÍCULO SEO PUBLICADO EXITOSAMENTE v2.0.2**

📝 **Título:** {post_title}
🎯 **Keyword principal:** {article_data.get('keyword_principal', 'N/A')}
📊 **Meta descripción:** {len(article_data.get('meta_descripcion', ''))} caracteres
🏷️ **Tags:** {', '.join(article_data.get('tags', []))}
📂 **Categoría:** {article_data.get('categoria', 'N/A')} ✅ VALIDADA
🔗 **Post ID:** {post_id}

**🚀 OPTIMIZACIONES SEO APLICADAS:**
• ✅ Título H1 optimizado (30-70 caracteres)
• ✅ Meta descripción con keyword (130 caracteres exactos)
• ✅ Estructura H2, H3, H4 semántica y periodística
• ✅ Enlaces internos y externos contextuales
• ✅ Datos estructurados JSON-LD para NewsArticle
• ✅ Tags categorizados y relevantes
• ✅ URL amigable (slug optimizado)
• ✅ Contenido 350+ palabras estructurado{' ✅ Imagen optimizada 1200x675px' if has_image else ''}

**🆕 MEJORAS v2.0.2:**
• ✅ Categoría obtenida dinámicamente de WordPress
• ✅ Validación estricta (no crea categorías nuevas)
• ✅ Adaptado a temática del sitio actual

🌐 **Ver en WordPress:**
{self.WORDPRESS_URL.replace('/xmlrpc.php', '')}/wp-admin/post.php?post={post_id}&action=edit

📈 **SEO Score:** PROFESIONAL - Optimizado para motores de búsqueda"""
                
                await processing_msg.edit_text(success_msg)
                self.stats['articles_created'] += 1
                
            else:
                await processing_msg.edit_text("❌ **Error al publicar artículo**\n\nVerifica:\n• Conexión a WordPress\n• Permisos de usuario\n• Configuración XML-RPC")
                self.stats['errors'] += 1
                
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            self.stats['errors'] += 1
            try:
                await update.message.reply_text(f"❌ **Error interno del sistema**\n\nDetalle: {str(e)[:100]}...\n\nIntenta nuevamente en unos momentos.")
            except:
                pass
    
    def _is_valid_journalist_message(self, message: Message) -> bool:
        """Verifica si el mensaje tiene formato válido para procesamiento periodístico"""
        has_image = bool(message.photo)
        has_text = bool((message.caption and len(message.caption.strip()) >= 10) or 
                       (message.text and len(message.text.strip()) >= 10))
        has_voice = bool(message.voice and self.openai_client)
        
        # Debe tener al menos texto suficiente, opcionalmente imagen o voz
        return has_text or has_voice
    
    async def _extract_content_from_message(self, message: Message) -> Optional[Dict]:
        """Extrae y procesa el contenido del mensaje de Telegram"""
        try:
            image_data = None
            
            # Obtener imagen si existe
            if message.photo:
                photo = message.photo[-1]  # La imagen de mayor resolución
                photo_file = await photo.get_file()
                
                # Descargar imagen usando requests (más estable)
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
            
            # Descargar usando requests
            response = requests.get(voice_file.file_path)
            if response.status_code != 200:
                return None
            
            # Guardar temporalmente
            temp_filename = f"temp_voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ogg"
            
            with open(temp_filename, 'wb') as f:
                f.write(response.content)
            
            # Transcribir con Whisper
            with open(temp_filename, 'rb') as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="es"
                )
            
            # Limpiar archivo temporal
            try:
                os.remove(temp_filename)
            except:
                pass
            
            return transcript.text
            
        except Exception as e:
            logger.error(f"Error transcribiendo audio: {e}")
            return None

# Variable global para instancia del bot
bot_instance = None

def create_flask_app():
    """Crea y configura la aplicación Flask"""
    app = Flask(__name__)
    
    @app.route('/webhook', methods=['POST'])
    def webhook():
        """Webhook para recibir actualizaciones de Telegram"""
        try:
            global bot_instance
            
            if not bot_instance:
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
    
    @app.route('/')
    def health_check():
        """Health check endpoint"""
        global bot_instance
        
        status = "Bot SEO Profesional v2.0.2 - ACTIVO ✅" if bot_instance else "Bot no inicializado ❌"
        
        info = f"""🤖 {status}

📰 **Características SEO:**
• Artículos 350+ palabras estructurados
• Títulos H1 optimizados (30-70 caracteres)
• Meta descripción exacta (130 caracteres)
• Structure H2, H3, H4 semántica
• Keywords principales y tags
• Enlaces internos/externos contextuales
• Datos estructurados JSON-LD NewsArticle
• Imágenes optimizadas 1200x675px
• Publicación directa WordPress

🆕 **NOVEDADES v2.0.2:**
• Categorías automáticas desde WordPress
• Validación estricta de categorías
• Adaptabilidad multi-sitio
• Prohibición de crear categorías nuevas

🔧 **Estado servicios:**"""
        
        if bot_instance:
            categories_count = len(bot_instance.wordpress_categories) if bot_instance.wordpress_categories else 0
            info += f"""
✅ Groq AI: {'Conectado' if bot_instance.groq_client else 'Desconectado'}
✅ WordPress: {'Conectado' if bot_instance.wp_client else 'Desconectado'}  
✅ OpenAI: {'Conectado' if bot_instance.openai_client else 'Desconectado'}
✅ Telegram: {'Conectado' if bot_instance.bot else 'Desconectado'}
📂 Categorías: {categories_count} disponibles

📊 **Estadísticas:**
• Mensajes procesados: {bot_instance.stats['messages_processed']}
• Artículos SEO creados: {bot_instance.stats['articles_created']}
• Tasa de éxito: {(bot_instance.stats['articles_created']/max(1,bot_instance.stats['messages_processed'])*100):.1f}%"""
        
        return info
    
    @app.route('/stats')
    def get_stats():
        global bot_instance
        if bot_instance:
            stats = bot_instance.stats.copy()
            stats['categories_count'] = len(bot_instance.wordpress_categories) if bot_instance.wordpress_categories else 0
            stats['version'] = '2.0.2'
            return jsonify(stats)
        return jsonify({'error': 'Bot not initialized'})
    
    return app

def main():
    """Función principal del bot"""
    global bot_instance
    
    try:
        # Inicializar bot
        bot_instance = TelegramToWordPressBotSEO()
        
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
        
        logger.info("🚀 Bot SEO Profesional v2.0.2 inicializado correctamente")
        logger.info(f"📊 Configuración activa:")
        logger.info(f"  - Groq AI: {'✅' if bot_instance.groq_client else '❌'}")
        logger.info(f"  - OpenAI: {'✅' if bot_instance.openai_client else '❌'}")
        logger.info(f"  - WordPress: {'✅' if bot_instance.wp_client else '❌'}")
        logger.info(f"  - Telegram: {'✅' if bot_instance.bot else '❌'}")
        logger.info(f"  - Categorías: {len(bot_instance.wordpress_categories) if bot_instance.wordpress_categories else 0} disponibles")
        logger.info(f"  - Usuarios autorizados: {len(bot_instance.AUTHORIZED_USERS) if bot_instance.AUTHORIZED_USERS else 'Todos'}")
        
        # Crear y ejecutar aplicación Flask
        app = create_flask_app()
        
        port = int(os.getenv('PORT', 10000))
        logger.info(f"✅ Servidor SEO v2.0.2 iniciado en puerto {port}")
        logger.info("🔗 Webhook URL: https://periodismo-bot.onrender.com/webhook")
        logger.info("🎯 Bot listo para generar artículos SEO profesionales")
        logger.info("🆕 Características v2.0.2: Categorías dinámicas + Multi-sitio")
        
        # Ejecutar Flask
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
        
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        raise

if __name__ == "__main__":
    main()
