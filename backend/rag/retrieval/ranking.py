
"""Ranking unificado de candidatos recuperados.

Combina señales léxicas, semánticas y de fusión RRF.
Trabaja exclusivamente con modelos tipados del dominio.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.rag.models import (
    CandidatoAlimento,
    DesgloseRanking,
    MetricasRanking,
    PuntuacionRanking,
)
from backend.rag.normalization import normalizador_alimentos


@dataclass(frozen=True, slots=True)
class PesosRanking:
    """Pesos inmutables de las señales del ranking."""

    nombre_exacto: float = 30.0
    cobertura: float = 25.0
    frase_completa: float = 15.0
    orden: float = 10.0
    similitud_vectorial: float = 15.0
    fusion_rrf: float = 5.0


PESOS_RANKING = PesosRanking()


def _numero_seguro(valor: float | None) -> float:
    """Limita una señal numérica al intervalo entre 0 y 1."""

    if valor is None:
        return 0.0

    return max(0.0, min(float(valor), 1.0))


def _proporcion_ordenada(
    tokens_consulta: tuple[str, ...],
    tokens_nombre: tuple[str, ...],
) -> float:
    """Calcula qué proporción de términos aparece en el orden consultado."""

    if not tokens_consulta:
        return 0.0

    posicion_nombre = 0
    encontrados = 0

    for token in tokens_consulta:
        try:
            indice = tokens_nombre.index(token, posicion_nombre)
        except ValueError:
            continue

        encontrados += 1
        posicion_nombre = indice + 1

    return encontrados / len(tokens_consulta)


def _calcular_metricas(
    query: str,
    candidato: CandidatoAlimento,
) -> MetricasRanking:
    """Calcula todas las señales normalizadas del candidato."""

    nombre = candidato.alimento.nombre

    query_normalizada = normalizador_alimentos.normalizar_texto(query)
    nombre_normalizado = normalizador_alimentos.normalizar_texto(nombre)

    tokens_query = normalizador_alimentos.obtener_tokens(query)
    tokens_nombre = normalizador_alimentos.obtener_tokens(nombre)

    nombre_exacto = float(
        bool(
            query_normalizada
            and nombre_normalizado
            and query_normalizada == nombre_normalizado
        )
    )

    cobertura = (
        sum(
            1
            for token in tokens_query
            if token in tokens_nombre
        ) / len(tokens_query)
        if tokens_query
        else 0.0
    )

    frase_completa = float(
        bool(
            query_normalizada
            and nombre_normalizado
            and query_normalizada in nombre_normalizado
        )
    )

    orden = _proporcion_ordenada(
        tokens_query,
        tokens_nombre,
    )

    return MetricasRanking(
        nombre_exacto=nombre_exacto,
        cobertura=cobertura,
        frase_completa=frase_completa,
        orden=orden,
        similitud_vectorial=_numero_seguro(candidato.similitud),
        fusion_rrf=_numero_seguro(
            candidato.puntuacion_rrf_normalizada
        ),
    )


def _calcular_desglose(
    metricas: MetricasRanking,
) -> DesgloseRanking:
    """Convierte las señales normalizadas en puntos ponderados."""

    return DesgloseRanking(
        nombre_exacto=(
            PESOS_RANKING.nombre_exacto * metricas.nombre_exacto
        ),
        cobertura=(
            PESOS_RANKING.cobertura * metricas.cobertura
        ),
        frase_completa=(
            PESOS_RANKING.frase_completa * metricas.frase_completa
        ),
        orden=(
            PESOS_RANKING.orden * metricas.orden
        ),
        similitud_vectorial=(
            PESOS_RANKING.similitud_vectorial
            * metricas.similitud_vectorial
        ),
        fusion_rrf=(
            PESOS_RANKING.fusion_rrf * metricas.fusion_rrf
        ),
    )


def _obtener_motivos(
    metricas: MetricasRanking,
) -> tuple[str, ...]:
    """Devuelve las señales que han contribuido al ranking."""

    motivos: list[str] = []

    if metricas.nombre_exacto > 0:
        motivos.append("nombre_exacto")

    if metricas.cobertura > 0:
        motivos.append("cobertura")

    if metricas.frase_completa > 0:
        motivos.append("frase_completa")

    if metricas.orden > 0:
        motivos.append("orden")

    if metricas.similitud_vectorial > 0:
        motivos.append("similitud_vectorial")

    if metricas.fusion_rrf > 0:
        motivos.append("fusion_rrf")

    return tuple(motivos)


def calcular_score_ranking(
    query: str,
    candidato: CandidatoAlimento,
) -> PuntuacionRanking:
    """Calcula una puntuación explicable entre 0 y 1."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("La consulta no puede estar vacía.")

    if not isinstance(candidato, CandidatoAlimento):
        raise TypeError("candidato debe ser CandidatoAlimento.")

    metricas = _calcular_metricas(query, candidato)
    desglose = _calcular_desglose(metricas)

    score_sobre_cien = sum((
        desglose.nombre_exacto,
        desglose.cobertura,
        desglose.frase_completa,
        desglose.orden,
        desglose.similitud_vectorial,
        desglose.fusion_rrf,
    ))

    return PuntuacionRanking(
        total=round(score_sobre_cien / 100.0, 6),
        coincidencia_exacta=metricas.nombre_exacto,
        cobertura=metricas.cobertura,
        coincidencia_frase=metricas.frase_completa,
        orden_tokens=metricas.orden,
        similitud_vectorial=metricas.similitud_vectorial,
        fusion_rrf=metricas.fusion_rrf,
        desglose=desglose,
        motivos=_obtener_motivos(metricas),
    )


def ordenar_por_ranking(
    resultados: list[CandidatoAlimento],
    query: str,
) -> list[CandidatoAlimento]:
    """Calcula las puntuaciones y devuelve candidatos ordenados."""

    if not isinstance(query, str):
        raise TypeError("query debe ser una cadena.")

    if not query.strip():
        raise ValueError("query no puede estar vacía.")

    candidatos_puntuados: list[CandidatoAlimento] = []

    for candidato in resultados:
        puntuacion = calcular_score_ranking(
            query=query,
            candidato=candidato,
        )

        candidato_actualizado = candidato.model_copy(
            update={"puntuacion": puntuacion}
        )

        candidatos_puntuados.append(candidato_actualizado)

    # El orden es estable: los empates conservan el orden de recuperación.
    candidatos_puntuados.sort(
        key=lambda candidato: candidato.puntuacion.total
        if candidato.puntuacion is not None
        else 0.0,
        reverse=True,
    )

    return candidatos_puntuados
