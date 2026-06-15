import streamlit as st
import pandas as pd
import json
import urllib.parse
import altair as alt
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List

# 1. Configuración de página
st.set_page_config(page_title="DataCareer AI", page_icon="💼", layout="wide")

# CSS para tarjetas profesionales y estilo visual
st.markdown("""
    <style>
    .match-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 15px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .match-badge { background-color: #2563eb; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; }
    </style>
""", unsafe_allow_html=True)

# 2. Esquemas de IA (Validación Pydantic)
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# 3. Motor de datos con caché
@st.cache_data
def obtener_data():
    roles = [
        ("Data Scientist", "Data Science", "Senior", ["Python", "SQL", "Machine Learning"], ["Liderazgo", "Comunicación"]),
        ("Data Engineer", "Data Engineering", "Semi-Senior", ["Spark", "AWS", "Python"], ["Proactividad", "Trabajo en equipo"]),
        ("Analista BI", "Business Intelligence", "Junior", ["Power BI", "SQL", "Excel"], ["Comunicación", "Atención al detalle"])
    ]
    data = []
    id_counter = 1
    for i in range(55): # Generación de 165 registros
        for r in roles:
            data.append({
                'id': id_counter, 'puesto': r[0], 'empresa': f"Corp {i}", 
                'especialidad': r[1], 'jerarquia': r[2], 'hard_skills': r[3], 'soft_skills': r[4]
            })
            id_counter += 1
    df = pd.DataFrame(data)
    df['link'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(r['puesto'])}&location=Peru", axis=1)
    return df

df_raw = obtener_data()

# 4. SIDEBAR: Filtros Globales
st.sidebar.header("⚙️ Filtros del Mercado")
filtro_esp = st.sidebar.selectbox("Especialidad Funcional", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
df_f = df_raw if filtro_esp == "Todos" else df_raw[df_raw['especialidad'] == filtro_esp]

# 5. INTERFAZ
st.title("💼 DataCareer AI")
tab1, tab2 = st.tabs(["📊 Inteligencia de Mercado", "🔍 Evaluador Inteligente de CV"])

with tab1:
    col1, col2 = st.columns(2)
    # Procesamiento crítico para gráficos (Explode para contar elementos de listas)
    hards = df_f.explode('hard_skills')
    softs = df_f.explode('soft_skills')
    
    with col1:
        st.subheader("Jerarquías")
        st.altair_chart(alt.Chart(df_f['jerarquia'].value_counts().reset_index()).mark_bar().encode(
            x=alt.X('count:Q', title='Cantidad'), y=alt.Y('jerarquia:N', sort='-x', title='Jerarquía')
        ), use_container_width=True)
        
        st.subheader("Hard Skills")
        st.altair_chart(alt.Chart(hards['hard_skills'].value_counts().reset_index()).mark_bar().encode(
            x=alt.X('count:Q', title='Cantidad'), y=alt.Y('hard_skills:N', sort='-x', title='Skill')
        ), use_container_width=True)

    with col2:
        st.subheader("Especialidad")
        st.altair_chart(alt.Chart(df_f['especialidad'].value_counts().reset_index()).mark_bar().encode(
            x=alt.X('count:Q', title='Cantidad'), y=alt.Y('especialidad:N', sort='-x', title='Espec.')
        ), use_container_width=True)
        
        st.subheader("Soft Skills")
        st.altair_chart(alt.Chart(softs['soft_skills'].value_counts().reset_index()).mark_bar().encode(
            x=alt.X('count:Q', title='Cantidad'), y=alt.Y('soft_skills:N', sort='-x', title='Skill')
        ), use_container_width=True)

    st.dataframe(df_f.drop(columns=['hard_skills', 'soft_skills']), column_config={"link": st.column_config.LinkColumn("Postular", display_text="Ver oferta")}, use_container_width=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV (PDF)", type="pdf")
    if archivo:
        try:
            reader = PdfReader(archivo)
            texto = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
            if not texto: st.warning("El PDF no tiene texto legible.")
            else:
                cliente_ai = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                with st.spinner("Analizando tu perfil con IA..."):
                    resp = cliente_ai.models.generate_content(
                        model='gemini-1.5-flash', 
                        contents=f"Evalúa este CV: {texto[:2000]} contra estas vacantes filtradas: {df_f.head(10).to_json()}", 
                        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RespuestaMatchIA)
                    )
                    datos = json.loads(resp.text)
                    for res in datos['evaluaciones']:
                        info = df_f[df_f['id'] == res['id_interno']].iloc[0]
                        st.markdown(f"""
                        <div class='match-card'>
                            <span class='match-badge'>{res['match_score']}% Match</span>
                            <h4 style='margin-top:15px'>{info['puesto']} en {info['empresa']}</h4>
                            <p>{res['coincidencias']}</p>
                            <a href='{info['link']}' target='_blank'>🔗 Postular en LinkedIn</a>
                        </div>
                        """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error técnico en el análisis: {e}")
