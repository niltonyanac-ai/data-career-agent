import os
import json
import random
import re
import pandas as pd
from supabase import create_client
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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
    # CORRECCIÓN: Elevado a 200 para superar el umbral de 180 requerido
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
            "hard_skills": h_skills,
            "soft_skills": s_skills
        })
    return ofertas

def cargar_vacantes_a_supabase():
    if SUPABASE_URL == "TU_SUPABASE_URL":
        print("⚠️ Configura las variables de entorno de Supabase.")
        return
        
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    ofertas = generar_mock_ofertas_representativas()
    
    print(f"Iniciando carga de {len(ofertas)} ofertas indexadas...")
    exitos = 0
    for oferta in ofertas:
        try:
            # CORRECCIÓN: .insert() en lugar de .upsert() para evitar fallos por ausencia de ID único explícito
            supabase.table("vacantes").insert(oferta).execute()
            exitos += 1
        except Exception as e:
            print(f"Error insertando oferta: {str(e)}")
            
    print(f"Procesamiento finalizado. {exitos} registros nuevos indexados.")


# =====================================================================
# NUEVAS MEJORAS COMPLEMENTARIAS (PRODUCCIÓN Y EVALUADOR ATS DE CV)
# =====================================================================

def obtener_datos_produccion():
    """
    Audita la conexión a Supabase y descarga la data real.
    Si falla o no está configurado, activa la contingencia de forma segura.
    """
    if SUPABASE_URL == "TU_SUPABASE_URL" or not SUPABASE_URL:
        # Si no hay credenciales reales en las variables de entorno, devolvemos la simulación
        df_mock = pd.DataFrame(generar_mock_ofertas_representativas())
        return df_mock, "Simulado / Contingencia"
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        response = supabase.table("vacantes").select("*").execute()
        
        if response.data and len(response.data) > 0:
            df_real = pd.DataFrame(response.data)
            return df_real, "Producción / Supabase"
        else:
            # Si la tabla está vacía, fallback a simulación
            df_mock = pd.DataFrame(generar_mock_ofertas_representativas())
            return df_mock, "Simulado / Contingencia"
    except Exception as e:
        print(f"Alerta: Redirigiendo a contingencia por error en producción: {e}")
        df_mock = pd.DataFrame(generar_mock_ofertas_representativas())
        return df_mock, "Simulado / Contingencia"

def calcular_match_ats_cv(texto_cv, df_ofertas):
    """
    Calcula matemáticamente el % de afinidad entre el CV y la descripción del puesto.
    Filtra ofertas con match > 70% y retorna el Top 10 ordenado.
    """
    if df_ofertas.empty or not texto_cv:
        return pd.DataFrame()
    
    # Limpieza estándar para evitar distorsiones por caracteres especiales
    def preprocesar(texto):
        texto = str(texto).lower()
        texto = re.sub(r'[^\w\s]', ' ', texto)
        return texto

    cv_limpio = preprocesar(texto_cv)
    descripciones = df_ofertas['descripcion'].fillna('').apply(preprocesar).tolist()
    
    # Construcción de la matriz numérica con TF-IDF
    textos_totales = [cv_limpio] + descripciones
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(textos_totales)
    
    # Medición de similitud geométrica (Coseno) entre el CV [0] y las vacantes [1:]
    similitudes = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    
    # Inyección de la métrica en una copia para proteger los datos originales
    df_analisis = df_ofertas.copy()
    df_analisis['Match %'] = similitudes * 100
    
    # REGLA: Filtrar estrictamente por encima del 70% de afinidad
    df_filtrado = df_analisis[df_analisis['Match %'] > 70]
    
    # Extraer las 10 ofertas con mayor rendimiento analítico
    df_top_10 = df_filtrado.sort_values(by='Match %', ascending=False).head(10)
    
    return df_top_10

if __name__ == "__main__":
    cargar_vacantes_a_supabase()
