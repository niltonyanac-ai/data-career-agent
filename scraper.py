import os
import json
import random
import re
import pandas as pd
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
        "Data Science", 
        "Business Intelligence", 
        "Data Engineering", 
        "Artificial Intelligence", 
        "Data Management",
        "Data Analytics"
    ]
    
    pool_hard_skills = {
        "Data Science": ["Python", "R", "Machine Learning", "Scikit-Learn", "SQL", "AWS", "Docker"],
        "Business Intelligence": ["Power BI", "SQL", "Tableau", "ETL", "Excel", "Data Warehouse", "DAX"],
        "Data Engineering": ["Python", "SQL", "Spark", "Airflow", "Snowflake", "Databricks", "AWS", "Azure"],
        "Artificial Intelligence": ["Python", "PyTorch", "TensorFlow", "LLMs", "LangChain", "OpenAI API", "NLP"],
        "Data Management": ["Gobierno de Datos", "Data Quality", "SQL", "Collibra", "Scrum", "KPIs"],
        "Data Analytics": ["Python", "SQL", "Excel", "Estadística Inferencial", "A/B Testing", "Mixpanel"]
    }
    
    pool_soft_skills = ["Comunicación Asertiva", "Liderazgo", "Resolución de Problemas", "Trabajo en Equipo", "Pensamiento Crítico", "Negociación"]
    
    ofertas = []
    for i in range(200):
        esp = random.choice(especialidades)
        rol = random.choice(roles) if esp != "Business Intelligence" else "Analista de BI"
        nivel = random.choice(jerarquias)
        titulo = f"{rol} ({nivel})"
        
        h_skills = random.sample(pool_hard_skills[esp], k=min(4, len(pool_hard_skills[esp])))
        s_skills = random.sample(pool_soft_skills, k=3)
        emp = random.choice(empresas)
        pais = random.choice(paises)
        
        ofertas.append({
            "link_oferta": f"https://www.linkedin.com/jobs/view/simulado-{i+1000}",
            "titulo": titulo,
            "empresa": emp,
            "pais": pais,
            "jerarquia": nivel,
            "especialidad_objetivo": esp,
            "descripcion": f"Buscamos un {titulo} para unirse al equipo de {emp} en {pais}. Requisitos clave: {', '.join(h_skills)}. Capacidad de {', '.join(s_skills)}.",
            "hard_skills": json.dumps(h_skills), # Almacenado como JSON String para coincidir con tu esquema de Supabase
            "soft_skills": json.dumps(s_skills)   # Almacenado como JSON String para coincidir con tu esquema de Supabase
        })
    return ofertas

def cargar_vacantes_a_supabase():
    """Pobla la base de datos de producción usando inserciones controladas."""
    if SUPABASE_URL == "TU_SUPABASE_URL" or not SUPABASE_URL:
        print("⚠️ Configura las variables de entorno válidas de Supabase antes de ejecutar la carga.")
        return
        
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    ofertas = generar_mock_ofertas_representativas()
    
    print(f"Iniciando carga de {len(ofertas)} ofertas indexadas...")
    exitos = 0
    for oferta in ofertas:
        try:
            supabase.table("vacantes").insert(oferta).execute()
            exitos += 1
        except Exception as e:
            print(f"Error insertando oferta individual: {str(e)}")
            
    print(f"Procesamiento finalizado. {exitos} registros nuevos indexados con éxito.")

def obtener_datos_produccion():
    """Descarga la data real de Supabase. Activa contingencia automática si el canal falla."""
    if SUPABASE_URL == "TU_SUPABASE_URL" or not SUPABASE_URL:
        return pd.DataFrame(generar_mock_ofertas_representativas()), "Simulado / Contingencia"
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        response = supabase.table("vacantes").select("*").execute()
        if response.data and len(response.data) > 0:
            return pd.DataFrame(response.data), "Producción / Supabase"
        return pd.DataFrame(generar_mock_ofertas_representativas()), "Simulado / Contingencia"
    except Exception as e:
        print(f"Alerta: Fallo en conexión productiva ({e}). Redirigiendo a contingencia.")
        return pd.DataFrame(generar_mock_ofertas_representativas()), "Simulado / Contingencia"

def calcular_match_ats_cv(texto_cv, df_ofertas):
    """
    Realiza un screening preliminar estadístico por TF-IDF para seleccionar 
    las 15 vacantes más viables semánticamente y evitar agotar cuotas del LLM.
    """
    if df_ofertas.empty or not texto_cv:
        return pd.DataFrame()
    
    def preprocesar(texto):
        texto = str(texto).lower()
        return re.sub(r'[^\w\s]', ' ', texto)

    cv_limpio = preprocesar(texto_cv)
    descripciones = df_ofertas['descripcion'].fillna('').apply(preprocesar).tolist()
    
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([cv_limpio] + descripciones)
    similitudes = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    
    df_analisis = df_ofertas.copy()
    df_analisis['score_screening'] = similitudes * 100
    
    # Retornamos las mejores posicionadas estadísticamente para ser evaluadas por Gemini en la UI de app.py
    return df_analisis.sort_values(by='score_screening', ascending=False).head(15)

# =====================================================================
# BLOQUE DE EJECUCIÓN (AUDITORÍA Y POBLAMIENTO)
# =====================================================================
if __name__ == "__main__":
    # Permite ejecutar este script directamente en la terminal para alimentar tu base de datos en Supabase
    cargar_vacantes_a_supabase()
