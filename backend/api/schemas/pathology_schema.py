from pydantic import BaseModel
from typing import Optional


class AnalizarPatologiasRequest(BaseModel):
    patologias: list[str]
    alertas_clinicas: Optional[list[dict]] = None


class ProtocoloResponse(BaseModel):
    patologias_identificadas: list[str]
    restricciones: list[str]
    alimentos_prohibidos: list[str]
    alimentos_prioritarios: list[str]
    conflictos_detectados: list[str]
    notas_dietista: str
    nivel_restriccion: str
