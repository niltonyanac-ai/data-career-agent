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
                df_f.drop(columns=['id']).sort_values(by='fecha_creacion', ascending=False), 
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
                            # Ordenamos por fecha descendente para garantizar evaluar lo más nuevo del mercado
                            df_ordenado = df_f.sort_values(by='fecha_creacion', ascending=False)
                            
                            # Agregamos la columna 'jerarquia' indispensable para el análisis dimensional profundo
                            contexto_ia = df_ordenado.head(25)[['id', 'puesto', 'jerarquia', 'hard_skills']].to_json(orient='records')
                            cv_recortado = texto[:1500].replace("\n", " ")
                            
                            prompt_blindado = (
                                f"Actúas como un reclutador corporativo técnico e implacable. "
                                f"Evalúa minuciosamente el siguiente CV recortado: {cv_recortado}. "
                                f"Mapea su afinidad contra este JSON de ofertas usando el id en id_interno: {contexto_ia}.\n\n"
                                f"Reglas matemáticas obligatorias para calcular el match_score (0 a 100):\n"
                                f"1. Si una oferta indica jerarquía 'Senior' o 'Líder / Jefatura' y el CV no refleja explícitamente años de experiencia sólida a cargo, el match máximo permitido es 55%.\n"
                                f"2. Saber SQL y Excel NO valida a un candidato para puestos etiquetados como 'Data Scientist' o 'Machine Learning Engineer'. Si no hay fundamentos estadísticos o de modelamiento evidentes en el CV para estos roles, el match máximo permitido es 45%.\n"
                                f"3. Reserva puntajes mayores al 85% únicamente si el rol, el seniority requerido y las tecnologías específicas calzan de manera exacta.\n"
                                f"Extrae en la estructura JSON solicitada SOLO aquellos registros cuyo cálculo matemático estricto supere el 70%."
                            )
                            
                            resp = cliente.models.generate_content(
                                model='gemini-2.5-flash', 
                                contents=prompt_blindado,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json", 
                                    response_schema=RespuestaMatchIA,
                                    temperature=0.0  # Consistencia y lógica estricta sin margen a la creatividad
                                )
                            )
                            
                            res_data = json.loads(resp.text)
                            evaluaciones = res_data.get('evaluaciones', [])
                            
                            if not evaluaciones:
                                st.info("Ninguna oferta disponible del mercado actual supera el 70% de compatibilidad estricta con tu perfil.")
                            else:
                                evaluaciones_ordenadas = sorted(evaluaciones, key=lambda x: x['match_score'], reverse=True)
                                for item in evaluaciones_ordenadas:
                                    match = df_f[df_f['id'] == item['id_interno']]
                                    if not match.empty:
                                        with st.container(border=True):
                                            st.write(f"### Match: {item['match_score']}% — {match.iloc[0]['puesto']}")
                                            st.write(f"**Empresa:** {match.iloc[0]['empresa']} | **Jerarquía:** {match.iloc[0]['jerarquia']}")
                                            st.write(f"**Criterio de coincidencia:** {item['coincidencias']}")
                                            st.link_button("🔗 Ver Oferta en LinkedIn", match.iloc[0]['link'])
                                            
                    except Exception as e:
                        if "429" in str(e):
                            st.error("⚠️ El servidor está recibiendo un alto volumen de solicitudes simultáneas. Por favor, reintenta en 15 segundos.")
                        else:
                            st.error(f"Error técnico de la IA: {e}")
                    finally:
                        st.session_state.procesando_cv = False
