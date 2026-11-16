
"""Fusión de candidatos recuperados mediante Reciprocal Rank Fusion.

Combina resultados textuales y vectoriales utilizando modelos tipados.
Cada fuente aporta como máximo una contribución por candidato.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.rag.models import CandidatoAlimento, FuenteBusqueda
from backend.rag.normalization import normalizador_alimentos


def _obtener_clave(candidato: CandidatoAlimento) -> str:
    """Identifica un candidato mediante ID o nombre normalizado.

    El ID tiene prioridad. El nombre solo se utiliza como alternativa
    cuando el candidato no dispone de un identificador válido.
    """
    identificador = candidato.alimento.id

    if identificador is not None and identificador.strip():
        return f"id:{identificador.strip()}"

    nombre = normalizador_alimentos.normalizar_texto(
        candidato.alimento.nombre
    )

    if nombre:
        return f"nombre:{nombre}"

    return ""


def _validar_resultados(
    resultados: Sequence[CandidatoAlimento],
) -> None:
    """Comprueba que todos los elementos sean candidatos tipados."""
    for candidato in resultados:
        if not isinstance(candidato, CandidatoAlimento):
            raise TypeError(
                "Todos los resultados deben ser "
                "instancias de CandidatoAlimento."
            )


def _obtener_indice(
    claves: list[str],
    clave: str,
) -> int | None:
    """Busca una clave dentro de la colección de candidatos."""
    try:
        return claves.index(clave)
    except ValueError:
        return None


def _crear_candidato_inicial(
    original: CandidatoAlimento,
    fuente: FuenteBusqueda,
    posicion: int,
    contribucion: float,
) -> CandidatoAlimento:
    """Crea un candidato con metadatos de la búsqueda actual."""
    es_textual = fuente == FuenteBusqueda.TEXTUAL

    return original.model_copy(
        update={
            "puntuacion_rrf": contribucion,
            "puntuacion_rrf_normalizada": 0.0,
            "puntuacion_textual": (
                original.puntuacion_textual if es_textual else 0.0
            ),
            "similitud": (
                None if es_textual else original.similitud
            ),
            "posicion_textual": posicion if es_textual else None,
            "posicion_vectorial": None if es_textual else posicion,
            "fuentes": (fuente,),
            "puntuacion": None,
        }
    )


def _fusionar_candidato(
    existente: CandidatoAlimento,
    nuevo: CandidatoAlimento,
    fuente: FuenteBusqueda,
    posicion: int,
    contribucion: float,
) -> CandidatoAlimento:
    """Añade la contribución de una segunda fuente al candidato."""
    es_textual = fuente == FuenteBusqueda.TEXTUAL

    return existente.model_copy(
        update={
            "puntuacion_rrf": (
                existente.puntuacion_rrf + contribucion
            ),
            "puntuacion_textual": (
                max(
                    existente.puntuacion_textual,
                    nuevo.puntuacion_textual,
                )
                if es_textual
                else existente.puntuacion_textual
            ),
            "similitud": (
                nuevo.similitud
                if not es_textual
                else existente.similitud
            ),
            "posicion_textual": (
                posicion if es_textual else existente.posicion_textual
            ),
            "posicion_vectorial": (
                existente.posicion_vectorial if es_textual else posicion
            ),
            "fuentes": existente.fuentes + (fuente,),
            "puntuacion": None,
        }
    )


def _orden_desempate(
    candidato: CandidatoAlimento,
) -> tuple[float, float, float, float, str]:
    """Devuelve una clave de ordenación determinista."""
    posicion_textual = (
        candidato.posicion_textual
        if candidato.posicion_textual is not None
        else float("inf")
    )
    posicion_vectorial = (
        candidato.posicion_vectorial
        if candidato.posicion_vectorial is not None
        else float("inf")
    )

    identificador = candidato.alimento.id or ""
    nombre = normalizador_alimentos.normalizar_texto(
        candidato.alimento.nombre
    )

    return (
        -candidato.puntuacion_rrf,
        posicion_textual,
        posicion_vectorial,
        -candidato.puntuacion_textual,
        identificador or nombre,
    )


def fusionar_resultados(
    resultados_textuales: Sequence[CandidatoAlimento],
    resultados_vectoriales: Sequence[CandidatoAlimento],
    k: int = 60,
) -> list[CandidatoAlimento]:
    """Fusiona rankings textuales y vectoriales mediante RRF.

    Las posiciones originales comienzan en 1. Los duplicados dentro
    de una misma fuente conservan su primera posición y solo aportan
    una contribución RRF.

    La fusión genera puntuaciones y fuentes nuevas para esta ejecución;
    no acumula metadatos de fusiones anteriores.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k debe ser un entero mayor o igual que 1.")

    _validar_resultados(resultados_textuales)
    _validar_resultados(resultados_vectoriales)

    claves: list[str] = []
    candidatos: list[CandidatoAlimento] = []

    fuentes_resultados = (
        (FuenteBusqueda.TEXTUAL, resultados_textuales),
        (FuenteBusqueda.VECTORIAL, resultados_vectoriales),
    )

    for fuente, resultados in fuentes_resultados:
        claves_vistas_en_fuente: list[str] = []

        for posicion, original in enumerate(resultados, start=1):
            clave = _obtener_clave(original)

            if not clave:
                continue

            # Una fuente no puede contribuir varias veces al mismo ID.
            if clave in claves_vistas_en_fuente:
                continue

            claves_vistas_en_fuente.append(clave)

            contribucion = 1.0 / (k + posicion)
            indice = _obtener_indice(claves, clave)

            if indice is None:
                candidato = _crear_candidato_inicial(
                    original=original,
                    fuente=fuente,
                    posicion=posicion,
                    contribucion=contribucion,
                )
                claves.append(clave)
                candidatos.append(candidato)
                continue

            candidatos[indice] = _fusionar_candidato(
                existente=candidatos[indice],
                nuevo=original,
                fuente=fuente,
                posicion=posicion,
                contribucion=contribucion,
            )

    puntuacion_maxima = 2.0 / (k + 1)

    candidatos_normalizados = [
        candidato.model_copy(
            update={
                "puntuacion_rrf_normalizada": min(
                    candidato.puntuacion_rrf / puntuacion_maxima,
                    1.0,
                )
            }
        )
        for candidato in candidatos
    ]

    candidatos_normalizados.sort(key=_orden_desempate)

    return candidatos_normalizados
