#!/usr/bin/env python3
import os
import logging
import requests
from flask import Flask, request, jsonify
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

# Inicializar clientes
groq_client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)

class ArticleBot:
    def __init__(self):
        # Cliente WordPress
        self.wordpress_client = Client(WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD)
        
        # Session para requests con timeout
        self.session = requests.Session()
        self.session.timeout = 15
        
        # URLs base de Telegram API
        self.telegram_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
        
        logger.info("✅ ArticleBot inicializado correctamente - SOLO requests síncronos")

    def send_telegram_message(self, chat_id, text):
        """Envía mensaje usando requests síncronos puros"""
        try:
            url = f"{self.telegram_base}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text
            }
            
            response = self.session.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Mensaje enviado exitosamente")
                return True
            else:
                logger.error(f"❌ Error enviando mensaje: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error enviando mensaje: {e}")
            return False

    def get_telegram_file_info(self, file_id):
        """Obtiene info del archivo usando requests síncronos"""
        try:
            url = f"{self.telegram_base}/getFile"
            params = {'file_id': file_id}
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return data['result']['file_path']
            
            logger.error(f"❌ Error obteniendo info del archivo: {response.status_code}")
            return None
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo info del archivo: {e}")
            return None

    def download_telegram_image(self, file_path):
        """Descarga imagen usando requests síncronos"""
        try:
            image_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
            
            response = self.session.get(image_url, timeout=15)
            
            if response.status_code == 200:
                logger.info("✅ Imagen descargada exitosamente")
                return response.content
            else:
                logger.error(f"❌ Error descargando imagen: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error descargando imagen: {e}")
            return None

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
📌 TÍTULO H1: 30-70 caracteres, ESPECÍFICO y claro
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
  "contenido_html": "Artículo completo con H2, H3 y enlaces internos SOLO a categorías existentes"
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
            """
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

    def process_image_message(self, update_data):
        """Procesa mensaje con imagen - COMPLETAMENTE síncrono"""
        try:
            message = update_data['message']
            chat_id = message['chat']['id']
            
            # Obtener la imagen de mayor resolución
            photos = message.get('photo', [])
            if not photos:
                logger.error("❌ No se encontraron fotos en el mensaje")
                return
                
            photo = photos[-1]  # Mayor resolución
            file_id = photo['file_id']
            
            text = message.get('caption', 'Artículo informativo')
            
            logger.info(f"📸 Procesando mensaje con foto")
            logger.info(f"📝 Texto: {text[:100]}...")
            
            # Obtener categorías WordPress existentes
            existing_categories = self.get_existing_categories()
            
            # Generar artículo con IA
            logger.info("🤖 Generando artículo con IA...")
            article_data = self.generate_seo_article_with_ia(text, existing_categories)
            
            # Obtener info del archivo de Telegram
            file_path = self.get_telegram_file_info(file_id)
            if not file_path:
                self.send_telegram_message(chat_id, "❌ Error obteniendo info de la imagen")
                return
            
            # Descargar imagen
            logger.info("📥 Descargando imagen...")
            image_data = self.download_telegram_image(file_path)
            
            if not image_data:
                self.send_telegram_message(chat_id, "❌ Error descargando la imagen")
                return
            
            # Subir imagen a WordPress
            logger.info("📤 Subiendo imagen a WordPress...")
            image_id = self.upload_image_to_wordpress(image_data, article_data['palabra_clave'])
            
            # Publicar artículo
            logger.info("📰 Publicando artículo...")
            post_id = self.publish_to_wordpress(article_data, image_id)
            
            if post_id:
                success_message = f"""✅ ¡Artículo publicado!

📰 {article_data['titulo_h1']}
🎯 Palabra clave: {article_data['palabra_clave']}
🔗 Post ID: {post_id}"""
                
                self.send_telegram_message(chat_id, success_message)
            else:
                self.send_telegram_message(chat_id, "❌ Error publicando el artículo")
                
        except Exception as e:
            logger.error(f"❌ Error procesando imagen: {e}")

# Instancia global única
article_bot = ArticleBot()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook 100% síncrono - Sin librerías async de Telegram"""
    try:
        update_data = request.get_json()
        
        if not update_data:
            return jsonify({'error': 'No JSON data'}), 400
        
        # Verificar si hay mensaje con foto
        if update_data.get('message') and update_data['message'].get('photo'):
            # Procesamiento completamente síncrono
            article_bot.process_image_message(update_data)
        
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
        "version": "1.1.9"
    }), 200

if __name__ == '__main__':
    logger.info("🚀 Iniciando ArticleBot v1.1.9 - SOLO requests síncronos...")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
