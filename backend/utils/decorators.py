import time
import logging
import re
from functools import wraps

from backend.utils.exceptions import AgenteError


logger = logging.getLogger(__name__)


def _es_error_reintentable(exc: Exception) -> bool:
    """
    Determina si merece la pena volver a intentar una llamada al LLM.

    Reintentamos:
    - 429 / rate limit
    - errores 500-599
    - errores temporales de conexión

    NO reintentamos:
    - 400
    - 401
    - 403
    - 413 (petición demasiado grande)
    - errores de validación
    """

    mensaje = str(exc).lower()

    # --------------------------------------------------------------
    # Errores HTTP explícitos
    # --------------------------------------------------------------

    if re.search(r"\b413\b", mensaje):
        return False

    if re.search(r"\b400\b", mensaje):
        return False

    if re.search(r"\b401\b", mensaje):
        return False

    if re.search(r"\b403\b", mensaje):
        return False

    # --------------------------------------------------------------
    # Rate limit
    # --------------------------------------------------------------

    if re.search(r"\b429\b", mensaje):
        return True

    if "rate limit" in mensaje:
        return True

    if "too many requests" in mensaje:
        return True

    # --------------------------------------------------------------
    # Errores 5xx
    # --------------------------------------------------------------

    if re.search(r"\b5\d\d\b", mensaje):
        return True

    if "internal server error" in mensaje:
        return True

    if "service unavailable" in mensaje:
        return True

    if "temporarily unavailable" in mensaje:
        return True

    # --------------------------------------------------------------
    # Errores temporales de red
    # --------------------------------------------------------------

    errores_red = (
        "timeout",
        "timed out",
        "connection reset",
        "connection aborted",
        "connection error",
        "temporarily",
    )

    if any(
        palabra in mensaje
        for palabra in errores_red
    ):
        return True

    # Por defecto NO repetir.
    return False


def _obtener_tiempo_retry(exc: Exception) -> float | None:
    """
    Intenta obtener el tiempo de espera indicado por Groq.

    Ejemplos que puede detectar:
    - try again in 10.815s
    - retry after 12 seconds
    """

    mensaje = str(exc).lower()

    patrones = [
        r"try again in\s+([\d.]+)\s*s",
        r"retry after\s+([\d.]+)\s*seconds?",
        r"retry-after[:\s]+([\d.]+)",
    ]

    for patron in patrones:
        match = re.search(
            patron,
            mensaje,
        )

        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

    return None


def reintentar_llamada_llm(
    max_intentos: int = 3,
    retardo_inicial: float = 2.0,
    backoff: float = 2.0,
):
    """
    Decorador para llamadas a LLM.

    Solo reintenta errores que probablemente sean temporales.
    No reintenta peticiones inválidas o demasiado grandes.
    """

    def decorador(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            intentos = 0
            retardo = retardo_inicial

            while intentos < max_intentos:

                try:
                    return func(
                        *args,
                        **kwargs,
                    )

                except Exception as exc:

                    intentos += 1

                    msg_exc = str(exc)

                    logger.warning(
                        "Error en llamada a LLM %s "
                        "(intento %d/%d): %s",
                        func.__name__,
                        intentos,
                        max_intentos,
                        msg_exc,
                    )

                    # --------------------------------------------------
                    # Si NO es reintentable, abortamos inmediatamente.
                    # --------------------------------------------------

                    if not _es_error_reintentable(exc):

                        logger.error(
                            "Error NO reintentable en %s. "
                            "No se realizará otra llamada para "
                            "evitar consumo innecesario de cuota.",
                            func.__name__,
                        )

                        raise AgenteError(
                            "Error no reintentable al contactar "
                            f"con el agente de IA: {msg_exc}"
                        ) from exc

                    # --------------------------------------------------
                    # Máximo de intentos
                    # --------------------------------------------------

                    if intentos >= max_intentos:

                        logger.error(
                            "Se excedieron los intentos máximos "
                            "para %s.",
                            func.__name__,
                        )

                        raise AgenteError(
                            "Error persistente al contactar "
                            f"con el agente de IA: {msg_exc}"
                        ) from exc

                    # --------------------------------------------------
                    # Si Groq indica cuánto esperar, lo respetamos.
                    # --------------------------------------------------

                    retry_after = _obtener_tiempo_retry(
                        exc
                    )

                    if retry_after is not None:

                        espera = max(
                            retry_after + 1.0,
                            retardo,
                        )

                    else:
                        espera = retardo

                    logger.info(
                        "Esperando %.1f segundos antes "
                        "del reintento...",
                        espera,
                    )

                    time.sleep(espera)

                    retardo *= backoff

            raise AgenteError(
                "No se pudo completar la llamada al LLM."
            )

        return wrapper

    return decorador