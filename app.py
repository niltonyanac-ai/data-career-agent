import streamlit as st
import pandas as pd
import json
import hashlib
import threading
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
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

# Inicialización de estado para CV y Caché
if "texto_cv_usuario" not in st.session_state:
    st.session_state["texto_cv_usuario"] = ""
if "ats_cache" not in st.session_state:
    st.session_state["ats_cache"] = {} # Diccionario para almacenar resultados previos por Hash

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("Falta configurar 'GEMINI_API_KEY' en st.secrets.")

# =====================================================================
# 1.5. PATRÓN SINGLETON PARA CONEXIÓN DE RECURSOS (MEJORA DE ESCALA)
# =====================================================================
@st.cache_resource
def obtener_cliente_supabase():
    """ Mantiene una única instancia de conexión activa en memoria para toda la app """
    if SUPABASE_AVAILABLE and "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        try:
            return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        except Exception:
            return None
    return None

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

def pre_ranking_heuristico(df, texto_cv):
    cv_clean = str(texto_cv).lower()
    scores = []
    stop_words = {"para", "como", "esta", "este", "todo", "sino", "pero", "experiencia", "conocimiento", "manejo", "perfil"}
    keywords_niveles = {
        "1.": ["practicante", "asistente", "intern", "trainee"],
        "2.": ["junior", "jr", "analista", "professional"],
        "3.": ["senior", "sr", "especialista", "advanced", "experto"],
        "4.": ["lider", "lead", "jefe", "supervisor"],
        "5.": ["subgerente", "sub-gerente", "product owner"],
        "6.": ["gerente", "manager", "director", "head", "chief"]
    }
    
    for _, fila in df.iterrows():
        score_local = 0
        jerarquia_puesto = str(fila.get('jerarquia_limpia', ''))
        
        for prefix, tokens in keywords_niveles.items():
            if prefix in jerarquia_puesto:
                if any(t in cv_clean for t in tokens):
                    score_local += 40
                break
        
        desc_puesto = str(fila.get('descripcion', '')).lower()
        palabras_filtradas = [
            p for p in desc_puesto.replace(',', ' ').replace('.', ' ').replace(':', ' ').split() 
            if len(p) > 3 and p not in stop_words
        ]
        
        coincidencias_tech = sum(1 for p in palabras_filtradas[:20] if p in cv_clean)
        score_local += (coincidencias_tech * 5)
        scores.append(score_local)
        
    df_ranked = df.copy()
    df_ranked['_score_heuristico'] = scores
    return df_ranked.sort_values(by='_score_heuristico', ascending=False).drop(columns=['_score_heuristico'])

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
    """
    Función optimizada. Lee primero desde el caché si el Hash del CV coincide.
    Implementa manejo de errores granulares para APIs de Google.
    """
    texto_cv = args["texto_cv"]
    fila_vacante = args["fila_vacante"]
    model_instance = args["model_instance"]
    cache_dict = args["cache_dict"]
    cv_hash = args["cv_hash"]
    
    # 1. VERIFICACIÓN DE CACHÉ
    llave_vacante = f"{fila_vacante.get('titulo', 'SD')}_{fila_vacante.get('empresa', 'SD')}_{fila_vacante.get('link_oferta', 'SD')}"
    llave_cache = f"{cv_hash}_{llave_vacante}"
    
    if llave_cache in cache_dict:
        return cache_dict[llave_cache] # Retorno instantáneo sin llamar a Gemini

    # 2. LLAMADA AL LLM SI NO ESTÁ EN CACHÉ
    detalles_oferta = f"""
    Título: {fila_vacante.get('titulo', 'No especificado')}
    Empresa: {fila_vacante.get('empresa', 'No especificada')}
    Especialidad: {fila_vacante.get('especialidad_objetivo', 'No especificado')}
    Jerarquía: {fila_vacante.get('jerarquia', 'No especificado')}
    Descripción: {fila_vacante.get('descripcion', 'No especificada')}
    """
    prompt_usuario = f"VACANTE:\n{detalles_oferta}\n\nCV:\n{texto_cv}"
    
    resultado_base = {
        "titulo": fila_vacante.get("titulo", "Puesto No Especificado"),
        "empresa": fila_vacante.get("empresa", "Empresa No Especificada"),
        "link": fila_vacante.get("link_oferta"),
        "jerarquia_evaluada": fila_vacante.get('jerarquia_limpia', 'No clasificada'),
        "match_score": 0,
        "coincidentes": [],
        "faltantes": [],
        "llave_cache": llave_cache
    }
    
    try:
        response = model_instance.generate_content(
            prompt_usuario,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json", response_schema=EvaluacionMatch, temperature=0.0
            )
        )
        
        # Limpieza preventiva por si la respuesta trae caracteres o bloques markdown extraños
        texto_limpio = response.text.strip()
        if texto_limpio.startswith("```json"):
            texto_limpio = texto_limpio.removeprefix("```json").removesuffix("```").strip()
        elif texto_limpio.startswith("```"):
            texto_limpio = texto_limpio.removeprefix("```").removesuffix("```").strip()
            
        evaluacion = json.loads(texto_limpio)
        resultado_base.update({
            "match_score": evaluacion.get("match_score", 0),
            "justificacion": evaluacion.get("justificacion", "Análisis completado."),
            "coincidentes": evaluacion.get("habilidades_coincidentes", []),
            "faltantes": evaluacion.get("habilidades_faltantes", [])
        })
        return resultado_base
        
    # MANEJO DE ERRORES ESPECÍFICOS DE PRODUCCIÓN
    except google_exceptions.ResourceExhausted:
        resultado_base["justificacion"] = "⚠️ Cuota excedida: Nuestros servidores están procesando demasiadas solicitudes en este momento (Rate Limit). Por favor, intenta de nuevo en unos minutos."
        return resultado_base
    except google_exceptions.ServiceUnavailable:
        resultado_base["justificacion"] = "🔌 Servicio temporalmente fuera de línea. Google Gemini está experimentando interrupciones intermitentes."
        return resultado_base
    except ValueError as e:
        if "StopCandidate" in str(e) or "safety" in str(e).lower():
            resultado_base["justificacion"] = "🛡️ Análisis bloqueado: El sistema de seguridad de la IA detuvo el escaneo. Asegúrate de que el documento no contenga información sensible o términos restringidos."
        else:
            resultado_base["justificacion"] = f"❌ Error de parseo en la respuesta de la IA: {str(e)}"
        return resultado_base
    except Exception as e:
        resultado_base["justificacion"] = f"❌ Error interno de procesamiento: {str(e)}"
        return resultado_base

# =====================================================================
# 3.5. TELEMETRÍA EN SEGUNDO PLANO (OPTIMIZADA MEDIANTE SINGLETON)
# =====================================================================
def registrar_telemetria_silenciosa(resultados_analisis):
    """ Función Fire-and-Forget que usa el cliente Singleton reutilizable """
    supabase = obtener_cliente_supabase()
    if not supabase:
        return
        
    try:
        datos_insertar = []
        for res in resultados_analisis:
            if res.get("match_score", 0) > 0:
                datos_insertar.append({
                    "jerarquia": res.get("jerarquia_evaluada", "Desconocida"),
                    "score": res["match_score"],
                    "origen": "Aplicación ATS"
                })
        
        if datos_insertar:
            supabase.table("telemetria_ats").insert(datos_insertar).execute()
    except Exception:
        pass # Silenciamos deliberadamente para asegurar desacoplamiento completo de la UI

# =====================================================================
# 4. FLUJO DE CARGA Y CONEXIÓN DE DATOS (SUPABASE INTERFACE OPTIMIZADA)
# =====================================================================
@st.cache_data(ttl=600)
def cargar_datos_seguros():
    supabase = obtener_cliente_supabase()
    if supabase:
        try:
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

# =====================================================================
# 5. FUNCIÓN PRINCIPAL DE LA APLICACIÓN (ENTRY POINT)
# =====================================================================
def main():
    df_raw = cargar_datos_seguros()
    df_vacantes = df_raw.copy()

    columnas_requeridas = {
        'titulo': 'Puesto No Especificado',
        'empresa': 'Empresa No Especificada',
        'pais': 'Perú',
        'jerarquia': 'Analista / Profesional',
        'descripcion': 'Sin descripción disponible.',
        'link_oferta': None
    }
    for col, valor_defecto in columnas_requeridas.items():
        if col not in df_vacantes.columns:
            df_vacantes[col] = valor_defecto

    df_vacantes['pais'] = df_vacantes['pais'].fillna('Latam / Remoto').astype(str).str.title()
    df_vacantes['jerarquia_limpia'] = df_vacantes['jerarquia'].apply(normalizar_jerarquia)

    # INTERFAZ DE USUARIO (UX/UI STREAMLIT)
    st.sidebar.header("🎯 Filtros del Mercado")

    lista_paises = sorted(list(df_vacantes['pais'].unique()))
    paises_seleccionados = st.sidebar.multiselect("País / Región", options=lista_paises, default=lista_paises)

    lista_jerarquias = sorted(list(df_vacantes['jerarquia_limpia'].unique()))
    jerarquias_seleccionadas = st.sidebar.multiselect("Nivel de Jerarquía / Seniority", options=lista_jerarquias, default=lista_jerarquias)

    # MEJORA UX: Control manual de Purga de memoria ATS desde Sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Gestión de Sesión")
    if st.sidebar.button("🧹 Limpiar Caché y Resultados", use_container_width=True):
        st.session_state["ats_cache"] = {}
        st.session_state["texto_cv_usuario"] = ""
        st.cache_data.clear()
        st.success("Caché liberada correctamente.")
        st.rerun()

    df_filtrado = df_vacantes[(df_vacantes['pais'].isin(paises_seleccionados)) & (df_vacantes['jerarquia_limpia'].isin(jerarquias_seleccionadas))].reset_index(drop=True)

    st.markdown("<h1 class='main-title'>💼 DataCareer AI</h1>", unsafe_allow_html=True)
    st.write("Encuentra y evalúa tu perfil contra las mejores oportunidades del mercado en tiempo real.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Ofertas Vigentes Filtradas", len(df_filtrado))
    col2.metric("Última Actualización del Pipeline", "18/06/2026 14:05")
    col3.metric("Origen de Datos", "Supabase DB" if (obtener_cliente_supabase() is not None) else "Simulado / Local")

    tab_mercado, tab_evaluador = st.tabs(["📊 Tablero del Mercado", "🔍 Evaluador ATS de CV"])

    with tab_mercado:
        st.subheader("Análisis de Demanda Real y Competencias Clave")
        if not df_filtrado.empty:
            st.bar_chart(df_filtrado['jerarquia_limpia'].value_counts())
            st.dataframe(df_filtrado[['titulo', 'empresa', 'pais', 'jerarquia_limpia']], use_container_width=True)
        else:
            st.info("No hay registros que coincidan con los filtros seleccionados de la barra lateral.")

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
            elif df_vacantes.empty:
                st.error("La base de datos de origen está vacía. No hay vacantes disponibles para comparar.")
            else:
                df_analizar = df_filtrado if not df_filtrado.empty else df_vacantes
                
                if df_filtrado.empty:
                    st.warning("⚠️ Nota: Como has desmarcado los filtros, el análisis se ejecutará usando todas las vacantes históricas disponibles en el sistema.")
                
                cv_hash = hashlib.md5(st.session_state["texto_cv_usuario"].encode('utf-8')).hexdigest()
                
                MAX_LLM_CALLS = 10
                if len(df_analizar) > MAX_LLM_CALLS:
                    with st.spinner("Realizando pre-ranking de relevancia estadística..."):
                        df_analizar = pre_ranking_heuristico(df_analizar, st.session_state["texto_cv_usuario"]).head(MAX_LLM_CALLS)
                    st.info(f"💡 Seleccionamos las {MAX_LLM_CALLS} ofertas con mayor correlación preliminar.")
                    
                with st.spinner("Procesando comparación ATS..."):
                    prompt_sistema = "Eres un validador ATS experto en reclutamiento para Data, Analítica e IA. Evalúa con alto rigor técnico y penaliza omisiones."
                    shared_model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=prompt_sistema)
                    
                    payloads = [
                        {
                            "texto_cv": st.session_state["texto_cv_usuario"],
                            "fila_vacante": fila,
                            "model_instance": shared_model,
                            "cache_dict": st.session_state["ats_cache"],
                            "cv_hash": cv_hash
                        }
                        for _, fila in df_analizar.iterrows()
                    ]
                    
                    with ThreadPoolExecutor(max_workers=5) as executor:
                        resultados_analisis = list(executor.map(evaluar_cv_contra_vacante, payloads))
                    
                    for res in resultados_analisis:
                        if "llave_cache" in res and res.get("match_score", 0) > 0:
                            st.session_state["ats_cache"][res["llave_cache"]] = res

                threading.Thread(target=registrar_telemetria_silenciosa, args=(resultados_analisis,), daemon=True).start()
                
                df_resultados = pd.DataFrame(resultados_analisis).sort_values(by="match_score", ascending=False).reset_index(drop=True)
                st.success("¡Análisis de compatibilidad finalizado!")
                
                for idx, res in df_resultados.iterrows():
                    score = res["match_score"]
                    color_badge = "#2ecc71" if score >= 75 else ("#f39c12" if score >= 45 else "#e74c3c")
                    
                    coincide_list = res.get('coincidentes', [])
                    falta_list = res.get('faltantes', [])
                    
                    s_coincidentes = ', '.join(coincide_list) if coincide_list else 'Ninguna detectada explícitamente.'
                    s_faltantes = ', '.join(falta_list) if falta_list else 'Ninguna brecha crítica encontrada.'
                    
                    link_html = ""
                    if res.get("link"):
                        link_html = f'<a href="{res["link"]}" target="_blank" class="action-link">🎯 Ver vacante activa en {res["empresa"]}</a>'
                    
                    st.markdown(f"""
                    <div class="match-card">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #f1f5f9; padding-bottom: 10px;">
                            <h4 style="margin: 0; color: #1e3a8a; font-size: 1.25em;">
                                {res.get('titulo', 'Puesto No Especificado')} <span style="color: #6b7280; font-size: 0.85em; font-weight: normal;">({res.get('empresa', 'Empresa No Especificada')})</span>
                            </h4>
                            <span style="background-color: {color_badge}; color: white; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 0.9em; white-space: nowrap;">
                                {score}% Match
                            </span>
                        </div>
                        <div style="margin-bottom: 12px; color: #334155; font-size: 0.95em; line-height: 1.5;">
                            <strong style="color: #0f172a;">Análisis Estratégico ATS:</strong> {res.get('justificacion', 'Sin justificación.')}
                        </div>
                        <div style="margin-bottom: 8px; font-size: 0.9em; color: #16a34a;">
                            <strong>✓ Habilidades Coincidentes:</strong> {s_coincidentes}
                        </div>
                        <div style="margin-bottom: 12px; font-size: 0.9em; color: #dc2626;">
                            <strong>✗ Brechas Técnicas Detectadas:</strong> {s_faltantes}
                        </div>
                        {link_html}
                    </div>
                    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
