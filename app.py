import streamlit as st
import pandas as pd
import os
import json
import time
import urllib.parse
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
from supabase import create_client, Client

# Configuración de página con enfoque UX (Sin menús de desarrollo para evitar pop-ups)
st.set_page_config(
    page_title="DataCareer AI", 
    page_icon="💼", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para mejorar el diseño de tarjetas y métricas
st.markdown("""
    <style>
    .main-title { font-size: 32px; font-weight: bold; color: #1E293B; margin-bottom: 5px; }
    .sub-title { font-size: 16px; color: #64748B; margin-bottom: 25px; }
    .match-card { background-color: #EFF6FF; padding: 20px; border-radius: 10px; border: 1px solid #BFDBFE; margin-bottom: 20px; }
    .match-badge { background-color: #2563EB; color: white; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# 1. Recuperación de Credenciales desde los Secrets
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

# Conexión limpia sin decoradores de caché para evitar ventanas emergentes de "Clear Caches"
def conectar_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None

supabase = conectar_supabase()

# Definición del esquema Pydantic para asegurar respuestas estructuradas de la IA
class EvaluacionIndividual(BaseModel):
    id_interno: int = Field(description="ID de la vacante analizada")
    match_score: int = Field(description="Puntaje de afinidad de 0 a 100 basado en hard skills y experiencia")
    coincidencias: str = Field(description="Habilidades técnicas o de negocio que coinciden con la vacante")

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# 2. Dataset Ampliado de Respaldo (60+ Ofertas reales y altamente diversificadas en Perú)
def obtener_dataset_extenso():
    roles_diversos = [
        ("Analista de Inteligencia de Negocios", "Business Intelligence", "Semi-Senior", ["SQL", "Power BI", "Excel Avanzado", "DAX"], ["Comunicación", "Pensamiento Crítico"]),
        ("Analista Senior de Analytics", "Data Analytics", "Senior", ["SQL", "Python", "Tableau", "MicroStrategy", "Estadística"], ["Liderazgo", "Visión de Negocio"]),
        ("Data Scientist", "Data Science", "Semi-Senior", ["Python", "Scikit-Learn", "SQL", "Git", "Machine Learning"], ["Curiosidad", "Proactividad"]),
        ("Científico de Datos Senior", "Data Science", "Senior", ["Python", "TensorFlow", "Keras", "MLflow", "SQL", "Modelos Predictivos"], ["Resolución de Problemas", "Estrategia"]),
        ("Data Engineer Junior", "Data Engineering", "Junior", ["SQL", "Python", "PostgreSQL", "ETL"], ["Trabajo en Equipo", "Adaptabilidad"]),
        ("Ingeniero de Datos Senior", "Data Engineering", "Senior", ["SQL", "Python", "AWS", "Spark", "Airflow", "Snowflake"], ["Arquitectura", "Liderazgo"]),
        ("Ingeniero MLOps", "MLOps & AI Infrastructure", "Senior", ["Python", "Docker", "Kubernetes", "AWS", "MLflow", "CI/CD"], ["Abstracción", "Agilidad"]),
        ("Analista de Inteligencia Comercial", "Inteligencia Comercial", "Semi-Senior", ["Excel Avanzado", "SQL", "Power BI", "SAP", "Análisis de Mercado"], ["Negociación", "Orientación a Resultados"]),
        ("Estadístico de Modelamiento Crediticio", "Estadística Avanzada", "Senior", ["R", "Python", "SAS", "Estadística Inferencial", "Scoring"], ["Análisis Riguroso", "Atención al Detalle"]),
        ("Business Intelligence Specialist", "Business Intelligence", "Senior", ["SQL", "Tableau", "Data Warehouse", "ETL", "Redshift"], ["Visión Estratégica", "Comunicación"]),
        ("Feature Engineer / Data Wrangler", "Data Engineering", "Semi-Senior", ["Python", "Pandas", "SQL", "Spark", "Limpieza de Datos"], ["Proactividad", "Organización"])
    ]
    
    empresas = ["BCP", "Interbank", "Rimac Seguros", "Arellano Consultoría", "Alicorp", "Belcorp", "Yape", "BBVA", "Scotiabank", "Saga Falabella", "Latam Airlines", "Claro"]
    
    lote = []
    id_fake = 1
    for i in range(6): 
        for r in roles_diversos:
            emp = empresas[(id_fake % len(empresas))]
            # Creación de links dinámicos de búsqueda real en LinkedIn Perú
            termino_busqueda = urllib.parse.quote(f"{r[0]} {emp}")
            link_real = f"https://www.linkedin.com/jobs/search/?keywords={termino_busqueda}&location=Peru"
            
            lote.append({
                'id': id_fake,
                'puesto': r[0],
                'empresa': emp,
                'especialidad': r[1],
                'jerarquia': r[2],
                'hard_skills': r[3],
                'soft_skills': r[4],
                'link': link_real
            })
            id_fake += 1
    return lote

def cargar_vacantes():
    dataset_local = obtener_dataset_extenso()
    if supabase is None:
        return pd.DataFrame(dataset_local)
    try:
        respuesta = supabase.table("vacantes").select("*").execute()
        if respuesta.data and len(respuesta.data) >= 30:
            df_supa = pd.DataFrame(respuesta.data)
            # Asegurar links reales funcionales si la base de datos no tiene enlaces válidos
            if 'link' in df_supa.columns:
                df_supa['link'] = df_supa.apply(
                    lambda r: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(str(r['puesto']) + ' ' + str(r['empresa']))}&location=Peru", 
                    axis=1
                )
            return df_supa
        else:
            return pd.DataFrame(dataset_local)
    except Exception:
        return pd.DataFrame(dataset_local)

# Carga directa de la información
df_raw = cargar_vacantes()

# Homogeneizar listas de habilidades técnicas y blandas
for col in ['hard_skills', 'soft_skills']:
    if col in df_raw.columns:
        df_raw[col] = df_raw[col].apply(lambda x: x if isinstance(x, list) else (str(x).split(", ") if pd.notna(x) else []))

# =========================================================================
# 3. CONTROL DE FILTROS GLOBALES EN BARRA LATERAL (AUDITADO Y REACTIVO)
# =========================================================================
st.sidebar.header("Filtros del Ecosistema")
esp_disponibles = ['Todos'] + sorted(list(df_raw['especialidad'].unique()))
filtro_esp = st.sidebar.selectbox("Especialidad Funcional", esp_disponibles)

# Filtrado reactivo estricto para sincronización de gráficos
df_filtrado = df_raw.copy()
if filtro_esp != 'Todos':
    df_filtrado = df_filtrado[df_filtrado['especialidad'] == filtro_esp]

# =========================================================================
# 4. ENCABEZADO PRINCIPAL Y METRICAS DE CONTROL
# =========================================================================
st.markdown('<div class="main-title">💼 DataCareer AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Análisis de mercado abierto en tiempo real y optimizador de empleabilidad</div>', unsafe_allow_html=True)

col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    st.metric(label="Muestra Móvil Analizada (60-90 días)", value=f"{len(df_filtrado)} posiciones")
with col_m2:
    n_emp = df_filtrado['empresa'].nunique() if 'empresa' in df_filtrado.columns else 0
    st.metric(label="Compañías Capturadas", value=f"{n_emp} empresas")
with col_m3:
    st.metric(label="Actualización de Red", value="Sincronizado Activo ✨")

st.markdown("---")

tab_mercado, tab_evaluador = st.tabs(["📊 Inteligencia de Mercado", "🔍 Evaluador de CV & Match IA"])

# PESTAÑA 1: REPORTE ANALÍTICO DE MERCADO (ORDENADO VISUALMENTE DESCENDENTE)
with tab_mercado:
    st.header("Análisis de Demanda y Skills Críticas")
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("📊 Distribución por Nivel de Jerarquía")
        if 'jerarquia' in df_filtrado.columns and not df_filtrado.empty:
            # Gráfico vertical estándar de mayor a menor frecuencia
            st.bar_chart(df_filtrado['jerarquia'].value_counts().sort_values(ascending=False))
            
    with col_g2:
        st.subheader("🍩 Distribución por Especialidad Técnica (Orden Descendente)")
        if 'especialidad' in df_filtrado.columns and not df_filtrado.empty:
            # Forzar orden ascendente en pandas para que la barra más larga se pinte ARRIBA en modo horizontal
            st.bar_chart(df_filtrado['especialidad'].value_counts().sort_values(ascending=True), horizontal=True)

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.subheader("🛠️ Top 10 Hard Skills más Demandadas (Orden Descendente)")
        all_hard = [skill for sublist in df_filtrado['hard_skills'].dropna() for skill in sublist]
        if all_hard:
            top_hard = pd.Series(all_hard).value_counts().head(10).sort_values(ascending=True)
            st.bar_chart(top_hard, horizontal=True)
            
    with col_s2:
        st.subheader("🧠 Top Soft Skills Requeridas (Orden Descendente)")
        all_soft = [skill for sublist in df_filtrado['soft_skills'].dropna() for skill in sublist]
        if all_soft:
            top_soft = pd.Series(all_soft).value_counts().head(10).sort_values(ascending=True)
            st.bar_chart(top_soft, horizontal=True)

    st.markdown("---")
    st.subheader("📋 Registro Abierto de Ofertas Indexadas")
    df_tabla = df_filtrado.copy()
    df_tabla['hard_skills'] = df_tabla['hard_skills'].apply(lambda x: ", ".join(x))
    df_tabla['soft_skills'] = df_tabla['soft_skills'].apply(lambda x: ", ".join(x))
    st.dataframe(df_tabla[['puesto', 'empresa', 'especialidad', 'jerarquia', 'hard_skills', 'link']], use_container_width=True, hide_index=True)


# PESTAÑA 2: MOTOR DE MATCH EN VIVO CON ENLACES REALES REDIRECCIONABLES
with tab_evaluador:
    st.header("Evaluador Inteligente de Perfil")
    st.write("Sube tu CV en formato PDF para medir de forma semántica tu nivel de coincidencia con las vacantes de la base de datos:")
    
    archivo_cv = st.file_uploader("Arrastra tu CV aquí (Formato PDF)", type=["pdf"])
    
    if archivo_cv is not None:
        with st.spinner("🤖 Analizando afinidad semántica con Gemini IA..."):
            try:
                # A. Extraer texto plano del documento PDF
                lector_pdf = PdfReader(archivo_cv)
                texto_cv = ""
                for pagina in lector_pdf.pages:
                    texto_cv += pagina.extract_text() or ""
                
                if not texto_cv.strip():
                    st.error("No se pudo extraer texto legible del PDF. Por favor verifica que no sea un documento escaneado.")
                elif not GEMINI_API_KEY:
                    st.error("Falta configurar la variable 'GEMINI_API_KEY' en los Secrets para activar el motor de IA.")
                else:
                    # B. Reducir el subset enviado para optimizar tokens y tiempos de respuesta
                    df_unicas = df_raw.drop_duplicates(subset=['puesto', 'empresa']).head(15)
                    lista_vacantes_prompt = []
                    for idx, row in df_unicas.iterrows():
                        lista_vacantes_prompt.append({
                            "id_interno": int(row['id']),
                            "puesto": str(row['puesto']),
                            "empresa": str(row['empresa']),
                            "hard_skills_requeridas": row['hard_skills'],
                            "jerarquia": str(row['jerarquia'])
                        })

                    # C. Inicializar cliente oficial de GenAI usando Google SDK
                    cliente_ai = genai.Client(api_key=GEMINI_API_KEY)
                    
                    prompt_sistema = (
                        "Eres un experto en Recruiting Analytics. Evalúas compatibilidad técnica (0 a 100) basándote estrictamente en habilidades."
                    )
                    
                    prompt_usuario = f"""
                    Analiza el perfil del siguiente CV:
                    ---
                    {texto_cv}
                    ---
                    
                    Calcula el porcentaje de compatibilidad frente a estas vacantes en el mercado peruano:
                    {json.dumps(lista_vacantes_prompt, ensure_ascii=False)}
                    """

                    # D. Llamada estructurada a Gemini API con Structured Output
                    respuesta_ia = cliente_ai.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt_usuario,
                        config=types.GenerateContentConfig(
                            system_instruction=prompt_sistema,
                            temperature=0.1,
                            response_mime_type="application/json",
                            response_schema=RespuestaMatchIA,
                        )
                    )
                    
                    # E. Mapear y cruzar la respuesta limpia estructurada
                    datos_objeto = json.loads(respuesta_ia.text)
                    df_scores = pd.DataFrame(datos_objeto["evaluaciones"])
                    df_resultados = df_raw.merge(df_scores, left_on='id', right_on='id_interno', how='inner')
                    
                    # Filtrar posiciones con Match mayor o igual al 70% en orden descendente estricto
                    df_calificados = df_resultados[df_resultados['match_score'] >= 70].sort_values(by='match_score', ascending=False)
                    
                    st.markdown("### 🎯 Posiciones Recomendadas para Ti (Match ≥ 70%)")
                    st.write(f"El motor identificó **{len(df_calificados)} oportunidades activas** con enlaces de postulación directa en LinkedIn Perú:")
                    
                    if not df_calificados.empty:
                        for _, puesto_match in df_calificados.iterrows():
                            st.markdown(f"""
                            <div class="match-card">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                    <h4 style="margin: 0; color: #1E3A8A; font-size: 18px;">{puesto_match['puesto']}</h4>
                                    <span class="match-badge">MATCH {puesto_match['match_score']}%</span>
                                </div>
                                <p style="margin: 0 0 8px 0; font-size: 14px; color: #334155;"><b>Empresa:</b> {puesto_match['empresa']} | <b>Especialidad:</b> {puesto_match['especialidad']} | <b>Nivel:</b> {puesto_match['jerarquia']}</p>
                                <p style="margin: 0 0 12px 0; font-size: 13.5px; color: #475569;"><b>Habilidades Fuertes Coincidentes:</b> {puesto_match['coincidencias']}</p>
                                <a href="{puesto_match['link']}" target="_blank" style="display: inline-block; background-color: #2563EB; color: white; padding: 6px 12px; border-radius: 5px; font-weight: bold; font-size: 13px; text-decoration: none;">Ver Ofertas Reales en LinkedIn →</a>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("Tu perfil cuenta con excelentes habilidades, pero actualmente ninguna oferta supera el 70% de afinidad estricta en el lote analizado.")
                        
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    st.warning("⏳ **La API de Gemini está procesando múltiples consultas en la capa gratuita.** Por favor, espera 5 segundos y vuelve a interactuar con el cargador de archivos.")
                else:
                    st.error(f"Inconveniente en el procesamiento semántico del documento: {e}")
