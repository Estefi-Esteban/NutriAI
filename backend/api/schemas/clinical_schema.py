from pydantic import BaseModel
from typing import Optional


class SubirAnaliticaRequest(BaseModel):
    """Para cuando el usuario introduce los valores manualmente."""
    valores: dict   # {"glucosa": 95, "ldl": 145, ...}


class AlertaClinica(BaseModel):
    marcador: str
    severidad: str
    mensaje: str


class AnalisisClinicoResponse(BaseModel):
    resumen_general: str
    marcadores: dict
    alertas: list[AlertaClinica]
    recomendaciones_nutricionales: list[str]
    notas_para_dietista: str
    requiere_atencion_medica: bool
    motivo_atencion_medica: Optional[str] = None
