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

@st.cache_resource
def obtener_cliente_supabase():
    if SUPABASE_AVAILABLE and "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        try:
            return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        except Exception:
            return None
    return None

class EvaluacionMatch(BaseModel):
    match_score: int = Field(..., description="Porcentaje de match real de 0 a 100 basado estrictamente en el cumplimiento de requisitos.")
    justificacion: str = Field(..., description="Explicación analítica clara detallando por qué cumple o no con el perfil.")
    habilidades_coincidentes: list[str] = Field(..., description="Lista de habilidades que el candidato sí posee.")
    habilidades_faltantes: list[str] = Field(..., description="Lista de tecnologías, herramientas o requisitos ausentes en el CV.")

# =====================================================================
# 3. CAPA DE INTELIGENCIA Y PROCESAMIENTO (BACKEND)
# =====================================================================
def normalizar_jerarquia(texto):
    if pd.isna(texto) or texto is None: return "3. Analista / Profesional"
    t = str(texto).lower().strip()
    if any(x in t for x in ["practicante", "asistente", "intern", "trainee", "pasantia"]): return "1. Practicante / Asistente"
    if any(x in t for x in ["gerente", "manager", "head", "director", "chief", "cdo", "cto", "ceo"]): return "6. Gerente / Head"
    if any(x in t for x in ["lider", "líder", "jefe", "jefatura", "lead", "supervisor"]): return "5. Líder / Jefe"
    if any(x in t for x in ["senior", "sr", "especialista", "advanced", "ssr"]): return "4. Analista Senior / Especialista"
    if "junior" in t or "jr" in t: return "2. Analista Junior"
    return "3. Analista / Profesional"

def pre_ranking_heuristico(df, texto_cv):
    cv_clean = str(texto_cv).lower()
    scores = []
    stop_words = {"para", "como", "esta", "este", "todo", "sino", "pero", "experiencia", "conocimiento", "manejo", "perfil"}
    keywords_niveles = {
        "1.": ["practicante", "asistente", "intern", "trainee"],
        "2.": ["junior", "jr"],
        "3.": ["analista", "professional", "profesional"],
        "4.": ["senior", "sr", "especialista", "advanced"],
        "5.": ["lider", "lead", "jefe", "supervisor"],
        "6.": ["gerente", "manager", "director", "head"]
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
    Jerarquía Requerida: {fila_vacante.get('jerarquia_limpia', 'No especificada')}
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
        model_instance = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
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
        
        evaluacion = json.loads(response.text.strip())
        resultado_base.update({
            "match_score": int(evaluacion.get("match_score", 0)),
            "justificacion": evaluacion.get("justificacion", "Análisis completado exitosamente."),
            "coincidentes": evaluacion.get("habilidades_coincidentes", []),
            "faltantes": evaluacion.get("habilidades_faltantes", [])
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
        ("Asistente de Datos e IA", "Practicante / Asistente", "Artificial Intelligence")
    ]
    
    for i in range(100):
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
    return pd.DataFrame(contingencia)

# =====================================================================
# 5. FUNCIÓN PRINCIPAL DE LA APLICACIÓN
# =====================================================================
def main():
    df_raw = cargar_datos_seguros()
    df_vacantes = df_raw.copy()

    # Sanitización estricta para evitar "Puesto No Especificado" bajo cualquier circunstancia
    def limpiar_titulo(row):
        t = str(row.get('titulo', '')).strip()
        if not t or t.lower() in ['nan', 'none', 'puesto no especificado', '']:
            return f"Especialista en {row.get('especialidad_objetivo', 'Analítica de Datos')}"
        return t

    df_vacantes['titulo'] = df_vacantes.apply(limpiar_titulo, axis=1)
    df_vacantes['pais'] = df_vacantes['pais'].fillna('Remoto Latam').astype(str).str.title()
    df_vacantes['jerarquia_limpia'] = df_vacantes['jerarquia'].apply(normalizar_jerarquia)

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

    st.markdown("<h1 class='main-title'>💼 DataCareer AI</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ofertas Vigentes Filtradas", len(df_filtrado))
    col2.metric("Última Sincronización", "19/06/2026 13:40")
    col3.metric("Origen Activo", "Supabase DB" if (obtener_cliente_supabase() is not None) else "Simulado / Contingencia")

    tab_mercado, tab_evaluador = st.tabs(["📊 Tablero Analítico", "🔍 Evaluador ATS de CV"])

    with tab_mercado:
        st.subheader("Análisis de Demanda Real y Competencias Clave")
        if not df_filtrado.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### **Distribución por Jerarquías Requeridas**")
                g1 = alt.Chart(df_filtrado).mark_bar(color='#1e3a8a').encode(
                    x=alt.X('jerarquia_limpia:N', sort='x', axis=alt.Axis(labelAngle=-45, labelFontSize=10), title="Seniority"),
                    y=alt.Y('count():Q', title="Vacantes"),
                    tooltip=['jerarquia_limpia', 'count()']
                ).properties(height=280)
                st.altair_chart(g1, use_container_width=True)

                st.markdown("#### **Top Hard Skills más Demandadas**")
                df_hard = df_filtrado.explode('hard_skills')
                df_hard = df_hard[df_hard['hard_skills'].astype(str).str.len() > 0]
                if not df_hard.empty:
                    g3 = alt.Chart(df_hard).mark_bar(color='#2ecc71').encode(
                        x=alt.X('hard_skills:N', sort='-y', axis=alt.Axis(labelAngle=-45, labelFontSize=10), title="Herramientas"),
                        y=alt.Y('count():Q', title="Apariciones"),
                        tooltip=['hard_skills', 'count()']
                    ).properties(height=280)
                    st.altair_chart(g3, use_container_width=True)

            with c2:
                st.markdown("#### **Demanda por Especialidad Funcional**")
                g2 = alt.Chart(df_filtrado).mark_bar(color='#f39c12').encode(
                    x=alt.X('especialidad_objetivo:N', sort='-y', axis=alt.Axis(labelAngle=-45, labelFontSize=10), title="Especialidad"),
                    y=alt.Y('count():Q', title="Vacantes"),
                    tooltip=['especialidad_objetivo', 'count()']
                ).properties(height=280)
                st.altair_chart(g2, use_container_width=True)

                st.markdown("#### **Top Soft Skills Requeridas**")
                df_soft = df_filtrado.explode('soft_skills')
                df_soft = df_soft[df_soft['soft_skills'].astype(str).str.len() > 0]
                if not df_soft.empty:
                    g4 = alt.Chart(df_soft).mark_bar(color='#9b59b6').encode(
                        x=alt.X('soft_skills:N', sort='-y', axis=alt.Axis(labelAngle=-45, labelFontSize=10), title="Competencias"),
                        y=alt.Y('count():Q', title="Apariciones"),
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
                
                MAX_LLM_CALLS = 10
                if len(df_analizar) > MAX_LLM_CALLS:
                    df_analizar = pre_ranking_heuristico(df_analizar, st.session_state["texto_cv_usuario"]).head(MAX_LLM_CALLS)
                
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
                
                # Modificación: Ordenamiento explícito restringido al Top 10 Real de Match
                df_resultados = pd.DataFrame(resultados_analisis).sort_values(by="match_score", ascending=False).head(10).reset_index(drop=True)
                
                st.success("¡Análisis de compatibilidad finalizado!")
                
                for idx, res in df_resultados.iterrows():
                    score = res["match_score"]
                    color_badge = "#2ecc71" if score >= 70 else ("#f39c12" if score >= 45 else "#e74c3c")
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
    main()
