import os
import json
import random
import pandas as pd
from supabase import create_client

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
    for i in range(165):
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
            supabase.table("vacantes").upsert(oferta).execute()
            exitos += 1
        except Exception as e:
            print(f"Error insertando oferta: {str(e)}")
            
    print(f"Procesamiento finalizado. {exitos} registros actualizados.")

if __name__ == "__main__":
    cargar_vacantes_a_supabase()
