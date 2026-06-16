import os
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Error: Las variables de entorno de Supabase no están configuradas.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def ejecutar_scraper():
    print("Iniciando búsqueda real de mercado en portales abiertos...")
    nuevas_vacantes = []
    
    # Lista de palabras clave estratégicas para tu sector
    palabras_clave = ["data scientist", "analista bi", "inteligencia comercial", "data analyst"]
    
    # Buscador agnóstico usando RSS feeds abiertos de empleo (evita bloqueos de login)
    for q in palabras_clave:
        try:
            url_feed = f"https://www.linkedin.com/jobs/api/seeMoreJobPostings/search?keywords={q}&location=Peru&f_TPR=r604800"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            raw_html = requests.get(url_feed, headers=headers, timeout=15).text
            soup = BeautifulSoup(raw_html, 'html.parser')
            
            tarjetas = soup.find_all('li')
            for tarjeta in tarjetas:
                try:
                    titulo_elem = tarjeta.find('h3', class_='base-search-card__title')
                    empresa_elem = tarjeta.find('h4', class_='base-search-card__subtitle')
                    link_elem = tarjeta.find('a', class_='base-card__full-link')
                    
                    if titulo_elem and empresa_elem and link_elem:
                        puesto = titulo_elem.text.strip()
                        empresa = empresa_elem.text.strip()
                        link = link_elem['href'].split('?')[0] # Limpia parámetros de tracking
                        
                        # Clasificación inteligente basada en mapeo de texto básico
                        puesto_lower = puesto.lower()
                        especialidad = "Data Science"
                        if "bi" in puesto_lower or "business intelligence" in puesto_lower:
                            especialidad = "Business Intelligence"
                        elif "comercial" in puesto_lower:
                            especialidad = "Inteligencia Comercial"
                        elif "analyst" in puesto_lower or "analista" in puesto_lower:
                            especialidad = "Data Analytics"
                            
                        # Jerarquía automática
                        jerarquia = "Analista"
                        if "senior" in puesto_lower or "sr" in puesto_lower or "lead" in puesto_lower:
                            jerarquia = "Senior"
                        elif "junior" in puesto_lower or "jr" in puesto_lower:
                            jerarquia = "Junior"
                        elif "jefe" in puesto_lower or "manager" in puesto_lower or "gerente" in puesto_lower:
                            jerarquia = "Líder / Jefatura"

                        # Asignación de competencias base recomendadas para auditoría por IA
                        h_skills = ["SQL", "Python"]
                        if "bi" in puesto_lower or "tableau" in puesto_lower or "power" in puesto_lower:
                            h_skills.extend(["Power BI", "Dashboards"])
                        
                        oferta = {
                            "puesto": puesto,
                            "empresa": empresa,
                            "especialidad": especialidad,
                            "jerarquia": jerarquia,
                            "hard_skills": h_skills,
                            "soft_skills": ["Análisis", "Comunicación"],
                            "link": link
                        }
                        
                        # Evita duplicados en la lista local antes de subir
                        if not any(v['link'] == link for v in nuevas_vacantes):
                            nuevas_vacantes.append(oferta)
                            
                except Exception as e_tarjeta:
                    continue
        except Exception as e_feed:
            print(f"Error procesando búsqueda para {q}: {e_feed}")

    # =========================================================================
    # CONTROL DE PERSISTENCIA Y INYECCIÓN
    # =========================================================================
    if len(nuevas_vacantes) == 0:
        print("La búsqueda arrojó 0 resultados reales en esta pasada. Abortando purga.")
        return

    try:
        print(f"Éxito. Se encontraron {len(nuevas_vacantes)} ofertas reales.")
        print("Vaciando inventario antiguo de manera segura...")
        supabase.table("vacantes").delete().neq("id", 0).execute()
        
        print("Inyectando registros reales indexados...")
        # Subimos en lotes pequeños para evitar sobrecargas de red
        for i in range(0, len(nuevas_vacantes), 10):
            lote = nuevas_vacantes[i:i+10]
            supabase.table("vacantes").insert(lote).execute()
            
        print("Sincronización masiva con el mercado real completada con éxito.")
    except Exception as e:
        print(f"Error de escritura en Supabase: {e}")

if __name__ == "__main__":
    ejecutar_scraper()
