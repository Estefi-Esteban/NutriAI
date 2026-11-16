
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
    *,
    similitud: float | None = None,
    puntuacion_textual: float = 0.0,
    fuente: FuenteBusqueda = FuenteBusqueda.TEXTUAL,
) -> CandidatoAlimento:
    return CandidatoAlimento(
        alimento=Alimento(
            id=identificador,
            nombre=nombre,
        ),
        similitud=similitud,
        puntuacion_textual=puntuacion_textual,
        fuentes=(fuente,),
    )


def test_fusiona_mismo_id_de_ambas_fuentes():
    textual = [
        crear_candidato("1", "Pollo", puntuacion_textual=0.9)
    ]
    vectorial = [
        crear_candidato(
            "1",
            "Pollo",
            similitud=0.95,
            fuente=FuenteBusqueda.VECTORIAL,
        )
    ]

    resultado = fusionar_resultados(textual, vectorial)

    assert len(resultado) == 1
    assert resultado[0].fuentes == (
        FuenteBusqueda.TEXTUAL,
        FuenteBusqueda.VECTORIAL,
    )
    assert resultado[0].posicion_textual == 1
    assert resultado[0].posicion_vectorial == 1
    assert resultado[0].similitud == pytest.approx(0.95)


def test_no_fusiona_ids_distintos_con_mismo_nombre():
    textual = [crear_candidato("1", "Pollo")]
    vectorial = [
        crear_candidato(
            "2",
            "Pollo",
            similitud=0.95,
            fuente=FuenteBusqueda.VECTORIAL,
        )
    ]

    resultado = fusionar_resultados(textual, vectorial)

    assert len(resultado) == 2


def test_fusiona_por_nombre_si_no_hay_id():
    textual = [crear_candidato(None, "Pechuga de pollo")]
    vectorial = [
        crear_candidato(
            None,
            "PECHUGA DE POLLO",
            similitud=0.95,
            fuente=FuenteBusqueda.VECTORIAL,
        )
    ]

    resultado = fusionar_resultados(textual, vectorial)

    assert len(resultado) == 1
    assert len(resultado[0].fuentes) == 2


def test_score_rrf_normalizado_entre_cero_y_uno():
    textual = [crear_candidato("1", "Pollo")]
    vectorial = [
        crear_candidato(
            "1",
            "Pollo",
            similitud=0.95,
            fuente=FuenteBusqueda.VECTORIAL,
        )
    ]

    resultado = fusionar_resultados(textual, vectorial)

    assert resultado[0].puntuacion_rrf_normalizada == pytest.approx(1.0)


def test_score_rrf_normalizado_es_menor_si_no_es_primero():
    textual = [
        crear_candidato("2", "Otro"),
        crear_candidato("1", "Pollo"),
    ]

    resultado = fusionar_resultados(textual, [])

    pollo = next(
        item for item in resultado if item.alimento.id == "1"
    )

    assert 0 < pollo.puntuacion_rrf_normalizada < 1


def test_score_rrf_original_se_conserva():
    textual = [crear_candidato("1", "Pollo")]
    vectorial = [
        crear_candidato(
            "1",
            "Pollo",
            similitud=0.95,
            fuente=FuenteBusqueda.VECTORIAL,
        )
    ]

    resultado = fusionar_resultados(textual, vectorial)

    assert resultado[0].puntuacion_rrf == pytest.approx(2 / 61)


def test_no_duplica_contribucion_de_una_fuente():
    textual = [
        crear_candidato("1", "Pollo"),
        crear_candidato("1", "Pollo"),
    ]

    resultado = fusionar_resultados(textual, [])

    assert len(resultado) == 1
    assert resultado[0].puntuacion_rrf == pytest.approx(1 / 61)
    assert resultado[0].posicion_textual == 1


def test_conserva_primera_posicion_del_duplicado():
    textual = [
        crear_candidato("1", "Pollo"),
        crear_candidato("2", "Leche"),
        crear_candidato("1", "Pollo"),
    ]

    resultado = fusionar_resultados(textual, [])

    pollo = next(
        item for item in resultado if item.alimento.id == "1"
    )

    assert pollo.posicion_textual == 1
    assert pollo.puntuacion_rrf == pytest.approx(1 / 61)


def test_id_vacio_se_trata_como_ausente():
    textual = [crear_candidato("", "Yogur natural")]
    vectorial = [
        crear_candidato(
            None,
            "YÓGUR NATURAL",
            similitud=0.95,
            fuente=FuenteBusqueda.VECTORIAL,
        )
    ]

    resultado = fusionar_resultados(textual, vectorial)

    assert len(resultado) == 1
    assert len(resultado[0].fuentes) == 2


def test_no_conserva_fuentes_heredadas():
    textual = [
        crear_candidato(
            "1",
            "Pollo",
            fuente=FuenteBusqueda.VECTORIAL,
        )
    ]

    resultado = fusionar_resultados(textual, [])

    assert resultado[0].fuentes == (FuenteBusqueda.TEXTUAL,)


def test_no_acumula_rrf_de_fusiones_anteriores():
    textual = [crear_candidato("1", "Pollo")]
    primera = fusionar_resultados(textual, [])
    segunda = fusionar_resultados(primera, [])

    assert segunda[0].puntuacion_rrf == pytest.approx(1 / 61)


@pytest.mark.parametrize("k", [0, -1, True, False, 1.5])
def test_rechaza_k_invalido(k):
    with pytest.raises(ValueError):
        fusionar_resultados([], [], k=k)


def test_rechaza_resultados_no_tipados():
    with pytest.raises(TypeError):
        fusionar_resultados([{"nombre": "Pollo"}], [])
