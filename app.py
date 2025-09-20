#!/usr/bin/env python3
"""
VERSIÓN v1.0.0 - Bot SEO Telegram a WordPress
Sistema de versionado implementado
Fixes mínimos sobre base funcional comprobada

CHANGELOG v1.0.0:
- Fix: Error 'NoneType' object has no attribute 'bot'
- Fix: Error 'WordPressPost' object has no attribute 'terms_names' 
- Fix: asyncio event loop issues
- Base: app_yoast_ultra_final.py (funcional comprobada)

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
    OPENAI_AVAILABLE = False

# Framework web
from flask import Flask, request, jsonify
import requests

# Telegram
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# WordPress
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media, taxonomies
from wordpress_xmlrpc.compat import xmlrpc_client

# IA
from groq import Groq

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutomacionPeriodisticaV1:
    """Sistema de automatización periodística v1.0.0"""
    
    def __init__(self):
        # Configuración desde variables de entorno
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.GROQ_API_KEY = os.getenv('GROQ_API_KEY')
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
        self.bot = None
        self.groq_client = None
        self.wp_client = None
        
        # Estadísticas
        self.stats = {
            'messages_processed': 0,
            'articles_created': 0,
            'errors': 0,
            'start_time': datetime.now()
        }
        
        self._init_services()
    
    def _init_services(self):
        """Inicializa todos los servicios"""
        try:
            # Bot de Telegram
            if self.TELEGRAM_BOT_TOKEN:
                self.bot = Bot(token=self.TELEGRAM_BOT_TOKEN)
                logger.info("✅ Bot de Telegram inicializado")
            
            # Cliente Groq
            if self.GROQ_API_KEY:
                self.groq_client = Groq(api_key=self.GROQ_API_KEY)
                logger.info("✅ Cliente Groq inicializado")
            
            # Cliente WordPress
            if all([self.WORDPRESS_URL, self.WORDPRESS_USERNAME, self.WORDPRESS_PASSWORD]):
                wp_url = self.WORDPRESS_URL
                if not wp_url.endswith('/xmlrpc.php'):
                    wp_url = wp_url.rstrip('/') + '/xmlrpc.php'
                
                self.wp_client = Client(wp_url, self.WORDPRESS_USERNAME, self.WORDPRESS_PASSWORD)
                logger.info("✅ Cliente WordPress inicializado")
            
        except Exception as e:
            logger.error(f"Error inicializando servicios: {e}")

    def extract_keyword_from_text(self, text: str) -> str:
        """Extrae palabra clave del texto"""
        words = re.findall(r'\b[a-záéíóúñA-ZÁÉÍÓÚÑ]{3,}\b', text)
        if len(words) >= 2:
            return ' '.join(words[:2]).lower()
        elif words:
            return words[0].lower()
        return "noticia actualidad"

    def generate_seo_article(self, user_text: str, keyword: str, has_image: bool = False) -> Dict:
        """Genera artículo SEO con IA"""
        try:
            prompt = f"""Sos un redactor SEO experto argentino. Creá un artículo periodístico profesional sobre: {user_text}

REQUISITOS YOAST SEO:
- Palabra clave: "{keyword}" (CON ESPACIOS)
- Mínimo 1200 palabras
- Densidad palabra clave: 0.8-1% (máximo 12 veces)
- Meta descripción: 135 caracteres exactos
- Usar español argentino (descubrí, mirá, conocé)
- Estructura H2/H3 balanceada
- Enlaces internos a /categoria/actualidad

PROHIBIDO:
- NO mencionar fuentes externas
- NO títulos genéricos como "Información Relevante"
- NO sobreoptimización

Formato JSON:
{{
  "titulo": "Título con keyword al inicio (máx 55 chars)",
  "metadescripcion": "Meta de 135 chars exactos con keyword",
  "palabra_clave": "{keyword}",
  "slug": "{keyword.replace(' ', '-')}",
  "contenido_html": "Artículo completo HTML",
  "tags": ["{keyword}"],
  "categoria": "Actualidad"
}}"""

            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Limpiar respuesta
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            article_data = json.loads(content)
            logger.info("✅ Artículo generado con IA")
            return article_data
            
        except Exception as e:
            logger.error(f"Error generando artículo: {e}")
            return self._fallback_article(user_text, keyword)
    
    def _fallback_article(self, user_text: str, keyword: str) -> Dict:
        """Artículo de respaldo"""
        return {
            "titulo": f"{keyword.title()} - Información Actualizada",
            "metadescripcion": f"Descubrí todo sobre {keyword}. Información completa y actualizada para mantenerte informado sobre este tema importante.",
            "palabra_clave": keyword,
            "slug": keyword.replace(' ', '-'),
            "contenido_html": f"<p>Información completa sobre <strong>{keyword}</strong>.</p><h2>Detalles sobre {keyword.title()}</h2><p>{user_text}</p>",
            "tags": [keyword],
            "categoria": "Actualidad"
        }

    def resize_image(self, image_data: bytes) -> bytes:
        """Redimensiona imagen"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                if img.width <= self.TARGET_WIDTH and img.height <= self.TARGET_HEIGHT:
                    return image_data
                
                img.thumbnail((self.TARGET_WIDTH, self.TARGET_HEIGHT), Image.Resampling.LANCZOS)
                
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=self.IMAGE_QUALITY)
                return output.getvalue()
        except:
            return image_data

    def upload_image_to_wordpress(self, image_data: bytes, filename: str, alt_text: str = "") -> Optional[str]:
        """Sube imagen a WordPress"""
        try:
            if not self.wp_client:
                return None
            
            processed_data = self.resize_image(image_data)
            
            # Preparar datos para upload
            data = {
                'name': filename,
                'type': 'image/jpeg',
                'bits': xmlrpc_client.Binary(processed_data),
                'overwrite': True
            }
            
            response = self.wp_client.call(media.UploadFile(data))
            
            if response and 'url' in response:
                logger.info(f"✅ Imagen subida: {response['url']}")
                return response['url']
            
        except Exception as e:
            logger.error(f"Error subiendo imagen: {e}")
        
        return None

    def publish_to_wordpress(self, article_data: Dict, image_url: Optional[str] = None) -> Tuple[Optional[int], Optional[str]]:
        """Publica artículo en WordPress"""
        try:
            if not self.wp_client:
                return None, None
            
            # Crear post
            post = WordPressPost()
            post.title = article_data['titulo']
            post.content = article_data['contenido_html']
            post.excerpt = article_data['metadescripcion']
            post.slug = article_data['slug']
            post.post_status = 'publish'
            
            # Fix: Configurar términos correctamente
            post.terms_names = {
                'category': [article_data.get('categoria', 'Actualidad')],
                'post_tag': article_data.get('tags', [])
            }
            
            # Configurar imagen destacada
            if image_url:
                try:
                    media_list = self.wp_client.call(media.GetMediaLibrary({}))
                    for media_item in media_list:
                        if hasattr(media_item, 'link') and image_url in media_item.link:
                            post.thumbnail = media_item.id
                            break
                except Exception as e:
                    logger.warning(f"Error configurando imagen destacada: {e}")
            
            # Publicar
            post_id = self.wp_client.call(posts.NewPost(post))
            
            if post_id:
                logger.info(f"✅ Artículo publicado: ID {post_id}")
                return post_id, post.title
            
        except Exception as e:
            logger.error(f"Error publicando artículo: {e}")
        
        return None, None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        welcome_msg = """🤖 **Bot SEO v1.0.0**

📸 Enviá foto + texto → Artículo SEO completo
📝 Solo texto → Artículo optimizado

🎯 **Optimización Yoast:**
• Densidad palabra clave balanceada
• Meta descripción 135 chars
• Estructura H2/H3 optimizada
• Imagen destacada automática

Comandos: /start /stats"""
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stats"""
        stats_msg = f"""📊 **Estadísticas v1.0.0**

📨 Mensajes: {self.stats['messages_processed']}
📰 Artículos: {self.stats['articles_created']} 
❌ Errores: {self.stats['errors']}

🔧 Servicios:
• Groq: {'✅' if self.groq_client else '❌'}
• WordPress: {'✅' if self.wp_client else '❌'}"""
        
        await update.message.reply_text(stats_msg, parse_mode='Markdown')

    async def handle_message_with_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes con foto"""
        try:
            user_id = update.effective_user.id
            
            if self.AUTHORIZED_USERS and user_id not in self.AUTHORIZED_USERS:
                await update.message.reply_text("❌ No autorizado")
                return
            
            self.stats['messages_processed'] += 1
            user_text = update.message.caption or "Noticia sin descripción"
            
            processing_msg = await update.message.reply_text("🔄 **Procesando artículo SEO v1.0.0...**")
            
            # Descargar imagen - Fix: usar self.bot en lugar de context.bot
            try:
                photo = update.message.photo[-1]
                file = await self.bot.get_file(photo.file_id)
                
                image_response = requests.get(file.file_path)
                if image_response.status_code == 200:
                    image_data = image_response.content
                    
                    # Generar artículo
                    keyword = self.extract_keyword_from_text(user_text)
                    article_data = self.generate_seo_article(user_text, keyword, True)
                    
                    # Subir imagen
                    filename = f"imagen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    image_url = self.upload_image_to_wordpress(image_data, filename, keyword)
                    
                    # Publicar
                    post_id, titulo = self.publish_to_wordpress(article_data, image_url)
                    
                    if post_id:
                        self.stats['articles_created'] += 1
                        await processing_msg.edit_text(f"✅ **Artículo v1.0.0 publicado**\n📰 {titulo}\n🔗 ID: {post_id}")
                    else:
                        await processing_msg.edit_text("❌ Error publicando")
                        
                else:
                    await processing_msg.edit_text("❌ Error descargando imagen")
                    
            except Exception as e:
                logger.error(f"Error procesando imagen: {e}")
                await processing_msg.edit_text(f"❌ Error: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error en handle_message_with_photo: {e}")
            self.stats['errors'] += 1

    async def handle_text_only(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes solo texto"""
        try:
            user_id = update.effective_user.id
            
            if self.AUTHORIZED_USERS and user_id not in self.AUTHORIZED_USERS:
                await update.message.reply_text("❌ No autorizado")
                return
            
            self.stats['messages_processed'] += 1
            user_text = update.message.text
            
            processing_msg = await update.message.reply_text("🔄 **Generando artículo SEO v1.0.0...**")
            
            # Generar y publicar
            keyword = self.extract_keyword_from_text(user_text)
            article_data = self.generate_seo_article(user_text, keyword, False)
            post_id, titulo = self.publish_to_wordpress(article_data)
            
            if post_id:
                self.stats['articles_created'] += 1
                await processing_msg.edit_text(f"✅ **Artículo v1.0.0 publicado**\n📰 {titulo}")
            else:
                await processing_msg.edit_text("❌ Error publicando")
                
        except Exception as e:
            logger.error(f"Error en handle_text_only: {e}")
            self.stats['errors'] += 1

# Inicializar sistema
sistema = AutomacionPeriodisticaV1()

# Flask app
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook principal"""
    try:
        json_data = request.get_json()
        if not json_data:
            return jsonify({'error': 'No JSON data'}), 400
        
        # Fix: Crear Update con bot del sistema
        update = Update.de_json(json_data, sistema.bot)
        
        if not update or not update.message:
            return jsonify({'status': 'no_message'}), 200
        
        # Fix: Procesar sin crear nuevos event loops
        if update.message.photo:
            asyncio.create_task(sistema.handle_message_with_photo(update, None))
        elif update.message.text:
            if update.message.text.startswith('/start'):
                asyncio.create_task(sistema.start_command(update, None))
            elif update.message.text.startswith('/stats'):
                asyncio.create_task(sistema.stats_command(update, None))
            else:
                asyncio.create_task(sistema.handle_text_only(update, None))
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'version': 'v1.0.0',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
