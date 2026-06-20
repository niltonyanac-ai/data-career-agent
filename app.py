import os
import json
import random
import hashlib
import threading
import re
import pandas as pd
import altair as alt
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel, Field
from pypdf import PdfReader
from supabase import create_client, Client
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import streamlit as st
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions

# =====================================================================
# 1. CONFIGURACIÓN DE VARIABLES DE ENTORNO Y SUPABASE (BACKEND)
# =====================================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "TU_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "TU_SUPABASE_KEY")

def generar_mock_ofertas_representativas():
    """Genera una muestra estadística robusta de vacantes estructuradas en Data, BI e IA"""
    roles = ["Data Scientist", "Analista de BI", "Data Engineer", "AI Engineer", "Gerente de Analítica", "Data Analyst"]
    empresas = ["BCP", "Interbank", "Rímac", "Alicorp", "Belcorp", "Inetum", "NTT DATA", "Globant", "Scotiabank", "Mindrift"]
    paises = ["Perú", "Colombia", "Chile", "México", "Remoto Latam"]
    
    jerarquias = [
        "Practicante / Asistente", 
        "Analista Junior", 
        "Analista / Profesional", 
        "Analista Senior / Especialista", 
        "Líder / Jefe", 
        "Gerente / Head"
    ]
    
    especialidades = [
        "Data Science", 
        "Business Intelligence", 
        "Data Engineering", 
        "Artificial Intelligence", 
        "Data Management",
        "Data Analytics"
    ]
    
    pool_hard_skills = {
        "Data Science": ["Python", "R", "Machine Learning", "Scikit-Learn", "SQL", "AWS", "Docker"],
        "Business Intelligence": ["Power BI", "SQL", "Tableau", "ETL", "Excel", "Data Warehouse", "DAX"],
        "Data Engineering": ["Python", "SQL", "Spark", "Airflow", "Snowflake", "Databricks", "AWS", "Azure"],
        "Artificial Intelligence": ["Python", "PyTorch", "TensorFlow", "LLMs", "LangChain", "OpenAI API", "NLP"],
        "Data Management": ["Gobierno de Datos", "Data Quality", "SQL", "Collibra", "Scrum", "KPIs"],
        "Data Analytics": ["Python", "SQL", "Excel", "Estadística Inferencial", "A/B Testing", "Mixpanel"]
    }
    
    pool_soft_skills = ["Comunicación Asertiva", "Liderazgo", "Resolución de Problemas", "Trabajo en Equipo", "Pensamiento Crítico", "Negociación"]
    
    ofertas = []
    for i in range(200):
        esp = random.choice(especialidades)
        rol = random.choice(roles) if esp != "Business Intelligence" else "Analista de BI"
        nivel = random.choice(jerarquias)
        titulo = f"{rol} ({nivel})"
        
        h_skills = random.sample(pool_hard_skills[esp], k=min(4, len(pool_hard_skills[esp])))
        s_skills = random.sample(pool_soft_skills, k=3)
        emp = random.choice(empresas)
        pais = random.choice(paises)
        
        ofertas.append({
            "link_oferta": f"https://www.linkedin.com/jobs/view/simulado-{i+1000}",
            "titulo": titulo,
            "empresa": emp,
            "pais": pais,
            "jerarquia": nivel,
            "especialidad_objetivo": esp,
            "descripcion": f"Buscamos un {titulo} para unirse al equipo de {emp} en {pais}. Requisitos clave: {', '.join(h_skills)}. Capacidad de {', '.join(s_skills)}.",
            "hard_skills": h_skills,
            "soft_skills": s_skills
        })
    return ofertas

def cargar_vacantes_a_supabase():
    if SUPABASE_URL == "TU_SUPABASE_URL":
        print("⚠️ Configura las variables de entorno de Supabase.")
        return
        
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    ofertas = generar_mock_ofertas_representativas()
    
    print(f"Iniciando carga masiva de {len(ofertas)} ofertas indexadas...")
    try:
        respuesta = supabase.table("vacantes").insert(ofertas).execute()
        print(f"¡Procesamiento finalizado con éxito! {len(respuesta.data)} registros nuevos indexados de golpe.")
    except Exception as e:
        print(f"❌ Fallo crítico en la inserción masiva: {str(e)}")


# =====================================================================
# 2. CONFIGURACIÓN DE LA PÁGINA DE STREAMLIT Y ESTILOS UI
# =====================================================================
st.set_page_config(
    page_title="DataCareer AI",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .match-card {
        border: 1px solid #e2e8f0; 
        padding: 20px; 
        border-radius: 10px; 
        margin-bottom: 15px; 
        background-color: #ffffff;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .main-title {
        color: #1e3a8a;
        font-weight: 800;
    }
    .action-link {
        display: inline-block;
        margin-top: 10px;
        padding: 8px 16px;
        background-color: #1e3a8a;
        color: white !important;
        text-decoration: none;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.9em;
    }
    .action-link:hover {
        background-color: #1e40af;
    }
</style>
""", unsafe_allow_html=True)

if "texto_cv_usuario" not in st.session_state:
    st.session_state["texto_cv_usuario"] = ""
if "ats_cache" not in st.session_state:
    st.session_state["ats_cache"] = {}

# 1. Validamos que la variable exista en los Secrets
if "GEMINI_API_KEY" in st.secrets:
    api_key_actual = st.secrets["GEMINI_API_KEY"]
    
    # 2. Control de CX: Evitar que tenga valores por defecto o vacíos
    if api_key_actual in ["", "TU_API_KEY_AQUI", "YOUR_API_KEY"]:
        st.error("⚠️ La API Key de Gemini está vacía o usa el texto por defecto en secrets.toml.")
    else:
        # Configuración oficial
        genai.configure(api_key=api_key_actual)
else:
    st.error("❌ Error Crítico: Falta configurar 'GEMINI_API_KEY' en las credenciales del servidor.")

@st.cache_resource
def obtener_cliente_supabase():
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        try:
            return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        except Exception:
            return None
    return None

class EvaluacionMatch(BaseModel):
    match_score: int = Field(..., description="Porcentaje de match real de 0 a 100 basado estrictamente en el cumplimiento de requisitos.")
    justificacion: str = Field(..., description="Explicación analítica clara detallando por qué cumple o no con el perfil.")
    habilidades_coincidentes: list[str] = Field(..., description="Lista de habilidades que el candidato sí posee.")
    habilidades_faltantes: list[str] = Field(..., description="Lista de tecnologías, herramientas o requisitos ausentes in el CV.")


# =====================================================================
# 3. CAPA DE INTELIGENCIA Y PROCESAMIENTO (BACKEND DEL APLICATIVO)
# =====================================================================
def normalizar_jerarquia(texto):
    if pd.isna(texto) or texto is None: 
        return "3. Analista / Profesional"
    t = str(texto).lower().strip()
    if any(x in t for x in ["practicante", "intern", "trainee", "pasantia", "becario", "pre profesional", "pro profesional"]): 
        return "1. Practicante / Trainee"
    if any(x in t for x in ["gerente", "manager", "head", "director", "chief", "cdo", "cto", "ceo", "vpe", "liderazgo ejecutivo"]): 
        return "6. Gerente / Head"
    if any(x in t for x in ["lider", "líder", "jefe", "jefatura", "lead", "supervisor", "coordinador"]): 
        return "5. Líder / Jefe"
    if any(x in t for x in ["senior", "sr", "especialista", "advanced", "ssr", "expert"]): 
        return "4. Analista Senior / Especialista"
    if any(x in t for x in ["junior", "jr", "asistente", "auxiliar", "entry level"]): 
        return "2. Analista Junior"
    return "3. Analista / Profesional"

def inferir_pais_por_datos(row):
    if pd.notna(row.get('pais')) and str(row.get('pais')).strip() != '' and str(row.get('pais')).lower() != 'nan':
        return str(row.get('pais')).strip()

    link = str(row.get('link_oferta', '')).lower()
    puesto = str(row.get('titulo', '')).lower()
    empresa = str(row.get('empresa', '')).lower()
    
    if any(k in link for k in ['.pe', 'peru']) or 'perú' in puesto or 'peru' in puesto or 'perú' in empresa:
        return 'Perú'
    if any(k in link for k in ['.cl', 'chile']) or 'chile' in puesto or 'chile' in empresa:
        return 'Chile'
    if any(k in link for k in ['.co', 'colombia']) or 'colombia' in puesto or 'colombia' in empresa:
        return 'Colombia'
    if any(k in link for k in ['.ec', 'ecuador']) or 'ecuador' in puesto or 'ecuador' in empresa:
        return 'Ecuador'
    return 'Remoto Latam'

def pre_ranking_ats_vectorial(df, texto_cv):
    if df.empty or not texto_cv.strip():
        return df

    def preprocesar(texto):
        texto = str(texto).lower()
        texto = re.sub(r'[^\w\s]', ' ', texto)
        return texto

    cv_limpio = preprocesar(texto_cv)
    descripciones = df['descripcion'].fillna('').apply(preprocesar).tolist()
    
    textos_totales = [cv_limpio] + descripciones
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(textos_totales)
    
    similitudes = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    
    df_ranked = df.copy()
    df_ranked['_score_vectorial'] = similitudes * 100
    
    return df_ranked.sort_values(by='_score_vectorial', ascending=False).drop(columns=['_score_vectorial'])

def extraer_texto_pdf(archivo_pdf):
    try:
        lector = PdfReader(archivo_pdf)
        texto_completo = []
        for pagina in lector.pages:
            parsed = pagina.extract_text()
            if parsed: texto_completo.append(parsed)
        return "\n".join(texto_completo)
    except Exception as e:
        st.error(f"Error al procesar el archivo PDF: {str(e)}")
        return ""

def evaluar_cv_contra_vacante(args):
    texto_cv = args["texto_cv"]
    fila_vacante = args["fila_vacante"]
    cv_hash = args["cv_hash"]
    
    titulo_puesto = fila_vacante.get('titulo')
    empresa_puesto = fila_vacante.get('empresa') or "Empresa No Especificada"
    link_puesto = fila_vacante.get('link_oferta')
    
    llave_vacante = f"{titulo_puesto}_{empresa_puesto}_{link_puesto}"
    llave_cache = f"{cv_hash}_{llave_vacante}"
    
    if llave_cache in args["cache_dict"]:
        return args["cache_dict"][llave_cache]

    detalles_oferta = f"""
    Título de la Oferta: {titulo_puesto}
    Empresa: {empresa_puesto}
    Especialidad Funcional: {fila_vacante.get('especialidad_objetivo', 'No especificado')}
    Jerarquía Requerida: {fila_vacante.get('jerarquia_limpia', 'No específica')}
    Descripción Detallada del Puesto: {fila_vacante.get('descripcion', 'No especificada')}
    """
    
    prompt_usuario = f"""
    Analiza semánticamente la afinidad del candidato con la vacante descrita.
    Devuelve estrictamente un objeto JSON que cumpla el formato de la clase EvaluacionMatch:
    - match_score: entero de 0 a 100.
    - justificacion: string descriptivo.
    - habilidades_coincidentes: array de strings.
    - habilidades_faltantes: array de strings.

    VACANTE OBJETIVO:
    {detalles_oferta}
    
    CURRÍCULUM VITAE DEL CANDIDATO:
    {texto_cv}
    """
    
    resultado_base = {
        "titulo": titulo_puesto,
        "empresa": empresa_puesto,
        "link": link_puesto,
        "jerarquia_evaluada": fila_vacante.get('jerarquia_limpia', 'No clasificada'),
        "match_score": 0,
        "coincidentes": [],
        "faltantes": [],
        "justificacion": "",
        "llave_cache": llave_cache
    }
    
    try:
        # CORRECCIÓN DE PRODUCCIÓN: Parámetro 'model' en lugar de 'model_name'
        model_instance = genai.GenerativeModel(
            model="gemini-1.5-flash",
            system_instruction="Eres un validador ATS experto en reclutamiento corporativo para Data, Analítica, Business Intelligence e IA."
        )
        
        response = model_instance.generate_content(
            prompt_usuario,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json", 
                response_schema=EvaluacionMatch, 
                temperature=0.1
            )
        )
        
        texto_limpio = response.text.strip()
        if texto_limpio.startswith("```json"):
            texto_limpio = texto_limpio.split("```json")[1].split("```")[0].strip()
        elif texto_limpio.startswith("```"):
            texto_limpio = texto_limpio.split("```")[1].split("```")[0].strip()

        evaluacion = json.loads(texto_limpio)
        resultado_base.update({
            "match_score": int(evaluacion.get("match_score", 0)),
            "justificacion": evaluacion.get("justificacion", "Análisis completado exitosamente."),
            "coincidentes": evaluacion.get("habilidades_coincidentes", evaluacion.get("coincidentes", [])),
            "faltantes": evaluacion.get("habilidades_faltantes", evaluacion.get("faltantes", []))
        })
        return resultado_base
        
    except google_exceptions.ResourceExhausted:
        resultado_base["justificacion"] = "⚠️ Cuota excedida (Rate Limit). Inténtalo de nuevo en unos momentos."
        return resultado_base
    except Exception as e:
        resultado_base["justificacion"] = f"❌ Error de parsing en el modelo: {str(e)}"
        return resultado_base

def registrar_telemetria_silenciosa(resultados_analisis):
    supabase = obtener_cliente_supabase()
    if not supabase: return
    try:
        datos = []
        for res in resultados_analisis:
            if res.get("match_score", 0) > 0:
                datos.append({
                    "jerarquia": res.get("jerarquia_evaluada", "Desconocida"),
                    "score": res["match_score"],
                    "origen": "Aplicación ATS"
                })
        if datos:
            supabase.table("telemetria_ats").insert(datos).execute()
    except Exception:
        pass


# =====================================================================
# 4. FLUJO DE CONEXIÓN DE DATOS Y CONTINGENCIA LOCAL
# =====================================================================
@st.cache_data(ttl=600)
def cargar_datos_seguros():
    supabase = obtener_cliente_supabase()
    if supabase:
        try:
            respuesta = supabase.table("vacantes").select("*").execute()
            if respuesta.data and len(respuesta.data) > 0:
                return pd.DataFrame(respuesta.data), "Supabase DB"
        except Exception as e:
            st.sidebar.error(f"Error cargando DB: {str(e)}. Activando contingencia.")
    
    contingencia = []
    paises_mock = ["Perú", "Colombia", "Chile", "México", "Remoto Latam"]
    h_skills_mock = [["Python", "SQL", "Machine Learning", "AWS"], ["Power BI", "SQL", "ETL", "DAX"], ["Python", "Spark", "Airflow", "Snowflake"]]
    s_skills_mock = [["Liderazgo", "Pensamiento Crítico"], ["Comunicación Asertiva", "Resolución de Problemas"]]
    empresas_mock = ["BCP", "Interbank", "Rímac", "Scotiabank", "Globant", "Mindrift"]
    
    titulos_mock = [
        ("Data Scientist", "Analista Senior / Especialista", "Data Science"),
        ("Analista de BI", "Analista / Profesional", "Business Intelligence"),
        ("Data Engineer", "Analista Senior / Especialista", "Data Engineering"),
        ("AI Software Engineer", "Analista Junior", "Artificial Intelligence"),
        ("Gerente de Analítica", "Gerente / Head", "Data Management"),
        ("Líder de Business Intelligence", "Líder / Jefe", "Business Intelligence"),
        ("Data Analyst", "Analista / Profesional", "Data Analytics"),
        ("Asistente de Datos e IA", "Practicante / Trainee", "Artificial Intelligence")
    ]
    
    for i in range(200):
        t, j, e = titulos_mock[i % len(titulos_mock)]
        p = paises_mock[i % len(paises_mock)]
        emp = empresas_mock[i % len(empresas_mock)]
        hs = h_skills_mock[i % len(h_skills_mock)]
        ss = s_skills_mock[i % len(s_skills_mock)]
        
        contingencia.append({
            "titulo": f"{t} #{i+1}",
            "empresa": emp,
            "jerarquia": j,
            "especialidad_objetivo": e,
            "pais": p,
            "descripcion": f"Requerimos profesionales con dominio estructurado en {', '.join(hs)}. Enfoque en {e}.",
            "link_oferta": f"https://www.linkedin.com/jobs/view/mock-{i+100}",
            "hard_skills": hs,
            "soft_skills": ss
        })
    return pd.DataFrame(contingencia), "Simulado / Contingencia"


# =====================================================================
# 5. FUNCIÓN PRINCIPAL DE LA APLICACIÓN (FRONTEND & UX)
# =====================================================================
def main():
    df_raw, origen_activo = cargar_datos_seguros()
    df_vacantes = df_raw.copy()

    mapeo_columnas = {
        'puesto': 'titulo',
        'especialidad': 'especialidad_objetivo',
        'link': 'link_oferta'
    }
    df_vacantes = df_vacantes.rename(columns=mapeo_columnas)

    columnas_faltantes_defecto = {
        'titulo': 'Puesto No Especificado',
        'empresa': 'Empresa No Especificada',
        'jerarquia': 'Analista / Profesional',
        'especialidad_objetivo': 'Analítica de Datos',
        'link_oferta': ''
    }

    for col, valor_defecto in columnas_faltantes_defecto.items():
        if col not in df_vacantes.columns:
            df_vacantes[col] = valor_defecto
        else:
            df_vacantes[col] = df_vacantes[col].fillna(valor_defecto)

    def limpiar_titulo(row):
        t = str(row.get('titulo', '')).strip()
        if not t or t.lower() in ['nan', 'none', 'puesto no especificado', '']:
            return f"Especialista en {row.get('especialidad_objetivo', 'Analítica de Datos')}"
        return t

    df_vacantes['titulo'] = df_vacantes.apply(limpiar_titulo, axis=1)
    df_vacantes['pais'] = df_vacantes.apply(inferir_pais_por_datos, axis=1)
    df_vacantes['jerarquia_limpia'] = df_vacantes['jerarquia'].apply(normalizar_jerarquia)

    if 'descripcion' not in df_vacantes.columns or df_vacantes['descripcion'].isna().all():
        def generar_descripcion_sintetica(row):
            hs = row.get('hard_skills', [])
            ss = row.get('soft_skills', [])
            hs_str = ", ".join(hs) if isinstance(hs, list) else str(hs)
            ss_str = ", ".join(ss) if isinstance(ss, list) else str(ss)
            return f"Búsqueda activa de {row.get('titulo')} para incorporarse al equipo de {row.get('empresa')}. Especialidad: {row.get('especialidad_objetivo')}. Requisitos e infraestructura tecnológica requerida: {hs_str}. Competencias blandas evaluadas: {ss_str}."
        df_vacantes['descripcion'] = df_vacantes.apply(generar_descripcion_sintetica, axis=1)

    # Panel lateral (Sidebar)
    st.sidebar.header("🎯 Filtros del Mercado")

    lista_paises = sorted(list(df_vacantes['pais'].unique()))
    paises_seleccionados = st.sidebar.multiselect("País / Región", options=lista_paises, default=lista_paises)

    lista_jerarquias = sorted(list(df_vacantes['jerarquia_limpia'].unique()))
    jerarquias_seleccionadas = st.sidebar.multiselect("Nivel de Seniority", options=lista_jerarquias, default=lista_jerarquias)

    lista_especialidades = sorted(list(df_vacantes['especialidad_objetivo'].unique()))
    especialidades_seleccionadas = st.sidebar.multiselect("Especialidad Funcional", options=lista_especialidades, default=lista_especialidades)

    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Limpiar Caché", use_container_width=True):
        st.session_state["ats_cache"] = {}
        st.session_state["texto_cv_usuario"] = ""
        st.cache_data.clear()
        st.rerun()

    df_filtrado = df_vacantes[
        (df_vacantes['pais'].isin(paises_seleccionados)) & 
        (df_vacantes['jerarquia_limpia'].isin(jerarquias_seleccionadas)) &
        (df_vacantes['especialidad_objetivo'].isin(especialidades_seleccionadas))
    ].reset_index(drop=True)

    st.markdown("<h1 class='main-title'>💼 DataCareer AI — Inteligencia de Mercado Data & Analytics</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ofertas Vigentes Filtradas", len(df_filtrado))
    col2.metric("Última Sincronización", "19/06/2026 22:20")
    col3.metric("Origen Activo", origen_activo)

    tab_mercado, tab_evaluador = st.tabs(["📊 Tablero Analítico", "🔍 Evaluador ATS de CV"])

    with tab_mercado:
        st.subheader("Análisis de Demanda Real y Competencias Clave")
        if not df_filtrado.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### **Distribución por Jerarquías Requeridas**")
                g1 = alt.Chart(df_filtrado).mark_bar(color='#1e3a8a').encode(
                    y=alt.Y('jerarquia_limpia:N', sort='ascending', title="Seniority"),
                    x=alt.X('count():Q', title="Vacantes"),
                    tooltip=['jerarquia_limpia', 'count()']
                ).properties(height=280)
                st.altair_chart(g1, use_container_width=True)

                st.markdown("#### **Top Hard Skills más Demandadas**")
                df_hard = df_filtrado.explode('hard_skills')
                df_hard = df_hard[df_hard['hard_skills'].astype(str).str.len() > 0]
                if not df_hard.empty:
                    g3 = alt.Chart(df_hard).mark_bar(color='#2ecc71').encode(
                        y=alt.Y('hard_skills:N', sort='-x', title="Herramientas"),
                        x=alt.X('count():Q', title="Apariciones"),
                        tooltip=['hard_skills', 'count()']
                    ).properties(height=280)
                    st.altair_chart(g3, use_container_width=True)

            with c2:
                st.markdown("#### **Demanda por Especialidad Funcional**")
                g2 = alt.Chart(df_filtrado).mark_bar(color='#f39c12').encode(
                    y=alt.Y('especialidad_objetivo:N', sort='-x', title="Especialidad"),
                    x=alt.X('count():Q', title="Vacantes"),
                    tooltip=['especialidad_objetivo', 'count()']
                ).properties(height=280)
                st.altair_chart(g2, use_container_width=True)

                st.markdown("#### **Top Soft Skills Requeridas**")
                df_soft = df_filtrado.explode('soft_skills')
                df_soft = df_soft[df_soft['soft_skills'].astype(str).str.len() > 0]
                if not df_soft.empty:
                    g4 = alt.Chart(df_soft).mark_bar(color='#9b59b6').encode(
                        y=alt.Y('soft_skills:N', sort='-x', title="Competencias"),
                        x=alt.X('count():Q', title="Apariciones"),
                        tooltip=['soft_skills', 'count()']
                    ).properties(height=280)
                    st.altair_chart(g4, use_container_width=True)

            st.markdown("---")
            st.markdown("#### **Explorador Detallado de Ofertas Laborales**")
            
            st.dataframe(
                df_filtrado[['titulo', 'empresa', 'pais', 'jerarquia_limpia', 'especialidad_objetivo', 'link_oferta']],
                column_config={
                    "titulo": st.column_config.TextColumn("Puesto Disponible"),
                    "empresa": st.column_config.TextColumn("Organización"),
                    "link_oferta": st.column_config.LinkColumn("Enlace Postulación", display_text="🎯 Ver Vacante en LinkedIn")
                },
                use_container_width=True,
                hide_index=True
            )

    with tab_evaluador:
        st.subheader("🤖 Escáner de Compatibilidad ATS por Inteligencia Artificial")
        archivo_subido = st.file_uploader("Sube tu CV en formato PDF:", type=["pdf"])
        
        if archivo_subido is not None:
            st.session_state["texto_cv_usuario"] = extraer_texto_pdf(archivo_subido)
            if st.session_state["texto_cv_usuario"]:
                st.success("¡Texto extraído del documento exitosamente!")

        if st.button("🚀 Ejecutar Match Inteligente"):
            if not st.session_state["texto_cv_usuario"].strip():
                st.error("Sube un archivo PDF válido primero.")
            elif df_vacantes.empty:
                st.error("No hay base de datos cargada.")
            else:
                df_analizar = df_filtrado if not df_filtrado.empty else df_vacantes
                cv_hash = hashlib.md5(st.session_state["texto_cv_usuario"].encode('utf-8')).hexdigest()
                
                # REGLA DE NEGOCIO: Selección por Filtro Estadístico Vectorial TF-IDF para optimizar costos de API
                MAX_LLM_CALLS = 15
                if len(df_analizar) > MAX_LLM_CALLS:
                    df_analizar = pre_ranking_ats_vectorial(df_analizar, st.session_state["texto_cv_usuario"]).head(MAX_LLM_CALLS)
                
                payloads = [
                    {
                        "texto_cv": st.session_state["texto_cv_usuario"],
                        "fila_vacante": fila,
                        "cache_dict": st.session_state["ats_cache"],
                        "cv_hash": cv_hash
                    }
                    for _, fila in df_analizar.iterrows()
                ]
                
                with st.spinner("Comparando analítica ATS con Gemini..."):
                    with ThreadPoolExecutor(max_workers=4) as executor:
                        resultados_analisis = list(executor.map(evaluar_cv_contra_vacante, payloads))
                
                for res in resultados_analisis:
                    if "llave_cache" in res and res.get("match_score", 0) > 0:
                        st.session_state["ats_cache"][res["llave_cache"]] = res

                threading.Thread(target=registrar_telemetria_silenciosa, args=(resultados_analisis,), daemon=True).start()
                
                # --- REGLA DE NEGOCIO DE PRODUCCIÓN: FILTRADO TOP 5 CON MATCH >= 70% ---
                df_procesado = pd.DataFrame(resultados_analisis)
                
                # Filtrar solo registros válidos con un porcentaje real mayor o igual a 70%
                df_filtrado_match = df_procesado[df_procesado["match_score"] >= 70]
                
                # Ordenar descendentemente por puntuación y tomar un máximo de 5 filas
                df_resultados = df_filtrado_match.sort_values(by="match_score", ascending=False).head(5).reset_index(drop=True)
                
                if df_resultados.empty:
                    st.warning("⚠️ No se encontraron ofertas que superen el 70% de match con el perfil de tu CV.")
                else:
                    st.success(f"¡Análisis de compatibilidad finalizado! Mostrando las {len(df_resultados)} mejores vacantes.")
                    
                    for idx, res in df_resultados.iterrows():
                        score = res["match_score"]
                        color_badge = "#2ecc71" # Verde puro para producción segura >= 70%
                        link_html = f'<a href="{res["link"]}" target="_blank" class="action-link">🎯 Ver Vacante Activa en {res["empresa"]}</a>' if res.get("link") else ""
                        
                        st.markdown(f"""
                        <div class="match-card">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #f1f5f9; padding-bottom: 10px;">
                                <h4 style="margin: 0; color: #1e3a8a; font-size: 1.25em;">
                                    {res.get('titulo')} <span style="color: #6b7280; font-size: 0.85em; font-weight: normal;">({res.get('empresa')})</span>
                                </h4>
                                <span style="background-color: {color_badge}; color: white; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 0.9em; white-space: nowrap;">
                                    {score}% Match
                                </span>
                            </div>
                            <div style="margin-bottom: 12px; color: #334155; font-size: 0.95em; line-height: 1.5;">
                                <strong>Análisis Estratégico ATS:</strong> {res.get('justificacion')}
                            </div>
                            <div style="margin-bottom: 8px; font-size: 0.9em; color: #16a34a;">
                                <strong>✓ Habilidades Coincidentes:</strong> {', '.join(res.get('coincidentes', [])) if res.get('coincidentes') else 'Ninguna detectada explícitamente.'}
                            </div>
                            <div style="margin-bottom: 12px; font-size: 0.9em; color: #dc2626;">
                                <strong>✗ Brechas Técnicas:</strong> {', '.join(res.get('faltantes', [])) if res.get('faltantes') else 'Ninguna brecha crítica detectada.'}
                            </div>
                            {link_html}
                        </div>
                        """, unsafe_allow_html=True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "load_data":
        cargar_vacantes_a_supabase()
    else:
        main()
