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

st.set_page_config(page_title="DataCareer AI", layout="wide", page_icon="💼")

# --- Esquemas Pydantic para Gemini ---
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# --- Conexión Nativa a Supabase con Caché en Tiempo Real ---
@st.cache_data(ttl=5, show_spinner="Cargando ofertas del mercado real...")
def obtener_data_real():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(url, key)
        
        respuesta = supabase.table("vacantes").select("*").execute()
        df = pd.DataFrame(respuesta.data)
        
        if df.empty:
            return pd.DataFrame(columns=['id', 'puesto', 'empresa', 'especialidad', 'jerarquia', 'hard_skills', 'soft_skills', 'link', 'fecha_creacion'])
        
        df['fecha_creacion'] = pd.to_datetime(df['fecha_creacion'])
        return df
    except Exception as e:
        st.error(f"Error de conexión con la base de datos: {e}")
        return pd.DataFrame()

df_raw = obtener_data_real()

# --- Interfaz Gráfica ---
st.title("💼 DataCareer AI")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])

if df_raw.empty:
    st.warning("⚠️ No hay ofertas disponibles en el repositorio central en este momento.")
else:
    with tab1:
        st.sidebar.header("⚙️ Filtros")
        filtro_esp = st.sidebar.selectbox("Especialidad", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
        dias = st.sidebar.slider("Antigüedad (días)", 1, 90, 90)
        
        df_f = df_raw.copy()
        if filtro_esp != "Todos": 
            df_f = df_f[df_f['especialidad'] == filtro_esp]
            
        limite_tiempo = datetime.now(df_f['fecha_creacion'].dt.tz) - timedelta(days=dias)
        df_f = df_f[df_f['fecha_creacion'] >= limite_tiempo]
        
        if df_f.empty:
            st.info("No se encontraron vacantes con los filtros seleccionados.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.altair_chart(alt.Chart(df_f['jerarquia'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('jerarquia:N', sort='-x')), use_container_width=True)
                st.altair_chart(alt.Chart(df_f.explode('hard_skills')['hard_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('hard_skills:N', sort='-x')), use_container_width=True)
            with col2:
                st.altair_chart(alt.Chart(df_f['especialidad'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('especialidad:N', sort='-x')), use_container_width=True)
                st.altair_chart(alt.Chart(df_f.explode('soft_skills')['soft_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('soft_skills:N', sort='-x')), use_container_width=True)

            st.dataframe(
                df_f.drop(columns=['id']), 
                column_config={"link": st.column_config.LinkColumn("Postular", display_text="Ver oferta")}, 
                use_container_width=True
            )

    with tab2:
        archivo = st.file_uploader("Sube tu CV (PDF/TXT)", type=['pdf', 'txt'])
        if archivo:
            if "procesando_cv" not in st.session_state:
                st.session_state.procesando_cv = False

            boton_deshabilitado = st.session_state.procesando_cv

            if st.button("Evaluar compatibilidad con ofertas", disabled=boton_deshabilitado):
                texto = ""
                if archivo.type == "application/pdf":
                    try:
                        reader = PdfReader(archivo)
                        texto = "".join([p.extract_text() for p in reader.pages])
                    except Exception as e:
                        st.error(f"Error al leer el archivo PDF: {e}")
                else:
                    texto = archivo.getvalue().decode("utf-8", errors="ignore")
                    
                if texto.strip() == "":
                    st.warning("El documento cargado no contiene texto legible.")
                else:
                    try:
                        st.session_state.procesando_cv = True
                        cliente = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                        
                        with st.spinner("⚡ Analizando afinidad en tiempo real con IA..."):
                            contexto_ia = df_f.head(25)[['id', 'puesto', 'hard_skills']].to_json(orient='records')
                            cv_recortado = texto[:1500].replace("\n", " ")
                            
                            prompt_minificado = (
                                f"CV:{cv_recortado}. Mapea contra este JSON de ofertas usando el id en id_interno. "
                                f"Extrae SOLO los que tengan MATCH > 70% basado en hard_skills: {contexto_ia}"
                            )
                            
                            resp = cliente.models.generate_content(
                                model='gemini-2.5-flash', 
                                contents=prompt_minificado,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json", 
                                    response_schema=RespuestaMatchIA,
                                    temperature=0.1
                                )
                            )
                            
                            res_data = json.loads(resp.text)
                            evaluaciones = res_data.get('evaluaciones', [])
                            
                            if not evaluaciones:
                                st.info("Ninguna oferta del mercado actual supera el 70% de compatibilidad con tu perfil.")
                            else:
                                evaluaciones_ordenadas = sorted(evaluaciones, key=lambda x: x['match_score'], reverse=True)
                                for item in evaluaciones_ordenadas:
                                    match = df_f[df_f['id'] == item['id_interno']]
                                    if not match.empty:
                                        with st.container(border=True):
                                            st.write(f"### Match: {item['match_score']}% — {match.iloc[0]['puesto']}")
                                            st.write(f"**Empresa:** {match.iloc[0]['empresa']} | **Jerarquía:** {match.iloc[0]['jerarquia']}")
                                            st.write(f"**Coincidencias encontradas:** {item['coincidencias']}")
                                            st.link_button("🔗 Ver Oferta en LinkedIn", match.iloc[0]['link'])
                                            
                    except Exception as e:
                        if "429" in str(e):
                            st.error("⚠️ El servidor de evaluación está muy solicitado en este segundo. Por favor, reintenta en 15 segundos.")
                        else:
                            st.error(f"Error técnico de la IA: {e}")
                    finally:
                        st.session_state.procesando_cv = False
