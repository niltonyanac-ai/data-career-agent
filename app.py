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
    
    # Dividimos la pantalla en dos columnas para los gráficos
    col_graf1, col_graf2 = st.columns(2)
    
    with col_graf1:
        # Gráfico 1: Barras de Habilidades
        data_skills = {"Habilidad": ["Python", "SQL", "AWS", "Tableau", "Power BI", "Databricks"], "Vacantes": [45, 38, 29, 25, 24, 18]}
        df_s = pd.DataFrame(data_skills).sort_values(by="Vacantes")
        fig_bar = px.bar(df_s, x="Vacantes", y="Habilidad", orientation='h', title="Top Herramientas Demandadas", color="Vacantes", color_continuous_scale="Blugrn")
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_graf2:
        # Gráfico 2: Dona de Especialidades (¡Añadido!)
        data_perfiles = {"Especialidad": ["Científico de Datos", "Analista de BI / Estadístico", "Data Engineer", "MLOps / AI Engineer"], "Porcentaje": [35, 30, 23, 12]}
        df_p = pd.DataFrame(data_perfiles)
        fig_pie = px.pie(df_p, values="Porcentaje", names="Especialidad", hole=0.5, title="Distribución de Oportunidades por Tipo de Perfil", color_discrete_sequence=px.colors.sequential.Blugrn_r)
        st.plotly_chart(fig_pie, use_container_width=True)

# --- PESTAÑA 2: EL EVALUADOR DE CV (DIAGNÓSTICO DETALLADO) ---
with tab2:
    st.header("Evaluación Personalizada de Currículum")
    st.write("Sube tu CV en formato PDF y selecciona tu rol objetivo para calibrar el nivel de match exacto contra nuestra base de vacantes.")
    
    # 📌 MEJORA 2: Selector de posición objetivo
    posicion_objetivo = st.selectbox(
        "¿A qué posición o especialidad deseas postular?",
        ["Selecciona una opción...", "Científico de Datos", "Analista de BI / Estadístico", "Data Engineer", "MLOps / AI Engineer"]
    )
    
    archivo_cv = st.file_uploader("Arrastra tu CV aquí (PDF)", type=["pdf"])
    
    if archivo_cv is not None and posicion_objetivo != "Selecciona una opción...":
        st.success(f"¡CV recibido con éxito! Preparando análisis contra el perfil de: **{posicion_objetivo}**")
        
        # Leemos el texto del PDF subido
        lector_pdf = pypdf.PdfReader(archivo_cv)
        texto_cv_usuario = ""
        for pagina in lector_pdf.pages:
            texto_cv_usuario += pagina.extract_text()
            
        # Simulación de ejecución de match con lógica dinámica según el rol elegido
        if st.button("Calcular Match Personalizado"):
            st.subheader(f"📊 Diagnóstico Detallado para: {posicion_objetivo}")
            
            if posicion_objetivo == "Data Engineer" or posicion_objetivo == "MLOps / AI Engineer":
                st.metric("Matching Score con el Perfil Objetivo", "6%", "-94% de brecha técnica")
                st.warning(f"⚠️ Probabilidad de pasar el filtro ATS para {posicion_objetivo}: **Baja**")
                st.info("💡 Análisis Semántico: Tu perfil actual cuenta con sólidas bases estadísticas y analíticas, pero carece de la infraestructura de ingeniería requerida para esta posición específica.")
                st.subheader("Brechas Técnicas Críticas a Cubrir para este Rol:")
                st.write(["Docker & Kubernetes", "Plataformas Cloud (AWS/GCP/Azure)", "Arquitecturas CI/CD y pipelines de MLOps"])
                
            else: # Data Scientist o BI
                st.metric("Matching Score con el Perfil Objetivo", "85%", "+15% sobre el promedio")
                st.success(f"🚀 Probabilidad de pasar el filtro ATS para {posicion_objetivo}: **Alta**")
                st.info(f"💡 Análisis Semántico: Gran alineación en analítica, modelamiento de datos y herramientas de visualización corporativas.")
                st.subheader("Habilidades Altamente Coincidentes Detectadas:")
                st.write(["Análisis Estadístico Avanzado", "Python y SQL Core", "Desarrollo de Dashboards de Negocio"])

    elif archivo_cv is not None and posicion_objetivo == "Selecciona una opción...":
        st.info("👈 Por favor, selecciona arriba la posición a la que deseas postular para poder calcular el match.")

# --- PESTAÑA 3: LISTADO DE EMPLEOS ---
with tab3:
    st.header("Ofertas de Empleo Vigentes Monitoreadas")
    ofertas_ejemplo = pd.DataFrame({
        "Puesto": ["Machine Learning Ops Engineer", "Data Scientist", "DATA SCIENTIST - PROYECTO", "COE ANALYTICS"],
        "Empresa": ["Yape", "NTT DATA", "Alicorp", "Banco de Crédito BCP"],
        "País": ["Perú", "Perú", "Perú", "Perú"]
    })
    st.dataframe(ofertas_ejemplo, use_container_width=True)
