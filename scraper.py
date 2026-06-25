import os
import json
import random
import re
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# =====================================================================
# CONFIGURACIÓN DE VARIABLES DE ENTORNO
# =====================================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "TU_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "TU_SUPABASE_KEY")

def generar_mock_ofertas_representativas():
    """Genera una muestra estadística robusta de vacantes estructuradas en Data, BI e IA"""
    roles = ["Data Scientist", "Analista de BI", "Data Engineer", "AI Engineer", "Gerente de Analítica", "Data Analyst"]
    empresas = ["BCP", "Interbank", "Rímac", "Alicorp", "Belcorp", "Inetum", "NTT DATA", "Globant", "Scotiabank", "Mindrift"]
    paises = ["Perú", "Colombia", "Chile", "México", "Remoto Latam"]
    
    jerarquias = [
        "Practicante / Asistente", 
        "Analista Junior", 
        "Analista / Profesional", 
        "Analista Senior / Especialista", 
        "Líder / Jefe", 
        "Gerente / Head"
    ]
    
    especialidades = [
        "Data Science", \
        "Business Intelligence", \
        "Data Engineering", \
        "Artificial Intelligence", \
        "Data Management",\
        "Data Analytics"
    ]
    
    pool_hard_skills = ["Python", "SQL", "Power BI", "AWS", "Databricks", "Spark", "R", "Tableau", "Snowflake", "Docker", "Machine Learning", "Git"]
    pool_soft_skills = ["Comunicación Asertiva", "Liderazgo", "Resolución de Problemas", "Trabajo en Equipo", "Pensamiento Crítico", "Negociación"]
    
    descripciones_ejemplo = [
        "Buscamos un profesional apasionado por los datos para unirse a nuestro equipo. Te encargarás de diseñar pipelines de datos, construir modelos predictivos y transformar la información en insights de alto impacto para la toma de decisiones estratégicas. Es indispensable dominar entornos en la nube y optimización de consultas complejas.",
        "Oportunidad clave para liderar la cultura Data-Driven. El perfil requiere alta capacidad analítica para diseñar tableros de control integrados, automatizar reportes directos a la gerencia y descubrir tendencias de mercado mediante análisis estadísticos avanzados.",
        "Buscamos Ingeniero/a enfocado en desplegar arquitecturas de IA y soluciones de analítica a gran escala. Trabajarás integrando APIs avanzadas de LLMs, optimizando bases de datos vectoriales y asegurando la escalabilidad de nuestros productos de inteligencia artificial."
    ]
    
    ofertas = []
    fecha_hoy = datetime.utcnow().isoformat()
    
    for i in range(200):
        rol_seleccionado = random.choice(roles)
        h_skills = random.sample(pool_hard_skills, random.randint(3, 6))
        s_skills = random.sample(pool_soft_skills, random.randint(2, 4))
        
        oferta = {
            "link_oferta": f"https://www.linkedin.com/jobs/view/simulado-{i+1000}",
            "titulo": rol_seleccionado,
            "empresa": random.choice(empresas),
            "pais": random.choice(paises),
            "jerarquia": random.choice(jerarquias),
            "especialidad_objetivo": random.choice(especialidades),
            "descripcion": random.choice(descripciones_ejemplo),
            "hard_skills": json.dumps(h_skills),
            "soft_skills": json.dumps(s_skills),
            "created_at": fecha_hoy
        }
        ofertas.append(oferta)
        
    return ofertas

def cargar_vacantes_a_supabase():
    """Pobla la base de datos controlando el almacenamiento de la capa gratuita"""
    if not SUPABASE_URL or SUPABASE_URL == "TU_SUPABASE_URL":
        print("⚠️ Configuración de Supabase ausente o por defecto. Omitiendo persistencia.")
        return
        
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # --- OPTIMIZACIÓN DE ALMACENAMIENTO (RETENCIÓN DE 30 DÍAS) ---
        # Evita que las ejecuciones diarias del CRON agoten los 500MB gratuitos
        try:
            limite_retencion = (datetime.utcnow() - timedelta(days=30)).isoformat()
            supabase.table("vacantes").delete().lt("created_at", limite_retencion).execute()
            print("🧹 Mantenimiento: Vacantes con más de 30 días de antigüedad depuradas con éxito.")
        except Exception as e:
            print(f"⚠️ Nota en mantenimiento preventivo: {str(e)}")

        # --- OPTIMIZACIÓN DE CONEXIONES (BULK INSERT) ---
        # Pasamos de un bucle 'for' ineficiente a inyectar las 200 filas en un solo viaje de red
        print("Generando lote de vacantes actualizadas...")
        nuevas_vacantes = generar_mock_ofertas_representativas()
        
        print(f"Enviando lote masivo de {len(nuevas_vacantes)} registros a Supabase...")
        resultado = supabase.table("vacantes").insert(nuevas_vacantes).execute()
        print(f"🚀 Base de datos actualizada. Se han indexado {len(resultado.data)} ofertas exitosamente.")
        
    except Exception as e:
        print(f"❌ Error crítico en el proceso de carga a Supabase: {str(e)}")

def extraer_mercado_vacantes():
    """
    Punto de entrada clave requerido por app.py.
    Intenta descargar las vacantes vigentes desde Supabase; si falla,
    activa el plan de contingencia generando datos en memoria para no romper la UI.
    """
    if not SUPABASE_URL or SUPABASE_URL == "TU_SUPABASE_URL":
        print("Variables de producción no configuradas. Activando modo simulación local.")
        return pd.DataFrame(generar_mock_ofertas_representativas()), "Simulado / Local"
        
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        # Traemos las vacantes ordenadas por la fecha más reciente
        respuesta = supabase.table("vacantes").select("*").order("created_at", ascending=False).execute()
        
        if respuesta.data and len(respuesta.data) > 0:
            df = pd.DataFrame(respuesta.data)
            # Sanitizamos los campos JSON que app.py parsea con json.loads()
            for col in ['hard_skills', 'soft_skills']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x)
            return df, "Supabase Cloud"
        else:
            print("Base de datos vacía. Generando contingencia...")
            return pd.DataFrame(generar_mock_ofertas_representativas()), "Simulado / Contingencia"
    except Exception as e:
        print(f"Fallo en la conexión a Supabase ({str(e)}). Redirigiendo a contingencia.")
        return pd.DataFrame(generar_mock_ofertas_representativas()), "Simulado / Contingencia"

def calcular_match_ats_cv(texto_cv, df_ofertas):
    """
    Algoritmo de Screening Estadístico Vectorial (TF-IDF + Similitud Coseno).
    Filtra preliminarmente el grueso del mercado para seleccionar el top de vacantes
    viables antes de que app.py delegue la evaluación cognitiva pesada a Gemini.
    """
    if df_ofertas.empty or not texto_cv:
        return pd.DataFrame()
    
    def preprocesar(texto):
        texto = str(texto).lower()
        # Remueve caracteres especiales preservando espacios
        return re.sub(r'[^\w\s]', ' ', texto)

    cv_limpio = preprocesar(texto_cv)
    descripciones = df_ofertas['descripcion'].fillna('').apply(preprocesar).tolist()
    
    vectorizer = TfidfVectorizer()
    # Ajustamos y transformamos la matriz incluyendo el CV en la posición 0
    tfidf_matrix = vectorizer.fit_transform([cv_limpio] + descripciones)
    
    # Calculamos la similitud del CV (índice 0) contra todas las ofertas (índices 1 en adelante)
    similitudes = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    
    df_analisis = df_ofertas.copy()
    df_analisis['score_screening'] = similitudes * 100
    
    # Retorna las 15 ofertas con mejor afinidad matemática, ordenadas descendentemente
    return df_analisis.sort_values(by='score_screening', ascending=False).head(15)

# =====================================================================
# BLOQUE DE EJECUCIÓN (AUDITORÍA Y POBLAMIENTO)
# =====================================================================
if __name__ == "__main__":
    print("--- INICIANDO AUDITORÍA Y COMPILACIÓN DE DATA DE MERCADO ---")
    cargar_vacantes_a_supabase()
    print("--- PROCESO FINALIZADO ---")
