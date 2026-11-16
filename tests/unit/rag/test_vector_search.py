
from types import SimpleNamespace
from unittest.mock import patch

from backend.rag.models import (
    CandidatoAlimento,
    FuenteBusqueda,
)
from backend.rag.retrieval.vector_search import (
    buscar_candidatos_por_vector,
)


def crear_punto_qdrant(
    nombre: str = "Pechuga de pollo",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=123,
        score=0.90,
        payload={
            "nombre": nombre,
            "nombre_normalizado": nombre.lower(),
            "kcal_100g": 110.0,
            "proteinas_100g": 23.0,
            "carbos_100g": 0.0,
            "azucares_100g": 0.0,
            "grasas_100g": 1.5,
            "fibra_100g": 0.0,
            "sal_100g": 0.12,
            "alergenos": "",
            "categorias": "es:carnes",
            "calidad_nutricional": "alta",
            "score_calidad": 92.0,
            "estado_alimento": "validado",
            "outlier_nutricional": False,
        },
    )


@patch("backend.rag.retrieval.vector_search.search_by_vector")
@patch("backend.rag.retrieval.vector_search.embed_text")
def test_busqueda_vectorial_devuelve_modelos_tipados(
    mock_embedding,
    mock_search,
):
    mock_embedding.return_value = [0.1, 0.2, 0.3]
    mock_search.return_value = [crear_punto_qdrant()]

    resultado = buscar_candidatos_por_vector("pollo")

    assert len(resultado) == 1
    assert isinstance(resultado[0], CandidatoAlimento)
    assert resultado[0].alimento.nombre == "Pechuga de pollo"
    assert resultado[0].alimento.id == "123"
    assert resultado[0].similitud == 0.90
    assert resultado[0].fuentes == (
        FuenteBusqueda.VECTORIAL,
    )


@patch("backend.rag.retrieval.vector_search.search_by_vector")
@patch("backend.rag.retrieval.vector_search.embed_text")
def test_busqueda_vectorial_sin_nombre(
    mock_embedding,
    mock_search,
):
    mock_embedding.return_value = [0.1, 0.2, 0.3]
    mock_search.return_value = [
        crear_punto_qdrant(nombre="")
    ]

    resultado = buscar_candidatos_por_vector("pollo")

    assert resultado == []


@patch("backend.rag.retrieval.vector_search.search_by_vector")
@patch("backend.rag.retrieval.vector_search.embed_text")
def test_busqueda_vectorial_vacia_no_consulta_qdrant(
    mock_embedding,
    mock_search,
):
    resultado = buscar_candidatos_por_vector("")

    assert resultado == []
    mock_embedding.assert_not_called()
    mock_search.assert_not_called()
