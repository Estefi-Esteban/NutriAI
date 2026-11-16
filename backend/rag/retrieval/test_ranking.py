
"""Pruebas de integración del ranking y la búsqueda textual."""

from types import SimpleNamespace

import pytest

from backend.rag.core import qdrant_service
from backend.rag.models import CandidatoAlimento, FuenteBusqueda
from backend.rag.normalization import normalizador_alimentos
from backend.rag.retrieval import text_search


def crear_registro(
    identificador: str,
    nombre: str,
    nombre_normalizado: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=identificador,
        payload={
            "nombre": nombre,
            "nombre_normalizado": nombre_normalizado or nombre.lower(),
            "kcal_100g": 91.0,
        },
    )


def test_normalizacion_unicode_conserva_el_contenido():
    assert normalizador_alimentos.normalizar_texto("plátano") == "platano"
    assert normalizador_alimentos.normalizar_texto("selección") == "seleccion"


def test_busqueda_devuelve_candidatos_tipados(monkeypatch):
    registros = [
        crear_registro("1", "Plátano"),
        crear_registro("2", "Chips de plátano"),
    ]

    monkeypatch.setattr(
        text_search,
        "search_by_text_paginated",
        lambda **kwargs: registros,
    )

    resultados = text_search.buscar_por_texto("plátano", limite=10)

    assert resultados
    assert all(
        isinstance(resultado, CandidatoAlimento)
        for resultado in resultados
    )
    assert resultados[0].fuentes == (FuenteBusqueda.TEXTUAL,)
    assert resultados[0].puntuacion is not None


def test_nombre_exacto_prioriza_alimento_sobre_derivados(monkeypatch):
    registros = [
        crear_registro("yogurt", "Yogurt de Plátano"),
        crear_registro("chips", "Chips de plátano"),
        crear_registro("natural", "Plátano"),
        crear_registro("canarias", "Plátano de Canarias IPG"),
    ]

    monkeypatch.setattr(
        text_search,
        "search_by_text_paginated",
        lambda **kwargs: registros,
    )

    resultados = text_search.buscar_por_texto("plátano", limite=10)

    assert resultados
    assert resultados[0].alimento.id == "natural"
    assert resultados[0].alimento.nombre == "Plátano"


def test_equivalencia_del_normalizador_permite_recuperar_alias(monkeypatch):
    registros = [
        crear_registro("deli", "Deli banana"),
        crear_registro("banana", "Banana"),
        crear_registro("platano", "Plátano"),
    ]

    monkeypatch.setattr(
        text_search,
        "search_by_text_paginated",
        lambda **kwargs: registros,
    )

    resultados = text_search.buscar_por_texto("banana", limite=10)

    assert resultados
    assert any(
        resultado.alimento.nombre == "Plátano"
        for resultado in resultados
    )
    assert resultados[0].alimento.nombre == "Banana"


def test_restriccion_sin_azucar_no_se_relaja():
    assert text_search.calcular_score_textual(
        "yogurt sin azúcar",
        "Yogurt sin azúcar",
    ) > 0

    assert text_search.calcular_score_textual(
        "yogurt sin azúcar",
        "Yogurt natural",
    ) == 0


def test_limite_de_resultados_se_respeta(monkeypatch):
    registros = [
        crear_registro(str(indice), f"Producto plátano {indice}")
        for indice in range(15)
    ]

    monkeypatch.setattr(
        text_search,
        "search_by_text_paginated",
        lambda **kwargs: registros,
    )

    resultados = text_search.buscar_por_texto("plátano", limite=5)

    assert len(resultados) == 5


def test_search_by_text_paginated_recoge_varias_paginas(monkeypatch):
    primera_pagina = [
        crear_registro("1", "Plátano", "platano")
    ]
    segunda_pagina = [
        crear_registro(
            "2",
            "Plátano de Canarias IPG",
            "platano de canarias ipg",
        )
    ]

    llamadas = []

    class ClienteQdrantSimulado:
        def scroll(self, **kwargs):
            llamadas.append(kwargs)

            if len(llamadas) == 1:
                return primera_pagina, "cursor-2"

            return segunda_pagina, None

    monkeypatch.setattr(
        qdrant_service,
        "get_qdrant_client",
        lambda: ClienteQdrantSimulado(),
    )

    resultados = qdrant_service.search_by_text_paginated(
        "platano",
        max_candidates=10,
        page_size=1,
    )

    assert [registro.id for registro in resultados] == ["1", "2"]
    assert len(llamadas) == 2
    assert llamadas[1]["offset"] == "cursor-2"
    assert all(
        llamada["with_vectors"] is False
        for llamada in llamadas
    )


@pytest.mark.parametrize(
    ("parametros", "valor"),
    [
        ({"max_candidates": 0}, "max_candidates"),
        ({"page_size": 101}, "page_size"),
    ],
)
def test_search_by_text_paginated_valida_limites(parametros, valor):
    with pytest.raises(ValueError):
        qdrant_service.search_by_text_paginated(
            "platano",
            **parametros,
        )
