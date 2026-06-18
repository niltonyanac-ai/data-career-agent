import streamlit as st
import pandas as pd
import json
import hashlib
import threading
import google.generativeai as genai
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor
from pypdf import PdfReader

# --- Configuración Inicial ---
st.set_page_config(page_title="DataCareer AI", page_icon="💼", layout="wide")

st.markdown("""
<style>
    .match-card { border: 1px solid #e2e8f0; padding: 20px; border-radius: 10px; margin-bottom: 15px; background-color: #ffffff; }
</style>
""", unsafe_allow_html=True)

if "texto_cv_usuario" not in st.session_state: st.session_state["texto_cv_usuario"] = ""
if "ats_cache" not in st.session_state: st.session_state["ats_cache"] = {}

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

class EvaluacionMatch(BaseModel):
    match_score: int = Field(..., ge=0, le=100)
    justificacion: str
    habilidades_coincidentes: list[str]
    habilidades_faltantes: list[str]

# --- Funciones de Backend ---
def normalizar_jerarquia(texto):
    if pd.isna(texto): return "2. Analista / Profesional"
    t = str(texto).lower()
    if any(x in t for x in ["practicante", "asistente"]): return "1. Practicante / Asistente"
    if any(x in t for x in ["gerente", "manager", "head"]): return "6. Gerente / Head"
    if any(x in t for x in ["lider", "jefe", "lead"]): return "4. Líder / Jefe"
    if any(x in t for x in ["senior", "sr", "especialista"]): return "3. Analista Senior"
    return "2. Analista / Profesional"

def extraer_texto_pdf(archivo):
    reader = PdfReader(archivo)
    return "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])

def evaluar_cv_contra_vacante(args):
    llave_cache = f"{args['cv_hash']}_{args['fila_vacante'].get('link_oferta', 'SD')}"
    if llave_cache in args["cache_dict"]: return args["cache_dict"][llave_cache]
    try:
        model = args["model_instance"]
        prompt = f"Evalúa este CV contra la vacante: {args['fila_vacante'].to_dict()}"
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json", response_schema=EvaluacionMatch))
        res = json.loads(response.text)
        res.update({"llave_cache": llave_cache, "titulo": args["fila_vacante"].get("titulo")})
        return res
    except Exception as e:
        return {"match_score": 0, "justificacion": f"Error en IA: {str(e)}", "titulo": "Error"}

def registrar_telemetria_silenciosa(resultados):
    pass

# --- Interfaz Principal ---
def main():
    # TTL ajustado a 60 segundos para mayor frescura de datos
    @st.cache_data(ttl=60)
    def cargar_datos():
        return pd.DataFrame([
            {"titulo": "Data Scientist", "empresa": "Inetum", "jerarquia": "Senior", "pais": "Perú", "descripcion": "Python, SQL", "link_oferta": "#"},
            {"titulo": "Analista BI", "empresa": "NTT", "jerarquia": "Analista", "pais": "Perú", "descripcion": "PowerBI, SQL", "link_oferta": "#"}
        ])
    
    df_vacantes = cargar_datos()
    df_vacantes['jerarquia_limpia'] = df_vacantes['jerarquia'].apply(normalizar_jerarquia)

    st.sidebar.header("🎯 Filtros")
    lista_paises = df_vacantes['pais'].unique()
    lista_jerarquias = df_vacantes['jerarquia_limpia'].unique()
    
    paises = st.sidebar.multiselect("País", lista_paises, default=lista_paises)
    jerarquias = st.sidebar.multiselect("Nivel", lista_jerarquias, default=lista_jerarquias)
    
    df_filtrado = df_vacantes[(df_vacantes['pais'].isin(paises)) & (df_vacantes['jerarquia_limpia'].isin(jerarquias))]

    tab1, tab2 = st.tabs(["📊 Mercado", "🔍 Evaluador ATS"])
    
    with tab1:
        st.subheader("Análisis de Demanda")
        c1, c2 = st.columns(2)
        # Manejo de nulos en gráficos
        c1.bar_chart(df_filtrado['jerarquia_limpia'].fillna("Sin especificar").value_counts())
        c2.bar_chart(df_filtrado['pais'].fillna("Sin especificar").value_counts())
        st.dataframe(df_filtrado)

    with tab2:
        archivo = st.file_uploader("Sube tu CV (PDF)", type=["pdf"])
        if archivo and st.button("🚀 Ejecutar Análisis"):
            texto = extraer_texto_pdf(archivo)
            cv_hash = hashlib.md5(texto.encode()).hexdigest()
            
            with st.spinner("Comparando con vacantes..."):
                payloads = [{"texto_cv": texto, "fila_vacante": row, "model_instance": genai.GenerativeModel("gemini-1.5-flash"), 
                             "cache_dict": st.session_state["ats_cache"], "cv_hash": cv_hash} for _, row in df_filtrado.iterrows()]
                
                with ThreadPoolExecutor(max_workers=3) as executor:
                    resultados = list(executor.map(evaluar_cv_contra_vacante, payloads))
                
                # Ordenar resultados por score de mayor a menor antes de mostrar
                resultados.sort(key=lambda x: x.get('match_score', 0), reverse=True)
                
                for res in resultados:
                    st.session_state["ats_cache"][res.get("llave_cache", "")] = res
                    st.markdown(f"""<div class="match-card">
                                   <h4>{res.get('titulo')} - {res.get('match_score')}% Match</h4>
                                   <p>{res.get('justificacion')}</p></div>""", unsafe_allow_html=True)
                
                threading.Thread(target=registrar_telemetria_silenciosa, args=(resultados,), daemon=True).start()

if __name__ == "__main__":
    main()
