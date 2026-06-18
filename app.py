import streamlit as st
import pandas as pd
import json
import altair as alt
import os
from datetime import datetime, timezone
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List
from supabase import create_client, Client

# --- CONFIGURACIÓN DEL ECOSISTEMA VISUAL ---
st.set_page_config(
    page_title="Tu Agente IA de Empleo en Tiempo Real", 
    layout="wide", 
    page_icon="💼"
)

# Inyección de estilos CSS estables (Blindado contra bugs de st.markdown)
st.html("""
<style>
    .main-title { font-size: 2.6rem; font-weight: 800; color: #1E293B; margin-bottom: 0.5rem; }
    .subtitle { font-size: 1.2rem; color: #64748B; margin-bottom: 2rem; }
    .kpi-container { background-color: #F8FAFC; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid #E2E8F0; }
</style>
""")

# --- MODELADO DE DATOS ESTRUCTURADOS (PYDANTIC) PARA GEMINI 2.5 FLASH ---
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str
    skills_faltantes: List[str]

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# --- RECUPERACIÓN DE DATOS DESDE SUPABASE ---
@st.cache_data(ttl=300, show_spinner="Sincronizando ofertas del mercado de tecnología...")
def obtener_data_real():
    try:
        url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
        if not url or not key:
            st.error("Faltan las credenciales de Supabase en secrets o variables de entorno.")
            return pd.DataFrame()
        
        supabase: Client = create_client(url, key)
        respuesta = supabase.table("vacantes").select("*").execute()
        df = pd.DataFrame(respuesta.data)
        if not df.empty and 'fecha_creacion' in df.columns:
            df['fecha_creacion'] = pd.to_datetime(df['fecha_creacion'])
        return df
    except Exception as e:
        st.error(f"Error de conexión con Supabase Engine: {e}")
        return pd.DataFrame()

df_vacantes = obtener_data_real()

# --- ARQUITECTURA DE NORMALIZACIÓN DE JERARQUÍAS (6 NIVELES DE MERCADO) ---
def normalizar_jerarquia(texto):
    if pd.isna(texto):
        return "2. Analista Junior / Analista"
    t = str(texto).lower()
    
    if any(x in t for x in ["practicante", "asistente", "intern", "trainee", "pasantía"]):
        return "1. Practicante / Asistente"
    elif any(x in t for x in ["senior", "sr", "especialista", "coordinador", "advanced", "ssr"]):
        return "3. Analista Senior / Especialista / Coordinador"
    elif any(x in t for x in ["lider", "líder", "jefe", "jefatura", "lead", "supervisor"]):
        return "4. Líder / Jefe"
    elif any(x in t for x in ["subgerente", "sub gerente", "sub-gerente", "product owner", "po"]):
        return "5. Sub Gerente / P.O."
    elif any(x in t for x in ["gerente", "manager", "head", "director", "vicedirector", "chief"]):
        return "6. Gerente / Head"
    else:
        return "2. Analista Junior / Analista"

# --- ENCABEZADO UX ---
st.html("""
    <div class="main-title">💼 DataCareer AI</div>
    <div class="subtitle">Encuentra y evalúa tu perfil contra las mejores oportunidades del mercado de Datos, Analítica y Business Intelligence en tiempo real.</div>
""")

if df_vacantes.empty:
    st.info("Sincronizando el flujo de datos inicial... Asegúrate de poblar Supabase a través del Scraper.")
else:
    # Pre-procesamiento y consistencia de variables añadidas
    df_vacantes['jerarquia_limpia'] = df_vacantes['jerarquia'].apply(normalizar_jerarquia)
    if 'pais' not in df_vacantes.columns:
        df_vacantes['pais'] = 'Perú'

    # --- BARRA LATERAL: FILTROS DINÁMICOS COMPLETOS ---
    st.sidebar.header("🎯 Filtros del Mercado")
    
    paises_disponibles = sorted(df_vacantes['pais'].unique().tolist())
    paises_sel = st.sidebar.multiselect("País / Región", options=paises_disponibles, default=paises_disponibles)
    
    especialidades = sorted(df_vacantes['especialidad'].dropna().unique().tolist())
    esp_sel = st.sidebar.selectbox("Especialidad Objetivo", ["Todas"] + list(especialidades))
    
    jerarquias_disponibles = sorted(df_vacantes['jerarquia_limpia'].unique().tolist())
    jer_sel = st.sidebar.multiselect("Nivel de Jerarquía / Seniority", options=jerarquias_disponibles, default=jerarquias_disponibles)
    
    # Segmentación cruzada en tiempo real
    df_filtrado = df_vacantes[
        (df_vacantes['jerarquia_limpia'].isin(jer_sel)) & 
        (df_vacantes['pais'].isin(paises_sel))
    ].copy()
    if esp_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado['especialidad'] == esp_sel]

    # --- MÉTRICAS DE IMPACTO TOTALMENTE DINÁMICAS ---
    total_ofertas_filtradas = len(df_filtrado)
    ultima_act = df_vacantes['fecha_creacion'].max().strftime('%d/%m/%Y %H:%M') if not df_vacantes['fecha_creacion'].isna().all() else "Sincronizado"
    
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        st.metric(label="📊 Ofertas Vigentes Filtradas", value=total_ofertas_filtradas, help="Muestra el conteo exacto interactivo según los filtros aplicados.")
    with col_kpi2:
        st.metric(label="🔄 Última Actualización del Pipeline", value=ultima_act)
    with col_kpi3:
        st.metric(label="🎯 Cobertura de Perfiles", value="100% Automatizada")

    # --- PESTAÑAS DEL MVP ---
    tab_mercado, tab_evaluador = st.tabs(["📊 Tablero del Mercado", "🔍 Evaluador ATS de CV"])
    
    # ==============================================================================
    # PESTAÑA 1: TABLERO ANALÍTICO DEL MERCADO
    # ==============================================================================
    with tab_mercado:
        st.subheader("Análisis de Demanda Real y Competencias Clave")
        if not df_filtrado.empty:
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                # 1. Gráfico de Distribución Jerárquica Normalizada
                st.markdown("**Distribución de Ofertas por Seniority (Mapeado Profesional)**")
                chart_jer = alt.Chart(df_filtrado).mark_bar(cornerRadiusTopRight=4).encode(
                    x=alt.X('count():Q', title='Cantidad de Vacantes'),
                    y=alt.Y('jerarquia_limpia:N', sort='x', title='Nivel Jerárquico'),
                    color=alt.Color('jerarquia_limpia:N', scale=alt.Scale(scheme='tableau10'), legend=None)
                ).properties(height=220)
                st.altair_chart(chart_jer, use_container_width=True)
                
                # 2. Reemplazo Estratégico: Top 5 Soft Skills
                st.markdown("**Top 5 Soft Skills más Solicitadas por la Industria**")
                if 'soft_skills' in df_filtrado.columns:
                    df_soft = df_filtrado.explode('soft_skills')
                    df_soft_counts = df_soft['soft_skills'].value_counts().reset_index().head(5)
                    df_soft_counts.columns = ['Soft Skill', 'Frecuencia']
                    chart_soft = alt.Chart(df_soft_counts).mark_bar(color='#FF9800', cornerRadiusTopRight=4).encode(
                        x=alt.X('Frecuencia:Q', title='Demanda en Ofertas'),
                        y=alt.Y('Soft Skill:N', sort='-x', title='Habilidad Blanda')
                    ).properties(height=180)
                    st.altair_chart(chart_soft, use_container_width=True)

            with col_g2:
                # 3. Forzado Explícito: Top 10 Empresas Contratantes
                st.markdown("**Top 10 Líderes de Contratación**")
                top_empresas = df_filtrado['empresa'].value_counts().reset_index().head(10)
                top_empresas.columns = ['empresa', 'count']
                chart_emp = alt.Chart(top_empresas).mark_bar(color='#0EA5E9', cornerRadiusTopRight=4).encode(
                    x=alt.X('count:Q', title='Vacantes Activas'),
                    y=alt.Y('empresa:N', sort='-x', title='Empresa')
                ).properties(height=220)
                st.altair_chart(chart_emp, use_container_width=True)
                
                # 4. Análisis de Hard Skills
                st.markdown("**Top de Tecnologías y Hard Skills más Pedidas**")
                if 'hard_skills' in df_filtrado.columns:
                    skills_series = df_filtrado['hard_skills'].explode().value_counts().reset_index().head(8)
                    skills_series.columns = ['Skill', 'Frecuencia']
                    chart_skills = alt.Chart(skills_series).mark_bar(color='#10B981', cornerRadiusTopRight=4).encode(
                        x=alt.X('Frecuencia:Q', title='Menciones en Ofertas'),
                        y=alt.Y('Skill:N', sort='-x', title='Tecnología')
                    ).properties(height=180)
                    st.altair_chart(chart_skills, use_container_width=True)

            # Dataframe Detallado Completo
            st.markdown("### 📋 Listado de Posiciones del Mercado Filtrado")
            st.dataframe(
                df_filtrado[['puesto', 'empresa', 'especialidad', 'jerarquia_limpia', 'link']],
                use_container_width=True,
                column_config={"link": st.column_config.LinkColumn("Enlace Postulación")}
            )
        else:
            st.warning("No hay registros disponibles para los filtros de búsqueda seleccionados.")
            
    # ==============================================================================
    # PESTAÑA 2: MOTOR INTEGRAL DE EVALUACIÓN ATS CON COGNICIÓN IA (OPTIMIZADO)
    # ==============================================================================
    with tab_evaluador:
        st.subheader("🤖 Escáner de Compatibilidad ATS por Inteligencia Artificial")
        st.markdown("Sube tu CV para contrastarlo en tiempo real mediante IA con las palabras clave e intenciones de búsqueda del mercado.")
        
        archivo_cv = st.file_uploader("Carga tu Currículum Vitae", type=["pdf", "txt"])
        
        if archivo_cv and not df_filtrado.empty:
            if st.button("🚀 Ejecutar Match Inteligente"):
                with st.spinner("Extrayendo semántica y comparando con Supabase Engine..."):
                    try:
                        # --- Extractor de texto multi-formato nativo ---
                        texto_cv = ""
                        nombre_archivo = archivo_cv.name.lower()
                        
                        if nombre_archivo.endswith('.pdf'):
                            lector = PdfReader(archivo_cv)
                            for pagina in lector.pages:
                                texto_cv += pagina.extract_text() or ""
                        elif nombre_archivo.endswith('.txt'):
                            texto_cv = archivo_cv.read().decode("utf-8")
                        
                        if len(texto_cv.strip()) < 50:
                            st.error("Texto legible insuficiente. Verifica que tu documento no sea una imagen escaneada.")
                            st.stop()

                        # Construcción del payload compacto blindado contra nulos e índices inconsistentes
                        contexto_vacantes = []
                        for _, row in df_filtrado.iterrows():
                            id_seguro = int(row['id']) if ('id' in row and pd.notnull(row['id'])) else int(row.name)
                            contexto_vacantes.append({
                                "id": id_seguro,
                                "puesto": str(row['puesto']),
                                "empresa": str(row['empresa']),
                                "hard_skills": row['hard_skills'] if ('hard_skills' in row and isinstance(row['hard_skills'], list)) else [],
                                "soft_skills": row['soft_skills'] if ('soft_skills' in row and isinstance(row['soft_skills'], list)) else []
                            })
                        
                        # Instanciación oficial del SDK Google GenAI
                        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                        
                        prompt = f"""
                        Actúa como un validador de ATS corporativo estricto y experto en reclutamiento técnico.
                        Analiza el siguiente Currículum Vitae frente a la lista de vacantes provistas.
                        
                        REGLAS DE EVALUACIÓN:
                        1. Calcula el 'match_score' de 0 a 100 evaluando la coincidencia real de Hard y Soft Skills.
                        2. Sé sumamente riguroso: si el CV carece de las tecnologías core de la vacante, el score debe caer drásticamente por debajo de 50.
                        3. Extrae de forma explícita las habilidades faltantes que el candidato debería aprender para esa posición.
                        
                        CV del Candidato:
                        {texto_cv}
                        
                        Lista de Vacantes Indexadas:
                        {json.dumps(contexto_vacantes)}
                        """
                        
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=RespuestaMatchIA,
                                temperature=0.1
                            ),
                        )
                        
                        # Procesamiento analítico y cruce estructurado de la inferencia de IA
                        resultados = json.loads(response.text)
                        df_evaluaciones = pd.DataFrame(resultados["evaluaciones"])
                        
                        if not df_evaluaciones.empty:
                            # Cruce seguro manejando la presencia o ausencia de la columna 'id' nativa
                            if 'id' in df_filtrado.columns:
                                df_final = df_filtrado.merge(df_evaluaciones, left_on='id', right_on='id_interno')
                            else:
                                df_filtrado['id_index'] = df_filtrado.index
                                df_final = df_filtrado.merge(df_evaluaciones, left_on='id_index', right_on='id_interno')
                            
                            # Mantener lógica original: Ordenar por afinidad y extraer estrictamente el TOP 10 de mayor Match
                            df_final = df_final.sort_values(by='match_score', ascending=False).head(10)
                            
                            st.markdown("### 🎯 Top 10 Ofertas más Relevantes según tu CV")
                            
                            for _, rank in df_final.iterrows():
                                # Sistema de color por umbrales dinámicos del código original
                                color_tag = "🟢" if rank['match_score'] >= 70 else "🟡" if rank['match_score'] >= 45 else "🔴"
                                
                                with st.expander(f"{color_tag} {rank['match_score']}% Match — {rank['puesto']} en {rank['empresa']}"):
                                    st.write(f"**💼 Especialidad:** {rank['especialidad']} | **🎯 Jerarquía:** {rank['jerarquia_limpia']}")
                                    st.info(f"**Palabras Clave / Coincidencias Identificadas:** {rank['coincidencias']}")
                                    
                                    if rank['skills_faltantes']:
                                        st.warning(f"**Filtro ATS - Habilidades Críticas Faltantes (Para optimizar tu CV):** {', '.join(rank['skills_faltantes'])}")
                                    
                                    st.markdown(f"[👉 Postular Directamente en el Enlace]({rank['link']})")
                        else:
                            st.warning("El motor cognitivo no pudo correlacionar la matriz del perfil.")
                    except Exception as ex:
                        st.error(f"Error crítico en el motor de inferencia IA: {ex}")
