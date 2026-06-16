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

# --- Esquemas Pydantic ---
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

# --- 2. Interfaz Gráfica ---
st.title("💼 DataCareer AI")
tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador de CV"])

with tab1:
    st.sidebar.header("⚙️ Filtros")
    filtro_esp = st.sidebar.selectbox("Especialidad", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
    dias = st.sidebar.slider("Antigüedad (días)", 1, 90, 90)
    
    df_f = df_raw.copy()
    if filtro_esp != "Todos": df_f = df_f[df_f['especialidad'] == filtro_esp]
    df_f = df_f[df_f['fecha'] >= (datetime.now() - timedelta(days=dias))]
    
    # Renderizado de los 4 Gráficos Requeridos
    col1, col2 = st.columns(2)
    with col1:
        st.altair_chart(alt.Chart(df_f['jerarquia'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('jerarquia:N', sort='-x')), use_container_width=True)
        st.altair_chart(alt.Chart(df_f.explode('hard_skills')['hard_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('hard_skills:N', sort='-x')), use_container_width=True)
    with col2:
        st.altair_chart(alt.Chart(df_f['especialidad'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('especialidad:N', sort='-x')), use_container_width=True)
        st.altair_chart(alt.Chart(df_f.explode('soft_skills')['soft_skills'].value_counts().reset_index()).mark_bar().encode(x='count:Q', y=alt.Y('soft_skills:N', sort='-x')), use_container_width=True)

    # Tabla limpia sin la columna 'id'
    st.dataframe(df_f.drop(columns=['id']), column_config={"Link": st.column_config.LinkColumn("Postular", display_text="Ver oferta")}, use_container_width=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV (PDF/TXT)", type=['pdf', 'txt'])
    if archivo:
        if st.button("Evaluar compatibilidad con ofertas"):
            texto = ""
            if archivo.type == "application/pdf":
                try:
                    reader = PdfReader(archivo)
                    texto = "".join([p.extract_text() for p in reader.pages])
                except Exception as e:
                    st.error(f"Error al leer el archivo PDF: {e}")
            else:
                texto = archivo.getvalue().decode("utf-8", errors="ignore")
                
            if texto.strip() == "":
                st.warning("No se pudo extraer texto del archivo subido.")
            else:
                try:
                    # Inicialización nativa con el nuevo SDK de Google GenAI
                    cliente = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                    with st.spinner("Analizando matches con IA..."):
                        # Usamos gemini-2.5-flash, el modelo estándar y nativo del nuevo SDK
                        resp = cliente.models.generate_content(
                            model='gemini-2.5-flash', 
                            contents=f"Evalúa el siguiente CV: {texto[:2000]}. Filtra y extrae únicamente las vacantes que tengan un MATCH > 70% basándote estrictamente en este listado JSON: {df_f.head(25).to_json()}",
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json", 
                                response_schema=RespuestaMatchIA
                            )
                        )
                        
                        res_data = json.loads(resp.text)
                        
                        if not res_data.get('evaluaciones'):
                            st.info("No se encontraron ofertas con un índice de compatibilidad mayor al 70%.")
                        else:
                            # Ordenar las evaluaciones de mayor a menor porcentaje de match
                            evaluaciones_ordenadas = sorted(res_data['evaluaciones'], key=lambda x: x['match_score'], reverse=True)
                            
                            for item in evaluaciones_ordenadas:
                                match = df_f[df_f['id'] == item['id_interno']]
                                if not match.empty:
                                    with st.container(border=True):
                                        st.write(f"### Match: {item['match_score']}% — {match.iloc[0]['puesto']}")
                                        st.write(f"**Especialidad:** {match.iloc[0]['especialidad']} | **Jerarquía:** {match.iloc[0]['jerarquia']}")
                                        st.write(f"**Coincidencias identificadas:** {item['coincidencias']}")
                                        st.link_button("🔗 Ver Oferta en LinkedIn", match.iloc[0]['Link'])
                                        
                except Exception as e:
                    if "429" in str(e):
                        st.warning("⚠️ Se ha agotado temporalmente la cuota de la API. Por favor, espera un minuto antes de volver a presionar el botón.")
                    else:
                        st.error(f"Error de comunicación con la IA: {e}")
