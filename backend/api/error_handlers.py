"""
error_handlers.py
-------------------
Manejadores globales de excepciones para FastAPI.
Convierten las excepciones del dominio en respuestas HTTP consistentes,
y capturan cualquier error inesperado sin que la API se caiga.
"""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.utils.exceptions import (
    NutriAIError,
    SesionNoEncontradaError,
    PerfilInvalidoError,
    RecursoNoEncontradoError,
    AgenteError,
)

logger = logging.getLogger(__name__)


def registrar_manejadores_error(app: FastAPI) -> None:
    """Registra todos los manejadores de excepciones en la app de FastAPI."""

    @app.exception_handler(SesionNoEncontradaError)
    async def manejar_sesion_no_encontrada(request: Request, exc: SesionNoEncontradaError):
        return JSONResponse(
            status_code=404,
            content={"error": "sesion_no_encontrada", "detail": str(exc)},
        )

    @app.exception_handler(RecursoNoEncontradoError)
    async def manejar_recurso_no_encontrado(request: Request, exc: RecursoNoEncontradoError):
        return JSONResponse(
            status_code=404,
            content={"error": "recurso_no_encontrado", "detail": str(exc)},
        )

    @app.exception_handler(PerfilInvalidoError)
    async def manejar_perfil_invalido(request: Request, exc: PerfilInvalidoError):
        return JSONResponse(
            status_code=422,
            content={"error": "perfil_invalido", "detail": str(exc)},
        )

    @app.exception_handler(AgenteError)
    async def manejar_error_agente(request: Request, exc: AgenteError):
        logger.error("Error de agente IA en %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={
                "error": "servicio_ia_no_disponible",
                "detail": "El asistente de IA no pudo procesar la solicitud. Inténtalo de nuevo en unos segundos.",
            },
        )

    @app.exception_handler(NutriAIError)
    async def manejar_error_generico_dominio(request: Request, exc: NutriAIError):
        logger.warning("Error de dominio no clasificado en %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=400,
            content={"error": "error_dominio", "detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def manejar_error_inesperado(request: Request, exc: Exception):
        # Cualquier error de programación que no anticipamos.
        # Lo logueamos COMPLETO (con traceback) pero al usuario solo le
        # devolvemos un mensaje genérico — nunca exponemos detalles internos.
        logger.exception("Error inesperado en %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "error_interno",
                "detail": "Ha ocurrido un error inesperado. El equipo ha sido notificado.",
            },
        )
