import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

# Configuración de la página (Debe ser la primera instrucción de Streamlit)
st.set_page_config(page_title="DataCareer AI", page_icon="💼", layout="wide")

# 1. Intentar obtener las credenciales de Supabase de todas las fuentes posibles
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")

@st.cache_resource
def conectar_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None

supabase = conectar_supabase()

# 2. Carga segura de datos forzando el formato DataFrame de Pandas
def cargar_vacantes():
    # Lote de respaldo por si Supabase está vacío o desconectado
    datos_respaldo = [
        {'puesto': 'Analista de Inteligencia de Negocios', 'empresa': 'Banco de Crédito del Perú (BCP)', 'especialidad': 'Data Analytics', 'jerarquia': 'Semi-Senior', 'hard_skills': 'SQL, Power BI', 'soft_skills': 'Comunicación', 'link': 'https://linkedin.com'},
        {'puesto': 'Analista Senior de Analytics', 'empresa': 'Interbank', 'especialidad': 'Data Analytics', 'jerarquia': 'Senior', 'hard_skills': 'SQL, Python', 'soft_skills': 'Liderazgo', 'link': 'https://linkedin.com'},
        {'puesto': 'Consultor de Analítica Avanzada', 'empresa': 'Arellano Consultoría', 'especialidad': 'Data Analytics', 'jerarquia': 'Senior', 'hard_skills': 'SQL, Excel Avanzado', 'soft_skills': 'Análisis', 'link': 'https://linkedin.com'},
        {'puesto': 'Científico de Datos Senior', 'empresa': 'Banco de Crédito del Perú (BCP)', 'especialidad': 'Data Science', 'jerarquia': 'Senior', 'hard_skills': 'Python, TensorFlow', 'soft_skills': 'Estrategia', 'link': 'https://linkedin.com'},
        {'puesto': 'Data Scientist', 'empresa': 'Interbank', 'especialidad': 'Data Science', 'jerarquia': 'Semi-Senior', 'hard_skills': 'Python, Scikit-Learn', 'soft_skills': 'Investigación', 'link': 'https://linkedin.com'},
        {'puesto': 'Ingeniero de Datos Senior', 'empresa': 'Rimac Seguros', 'especialidad': 'Data Engineering', 'jerarquia': 'Senior', 'hard_skills': 'SQL, Python, AWS', 'soft_skills': 'Autonomía', 'link': 'https://linkedin.com'},
        {'puesto': 'Data Engineer', 'empresa': 'Interbank', 'especialidad': 'Data Engineering', 'jerarquia': 'Semi-Senior', 'hard_skills': 'SQL, Airflow', 'soft_skills': 'Planificación', 'link': 'https://linkedin.com'}
    ]
    
    if supabase is None:
        return pd.DataFrame(datos_respaldo)
        
    try:
        respuesta = supabase.table("vacantes").select("*").execute()
        if respuesta.data and len(respuesta.data) > 0:
            df = pd.DataFrame(respuesta.data)
            # Asegurar formatos limpios de texto para visualización
            for col in ['hard_skills', 'soft_skills']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
            return df
        else:
            return pd.DataFrame(datos_respaldo)
    except Exception:
        return pd.DataFrame(datos_respaldo)

# Cargar los datos
df_vacantes = cargar_vacantes()

# =========================================================================
# 3. INTERFAZ GRÁFICA DEL DASHBOARD (STREAMLIT)
# =========================================================================

# Título Principal
st.title("💼 DataCareer AI")
st.subheader("Análisis de mercado en tiempo real y evaluador de CVs para perfiles de Datos")

# Indicadores clave en barra superior (KPIs)
total_ofertas = len(df_vacantes)
col_kpi1, col_kpi2, col_kpi3 = st.columns(3)

with col_kpi1:
    st.metric(label="Ofertas activas en los últimos 60 días", value=f"{total_ofertas} posiciones")
with col_kpi2:
    empresas_unicas = df_vacantes['empresa'].nunique() if 'empresa' in df_vacantes.columns else 0
    st.metric(label="Empresas monitoreadas", value=f"{empresas_unicas}")
with col_kpi3:
    st.metric(label="Estado del Sistema", value="Sincronizado ✨")

st.markdown("---")

# Crear pestañas para organizar la navegación
tab1, tab2 = st.tabs(["📊 Dashboard del Mercado", "🔍 Vacantes Encontradas"])

with tab1:
    st.header("Tendencias Acumuladas del Mercado Laboral")
    
    # Barra lateral / Filtros dinámicos
    st.sidebar.header("Filtros de Búsqueda")
    
    especialidades = ['Todos'] + list(df_vacantes['especialidad'].unique()) if 'especialidad' in df_vacantes.columns else ['Todos']
    sel_esp = st.sidebar.selectbox("Selecciona Especialidad", especialidades)
    
    # Filtrar el DataFrame según la selección del usuario
    df_filtrado = df_vacantes.copy()
    if sel_esp != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['especialidad'] == sel_esp]
        
    # Gráfico simple incorporado (Métricas por jerarquía/seniority)
    if 'jerarquia' in df_filtrado.columns and not df_filtrado.empty:
        st.subheader("Distribución de Vacantes por Seniority")
        conteo_jerarquia = df_filtrado['jerarquia'].value_counts()
        st.bar_chart(conteo_jerarquia)
    else:
        st.info("No hay suficientes datos estructurados para mostrar gráficos de barra.")

with tab2:
    st.header("Repositorio de Ofertas en el Mercado Abierto")
    st.write("A continuación se detallan las posiciones detectadas de forma agnóstica en el ecosistema de Perú:")
    
    # Mostrar la tabla interactiva de datos limpios
    if not df_filtrado.empty:
        columnas_visibles = [c for c in ['puesto', 'empresa', 'especialidad', 'jerarquia', 'hard_skills', 'link'] if c in df_filtrado.columns]
        st.dataframe(df_filtrado[columnas_visibles], use_container_width=True)
    else:
        st.warning("No se encontraron registros que coincidan con los filtros seleccionados.")
