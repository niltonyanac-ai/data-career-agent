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

st.markdown("""
    <style>
    .match-card { background-color: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 15px; }
    .match-badge { background-color: #2563eb; color: white; padding: 4px 10px; border-radius: 6px; float: right; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# 2. Esquemas de IA
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# 3. Motor de datos completo
@st.cache_data
def obtener_data():
    roles = [
        ("Data Scientist", "Data Science", "Senior", ["Python", "SQL"], ["Liderazgo"]),
        ("Data Engineer", "Data Engineering", "Semi-Senior", ["Spark", "AWS"], ["Proactividad"]),
        ("Analista BI", "Business Intelligence", "Junior", ["Power BI", "SQL"], ["Comunicación"])
    ]
    data = []
    for i in range(50):
        for r in roles:
            data.append({'id': len(data)+1, 'puesto': r[0], 'empresa': f"Tech Corp {i}", 'especialidad': r[1], 'jerarquia': r[2], 'hard_skills': str(r[3]), 'soft_skills': str(r[4])})
    df = pd.DataFrame(data)
    df['link'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(r['puesto'])}&location=Peru", axis=1)
    return df

df_f = obtener_data()

# 4. Interfaz
st.title("💼 DataCareer AI")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])

with tab1:
    st.subheader("Análisis de Oportunidades")
    chart = alt.Chart(df_f['puesto'].value_counts().reset_index()).mark_bar().encode(
        x=alt.X('count:Q', title='Cantidad'), y=alt.Y('puesto:N', sort='-x', title='Puesto')
    )
    st.altair_chart(chart, use_container_width=True)
    st.dataframe(df_f, column_config={"link": st.column_config.LinkColumn("Postular", display_text="Ver oferta")}, use_container_width=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV (PDF)", type="pdf")
    if archivo:
        try:
            reader = PdfReader(archivo)
            texto = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
            
            # Cliente configurado para mayor estabilidad
            cliente_ai = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            
            with st.spinner("Analizando perfil..."):
                respuesta = cliente_ai.models.generate_content(
                    model='gemini-1.5-flash', 
                    contents=f"Evalúa este CV: {texto[:3000]} contra estas vacantes: {df_f.head(20).to_json()}",
                    config=types.GenerateContentConfig(
                        system_instruction="Eres un headhunter. Devuelve JSON.",
                        response_mime_type="application/json",
                        response_schema=RespuestaMatchIA
                    )
                )
            
            datos = json.loads(respuesta.text)
            for res in datos['evaluaciones']:
                # Mapeo de datos para mostrar el enlace en el resultado de la IA
                info = df_f[df_f['id'] == res['id_interno']].iloc[0]
                st.markdown(f"""
                <div class='match-card'>
                    <span class='match-badge'>{res['match_score']}% Match</span>
                    <h4>{info['puesto']} en {info['empresa']}</h4>
                    <p>{res['coincidencias']}</p>
                    <a href='{info['link']}' target='_blank'>Ir a la oferta</a>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error técnico: {e}")
