import streamlit as st
import pandas as pd
import json
import altair as alt
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List

# 1. Configuración de Performance (Gratis)
st.set_page_config(page_title="DataCareer AI", layout="wide")

class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

@st.cache_data(ttl=3600) # Limpieza automática cada hora
def obtener_data():
    roles = [
        ("Data Scientist", "Data Science", "Senior", ["Python", "SQL"], ["Liderazgo"]),
        ("Data Engineer", "Data Engineering", "Semi-Senior", ["Spark", "AWS"], ["Proactividad"]),
        ("Analista BI", "Business Intelligence", "Junior", ["Power BI", "SQL"], ["Comunicación"])
    ]
    data = []
    for i in range(20): # Mantenemos 60 registros para no agotar la RAM
        for r in roles:
            data.append({'id': len(data)+1, 'puesto': r[0], 'especialidad': r[1], 'jerarquia': r[2], 'hard_skills': r[3], 'soft_skills': r[4]})
    return pd.DataFrame(data)

df_raw = obtener_data()

# 2. UI y Lógica de Filtrado
st.title("💼 DataCareer AI")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador"])

with tab1:
    filtro = st.selectbox("Filtrar por Especialidad", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
    df_f = df_raw if filtro == "Todos" else df_raw[df_raw['especialidad'] == filtro]
    
    # Gráficos con procesamiento 'explode'
    df_h = df_f.explode('hard_skills')
    st.altair_chart(alt.Chart(df_h['hard_skills'].value_counts().reset_index()).mark_bar().encode(
        x='count:Q', y=alt.Y('hard_skills:N', sort='-x')), use_container_width=True)
    st.dataframe(df_f, use_container_width=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV (PDF)", type="pdf")
    if archivo:
        try:
            reader = PdfReader(archivo)
            texto = "".join([p.extract_text() for p in reader.pages])
            
            # Cliente configurado para entorno gratuito (gemini-1.0-pro es el más estable en Free Tier)
            cliente_ai = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            
            with st.spinner("Analizando..."):
                resp = cliente_ai.models.generate_content(
                    model='gemini-1.0-pro',
                    contents=f"Evalúa este CV: {texto[:1000]} contra estas vacantes: {df_f.head(5).to_json()}",
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RespuestaMatchIA)
                )
                for res in json.loads(resp.text)['evaluaciones']:
                    st.write(f"✅ Match: {res['match_score']}% | {res['coincidencias']}")
        except Exception as e:
            st.error(f"Error técnico: {e}. Verifica tu API Key en AI Studio.")
