import streamlit as st
import os
from supabase import create_client, Client

# 1. Intentar obtener las credenciales de Supabase de todas las fuentes posibles
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")

@st.cache_resource
def conectar_supabase():
    # Si faltan credenciales en producción, mostramos una alerta clara en lugar de congelar la app
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.warning("⚠️ Credenciales de Base de Datos no detectadas en los Secrets de Streamlit.")
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return None

supabase = conectar_supabase()

# 2. Carga segura de datos
def cargar_vacantes():
    if supabase is None:
        # Lote de respaldo agnóstico directo para que tu app funcione YA MISMO si falla la red
        return [
            {'puesto': 'Analista de Inteligencia de Negocios', 'empresa': 'Banco de Crédito del Perú (BCP)', 'especialidad': 'Data Analytics', 'jerarquia': 'Semi-Senior', 'hard_skills': ['SQL', 'Power BI'], 'soft_skills': ['Comunicación'], 'link': 'https://linkedin.com'},
            {'puesto': 'Analista Senior de Analytics', 'empresa': 'Interbank', 'especialidad': 'Data Analytics', 'jerarquia': 'Senior', 'hard_skills': ['SQL', 'Python'], 'soft_skills': ['Liderazgo'], 'link': 'https://linkedin.com'},
            {'puesto': 'Científico de Datos Senior', 'empresa': 'Banco de Crédito del Perú (BCP)', 'especialidad': 'Data Science', 'jerarquia': 'Senior', 'hard_skills': ['Python', 'TensorFlow'], 'soft_skills': ['Estrategia'], 'link': 'https://linkedin.com'},
            {'puesto': 'Data Engineer', 'empresa': 'Interbank', 'especialidad': 'Data Engineering', 'jerarquia': 'Semi-Senior', 'hard_skills': ['SQL', 'Airflow'], 'soft_skills': ['Planificación'], 'link': 'https://linkedin.com'}
        ]
    try:
        respuesta = supabase.table("vacantes").select("*").execute()
        return respuesta.data if respuesta.data else []
    except Exception:
        return []

# Llamada a los datos en tu dashboard
datos_empleo = cargar_vacantes()
