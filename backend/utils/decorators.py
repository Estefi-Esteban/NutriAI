"""
decorators.py
-------------
Decoradores de utilidad para el proyecto NutriAI.
"""

import time
import logging
from functools import wraps
from backend.utils.exceptions import AgenteError

logger = logging.getLogger(__name__)


def reintentar_llamada_llm(max_intentos: int = 3, retardo_inicial: float = 2.0, backoff: float = 2.0):
    """
    Decorador para reintentar llamadas a APIs de LLM (como Groq) en caso de errores
    temporales como rate limits (HTTP 429) o fallos de conexión.
    """
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            intentos = 0
            retardo = retardo_inicial
            while intentos < max_intentos:
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    intentos += 1
                    msg_exc = str(exc)
                    # Si el error es una excepción que queremos propagar inmediatamente sin reintentar (por ej. ValueError de dominio),
                    # podríamos controlarlo, pero para Groq reintentamos en cualquier error de red/rate limit.
                    logger.warning(
                        "Error en llamada a LLM %s (intento %d/%d): %s",
                        func.__name__, intentos, max_intentos, msg_exc
                    )
                    
                    if intentos >= max_intentos:
                        logger.error("Se excedieron los intentos máximos para la función de LLM %s.", func.__name__)
                        raise AgenteError(f"Error persistente al contactar con el agente de IA: {msg_exc}") from exc
                    
                    logger.info("Esperando %.1f segundos antes del reintento...", retardo)
                    time.sleep(retardo)
                    retardo *= backoff
            return None
        return wrapper
    return decorador
