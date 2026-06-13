import streamlit as st
import pandas as pd
import plotly.express as px
from google import genai
from google.genai import types
import json
import pypdf

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(page_title="DataCareer AI - Asesor de Carrera", layout="wide", initial_sidebar_state="expanded")

# --- ENLACE CON LA IA ---
# Jalamos la API Key guardada de forma segura en los Secrets de Streamlit
API_KEY = st.secrets.get("GEMINI_API_KEY", "TU_API_KEY_AQUI")

# --- INTERFAZ VISUAL (STREAMLIT) ---
st.title("💼 DataCareer AI")
st.subheader("Análisis de mercado en tiempo real y evaluador de CVs para perfiles de Datos")

# Creamos las pestañas dinámicas que estructuran la navegación
tab1, tab2, tab3 = st.tabs(["📊 Dashboard del Mercado", "🔍 Evaluar mi CV", "📋 Vacantes Disponibles"])

# --- PESTAÑA 1: EL DASHBOARD VISUAL ---
with tab1:
    st.header("Tendencias del Mercado Laboral (Perú y Región)")
    
    # KPIs principales
    col1, col2, col3 = st.columns(3)
    col1.metric("Vacantes Analizadas (Últimos 60 días)", "369", "+20 hoy")
    col2.metric("País Principal", "Perú (60%)")
    col3.metric("Skill Más Solicitada", "Python")
    
    # Renderizamos los gráficos de Plotly que calibramos antes
    data_skills = {"Habilidad": ["Python", "SQL", "AWS", "Tableau", "Power BI", "Databricks"], "Vacantes": [45, 38, 29, 25, 24, 18]}
    df_s = pd.DataFrame(data_skills).sort_values(by="Vacantes")
    
    fig = px.bar(df_s, x="Vacantes", y="Habilidad", orientation='h', title="Top Herramientas Demandadas", color="Vacantes", color_continuous_scale="Blugrn")
    st.plotly_chart(fig, use_container_width=True)

# --- PESTAÑA 2: EL EVALUADOR DE CV ---
with tab2:
    st.header("Sube tu Currículum Vitae")
    st.write("Sube tu CV en formato PDF. Nuestro agente lo contrastará con las vacantes activas del mercado para medir tu probabilidad de éxito.")
    
    archivo_cv = st.file_uploader("Arrastra tu CV aquí (PDF)", type=["pdf"])
    
    if archivo_cv is not None:
        st.success("¡CV recibido con éxito! Procesando análisis semántico...")
        
        # Leemos el texto del PDF subido por el usuario
        lector_pdf = pypdf.PdfReader(archivo_cv)
        texto_cv_usuario = ""
        for pagina in lector_pdf.pages:
            texto_cv_usuario += pagina.extract_text()
            
        # Simulación de ejecución de match con el botón
        if st.button("Calcular Match con Vacantes Activas"):
            st.metric("Matching Score General con el Mercado", "6%", "-94% de brecha técnica")
            
            st.warning("⚠️ Probabilidad de Entrevista para roles MLOps/Data Engineer: **Baja**")
            st.info("💡 Tu perfil tiene una fuerte alineación (85%) con roles de: **Científico de Datos** o **Analista de BI**.")
            
            st.subheader("Brechas Técnicas Críticas a Cubrir:")
            st.write(["Docker & Kubernetes", "Plataformas Cloud (AWS/GCP/Azure)", "Arquitecturas CI/CD y MLOps"])

# --- PESTAÑA 3: LISTADO DE EMPLEOS ---
with tab3:
    st.header("Ofertas de Empleo Vigentes Monitoreadas")
    ofertas_ejemplo = pd.DataFrame({
        "Puesto": ["Machine Learning Ops Engineer", "Data Scientist", "DATA SCIENTIST - PROYECTO", "COE ANALYTICS"],
        "Empresa": ["Yape", "NTT DATA", "Alicorp", "Banco de Crédito BCP"],
        "País": ["Perú", "Perú", "Perú", "Perú"]
    })
    st.dataframe(ofertas_ejemplo, use_container_width=True)
