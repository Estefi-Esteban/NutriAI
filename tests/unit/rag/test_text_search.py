
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.rag.models import (
    CandidatoAlimento,
    FuenteBusqueda,
)
from backend.rag.retrieval.text_search import (
    buscar_candidatos_por_texto,
    calcular_score_textual,
)


def crear_registro(
    identificador: int,
    nombre: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=identificador,
        payload={
            "nombre": nombre,
            "nombre_normalizado": nombre.lower(),
            "kcal_100g": 65,
            "proteinas_100g": 4,
        },
    )


def test_score_textual_nombre_exacto():
    puntuacion = calcular_score_textual(
        "yogur natural",
        "Yogur natural",
    )

    assert puntuacion == pytest.approx(150.0)


def test_score_textual_nombre_parcial():
    puntuacion = calcular_score_textual(
        "yogur natural",
        "Yogur natural de vaca",
    )

    assert puntuacion < 150.0
    assert puntuacion > 0.0


def test_restriccion_critica_no_coincidente():
    puntuacion = calcular_score_textual(
        "yogur sin lactosa",
        "Yogur natural",
    )

    assert puntuacion == 0.0


def test_busqueda_textual_devuelve_modelos_tipados():
    registros = [
        crear_registro(1, "Yogur natural"),
        crear_registro(2, "Leche entera"),
    ]

    with patch(
        "backend.rag.retrieval.text_search.search_by_text_paginated",
        return_value=registros,
    ):
        resultados = buscar_candidatos_por_texto(
            "yogur natural",
            aplicar_ranking=False,
        )

    assert len(resultados) == 2
    assert all(
        isinstance(candidato, CandidatoAlimento)
        for candidato in resultados
    )

    assert resultados[0].alimento.nombre == "Yogur natural"
    assert resultados[0].fuentes == (FuenteBusqueda.TEXTUAL,)


def test_busqueda_textual_elimina_duplicados():
    registro = crear_registro(1, "Yogur natural")

    with patch(
        "backend.rag.retrieval.text_search.search_by_text_paginated",
        return_value=[registro],
    ):
        resultados = buscar_candidatos_por_texto(
            "banana",
            aplicar_ranking=False,
        )

    assert len(resultados) == 1


def test_busqueda_textual_vacia_no_consulta_qdrant():
    with patch(
        "backend.rag.retrieval.text_search.search_by_text_paginated"
    ) as buscar:
        resultados = buscar_candidatos_por_texto(" ")

    assert resultados == []
    buscar.assert_not_called()


def test_limite_invalido():
    with pytest.raises(ValueError):
        buscar_candidatos_por_texto(
            "yogur",
            limite=0,
        )
