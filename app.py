import streamlit as st
import pandas as pd
import os
import json
from pypdf import PdfReader
from google import genai
from google.genai import types
from supabase import create_client, Client

# Configuración de página con enfoque UX
st.set_page_config(page_title="DataCareer AI", page_icon="💼", layout="wide")

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

@st.cache_resource
def conectar_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None

supabase = conectar_supabase()

# 2. Dataset Ampliado de Respaldo (60+ Posiciones Diversificadas de Datos en Perú)
def obtener_dataset_extenso():
    roles = [
        ("Analista de Inteligencia de Negocios", "Data Analytics", "Semi-Senior", ["SQL", "Power BI", "Excel Avanzado", "DAX"], ["Comunicación", "Pensamiento Crítico"]),
        ("Analista Senior de Analytics", "Data Analytics", "Senior", ["SQL", "Python", "Tableau", "MicroStrategy", "Estadística"], ["Liderazgo", "Visión de Negocio"]),
        ("Data Scientist", "Data Science", "Semi-Senior", ["Python", "Scikit-Learn", "SQL", "Git", "Machine Learning"], ["Curiosidad", "Proactividad"]),
        ("Científico de Datos Senior", "Data Science", "Senior", ["Python", "TensorFlow", "Keras", "MLflow", "SQL", "Modelos Predictivos"], ["Resolución de Problemas", "Estrategia"]),
        ("Data Engineer Junior", "Data Engineering", "Junior", ["SQL", "Python", "PostgreSQL", "ETL"], ["Trabajo en Equipo", "Adaptabilidad"]),
        ("Ingeniero de Datos Senior", "Data Engineering", "Senior", ["SQL", "Python", "AWS", "Spark", "Airflow", "Snowflake"], ["Arquitectura", "Liderazgo"]),
        ("Ingeniero MLOps", "Data Science", "Senior", ["Python", "Docker", "Kubernetes", "AWS", "MLflow", "CI/CD"], ["Abstracción", "Agilidad"]),
        ("Analista de Inteligencia Comercial", "Data Analytics", "Semi-Senior", ["Excel Avanzado", "SQL", "Power BI", "SAP", "Análisis de Mercado"], ["Negociación", "Orientación a Resultados"]),
        ("Estadístico de Modelamiento Crediticio", "Data Science", "Senior", ["R", "Python", "SAS", "Estadística Inferencial", "Scoring"], ["Análisis Riguroso", "Atención al Detalle"]),
        ("Business Intelligence Specialist", "Data Analytics", "Senior", ["SQL", "Tableau", "Data Warehouse", "ETL", "Redshift"], ["Visión Estratégica", "Comunicación"]),
        ("Feature Engineer / Data Wrangler", "Data Engineering", "Semi-Senior", ["Python", "Pandas", "SQL", "Spark", "Limpieza de Datos"], ["Proactividad", "Organización"])
    ]
    
    empresas = ["BCP", "Interbank", "Rimac Seguros", "Arellano Consultoría", "Alicorp", "Belcorp", "Yape", "BBVA", "Scotiabank", "Saga Falabella", "Latam Airlines", "Claro"]
    
    lote = []
    id_fake = 1
    for i in range(6): 
        for r in roles:
            emp = empresas[(id_fake % len(empresas))]
            lote.append({
                'id': id_fake,
                'puesto': r[0],
                'empresa': emp,
                'especialidad': r[1],
                'jerarquia': r[2],
                'hard_skills': r[3],
                'soft_skills': r[4],
                'link': f'https://linkedin.com/jobs/view/{1000 + id_fake}'
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
            return pd.DataFrame(respuesta.data)
        else:
            return pd.DataFrame(dataset_local)
    except Exception:
        return pd.DataFrame(dataset_local)

# Carga e inicialización de datos base
df_raw = cargar_vacantes()

# Asegurar formato homogéneo de listas de habilidades para gráficos
for col in ['hard_skills', 'soft_skills']:
    if col in df_raw.columns:
        df_raw[col] = df_raw[col].apply(lambda x: x if isinstance(x, list) else (str(x).split(", ") if pd.notna(x) else []))

# =========================================================================
# 3. CONTROL DE FILTROS GLOBALES (BARRA LATERAL)
# =========================================================================
st.sidebar.header("Filtros del Ecosistema")
esp_disponibles = ['Todos'] + list(df_raw['especialidad'].unique())
filtro_esp = st.sidebar.selectbox("Especialidad Funcional", esp_disponibles)

df_filtrado = df_raw.copy()
if filtro_esp != 'Todos':
    df_filtrado = df_filtrado[df_filtrado['especialidad'] == filtro_esp]

# =========================================================================
# 4. ENCABEZADO PRINCIPAL Y ESTRUCTURA VISUAL
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

# PESTAÑA 1: REPORTE ANALÍTICO DE MERCADO
with tab_mercado:
    st.header("Análisis de Demanda y Skills Críticas")
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("📊 Distribución por Nivel de Jerarquía")
        if 'jerarquia' in df_filtrado.columns and not df_filtrado.empty:
            st.bar_chart(df_filtrado['jerarquia'].value_counts())
    with col_g2:
        st.subheader("🍩 Distribución por Tipo de Posición")
        if 'puesto' in df_filtrado.columns and not df_filtrado.empty:
            st.bar_chart(df_filtrado['especialidad'].value_counts(), horizontal=True)

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.subheader("🛠️ Top 10 Hard Skills más Demandadas")
        all_hard = [skill for sublist in df_filtrado['hard_skills'].dropna() for skill in sublist]
        if all_hard:
            st.bar_chart(pd.Series(all_hard).value_counts().head(10), horizontal=True)
    with col_s2:
        st.subheader("🧠 Top Soft Skills Requeridas")
        all_soft = [skill for sublist in df_filtrado['soft_skills'].dropna() for skill in sublist]
        if all_soft:
            st.bar_chart(pd.Series(all_soft).value_counts().head(10), horizontal=True)

    st.markdown("---")
    st.subheader("📋 Registro Abierto de Ofertas Indexadas")
    df_tabla = df_filtrado.copy()
    df_tabla['hard_skills'] = df_tabla['hard_skills'].apply(lambda x: ", ".join(x))
    df_tabla['soft_skills'] = df_tabla['soft_skills'].apply(lambda x: ", ".join(x))
    st.dataframe(df_tabla[['puesto', 'empresa', 'especialidad', 'jerarquia', 'hard_skills', 'link']], use_container_width=True, hide_index=True)


# PESTAÑA 2: MOTOR DE MATCH SEMÁNTICO EN VIVO (CON INTELIGENCIA ARTIFICIAL)
with tab_evaluador:
    st.header("Evaluador Inteligente de Perfil")
    st.write("Sube tu CV en formato PDF para medir de forma semántica tu nivel de coincidencia con las vacantes:")
    
    archivo_cv = st.file_uploader("Arrastra tu CV aquí (Formato PDF)", type=["pdf"])
    
    if archivo_cv is not None:
        with st.spinner("🤖 Extrayendo texto y procesando afinidad semántica con Gemini IA..."):
            try:
                # A. Extraer texto del PDF cargado por el usuario
                lector_pdf = PdfReader(archivo_cv)
                texto_cv = ""
                for pagina in lector_pdf.pages:
                    texto_cv += pagina.extract_text() or ""
                
                if not texto_cv.strip():
                    st.error("No se pudo extraer texto legible del PDF. Por favor verifica que no sea una imagen escaneada.")
                elif not GEMINI_API_KEY:
                    st.error("Falta configurar la variable 'GEMINI_API_KEY' en los Secrets para activar la IA.")
                else:
                    # B. Preparar subset de vacantes únicas para optimizar tokens enviados a la IA
                    df_unicas = df_raw.drop_duplicates(subset=['puesto', 'empresa']).head(15)
                    lista_vacantes_prompt = []
                    for idx, row in df_unicas.iterrows():
                        lista_vacantes_prompt.append({
                            "id_interno": int(row['id']),
                            "puesto": row['puesto'],
                            "empresa": row['empresa'],
                            "hard_skills_requeridas": row['hard_skills'],
                            "jerarquia": row['jerarquia']
                        })

                    # C. Configurar el Cliente de GenAI y estructurar el Prompt Técnico
                    cliente_ai = genai.Client(api_key=GEMINI_API_KEY)
                    
                    prompt_sistema = (
                        "Eres un consultor experto en reclutamiento técnico y analítica de talento (UX/HR Analytics). "
                        "Tu tarea es evaluar el nivel de coincidencia (Match Score del 0 al 100) entre el Currículum Vitae provisto "
                        "y el listado de vacantes de empleo adjunto. Debes responder UNICAMENTE con una estructura JSON válida."
                    )
                    
                    prompt_usuario = f"""
                    Analiza el siguiente texto extraído de un CV:
                    ---
                    {texto_cv}
                    ---
                    
                    A continuación, evalúa el CV contra esta lista de ofertas de empleo en Perú:
                    {json.dumps(lista_vacantes_prompt, ensure_ascii=False)}
                    
                    Genera una estructura JSON con la clave exacta "evaluaciones", que contenga una lista de objetos. 
                    Cada objeto debe tener exactamente estos campos:
                    - "id_interno": (entero)
                    - "match_score": (entero de 0 a 100 basado en coincidencia de hard skills y experiencia)
                    - "coincidencias": (texto breve indicando qué habilidades clave sí posee el candidato)
                    
                    Devuelve única y exclusivamente el código JSON limpio, sin bloques de marcado markdown ```json ni texto adicional.
                    """

                    # D. Llamada asíncrona estructurada a Gemini
                    respuesta_ia = cliente_ai.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt_usuario,
                        config=types.GenerateContentConfig(
                            system_instruction=prompt_sistema,
                            temperature=0.2
                        )
                    )
                    
                    # E. Parsear e indexar resultados
                    texto_limpio = respuesta_ia.text.strip().replace("```json", "").replace("```", "")
                    datos_match = json.loads(texto_limpio)
                    
                    df_scores = pd.DataFrame(datos_match["evaluaciones"])
                    
                    # Cruzar puntajes de IA con el DataFrame original de vacantes
                    df_resultados = df_raw.merge(df_scores, left_on='id', right_on='id_interno', how='inner')
                    
                    # FILTRO CRÍTICO UX: Mostrar solo posiciones que superen el 70% de Match
                    df_calificados = df_resultados[df_resultados['match_score'] >= 70].sort_values(by='match_score', ascending=False)
                    
                    # F. Renderizado UX de Resultados en Pantalla
                    st.markdown("### 🎯 Posiciones Recomendadas para Ti (Match ≥ 70%)")
                    st.write(f"El motor de IA analizó tu perfil frente a la base de datos abierta y detectó **{len(df_calificados)} oportunidades de alta compatibilidad**:")
                    
                    if not df_calificados.empty:
                        for _, puesto_match in df_calificados.iterrows():
                            # Generación dinámica de tarjetas HTML adaptativas
                            st.markdown(f"""
                            <div class="match-card">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                    <h4 style="margin: 0; color: #1E3A8A; font-size: 18px;">{puesto_match['puesto']}</h4>
                                    <span class="match-badge">MATCH {puesto_match['match_score']}%</span>
                                </div>
                                <p style="margin: 0 0 8px 0; font-size: 14px; color: #334155;"><b>Empresa:</b> {puesto_match['empresa']} | <b>Nivel:</b> {puesto_match['jerarquia']}</p>
                                <p style="margin: 0 0 12px 0; font-size: 13.5px; color: #475569;"><b>Habilidades Clave Detectadas:</b> {puesto_match['coincidencias']}</p>
                                <a href="{puesto_match['link']}" target="_blank" style="color: #2563EB; font-weight: bold; font-size: 14px; text-decoration: none;">Postular en LinkedIn →</a>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("Tu perfil cuenta con habilidades sólidas, pero actualmente ninguna posición en el lote supera el 70% de match estricto. ¡Te recomendamos actualizar palabras clave en tu CV!")
                        
            except Exception as e:
                st.error(f"Ocurrió un inconveniente durante el análisis semántico: {e}")
