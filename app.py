import streamlit as st
import pandas as pd
import json
import altair as alt
from datetime import datetime, timedelta
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List
from supabase import create_client, Client

# Configuración del ecosistema visual de la aplicación
st.set_page_config(page_title="DataCareer AI - Plataforma de Empleabilidad", layout="wide", page_icon="💼")

# --- Modelado de Datos Estrictos para la IA ---
class EvaluacionIndividual(BaseModel):
    id_interno: int
    match_score: int
    coincidencias: str

class RespuestaMatchIA(BaseModel):
    evaluaciones: List[EvaluacionIndividual]

# --- Capa de Datos con Caché Resiliente ---
@st.cache_data(ttl=15, show_spinner="Sincronizando el ecosistema analítico...")
def obtener_data_real():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(url, key)
        
        respuesta = supabase.table("vacantes").select("*").execute()
        df = pd.DataFrame(respuesta.data)
        
        if df.empty:
            return pd.DataFrame(columns=['id', 'puesto', 'empresa', 'especialidad', 'jerarquia', 'hard_skills', 'soft_skills', 'link', 'fecha_creacion'])
        
        df['fecha_creacion'] = pd.to_datetime(df['fecha_creacion'])
        return df
    except Exception as e:
        st.error(f"Error de enlace con el repositorio de datos: {e}")
        return pd.DataFrame()

df_raw = obtener_data_real()

# --- Bloque Header Corporativo (Diseño UX/CX Recomendado) ---
st.write("# 💼 DataCareer AI")
st.write("### *Optimización de Perfiles Profesionales en Data, Analytics & Inteligencia Artificial*")
st.markdown(
    """
    Bienvenido a la plataforma avanzada de inteligencia de mercado de talento. Este servicio audita en tiempo real 
    las demandas de contratación en el sector tecnológico y contrasta la arquitectura de tu currículum vitae 
    frente a necesidades de negocio validadas mediante modelos de procesamiento de lenguaje natural (LLM).
    """
)
st.write("---")

if df_raw.empty:
    st.warning("⚠️ Monitoreo temporal fuera de línea. No se registran ofertas analíticas en el almacén central.")
else:
    # --- Barra Lateral Estructurada de Filtros Coherentes ---
    st.sidebar.header("⚙️ Consola de Filtros")
    filtro_esp = st.sidebar.selectbox("Especialidad Analítica", ["Todos"] + sorted(list(df_raw['especialidad'].unique())))
    filtro_jer = st.sidebar.selectbox("Nivel / Jerarquía del Puesto", sorted(list(df_raw['jerarquia'].unique())))
    dias = st.sidebar.slider("Antigüedad de las Ofertas (Días)", 1, 90, 90)
    
    # Procesamiento dinámico del DataFrame bajo demanda
    df_f = df_raw.copy()
    if filtro_esp != "Todos": 
        df_f = df_f[df_f['especialidad'] == filtro_esp]
    
    df_f = df_f[df_f['jerarquia'] == filtro_jer]
        
    limite_tiempo = datetime.now(df_f['fecha_creacion'].dt.tz) - timedelta(days=dias)
    df_f = df_f[df_f['fecha_creacion'] >= limite_tiempo]
    
    # Renderizado dinámico de KPIs del mercado en tiempo real
    total_disponible = len(df_f)
    ultima_act = df_raw['fecha_creacion'].max().strftime('%d/%m/%Y %H:%M')
    
    m1, m2 = st.columns(2)
    with m1:
        st.metric(label="Ofertas Analíticas Disponibles", value=total_disponible)
    with m2:
        st.metric(label="Última Sincronización del Mercado", value=ultima_act)
        
    tab1, tab2 = st.tabs(["📊 Dashboard de Tendencias de Mercado", "🔍 Evaluador de CV por Jerarquía"])

    # ==========================================
    # PESTAÑA 1: VISUALIZACIÓN DE ANALÍTICA AVANZADA
    # ==========================================
    with tab1:
        if df_f.empty:
            st.info("No se registran ofertas que cumplan con la combinación de filtros seleccionada en este momento.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.write("#### Volumen por Especialidad Analítica")
                st.altair_chart(alt.Chart(df_f['especialidad'].value_counts().reset_index()).mark_bar(color='#1f77b4').encode(x='count:Q', y=alt.Y('especialidad:N', sort='-x')), use_container_width=True)
                
                st.write("#### Requerimientos Tecnológicos (Hard Skills)")
                st.altair_chart(alt.Chart(df_f.explode('hard_skills')['hard_skills'].value_counts().reset_index()).mark_bar(color='#aec7e8').encode(x='count:Q', y=alt.Y('hard_skills:N', sort='-x')), use_container_width=True)
            with col2:
                st.write("#### Distribución de Seniority Detectado")
                st.altair_chart(alt.Chart(df_f['jerarquia'].value_counts().reset_index()).mark_bar(color='#ff7f0e').encode(x='count:Q', y=alt.Y('jerarquia:N', sort='-x')), use_container_width=True)
                
                st.write("#### Competencias Blandas Demandadas (Soft Skills)")
                st.altair_chart(alt.Chart(df_f.explode('soft_skills')['soft_skills'].value_counts().reset_index()).mark_bar(color='#ffbb78').encode(x='count:Q', y=alt.Y('soft_skills:N', sort='-x')), use_container_width=True)

            st.write("#### Catálogo Consolidado de Ofertas de Trabajo")
            st.dataframe(
                df_f.drop(columns=['id']).sort_values(by='fecha_creacion', ascending=False), 
                column_config={"link": st.column_config.LinkColumn("Postular", display_text="Ver Oferta")}, 
                use_container_width=True
            )

    # ==========================================
    # PESTAÑA 2: EVALUADOR MATRICIAL DE CV
    # ==========================================
    with tab2:
        st.write(f"#### Evaluando Perfiles exclusivamente para el Nivel: **{filtro_jer}**")
        st.info(f"Nota de UX: Este módulo contrasta tu CV únicamente contra las {len(df_f.head(30))} vacantes filtradas en el panel izquierdo.")
        
        archivo = st.file_uploader("Carga tu Currículum Vitae en formato digital (PDF o TXT)", type=['pdf', 'txt'])
        if archivo:
            if "procesando_cv" not in st.session_state:
                st.session_state.procesando_cv = False

            if st.button("Ejecutar Auditoría de Compatibilidad", disabled=st.session_state.procesando_cv):
                texto = ""
                if archivo.type == "application/pdf":
                    try:
                        reader = PdfReader(archivo)
                        texto = "".join([p.extract_text() for p in reader.pages])
                    except Exception as e:
                        st.error(f"Error en la lectura estructural del PDF: {e}")
                else:
                    texto = archivo.getvalue().decode("utf-8", errors="ignore")
                    
                if texto.strip() == "":
                    st.warning("El documento no posee texto legible. Verifique que no sea un archivo escaneado como imagen.")
                elif df_f.empty:
                    st.warning("No hay un grupo de control de vacantes disponible para la jerarquía seleccionada.")
                else:
                    try:
                        st.session_state.procesando_cv = True
                        cliente = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                        
                        with st.spinner("⚡ Calculando afinidad matricial en el clúster LLM..."):
                            # Ordenamiento estricto por ID para garantizar la invariabilidad del contexto
                            df_ordenado = df_f.sort_values(by='id', ascending=True)
                            contexto_ia = df_ordenado.head(30)[['id', 'puesto', 'jerarquia', 'hard_skills']].to_json(orient='records')
                            cv_recortado = texto[:1800].replace("\n", " ")
                            
                            prompt_algoritmico = (
                                f"Eres un motor matemático frío, determinista y estricto de emparejamiento técnico corporativo.\n"
                                f"Tu tarea es evaluar la afinidad del CV proporcionado contra un catálogo de ofertas del nivel jerárquico: {filtro_jer}.\n\n"
                                f"Entrada de CV Profesional: {cv_recortado}\n"
                                f"Catálogo Base de Ofertas (JSON): {contexto_ia}\n\n"
                                f"REGLAS CRÍTICAS DE CALIBRACIÓN MATEMÁTICA (Match Score del 0 al 100):\n"
                                f"1. Evalúa de forma aislada cada elemento del catálogo respetando su orden por 'id'.\n"
                                f"2. Penalizaciones Obligatorias y Techos de Puntuación:\n"
                                f"   - Si la oferta pertenece a la jerarquía 'Senior' o 'Líder / Jefatura' y el CV no explicita métricas cuantitativas de impacto o más de 5 años dirigiendo áreas analíticas, el match score tiene un techo máximo inamovible de 45%.\n"
                                f"   - Si el puesto es para 'Data Science' y el CV carece de mención explícita a modelos predictivos, álgebra, estadística avanzada o desarrollo estructurado en Python/R, el match score máximo es de 40%.\n"
                                f"3. Restringe las calificaciones superiores al 85% únicamente a perfiles que demuestren simetría total en herramientas especializadas, nivel del puesto y dominio sectorial.\n"
                                f"4. Retorna en la estructura JSON configurada SOLAMENTE aquellos registros cuyo cómputo final sea estrictamente igual o superior al 70%. Sé implacable y consistente."
                            )
                            
                            resp = cliente.models.generate_content(
                                model='gemini-2.5-flash', 
                                contents=prompt_algoritmico,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json", 
                                    response_schema=RespuestaMatchIA,
                                    temperature=0.0  # Apaga la creatividad para mitigar la variación estocástica
                                )
                            )
                            
                            res_data = json.loads(resp.text)
                            evaluaciones = res_data.get('evaluaciones', [])
                            
                            if not evaluaciones:
                                st.info(f"Análisis finalizado: Ninguna de las ofertas para el nivel '{filtro_jer}' cumple con el umbral mínimo del 70% de compatibilidad técnica con el CV provisto.")
                            else:
                                evaluaciones_ordenadas = sorted(evaluaciones, key=lambda x: x['match_score'], reverse=True)
                                for item in evaluaciones_ordenadas:
                                    match = df_f[df_f['id'] == item['id_interno']]
                                    if not match.empty:
                                        with st.container(border=True):
                                            st.write(f"### Match Técnico: {item['match_score']}% — {match.iloc[0]['puesto']}")
                                            st.write(f"**Empresa:** {match.iloc[0]['empresa']} | **Especialidad:** {match.iloc[0]['especialidad']}")
                                            st.write(f"**Justificación de Coincidencia:** {item['coincidencias']}")
                                            st.link_button("🔗 Aplicar a la Vacante Real", match.iloc[0]['link'])
                                            
                    except Exception as e:
                        if "429" in str(e):
                            st.error("⚠️ El clúster de cómputo gratuito está experimentando una alta demanda simultánea. Reintente en 10 segundos.")
                        else:
                            st.error(f"Error en la capa de procesamiento del lenguaje: {e}")
                    finally:
                        st.session_state.procesando_cv = False
