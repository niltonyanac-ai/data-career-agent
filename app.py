import streamlit as st
import pandas as pd
import json
import urllib.parse
import altair as alt
from datetime import datetime, timedelta
import random
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List

try:
    import docx
except ImportError:
    docx = None

st.set_page_config(page_title="DataCareer AI", layout="wide", page_icon="💼")

# --- Esquemas ---
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# --- 1. Motor de Datos (Sin cache para evitar conflicto mientras desarrollas) ---
def obtener_data():
    roles_config = [
        ("Data Scientist", "Data Science", "Senior", ["Python", "SQL", "ML"], ["Liderazgo"], 0.15),
        ("Data Engineer", "Data Engineering", "Semi-Senior", ["Spark", "Airflow", "AWS"], ["Proactividad"], 0.25),
        ("Especialista BI", "Business Intelligence", "Junior", ["Power BI", "SQL", "Tableau"], ["Comunicación"], 0.25),
        ("MLOps Engineer", "MLOps", "Senior", ["Kubernetes", "Docker", "MLflow"], ["Agilidad"], 0.10),
        ("Estadístico", "Estadística", "Semi-Senior", ["R", "Python", "SQL"], ["Analítica"], 0.10),
        ("Analista", "Inteligencia Comercial", "Mid", ["Excel", "SQL", "Salesforce"], ["Negocio"], 0.15)
    ]
    data = []
    for i in range(250):
        r = random.choices(roles_config, weights=[item[5] for item in roles_config])[0]
        fecha = datetime.now() - timedelta(days=random.randint(0, 90))
        data.append({'id': i + 1, 'puesto': r[0], 'especialidad': r[1], 'jerarquia': r[2], 
                     'hard_skills': r[3], 'soft_skills': r[4], 'fecha_publicacion': fecha})
    return pd.DataFrame(data)

df_raw = obtener_data()

# --- 2. Lógica de archivos ---
def procesar_archivo(archivo):
    try:
        if archivo.type == "application/pdf":
            return "".join([p.extract_text() for p in PdfReader(archivo).pages])
        elif "wordprocessingml" in archivo.type and docx:
            return "\n".join([para.text for para in docx.Document(archivo).paragraphs])
        else:
            return archivo.getvalue().decode("utf-8")
    except Exception: return None

# --- 3. UI ---
st.title("💼 DataCareer AI: Termómetro Laboral")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])

with tab1:
    filtro_esp = st.sidebar.selectbox("Especialidad", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
    dias = st.sidebar.slider("Antigüedad (días)", 1, 90, 90)
    
    df_f = df_raw.copy()
    if filtro_esp != "Todos": df_f = df_f[df_f['especialidad'] == filtro_esp]
    df_f = df_f[df_f['fecha_publicacion'] >= (datetime.now() - timedelta(days=dias))]
    
    # 4 GRÁFICOS RESTAURADOS
    c1, c2 = st.columns(2)
    with c1:
        st.altair_chart(alt.Chart(df_f['jerarquia'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('jerarquia:N', sort='-x')), use_container_width=True)
        st.altair_chart(alt.Chart(df_f.explode('hard_skills')['hard_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('hard_skills:N', sort='-x')), use_container_width=True)
    with c2:
        st.altair_chart(alt.Chart(df_f['especialidad'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('especialidad:N', sort='-x')), use_container_width=True)
        st.altair_chart(alt.Chart(df_f.explode('soft_skills')['soft_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('soft_skills:N', sort='-x')), use_container_width=True)

    st.dataframe(df_f, use_container_width=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV", type=['pdf', 'docx', 'txt'])
    if archivo:
        texto = procesar_archivo(archivo)
        if texto:
            cliente = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            resp = cliente.models.generate_content(
                model='gemini-1.0-pro', 
                contents=f"Evalúa CV: {texto[:1000]}. Filtra datos: {df_f.head(10).to_json()}",
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RespuestaMatchIA)
            )
            for res in json.loads(resp.text)['evaluaciones']:
                m = df_f[df_f['id'] == res['id_interno']]
                if not m.empty:
                    st.success(f"Match: {res['match_score']}% | {m.iloc[0]['puesto']}")
