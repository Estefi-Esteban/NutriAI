import os
import tempfile
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.api.schemas.clinical_schema import (
    SubirAnaliticaRequest, AnalisisClinicoResponse
)
from backend.api.dependencies import get_current_user, get_db
from backend.api.rate_limiter import limitar_peticiones_ia
from backend.database.models import UserProfile
from backend.agents.clinical_agent import ClinicalAgent
from backend.utils.pdf_extractor import extraer_texto_analitica, parsear_valores_analitica

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analitica", tags=["Analítica Clínica"])


@router.post("/subir-archivo", response_model=AnalisisClinicoResponse)
async def analizar_archivo(
    archivo: UploadFile = File(...),
    current_user = Depends(limitar_peticiones_ia),
    db: Session = Depends(get_db),
):
    """
    Sube un PDF o imagen de analítica.
    El sistema extrae los valores automáticamente y los analiza.
    """
    extensiones_validas = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
    ext = os.path.splitext(archivo.filename)[1].lower()

    if ext not in extensiones_validas:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Usa: {extensiones_validas}"
        )

    # Guardamos el archivo temporalmente para procesarlo
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        contenido = await archivo.read()
        tmp.write(contenido)
        ruta_tmp = tmp.name

    try:
        texto = extraer_texto_analitica(ruta_tmp)
        if not texto.strip():
            raise HTTPException(
                status_code=422,
                detail="No se pudo extraer texto del archivo. Prueba con una imagen más nítida."
            )

        valores = parsear_valores_analitica(texto)
        if not valores:
            raise HTTPException(
                status_code=422,
                detail="No se encontraron marcadores reconocibles. Introduce los valores manualmente."
            )

        agente = ClinicalAgent()
        
        # Enriquecer perfil del usuario a partir de la base de datos
        perfil_basico = {"user_id": current_user.id}
        try:
            perfil = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
            if perfil:
                perfil_basico = {
                    "sexo": perfil.sexo,
                    "edad": perfil.edad,
                    "peso_kg": perfil.peso_kg,
                    "altura_cm": perfil.altura_cm,
                    "objetivo": perfil.objetivo_principal.value if perfil.objetivo_principal else None,
                    "patologias": perfil.patologias or [],
                    "alergias": perfil.alergias or [],
                    "dieta": perfil.dieta_tipo.value if perfil.dieta_tipo else None
                }
        except Exception as e:
            logger.warning(f"Error al obtener perfil del usuario {current_user.id}: {e}")

        analisis = agente.analizar(perfil=perfil_basico, valores=valores)
        return AnalisisClinicoResponse(**analisis)

    finally:
        os.unlink(ruta_tmp)  # limpiamos el archivo temporal


@router.post("/manual", response_model=AnalisisClinicoResponse)
def analizar_manual(
    payload: SubirAnaliticaRequest,
    current_user = Depends(limitar_peticiones_ia),
    db: Session = Depends(get_db),
):
    """
    Introduce los valores de la analítica manualmente.
    Útil si no puedes subir el PDF o prefieres hacerlo a mano.
    """
    if not payload.valores:
        raise HTTPException(
            status_code=400,
            detail="Debes proporcionar al menos un valor analítico."
        )

    agente = ClinicalAgent()
    
    # Enriquecer perfil del usuario a partir de la base de datos
    perfil_basico = {"user_id": current_user.id}
    try:
        perfil = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
        if perfil:
            perfil_basico = {
                "sexo": perfil.sexo,
                "edad": perfil.edad,
                "peso_kg": perfil.peso_kg,
                "altura_cm": perfil.altura_cm,
                "objetivo": perfil.objetivo_principal.value if perfil.objetivo_principal else None,
                "patologias": perfil.patologias or [],
                "alergias": perfil.alergias or [],
                "dieta": perfil.dieta_tipo.value if perfil.dieta_tipo else None
            }
    except Exception as e:
        logger.warning(f"Error al obtener perfil del usuario {current_user.id}: {e}")

    analisis = agente.analizar(perfil=perfil_basico, valores=payload.valores)
    return AnalisisClinicoResponse(**analisis)
