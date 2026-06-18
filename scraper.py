import os
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

# ==============================================================================
# 1. CONEXIÓN DE INFRAESTRUCTURA SEGURA
# ==============================================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")  # Inyecta tu clave secreta de forma segura

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Variables de entorno SUPABASE_URL o SUPABASE_KEY ausentes.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def ejecutar_pipeline_global():
    print("🚀 Iniciando Pipeline Regional Avanzado Antiban...")
    nuevas_vacantes = []
    
    # --- MATRIZ DE EXPANSIÓN LATAM (Requerimiento de Cobertura) ---
    PAISES_LATAM = {
        "Perú": "102890719",
        "Colombia": "103977389",
        "México": "103323778",
        "Chile": "104621116",
        "Argentina": "100446939"
    }
    
    roles = [
        "data scientist", "analista de datos", "business intelligence", 
        "inteligencia comercial", "data analyst", "analytics", 
        "ingeniero de datos", "data engineer", "cientifico de datos",
        "analytics manager", "data leader"
    ]
    
    LISTA_NEGRA = [
        "quimico", "química", "laboratorio", "clinico", "clínico", "creditos", 
        "créditos", "contable", "contabilidad", "legal", "procesos", "calidad",
        "rrhh", "recursos humanos", "compras", "inventarios", "microbiologia",
        "farmaceutico", "biologo", "mantenimiento", "soporte tecnico"
    ]

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
    ]

    # --- EXTRACCIÓN MATRICIAL CRUZADA ---
    for pais, geo_id in PAISES_LATAM.items():
        print(f"\n🌍 Escaneando Mercado Regional: {pais}...")
        
        for r in roles:
            # Paginación profunda (0, 25, 50, 75) para barrer todas las empresas actuales
            for start in [0, 25, 50, 75]: 
                try:
                    headers = {
                        "User-Agent": random.choice(USER_AGENTS),
                        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
                    }
                    
                    # f_TPR=r2592000 asegura indexar solo lo publicado en los últimos 30 días
                    url = f"https://www.linkedin.com/jobs/api/seeMoreJobPostings/search?keywords={r}&geoId={geo_id}&f_TPR=r2592000&start={start}"
                    
                    respuesta = requests.get(url, headers=headers, timeout=15)
                    
                    # Pausa técnica antiban aleatoria estricta
                    time.sleep(random.uniform(2.5, 4.5))
                    
                    if respuesta.status_code != 200:
                        print(f"  ⚠️ Alerta: Fin de respuestas o rate limit para {r} en {pais} (Status: {respuesta.status_code})")
                        break # Salta al siguiente rol si esta página ya no responde
                        
                    soup = BeautifulSoup(respuesta.text, 'html.parser')
                    tarjetas = soup.find_all('li')
                    
                    if not tarjetas:
                        break
                        
                    for tarjeta in tarjetas:
                        titulo_elem = tarjeta.find('h3', class_='base-search-card__title')
                        empresa_elem = tarjeta.find('h4', class_='base-search-card__subtitle')
                        link_elem = tarjeta.find('a', class_='base-card__full-link')
                        
                        if titulo_elem and empresa_elem and link_elem:
                            puesto = titulo_elem.text.strip()
                            empresa = empresa_elem.text.strip()
                            link = link_elem['href'].split('?')[0]
                            puesto_lower = puesto.lower()
                            
                            # Filtro 1: Lista Negra
                            if any(negra in puesto_lower for negra in LISTA_NEGRA):
                                continue
                                
                            # Filtro 2: Términos Válidos
                            TERMINOS_VALIDOS = ["data", "analyst", "analista", "bi", "intelligence", "inteligencia", "scientist", "cientifico", "analytics", "engineer", "ingeniero", "ai", "artificial", "leader", "lider", "manager"]
                            if not any(valido in puesto_lower for valido in TERMINOS_VALIDOS):
                                continue

                            # Taxonomía analítica precisa
                            especialidad = None
                            if "bi" in puesto_lower or "intelligence" in puesto_lower or "inteligencia" in puesto_lower:
                                especialidad = "Inteligencia Comercial" if "comercial" in puesto_lower else "Business Intelligence"
                            elif any(x in puesto_lower for x in ["scientist", "científico", "ciencia", "learning", "ai", "artificial"]):
                                    especialidad = "Data Science"
                            elif "engineer" in puesto_lower or "ingeniero de datos" in puesto_lower:
                                    especialidad = "Data Engineering"
                            elif any(x in puesto_lower for x in ["analista de datos", "data analyst", "analytics"]):
                                    especialidad = "Data Analytics"
                                    
                            if not especialidad:
                                continue
                                
                            # Clasificación de jerarquía base para el payload
                            jerarquia = "Analista"
                            if any(x in puesto_lower for x in ["senior", "sr", "lead", "principal", "advanced", "especialista"]):
                                jerarquia = "Senior"
                            elif any(x in puesto_lower for x in ["junior", "jr", "practicante", "trainee", "asistente"]):
                                jerarquia = "Junior"
                            elif any(x in puesto_lower for x in ["jefe", "jefatura", "manager", "gerente", "coordinador", "director", "head"]):
                                jerarquia = "Líder / Jefatura"

                            # Extracción Sintáctica de Hard Skills
                            hard_skills = []
                            if "excel" in puesto_lower or "analista" in puesto_lower: hard_skills.append("Excel")
                            if any(x in puesto_lower for x in ["sql", "data"]): hard_skills.append("SQL")
                            if "python" in puesto_lower or "scientist" in puesto_lower: hard_skills.append("Python")
                            if "power bi" in puesto_lower or "bi" in puesto_lower: hard_skills.append("Power BI")
                            if "tableau" in puesto_lower: hard_skills.append("Tableau")
                            if "aws" in puesto_lower or "cloud" in puesto_lower: hard_skills.append("Cloud Computing")
                            if not hard_skills: hard_skills = ["SQL", "Excel"]
                            
                            # Extracción Sintáctica de Soft Skills
                            soft_skills = ["Análisis de Datos", "Pensamiento Crítico"]
                            if jerarquia in ["Senior", "Líder / Jefatura"]:
                                soft_skills = ["Liderazgo", "Gestión de Stakeholders"]
                            elif especialidad == "Data Science":
                                soft_skills = ["Resolución de Problemas Complejos", "Curiosidad Científica"]

                            oferta = {
                                "puesto": puesto,
                                "empresa": empresa,
                                "especialidad": especialidad,
                                "jerarquia": puesto,  # Enviamos el puesto completo para que la normalización de 6 niveles en app.py haga el mapeo semántico experto
                                "pais": pais,         # Telemetría de origen geográfica real
                                "hard_skills": hard_skills,
                                "soft_skills": soft_skills,
                                "link": link
                            }
                            
                            # Evitar duplicados duplicados dentro del mismo ciclo en memoria
                            if not any(v['link'] == link for v in nuevas_vacantes):
                                nuevas_vacantes.append(oferta)
                                
                except Exception as e:
                    print(f"  ❌ Error procesando iteración start={start}: {e}")
                    continue

    # ==============================================================================
    # 5. PERSISTENCIA SEGURA E INCREMENTAL (UPSERT)
    # ==============================================================================
    if not nuevas_vacantes:
        print("\n⚠️ Cero registros nuevos extraídos en este ciclo regional. Abortando persistencia para proteger el histórico.")
        return

    try:
        print(f"\n📦 Procesadas con éxito {len(nuevas_vacantes)} ofertas puras en LATAM.")
        print("Sincronizando mediante Upsert incremental en Supabase...")
        
        # Inserción segura registro por registro evaluando conflicto en la URL única de la oferta
        for o in nuevas_vacantes:
            supabase.table("vacantes").upsert(o, on_conflict="link").execute()
            
        # Mantenimiento estricto de la ventana histórica de 30 días requerida por tu negocio
        fecha_limite = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        print(f"🧹 Purgando registros obsoletos anteriores a la ventana del mercado: {fecha_limite}")
        supabase.table("vacantes").delete().lt("fecha_creacion", fecha_limite).execute()
        
        print("✅ Pipeline Global ejecutado de forma impecable y sin riesgos.")
    except Exception as e:
        print(f"❌ Error de persistencia en Supabase Engine: {e}")

if __name__ == "__main__":
    ejecutar_pipeline_global()
