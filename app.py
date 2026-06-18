import subprocess
import sys
import time

# Lista de librerías esenciales para la IA, Base de Datos y PDFs
LIBRERIAS_CORE = ["google-genai", "supabase", "pypdf"]

for libreria in LIBRERIAS_CORE:
    nombre_modulo = libreria.replace("-", "_")
    try:
        __import__(nombre_modulo)
    except ImportError:
        # Forzar la instalación síncrona en el contenedor de Streamlit
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", libreria])
        time.sleep(2)  # Pausa técnica de seguridad para que el sistema asiente el módulo

# --- AHORA SÍ, UNA VEZ ASEGURADOS LOS MÓDULOS, CONTINÚAN LOS IMPORTS NORMALES ---
import streamlit as st
import pandas as pd
import json
import altair as alt
from datetime import datetime, timedelta
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List
from supabase import create_client, Client

# Configuración del ecosistema visual de la aplicación
st.set_page_config(page_title="DataCareer AI - Plataforma de Empleabilidad", layout="wide", page_icon="💼")

# --- Modelado de Datos Estrictos para la IA ---
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# --- Capa de Datos con Caché Resiliente ---
@st.cache_data(ttl=15, show_spinner="Sincronizando el ecosistema analítico...")
def obtener_data_real():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(url, key)
        
        respuesta = supabase.table("vacantes").select("*").execute()
        df = pd.DataFrame(respuesta.data)
        if not df.empty and 'fecha_creacion' in df.columns:
            df['fecha_creacion'] = pd.to_datetime(df['fecha_creacion'])
        return df
    except Exception as e:
        st.error(f"Error de conexión con el backend de datos: {e}")
        return pd.DataFrame()

df_vacantes = obtener_data_real()

# --- Interfaz de Usuario y Cuadro de Mando ---
st.title("💼 DataCareer AI")
st.markdown("### Sistema Inteligente de Monitoreo de Mercado y Empleabilidad")

if df_vacantes.empty:
    st.info("Sincronizando el flujo de datos inicial... Ejecuta el Scraper en GitHub Actions para poblar el ecosistema.")
else:
    # KPIs en la Portada
    total_ofertas = len(df_vacantes)
    ultima_act = df_vacantes['fecha_creacion'].max().strftime('%d/%m/%Y %H:%M')
    
    col_kpi1, col_kpi2 = st.columns(2)
    with col_kpi1:
        st.metric("Ofertas Vigentes Monitoreadas", total_ofertas)
    with col_kpi2:
        st.metric("Última Actualización del Pipeline", ultima_act)
        
    # Filtros Avanzados en Barra Lateral
    st.sidebar.header("Filtros Analíticos")
    especialidades = df_vacantes['especialidad'].unique().tolist()
    esp_sel = st.sidebar.selectbox("Especialidad Objetivo", ["Todas"] + especialidades)
    
    jerarquias = df_vacantes['jerarquia'].unique().tolist()
    jer_sel = st.sidebar.multiselect("Nivel de Jerarquía", jerarquias, default=jerarquias)
    
    # Filtrado Dinámico
    df_filtrado = df_vacantes[df_vacantes['jerarquia'].isin(jer_sel)]
    if esp_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado['especialidad'] == esp_sel]
        
    # Pestañas de Trabajo
    tab_mercado, tab_evaluador = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])
    
    with tab_mercado:
        st.subheader("Análisis de Demanda Real")
        if not df_filtrado.empty:
            # Gráfico de Jerarquías
            chart_jer = alt.Chart(df_filtrado).mark_bar().encode(
                x=alt.X('count():Q', title='Cantidad de Vacantes'),
                y=alt.Y('jerarquia:N', sort='-x', title='Jerarquía'),
                color=alt.value('#0068c9')
            ).properties(height=200)
            st.altair_chart(chart_jer, use_container_width=True)
            
            # Tabla de ofertas
            st.write("### Ofertas Detectadas", df_filtrado[['fecha_creacion', 'puesto', 'empresa', 'especialidad', 'jerarquia']])
        else:
            st.warning("No hay registros para los filtros seleccionados.")
            
    with tab_evaluador:
        st.subheader("Evaluador Inteligente de Perfiles (Gemini 2.5)")
        archivo_cv = st.file_uploader("Carga tu Currículum Vitae (Formato PDF)", type=["pdf"])
        
        if archivo_cv and not df_filtrado.empty:
            if st.button("Iniciar Evaluación de Compatibilidad"):
                with st.spinner("Analizando semántica del CV frente a las vacantes de Supabase..."):
                    try:
                        # Leer PDF
                        lector = PdfReader(archivo_cv)
                        texto_cv = ""
                        for pagina in lector.pages:
                            texto_cv += pagina.extract_text()
                            
                        # Preparar cliente Gemini
                        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                        
                        # Construcción del Prompt Estricto Determinista
                        contexto_vacantes = []
                        for _, row in df_filtrado.iterrows():
                            contexto_vacantes.append({
                                "id": row['id'],
                                "puesto": row['puesto'],
                                "empresa": row['empresa'],
                                "hard_skills": row['hard_skills'],
                                "soft_skills": row['soft_skills']
                            })
                            
                        prompt = f"""
                        Actúa como un validador de ATS corporativo estricto y determinista de alta precisión.
                        Analiza el siguiente Currículum Vitae frente a la lista de vacantes reales provistas.
                        
                        REGLAS CRÍTICAS:
                        1. Calcula el 'match_score' de 0 a 100 basándote estrictamente en las Hard Skills y Soft Skills explícitamente presentes tanto en el CV como en la vacante.
                        2. Si el perfil no se alinea en absoluto (por ejemplo, áreas de negocio incompatibles o falta total de tecnologías core), el score DEBE ser 0. NO inventes emparejamientos artificiales.
                        3. La respuesta debe estructurarse estrictamente bajo el esquema JSON solicitado, sin textos introductorios ni marcas markdown de bloque ```json.
                        
                        CV del Candidato:
                        {texto_cv}
                        
                        Lista de Vacantes Disponibles:
                        {json.dumps(contexto_vacantes)}
                        """
                        
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=RespuestaMatchIA,
                                temperature=0.0  # Máximo determinismo
                            ),
                        )
                        
                        # Parsear e integrar resultados
                        resultados = json.loads(response.text)
                        df_evaluaciones = pd.DataFrame(resultados["evaluaciones"])
                        
                        if not df_evaluaciones.empty:
                            df_final = df_filtrado.merge(df_evaluaciones, left_on='id', right_on='id_interno')
                            df_final = df_final.sort_values(by='match_score', ascending=False)
                            
                            st.success("¡Análisis completado con éxito!")
                            for _, rank in df_final.iterrows():
                                color_score = "🟢" if rank['match_score'] >= 70 else "🟡" if rank['match_score'] >= 40 else "🔴"
                                with st.expander(f"{color_score} {rank['match_score']}% Match - {rank['puesto']} en {rank['empresa']}"):
                                    st.write(f"**Especialidad:** {rank['especialidad']} | **Jerarquía:** {rank['jerarquia']}")
                                    st.write(f"**Coincidencias Clave Detectadas:** {rank['coincidencias']}")
                        else:
                            st.warning("El modelo ATS determinista no encontró coincidencias estructurales mínimas con las vacantes activas.")
                    except Exception as ex:
                        st.error(f"Error durante el proceso de evaluación por Inteligencia Artificial: {ex}")
