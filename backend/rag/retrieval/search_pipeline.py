
"""
Pipeline híbrido de recuperación de alimentos para NutriAI.

Coordina:
1. Recuperación textual.
2. Recuperación vectorial.
3. Fusión mediante Reciprocal Rank Fusion.
4. Ranking unificado.

Trabaja exclusivamente con modelos tipados.
"""

import logging

from backend.rag.models import (
    CandidatoAlimento,
    FuenteBusqueda,
    ResultadoBusqueda,
)
from backend.rag.retrieval.text_search import (
    buscar_candidatos_por_texto,
)
from backend.rag.retrieval.vector_search import (
    buscar_candidatos_por_vector,
)
from backend.rag.retrieval.fusion import fusionar_resultados
from backend.rag.retrieval.ranking import ordenar_por_ranking

logger = logging.getLogger(__name__)


def recuperar_resultado(
    query: str,
    limite_textual: int = 30,
    limite_vectorial: int = 30,
    limite_final: int = 50,
    rrf_k: int = 60,
) -> ResultadoBusqueda:
    """Recupera candidatos y conserva el estado de cada fuente."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("La consulta no puede estar vacía.")

    if not 1 <= limite_textual <= 100:
        raise ValueError("limite_textual debe estar entre 1 y 100.")

    if not 1 <= limite_vectorial <= 100:
        raise ValueError("limite_vectorial debe estar entre 1 y 100.")

    if limite_final < 1:
        raise ValueError("limite_final debe ser mayor que cero.")

    if rrf_k < 1:
        raise ValueError("rrf_k debe ser mayor o igual que 1.")

    resultados_textuales: list[CandidatoAlimento] = []
    resultados_vectoriales: list[CandidatoAlimento] = []

    busqueda_textual_correcta = False
    busqueda_vectorial_correcta = False

    try:
        resultados_textuales = buscar_candidatos_por_texto(
            query,
            limite=limite_textual,
            aplicar_ranking=False,
            propagar_errores=True,
        )
        busqueda_textual_correcta = True

    except Exception:
        logger.exception("Error en recuperación textual.")

    try:
        resultados_vectoriales = buscar_candidatos_por_vector(
            query,
            limite=limite_vectorial,
        )
        busqueda_vectorial_correcta = True

    except Exception:
        logger.exception("Error en recuperación vectorial.")

    candidatos_fusionados = fusionar_resultados(
        resultados_textuales,
        resultados_vectoriales,
        k=rrf_k,
    )

    candidatos_rankeados = ordenar_por_ranking(
        candidatos_fusionados,
        query,
    )

    candidatos_finales = tuple(candidatos_rankeados[:limite_final])

    fuentes_consultadas = (
        FuenteBusqueda.TEXTUAL,
        FuenteBusqueda.VECTORIAL,
    )

    return ResultadoBusqueda(
        consulta=query.strip(),
        candidatos=candidatos_finales,
        candidato_seleccionado=(
            candidatos_finales[0] if candidatos_finales else None
        ),
        fuentes_consultadas=fuentes_consultadas,
        busqueda_textual_correcta=busqueda_textual_correcta,
        busqueda_vectorial_correcta=busqueda_vectorial_correcta,
    )


def recuperar_candidatos(
    query: str,
    limite_textual: int = 30,
    limite_vectorial: int = 30,
    limite_final: int = 50,
    rrf_k: int = 60,
) -> list[CandidatoAlimento]:
    """Devuelve únicamente los candidatos del resultado híbrido."""

    if not isinstance(query, str) or not query.strip():
        return []

    resultado = recuperar_resultado(
        query=query,
        limite_textual=limite_textual,
        limite_vectorial=limite_vectorial,
        limite_final=limite_final,
        rrf_k=rrf_k,
    )

    return list(resultado.candidatos)
