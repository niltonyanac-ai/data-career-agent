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

# Configuración de diseño profesional
st.set_page_config(page_title="DataCareer AI", layout="wide", page_icon="💼")

# Esquemas Pydantic para estructura garantizada
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# Motor de datos optimizado
@st.cache_data
def obtener_data():
    roles = [
        ("Data Scientist", "Data Science", "Senior", ["Python", "SQL", "Machine Learning"], ["Liderazgo", "Comunicación"]),
        ("Data Engineer", "Data Engineering", "Semi-Senior", ["Spark", "AWS", "Python"], ["Proactividad", "Trabajo en equipo"]),
        ("Analista BI", "Business Intelligence", "Junior", ["Power BI", "SQL", "Excel"], ["Comunicación", "Atención al detalle"])
    ]
    data = []
    for i in range(55):
        for r in roles:
            data.append({
                'id': len(data)+1, 'puesto': r[0], 'empresa': f"Corp {i}", 
                'especialidad': r[1], 'jerarquia': r[2], 'hard_skills': r[3], 'soft_skills': r[4]
            })
    df = pd.DataFrame(data)
    df['Postular'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(r['puesto'])}", axis=1)
    return df

df_raw = obtener_data()

# Interfaz Principal
st.title("💼 DataCareer AI: Inteligencia de Mercado Laboral")
tab1, tab2 = st.tabs(["📊 Inteligencia de Mercado", "🔍 Evaluador Inteligente de CV"])

with tab1:
    st.sidebar.header("⚙️ Configuración")
    filtro = st.sidebar.selectbox("Selecciona Especialidad Funcional", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
    df_f = df_raw if filtro == "Todos" else df_raw[df_raw['especialidad'] == filtro]
    
    # 4 Gráficos Profesionales
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Jerarquías Demandadas")
        st.altair_chart(alt.Chart(df_f['jerarquia'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('jerarquia:N', sort='-x')), use_container_width=True)
        st.subheader("Hard Skills")
        st.altair_chart(alt.Chart(df_f.explode('hard_skills')['hard_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('hard_skills:N', sort='-x')), use_container_width=True)
    with col2:
        st.subheader("Especialidad Funcional")
        st.altair_chart(alt.Chart(df_f['especialidad'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('especialidad:N', sort='-x')), use_container_width=True)
        st.subheader("Soft Skills")
        st.altair_chart(alt.Chart(df_f.explode('soft_skills')['soft_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('soft_skills:N', sort='-x')), use_container_width=True)

    st.dataframe(df_f.drop(columns=['id']), column_config={"Postular": st.column_config.LinkColumn("Acción", display_text="Ver oferta")}, use_container_width=True)

with tab2:
    st.subheader("Evaluador Automático")
    archivo = st.file_uploader("Sube tu CV en formato PDF", type="pdf")
    if archivo:
        try:
            reader = PdfReader(archivo)
            texto = "".join([p.extract_text() for p in reader.pages])
            cliente_ai = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            
            with st.spinner("Realizando match semántico de alta precisión..."):
                resp = cliente_ai.models.generate_content(
                    model='gemini-1.0-pro',
                    contents=f"CV: {texto[:1500]}. Filtra y muestra solo vacantes con MATCH superior al 70%. Datos vacantes: {df_f.head(20).to_json()}",
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RespuestaMatchIA)
                )
                
                evaluaciones = json.loads(resp.text)['evaluaciones']
                if not evaluaciones:
                    st.warning("No se encontraron coincidencias superiores al 70%. Intenta con un CV más detallado.")
                else:
                    for res in evaluaciones:
                        match = df_f[df_f['id'] == res['id_interno']]
                        if not match.empty:
                            info = match.iloc[0]
                            with st.container(border=True):
                                st.success(f"### {info['puesto']} en {info['empresa']} ({res['match_score']}% Match)")
                                st.write(f"**Coincidencias clave:** {res['coincidencias']}")
                                st.link_button("🔗 Ver Oferta en LinkedIn", info['Postular'])
        except Exception as e:
            st.error("Ocurrió un error al procesar el archivo. Por favor, asegúrate de que sea un PDF legible.")
