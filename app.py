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

# Estilos UX
st.markdown("""<style>
    .match-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .match-badge { background-color: #2563eb; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 12px; }
</style>""", unsafe_allow_html=True)

# Esquemas de IA
class Evaluacion(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

# 1. CARGA DE DATOS ESCALADA (165 registros)
def obtener_data():
    try:
        supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        res = supabase.table("vacantes").select("*").execute()
        df = pd.DataFrame(res.data)
    except:
        roles = [
            ("Data Scientist", "Data Science", "Senior", ["Python", "SQL"], ["Liderazgo"]),
            ("Data Engineer", "Data Engineering", "Semi-Senior", ["Spark", "AWS"], ["Proactividad"]),
            ("Analista BI", "Business Intelligence", "Junior", ["Power BI", "SQL"], ["Comunicación"]),
            ("Data Analyst", "Data Analytics", "Senior", ["Tableau", "SQL"], ["Visión de Negocio"]),
            ("Ingeniero MLOps", "MLOps", "Senior", ["Docker", "Kubernetes"], ["Agilidad"]),
            ("Analista Comercial", "Inteligencia Comercial", "Semi-Senior", ["Excel", "SQL"], ["Negociación"]),
            ("Especialista Data Science", "Data Science", "Senior", ["TensorFlow", "Python"], ["Estrategia"]),
            ("Arquitecto de Datos", "Data Engineering", "Senior", ["Snowflake", "ETL"], ["Arquitectura"]),
            ("Analista Senior BI", "Business Intelligence", "Senior", ["MicroStrategy", "SQL"], ["Comunicación"]),
            ("Data Wrangler", "Data Engineering", "Junior", ["Pandas", "Python"], ["Organización"]),
            ("Analista Estadístico", "Estadística Avanzada", "Senior", ["R", "SAS"], ["Análisis Riguroso"])
        ]
        lote = []
        for i in range(15):
            for r in roles:
                lote.append({'id': len(lote)+1, 'puesto': r[0], 'empresa': f"Empresa {i+1}", 'especialidad': r[1], 'jerarquia': r[2], 'hard_skills': r[3], 'soft_skills': r[4]})
        df = pd.DataFrame(lote)
    
    df['link'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(str(r['puesto']) + ' ' + str(r['empresa']))}&location=Peru", axis=1)
    return df

df_raw = obtener_data()

# 2. INTERFAZ
st.title("💼 DataCareer AI")
filtro = st.sidebar.selectbox("Especialidad Funcional", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
df_f = df_raw if filtro == "Todos" else df_raw[df_raw['especialidad'] == filtro]

tab1, tab2 = st.tabs(["📊 Inteligencia de Mercado", "🔍 Evaluador de CV"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Vacantes por Jerarquía (Descendente)")
        st.bar_chart(df_f['jerarquia'].value_counts().sort_values(ascending=False))
        st.subheader("Hard Skills más demandadas")
        st.bar_chart(pd.Series([s for sub in df_f['hard_skills'] for s in sub]).value_counts().sort_values(ascending=True), horizontal=True)
    with col2:
        st.subheader("Vacantes por Especialidad (Descendente)")
        st.bar_chart(df_f['especialidad'].value_counts().sort_values(ascending=True), horizontal=True)
        st.subheader("Soft Skills más demandadas")
        st.bar_chart(pd.Series([s for sub in df_f['soft_skills'] for s in sub]).value_counts().sort_values(ascending=True), horizontal=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV (PDF)", type="pdf")
    if archivo:
        with st.spinner("Analizando afinidad..."):
            try:
                reader = PdfReader(archivo)
                texto = "".join([p.extract_text() for p in reader.pages])
                client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                
                res = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=f"Analiza: {texto[:3000]} contra: {df_f.to_json()}",
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=List[Evaluacion])
                )
                
                df_match = pd.merge(df_f, pd.DataFrame(json.loads(res.text)), left_on='id', right_on='id_interno')
                
                for _, row in df_match.sort_values('match_score', ascending=False).iterrows():
                    st.markdown(f"""<div class='match-card'>
                        <h4>{row['puesto']} - {row['empresa']} <span class='match-badge'>{row['match_score']}%</span></h4>
                        <p>{row['coincidencias']}</p>
                        <a href='{row['link']}' target='_blank'>Postular en LinkedIn</a>
                    </div>""", unsafe_allow_html=True)
            except Exception as e:
                st.error("Error al procesar el match. Asegúrate de que el PDF sea legible.")
