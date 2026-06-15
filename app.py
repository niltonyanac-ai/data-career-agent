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

# CSS para tarjetas profesionales
st.markdown("""
    <style>
    .match-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .match-badge { background-color: #0f172a; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

# 2. Esquemas de IA
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# 3. Motor de datos
@st.cache_data
def obtener_data():
    roles = [
        ("Data Scientist", "Data Science", "Senior", ["Python", "SQL", "Machine Learning"]),
        ("Data Engineer", "Data Engineering", "Semi-Senior", ["Spark", "AWS", "Python"]),
        ("Analista BI", "Business Intelligence", "Junior", ["Power BI", "SQL", "Excel"])
    ]
    data = []
    id_counter = 1
    for i in range(55):
        for r in roles:
            data.append({
                'id': id_counter, 'puesto': r[0], 'empresa': f"Tech Corp {i}", 
                'especialidad': r[1], 'jerarquia': r[2], 'hard_skills': str(r[3])
            })
            id_counter += 1
    df = pd.DataFrame(data)
    # URL optimizada para búsqueda de LinkedIn
    df['link'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(r['puesto'])}&location=Peru", axis=1)
    return df

df_f = obtener_data()

# 4. Interfaz Principal
st.title("💼 DataCareer AI")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])

with tab1:
    st.subheader("Análisis de 165 ofertas activas")
    col1, col2 = st.columns(2)
    with col1:
        # Gráfico Jerarquías
        chart = alt.Chart(df_f['jerarquia'].value_counts().reset_index()).mark_bar().encode(
            x=alt.X('count:Q', title='Cant.'), y=alt.Y('jerarquia:N', sort='-x', title='Jerarquía')
        )
        st.altair_chart(chart, use_container_width=True)
    with col2:
        # Gráfico Especialidades
        chart2 = alt.Chart(df_f['especialidad'].value_counts().reset_index()).mark_bar().encode(
            x=alt.X('count:Q', title='Cant.'), y=alt.Y('especialidad:N', sort='-x', title='Espec.')
        )
        st.altair_chart(chart2, use_container_width=True)
    
    st.dataframe(df_f, column_config={"link": st.column_config.LinkColumn("Postular", display_text="Ver oferta")}, use_container_width=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV (PDF)", type="pdf")
    if archivo:
        try:
            reader = PdfReader(archivo)
            texto = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
            
            if not texto:
                st.warning("El PDF no contiene texto legible.")
            else:
                cliente_ai = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                with st.spinner("Analizando tu perfil..."):
                    respuesta = cliente_ai.models.generate_content(
                        model='gemini-1.5-flash', 
                        contents=f"Evalúa este CV: {texto[:2000]} contra estas vacantes: {df_f.head(10).to_json()}",
                        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RespuestaMatchIA)
                    )
                    datos = json.loads(respuesta.text)
                    for res in datos['evaluaciones']:
                        info = df_f[df_f['id'] == res['id_interno']].iloc[0]
                        st.markdown(f"""
                        <div class='match-card'>
                            <span class='match-badge'>{res['match_score']}% Match</span>
                            <h4 style='margin-top:10px'>{info['puesto']}</h4>
                            <p>{res['coincidencias']}</p>
                            <a href='{info['link']}' target='_blank'>🔗 Ir a la oferta</a>
                        </div>
                        """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error detectado: {e}")
