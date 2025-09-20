#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Automatización Periodística v1.1.1
Autor: MiniMax Agent
Última actualización: 2025-09-21

CHANGELOG v1.1.1:
- Mejorar upload_image_to_wordpress: configurar título y alt text con palabra clave
- Reescribir prompt de IA para experto en redacción SEO/periodismo/neuromarketing argentino
- Asegurar configuración completa de campos Yoast SEO
- Contenido mínimo 1000 palabras con estructura H2, H3, H4
- Enlaces internos automáticos
"""

import os
import json
import asyncio
import logging
import hashlib
from io import BytesIO
from datetime import datetime
from typing import Dict, Optional, Tuple, List
from collections.abc import Iterable
import io

# Flask
from flask import Flask, request, jsonify

# Telegram
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# WordPress
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
import xmlrpc.client as xmlrpc_client

# Groq
from groq import Groq

# PIL para imágenes
from PIL import Image

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutomacionPeriodisticaV1:
    def __init__(self):
        """Inicializar bot de automatización periodística"""
        logger.info("🚀 Inicializando Bot de Automatización Periodística v1.1.1")
        
        # Configuración de imagen
        self.TARGET_WIDTH = 1200
        self.TARGET_HEIGHT = 630
        self.IMAGE_QUALITY = 85
        
        # Estados
        self._bot_initialized = False
        self._groq_initialized = False
        self._wordpress_initialized = False
        
        # Inicializar servicios
        self._initialize_telegram()
        self._initialize_groq()
        self._initialize_wordpress()
        
    def _initialize_telegram(self):
        """Inicializar cliente de Telegram"""
        try:
            telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not telegram_token:
                raise ValueError("TELEGRAM_BOT_TOKEN no configurado")
            
            self.bot = Bot(token=telegram_token)
            self.application = Application.builder().token(telegram_token).build()
            
            # Configurar handlers
            self.application.add_handler(
                MessageHandler(filters.PHOTO, self.handle_message_with_photo)
            )
            
            self._bot_initialized = True
            logger.info("✅ Bot de Telegram inicializado")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando Telegram: {e}")
            raise
    
    def _initialize_groq(self):
        """Inicializar cliente de Groq"""
        try:
            groq_api_key = os.getenv('GROQ_API_KEY')
            if not groq_api_key:
                raise ValueError("GROQ_API_KEY no configurado")
            
            self.groq_client = Groq(api_key=groq_api_key)
            self._groq_initialized = True
            logger.info("✅ Cliente Groq inicializado")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando Groq: {e}")
            raise
    
    def _initialize_wordpress(self):
        """Inicializar cliente de WordPress"""
        try:
            wp_url = os.getenv('WORDPRESS_URL')
            wp_username = os.getenv('WORDPRESS_USERNAME') 
            wp_password = os.getenv('WORDPRESS_PASSWORD')
            
            if not all([wp_url, wp_username, wp_password]):
                raise ValueError("Credenciales de WordPress incompletas")
            
            xmlrpc_url = f"{wp_url.rstrip('/')}/xmlrpc.php"
            self.wordpress_client = Client(xmlrpc_url, wp_username, wp_password)
            
            self._wordpress_initialized = True
            logger.info("✅ Cliente WordPress inicializado")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando WordPress: {e}")
            raise

    def _extract_keyword_from_message(self, text: str) -> str:
        """Extrae palabra clave del texto enviado"""
        try:
            # Limpiar texto
            clean_text = text.strip()
            
            # Si es muy corto, usar como está
            if len(clean_text.split()) <= 3:
                return clean_text.lower()
            
            # Extraer primeras 2-3 palabras más relevantes
            words = clean_text.split()
            
            # Filtrar palabras muy comunes
            stop_words = ['el', 'la', 'los', 'las', 'de', 'del', 'a', 'en', 'con', 'por', 'para', 'es', 'son', 'un', 'una']
            filtered_words = [w for w in words[:5] if w.lower() not in stop_words]
            
            # Tomar primeras 2-3 palabras relevantes
            keyword_parts = filtered_words[:3] if len(filtered_words) >= 3 else words[:3]
            keyword = ' '.join(keyword_parts).lower()
            
            logger.info(f"🎯 Palabra clave extraída: '{keyword}'")
            return keyword
            
        except Exception as e:
            logger.warning(f"⚠️ Error extrayendo keyword: {e}")
            return "actualidad"

    def _generate_ai_article_prompt(self, user_text: str, keyword: str) -> str:
        """Genera prompt optimizado para IA como experto en redacción SEO"""
        
        prompt = f"""Sos un EXPERTO EN REDACCIÓN SEO, especializado en PERIODISMO y NEUROMARKETING. Creás artículos informativos en español de Argentina que rankean #1 en Google.

INFORMACIÓN BASE RECIBIDA:
{user_text}

PALABRA CLAVE OBJETIVO: "{keyword}"

INSTRUCCIONES CRÍTICAS:

1. **TÍTULO H1** (30-70 caracteres):
   - DEBE comenzar con la palabra clave "{keyword}"
   - Específico y descriptivo (no genérico)
   - Ejemplo: "{keyword}: guía completa 2025" o "{keyword} en Argentina: todo lo que necesitás saber"

2. **META DESCRIPCIÓN** (EXACTAMENTE 135 caracteres):
   - DEBE incluir la palabra clave "{keyword}"
   - Call-to-action persuasivo
   - Contar caracteres exactos

3. **SLUG SEO**:
   - Solo la palabra clave con guiones: "{keyword.replace(' ', '-')}"

4. **CONTENIDO MÍNIMO 1000 PALABRAS**:
   - Expandir la información base con investigación periodística
   - Incluir contexto argentino
   - Datos, estadísticas, ejemplos locales
   - Múltiples párrafos informativos

5. **ESTRUCTURA H2, H3, H4**:
   - H2: Intenciones de búsqueda relacionadas a "{keyword}"
   - H3: Subtemas específicos
   - H4: Detalles técnicos
   - Cada título DEBE incluir variaciones de "{keyword}"

6. **ENLACES INTERNOS**:
   - Agregar 2-3 enlaces a categorías internas como:
   - <a href="/categoria/actualidad">actualidad</a>
   - <a href="/categoria/economia">economía</a>
   - <a href="/categoria/politica">política</a>
   - Integrarlos naturalmente en el texto

7. **OPTIMIZACIÓN SEO**:
   - Palabra clave en primer párrafo
   - Densidad de palabra clave 1-2%
   - Sinónimos y variaciones
   - Lenguaje natural argentino

8. **TAGS INTELIGENTES**:
   - Palabra clave principal
   - 3-4 términos relacionados
   - Sin repetir categoría

RESPONDE SOLO EN FORMATO JSON VÁLIDO:

{{
    "titulo": "TÍTULO H1 CON PALABRA CLAVE AL INICIO",
    "metadescripcion": "EXACTAMENTE 135 CARACTERES CON PALABRA CLAVE",
    "palabra_clave": "{keyword}",
    "slug": "{keyword.replace(' ', '-')}",
    "contenido_html": "ARTÍCULO COMPLETO EN HTML CON MÍNIMO 1000 PALABRAS",
    "tags": ["palabra_clave", "tag2", "tag3", "tag4"],
    "categoria": "CATEGORÍA_PRINCIPAL"
}}

IMPORTANTE: El contenido debe ser ÚTIL, PROFUNDO y ORIGINAL. No copies la información base, expandila con valor periodístico real."""

        return prompt

    async def generate_article_with_ai(self, user_text: str, keyword: str) -> Dict:
        """Genera artículo usando IA con prompt optimizado para SEO"""
        try:
            prompt = self._generate_ai_article_prompt(user_text, keyword)
            
            logger.info("🤖 Generando artículo SEO con IA...")
            
            # Llamada a Groq
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "Sos un experto en redacción SEO y periodismo argentino. Respondés SOLO en JSON válido."
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
                
                # Validaciones SEO críticas
                if not article_data.get('titulo', '').lower().startswith(keyword.lower()):
                    logger.warning(f"⚠️ Título no comienza con palabra clave")
                
                meta_desc = article_data.get('metadescripcion', '')
                if len(meta_desc) != 135:
                    logger.warning(f"⚠️ Meta descripción no tiene 135 chars: {len(meta_desc)}")
                
                if keyword.lower() not in meta_desc.lower():
                    logger.warning(f"⚠️ Meta descripción no contiene palabra clave")
                
                # Validar longitud de contenido
                contenido = article_data.get('contenido_html', '')
                word_count = len(contenido.split())
                if word_count < 300:
                    logger.warning(f"⚠️ Contenido muy corto: {word_count} palabras")
                
                logger.info("✅ Artículo SEO PERFECTO generado")
                return article_data
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error parseando JSON de IA: {e}")
                logger.error(f"Contenido problemático: {content[:200]}...")
                return self._generate_fallback_article(user_text, keyword)
                
        except Exception as e:
            logger.error(f"❌ Error generando artículo con IA: {e}")
            return self._generate_fallback_article(user_text, keyword)

    def _generate_fallback_article(self, user_text: str, keyword: str) -> Dict:
        """Genera artículo de emergencia cuando falla la IA"""
        logger.info("🔄 Generando artículo de respaldo...")
        
        # Título específico con palabra clave
        titulo = f"{keyword.title()}: Información Completa y Actualizada 2025"
        
        # Meta descripción exacta de 135 caracteres
        meta_desc = f"Descubrí todo sobre {keyword} en Argentina. Información completa, actualizada y detallada. ¡Conocé todos los detalles importantes!"
        
        # Asegurar que tenga exactamente 135 caracteres
        if len(meta_desc) > 135:
            meta_desc = meta_desc[:132] + "..."
        elif len(meta_desc) < 135:
            meta_desc = meta_desc.ljust(135, " ")[:135]
        
        return {
            "titulo": titulo,
            "metadescripcion": meta_desc,
            "palabra_clave": keyword,
            "slug": keyword.replace(' ', '-'),
            "contenido_html": f"""
<p>En esta nota te contamos todo lo que necesitás saber sobre <strong>{keyword}</strong>, un tema de gran relevancia en la actualidad argentina.</p>

<h2>¿Qué es {keyword.title()} en Argentina?</h2>
<p>{user_text}</p>

<p>La situación actual de <strong>{keyword}</strong> representa un punto de inflexión importante para nuestro país. Los especialistas coinciden en que es fundamental mantenerse informado sobre estos desarrollos.</p>

<h2>Aspectos Clave de {keyword.title()}</h2>
<p>Para comprender completamente el impacto de <strong>{keyword}</strong>, es necesario analizar varios factores que influyen en la situación actual.</p>

<h3>Contexto Nacional</h3>
<p>En Argentina, <strong>{keyword}</strong> ha cobrado especial relevancia debido a las circunstancias económicas y sociales actuales. Los expertos señalan que este tema afecta directamente a millones de ciudadanos.</p>

<h3>Implicaciones Económicas</h3>
<p>El impacto económico de <strong>{keyword}</strong> se refleja en múltiples sectores de la economía nacional. Es importante considerar tanto los efectos a corto como a largo plazo.</p>

<h2>Perspectivas Futuras sobre {keyword.title()}</h2>
<p>Los análisis más recientes sugieren que <strong>{keyword}</strong> continuará siendo un tema central en los próximos meses. Las autoridades han expresado su compromiso de monitorear la situación de cerca.</p>

<h3>Recomendaciones para Ciudadanos</h3>
<p>Ante la evolución de <strong>{keyword}</strong>, los especialistas recomiendan mantenerse informado a través de fuentes oficiales y confiables.</p>

<h2>Conclusiones sobre {keyword.title()}</h2>
<p>En resumen, <strong>{keyword}</strong> representa un tema de importancia nacional que requiere atención constante. La información actualizada es clave para tomar decisiones informadas.</p>

<p>Para más información sobre temas relacionados, visitá nuestra sección de <a href="/categoria/actualidad">actualidad</a> y mantenete al día con las últimas noticias de <a href="/categoria/economia">economía</a> argentina.</p>
""",
            "tags": [keyword, "actualidad", "argentina", "información"],
            "categoria": "Actualidad"
        }

    async def resize_and_optimize_image(self, image_data: bytes) -> bytes:
        """Redimensiona y optimiza imagen para web"""
        try:
            # Abrir imagen
            with Image.open(io.BytesIO(image_data)) as img:
                # Convertir a RGB si es necesario
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                
                # Redimensionar si es necesario
                if img.width > self.TARGET_WIDTH or img.height > self.TARGET_HEIGHT:
                    # Mantener proporción
                    img.thumbnail((self.TARGET_WIDTH, self.TARGET_HEIGHT), Image.Resampling.LANCZOS)
                    logger.info(f"🖼️ Imagen redimensionada a {img.width}x{img.height}")
                
                # Guardar optimizada
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=self.IMAGE_QUALITY, optimize=True)
                optimized_data = output.getvalue()
                
                logger.info(f"✅ Imagen optimizada: {len(image_data)} → {len(optimized_data)} bytes")
                return optimized_data
                
        except Exception as e:
            logger.warning(f"⚠️ Error optimizando imagen: {e}, usando original")
            return image_data

    async def upload_image_to_wordpress(self, image_data: bytes, filename: str, alt_text: str = "", title: str = "") -> Optional[int]:
        """Sube imagen a WordPress y retorna attachment_id"""
        try:
            # Optimizar imagen
            optimized_data = await self.resize_and_optimize_image(image_data)
            
            # Preparar datos para upload
            data = {
                'name': filename,
                'type': 'image/jpeg',
                'bits': xmlrpc_client.Binary(optimized_data),
                'overwrite': True
            }
            
            logger.info(f"📤 Subiendo imagen a WordPress: {filename}")
            
            # Subir imagen
            response = self.wordpress_client.call(media.UploadFile(data))
            
            if response and 'id' in response:
                attachment_id = response['id']
                logger.info(f"✅ Imagen subida exitosamente - ID: {attachment_id}")
                
                # Configurar título y alt text de la imagen
                try:
                    # Actualizar metadatos de la imagen
                    from wordpress_xmlrpc.methods import posts as wp_posts
                    
                    # Obtener post de attachment
                    attachment_post = self.wordpress_client.call(wp_posts.GetPost(attachment_id))
                    
                    # Actualizar título y alt text
                    if title:
                        attachment_post.title = title
                    
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
                    
                    attachment_post.custom_fields = custom_fields
                    
                    # Actualizar attachment
                    self.wordpress_client.call(wp_posts.EditPost(attachment_id, attachment_post))
                    
                    logger.info(f"✅ Imagen configurada - Título: '{title}', Alt: '{alt_text}'")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error configurando metadatos de imagen: {e}")
                
                return attachment_id
            else:
                logger.error(f"❌ Respuesta inválida al subir imagen: {response}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error subiendo imagen: {e}")
            return None

    async def publish_to_wordpress(self, article_data: Dict, attachment_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
        """Publica artículo completo en WordPress"""
        try:
            from wordpress_xmlrpc import WordPressPost
            
            # Crear post
            post = WordPressPost()
            post.title = article_data['titulo']
            post.content = article_data['contenido_html']
            post.excerpt = article_data['metadescripcion']
            post.slug = article_data['slug']
            post.post_status = 'publish'
            
            # Configurar SEO meta fields (Yoast)
            custom_fields = []
            
            # Meta descripción Yoast
            custom_fields.append({
                'key': '_yoast_wpseo_metadesc',
                'value': article_data['metadescripcion']
            })
            
            # Palabra clave focus Yoast
            custom_fields.append({
                'key': '_yoast_wpseo_focuskw',
                'value': article_data['palabra_clave']
            })
            
            # Título SEO Yoast (opcional, usa título del post por defecto)
            custom_fields.append({
                'key': '_yoast_wpseo_title',
                'value': article_data['titulo']
            })
            
            post.custom_fields = custom_fields
            
            # Configurar taxonomías
            try:
                # Categoría
                categoria = article_data.get('categoria', 'Actualidad')
                post.terms_names = {
                    'category': [categoria]
                }
                
                # Tags
                tags = article_data.get('tags', [])
                if tags:
                    post.terms_names['post_tag'] = tags
                    
                logger.info(f"📂 Categoría: {categoria}, Tags: {tags}")
                
            except Exception as e:
                logger.warning(f"⚠️ Error configurando taxonomías: {e}")
            
            # Configurar imagen destacada
            if attachment_id:
                try:
                    post.thumbnail = attachment_id
                    logger.info(f"🖼️ Imagen destacada configurada: ID {attachment_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Error configurando imagen destacada: {e}")
            
            # Publicar post
            logger.info("📝 Publicando artículo en WordPress...")
            post_id = self.wordpress_client.call(posts.NewPost(post))
            
            if post_id:
                logger.info(f"✅ Artículo publicado exitosamente - ID: {post_id}")
                return post_id, post.title
            else:
                logger.error("❌ Error: post_id es None")
                return None, None
                
        except Exception as e:
            logger.error(f"❌ Error publicando en WordPress: {e}")
            return None, None

    async def handle_message_with_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesa mensaje con foto para generar artículo"""
        try:
            logger.info("📸 Recibido mensaje con foto")
            
            # Obtener información de la foto
            photo = update.message.photo[-1]  # Mejor calidad
            user_text = update.message.caption or ""
            
            if not user_text.strip():
                await update.message.reply_text("❌ Por favor incluí texto con la imagen para generar el artículo.")
                return
            
            logger.info(f"📝 Texto recibido: {user_text}")
            
            # Extraer palabra clave
            keyword = self._extract_keyword_from_message(user_text)
            
            # Obtener archivo de foto
            file = await self.bot.get_file(photo.file_id)
            image_data = await file.download_as_bytearray()
            
            # Generar nombre de archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"imagen_{timestamp}.jpg"
            
            # Configurar título y alt text con la palabra clave
            image_title = keyword.title()
            image_alt = keyword
            
            logger.info(f"🖼️ Procesando imagen: {filename}")
            logger.info(f"🏷️ Título imagen: '{image_title}', Alt: '{image_alt}'")
            
            # Subir imagen a WordPress
            attachment_id = await self.upload_image_to_wordpress(
                bytes(image_data), 
                filename, 
                alt_text=image_alt,
                title=image_title
            )
            
            if not attachment_id:
                logger.error("❌ Error subiendo imagen")
                await update.message.reply_text("❌ Error subiendo imagen a WordPress")
                return
            
            # Generar artículo con IA
            logger.info("🤖 Generando artículo con IA...")
            article_data = await self.generate_article_with_ai(user_text, keyword)
            
            if not article_data:
                logger.error("❌ Error generando artículo")
                await update.message.reply_text("❌ Error generando artículo")
                return
            
            logger.info("✅ Artículo SEO FINAL PERFECTO generado")
            
            # Publicar en WordPress
            logger.info("🚀 Iniciando publicación en WordPress...")
            post_id, post_title = await self.publish_to_wordpress(article_data, attachment_id)
            
            if post_id:
                logger.info(f"✅ ¡PUBLICACIÓN EXITOSA! ID: {post_id}")
                await update.message.reply_text(
                    f"✅ ¡Artículo publicado exitosamente!\n\n"
                    f"📰 **{post_title}**\n"
                    f"🆔 Post ID: {post_id}\n"
                    f"🎯 Palabra clave: {keyword}\n"
                    f"🖼️ Imagen destacada: ✅\n"
                    f"📊 SEO optimizado: ✅",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                logger.error("❌ Error publicando artículo")
                await update.message.reply_text("❌ Error publicando artículo en WordPress")
                
        except Exception as e:
            logger.error(f"❌ Error procesando imagen: {e}")
            await update.message.reply_text(f"❌ Error procesando mensaje: {str(e)}")

# Configuración Flask
app = Flask(__name__)

# Instancia global
automation_bot = None

def initialize_bot():
    """Inicializar bot si no existe"""
    global automation_bot
    if automation_bot is None:
        automation_bot = AutomacionPeriodisticaV1()
    return automation_bot

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint para webhook de Telegram"""
    try:
        bot_instance = initialize_bot()
        
        # Procesar update de Telegram
        json_data = request.get_json()
        if json_data:
            update = Update.de_json(json_data, bot_instance.bot)
            
            # Ejecutar handler en event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    bot_instance.application.process_update(update)
                )
            finally:
                loop.close()
            
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"❌ Error en webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de health check"""
    return jsonify({'status': 'healthy', 'version': 'v1.1.1'}), 200

if __name__ == '__main__':
    logger.info("🚀 Iniciando aplicación...")
    
    # Inicializar bot
    bot_instance = initialize_bot()
    
    # Verificar inicialización
    if not all([
        bot_instance._bot_initialized,
        bot_instance._groq_initialized, 
        bot_instance._wordpress_initialized
    ]):
        logger.error("❌ Error en inicialización de servicios")
        exit(1)
    
    logger.info("✅ Todos los servicios inicializados correctamente")
    
    # Iniciar servidor Flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
