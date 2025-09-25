"""
TELEGRAM BOT SEO PROFESIONAL - VERSIÓN 6.5.2
===============================================
FECHA: 2025-09-26
ESTADO: DEBUG — Se mejora el log de errores de Groq
MEJORAS:
✅ Mejor logging de errores de Groq
✅ Más contexto en caso de fallo de IA
"""
# ... (todo el código igual hasta aquí) ...

# Generar contenido SEO con Groq
async def generate_seo_content(caption: str) -> Optional[dict]:
    prompt = f"""
Eres un periodista argentino experto en SEO. Convierte esta información en un artículo periodístico completo y optimizado:
INFORMACIÓN: {caption}
Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:
{{
    "keyword_principal": "frase clave objetivo (2-3 palabras)",
    "titulo": "Keyword Principal: Título periodístico llamativo (30-70 caracteres)",
    "slug": "titulo-seo-amigable",
    "meta_descripcion": "Meta descripción real y atractiva, <= 156 caracteres, con la keyword y buen gancho",
    "contenido_html": "Artículo en HTML con <h1>, <h2>, <h3>, <p>, <strong>, <ul>, <li>. Mínimo 500 palabras. Incluye 1 enlace interno (elige entre: {', '.join(existing_categories) if existing_categories else 'actualidad'}). NO enlaces salientes a otros medios. Usa comillas simples. Repite la keyword 4-6 veces.",
    "tags": ["keyword_principal", "tag2", "tag3", "tag4", "tag5"],
    "alt_text": "Descripción SEO de la imagen (máx. 120 caracteres, específica)",
    "categoria": "Categoría principal (elige entre: {', '.join(existing_categories) if existing_categories else 'Actualidad, Internacional, Política'})"
}}
REGLAS:
- keyword_principal: específica y relevante
- titulo: keyword al inicio
- meta_descripcion: <= 156 caracteres, sin "prompt"
- contenido_html: mínimo 500 palabras, sin comillas dobles, sin &quot;, repite keyword 4-6 veces, NO enlaces a otros medios
- categoría: NO inventes, usa solo las permitidas
- tags: incluye keyword_principal como primer tag
"""
    try:
        logger.info("🔍 Enviando solicitud a Groq...")
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=8000
        )
        raw = completion.choices[0].message.content
        logger.info("✅ Respuesta recibida de Groq. Procesando JSON...")
        result = extract_json_robust(raw)
        if result:
            logger.info("✅ JSON extraído correctamente.")
            return result
        else:
            logger.error("❌ No se pudo extraer un JSON válido de la respuesta de Groq.")
            logger.debug(f"Respuesta cruda de Groq: {raw[:500]}...")  # Solo los primeros 500 chars
            return None
    except Exception as e:
        logger.error(f"❌ Error con Groq: {e}")
        return None

# ... (el resto del código sigue igual) ...
