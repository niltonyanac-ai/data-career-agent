import streamlit as st
import pandas as pd
import json
import altair as alt
from datetime import datetime, timezone
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List
from supabase import create_client, Client

# Configuración del ecosistema visual de la aplicación
st.set_page_config(
    page_title="DataCareer AI - Monitor de Empleabilidad", 
    layout="wide", 
    page_icon="💼"
)

# Inyección de estilos usando st.html (evita el bug de métricas de st.markdown)
st.html("""
<style>
    .main-title { font-size: 2.6rem; font-weight: 800; color: #1E293B; margin-bottom: 0.5rem; }
    .subtitle { font-size: 1.2rem; color: #64748B; margin-bottom: 2rem; }
    .kpi-container { background-color: #F8FAFC; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid #E2E8F0; }
</style>
""")

# --- Modelado de Datos para Gemini 2.5 Flash ---
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str
    skills_faltantes: List[str]

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# --- Conexión Segura y Recuperación de Datos ---
@st.cache_data(ttl=300, show_spinner="Sincronizando ofertas del mercado de tecnología...")
def obtener_data_real():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(url, key)
        
        respuesta = supabase.table("vacantes").select("*").execute()
        df = pd.DataFrame(respuesta.data)
        if not df.empty and 'fecha_creacion' in df.columns:
            df['fecha_creacion'] = pd.to_datetime(df['fecha_creacion'])
        return df
    except Exception as e:
        st.error(f"Error de conexión con Supabase: {e}")
        return pd.DataFrame()

df_vacantes = obtener_data_real()

# --- Encabezado Principal Orientado a la Conversión (UX Vendedora) ---
st.markdown('<div class="main-title">💼 DataCareer AI</div>', unsafe_allowed_html=True)
st.markdown(
    '<div class="subtitle">Encuentra y evalúa tu perfil contra las mejores oportunidades del mercado de Datos, Analítica y Business Intelligence en tiempo real.</div>', 
    unsafe_allowed_html=True
)

if df_vacantes.empty:
    st.info("Sincronizando el flujo de datos inicial... Asegúrate de poblar Supabase a través del Scraper.")
else:
    # Métricas de Impacto Requeridas
    total_ofertas = len(df_vacantes)
    ultima_act = df_vacantes['fecha_creacion'].max().strftime('%d/%m/%Y %H:%M')
    
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        st.metric(label="📊 Ofertas Vigentes Procesadas (Últimos 30 días)", value=total_ofertas, help="Mínimo objetivo del sistema: > 160 ofertas concurrentes.")
    with col_kpi2:
        st.metric(label="🔄 Última Actualización del Pipeline", value=ultima_act)
    with col_kpi3:
        st.metric(label="🎯 Cobertura de Perfiles", value="100% Automatizada")

    # --- Filtros en Barra Lateral ---
    st.sidebar.header("🎯 Filtros del Mercado")
    especialidades = sorted(df_vacantes['especialidad'].unique().tolist())
    esp_sel = st.sidebar.selectbox("Especialidad Objetivo", ["Todas"] + list(especialidades))
    
    jerarquias = sorted(df_vacantes['jerarquia'].unique().tolist())
    jer_sel = st.sidebar.multiselect("Nivel de Jerarquía / Seniority", jerarquias, default=jerarquias)
    
    # Filtrado Dinámico usando .copy() para evitar SettingWithCopyWarning
    df_filtrado = df_vacantes[df_vacantes['jerarquia'].isin(jer_sel)].copy()
    if esp_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado['especialidad'] == esp_sel]

    # --- Estructura de Pestañas ---
    tab_mercado, tab_evaluador = st.tabs(["📊 Tablero del Mercado", "🔍 Evaluador ATS de CV"])
    
    with tab_mercado:
        st.subheader("Análisis de Demanda Real y Competencias Clave")
        
        if not df_filtrado.empty:
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                # 1. Gráfico de Niveles Jerárquicos
                st.markdown("**Distribución de Ofertas por Seniority**")
                chart_jer = alt.Chart(df_filtrado).mark_bar(cornerRadiusTopRight=4).encode(
                    x=alt.X('count():Q', title='Cantidad de Vacantes'),
                    y=alt.Y('jerarquia:N', sort='-x', title='Nivel Jerárquico'),
                    color=alt.Color('jerarquia:N', scale=alt.Scale(scheme='tableau10'), legend=None)
                ).properties(height=220)
                st.altair_chart(chart_jer, use_container_width=True)
                
                # 2. Antigüedad de las Ofertas (Seguro gracias al .copy() previo)
                st.markdown("**Antigüedad de Publicación (Días transcurridos)**")
                df_filtrado['dias_antiguedad'] = (datetime.now(timezone.utc) - df_filtrado['fecha_creacion']).dt.days
                chart_ant = alt.Chart(df_filtrado).mark_bar(color='#475569').encode(
                    x=alt.X('dias_antiguedad:O', title='Días de Antigüedad'),
                    y=alt.Y('count():Q', title='Número de Ofertas')
                ).properties(height=180)
                st.altair_chart(chart_ant, use_container_width=True)

            with col_g2:
                # 3. Top 10 Empresas Contratantes
                st.markdown("**Top 10 Líderes de Contratación**")
                top_empresas = df_filtrado['empresa'].value_counts().reset_index().head(10)
                top_empresas.columns = ['empresa', 'count']
                chart_emp = alt.Chart(top_empresas).mark_bar(color='#0EA5E9').encode(
                    x=alt.X('count:Q', title='Vacantes Activas'),
                    y=alt.Y('empresa:N', sort='-x', title='Empresa')
                ).properties(height=220)
                st.altair_chart(chart_emp, use_container_width=True)
                
                # 4. Análisis Agregado de Hard Skills Demandadas
                st.markdown("**Top de Tecnologías y Hard Skills más Pedidas**")
                skills_series = df_filtrado['hard_skills'].explode().value_counts().reset_index().head(8)
                skills_series.columns = ['Skill', 'Frecuencia']
                chart_skills = alt.Chart(skills_series).mark_bar(color='#10B981').encode(
                    x=alt.X('Frecuencia:Q', title='Menciones en Ofertas'),
                    y=alt.Y('Skill:N', sort='-x', title='Tecnología')
                ).properties(height=180)
                st.altair_chart(chart_skills, use_container_width=True)

            # Vista detallada de Datos
            st.markdown("### 📋 Listado de Posiciones del Mercado Filtrado")
            st.dataframe(
                df_filtrado[['puesto', 'empresa', 'especialidad', 'jerarquia', 'link']],
                use_container_width=True,
                column_config={"link": st.column_config.LinkColumn("Enlace Postulación")}
            )
        else:
            st.warning("No hay registros disponibles para los filtros de búsqueda seleccionados.")
            
    with tab_evaluador:
        st.subheader("🤖 Escáner de Compatibilidad ATS por Inteligencia Artificial")
        st.markdown("Sube tu CV para contrastarlo en tiempo real mediante IA con las palabras clave e intenciones de búsqueda de nuestro mercado indexado.")
        
        # Ajustado a formatos con extracción de texto nativa garantizada
        archivo_cv = st.file_uploader("Carga tu Currículum Vitae", type=["pdf", "txt"])
        
        if archivo_cv and not df_filtrado.empty:
            if st.button("🚀 Ejecutar Match Inteligente"):
                with st.spinner("Extrayendo semántica y comparando con Supabase Engine..."):
                    try:
                        # --- Extracción de texto multi-formato ---
                        texto_cv = ""
                        nombre_archivo = archivo_cv.name.lower()
                        
                        if nombre_archivo.endswith('.pdf'):
                            lector = PdfReader(archivo_cv)
                            for pagina in lector.pages:
                                texto_cv += pagina.extract_text() or ""
                        elif nombre_archivo.endswith('.txt'):
                            texto_cv = archivo_cv.read().decode("utf-8")
                        
                        if len(texto_cv.strip()) < 50:
                            st.error("No se pudo extraer suficiente texto legible de tu documento. Por favor, verifica que no sea una imagen escaneada.")
                            st.stop()

                        # Preparar payload de vacantes reducido y blindado contra nulos
                        contexto_vacantes = []
                        for _, row in df_filtrado.iterrows():
                            id_seguro = int(row['id']) if pd.notnull(row['id']) else 0
                            contexto_vacantes.append({
                                "id": id_seguro,
                                "puesto": str(row['puesto']),
                                "empresa": str(row['empresa']),
                                "hard_skills": row['hard_skills'] if isinstance(row['hard_skills'], list) else [],
                                "soft_skills": row['soft_skills'] if isinstance(row['soft_skills'], list) else []
                            })
                        
                        # Instanciar cliente oficial Google GenAI
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
                        
                        # Procesamiento de Resultados
                        resultados = json.loads(response.text)
                        df_evaluaciones = pd.DataFrame(resultados["evaluaciones"])
                        
                        if not df_evaluaciones.empty:
                            df_final = df_filtrado.merge(df_evaluaciones, left_on='id', right_on='id_interno')
                            # Filtro estricto del requerimiento: Match mayor o igual al 70%
                            df_final = df_final[df_final['match_score'] >= 70]
                            df_final = df_final.sort_values(by='match_score', ascending=False)
                            
                            st.markdown("### 🎯 Ofertas Afines Recomendadas (>70% Match)")
                            
                            if df_final.empty:
                                st.info("Se completó el análisis, pero ninguna vacante actual cumple con el umbral del 70% de afinidad estructural.")
                            else:
                                for _, rank in df_final.iterrows():
                                    with st.expander(f"🟢 {rank['match_score']}% Match — {rank['puesto']} en {rank['empresa']}"):
                                        st.write(f"**💼 Especialidad:** {rank['especialidad']} | **🎯 Jerarquía:** {rank['jerarquia']}")
                                        st.info(f"**Coincidencias Identificadas:** {rank['coincidencias']}")
                                        if rank['skills_faltantes']:
                                            st.warning(f"**Gaps identified (Habilidades recomendadas a adquirir):** {', '.join(rank['skills_faltantes'])}")
                                        st.markdown(f"[👉 Postular Directamente en LinkedIn]({rank['link']})")
                        else:
                            st.warning("El motor cognitivo no pudo correlacionar la matriz del perfil.")
                    except Exception as ex:
                        st.error(f"Error crítico en el motor de inferencia IA: {ex}")
