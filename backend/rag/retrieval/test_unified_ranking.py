
"""Pruebas del contrato unificado y tipado del ranking."""

import pytest

from backend.rag.models import Alimento, CandidatoAlimento
from backend.rag.retrieval.ranking import (
    calcular_score_ranking,
    ordenar_por_ranking,
)


def crear_candidato(
    nombre: str,
    *,
    identificador: str | None = None,
    categorias: str = "",
    similitud: float | None = None,
    rrf: float = 0.0,
) -> CandidatoAlimento:
    return CandidatoAlimento(
        alimento=Alimento(
            id=identificador,
            nombre=nombre,
            categorias=categorias,
        ),
        similitud=similitud,
        puntuacion_rrf_normalizada=rrf,
    )


def test_nombre_exacto_supera_coincidencia_parcial():
    exacto = calcular_score_ranking(
        "pechuga de pollo",
        crear_candidato("Pechuga de pollo"),
    )
    parcial = calcular_score_ranking(
        "pechuga de pollo",
        crear_candidato("Pollo asado"),
    )

    assert exacto.total > parcial.total


def test_nombre_exacto_tiene_senal_explicita():
    resultado = calcular_score_ranking(
        "pechuga de pollo",
        crear_candidato("Pechuga de pollo"),
    )

    assert resultado.coincidencia_exacta == 1.0
    assert "nombre_exacto" in resultado.motivos


def test_cobertura_completa_supera_cobertura_parcial():
    completo = calcular_score_ranking(
        "pechuga de pollo",
        crear_candidato("Pechuga de pollo fresca"),
    )
    parcial = calcular_score_ranking(
        "pechuga de pollo",
        crear_candidato("Pollo asado"),
    )

    assert completo.cobertura > parcial.cobertura


def test_frase_completa_se_detecta():
    resultado = calcular_score_ranking(
        "pechuga de pollo",
        crear_candidato("Pechuga de pollo fresca"),
    )

    assert resultado.coincidencia_frase == 1.0


def test_orden_de_palabras_se_evalua():
    resultado = calcular_score_ranking(
        "pechuga de pollo",
        crear_candidato("Pollo pechuga"),
    )

    assert resultado.orden_tokens < 1.0


def test_similitud_vectorial_se_conserva():
    resultado = calcular_score_ranking(
        "pollo",
        crear_candidato("Pollo asado", similitud=0.93),
    )

    assert resultado.similitud_vectorial == 0.93


def test_fusion_rrf_se_evalua():
    resultado = calcular_score_ranking(
        "pollo",
        crear_candidato("Pollo", rrf=0.8),
    )

    assert resultado.fusion_rrf == 0.8
    assert resultado.desglose.fusion_rrf == 4.0


def test_las_categorias_no_alteran_la_puntuacion():
    sin_categoria = calcular_score_ranking(
        "pollo",
        crear_candidato("Pechuga de pollo"),
    )
    con_categoria = calcular_score_ranking(
        "pollo",
        crear_candidato(
            "Pechuga de pollo",
            categorias="Carnes, Aves",
        ),
    )

    assert sin_categoria.total == con_categoria.total


def test_categoria_desconocida_no_penaliza():
    resultado = calcular_score_ranking(
        "pollo",
        crear_candidato(
            "Pechuga de pollo",
            categorias="nan",
        ),
    )

    assert resultado.total > 0


def test_puntuacion_esta_normalizada():
    resultado = calcular_score_ranking(
        "pechuga de pollo",
        crear_candidato(
            "Pechuga de pollo",
            similitud=0.93,
            rrf=0.8,
        ),
    )

    assert 0.0 <= resultado.total <= 1.0


def test_consulta_vacia_se_rechaza():
    with pytest.raises(ValueError):
        calcular_score_ranking(
            "",
            crear_candidato("Pechuga de pollo"),
        )


def test_ordenacion_devuelve_candidatos_tipados():
    candidatos = [
        crear_candidato("Pollo asado", identificador="2"),
        crear_candidato("Pechuga de pollo", identificador="1"),
    ]

    resultado = ordenar_por_ranking(
        candidatos,
        "pechuga de pollo",
    )

    assert resultado[0].alimento.id == "1"
    assert all(
        isinstance(candidato, CandidatoAlimento)
        for candidato in resultado
    )
    assert all(
        candidato.puntuacion is not None
        for candidato in resultado
    )


def test_ordenacion_no_modifica_candidatos_originales():
    candidatos = [
        crear_candidato("Pollo asado"),
        crear_candidato("Pechuga de pollo"),
    ]

    ordenar_por_ranking(candidatos, "pechuga de pollo")

    assert all(
        candidato.puntuacion is None
        for candidato in candidatos
    )
