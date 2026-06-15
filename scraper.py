import os
import datetime
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def limpiar_datos_antiguos():
    """Borra ofertas con más de 60 días para proteger el almacenamiento gratuito"""
    hace_60_dias = (datetime.datetime.now() - datetime.timedelta(days=60)).isoformat()
    try:
        # Elimina registros donde fecha_creacion sea menor a hace 60 días
        supabase.table("vacantes").delete().lt("fecha_creacion", hace_60_dias).execute()
        print("🧹 Limpieza completada: Se eliminaron las vacantes con más de 60 días.")
    except Exception as e:
        print(f"Error al limpiar historial: {e}")

def clasificar_jerarquia(titulo):
    t = titulo.lower()
    if any(x in t for x in ["practicante", "asistente", "junior", "jr"]):
        return "Practicante/asistente/analista Jr."
    if any(x in t for x in ["jefe", "leader", "líder", "product owner", "po"]):
        return "Líder/Jefe/PO"
    if "subgerente" in t or "sub gerente" in t:
        return "Sub Gerente"
    if any(x in t for x in ["gerente", "head", "director", "manager"]):
        return "Gerente/Head/Director"
    if any(x in t for x in ["especialista", "coordinador", "supervisor"]):
        return "Especialista/Coordinador/Supervisor"
    return "Analista/Analista Sr"

def ejecutar_scraping():
    # 1. Purgar memoria antes de meter nuevos datos
    limpiar_datos_antiguos()
    
    print("Iniciando barrido de mercado en LinkedIn Perú...")
    url_linkedin = "https://www.linkedin.com/jobs/search/?keywords=Data&location=Peru"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url_linkedin, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all('div', class_='base-search-card')
        
        for card in cards:
            try:
                titulo = card.find('h3', class_='base-search-card__title').text.strip()
                empresa = card.find('h4', class_='base-search-card__subtitle').text.strip()
                link = card.find('a', class_='base-card__full-link')['href'].split('?')[0]
                
                jerarquia = clasificar_jerarquia(titulo)
                
                especialidad = "Analista de BI / Estadístico"
                if "scientist" in titulo.lower() or "ciencia de datos" in titulo.lower():
                    especialidad = "Científico de Datos"
                elif "engineer" in titulo.lower() or "ingeniero de datos" in titulo.lower():
                    especialidad = "Data Engineer"
                elif "ops" in titulo.lower() or "ai" in titulo.lower():
                    especialidad = "MLOps / AI Engineer"
                
                hard_skills = ["Python", "SQL"] if "Científico" in especialidad else ["SQL", "Power BI"]
                soft_skills = ["Gestión", "Data Storytelling"] if "Jefe" in jerarquia else ["Autonomía", "Problemas"]
                
                payload = {
                    "puesto": titulo,
                    "empresa": empresa,
                    "especialidad": especialidad,
                    "jerarquia": jerarquia,
                    "hard_skills": hard_skills,
                    "soft_skills": soft_skills,
                    "link": link
                }
                
                supabase.table("vacantes").upsert(payload, on_conflict="link").execute()
            except Exception:
                continue
        print("¡Sincronización completada!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    ejecutar_scraping()
