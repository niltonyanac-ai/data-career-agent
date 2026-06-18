import streamlit as pd  # Importación base para la UI
import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from pydantic import BaseModel, Field

# =====================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y ESTILOS
# =====================================================================
st.set_page_config(
    page_title="DataCareer AI",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyección de CSS personalizado para evitar "look aplanado" y estilizar tarjetas
st.markdown("""
<style>
    .match-card {
        border: 1px solid #e2e8f0; 
        padding: 20px; 
        border-radius: 10px; 
        margin-bottom: 20px; 
        background-color: #ffffff;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .main-title {
        color: #1e3a8a;
        font-weight: 800;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# 2. DEFINICIÓN DE ESQUEMAS ESTRUCTURADOS (PYDANTIC)
# =====================================================================
class EvaluacionMatch(BaseModel):
    """Esquema estricto para forzar el rigor en la evaluación del modelo AI."""
    match_score: int = Field(
        ..., 
        description="Porcentaje de match real entre el CV y la vacante, de 0 a 100 basado estrictamente en requisitos explicitados."
    )
    justificacion: str = Field(
        ..., 
        description="Explicación detallada y objetiva de por qué se asignó ese puntaje, mencionando vacíos de habilidades si los hay."
    )
    habilidades_coincidentes: list[str] = Field(
        ..., 
        description="Lista de hard y soft skills que el candidato SÍ cumple de forma demostrable en su CV para esta oferta."
    )
    habilidades_faltantes: list[str] = Field(
        ..., 
        description="Lista de tecnologías o requisitos críticos que solicita la oferta pero el CV NO menciona."
    )

# =====================================================================
# 3. CAPA DE INTELIGENCIA Y PROCESAMIENTO (BACKEND)
# =====================================================================
def normalizar_jerarquia(texto):
    """Mapeo semántico de 6 niveles ampliado para evitar agrupaciones erróneas."""
    if pd.isna(texto):
        return "2. Analista / Profesional"
    
    t = str(texto).lower().strip()
    
    # 1. Practicante / Asistente / Trainee
    if any(x in t for x in ["practicante", "asistente", "intern", "trainee", "pasantia", "pasantía", "becario"]):
        return "1. Practicante / Asistente"
    
    # 6. Gerente / Head / Director
    elif any(x in t for x in ["gerente", "manager", "head", "director", "vicedirector", "chief", "cdo", "cto", "ceo"]):
        return "6. Gerente / Head"
    
    # 5. Sub Gerente / Product Owner / Scrum Master
    elif any(x in t for x in ["subgerente", "sub gerente", "sub-gerente", "product owner", "po", "scrum"]):
        return "5. Sub Gerente / P.O."
    
    # 4. Líder / Jefe / Supervisor
    elif any(x in t for x in ["lider", "líder", "jefe", "jefatura", "lead", "supervisor", "coordinador"]):
        return "4. Líder / Jefe"
    
    # 3. Analista Senior / Especialista / Ssr avanzado
    elif any(x in t for x in ["senior", "sr", "especialista", "advanced", "ssr", "semi-senior", "semisenior"]):
        return "3. Analista Senior / Especialista"
    
    # 2. Analista Junior / Analista Base
    else:
        if "junior" in t or "jr" in t:
            return "2. Analista Junior"
        return "2. Analista / Profesional"


def evaluar_cv_contra_vacante(texto_cv, fila_vacante, modelo="gemini-1.5-flash"):
    """Compara semánticamente el CV contra una vacante usando penalización estricta."""
    detalles_oferta = f"""
    Título del Puesto: {fila_vacante.get('titulo', 'No especificado')}
    Especialidad: {fila_vacante.get('especialidad_objetivo', 'No especificado')}
    Jerarquía: {fila_vacante.get('jerarquia', 'No especificado')}
    Descripción y Requisitos: {fila_vacante.get('descripcion', 'No especificada')}
    """
    
    prompt_sistema = """
    Eres un validador ATS (Applicant Tracking System) experto en reclutamiento para Data, Analítica e IA. 
    Tu objetivo es calcular el porcentaje de compatibilidad (Match Score) real entre un CV y una vacante.
    
    CRITERIOS ESTRICTOS DE CALIFICACIÓN:
    - Sé sumamente riguroso. Un match del 100% SOLO existe si el candidato cumple de forma idéntica con absolutamente todos los requisitos.
    - Si la oferta pide una tecnología clave (ej. SQL, Python, Power BI, AWS, Spark) y esta NO figura en el CV, debes penalizar el 'match_score' restando de 15 a 25 puntos por cada ausencia.
    - No asumas conocimiento. Si el CV no menciona una herramienta, se asume que no la domina.
    """
    
    prompt_usuario = f"""
    CONTEXTO DE LA OFERTA DE EMPLEO:
    {detalles_oferta}
    
    -----------------------------------------------------------------------
    TEXTO EXTRAÍDO DEL CV DEL CANDIDATO:
    {texto_cv}
    
    -----------------------------------------------------------------------
    Analiza detalladamente ambos textos y genera tu respuesta estructurada respetando estrictamente el esquema JSON solicitado.
    """
    
    try:
        model = genai.GenerativeModel(
            model_name=modelo,
            system_instruction=prompt_sistema
        )
        
        response = model.generate_content(
            prompt_usuario,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=EvaluacionMatch,
                temperature=0.1  # Temperatura baja para garantizar reproducibilidad y rigor
            )
        )
        return json.loads(response.text)

    except Exception as e:
        # Fallback seguro contra fallos de cuotas o API (Evita el 100% por defecto)
        return {
            "match_score": 0,
            "justificacion": f"Error técnico de evaluación: {str(e)}",
            "habilidades_coincidentes": [],
            "habilidades_faltantes": []
        }

# =====================================================================
# 4. FLUJO DE CARGA Y SIMULACIÓN DE DATOS (SUPABASE INTERFACE)
# =====================================================================
@st.cache_data(ttl=600)
def cargar_datos_seguros():
    """Simulación segura de la carga desde Supabase (Poblar con tu cliente real)."""
    # NOTA: Reemplazar con tu query real: supabase.table('ofertas').select('*').execute()
    # Aquí simulamos una estructura limpia preservando los enlaces originales.
    datos_prueba = [
        {"titulo": "Data Scientist Senior", "empresa": "Inetum", "jerarquia": "Senior", "especialidad_objetivo": "Data Science", "pais": "Perú", "descripcion": "Reiere Python, SQL, AWS, Machine Learning.", "link_oferta": "https://www.linkedin.com/jobs/view/1"},
        {"titulo": "Analista de Business Intelligence", "empresa": "NTT DATA", "jerarquia": "Analista", "especialidad_objetivo": "Business Intelligence", "pais": "Colombia", "descripcion": "Experiencia avanzada en Power BI, SQL y ETL.", "link_oferta": "https://www.linkedin.com/jobs/view/2"},
        {"titulo": "Gerente de Analítica de Datos", "empresa": "Mindrift", "jerarquia": "Gerente", "especialidad_objetivo": "Data Management", "pais": "Chile", "descripcion": "Liderazgo de equipos, Gobierno de Datos, Estrategia cloud.", "link_oferta": "https://www.linkedin.com/jobs/view/3"},
        {"titulo": "Practicante de IA y Modelado", "empresa": "Tata Consultancy", "jerarquia": "Practicante", "especialidad_objetivo": "Artificial Intelligence", "pais": "Perú", "descripcion": "Estudiante de estadística o sistemas. Python básico.", "link_oferta": "https://www.linkedin.com/jobs/view/4"}
    ]
    return pd.DataFrame(datos_prueba)

# Carga inicial de datos de la vacante
df_raw = cargar_datos_seguros()

if df_raw.empty:
    st.warning("No se encontraron ofertas disponibles en la base de datos de Supabase.")
    st.stop()

# --- PROCESAMIENTO Y LIMPIEZA INICIAL ---
df_vacantes = df_raw.copy()

# Apertura dinámica de Países (Evita sobreescribir todo con 'Perú')
if 'pais' not in df_vacantes.columns:
    df_vacantes['pais'] = 'Perú'
else:
    df_vacantes['pais'] = df_vacantes['pais'].fillna('Latam / Remoto').astype(str).str.title()

# Aplicación de la jerarquía enriquecida de 6 niveles
df_vacantes['jerarquia_limpia'] = df_vacantes['jerarquia'].apply(normalizar_jerarquia)

# =====================================================================
# 5. INTERFAZ DE USUARIO (UX/UI STREAMLIT)
# =====================================================================

# --- BARRA LATERAL: FILTROS GLOBALES ---
st.sidebar.header("🎯 Filtros del Mercado")

lista_paises = sorted(df_vacantes['pais'].unique())
paises_seleccionados = st.sidebar.multiselect("País / Región", options=lista_paises, default=lista_paises[:1])

lista_jerarquias = sorted(df_vacantes['jerarquia_limpia'].unique())
jerarquias_seleccionadas = st.sidebar.multiselect("Nivel de Jerarquía / Seniority", options=lista_jerarquias, default=lista_jerarquias)

# Filtrado reactivo en tiempo real
df_filtrado = df_vacantes[
    (df_vacantes['pais'].isin(paises_seleccionados)) & 
    (df_vacantes['jerarquia_limpia'].isin(jerarquias_seleccionadas))
]

# --- CUERPO PRINCIPAL ---
st.markdown("<h1 class='main-title'>💼 DataCareer AI</h1>", unsafe_allow_html=True)
st.write("Encuentra y evalúa tu perfil contra las mejores oportunidades del mercado en tiempo real.")

# KPIs principales superiores
col1, col2, col3 = st.columns(3)
col1.metric("Ofertas Vigentes Filtradas", len(df_filtrado))
col2.metric("Última Actualización del Pipeline", "18/06/2026 17:42")
col3.metric("Cobertura de Perfiles", "100% Automatizada")

# Creación de Pestañas
tab_mercado, tab_evaluador = st.tabs(["📊 Tablero del Mercado", "🔍 Evaluador ATS de CV"])

with tab_mercado:
    st.subheader("Análisis de Demanda Real y Competencias Clave")
    if not df_filtrado.empty:
        # Gráfico rápido de distribución por jerarquía corregida
        st.bar_chart(df_filtrado['jerarquia_limpia'].value_counts())
        st.dataframe(df_filtrado[['titulo', 'empresa', 'pais', 'jerarquia_limpia']], use_container_width=True)
    else:
        st.info("No hay registros que coincidan con los filtros seleccionados en la barra lateral.")

with tab_evaluador:
    st.subheader("🤖 Escáner de Compatibilidad ATS por Inteligencia Artificial")
    st.write("Sube tu CV en formato de texto plano para contrastarlo contra las vacantes filtradas.")
    
    # Entrada de texto del CV (Reemplazable por st.file_uploader y extractor de PDF)
    texto_cv_usuario = st.text_area("Carga o pega el texto de tu Currículum Vitae aquí:", height=150)
    
    if st.button("🚀 Ejecutar Match Inteligente"):
        if not texto_cv_usuario.strip():
            st.error("Por favor, ingresa el contenido de tu CV para realizar la simulación semántica.")
        elif df_filtrado.empty:
            st.error("No hay vacantes en la vista filtrada para comparar. Ajusta los filtros de la barra lateral.")
        else:
            resultados_analisis = []
            
            with st.spinner("Extrayendo semántica y comparando con Supabase Engine rigurosamente..."):
                # Iteración limpia e independiente fila por fila
                for _, fila in df_filtrado.iterrows():
                    evaluacion = evaluar_cv_contra_vacante(texto_cv_usuario, fila)
                    
                    resultados_analisis.append({
                        "titulo": fila.get("titulo"),
                        "empresa": fila.get("empresa"),
                        "link": fila.get("link_oferta"),
                        "match_score": evaluacion.get("match_score", 0),
                        "justificacion": evaluacion.get("justificacion", "Sin justificación."),
                        "coincidentes": evaluacion.get("habilidades_coincidentes", []),
                        "faltantes": evaluacion.get("habilidades_faltantes", [])
                    })
            
            # Ordenar de forma descendente por el valor del Match Score Real
            df_resultados = pd.DataFrame(resultados_analisis).sort_values(by="match_score", ascending=False)
            
            # Renderizado Dinámico de Resultados
            st.success("¡Análisis completado con éxito! Listado ordenado por afinidad real:")
            
            for _, res in df_resultados.iterrows():
                score = res["match_score"]
                # Color dinámico condicional basado en severidad
                color_badge = "#2ecc71" if score >= 75 else ("#f39c12" if score >= 45 else "#e74c3c")
                
                # Renderizado HTML inyectado estructurado
                st.markdown(f"""
                <div class="match-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0; color: #1e3a8a;">{res['titulo']} <span style="color: #6b7280; font-size: 0.85em;">({res['empresa']})</span></h4>
                        <span style="background-color: {color_badge}; color: white; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 0.9em;">
                            {score}% Match
                        </span>
                    </div>
                    <p style="margin-top: 12px; font-size: 0.95em; color: #374151;"><strong>Análisis Estratégico ATS:</strong> {res['justificacion']}</p>
                    <p style="font-size: 0.9em; color: #16a34a; margin-bottom: 4px;"><strong>✓ Habilidades Coincidentes:</strong> {', '.join(res['coincidentes']) if res['coincidentes'] else 'Ninguna detectada explícitamente.'}</p>
                    <p style="font-size: 0.9em; color: #dc2626; margin-bottom: 0px;"><strong>✗ Brechas Técnicas Detectadas:</strong> {', '.join(res['faltantes']) if res['faltantes'] else 'Ninguna brecha crítica encontrada.'}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Colocación limpia del botón de salida externa (Conserva el Link original de LinkedIn)
                if res["link"]:
                    st.link_button(f"🎯 Ver vacante activa de {res['empresa']}", url=res["link"])
                    st.markdown("<br>", unsafe_allow_html=True)
