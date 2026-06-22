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
from sqlalchemy.orm import Session

from backend.api.schemas.vision_schema import AnalisisVisualResponse
from backend.api.dependencies import get_current_user, get_db
from backend.agents.vision_agent import VisionAgent

logger = logging.getLogger(__name__)

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
    current_user=Depends(get_current_user),
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
    foto: UploadFile = File(..., description="Foto del plato (jpg, png o webp, máx 10MB)"),
    comida: str = "almuerzo",   # query param opcional
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analiza la foto Y registra la ingesta en el seguimiento diario del usuario.

    Parámetro `comida`: desayuno | almuerzo | cena | snack (por defecto: almuerzo)
    """
    mime_type = _validar_imagen(foto)
    contenido = await foto.read()

    if len(contenido) > MAX_TAMANO_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Máximo {MAX_TAMANO_MB}MB.")
    if len(contenido) < 1000:
        raise HTTPException(status_code=400, detail="Archivo vacío o demasiado pequeño.")

    agente = VisionAgent()
    try:
        resultado = agente.analizar_plato(contenido, mime_type)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("VisionRouter (registrar): %s", e)
        raise HTTPException(status_code=500, detail="Error interno al analizar la imagen.")

    # Registrar en seguimiento diario si hay datos de macros
    totales = resultado.get("totales", {})
    if totales.get("kcal", 0) > 0:
        try:
            _registrar_ingesta(db, current_user.id, comida, resultado)
        except Exception as e:
            # No rompemos el flujo si el registro falla — solo logueamos
            logger.warning(
                "VisionRouter: no se pudo registrar la ingesta del usuario %s: %s",
                current_user.id, e,
            )

    return AnalisisVisualResponse(**resultado)


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
