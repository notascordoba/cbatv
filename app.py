#!/usr/bin/env python3
import os
import logging
import asyncio
import requests
from flask import Flask, request, jsonify
from telegram import Update, Bot
from datetime import datetime
from groq import Groq
import json
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media, taxonomies
from wordpress_xmlrpc.compat import xmlrpc_client
import tempfile

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables de entorno
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
WORDPRESS_URL = os.getenv('WORDPRESS_URL')
WORDPRESS_USERNAME = os.getenv('WORDPRESS_USERNAME')
WORDPRESS_PASSWORD = os.getenv('WORDPRESS_PASSWORD')

# Validación de variables de entorno
required_vars = ['TELEGRAM_TOKEN', 'GROQ_API_KEY', 'WORDPRESS_URL', 'WORDPRESS_USERNAME', 'WORDPRESS_PASSWORD']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"❌ Variables de entorno faltantes: {missing_vars}")
    exit(1)

# Inicializar clientes GLOBALES (patrón v1.1.0)
groq_client = Groq(api_key=GROQ_API_KEY)

app = Flask(__name__)

class ArticleBot:
    def __init__(self):
        # Cliente WordPress
        self.wordpress_client = Client(WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
        
        # ✅ UNA SOLA instancia de Bot (patrón v1.1.0)
        self.bot = Bot(token=TELEGRAM_TOKEN)
        
        logger.info("✅ ArticleBot inicializado correctamente")

    def get_existing_categories(self):
        """Obtiene las categorías existentes de WordPress"""
        try:
            categories = self.wordpress_client.call(taxonomies.GetTerms('category'))
            category_list = [cat.name.lower() for cat in categories if hasattr(cat, 'name')]
            logger.info(f"✅ Categorías WordPress encontradas: {category_list}")
            return category_list
        except Exception as e:
            logger.error(f"❌ Error obteniendo categorías WordPress: {e}")
            return ['actualidad', 'noticias']

    def generate_seo_article_with_ia(self, topic, existing_categories):
        """Genera artículo SEO optimizado con IA"""
        categories_str = ", ".join(existing_categories)
        
        prompt = f"""
Eres un EXPERTO EN REDACCIÓN SEO especializado en PERIODISMO y NEUROMARKETING. 

Crea un artículo INFORMATIVO en ESPAÑOL DE ARGENTINA sobre: "{topic}"

INSTRUCCIONES CRÍTICAS:
📌 PALABRA CLAVE: Extrae UNA palabra clave ESPECÍFICA y RELEVANTE del tema
📌 TÍTULO H1: 30-70 caracteres, ESPECÍFICO y claro (ej: "PJ Critica Plan Energético del Gobierno Nacional")
📌 LONGITUD: 600-1000 palabras mínimo
📌 ESTRUCTURA: H1 > Introducción > H2 con H3 subsecciones > Conclusión natural
📌 LENGUAJE: Natural argentino, NO robótico
📌 SEO: Meta descripción 120-130 caracteres con palabra clave
📌 KEYWORDS: Densidad natural, máximo 6 menciones
📌 ENLACES: SOLO a estas categorías WordPress existentes: {categories_str}

FORMATO REQUERIDO:
{{
  "titulo_h1": "Título específico de 30-70 caracteres",
  "palabra_clave": "palabra-clave-especifica",
  "meta_descripcion": "Descripción de 120-130 caracteres con palabra clave",
  "slug": "slug-optimizado-con-palabra-clave",
  "contenido_html": "Artículo completo con H2, H3 y enlaces internos SOLO a categorías existentes",
  "resumen_imagen": "Descripción específica para imagen del tema exacto"
}}

RECORDA: Actúa como PERIODISTA ARGENTINO experto, NO como IA genérica.
"""
        
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            logger.info(f"✅ Artículo generado exitosamente")
            
            # Parsear JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                logger.warning("⚠️ No se encontró JSON válido, usando formato de respaldo")
                return self._create_fallback_article(topic)
                
        except Exception as e:
            logger.error(f"❌ Error generando artículo con IA: {e}")
            return self._create_fallback_article(topic)

    def _create_fallback_article(self, topic):
        """Artículo de respaldo si falla la IA"""
        return {
            "titulo_h1": f"Información sobre {topic[:50]}",
            "palabra_clave": "información-política",
            "meta_descripcion": f"Conocé los detalles sobre {topic[:80]}. Info completa para Argentina.",
            "slug": "informacion-politica-actualizada",
            "contenido_html": f"""
            <p>Te contamos toda la información sobre <strong>la situación política actual</strong>.</p>
            <h2>Detalles Importantes</h2>
            <p>{topic}</p>
            <p>Para más información, visitá nuestra sección de <a href="/categoria/actualidad">actualidad</a>.</p>
            """,
            "resumen_imagen": f"Imagen sobre {topic[:50]}"
        }

    def upload_image_to_wordpress(self, image_data, alt_text_imagen):
        """Sube imagen a WordPress con título y alt text configurados"""
        try:
            # Crear archivo temporal
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"imagen_{timestamp}.jpg"
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(image_data)
            temp_file.close()
            
            # Subir a WordPress
            with open(temp_file.name, 'rb') as img_file:
                data = {
                    'name': filename,
                    'type': 'image/jpeg',
                    'bits': xmlrpc_client.Binary(img_file.read())
                }
                
                response = self.wordpress_client.call(media.UploadFile(data))
                logger.info(f"✅ Imagen subida con ID: {response['id']}")
                
                # CONFIGURAR TÍTULO Y ALT TEXT
                post = WordPressPost()
                post.title = alt_text_imagen
                post.custom_fields = []
                
                # Alt text
                post.custom_fields.append({
                    'key': '_wp_attachment_image_alt',
                    'value': alt_text_imagen
                })
                
                # Actualizar metadata
                self.wordpress_client.call(posts.EditPost(response['id'], post))
                logger.info(f"✅ Título y alt text configurados: '{alt_text_imagen}'")
                
                # Limpiar archivo temporal
                os.unlink(temp_file.name)
                
                return response['id']
                
        except Exception as e:
            logger.error(f"❌ Error subiendo imagen: {e}")
            return None

    def publish_to_wordpress(self, article_data, image_id=None):
        """Publica artículo en WordPress con configuración SEO completa"""
        try:
            post = WordPressPost()
            post.title = article_data['titulo_h1']
            post.content = article_data['contenido_html']
            post.post_status = 'publish'
            post.comment_status = 'open'
            
            # Imagen destacada
            if image_id:
                post.thumbnail = image_id
                logger.info(f"✅ Imagen destacada configurada: {image_id}")
            
            # Configuración SEO Yoast
            post.custom_fields = []
            
            # Meta descripción
            post.custom_fields.append({
                'key': '_yoast_wpseo_metadesc',
                'value': article_data['meta_descripcion']
            })
            
            # Palabra clave principal
            post.custom_fields.append({
                'key': '_yoast_wpseo_focuskw',
                'value': article_data['palabra_clave']
            })
            
            # Slug optimizado
            post.slug = article_data['slug']
            
            # Publicar
            post_id = self.wordpress_client.call(posts.NewPost(post))
            logger.info(f"✅ Artículo publicado con ID: {post_id}")
            
            return post_id
            
        except Exception as e:
            logger.error(f"❌ Error publicando en WordPress: {e}")
            return None

    async def handle_message_with_photo(self, update):
        """Procesa mensaje con imagen usando el patrón exitoso de v1.1.0"""
        try:
            message = update.message
            chat_id = message.chat_id
            
            # Obtener la imagen de mayor resolución
            photo = message.photo[-1]
            text = message.caption or "Artículo informativo"
            
            logger.info(f"📸 Procesando mensaje con foto")
            logger.info(f"📝 Texto: {text[:100]}...")
            
            # ✅ Usar self.bot (MISMA instancia, patrón v1.1.0)
            await self.bot.send_message(chat_id=chat_id, text="📝 Procesando tu solicitud...")
            
            # Obtener categorías WordPress existentes
            existing_categories = self.get_existing_categories()
            
            # Generar artículo con IA
            logger.info("🤖 Generando artículo con IA...")
            article_data = self.generate_seo_article_with_ia(text, existing_categories)
            
            # ✅ Descargar imagen usando self.bot (patrón v1.1.0)
            file = await self.bot.get_file(photo.file_id)
            image_response = requests.get(file.file_path)  # ✅ Patrón original de v1.1.0
            
            if image_response.status_code != 200:
                await self.bot.send_message(chat_id=chat_id, text="❌ Error descargando la imagen")
                return
            
            image_data = image_response.content
            
            # Subir imagen a WordPress
            logger.info("📤 Subiendo imagen a WordPress...")
            image_id = self.upload_image_to_wordpress(image_data, article_data['palabra_clave'])
            
            # Publicar artículo
            logger.info("📰 Publicando artículo...")
            post_id = self.publish_to_wordpress(article_data, image_id)
            
            if post_id:
                success_message = f"""✅ ¡Artículo publicado exitosamente!

📰 Título: {article_data['titulo_h1']}
🎯 Palabra clave: {article_data['palabra_clave']}
📝 Meta descripción: {article_data['meta_descripcion']}
🔗 Slug: {article_data['slug']}
📸 Imagen destacada: {"Sí" if image_id else "No"}

🔗 Post ID: {post_id}"""
                
                await self.bot.send_message(chat_id=chat_id, text=success_message)
            else:
                await self.bot.send_message(chat_id=chat_id, text="❌ Error publicando el artículo")
                
        except Exception as e:
            logger.error(f"❌ Error procesando imagen: {e}")
            await self.bot.send_message(chat_id=chat_id, text=f"❌ Error: {str(e)}")

# ✅ Instancia GLOBAL única (patrón v1.1.0)
article_bot = ArticleBot()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook usando patrón exitoso de v1.1.0"""
    try:
        json_str = request.get_data().decode('UTF-8')
        
        # ✅ Usar self.bot de la instancia global (patrón v1.1.0)
        update = Update.de_json(json.loads(json_str), article_bot.bot)
        
        if update.message and update.message.photo:
            # ✅ Patrón exacto de v1.1.0
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(article_bot.handle_message_with_photo(update))
            finally:
                loop.close()
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"Error crítico en webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.1.7"
    }), 200

if __name__ == '__main__':
    logger.info("🚀 Iniciando ArticleBot v1.1.7 - Patrón exitoso de v1.1.0...")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
