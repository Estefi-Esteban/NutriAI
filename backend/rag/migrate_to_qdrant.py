
"""
migrate_to_qdrant.py
---------------------
Migra los alimentos de alimentos_limpios.csv a Qdrant Cloud.

IMPORTANTE:
Esta versión RECONSTRUYE la colección "alimentos" antes de migrar.
Por tanto, reemplaza la versión anterior del dataset.

VERSIÓN OPTIMIZADA CON FASTEMBED
"""

import os
import sys
import uuid
import math
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)

RUTA_CSV = Path("data/food_db/alimentos_limpios.csv")

MODELO_EMBEDDINGS = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

COLECCION = "alimentos"
DIMENSION_VECTOR = 384
TAMANO_LOTE = 1000
LOG_CADA = 5


# ---------------------------------------------------------------------------
# Conversión de datos
# ---------------------------------------------------------------------------

def _bool(valor) -> bool:
    """Convierte de forma segura valores booleanos del CSV."""

    if isinstance(valor, bool):
        return valor

    if valor is None:
        return False

    return str(valor).strip().lower() in {
        "true",
        "1",
        "yes",
        "si",
        "sí",
    }


def _num(valor) -> float:
    """
    Convierte campos numéricos generales a float.

    Los valores ausentes o inválidos devuelven 0.0.
    No utilizar para información nutricional.
    """

    if valor is None or isinstance(valor, bool):
        return 0.0

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 0.0

    return numero if math.isfinite(numero) else 0.0


def _nutriente(valor) -> float | None:
    """
    Convierte un nutriente sin confundir ausencia con cero real.

    Devuelve:
    - float: valor nutricional válido.
    - 0.0: cero real registrado.
    - None: dato ausente, inválido o negativo.
    """

    if valor is None or isinstance(valor, bool):
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numero) or numero < 0.0:
        return None

    return numero


def _texto(valor: object, limite: int | None = None) -> str:
    """
    Normaliza texto procedente del CSV.

    Los valores ausentes se convierten en cadenas vacías.
    Evita almacenar NaN, None o null como texto literal.
    """

    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass

    texto = str(valor).strip()

    if texto.casefold() in {"nan", "none", "null", "<na>"}:
        return ""

    if limite is not None:
        texto = texto[:limite]

    return texto


def _filtrar_nutrientes_desconocidos(
    payload: dict,
) -> dict:
    """
    Omite nutrientes desconocidos del payload de Qdrant.

    Qdrant no necesita recibir campos nutricionales con None.
    Los ceros reales se conservan.
    """

    campos_nutricionales = {
        "kcal_100g",
        "proteinas_100g",
        "carbos_100g",
        "azucares_100g",
        "grasas_100g",
        "fibra_100g",
        "sal_100g",
    }

    return {
        clave: valor
        for clave, valor in payload.items()
        if (
            clave not in campos_nutricionales
            or valor is not None
        )
    }


# ---------------------------------------------------------------------------
# Construcción de embeddings
# ---------------------------------------------------------------------------

def _limpiar_categorias(valor: object) -> str:
    """Limpia categorías sin utilizar listas específicas de alimentos."""

    texto = _texto(valor)

    if not texto:
        return ""

    categorias = []

    for categoria in texto.split(","):
        categoria = categoria.strip()

        # Eliminar prefijos de idioma al principio de cada categoría.
        if len(categoria) > 3 and categoria[2] == ":":
            categoria = categoria[3:].strip()

        if not categoria:
            continue

        if categoria.casefold() not in {
            existente.casefold() for existente in categorias
        }:
            categorias.append(categoria)

    return ", ".join(categorias)


def _texto_embedding(row: pd.Series) -> str:
    """
    Construye el texto para generar el embedding.

    Requiere un nombre válido para identificar el alimento.
    Las categorías aportan contexto adicional.
    """

    nombre = _texto(row.get("nombre"), limite=200)

    # No generar embeddings de registros sin nombre.
    if not nombre:
        return ""

    categorias = _limpiar_categorias(
        row.get("categories")
    )

    if categorias:
        return f"{nombre} — {categorias}"

    return nombre



def _construir_payload(row: pd.Series) -> dict | None:
    """
    Construye el payload de un alimento para Qdrant.

    Devuelve None si el alimento no tiene un nombre válido.
    Omite nutrientes desconocidos y conserva los ceros reales.
    """

    nombre = _texto(
        row.get("nombre"),
        limite=200,
    )

    if not nombre:
        return None

    payload = {
        # Identificación
        "nombre": nombre,

        "nombre_normalizado": _texto(
            row.get("nombre_normalizado"),
            limite=200,
        ),

        # Información nutricional
        "kcal_100g": _nutriente(
            row.get("energy-kcal_100g")
        ),

        "kcal_estimadas_100g": _num(
            row.get("kcal_estimadas_100g")
        ),

        "diferencia_kcal_relativa": _num(
            row.get("diferencia_kcal_relativa")
        ),

        "calidad_nutricional": _texto(
            row.get("calidad_nutricional")
        ),

        "score_calidad": _num(
            row.get("score_calidad")
        ),

        "estado_alimento": _texto(
            row.get("estado_alimento")
        ),

        "outlier_nutricional": _bool(
            row.get("outlier_nutricional")
        ),

        "proteinas_100g": _nutriente(
            row.get("proteins_100g")
        ),

        "carbos_100g": _nutriente(
            row.get("carbohydrates_100g")
        ),

        "azucares_100g": _nutriente(
            row.get("sugars_100g")
        ),

        "grasas_100g": _nutriente(
            row.get("fat_100g")
        ),

        "fibra_100g": _nutriente(
            row.get("fiber_100g")
        ),

        "sal_100g": _nutriente(
            row.get("salt_100g")
        ),

        # Información adicional
        "alergenos": _texto(
            row.get("allergens"),
            limite=300,
        ),

        "categorias": _limpiar_categorias(
            row.get("categories")
        )[:500],
    }

    return _filtrar_nutrientes_desconocidos(payload)


# ---------------------------------------------------------------------------
# Gestión de la colección Qdrant
# ---------------------------------------------------------------------------

def reconstruir_coleccion(cliente: QdrantClient) -> None:
    """
    Elimina la colección actual 'alimentos', si existe,
    y crea una nueva vacía con la configuración correcta.

    ATENCIÓN: esta operación elimina los puntos existentes.
    """

    colecciones = [
        coleccion.name
        for coleccion in cliente.get_collections().collections
    ]

    if COLECCION in colecciones:
        logger.warning(
            "⚠️ Eliminando colección existente '%s'...",
            COLECCION,
        )

        cliente.delete_collection(
            collection_name=COLECCION
        )

        logger.info(
            "Colección anterior eliminada ✓"
        )

    logger.info(
        "Creando colección '%s'...",
        COLECCION,
    )

    cliente.create_collection(
        collection_name=COLECCION,
        vectors_config=VectorParams(
            size=DIMENSION_VECTOR,
            distance=Distance.COSINE,
        ),
    )

    logger.info(
        "Colección nueva creada ✓"
    )


# ---------------------------------------------------------------------------
# Migración principal
# ---------------------------------------------------------------------------


def migrar() -> None:

    # -----------------------------------------------------------------------
    # 1. Variables de entorno
    # -----------------------------------------------------------------------

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        logger.error(
            "❌ QDRANT_URL no está configurada en el .env"
        )
        sys.exit(1)

    if not qdrant_api_key:
        logger.error(
            "❌ QDRANT_API_KEY no está configurada en el .env"
        )
        sys.exit(1)

    logger.info(
        "Conectando a Qdrant Cloud: %s",
        qdrant_url,
    )

    cliente = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
    )

    # -----------------------------------------------------------------------
    # 2. Comprobar CSV
    # -----------------------------------------------------------------------

    if not RUTA_CSV.exists():
        logger.error(
            "❌ CSV no encontrado: %s",
            RUTA_CSV.resolve(),
        )
        sys.exit(1)

    logger.info(
        "Leyendo %s ...",
        RUTA_CSV,
    )

    df = pd.read_csv(
        RUTA_CSV,
        low_memory=False,
    )

    total = len(df)

    logger.info(
        "Total alimentos: %d",
        total,
    )

    if total == 0:
        logger.error(
            "❌ El CSV está vacío."
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 3. Cargar modelo
    # -----------------------------------------------------------------------

    logger.info(
        "Cargando modelo FastEmbed '%s'...",
        MODELO_EMBEDDINGS,
    )

    modelo = TextEmbedding(
        MODELO_EMBEDDINGS
    )

    logger.info(
        "Modelo cargado ✓"
    )

    # -----------------------------------------------------------------------
    # 4. Reconstruir colección
    # -----------------------------------------------------------------------

    logger.warning(
        "⚠️ Se va a RECONSTRUIR la colección '%s'.",
        COLECCION,
    )

    # ATENCIÓN:
    # Esta función elimina la colección existente.
    # No ejecutar sin autorización y sin una copia de seguridad.

    reconstruir_coleccion(cliente)

    # -----------------------------------------------------------------------
    # 5. Migración por lotes
    # -----------------------------------------------------------------------

    subidos = 0
    errores = 0
    descartados = 0

    lotes_totales = (
        total + TAMANO_LOTE - 1
    ) // TAMANO_LOTE

    for n_lote, inicio in enumerate(
        range(0, total, TAMANO_LOTE)
    ):

        lote = df.iloc[
            inicio:inicio + TAMANO_LOTE
        ]

        # ---------------------------------------------------------------
        # 5.1. Preparar registros válidos
        # ---------------------------------------------------------------

        registros_validos = []

        for indice, row in lote.iterrows():

            texto = _texto_embedding(row)

            if not texto:
                descartados += 1
                continue

            registros_validos.append(
                (indice, row, texto)
            )

        textos = [
            texto
            for _, _, texto in registros_validos
        ]

        if not textos:

            logger.warning(
                "Lote %d/%d sin alimentos válidos.",
                n_lote + 1,
                lotes_totales,
            )

            continue

        # ---------------------------------------------------------------
        # 5.2. Generar embeddings
        # ---------------------------------------------------------------

        vectores = list(
            modelo.embed(textos)
        )

        if len(vectores) != len(registros_validos):

            logger.error(
                "Número de vectores incorrecto en lote %d/%d.",
                n_lote + 1,
                lotes_totales,
            )

            errores += len(registros_validos)
            continue

        # ---------------------------------------------------------------
        # 5.3. Construir puntos utilizando el payload tipado
        # ---------------------------------------------------------------

        puntos: list[PointStruct] = []

        for j, (_, row, _) in enumerate(
            registros_validos
        ):

            payload = _construir_payload(row)

            # Protección adicional por si el payload
            # no puede construirse correctamente.

            if payload is None:
                descartados += 1
                continue

            puntos.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vectores[j],
                    payload=payload,
                )
            )

        if not puntos:
            logger.warning(
                "Lote %d/%d sin puntos válidos para subir.",
                n_lote + 1,
                lotes_totales,
            )
            continue

        # ---------------------------------------------------------------
        # 5.4. Subir lote a Qdrant
        # ---------------------------------------------------------------

        try:

            cliente.upsert(
                collection_name=COLECCION,
                points=puntos,
            )

            subidos += len(puntos)

        except Exception as exc:

            logger.warning(
                "Error en lote %d/%d: %s",
                n_lote + 1,
                lotes_totales,
                exc,
            )

            errores += len(puntos)
            continue

        # ---------------------------------------------------------------
        # 5.5. Mostrar progreso
        # ---------------------------------------------------------------

        if (
            (n_lote + 1) % LOG_CADA == 0
            or (n_lote + 1) == lotes_totales
        ):

            procesados = (
                subidos + descartados + errores
            )

            pct = (
                100 * procesados // total
            )

            logger.info(
                "Lote %d/%d — "
                "%d subidos, %d descartados, "
                "%d errores (%d%% procesado)",
                n_lote + 1,
                lotes_totales,
                subidos,
                descartados,
                errores,
                pct,
            )

    # -----------------------------------------------------------------------
    # 6. Verificación final
    # -----------------------------------------------------------------------

    info_final = cliente.get_collection(
        COLECCION
    )

    puntos_finales = (
        info_final.points_count or 0
    )

    logger.info(
        "─" * 60
    )

    logger.info(
        "✅ RESUMEN DE MIGRACIÓN"
    )

    logger.info(
        "   Alimentos originales: %d",
        total,
    )

    logger.info(
        "   Subidos correctamente: %d",
        subidos,
    )

    logger.info(
        "   Descartados: %d",
        descartados,
    )

    logger.info(
        "   Errores: %d",
        errores,
    )

    logger.info(
        "   Puntos en Qdrant: %d",
        puntos_finales,
    )

    logger.info(
        "─" * 60
    )

    # -----------------------------------------------------------------------
    # 7. Comprobación final
    # -----------------------------------------------------------------------

    procesados = (
        subidos + descartados + errores
    )

    if (
        errores == 0
        and procesados == total
        and puntos_finales == subidos
    ):

        logger.info(
            "🎉 Migración completada. "
            "Los puntos de Qdrant coinciden con los registros válidos."
        )

    else:

        logger.warning(
            "⚠️ MIGRACIÓN INCOMPLETA O INCONSISTENTE."
        )

        logger.warning(
            "Registros contabilizados: %d/%d",
            procesados,
            total,
        )

        logger.warning(
            "Puntos esperados: %d | Puntos encontrados: %d",
            subidos,
            puntos_finales,
        )


if __name__ == "__main__":
    migrar()
