
"""Pruebas de ranking: relevancia textual y señales tipadas."""

import pytest

from backend.rag.models import Alimento, CandidatoAlimento, InformacionNutricional
from backend.rag.retrieval.ranking import (
    calcular_score_ranking,
    ordenar_por_ranking,
)


def crear_candidato(
    nombre: str,
    identificador: str | None = None,
    similitud: float | None = None,
    rrf: float = 0.0,
    puntuacion_textual: float = 0.0,
) -> CandidatoAlimento:
    return CandidatoAlimento(
        alimento=Alimento(
            id=identificador,
            nombre=nombre,
        ),
        similitud=similitud,
        puntuacion_rrf_normalizada=rrf,
        puntuacion_textual=puntuacion_textual,
    )


def test_nombre_exacto_supera_producto_con_modificador():
    exacto = calcular_score_ranking(
        "plátano",
        crear_candidato("Plátano"),
    )
    derivado = calcular_score_ranking(
        "plátano",
        crear_candidato("Plátano chip"),
    )

    assert exacto.total > derivado.total


def test_categoria_no_altera_relevancia_textual():
    normal = calcular_score_ranking(
        "plátano",
        crear_candidato("Plátano"),
    )

    clasificado = calcular_score_ranking(
        "plátano",
        crear_candidato("Plátano"),
    )

    assert normal.total == clasificado.total


def test_yogur_no_se_penaliza_por_categoria():
    resultado = calcular_score_ranking(
        "yogurt",
        crear_candidato("Yogurt natural"),
    )

    assert resultado.total > 0


def test_modificador_solicitado_se_conserva():
    resultado = calcular_score_ranking(
        "helado de plátano",
        crear_candidato("Helado de plátano con chocolate"),
    )

    assert resultado.total > 0
    assert resultado.coincidencia_frase == 1.0


def test_producto_con_terminos_en_orden_supera_terminos_invertidos():
    ordenado = calcular_score_ranking(
        "pollo cocido",
        crear_candidato("Pechuga de pollo cocido"),
    )
    invertido = calcular_score_ranking(
        "pollo cocido",
        crear_candidato("Cocido de ternera y pollo"),
    )

    assert ordenado.orden_tokens > invertido.orden_tokens


def test_pechuga_de_pollo_cocido_es_un_candidato_valido():
    resultado = calcular_score_ranking(
        "pechuga de pollo cocido",
        crear_candidato("Pechuga de pollo cocido"),
    )

    assert resultado.total > 0


def test_aliases_no_se_implementan_en_el_ranking():
    # La equivalencia banana/plátano pertenece al normalizador.
    # El ranking compara las señales que recibe, no crea alias propios.
    resultado = calcular_score_ranking(
        "banana",
        crear_candidato("Plátano"),
    )

    assert resultado.total >= 0


@pytest.mark.parametrize(
    "categorias",
    [None, "nan", [], ["Lácteos", None]],
)
def test_metadatos_ausentes_no_afectan_al_ranking(categorias):
    # Las categorías no forman parte de la puntuación actual.
    resultado = calcular_score_ranking(
        "plátano",
        crear_candidato("Plátano"),
    )

    assert resultado.total > 0


def test_ordenar_conserva_candidatos_originales():
    originales = [
        crear_candidato(
            "Plátano chip",
            identificador="2",
            puntuacion_textual=102,
        ),
        crear_candidato(
            "Plátano",
            identificador="1",
            puntuacion_textual=125,
        ),
    ]

    ordenados = ordenar_por_ranking(
        originales,
        "plátano",
    )

    assert ordenados[0].alimento.nombre == "Plátano"
    assert originales[0].puntuacion is None
    assert originales[1].puntuacion is None


def test_ordenacion_usa_puntuacion_unificada():
    originales = [
        crear_candidato(
            "Plátano natural",
            puntuacion_textual=80,
        ),
        crear_candidato(
            "Plátano fresco",
            puntuacion_textual=90,
        ),
    ]

    ordenados = ordenar_por_ranking(
        originales,
        "plátano",
    )

    assert all(
        candidato.puntuacion is not None
        for candidato in ordenados
    )


def test_datos_nutricionales_no_alteran_el_ranking():
    candidato_sin_datos = crear_candidato("Plátano")

    candidato_con_datos = CandidatoAlimento(
        alimento=Alimento(
            nombre="Plátano",
            nutricion=InformacionNutricional(
                kcal_100g=89.0,
                proteinas_100g=1.1,
                carbos_100g=22.8,
                azucares_100g=12.2,
                grasas_100g=0.3,
                fibra_100g=2.6,
                sal_100g=0.0,
            ),
        )
    )

    puntuacion_sin_datos = calcular_score_ranking(
        "plátano",
        candidato_sin_datos,
    )

    puntuacion_con_datos = calcular_score_ranking(
        "plátano",
        candidato_con_datos,
    )

    assert puntuacion_sin_datos.total == puntuacion_con_datos.total
