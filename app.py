import streamlit as st
import pandas as pd
import json
import urllib.parse
import altair as alt
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List

# Importación segura (la librería se llama python-docx, el módulo es docx)
try:
    import docx
except ImportError:
    docx = None

st.set_page_config(page_title="DataCareer AI", layout="wide", page_icon="💼")

# --- ESQUEMAS ---
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# --- MOTOR DE DATOS (Nueva versión para evitar conflicto de caché) ---
@st.cache_data(show_spinner=False)
def cargar_ofertas_v2():
    roles = [
        ("Data Scientist", "Data Science", "Senior", ["Python", "SQL", "ML"], ["Liderazgo"]),
        ("MLOps Engineer", "MLOps", "Senior", ["Kubernetes", "Docker"], ["Agilidad"]),
        ("Estadístico", "Estadística", "Semi-Senior", ["R", "Python"], ["Analítica"]),
        ("Especialista BI", "Business Intelligence", "Junior", ["Power BI", "SQL"], ["Comunicación"]),
        ("Analista Inteligencia Comercial", "Inteligencia Comercial", "Mid", ["Excel", "SQL"], ["Negocio"])
    ]
    data = []
    for i in range(40):
        for r in roles:
            data.append({'id': len(data)+1, 'puesto': r[0], 'especialidad': r[1], 'jerarquia': r[2], 'hard_skills': r[3], 'soft_skills': r[4]})
    df = pd.DataFrame(data)
    df['Postular'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(r['puesto'])}", axis=1)
    return df

df_raw = cargar_ofertas_v2()

# --- LECTURA DE ARCHIVOS ---
def leer_archivo(archivo):
    try:
        if archivo.name.endswith('.pdf'):
            reader = PdfReader(archivo)
            return "\n".join([p.extract_text() for p in reader.pages])
        elif archivo.name.endswith('.docx'):
            if docx:
                doc = docx.Document(archivo)
                return "\n".join([para.text for para in doc.paragraphs])
            else:
                return "Error: Librería docx no instalada."
        elif archivo.name.endswith('.txt'):
            return archivo.getvalue().decode("utf-8")
    except Exception:
        return ""
    return ""

# --- UI ---
st.title("💼 DataCareer AI")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])

with tab1:
    filtro = st.sidebar.selectbox("Especialidad", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
    df_f = df_raw if filtro == "Todos" else df_raw[df_raw['especialidad'] == filtro]
    st.dataframe(df_f.drop(columns=['id']), use_container_width=True)

with tab2:
    archivo = st.file_uploader("Cargar CV", type=['pdf', 'docx', 'txt'])
    if archivo:
        texto = leer_archivo(archivo)
        if texto:
            try:
                cliente_ai = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                resp = cliente_ai.models.generate_content(
                    model='gemini-1.0-pro',
                    contents=f"CV: {texto[:1500]}. Solo vacantes >70% match. Datos: {df_f.head(10).to_json()}",
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RespuestaMatchIA)
                )
                for res in json.loads(resp.text)['evaluaciones']:
                    match = df_f[df_f['id'] == res['id_interno']]
                    if not match.empty:
                        st.success(f"Match: {res['match_score']}% - {match.iloc[0]['puesto']}")
            except Exception as e:
                st.error("Error al procesar el archivo.")
