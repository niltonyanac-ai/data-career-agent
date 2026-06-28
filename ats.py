# ats.py
import json
import re
from typing import List, Dict, Any
from pydantic import BaseModel
import google.generativeai as genai
from config import PESOS_ATS

# =====================================================================
# 1. ESQUEMA DE DATOS REDUCIDO (ACCIÓN 2 Y 3)
# =====================================================================
class PerfilCV(BaseModel):
    hard_skills: List[str]
    experiencia: float
    especialidad: str
    idiomas: List[str]
    soft_skills: List[str]

# =====================================================================
# 2. EXTRACCIÓN DETERMINISTA CON LLM (ACCIÓN 4)
# =====================================================================
def extraer_perfil_cv(texto_cv: str, model_instance) -> Dict[str, Any]:
    """
    Extrae únicamente las 5 dimensiones clave del CV.
    """
    prompt = f"""
    Eres un extractor de datos ATS. Analiza el siguiente CV y extrae EXCLUSIVAMENTE las siguientes 5 variables en formato JSON.
    
    Reglas de extracción:
    1. hard_skills: Lista de herramientas, software y lenguajes técnicos.
    2. experiencia: Número total de años de experiencia laboral (ej. 4.5). Usa 0 si no hay.
    3. especialidad: El dominio principal del perfil (ej. "Data Science", "Business Intelligence", "Data Engineering").
    4. idiomas: Lista de idiomas mencionados.
    5. soft_skills: Lista de habilidades blandas explícitas.
    
    CURRÍCULUM VITAE:
    {texto_cv[:4000]}
    """
    
    configuracion = genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=PerfilCV,
        temperature=0.0
    )
    
    try:
        response = model_instance.generate_content(prompt, generation_config=configuracion)
        texto_limpio = re.sub(r'^```json\s*|\s*```$', '', response.text.strip(), flags=re.MULTILINE)
        return json.loads(texto_limpio)
    except Exception as e:
        print(f"⚠️ Error extrayendo perfil: {e}")
        return {"hard_skills": [], "experiencia": 0.0, "especialidad": "", "idiomas": [], "soft_skills": []}

# =====================================================================
# 3. HELPER: CLASIFICACIÓN DEL ROL
# =====================================================================
def clasificar_rol_vacante(jerarquia: str) -> str:
    """Define si la vacante aplica para pesos de técnico, líder o gerente."""
    jerarquia = str(jerarquia).lower()
    if any(x in jerarquia for x in ["gerente", "head", "director", "chief"]):
        return "gerente"
    elif any(x in jerarquia for x in ["lider", "jefe", "lead", "coordinador"]):
        return "lider"
    else:
        return "tecnico"

# =====================================================================
# 4. MOTOR MATEMÁTICO 100% PYTHON (ACCIÓN 1, 5, 8 Y 33)
# =====================================================================
def calcular_score_matematico(perfil_cv: Dict[str, Any], vacante: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcula el Score ATS usando la matriz de pesos centralizada.
    """
    tipo_rol = clasificar_rol_vacante(vacante.get("jerarquia_limpia", ""))
    pesos = PESOS_ATS[tipo_rol]
    
    # 1. Hard Skills
    cv_hard = [h.lower().strip() for h in perfil_cv.get("hard_skills", [])]
    req_hard = [h.lower().strip() for h in vacante.get("hard_skills", [])]
    coincidentes_hard = [h for h in req_hard if h in cv_hard]
    faltantes_hard = [h for h in req_hard if h not in cv_hard]
    score_hard = (len(coincidentes_hard) / len(req_hard)) * pesos["hard_skills"] if req_hard else pesos["hard_skills"]
    
    # 2. Experiencia
    exp_cv = float(perfil_cv.get("experiencia", 0.0))
    exp_req = float(vacante.get("anios_experiencia_req", 2.0))
    score_exp = pesos["experiencia"] if exp_cv >= exp_req else (exp_cv / exp_req) * pesos["experiencia"]
    
    # 3. Especialidad
    esp_cv = str(perfil_cv.get("especialidad", "")).lower()
    esp_req = str(vacante.get("especialidad_objetivo", "")).lower()
    score_esp = pesos["especialidad"] if esp_req and esp_req in esp_cv else 0.0
    
    # 4. Idiomas (Simplificado: si piden inglés y lo tiene o no piden, puntaje completo)
    cv_idiomas = [i.lower() for i in perfil_cv.get("idiomas", [])]
    req_idiomas = ["inglés"] # Esto debería venir del scraper, lo hardcodeamos para la estructura actual
    score_idiomas = pesos["idiomas"] if any(req in cv for req in req_idiomas for cv in cv_idiomas) else 0.0
    
    # 5. Soft Skills
    cv_soft = [s.lower().strip() for s in perfil_cv.get("soft_skills", [])]
    req_soft = [s.lower().strip() for s in vacante.get("soft_skills", [])]
    score_soft = (len([s for s in req_soft if s in cv_soft]) / len(req_soft)) * pesos["soft_skills"] if req_soft else pesos["soft_skills"]
    
    score_total = round(score_hard + score_exp + score_esp + score_idiomas + score_soft)
    
    desglose_ui = f"""
    Hard Skills .......... {round(score_hard)} / {pesos['hard_skills']}
    Experiencia .......... {round(score_exp)} / {pesos['experiencia']}
    Especialidad ......... {round(score_esp)} / {pesos['especialidad']}
    Idiomas .............. {round(score_idiomas)} / {pesos['idiomas']}
    Soft Skills .......... {round(score_soft)} / {pesos['soft_skills']}
    TOTAL ................ {score_total}%
    """

    return {
        "match_score": score_total,
        "coincidentes": coincidentes_hard,
        "faltantes": faltantes_hard,
        "desglose_texto": desglose_ui,
        "tipo_rol_evaluado": tipo_rol
    }
