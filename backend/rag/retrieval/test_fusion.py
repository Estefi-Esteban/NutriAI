
"""Pruebas del contrato tipado de la fusión RRF."""

import pytest

from backend.rag.models import (
    Alimento,
    CandidatoAlimento,
    FuenteBusqueda,
)
from backend.rag.retrieval.fusion import fusionar_resultados


def crear_candidato(
    identificador: str | None,
    nombre: str,
    similitud: float | None = None,
    puntuacion_textual: float = 0.0,
) -> CandidatoAlimento:
    return CandidatoAlimento(
        alimento=Alimento(
            id=identificador,
            nombre=nombre,
        ),
        similitud=similitud,
        puntuacion_textual=puntuacion_textual,
    )


def test_fusiona_resultados_de_ambas_busquedas():
    textuales = [
        crear_candidato("1", "Pechuga de pollo"),
        crear_candidato("2", "Muslo de pollo"),
    ]

    vectoriales = [
        crear_candidato("3", "Pollo asado", similitud=0.91),
        crear_candidato("1", "Pechuga de pollo", similitud=0.95),
    ]

    resultado = fusionar_resultados(textuales, vectoriales)

    identificadores = {
        candidato.alimento.id
        for candidato in resultado
    }

    assert identificadores == {"1", "2", "3"}
    assert len(resultado) == 3


def test_elimina_duplicados_entre_fuentes():
    resultado = fusionar_resultados(
        [
            crear_candidato("1", "Pechuga de pollo"),
        ],
        [
            crear_candidato(
                "1",
                "Pechuga de pollo",
                similitud=0.95,
            ),
        ],
    )

    assert len(resultado) == 1
    assert resultado[0].alimento.id == "1"


def test_prioriza_candidato_presente_en_ambas_busquedas():
    textuales = [
        crear_candidato("1", "Pechuga de pollo"),
        crear_candidato("2", "Muslo de pollo"),
    ]

    vectoriales = [
        crear_candidato("2", "Muslo de pollo", similitud=0.90),
        crear_candidato("3", "Pollo asado", similitud=0.80),
    ]

    resultado = fusionar_resultados(textuales, vectoriales)

    assert resultado[0].alimento.id == "2"
    assert (
        resultado[0].puntuacion_rrf
        > resultado[1].puntuacion_rrf
    )


def test_conserva_las_fuentes_de_busqueda():
    resultado = fusionar_resultados(
        [crear_candidato("1", "Yogur natural")],
        [
            crear_candidato(
                "1",
                "Yogur natural",
                similitud=0.95,
            ),
        ],
    )

    assert resultado[0].fuentes == (
        FuenteBusqueda.TEXTUAL,
        FuenteBusqueda.VECTORIAL,
    )


def test_acepta_listas_vacias():
    assert fusionar_resultados([], []) == []


def test_acepta_una_lista_vacia():
    resultado = fusionar_resultados(
        [crear_candidato("1", "Yogur natural")],
        [],
    )

    assert len(resultado) == 1
    assert resultado[0].alimento.nombre == "Yogur natural"
    assert resultado[0].fuentes == (FuenteBusqueda.TEXTUAL,)


def test_rechaza_resultados_no_tipados():
    with pytest.raises(TypeError, match="CandidatoAlimento"):
        fusionar_resultados(
            [{"nombre": "Yogur natural"}],
            [],
        )


@pytest.mark.parametrize("k", [0, -1, True, False, 1.5])
def test_rechaza_parametros_k_invalidos(k):
    with pytest.raises(ValueError):
        fusionar_resultados([], [], k=k)
