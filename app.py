import streamlit as st
import pandas as pd
import json
import urllib.parse
import altair as alt
import docx  # Requiere: pip install python-docx
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List

st.set_page_config(page_title="DataCareer AI", layout="wide", page_icon="💼")

class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

@st.cache_data
def obtener_data():
    # Catálogo expandido de especialidades
    roles = [
        ("Data Scientist", "Data Science", "Senior", ["Python", "SQL", "ML"], ["Liderazgo"]),
        ("MLOps Engineer", "MLOps", "Senior", ["Kubernetes", "Docker", "Python"], ["Agilidad"]),
        ("Estadístico", "Estadística", "Semi-Senior", ["R", "Python", "SQL"], ["Analítica"]),
        ("Especialista BI", "Business Intelligence", "Junior", ["Power BI", "SQL"], ["Comunicación"]),
        ("Analista Inteligencia Comercial", "Inteligencia Comercial", "Mid", ["Excel", "SQL", "CRM"], ["Negocio"])
    ]
    data = []
    for i in range(40):
        for r in roles:
            data.append({'id': len(data)+1, 'puesto': r[0], 'especialidad': r[1], 'jerarquia': r[2], 'hard_skills': r[3], 'soft_skills': r[4]})
    df = pd.DataFrame(data)
    df['Postular'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(r['puesto'])}", axis=1)
    return df

df_raw = obtener_data()

# Lógica de lectura de archivos múltiples
def leer_archivo(archivo):
    if archivo.name.endswith('.pdf'):
        reader = PdfReader(archivo)
        return "".join([p.extract_text() for p in reader.pages])
    elif archivo.name.endswith('.docx'):
        doc = docx.Document(archivo)
        return "\n".join([para.text for para in doc.paragraphs])
    elif archivo.name.endswith('.txt'):
        return archivo.getvalue().decode("utf-8")
    return ""

# Interfaz
st.title("💼 DataCareer AI: Inteligencia Laboral")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])

with tab1:
    filtro = st.sidebar.selectbox("Especialidad", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
    df_f = df_raw if filtro == "Todos" else df_raw[df_raw['especialidad'] == filtro]
    
    col1, col2 = st.columns(2)
    with col1:
        st.altair_chart(alt.Chart(df_f.explode('hard_skills')['hard_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y='hard_skills:N'), use_container_width=True)
    with col2:
        st.altair_chart(alt.Chart(df_f.explode('soft_skills')['soft_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y='soft_skills:N'), use_container_width=True)
    st.dataframe(df_f.drop(columns=['id']), column_config={"Postular": st.column_config.LinkColumn("Acción", display_text="Ver oferta")}, use_container_width=True)

with tab2:
    archivo = st.file_uploader("Cargar CV (PDF, DOCX, TXT)", type=['pdf', 'docx', 'txt'])
    if archivo:
        texto = leer_archivo(archivo)
        if texto:
            try:
                cliente_ai = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                with st.spinner("Analizando perfil..."):
                    resp = cliente_ai.models.generate_content(
                        model='gemini-1.0-pro',
                        contents=f"CV: {texto[:2000]}. Filtra vacantes con >70% match. Datos: {df_f.head(10).to_json()}",
                        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RespuestaMatchIA)
                    )
                    for res in json.loads(resp.text)['evaluaciones']:
                        match = df_f[df_f['id'] == res['id_interno']]
                        if not match.empty:
                            info = match.iloc[0]
                            st.success(f"Match: {res['match_score']}% - {info['puesto']}")
                            st.link_button("🔗 Ver Oferta", info['Postular'])
            except Exception as e:
                st.error("Error al procesar el documento.")
