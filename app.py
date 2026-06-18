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

# Configuración de página inicial en la raíz del script
st.set_page_config(page_title="DataCareer AI", layout="wide", page_icon="💼")

# --- Esquemas Pydantic para Gemini (Garantizan Estructura del JSON de Salida) ---
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# --- Conexión Nativa a Supabase con Sistema de Caché Optimizado ---
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

# Carga e inicialización del DataFrame Global
df_raw = obtener_data_real()

st.title("💼 DataCareer AI")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])

if df_raw.empty:
    st.warning("⚠️ No hay ofertas analíticas disponibles en el repositorio central en este momento.")
else:
    # ==========================================
    # PESTAÑA 1: ANALÍTICA DE MERCADO PUREZA DATA/IA
    # ==========================================
    with tab1:
        st.sidebar.header("⚙️ Filtros")
        filtro_esp = st.sidebar.selectbox("Especialidad", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
        dias = st.sidebar.slider("Antigüedad (días)", 1, 90, 90)
        
        # Copia de seguridad lógica para filtros dinámicos
        df_f = df_raw.copy()
        if filtro_esp != "Todos": 
            df_f = df_f[df_f['especialidad'] == filtro_esp]
            
        limite_tiempo = datetime.now(df_f['fecha_creacion'].dt.tz) - timedelta(days=dias)
        df_f = df_f[df_f['fecha_creacion'] >= limite_tiempo]
        
        if df_f.empty:
            st.info("No se encontraron vacantes analíticas con los filtros seleccionados.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.write("#### Distribución por Jerarquía")
                st.altair_chart(alt.Chart(df_f['jerarquia'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('jerarquia:N', sort='-x')), use_container_width=True)
                
                st.write("#### Hard Skills Demandadas")
                st.altair_chart(alt.Chart(df_f.explode('hard_skills')['hard_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('hard_skills:N', sort='-x')), use_container_width=True)
            with col2:
                st.write("#### Demanda por Especialidad")
                st.altair_chart(alt.Chart(df_f['especialidad'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('especialidad:N', sort='-x')), use_container_width=True)
                
                st.write("#### Soft Skills Clave")
                st.altair_chart(alt.Chart(df_f.explode('soft_skills')['soft_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('soft_skills:N', sort='-x')), use_container_width=True)

            st.write("#### Ofertas Vigentes Monitoreadas")
            st.dataframe(
                df_f.drop(columns=['id']).sort_values(by='fecha_creacion', ascending=False), 
                column_config={"link": st.column_config.LinkColumn("Postular", display_text="Ver oferta")}, 
                use_container_width=True
            )

    # ==========================================
    # PESTAÑA 2: EVALUADOR DETERMINISTA RÍGIDO CV
    # ==========================================
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
                            # DETERMINISMO 1: Forzar ordenamiento estricto por ID para consistencia invariante de contexto
                            df_ordenado = df_f.sort_values(by='id', ascending=True)
                            contexto_ia = df_ordenado.head(30)[['id', 'puesto', 'jerarquia', 'hard_skills']].to_json(orient='records')
                            cv_recortado = texto[:1500].replace("\n", " ")
                            
                            # DETERMINISMO 2: Prompt algorítmico libre de ambigüedad interpretativa
                            prompt_blindado = (
                                f"Eres un algoritmo de emparejamiento matemático frío y determinista. Tu objetivo es emparejar un CV con un catálogo de ofertas de empleo.\n\n"
                                f"Entrada CV: {cv_recortado}\n"
                                f"Entrada Ofertas (JSON): {contexto_ia}\n\n"
                                f"INSTRUCCIONES DE PROCESAMIENTO OBLIGATORIAS:\n"
                                f"1. Procesa cada oferta una por una en el orden exacto proporcionado.\n"
                                f"2. Aplica penalizaciones estrictas fijas:\n"
                                f"   - Si la oferta requiere jerarquía 'Senior' o 'Líder / Jefatura' y el CV no tiene más de 5 años de experiencia explícitos, el match score se limita a un techo máximo de 50%.\n"
                                f"   - Si la oferta es para 'Data Science' y el CV no lista modelos matemáticos, algoritmos o Python/R, el match score máximo es 40%.\n"
                                f"3. Calcula el match score final basándote únicamente en hechos verificables en el texto proporcionado.\n"
                                f"4. Devuelve en la estructura JSON requerida SOLAMENTE aquellos registros cuyo cálculo numérico final sea estrictamente mayor o igual a 70%. No inventes ni varíes la lógica bajo ninguna circunstancia."
                            )
                            
                            resp = cliente.models.generate_content(
                                model='gemini-2.5-flash', 
                                contents=prompt_blindado,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json", 
                                    response_schema=RespuestaMatchIA,
                                    temperature=0.0  # Anula la creatividad de la IA
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
