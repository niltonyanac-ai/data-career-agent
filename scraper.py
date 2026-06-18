import os
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Configuración de entorno seguro
SUPABASE_URL = "https://ktevmevkvrxbeaamdnvy.supabase.co"
SUPABASE_KEY = "sb_secret_BxCedbLKl1J_7ePbamZnzg_kZvNhfdA"

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Error crítico: Credenciales de acceso a Supabase ausentes.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def ejecutar_scraper():
    print("Iniciando pipeline de extracción automatizada con filtros de pureza...")
    nuevas_vacantes = []
    
    roles = [
        "data scientist", "analista de datos", "business intelligence", 
        "inteligencia comercial", "data analyst", "analytics", 
        "ingeniero de datos", "data engineer", "cientifico de datos"
    ]
    
    # Lista negra estricta de exclusión sectorial
    LISTA_NEGRA = [
        "quimico", "química", "laboratorio", "clinico", "clínico", "creditos", 
        "créditos", "contable", "contabilidad", "legal", "procesos", "calidad",
        "rrhh", "recursos humanos", "compras", "inventarios", "microbiologia",
        "farmaceutico", "biologo", "mantenimiento", "soporte tecnico", "abogado",
        "medico", "médico", "enfermero", "psicologo"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }

    for r in roles:
        for start in [0, 25, 50, 75]:
            try:
                url = f"https://www.linkedin.com/jobs/api/seeMoreJobPostings/search?keywords={r}&location=Peru&f_TPR=r7776000&start={start}"
                respuesta = requests.get(url, headers=headers, timeout=15)
                
                if respuesta.status_code != 200:
                    continue
                    
                soup = BeautifulSoup(respuesta.text, 'html.parser')
                tarjetas = soup.find_all('li')
                
                for tarjeta in tarjetas:
                    titulo_elem = tarjeta.find('h3', class_='base-search-card__title')
                    empresa_elem = tarjeta.find('h4', class_='base-search-card__subtitle')
                    link_elem = tarjeta.find('a', class_='base-card__full-link')
                    
                    if titulo_elem and empresa_elem and link_elem:
                        puesto = titulo_elem.text.strip()
                        empresa = empresa_elem.text.strip()
                        link = link_elem['href'].split('?')[0]
                        
                        puesto_lower = puesto.lower()
                        
                        # Filtro 1: Lista negra sectorial
                        if any(negra in puesto_lower for negra in LISTA_NEGRA):
                            continue
                            
                        # Filtro 2: Validación de términos core de tecnología y datos
                        TERMINOS_VALIDOS = ["data", "analyst", "analista", "bi", "intelligence", "inteligencia", "scientist", "cientifico", "analytics", "engineer", "ingeniero", "modelamiento", "machine", "ai", "artificial"]
                        if not any(valido in puesto_lower for valido in TERMINOS_VALIDOS):
                            continue

                        # Clasificación y asignación precisa de especialidad
                        especialidad = None
                        if "bi" in puesto_lower or "intelligence" in puesto_lower or "inteligencia" in puesto_lower:
                            if "comercial" in puesto_lower:
                                especialidad = "Inteligencia Comercial"
                            else:
                                especialidad = "Business Intelligence"
                        elif "scientist" in puesto_lower or "científico" in puesto_lower or "ciencia" in puesto_lower or "learning" in puesto_lower or "ai" in puesto_lower:
                            especialidad = "Data Science"
                        elif "engineer" in puesto_lower or "ingeniero de datos" in puesto_lower:
                            especialidad = "Data Engineering"
                        elif "analista de datos" in puesto_lower or "data analyst" in puesto_lower or "analytics" in puesto_lower:
                            especialidad = "Data Analytics"
                        elif "comercial" in puesto_lower:
                            especialidad = "Inteligencia Comercial"
                        
                        # Purgar si no encaja en las taxonomías analíticas deseadas
                        if not especialidad:
                            continue
                            
                        # Clasificación de Jerarquía / Seniority
                        jerarquia = "Analista"
                        if any(x in puesto_lower for x in ["senior", "sr", "lead", "principal", "advanced"]):
                            jerarquia = "Senior"
                        elif any(x in puesto_lower for x in ["junior", "jr", "practicante", "trainee", "asistente"]):
                            jerarquia = "Junior"
                        elif any(x in puesto_lower for x in ["jefe", "jefatura", "manager", "gerente", "coordinador"]):
                            jerarquia = "Líder / Jefatura"

                        # Extracción Contextual de Hard Skills
                        hard_skills = []
                        if "excel" in puesto_lower or "analista" in puesto_lower: hard_skills.append("Excel")
                        if any(x in puesto_lower for x in ["sql", "data", "engineer", "scientist"]): hard_skills.append("SQL")
                        if "python" in puesto_lower or "scientist" in puesto_lower or "learning" in puesto_lower: hard_skills.append("Python")
                        if "r" in puesto_lower and "engineer" not in puesto_lower: hard_skills.append("R")
                        if "power bi" in puesto_lower or "bi" in puesto_lower: hard_skills.append("Power BI")
                        if "tableau" in puesto_lower: hard_skills.append("Tableau")
                        if "spark" in puesto_lower or "databricks" in puesto_lower: hard_skills.append("Spark")
                        if any(x in puesto_lower for x in ["aws", "azure", "gcp", "cloud"]): hard_skills.append("Cloud Computing")
                        
                        if not hard_skills: hard_skills = ["SQL", "Excel"]
                        
                        # MEJORA UX: Mapeo dinámico y diverso de Soft Skills según el perfil
                        soft_skills = ["Análisis de Datos", "Pensamiento Crítico"]
                        if jerarquia in ["Senior", "Líder / Jefatura"]:
                            soft_skills = ["Liderazgo", "Gestión de Stakeholders", "Visión de Negocio"]
                        elif especialidad == "Inteligencia Comercial":
                            soft_skills = ["Comunicación Asertiva", "Orientación a Resultados", "Storytelling"]
                        elif especialidad == "Data Science":
                            soft_skills = ["Resolución de Problemas Complejos", "Curiosidad Científica"]
                        
                        oferta = {
                            "puesto": puesto,
                            "empresa": empresa,
                            "especialidad": especialidad,
                            "jerarquia": jerarquia,
                            "hard_skills": hard_skills,
                            "soft_skills": soft_skills,
                            "link": link
                        }
                        
                        if not any(v['link'] == link for v in nuevas_vacantes):
                            nuevas_vacantes.append(oferta)
                            
            except Exception:
                continue

    if len(nuevas_vacantes) == 0:
        print("La extracción finalizó con 0 registros válidos. Operación abortada para proteger la persistencia.")
        return

    try:
        print(f"Limpieza exitosa. Procesadas {len(nuevas_vacantes)} ofertas puras de Data/IA.")
        print("Efectuando truncamiento limpio de la tabla...")
        supabase.table("vacantes").delete().neq("id", 0).execute()
        
        print("Ejecutando inserción por lotes optimizados...")
        for i in range(0, len(nuevas_vacantes), 20):
            lote = nuevas_vacantes[i:i+20]
            supabase.table("vacantes").insert(lote).execute()
            
        print("Sincronización con repositorio central completada con éxito.")
    except Exception as e:
        print(f"Error de persistencia en Supabase: {e}")

if __name__ == "__main__":
    ejecutar_scraper()
