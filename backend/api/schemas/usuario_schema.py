from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    email: str
    fecha_creacion: datetime


class PerfilResponse(BaseModel):
    user_id: int
    peso_kg: float
    altura_cm: float
    edad: int
    sexo: str
    objetivo_principal: str
    nivel_actividad: str
    dieta_tipo: str
    alergias: list
    intolerancias: list
    tiempo_cocina_min: int
    personas_en_casa: int
