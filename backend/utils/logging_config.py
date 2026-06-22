"""
logging_config.py
-------------------
Configuración central de logging para todo el proyecto.
Se llama UNA vez al arrancar la API (o cualquier script), y a partir
de ahí cualquier módulo usa logging.getLogger(__name__) normalmente.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Definir la ruta de logs relativa al directorio raíz del proyecto
RUTA_LOGS = Path("logs")
RUTA_LOGS.mkdir(exist_ok=True)


def configurar_logging(nivel: int = logging.INFO) -> None:
    """
    Configura el logging raíz del proyecto:
      - Consola: para desarrollo, todo lo que pasa en tiempo real
      - Archivo logs/nutriai.log: persiste entre ejecuciones, con rotación
        automática para que no crezca sin límite (máx 5MB x 3 backups)
    """
    formato = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger_raiz = logging.getLogger()
    logger_raiz.setLevel(nivel)

    # Evitar handlers duplicados si se llama más de una vez (ej: con --reload de uvicorn)
    if logger_raiz.handlers:
        return

    # Handler de consola
    handler_consola = logging.StreamHandler(sys.stdout)
    handler_consola.setFormatter(formato)
    logger_raiz.addHandler(handler_consola)

    # Handler de archivo con rotación (máx 5MB, guarda 3 archivos antiguos)
    handler_archivo = RotatingFileHandler(
        RUTA_LOGS / "nutriai.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler_archivo.setFormatter(formato)
    logger_raiz.addHandler(handler_archivo)

    # Silenciar librerías muy verbosas que no nos interesan a ese nivel
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
