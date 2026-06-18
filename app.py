import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor
from pypdf import PdfReader

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# =====================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y ESTILOS
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
        margin-bottom: 5px; 
        background-color: #ffffff;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .main-title {
        color: #1e3a8a;
        font-weight: 800;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar estados de sesión para estabilidad en rerenders
if "texto_cv_usuario" not in st.session_state:
    st.session_state["texto_cv_usuario"] = ""

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("Falta configurar 'GEMINI_API_KEY' en st.secrets.")

# =====================================================================
# 2. DEFINICIÓN DE ESQUEMAS ESTRUCTURADOS (PYDANTIC)
# =====================================================================
class EvaluacionMatch(BaseModel):
    match_score: int = Field(..., description="Porcentaje de match real de 0 a 100 basado en requisitos.")
    justificacion: str = Field(..., description="Explicación detallada de por qué se asignó el puntaje.")
    habilidades_coincidentes: list[str] = Field(..., description="Lista de habilidades que el candidato cumple.")
    habilidades_faltantes: list[str] = Field(..., description="Lista de tecnologías o requisitos faltantes.")

# =====================================================================
# 3. CAPA DE INTELIGENCIA Y PROCESAMIENTO (BACKEND)
# =====================================================================
def normalizar_jerarquia(texto):
    if pd.isna(texto) or texto is None: return "2. Analista / Profesional"
    t = str(texto).lower().strip()
    if any(x in t for x in ["practicante", "asistente", "intern", "trainee", "pasantia"]): return "1. Practicante / Asistente"
    if any(x in t for x in ["gerente", "manager", "head", "director", "chief", "cdo", "cto", "ceo"]): return "6. Gerente / Head"
    if any(x in t for x in ["subgerente", "sub-gerente", "product owner", "po", "scrum"]): return "5. Sub Gerente / P.O."
    if any(x in t for x in ["lider", "líder", "jefe", "jefatura", "lead", "supervisor"]): return "4. Líder / Jefe"
    if any(x in t for x in ["senior", "sr", "especialista", "advanced", "ssr"]): return "3. Analista Senior / Especialista"
    if "junior" in t or "jr" in t: return "2. Analista Junior"
    return "2. Analista / Profesional"

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

def evaluar_cv_contra_vacante(texto_cv, fila_vacante, modelo="gemini-1.5-flash"):
    detalles_oferta = f"""
    Título: {fila_vacante.get('titulo', 'No especificado')}
    Especialidad: {fila_vacante.get('especialidad_objetivo', 'No especificado')}
    Jerarquía: {fila_vacante.get('jerarquia', 'No especificado')}
    Descripción: {fila_vacante.get('descripcion', 'No especificada')}
    """
    prompt_sistema = "Eres un validador ATS experto en reclutamiento para Data, Analítica e IA. Evalúa con alto rigor técnico y penaliza omisiones."
    prompt_usuario = f"VACANTE:\n{detalles_oferta}\n\nCV:\n{texto_cv}"
    
    try:
        model = genai.GenerativeModel(model_name=modelo, system_instruction=prompt_sistema)
        response = model.generate_content(
            prompt_usuario,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json", response_schema=EvaluacionMatch, temperature=0.0
            )
        )
        evaluacion = json.loads(response.text)
        return {
            "titulo": fila_vacante.get("titulo", "Puesto No Especificado"),
            "empresa": fila_vacante.get("empresa", "Empresa No Especificada"),
            "link": fila_vacante.get("link_oferta"),
            "match_score": evaluacion.get("match_score", 0),
            "justificacion": evaluacion.get("justificacion", "Sin justificación."),
            "coincidentes": evaluacion.get("habilidades_coincidentes", []),
            "faltantes": evaluacion.get("habilidades_faltantes", [])
        }
    except Exception as e:
        return {"titulo": fila_vacante.get("titulo"), "empresa": fila_vacante.get("empresa"), "link": fila_vacante.get("link_oferta"), "match_score": 0, "justificacion": f"Error: {str(e)}", "coincidentes": [], "faltantes": []}

# =====================================================================
# 4. FLUJO DE CARGA Y CONEXIÓN DE DATOS (SUPABASE INTERFACE)
# =====================================================================
@st.cache_data(ttl=600)
def cargar_datos_seguros():
    if SUPABASE_AVAILABLE and "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        try:
            supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
            respuesta = supabase.table("vacantes").select("*").execute()
            if respuesta.data:
                return pd.DataFrame(respuesta.data)
        except Exception as e:
            st.sidebar.error(f"Error en Supabase: {str(e)}. Usando fallback.")
    
    return pd.DataFrame([
        {"titulo": "Data Scientist Senior", "empresa": "Inetum", "jerarquia": "Senior", "especialidad_objetivo": "Data Science", "pais": "Perú", "descripcion": "Requiere Python, SQL, AWS, Machine Learning.", "link_oferta": "https://www.linkedin.com/jobs/view/1"},
        {"titulo": "Analista de Business Intelligence", "empresa": "NTT DATA", "jerarquia": "Analista", "especialidad_objetivo": "Business Intelligence", "pais": "Colombia", "descripcion": "Experiencia avanzada en Power BI, SQL y ETL.", "link_oferta": "https://www.linkedin.com/jobs/view/2"},
        {"titulo": "Gerente de Analítica de Datos", "empresa": "Mindrift", "jerarquia": "Gerente", "especialidad_objetivo": "Data Management", "pais": "Chile", "descripcion": "Liderazgo de equipos, Gobierno de Datos.", "link_oferta": "https://www.linkedin.com/jobs/view/3"}
    ])

df_raw = cargar_datos_seguros()
df_vacantes = df_raw.copy()

if 'pais' not in df_vacantes.columns: df_vacantes['pais'] = 'Perú'
else: df_vacantes['pais'] = df_vacantes['pais'].fillna('Latam / Remoto').astype(str).str.title()
df_vacantes['jerarquia_limpia'] = df_vacantes['jerarquia'].apply(normalizar_jerarquia)

# =====================================================================
# 5. INTERFAZ DE USUARIO (UX/UI STREAMLIT)
# =====================================================================
st.sidebar.header("🎯 Filtros del Mercado")
lista_paises = sorted(df_vacantes['pais'].unique())
paises_seleccionados = st.sidebar.multiselect("País / Región", options=lista_paises, default=lista_paises)

lista_jerarquias = sorted(df_vacantes['jerarquia_limpia'].unique())
jerarquias_seleccionadas = st.sidebar.multiselect("Nivel de Jerarquía / Seniority", options=lista_jerarquias, default=lista_jerarquias)

df_filtrado = df_vacantes[(df_vacantes['pais'].isin(paises_seleccionados)) & (df_vacantes['jerarquia_limpia'].isin(jerarquias_seleccionadas))].reset_index(drop=True)

st.markdown("<h1 class='main-title'>💼 DataCareer AI</h1>", unsafe_allow_html=True)
st.write("Encuentra y evalúa tu perfil contra las mejores oportunidades del mercado en tiempo real.")

col1, col2, col3 = st.columns(3)
col1.metric("Ofertas Vigentes Filtradas", len(df_filtrado))
col2.metric("Última Actualización del Pipeline", "18/06/2026 14:05")
col3.metric("Origen de Datos", "Supabase DB" if (SUPABASE_AVAILABLE and "SUPABASE_URL" in st.secrets) else "Simulado / Local")

tab_mercado, tab_evaluador = st.tabs(["📊 Tablero del Mercado", "🔍 Evaluador ATS de CV"])

with tab_mercado:
    st.subheader("Análisis de Demanda Real y Competencias Clave")
    if not df_filtrado.empty:
        st.bar_chart(df_filtrado['jerarquia_limpia'].value_counts())
        st.dataframe(df_filtrado[['titulo', 'empresa', 'pais', 'jerarquia_limpia']], use_container_width=True)
    else:
        st.info("No hay registros que coincidan con los filtros seleccionados.")

with tab_evaluador:
    st.subheader("🤖 Escáner de Compatibilidad ATS por Inteligencia Artificial")
    
    archivo_subido = st.file_uploader("Sube tu Currículum Vitae en formato PDF:", type=["pdf"])
    
    if archivo_subido is not None:
        with st.spinner("Lectura e indexación estructural del PDF..."):
            st.session_state["texto_cv_usuario"] = extraer_texto_pdf(archivo_subido)
        
        if st.session_state["texto_cv_usuario"]:
            st.success("¡Texto extraído del documento exitosamente!")
            with st.expander("👁️ Ver contenido extraído del CV"):
                st.text(st.session_state["texto_cv_usuario"])

    if st.button("🚀 Ejecutar Match Inteligente"):
        if not st.session_state["texto_cv_usuario"].strip():
            st.error("Por favor, sube un archivo PDF válido antes de ejecutar el análisis.")
        elif df_filtrado.empty:
            st.error("No hay vacantes en los segmentos seleccionados para realizar el contraste.")
        else:
            with st.spinner("Procesando comparación ATS concurrente con Gemini Engine..."):
                lista_filas = [fila for _, fila in df_filtrado.iterrows()]
                with ThreadPoolExecutor(max_workers=5) as executor:
                    resultados_analisis = list(executor.map(lambda f: evaluar_cv_contra_vacante(st.session_state["texto_cv_usuario"], f), lista_filas))
            
            df_resultados = pd.DataFrame(resultados_analisis).sort_values(by="match_score", ascending=False).reset_index(drop=True)
            st.success("¡Análisis de compatibilidad finalizado!")
            
            for idx, res in df_resultados.iterrows():
                score = res["match_score"]
                color_badge = "#2ecc71" if score >= 75 else ("#f39c12" if score >= 45 else "#e74c3c")
                s_coincidentes = ', '.join(res['coincidentes']) if res['coincidentes'] else 'Ninguna detectada explícitamente.'
                s_faltantes = ', '.join(res['faltantes']) if res['faltantes'] else 'Ninguna brecha crítica encontrada.'
                
                st.markdown(f"""
                <div class="match-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #f1f5f9; padding-bottom: 10px;">
                        <h4 style="margin: 0; color: #1e3a8a; font-size: 1.25em;">
                            {res['titulo']} <span style="color: #6b7280; font-size: 0.85em; font-weight: normal;">({res['empresa']})</span>
                        </h4>
                        <span style="background-color: {color_badge}; color: white; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 0.9em; white-space: nowrap;">
                            {score}% Match
                        </span>
                    </div>
                    <div style="margin-bottom: 12px; color: #334155; font-size: 0.95em; line-height: 1.5;">
                        <strong style="color: #0f172a;">Análisis Estratégico ATS:</strong> {res['justificacion']}
                    </div>
                    <div style="margin-bottom: 8px; font-size: 0.9em; color: #16a34a;">
                        <strong>✓ Habilidades Coincidentes:</strong> {s_coincidentes}
                    </div>
                    <div style="margin-bottom: 5px; font-size: 0.9em; color: #dc2626;">
                        <strong>✗ Brechas Técnicas Detectadas:</strong> {s_faltantes}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if res.get("link"):
                    st.link_button(f"🎯 Ver vacante activa en {res['empresa']}", url=res["link"], key=f"btn_lnk_{idx}")
                st.write("")
