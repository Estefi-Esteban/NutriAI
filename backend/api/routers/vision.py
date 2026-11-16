
"""
Router de análisis visual de platos y registro de ingestas.

POST /vision/analizar-plato
    Analiza una imagen y devuelve alimentos y datos nutricionales.

POST /vision/analizar-plato/registrar
    Registra manualmente los macros de una comida.
"""

from __future__ import annotations

import logging
import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db
from backend.api.rate_limiter import limitar_peticiones_ia
from backend.api.schemas.vision_schema import AnalisisVisualResponse
from backend.agents.vision_agent import VisionAgent

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/vision",
    tags=["Visión — Análisis de Platos"],
)

MIME_VALIDOS = {
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".webp": ("image/webp", b"RIFF"),
}

MAX_TAMANO_BYTES = 10 * 1024 * 1024
TAMANO_MINIMO_BYTES = 1000

COMIDAS_VALIDAS = {
    "desayuno",
    "media_manana",
    "almuerzo",
    "comida",
    "merienda",
    "cena",
}


class RegistrarMacrosRequest(BaseModel):
    """Datos nutricionales enviados para registrar una comida."""

    model_config = ConfigDict(str_strip_whitespace=True)

    nombre_plato: str = Field(min_length=1, max_length=200)
    kcal: float = Field(ge=0, le=10000, allow_inf_nan=False)
    proteinas_g: float = Field(ge=0, le=1000, allow_inf_nan=False)
    carbos_g: float = Field(ge=0, le=2000, allow_inf_nan=False)
    grasas_g: float = Field(ge=0, le=1000, allow_inf_nan=False)


def _validar_imagen(archivo: UploadFile) -> tuple[str, str]:
    """Valida la extensión y obtiene MIME y extensión."""

    extension = os.path.splitext(archivo.filename or "")[1].lower()

    configuracion = MIME_VALIDOS.get(extension)

    if configuracion is None:
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Usa JPG, PNG o WEBP.",
        )

    mime_type, _ = configuracion

    return mime_type, extension


def _validar_firma_imagen(contenido: bytes, extension: str) -> bool:
    """Comprueba que la firma binaria corresponde al formato declarado."""

    if extension == ".webp":
        return (
            len(contenido) >= 12
            and contenido.startswith(b"RIFF")
            and contenido[8:12] == b"WEBP"
        )

    firma = MIME_VALIDOS[extension][1]

    return contenido.startswith(firma)


async def _leer_imagen_limitada(
    foto: UploadFile,
    extension: str,
) -> bytes:
    """Lee la imagen sin permitir superar el límite de tamaño."""

    contenido = await foto.read(MAX_TAMANO_BYTES + 1)

    if len(contenido) > MAX_TAMANO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="La imagen supera el límite de 10 MB.",
        )

    if len(contenido) < TAMANO_MINIMO_BYTES:
        raise HTTPException(
            status_code=400,
            detail="El archivo está vacío o es demasiado pequeño.",
        )

    if not _validar_firma_imagen(contenido, extension):
        raise HTTPException(
            status_code=400,
            detail="El contenido del archivo no coincide con el formato declarado.",
        )

    return contenido


def _validar_resultado_agente(resultado: dict) -> dict:
    """
    Valida la respuesta completa del agente.

    Los esquemas permiten campos adicionales, por lo que se conservan
    los nuevos desgloses nutricionales sin saltarse la validación.
    """

    try:
        modelo = AnalisisVisualResponse.model_validate(resultado)
        return modelo.model_dump()

    except Exception as exc:
        logger.exception(
            "La respuesta de VisionAgent no cumple el esquema esperado."
        )
        raise ValueError(
            "La respuesta del agente no tiene un formato válido."
        ) from exc


@router.post(
    "/analizar-plato",
    response_model=AnalisisVisualResponse,
)
async def analizar_plato(
    foto: UploadFile = File(
        ...,
        description="Foto del plato (JPG, PNG o WEBP, máximo 10 MB)",
    ),
    current_user=Depends(limitar_peticiones_ia),
):
    """
    Analiza una imagen de un plato.

    Devuelve:
    - Alimentos detectados.
    - Cantidades estimadas.
    - Macros nutricionales disponibles.
    - Datos verificados mediante RAG.
    - Totales nutricionales.
    """

    mime_type, extension = _validar_imagen(foto)

    try:
        contenido = await _leer_imagen_limitada(foto, extension)

        logger.info(
            "VisionRouter: usuario %s subió imagen de %.1f KB",
            getattr(current_user, "id", "desconocido"),
            len(contenido) / 1024,
        )

        # El agente utiliza HTTP síncrono y consultas a Qdrant.
        # No debemos bloquear el event loop de FastAPI.
        resultado = await run_in_threadpool(
            VisionAgent().analizar_plato,
            contenido,
            mime_type,
        )

        return _validar_resultado_agente(resultado)

    except HTTPException:
        raise

    except ValueError as exc:
        logger.warning(
            "VisionRouter: respuesta o entrada inválida: %s",
            exc,
        )
        raise HTTPException(
            status_code=422,
            detail="No se pudo interpretar correctamente la imagen.",
        ) from exc

    except RuntimeError as exc:
        logger.error(
            "VisionRouter: servicio de visión no disponible: %s",
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="El servicio de análisis visual no está disponible ahora mismo.",
        ) from exc

    except Exception as exc:
        logger.exception(
            "VisionRouter: error inesperado durante el análisis."
        )
        raise HTTPException(
            status_code=500,
            detail="Error interno al analizar la imagen.",
        ) from exc

    finally:
        await foto.close()


@router.post(
    "/analizar-plato/registrar",
    response_model=AnalisisVisualResponse,
)
async def analizar_y_registrar(
    payload: RegistrarMacrosRequest,
    comida: str = "almuerzo",
    current_user=Depends(limitar_peticiones_ia),
    db: Session = Depends(get_db),
):
    """
    Registra manualmente los macros de una comida.
    """

    comida_normalizada = comida.strip().casefold()

    if comida_normalizada not in COMIDAS_VALIDAS:
        raise HTTPException(
            status_code=422,
            detail=(
                "Comida no válida. Valores permitidos: "
                f"{sorted(COMIDAS_VALIDAS)}"
            ),
        )

    try:
        from backend.database.models import IngestaDiaria

        ingesta = IngestaDiaria(
            user_id=current_user.id,
            fecha=date.today(),
            comida=comida_normalizada,
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

        logger.info(
            "VisionRouter: ingesta manual registrada para usuario %s",
            current_user.id,
        )

    except Exception as exc:
        db.rollback()

        logger.exception(
            "No se pudo registrar la ingesta de visión."
        )

        raise HTTPException(
            status_code=500,
            detail="No se pudo registrar la comida en el diario.",
        ) from exc

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
            "alimentos_sin_datos": [],
        },
        "totales_estimados": {
            "kcal": payload.kcal,
            "proteinas_g": payload.proteinas_g,
            "carbos_g": payload.carbos_g,
            "grasas_g": payload.grasas_g,
        },
        "totales_verificados": None,
        "validacion_nutricional": {
            "alimentos_verificados": 0,
            "total_alimentos": 0,
            "totales_verificados_completos": False,
        },
        "disclaimer": (
            "Macros registrados manualmente; "
            "no han sido verificados por RAG."
        ),
    }
