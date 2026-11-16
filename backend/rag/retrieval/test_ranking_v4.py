
"""Pruebas de relevancia textual y metadatos del ranking."""

from backend.rag.models import Alimento, CandidatoAlimento
from backend.rag.retrieval.ranking import calcular_score_ranking


def crear_candidato(
    nombre: str,
    categorias: str = "",
) -> CandidatoAlimento:
    return CandidatoAlimento(
        alimento=Alimento(
            nombre=nombre,
            categorias=categorias,
        )
    )


def score(query: str, candidato: CandidatoAlimento) -> float:
    return calcular_score_ranking(query, candidato).total


def test_nombre_completo_supera_coincidencia_parcial():
    pechuga = crear_candidato("Pechuga de pollo", "Carnes, Aves")
    pate = crear_candidato("Paté de pollo", "Patés")

    assert score("pechuga de pollo", pechuga) > score(
        "pechuga de pollo",
        pate,
    )


def test_tomate_supera_producto_con_coincidencia_parcial():
    tomate = crear_candidato("Tomate")
    hummus = crear_candidato("Hummus de tomate")

    assert score("tomate", tomate) > score("tomate fresco", hummus)


def test_categoria_no_modifica_la_relevancia():
    fruta = crear_candidato("Manzana", "Frutas, Manzanas")
    bebida = crear_candidato("Manzana", "Bebidas, Zumos y néctares")

    assert score("manzana", fruta) == score("manzana", bebida)


def test_nombre_leche_supera_pan_de_leche():
    leche = crear_candidato("Leche", "Lácteos")
    pan = crear_candidato("Pan de leche", "Panadería, Bollería")

    assert score("leche", leche) > score("leche", pan)


def test_arroz_exacto_supera_arroz_preparado():
    arroz = crear_candidato("Arroz", "Cereales")
    preparado = crear_candidato("Arroz preparado", "Platos preparados")

    assert score("arroz", arroz) > score("arroz", preparado)


def test_modificador_solicitado_se_conserva():
    resultado = calcular_score_ranking(
        "paté de pollo",
        crear_candidato(
            "Paté de pollo",
            "Patés, Productos de carne",
        ),
    )

    assert resultado.total > 0
    assert resultado.coincidencia_exacta == 1.0


def test_categoria_desconocida_no_se_penaliza():
    candidato = crear_candidato(
        "Pechuga de pollo",
        "nan",
    )

    resultado = calcular_score_ranking(
        "pechuga de pollo",
        candidato,
    )

    assert resultado.total > 0
    assert resultado.coincidencia_exacta == 1.0
