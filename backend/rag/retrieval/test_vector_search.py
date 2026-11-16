
from unittest.mock import patch

import pytest

from backend.rag.retrieval.vector_search import buscar_por_vector

def punto_qdrant(
    identificador="123",
    nombre="Pechuga de pollo",
    score=0.90,
):
    class Punto:
        pass

    punto = Punto()
    punto.id = identificador
    punto.score = score
    punto.payload = {
        "nombre": nombre,
        "kcal_100g": 110.0,
        "proteinas_100g": 23.0,
        "carbos_100g": 0.0,
        "grasas_100g": 1.5,
    }

    return punto


@patch("backend.rag.retrieval.vector_search.search_by_vector")
@patch("backend.rag.retrieval.vector_search.embed_text")
def test_busca_alimentos_por_vector(
    mock_embedding,
    mock_search,
):
    mock_embedding.return_value = [0.1, 0.2, 0.3]
    mock_search.return_value = [
        punto_qdrant()
    ]

    resultado = buscar_por_vector("pollo")

    assert len(resultado) == 1
    assert resultado[0]["nombre"] == "Pechuga de pollo"
    assert resultado[0]["id"] == "123"
    assert resultado[0]["similitud"] == 0.9
    assert resultado[0]["tipo_coincidencia"] == "vectorial"
    assert resultado[0]["verificado_rag"] is False

    mock_embedding.assert_called_once_with("pollo")
    mock_search.assert_called_once()


@patch("backend.rag.retrieval.vector_search.search_by_vector")
@patch("backend.rag.retrieval.vector_search.embed_text")
def test_conserva_datos_nutricionales(
    mock_embedding,
    mock_search,
):
    mock_embedding.return_value = [0.1, 0.2]
    mock_search.return_value = [
        punto_qdrant()
    ]

    resultado = buscar_por_vector("pollo")

    assert resultado[0]["kcal_100g"] == 110.0
    assert resultado[0]["proteinas_100g"] == 23.0
    assert resultado[0]["carbos_100g"] == 0.0
    assert resultado[0]["grasas_100g"] == 1.5


@patch("backend.rag.retrieval.vector_search.search_by_vector")
@patch("backend.rag.retrieval.vector_search.embed_text")
def test_consulta_vectorial_vacia(
    mock_embedding,
    mock_search,
):
    resultado = buscar_por_vector("")

    assert resultado == []
    mock_embedding.assert_not_called()
    mock_search.assert_not_called()


def test_rechaza_limite_invalido():
    with pytest.raises(ValueError):
        buscar_por_vector("pollo", limite=0)


def test_rechaza_umbral_invalido():
    with pytest.raises(ValueError):
        buscar_por_vector("pollo", umbral_similitud=1.5)


@patch("backend.rag.retrieval.vector_search.search_by_vector")
@patch("backend.rag.retrieval.vector_search.embed_text")
def test_devuelve_lista_vacia_si_falla_qdrant(
    mock_embedding,
    mock_search,
):
    mock_embedding.return_value = [0.1, 0.2]
    mock_search.side_effect = RuntimeError("Error Qdrant")

    resultado = buscar_por_vector("pollo")

    assert resultado == []
