"""
vision.py — Router del Agente de Visión
-----------------------------------------
POST /vision/analizar-plato
    Sube una foto de un plato y recibe los macros estimados + verificados.

POST /vision/analizar-plato/registrar
    Como el anterior, pero además registra la ingesta en el seguimiento diario.
"""

import logging
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.schemas.vision_schema import AnalisisVisualResponse
from backend.api.dependencies import get_current_user, get_db
from backend.api.rate_limiter import limitar_peticiones_ia
from backend.agents.vision_agent import VisionAgent

logger = logging.getLogger(__name__)

class RegistrarMacrosRequest(BaseModel):
    nombre_plato: str
    kcal: float
    proteinas_g: float
    carbos_g: float
    grasas_g: float


router = APIRouter(prefix="/vision", tags=["Visión — Análisis de Platos"])

# Tipos MIME que aceptamos
MIME_VALIDOS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

MAX_TAMANO_MB = 10


def _validar_imagen(archivo: UploadFile) -> str:
    """Valida extensión y devuelve el MIME type correcto."""
    import os
    ext = os.path.splitext(archivo.filename or "")[1].lower()
    if ext not in MIME_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Usa: {list(MIME_VALIDOS.keys())}",
        )
    return MIME_VALIDOS[ext]


@router.post("/analizar-plato", response_model=AnalisisVisualResponse)
async def analizar_plato(
    foto: UploadFile = File(..., description="Foto del plato (jpg, png o webp, máx 10MB)"),
    current_user=Depends(limitar_peticiones_ia),
):
    """
    Analiza una foto de un plato de comida y devuelve:
    - Alimentos detectados con su cantidad estimada en gramos
    - Macros verificados desde la base de datos nutricional (ChromaDB)
    - Totales de calorías, proteínas, carbohidratos y grasas

    **Nota:** Las cantidades son estimaciones visuales. El margen de error
    es de ±20% en función del ángulo, la iluminación y el tamaño del plato.
    """
    mime_type = _validar_imagen(foto)

    contenido = await foto.read()

    # Comprobamos tamaño (10 MB max)
    if len(contenido) > MAX_TAMANO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"La imagen es demasiado grande. Máximo {MAX_TAMANO_MB}MB.",
        )

    if len(contenido) < 1000:
        raise HTTPException(
            status_code=400,
            detail="El archivo está vacío o es demasiado pequeño.",
        )

    logger.info(
        "VisionRouter: usuario %s subió imagen de %.1f KB",
        current_user.id,
        len(contenido) / 1024,
    )

    agente = VisionAgent()
    try:
        resultado = agente.analizar_plato(contenido, mime_type)
    except RuntimeError as e:
        logger.error("VisionRouter: error del agente — %s", e)
        raise HTTPException(
            status_code=503,
            detail="El servicio de análisis visual no está disponible ahora mismo. Intenta de nuevo.",
        )
    except Exception as e:
        logger.error("VisionRouter: error inesperado — %s", e)
        raise HTTPException(status_code=500, detail="Error interno al analizar la imagen.")

    return AnalisisVisualResponse(**resultado)


@router.post("/analizar-plato/registrar", response_model=AnalisisVisualResponse)
async def analizar_y_registrar(
    payload: RegistrarMacrosRequest,
    comida: str = "almuerzo",   # query param opcional
    current_user=Depends(limitar_peticiones_ia),
    db: Session = Depends(get_db),
):
    """
    Registra directamente los macros de un plato en el seguimiento diario (formato JSON).
    """
    try:
        from backend.database.models import IngestaDiaria
        from datetime import date

        ingesta = IngestaDiaria(
            user_id=current_user.id,
            fecha=date.today(),
            comida=comida,
            descripcion=payload.nombre_plato,
            kcal=payload.kcal,
            proteinas_g=payload.proteinas_g,
            carbos_g=payload.carbos_g,
            grasas_g=payload.grasas_g,
            origen="vision",
            detalle_json=[],
        )
        db.add(ingesta)
        db.commit()
        logger.info("VisionRouter: ingesta directa registrada para usuario %s", current_user.id)
    except Exception as e:
        db.rollback()
        logger.error("VisionRouter (registrar directo): %s", e)
        raise HTTPException(status_code=500, detail="No se pudo registrar la comida en el diario.")

    # Devolvemos un objeto compatible con AnalisisVisualResponse
    return {
        "descripcion_plato": payload.nombre_plato,
        "calidad_imagen": "BUENA",
        "advertencia": None,
        "alimentos": [],
        "totales": {
            "kcal": payload.kcal,
            "proteinas_g": payload.proteinas_g,
            "carbos_g": payload.carbos_g,
            "grasas_g": payload.grasas_g,
            "alimentos_sin_datos": []
        },
        "disclaimer": "Registrado directamente."
    }


def _registrar_ingesta(db: Session, user_id: int, comida: str, analisis: dict):
    """
    Guarda la ingesta detectada en el historial diario del usuario.
    Usa el modelo IngestaDiaria si existe, si no lo omite silenciosamente.
    """
    try:
        from backend.database.models import IngestaDiaria
        from datetime import date

        ingesta = IngestaDiaria(
            user_id=user_id,
            fecha=date.today(),
            comida=comida,
            descripcion=analisis.get("descripcion_plato", "Plato analizado por visión"),
            kcal=analisis["totales"]["kcal"],
            proteinas_g=analisis["totales"]["proteinas_g"],
            carbos_g=analisis["totales"]["carbos_g"],
            grasas_g=analisis["totales"]["grasas_g"],
            origen="vision",
            detalle_json=analisis.get("alimentos", []),
        )
        db.add(ingesta)
        db.commit()
        logger.info("VisionRouter: ingesta registrada para usuario %s", user_id)

    except ImportError:
        # El modelo IngestaDiaria aún no existe — modo degradado sin registro
        logger.info("VisionRouter: IngestaDiaria no disponible, skipping registro")
    except Exception as e:
        db.rollback()
        raise e
