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

# --- 1. Motor de Datos ---
@st.cache_data(show_spinner=False)
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
        # Generar fechas reales para que el filtro funcione
        dias_aleatorios = random.randint(0, 90)
        fecha = datetime.now() - timedelta(days=dias_aleatorios)
        data.append({
            'id': i + 1, 'puesto': r[0], 'especialidad': r[1], 'jerarquia': r[2], 
            'hard_skills': r[3], 'soft_skills': r[4], 'fecha_publicacion': fecha
        })
    df = pd.DataFrame(data)
    df['Postular'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(r['puesto'])}", axis=1)
    return df

df_raw = obtener_data()

# --- 2. Lógica de lectura de archivos ---
def procesar_archivo(archivo):
    try:
        if archivo.name.endswith('.pdf'):
            reader = PdfReader(archivo)
            return "".join([p.extract_text() for p in reader.pages])
        elif archivo.name.endswith('.docx') and docx:
            doc = docx.Document(archivo)
            return "\n".join([para.text for para in doc.paragraphs])
        elif archivo.name.endswith('.txt'):
            return archivo.getvalue().decode("utf-8")
    except Exception as e:
        st.error(f"Error al leer archivo: {e}")
    return None

# --- 3. Interfaz ---
st.title("💼 DataCareer AI: Termómetro Laboral")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])

with tab1:
    st.sidebar.header("⚙️ Filtros")
    filtro_esp = st.sidebar.selectbox("Especialidad", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
    dias_antiguedad = st.sidebar.slider("Antigüedad máxima (días):", 1, 90, 90)
    
    # Aplicar filtros (Ordenados por fecha más reciente)
    df_f = df_raw.copy()
    if filtro_esp != "Todos":
        df_f = df_f[df_f['especialidad'] == filtro_esp]
    
    limite = datetime.now() - timedelta(days=dias_antiguedad)
    df_f = df_f[df_f['fecha_publicacion'] >= limite].sort_values(by='fecha_publicacion', ascending=False)
    
    # Gráficos REINCORPORADOS
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Hard Skills en Demanda")
        st.altair_chart(alt.Chart(df_f.explode('hard_skills')['hard_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('hard_skills:N', sort='-x')), use_container_width=True)
    with c2:
        st.subheader("Especialidad")
        st.altair_chart(alt.Chart(df_f['especialidad'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('especialidad:N', sort='-x')), use_container_width=True)
    
    st.dataframe(df_f.drop(columns=['id']), column_config={"Postular": st.column_config.LinkColumn("Acción", display_text="Ver oferta")}, use_container_width=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV (PDF, DOCX, TXT)", type=['pdf', 'docx', 'txt'])
    if archivo:
        texto = procesar_archivo(archivo)
        if texto:
            try:
                cliente = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                with st.spinner("Analizando match >70%..."):
                    resp = cliente.models.generate_content(
                        model='gemini-1.0-pro', 
                        contents=f"Evalúa CV: {texto[:1500]}. Filtra y muestra solo vacantes con MATCH > 70%. Datos: {df_f.head(15).to_json()}", 
                        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RespuestaMatchIA)
                    )
                    for res in json.loads(resp.text)['evaluaciones']:
                        m = df_f[df_f['id'] == res['id_interno']]
                        if not m.empty:
                            with st.container(border=True):
                                st.success(f"Match: {res['match_score']}% | {m.iloc[0]['puesto']}")
                                st.link_button("🔗 Ver Oferta en LinkedIn", m.iloc[0]['Postular'])
            except Exception as e:
                st.error("Error al procesar el archivo. Revisa tu API Key.")
