import streamlit as st
import pandas as pd
import json
import urllib.parse
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
from supabase import create_client

# Configuración de página
st.set_page_config(page_title="DataCareer AI", page_icon="💼", layout="wide")

# Estilos CSS
st.markdown("""<style>
    .match-card { background-color: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 15px; }
    .match-badge { background-color: #2563eb; color: white; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
</style>""", unsafe_allow_html=True)

# Esquemas de IA
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# --- CAPA DE DATOS (Optimizada) ---
def cargar_datos():
    # 1. Intentar Supabase
    try:
        supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        res = supabase.table("vacantes").select("*").execute()
        df = pd.DataFrame(res.data)
    except:
        # 2. Respaldo local
        df = pd.DataFrame([{"id": 1, "puesto": "Data Scientist", "empresa": "BCP", "especialidad": "Data Science", "jerarquia": "Senior", "hard_skills": "Python, SQL", "soft_skills": "Liderazgo"}])
    
    # Limpieza: Convertir strings de habilidades a listas
    for col in ['hard_skills', 'soft_skills']:
        df[col] = df[col].apply(lambda x: x.split(", ") if isinstance(x, str) else [])
    
    # Generar links reales (se regeneran cada vez para asegurar validez)
    df['link'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(r['puesto'] + ' ' + r['empresa'])}&location=Peru", axis=1)
    return df

df_raw = cargar_datos()

# --- INTERFAZ ---
st.title("💼 DataCareer AI")
filtro = st.sidebar.selectbox("Especialidad", ["Todos"] + list(df_raw['especialidad'].unique()))
df_f = df_raw if filtro == "Todos" else df_raw[df_raw['especialidad'] == filtro]

tab1, tab2 = st.tabs(["📊 Inteligencia de Mercado", "🔍 Evaluador de CV"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Jerarquías")
        st.bar_chart(df_f['jerarquia'].value_counts().sort_values(ascending=False))
    with col2:
        st.subheader("Especialidades")
        st.bar_chart(df_f['especialidad'].value_counts().sort_values(ascending=True), horizontal=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV (PDF)", type="pdf")
    if archivo:
        # Lógica de IA consolidada
        try:
            lector = PdfReader(archivo)
            texto = "".join([p.extract_text() for p in lector.pages])
            
            client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            # Prompt optimizado para velocidad
            res = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"Analiza este CV: {texto[:4000]} contra estas vacantes: {df_f.to_json()}",
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RespuestaMatchIA)
            )
            data_ia = json.loads(res.text)
            
            for item in data_ia["evaluaciones"]:
                match = df_f[df_f['id'] == item['id_interno']].iloc[0]
                st.markdown(f"""<div class='match-card'>
                    <h4>{match['puesto']} en {match['empresa']} <span class='match-badge'>{item['match_score']}%</span></h4>
                    <a href='{match['link']}' target='_blank'>Postular en LinkedIn</a>
                </div>""", unsafe_allow_html=True)
        except Exception as e:
            st.error("Error en el motor de IA. Intenta con un archivo más ligero.")
