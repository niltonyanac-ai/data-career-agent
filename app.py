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

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="DataCareer AI", page_icon="💼", layout="wide")

st.markdown("""
    <style>
    .match-card { background-color: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 15px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
    .match-badge { background-color: #2563eb; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 13px; float: right; }
    .job-title { color: #1e293b; margin-top: 0; margin-bottom: 5px; font-size: 1.2rem; }
    .company-name { color: #64748b; font-weight: 500; margin-bottom: 10px; font-size: 1rem; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. ESQUEMAS DE INTELIGENCIA ARTIFICIAL
# -----------------------------------------------------------------------------
class EvaluacionIndividual(BaseModel):
    id_interno: int = Field(description="El ID exacto de la vacante evaluada")
    match_score: int = Field(description="Porcentaje de 0 a 100 de compatibilidad")
    coincidencias: str = Field(description="Breve justificación de las habilidades coincidentes")

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# -----------------------------------------------------------------------------
# 3. MOTOR DE DATOS (Forzado a simulación local para visualizar multiespecialidad)
# -----------------------------------------------------------------------------
def obtener_data():
    # CONEXIÓN A SUPABASE COMENTADA PARA FORZAR DATOS DE PRUEBA
    # try:
    #     supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    #     res = supabase.table("vacantes").select("*").execute()
    #     df = pd.DataFrame(res.data)
    # except:
    
    # Respaldo de alta densidad (Asegura volumen y diversidad sin colapsar RAM)
    roles = [
        ("Data Scientist", "Data Science", "Senior", ["Python", "SQL", "Machine Learning"], ["Liderazgo", "Comunicación"]),
        ("Data Engineer", "Data Engineering", "Semi-Senior", ["Spark", "AWS", "Python"], ["Proactividad", "Trabajo en equipo"]),
        ("Analista BI", "Business Intelligence", "Junior", ["Power BI", "SQL", "Excel"], ["Comunicación", "Atención al detalle"]),
        ("Data Analyst", "Data Analytics", "Senior", ["Tableau", "SQL", "Python"], ["Visión de Negocio", "Análisis Crítico"]),
        ("Ingeniero MLOps", "MLOps", "Senior", ["Docker", "Kubernetes", "AWS"], ["Agilidad", "Resolución de problemas"]),
        ("Analista Comercial", "Inteligencia Comercial", "Semi-Senior", ["Excel", "SQL", "Power BI"], ["Negociación", "Estrategia"]),
        ("Especialista IA", "Data Science", "Senior", ["TensorFlow", "PyTorch", "Python"], ["Estrategia", "Innovación"]),
        ("Arquitecto de Datos", "Data Engineering", "Senior", ["Snowflake", "ETL", "GCP"], ["Arquitectura", "Liderazgo"]),
        ("Desarrollador BI", "Business Intelligence", "Senior", ["MicroStrategy", "SQL", "DAX"], ["Comunicación", "Gestión de tiempo"]),
        ("Data Wrangler", "Data Engineering", "Junior", ["Pandas", "Python", "SQL"], ["Organización", "Paciencia"]),
        ("Analista Estadístico", "Estadística Avanzada", "Senior", ["R", "SAS", "Python"], ["Análisis Riguroso", "Lógica"])
    ]
    
    lote = []
    id_counter = 1
    for i in range(15):  # 15 iteraciones x 11 roles = 165 registros
        for r in roles:
            lote.append({
                'id': id_counter,  # ID único garantizado como entero
                'puesto': r[0],
                'empresa': f"Corporación Data Latam {i+1}",
                'especialidad': r[1],
                'jerarquia': r[2],
                'hard_skills': r[3],
                'soft_skills': r[4]
            })
            id_counter += 1
    df = pd.DataFrame(lote)

    # Transformaciones Críticas para Interfaz
    for col in ['hard_skills', 'soft_skills']:
        df[col] = df[col].apply(lambda x: x.split(", ") if isinstance(x, str) else x)
    
    # Generación del Link Real (Nunca correlativo, basado en texto web-safe)
    df['link'] = df.apply(lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(str(r['puesto']) + ' ' + str(r['empresa']))}&location=Peru", axis=1)
    
    return df

df_raw = obtener_data()

# -----------------------------------------------------------------------------
# 4. BARRA LATERAL Y FILTROS ESTRUCTURALES
# -----------------------------------------------------------------------------
st.title("💼 DataCareer AI")
st.sidebar.header("Filtros del Mercado")

lista_especialidades = ["Todos"] + sorted(list(df_raw['especialidad'].unique()))
filtro = st.sidebar.selectbox("Especialidad Funcional", lista_especialidades)

df_f = df_raw if filtro == "Todos" else df_raw[df_raw['especialidad'] == filtro]

# -----------------------------------------------------------------------------
# 5. PESTAÑAS Y RENDERIZADO VISUAL
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["📊 Inteligencia de Mercado", "🔍 Evaluador Inteligente de CV"])

# PESTAÑA 1: GRÁFICOS ORDENADOS Y LISTADO INFERIOR
with tab1:
    st.markdown(f"### Análisis de {len(df_f)} ofertas activas")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Jerarquías (Descendente)")
        st.bar_chart(df_f['jerarquia'].value_counts().sort_values(ascending=False))
        
        st.subheader("Hard Skills Más Demandadas")
        hard_skills_flat = [skill for sublist in df_f['hard_skills'] if isinstance(sublist, list) for skill in sublist]
        if hard_skills_flat:
            top_hard = pd.Series(hard_skills_flat).value_counts().head(10).sort_values(ascending=True)
            st.bar_chart(top_hard, horizontal=True)

    with col2:
        st.subheader("Especialidad (Descendente)")
        st.bar_chart(df_f['especialidad'].value_counts().sort_values(ascending=True), horizontal=True)
        
        st.subheader("Soft Skills Más Demandadas")
        soft_skills_flat = [skill for sublist in df_f['soft_skills'] if isinstance(sublist, list) for skill in sublist]
        if soft_skills_flat:
            top_soft = pd.Series(soft_skills_flat).value_counts().head(10).sort_values(ascending=True)
            st.bar_chart(top_soft, horizontal=True)

    st.markdown("---")
    st.subheader("📋 Registro Completo de Oportunidades")
    
    df_visor = df_f[['puesto', 'empresa', 'especialidad', 'jerarquia', 'hard_skills', 'link']].copy()
    df_visor['hard_skills'] = df_visor['hard_skills'].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
    
    st.dataframe(
        df_visor,
        column_config={"link": st.column_config.LinkColumn("Enlace LinkedIn")},
        use_container_width=True, 
        hide_index=True
    )

# PESTAÑA 2: MOTOR DE MATCH IA Y ENSAMBLAJE DE LINKS
with tab2:
    st.markdown("### Evaluador Semántico de Empleabilidad")
    archivo = st.file_uploader("Sube tu CV (Formato PDF)", type="pdf")
    
    if archivo:
        with st.spinner("🤖 El agente de IA está analizando tu perfil contra el mercado..."):
            try:
                reader = PdfReader(archivo)
                texto_cv = "".join([pagina.extract_text() for pagina in reader.pages if pagina.extract_text()])
                
                if not texto_cv.strip():
                    st.error("No se detectó texto en el PDF. Por favor, sube un documento que no sea una imagen escaneada.")
                else:
                    cliente_ai = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                    
                    df_prompt = df_f[['id', 'puesto', 'empresa', 'hard_skills']].copy()
                    
                    # EJECUCIÓN DEL LLM: CAMBIO A GEMINI-1.5-FLASH PARA ESTABILIDAD Y EVITAR ERROR 503
                    respuesta_ia = cliente_ai.models.generate_content(
                        model='gemini-1.5-flash', 
                        contents=f"Evalúa la compatibilidad de este CV:\n{texto_cv[:3000]}\n\nContra estas vacantes:\n{df_prompt.to_json(orient='records')}",
                        config=types.GenerateContentConfig(
                            system_instruction="Eres un headhunter técnico. Retorna los resultados en formato JSON exacto según el esquema provisto.",
                            temperature=0.1,
                            response_mime_type="application/json",
                            response_schema=RespuestaMatchIA
                        )
                    )
                    
                    datos_objeto = json.loads(respuesta_ia.text)
                    df_scores = pd.DataFrame(datos_objeto["evaluaciones"])
                    
                    df_resultados_finales = pd.merge(df_f, df_scores, left_on='id', right_on='id_interno', how='inner')
                    
                    df_calificados = df_resultados_finales[df_resultados_finales['match_score'] > 50].sort_values(by='match_score', ascending=False)
                    
                    st.success(f"Se encontraron {len(df_calificados)} oportunidades que hacen match con tu perfil.")
                    
                    for index, row in df_calificados.iterrows():
                        st.markdown(f"""
                        <div class="match-card">
                            <span class="match-badge">Match: {row['match_score']}%</span>
                            <h3 class="job-title">{row['puesto']}</h3>
                            <p class="company-name">{row['empresa']} | Nivel: {row['jerarquia']}</p>
                            <p style="color: #475569; font-size: 0.95rem;"><strong>Coincidencias clave:</strong> {row['coincidencias']}</p>
                            <a href="{row['link']}" target="_blank" style="text-decoration: none; background-color: #0f172a; color: white; padding: 8px 16px; border-radius: 6px; font-size: 0.9rem; font-weight: 500; display: inline-block; margin-top: 5px;">Postular en LinkedIn Perú</a>
                        </div>
                        """, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Se produjo un error durante el análisis de la Inteligencia Artificial. Asegúrese de que el PDF sea legible y reintente. Detalles técnicos: {str(e)}")
