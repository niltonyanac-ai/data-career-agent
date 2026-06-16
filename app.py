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

st.set_page_config(page_title="DataCareer AI", layout="wide", page_icon="💼")

# --- Esquemas ---
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# --- 1. Motor de Datos ---
def obtener_data():
    roles_config = [
        ("Data Scientist", "Data Science", "Senior", ["Python", "SQL"], ["Liderazgo"], 0.15),
        ("Data Engineer", "Data Engineering", "Semi-Senior", ["Spark", "AWS"], ["Proactividad"], 0.25),
        ("Especialista BI", "Business Intelligence", "Junior", ["Power BI", "SQL"], ["Comunicación"], 0.25),
        ("MLOps Engineer", "MLOps", "Senior", ["Kubernetes", "Docker"], ["Agilidad"], 0.10),
        ("Estadístico", "Estadística", "Semi-Senior", ["R", "Python"], ["Analítica"], 0.10),
        ("Analista", "Inteligencia Comercial", "Mid", ["Excel", "SQL"], ["Negocio"], 0.15)
    ]
    data = []
    for i in range(200):
        r = random.choices(roles_config, weights=[item[5] for item in roles_config])[0]
        data.append({
            'id': i + 1, 'puesto': r[0], 'especialidad': r[1], 'jerarquia': r[2], 
            'hard_skills': r[3], 'soft_skills': r[4], 
            'fecha': datetime.now() - timedelta(days=random.randint(0, 90))
        })
    df = pd.DataFrame(data)
    df['Link'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(r['puesto'])}", axis=1)
    return df

df_raw = obtener_data()

# --- 2. Interfaz ---
st.title("💼 DataCareer AI")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])

with tab1:
    st.sidebar.header("⚙️ Filtros")
    filtro_esp = st.sidebar.selectbox("Especialidad", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
    dias = st.sidebar.slider("Antigüedad (días)", 1, 90, 90)
    
    df_f = df_raw.copy()
    if filtro_esp != "Todos": df_f = df_f[df_f['especialidad'] == filtro_esp]
    df_f = df_f[df_f['fecha'] >= (datetime.now() - timedelta(days=dias))]
    
    col1, col2 = st.columns(2)
    with col1:
        st.altair_chart(alt.Chart(df_f['jerarquia'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('jerarquia:N', sort='-x')), use_container_width=True)
        st.altair_chart(alt.Chart(df_f.explode('hard_skills')['hard_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('hard_skills:N', sort='-x')), use_container_width=True)
    with col2:
        st.altair_chart(alt.Chart(df_f['especialidad'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('especialidad:N', sort='-x')), use_container_width=True)
        st.altair_chart(alt.Chart(df_f.explode('soft_skills')['soft_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('soft_skills:N', sort='-x')), use_container_width=True)

    st.dataframe(df_f.drop(columns=['id']), column_config={"Link": st.column_config.LinkColumn("Postular", display_text="Ver oferta")}, use_container_width=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV (PDF/TXT)", type=['pdf', 'txt'])
    if archivo:
        # Botón para activar IA (Previene errores 429 por llamadas automáticas)
        if st.button("Evaluar compatibilidad con ofertas"):
            texto = ""
            if archivo.type == "application/pdf":
                texto = "".join([p.extract_text() for p in PdfReader(archivo).pages])
            else:
                texto = archivo.getvalue().decode("utf-8", errors="ignore")
                
            try:
                cliente = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                with st.spinner("Analizando matches con IA..."):
                    resp = cliente.models.generate_content(
                        model='gemini-1.5-flash', # Más estable para cuotas gratuitas
                        contents=f"Evalúa CV: {texto[:1500]}. Filtra ofertas con Match > 70% de: {df_f.head(20).to_json()}",
                        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RespuestaMatchIA)
                    )
                    res_data = json.loads(resp.text)
                    for item in res_data['evaluaciones']:
                        match = df_f[df_f['id'] == item['id_interno']]
                        if not match.empty:
                            with st.container(border=True):
                                st.write(f"### Match: {item['match_score']}% - {match.iloc[0]['puesto']}")
                                st.link_button("🔗 Ver Oferta en LinkedIn", match.iloc[0]['Link'])
            except Exception as e:
                if "429" in str(e):
                    st.warning("⚠️ Límite de cuota excedido. Espera unos segundos e intenta de nuevo.")
                else:
                    st.error(f"Error técnico: {e}")
