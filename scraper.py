import os
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Error: Las variables de entorno de Supabase no están configuradas.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def ejecutar_scraper():
    print("Iniciando búsqueda agnóstica de mercado...")
    nuevas_vacantes = []
    
    # --- PROCESAMIENTO DE EJEMPLO DE EXTRACCIÓN ---
    # Formato de guardado exacto e idóneo para inyectar a tu tabla pública
    # 'hard_skills' y 'soft_skills' se envían como listas nativas de Python [] para mapear con text[]
    ejemplo_oferta = {
        "puesto": "Analista de Inteligencia Comercial", # Especialidad purificada, el puesto puede mantener el descriptor formal
        "empresa": "Corporación Ripley Perú",
        "especialidad": "Inteligencia Comercial",
        "jerarquia": "Mid",
        "hard_skills": ["Excel", "SQL", "Tableau"], 
        "soft_skills": ["Negocio", "Comunicación"],
        "link": "https://www.linkedin.com/jobs/view/123456789"
    }
    nuevas_vacantes.append(ejemplo_oferta)
    
    # =========================================================================
    # CONTROL DE PERSISTENCIA
    # =========================================================================
    if len(nuevas_vacantes) == 0:
        print("La búsqueda arrojó 0 resultados. Abortando purga para resguardar datos históricos.")
        return

    try:
        print("Éxito. Actualizando repositorio central en Supabase...")
        # El .neq("id", 0) asegura vaciar todo el inventario de manera segura
        supabase.table("vacantes").delete().neq("id", 0).execute()
        
        # Inserción masiva limpia
        supabase.table("vacantes").insert(nuevas_vacantes).execute()
        print("Sincronización masiva completada.")
    except Exception as e:
        print(f"Error de escritura en Supabase: {e}")

if __name__ == "__main__":
    ejecutar_scraper()
