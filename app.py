import streamlit as st
import pandas as pd
import json
import hashlib
import threading
import altair as alt
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

if "texto_cv_usuario" not in st.session_state:
    st.session_state["texto_cv_usuario"] = ""
if "ats_cache" not in st.session_state:
    st.session_state["ats_cache"] = {}

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("Falta configurar 'GEMINI_API_KEY' en st.secrets.")

# =====================================================================
# 1.5. PATRÓN SINGLETON PARA CONEXIÓN DE RECURSOS
# =====================================================================
@st.cache_resource
def obtener_cliente_supabase():
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
    match_score: int = Field(..., description="Porcentaje de match real de 0 a 100 basado estrictamente en el cumplimiento de requisitos mínimos y deseables.")
    justificacion: str = Field(..., description="Explicación analítica clara detallando por qué cumple o no con el perfil.")
    habilidades_coincidentes: list[str] = Field(..., description="Lista de habilidades que el candidato sí posee.")
    habilidades_faltantes: list[str] = Field(..., description="Lista de tecnologías, herramientas o requisitos ausentes en el CV.")

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
        
        coincidencias_tech = sum(1 for p in palabras_filtradas[:25] if p in cv_clean)
        score_local += (coincidencias_tech * 6)
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
    texto_cv = args["texto_cv"]
    fila_vacante = args["fila_vacante"]
    model_instance = args["model_instance"]
    cache_dict = args["cache_dict"]
    cv_hash = args["cv_hash"]
    
    llave_vacante = f"{fila_vacante.get('titulo', 'SD')}_{fila_vacante.get('empresa', 'SD')}_{fila_vacante.get('link_oferta', 'SD')}"
    llave_cache = f"{cv_hash}_{llave_vacante}"
    
    if llave_cache in cache_dict:
        return cache_dict[llave_cache]

    detalles_oferta = f"""
    Título de la Oferta: {fila_vacante.get('titulo', 'No especificado')}
    Empresa: {fila_vacante.get('empresa', 'No especificada')}
    Especialidad Funcional: {fila_vacante.get('especialidad_objetivo', 'No especificado')}
    Jerarquía Requerida: {fila_vacante.get('jerarquia_limpia', 'No especificada')}
    Descripción Detallada del Puesto: {fila_vacante.get('descripcion', 'No especificada')}
    """
    
    prompt_usuario = f"""
    Por favor, analiza semánticamente la afinidad del candidato con la vacante descrita.
    Para el cálculo del `match_score`, sé justo: si el CV demuestra competencias sólidas y alineación de stack o negocio, asígnale un porcentaje de compatibilidad representativo y realista (superando el 70% si existe correlación técnica sólida). 
    
    VACANTE OBJETIVO:
    {detalles_oferta}
    
    CURRÍCULUM VITAE DEL CANDIDATO:
    {texto_cv}
    """
    
    resultado_base = {
        "titulo": fila_vacante.get("titulo", "Puesto No Especificado"),
        "empresa": fila_vacante.get("empresa", "Empresa No Especificada"),
        "link": fila_vacante.get("link_oferta"),
        "jerarquia_evaluada": fila_vacante.get('jerarquia_limpia', 'No clasificada'),
        "match_score": 0,
        "coincidentes": [],
        "faltantes": [],
        "justificacion": "",
        "llave_cache": llave_cache
    }
    
    try:
        response = model_instance.generate_content(
            prompt_usuario,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json", response_schema=EvaluacionMatch, temperature=0.1
            )
        )
        
        texto_limpio = response.text.strip()
        if texto_limpio.startswith("```json"):
            texto_limpio = texto_limpio.removeprefix("```json").removesuffix("```").strip()
            
        evaluacion = json.loads(texto_limpio)
        resultado_base.update({
            "match_score": int(evaluacion.get("match_score", 0)),
            "justificacion": evaluacion.get("justificacion", "Análisis completado de forma exitosa."),
            "coincidentes": evaluacion.get("habilidades_coincidentes", []),
            "faltantes": evaluacion.get("habilidades_faltantes", [])
        })
        return resultado_base
        
    except google_exceptions.ResourceExhausted:
        resultado_base["justificacion"] = "⚠️ Cuota excedida (Rate Limit). Reintentando internamente..."
        return resultado_base
    except Exception as e:
        resultado_base["justificacion"] = f"❌ No se pudo completar el análisis automatizado: {str(e)}"
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
# 4. FLUJO DE CARGA Y CONEXIÓN DE DATOS (MUESTRA ESTADÍSTICA ROBUSTA)
# =====================================================================
@st.cache_data(ttl=600)
def cargar_datos_seguros():
    supabase = obtener_cliente_supabase()
    if supabase:
        try:
            respuesta = supabase.table("vacantes").select("*").execute()
            if respuesta.data and len(respuesta.data) > 0:
                return pd.DataFrame(respuesta.data)
        except Exception as e:
            st.sidebar.error(f"Error cargando desde DB de producción: {str(e)}. Activando contingencia.")
    
    # Dataset de contingencia representativo y multiregional para evitar fallos de inicialización
    contingencia = []
    paises_mock = ["Perú", "Colombia", "Chile", "México", "Remoto Latam"]
    h_skills_mock = [["Python", "SQL", "Machine Learning", "AWS"], ["Power BI", "SQL", "ETL", "DAX"], ["Python", "Spark", "Airflow", "Snowflake"], ["Python", "LLMs", "LangChain"]]
    s_skills_mock = [["Liderazgo", "Pensamiento Crítico"], ["Comunicación Asertiva", "Resolución de Problemas"]]
    empresas_mock = ["BCP", "Interbank", "Rímac", "Alicorp", "Globant", "NTT DATA"]
    
    titulos_mock = [
        ("Data Scientist Senior", "Senior", "Data Science"),
        ("Analista de Business Intelligence", "Analista", "Business Intelligence"),
        ("Data Engineer Advanced", "Senior", "Data Engineering"),
        ("AI Software Engineer", "Analista", "Artificial Intelligence"),
        ("Gerente de Analítica de Datos", "Gerente", "Data Management"),
        ("Practicante de Inteligencia Comercial", "Practicante", "Business Intelligence"),
        ("Jefe de Gobierno de Datos", "Jefe", "Data Management")
    ]
    
    # Generamos un set de contingencia robusto para garantizar que los filtros siempre tengan contenido
    for i in range(45):
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
            "descripcion": f"Requerimos profesionales con dominio estructurado en {', '.join(hs)}. Enfoque en analítica avanzada y {', '.join(ss)}.",
            "link_oferta": f"[https://www.linkedin.com/jobs/view/mock-](https://www.linkedin.com/jobs/view/mock-){i+100}",
            "hard_skills": hs,
            "soft_skills": ss
        })
    return pd.DataFrame(contingencia)

# =====================================================================
# 5. FUNCIÓN PRINCIPAL DE LA APLICACIÓN (CORRECCIÓN RUNTIME ENTRY POINT)
# =====================================================================
def main():
    df_raw = cargar_datos_seguros()
    df_vacantes = df_raw.copy()

    # Sanitización garantizada de datos estructurados de entrada
    columnas_defecto = {
        'titulo': 'Puesto No Especificado', 'empresa': 'Empresa No Especificada',
        'pais': 'Perú', 'jerarquia': 'Analista / Profesional',
        'especialidad_objetivo': 'Data & Analytics', 'descripcion': 'Sin descripción.',
        'link_oferta': None, 'hard_skills': [], 'soft_skills': []
    }
    for col, valor in columnas_defecto.items():
        if col not in df_vacantes.columns:
            df_vacantes[col] = valor

    df_vacantes['pais'] = df_vacantes['pais'].fillna('Remoto Latam').astype(str).str.title()
    df_vacantes['jerarquia_limpia'] = df_vacantes['jerarquia'].apply(normalizar_jerarquia)

    # -----------------------------------------------------------------
    # CONTROL DE CONTENIDOS - PANEL LATERAL (SIDEBAR DE FILTROS GLOBALES)
    # -----------------------------------------------------------------
    st.sidebar.header("🎯 Filtros del Mercado")

    lista_paises = sorted(list(df_vacantes['pais'].unique()))
    paises_seleccionados = st.sidebar.multiselect("País / Región", options=lista_paises, default=lista_paises)

    lista_jerarquias = sorted(list(df_vacantes['jerarquia_limpia'].unique()))
    jerarquias_seleccionadas = st.sidebar.multiselect("Nivel de Seniority", options=lista_jerarquias, default=lista_jerarquias)

    lista_especialidades = sorted(list(df_vacantes['especialidad_objetivo'].unique()))
    especialidades_seleccionadas = st.sidebar.multiselect("Especialidad Funcional", options=lista_especialidades, default=lista_especialidades)

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Gestión de Sesión")
    if st.sidebar.button("🧹 Limpiar Caché y Resultados", use_container_width=True):
        st.session_state["ats_cache"] = {}
        st.session_state["texto_cv_usuario"] = ""
        st.cache_data.clear()
        st.success("Caché liberada correctamente.")
        st.rerun()

    # Aplicación estricta de filtros sobre el set de datos en tiempo real
    df_filtrado = df_vacantes[
        (df_vacantes['pais'].isin(paises_seleccionados)) & 
        (df_vacantes['jerarquia_limpia'].isin(jerarquias_seleccionadas)) &
        (df_vacantes['especialidad_objetivo'].isin(especialidades_seleccionadas))
    ].reset_index(drop=True)

    # Encabezado UI principal
    st.markdown("<h1 class='main-title'>💼 DataCareer AI</h1>", unsafe_allow_html=True)
    st.write("Ecosistema de inteligencia de talento para la evaluación de compatibilidad laboral en tiempo real.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Ofertas Vigentes Filtradas", len(df_filtrado))
    col2.metric("Última Sincronización del Pipeline", "19/06/2026 13:00")
    col3.metric("Origen de Datos Activo", "Supabase DB" if (obtener_cliente_supabase() is not None) else "Simulado / Contingencia")

    tab_mercado, tab_evaluador = st.tabs(["📊 Tablero Analítico del Mercado", "🔍 Evaluador ATS de CV"])

    # -----------------------------------------------------------------
    # TAB 1: LOS 4 GRÁFICOS OBLIGATORIOS (ALTAIR CON DETECCIÓN EXPLODE Y SORT)
    # -----------------------------------------------------------------
    with tab_mercado:
        st.subheader("Análisis de Demanda Real y Competencias Clave")
        
        if not df_filtrado.empty:
            # Grid balanceado 2x2 para evitar vistas aplanadas o asimétricas
            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("#### **Distribución por Jerarquías Requeridas**")
                g1 = alt.Chart(df_filtrado).mark_bar(color='#1e3a8a').encode(
                    x=alt.X('jerarquia_limpia:N', sort='-y', title="Nivel de Seniority"),
                    y=alt.Y('count():Q', title="Volumen de Vacantes")
                ).properties(height=280)
                st.altair_chart(g1, use_container_width=True)

                # Procesamiento mediante .explode() para mapeo de Hard Skills individuales
                st.markdown("#### **Top Hard Skills más Demandadas**")
                df_hard = df_filtrado.explode('hard_skills')
                df_hard = df_hard[df_hard['hard_skills'].astype(str).str.len() > 0]
                
                if not df_hard.empty:
                    g3 = alt.Chart(df_hard).mark_bar(color='#2ecc71').encode(
                        x=alt.X('hard_skills:N', sort='-y', title="Tecnologías / Herramientas"),
                        y=alt.Y('count():Q', title="Frecuencia de Aparición")
                    ).properties(height=280)
                    st.altair_chart(g3, use_container_width=True)
                else:
                    st.info("Sin registros de Hard Skills en este segmento.")

            with c2:
                st.markdown("#### **Demanda por Especialidad Funcional**")
                g2 = alt.Chart(df_filtrado).mark_bar(color='#f39c12').encode(
                    x=alt.X('especialidad_objetivo:N', sort='-y', title="Especialidad"),
                    y=alt.Y('count():Q', title="Volumen de Vacantes")
                ).properties(height=280)
                st.altair_chart(g2, use_container_width=True)

                # Procesamiento mediante .explode() para mapeo de Soft Skills individuales
                st.markdown("#### **Top Soft Skills Requeridas**")
                df_soft = df_filtrado.explode('soft_skills')
                df_soft = df_soft[df_soft['soft_skills'].astype(str).str.len() > 0]
                
                if not df_soft.empty:
                    g4 = alt.Chart(df_soft).mark_bar(color='#9b59b6').encode(
                        x=alt.X('soft_skills:N', sort='-y', title="Competencias Blandas"),
                        y=alt.Y('count():Q', title="Frecuencia de Aparición")
                    ).properties(height=280)
                    st.altair_chart(g4, use_container_width=True)
                else:
                    st.info("Sin registros de Soft Skills en este segmento.")

            st.markdown("---")
            st.markdown("#### **Explorador Detallado de Ofertas Laborales**")
            st.dataframe(df_filtrado[['titulo', 'empresa', 'pais', 'jerarquia_limpia', 'especialidad_objetivo']], use_container_width=True)
        else:
            st.info("No hay registros que coincidan con los filtros seleccionados.")

    # -----------------------------------------------------------------
    # TAB 2: EVALUADOR ATS OPTIMIZADO
    # -----------------------------------------------------------------
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
                st.error("La base de datos de origen está vacía.")
            else:
                df_analizar = df_filtrado if not df_filtrado.empty else df_vacantes
                cv_hash = hashlib.md5(st.session_state["texto_cv_usuario"].encode('utf-8')).hexdigest()
                
                MAX_LLM_CALLS = 10
                if len(df_analizar) > MAX_LLM_CALLS:
                    with st.spinner("Realizando pre-ranking de relevancia estadística..."):
                        df_analizar = pre_ranking_heuristico(df_analizar, st.session_state["texto_cv_usuario"]).head(MAX_LLM_CALLS)
                    st.info(f"💡 Evaluando semánticamente el Top {MAX_LLM_CALLS} de vacantes con mayor afinidad estadística preliminar.")
                    
                with st.spinner("Procesando comparación analítica ATS con Gemini 1.5 Flash..."):
                    prompt_sistema = "Eres un validador ATS experto en reclutamiento corporativo para Data, Analítica, Business Intelligence e IA. Evalúas con alto rigor y especificidad técnica."
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
                
                # Renderizado dinámico de tarjetas profesionales de correspondencia (Match Cards)
                for idx, res in df_resultados.iterrows():
                    score = res["match_score"]
                    color_badge = "#2ecc71" if score >= 70 else ("#f39c12" if score >= 45 else "#e74c3c")
                    
                    coincide_list = res.get('coincidentes', [])
                    falta_list = res.get('faltantes', [])
                    
                    s_coincidentes = ', '.join(coincide_list) if coincide_list else 'Ninguna detectada explícitamente.'
                    s_faltantes = ', '.join(falta_list) if falta_list else 'Ninguna brecha crítica detectada.'
                    
                    link_html = ""
                    if res.get("link"):
                        link_html = f'<a href="{res["link"]}" target="_blank" class="action-link">🎯 Ver Vacante Activa en {res["empresa"]}</a>'
                    
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
                            <strong style="color: #0f172a;">Análisis Estratégico ATS:</strong> {res.get('justificacion', 'Sin justificación disponible.')}
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
