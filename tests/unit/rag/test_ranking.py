
import pytest

from backend.rag.models import (
    Alimento,
    CandidatoAlimento,
    FuenteBusqueda,
)
from backend.rag.retrieval.ranking import (
    calcular_score_ranking,
    ordenar_por_ranking,
)


def crear_candidato(
    nombre: str,
    similitud: float | None = None,
    puntuacion_textual: float = 0.0,
    puntuacion_rrf: float = 0.0,
    puntuacion_rrf_normalizada: float = 0.0,
) -> CandidatoAlimento:
    return CandidatoAlimento(
        alimento=Alimento(nombre=nombre),
        similitud=similitud,
        puntuacion_textual=puntuacion_textual,
        puntuacion_rrf=puntuacion_rrf,
        puntuacion_rrf_normalizada=puntuacion_rrf_normalizada,
        fuentes=(FuenteBusqueda.TEXTUAL,),
    )


def test_nombre_exacto_obtiene_puntuacion_maxima_lexica():
    candidato = crear_candidato("Yogur natural")

    puntuacion = calcular_score_ranking(
        "Yogur natural",
        candidato,
    )

    assert puntuacion.total == pytest.approx(0.80)
    assert puntuacion.coincidencia_exacta == 1.0
    assert puntuacion.cobertura == 1.0
    assert puntuacion.coincidencia_frase == 1.0
    assert puntuacion.orden_tokens == 1.0


def test_ranking_devuelve_modelos_tipados():
    candidatos = [
        crear_candidato("Leche entera"),
        crear_candidato("Yogur natural"),
    ]

    resultados = ordenar_por_ranking(
        candidatos,
        "Yogur natural",
    )

    assert len(resultados) == 2
    assert all(
        isinstance(candidato, CandidatoAlimento)
        for candidato in resultados
    )
    assert resultados[0].alimento.nombre == "Yogur natural"
    assert resultados[0].puntuacion is not None


def test_ranking_conserva_los_candidatos_originales():
    candidato = crear_candidato("Yogur natural")

    ordenar_por_ranking(
        [candidato],
        "Yogur natural",
    )

    assert candidato.puntuacion is None


def test_ranking_incorpora_similitud_vectorial():
    candidato = crear_candidato(
        nombre="Yogur natural",
        similitud=0.90,
    )

    puntuacion = calcular_score_ranking(
        "Yogur natural",
        candidato,
    )

    assert puntuacion.similitud_vectorial == pytest.approx(0.90)
    assert puntuacion.desglose.similitud_vectorial == pytest.approx(13.5)


def test_ranking_incorpora_fusion_rrf():
    candidato = crear_candidato(
        nombre="Yogur natural",
        puntuacion_rrf_normalizada=0.80,
    )

    puntuacion = calcular_score_ranking(
        "Yogur natural",
        candidato,
    )

    assert puntuacion.fusion_rrf == pytest.approx(0.80)
    assert puntuacion.desglose.fusion_rrf == pytest.approx(4.0)


def test_ranking_rechaza_consulta_vacia():
    candidato = crear_candidato("Yogur natural")

    with pytest.raises(ValueError):
        calcular_score_ranking("", candidato)


def test_ordenacion_rechaza_consulta_vacia():
    with pytest.raises(ValueError):
        ordenar_por_ranking([], "")
