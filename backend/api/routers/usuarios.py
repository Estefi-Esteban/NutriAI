from fastapi import APIRouter, HTTPException, Depends

from backend.api.schemas.usuario_schema import UsuarioResponse, PerfilResponse
from backend.api.dependencies import get_current_user
from backend.database.connection import SessionLocal
from backend.database.models import User
from backend.database.repositories.user_repository import obtener_perfil

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get("/me", response_model=UsuarioResponse)
def obtener_usuario(current_user: User = Depends(get_current_user)):
    """Devuelve los datos básicos del usuario autenticado."""
    return UsuarioResponse(
        id=current_user.id,
        nombre=current_user.nombre,
        email=current_user.email,
        fecha_creacion=current_user.fecha_creacion,
    )


@router.get("/me/perfil", response_model=PerfilResponse)
def obtener_perfil_usuario(current_user: User = Depends(get_current_user)):
    """Devuelve el perfil nutricional completo del usuario autenticado."""
    with SessionLocal() as db:
        perfil = obtener_perfil(db, user_id=current_user.id)
        if perfil is None:
            raise HTTPException(status_code=404, detail="Este usuario no tiene perfil guardado")

        return PerfilResponse(
            user_id=perfil.user_id,
            peso_kg=perfil.peso_kg,
            altura_cm=perfil.altura_cm,
            edad=perfil.edad,
            sexo=perfil.sexo,
            objetivo_principal=perfil.objetivo_principal.value,
            nivel_actividad=perfil.nivel_actividad.value,
            dieta_tipo=perfil.dieta_tipo.value,
            alergias=perfil.alergias or [],
            intolerancias=perfil.intolerancias or [],
            tiempo_cocina_min=perfil.tiempo_cocina_min,
            personas_en_casa=perfil.personas_en_casa,
        )
