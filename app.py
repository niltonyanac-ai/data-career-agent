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

st.set_page_config(page_title="DataCareer AI", page_icon="💼", layout="wide")

# Estilos CSS
st.markdown("""<style>
    .match-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 15px; }
    .match-badge { background-color: #2563eb; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; }
</style>""", unsafe_allow_html=True)

class Evaluacion(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

# CARGA DE DATOS SIN CACHÉ
def obtener_data():
    try:
        supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        res = supabase.table("vacantes").select("*").execute()
        df = pd.DataFrame(res.data)
    except:
        roles = [("Data Scientist", "Data Science", "Senior", ["Python", "SQL"], ["Liderazgo"])]
        lote = [{'id': i, 'puesto': r[0], 'empresa': 'Empresa Demo', 'especialidad': r[1], 'jerarquia': r[2], 'hard_skills': r[3], 'soft_skills': r[4]} for i, r in enumerate(roles * 20)]
        df = pd.DataFrame(lote)
    
    df['link'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(str(r['puesto']) + ' ' + str(r['empresa']))}&location=Peru", axis=1)
    return df

df_raw = obtener_data()

# UI
st.title("💼 DataCareer AI")
filtro = st.sidebar.selectbox("Especialidad Funcional", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
df_f = df_raw if filtro == "Todos" else df_raw[df_raw['especialidad'] == filtro]

tab1, tab2 = st.tabs(["📊 Inteligencia de Mercado", "🔍 Evaluador de CV"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Jerarquías (Descendente)")
        # Forzar orden descendente: count().sort_values(ascending=False)
        st.bar_chart(df_f['jerarquia'].value_counts().sort_values(ascending=False))
        st.subheader("Hard Skills")
        st.bar_chart(pd.Series([s for sub in df_f['hard_skills'] for s in sub]).value_counts().sort_values(ascending=False), horizontal=True)
    with col2:
        st.subheader("Especialidad (Descendente)")
        st.bar_chart(df_f['especialidad'].value_counts().sort_values(ascending=False), horizontal=True)
        st.subheader("Soft Skills")
        st.bar_chart(pd.Series([s for sub in df_f['soft_skills'] for s in sub]).value_counts().sort_values(ascending=False), horizontal=True)
    
    st.markdown("### Registro Completo de Ofertas")
    st.dataframe(df_f[['puesto', 'empresa', 'especialidad', 'jerarquia', 'link']], use_container_width=True)

with tab2:
    archivo = st.file_uploader("Sube tu CV (PDF)", type="pdf")
    if archivo:
        try:
            texto = "".join([p.extract_text() for p in PdfReader(archivo).pages])
            client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            
            res = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=f"Analiza CV: {texto[:3000]} contra: {df_f.to_json()}",
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=List[Evaluacion])
            )
            
            df_match = pd.merge(df_f, pd.DataFrame(json.loads(res.text)), left_on='id', right_on='id_interno')
            
            for _, row in df_match.sort_values('match_score', ascending=False).iterrows():
                st.markdown(f"""<div class='match-card'>
                    <h4>{row['puesto']} - {row['empresa']} <span class='match-badge'>{row['match_score']}%</span></h4>
                    <p>{row['coincidencias']}</p>
                    <a href='{row['link']}' target='_blank'>Postular</a>
                </div>""", unsafe_allow_html=True)
        except Exception as e:
            st.error("Error al procesar el CV. Verifica que sea un PDF de texto, no una imagen.")
