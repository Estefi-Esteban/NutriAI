"""
Tests del módulo de evaluación del buscador de alimentos.

No usan red ni Qdrant. Solo el último grupo lee data/food_db/alimentos_limpios.csv
(se omite si el archivo no existe).
"""

import json
from pathlib import Path

import pytest

from backend.rag.evaluation import evaluar as modulo_evaluar
from backend.rag.evaluation.casos import CasoEvaluacion, cargar_casos
from backend.rag.evaluation.metricas import (
    ResultadoCaso,
    Veredicto,
    evaluar_respuesta,
    normalizar,
    percentil,
    resumir,
)

RAIZ = Path(__file__).resolve().parents[3]
FIXTURE = RAIZ / "tests" / "fixtures" / "eval_alimentos.jsonl"
CATALOGO = RAIZ / "data" / "food_db" / "alimentos_limpios.csv"


def hacer_caso(decision="aceptar", regex=r"^tomates?$", kcal=((15, 25),), abst=False, id="t-1", cat="generico"):
    return CasoEvaluacion(
        id=id,
        consulta="tomate",
        categoria=cat,
        origen="texto",
        decision_esperada=decision,
        acepta_regex=None if decision == "abstener" else regex,
        kcal_ref=kcal,
        abstencion_aceptable=abst,
    )


# ---------------------------------------------------------------------------
# normalizar
# ---------------------------------------------------------------------------

def test_normalizar_quita_tildes_mayusculas_y_signos():
    assert normalizar("  Brócoli   CRUDO! ") == "brocoli crudo"
    assert normalizar("Yogur 0% natural") == "yogur 0% natural"
    assert normalizar(None) == ""


# ---------------------------------------------------------------------------
# evaluar_respuesta
# ---------------------------------------------------------------------------

def test_respuesta_correcta():
    r = evaluar_respuesta(hacer_caso(), {"nombre": "Tomate", "kcal_100g": 25})
    assert r == Veredicto.CORRECTO


def test_otro_alimento_es_falso_positivo_de_identidad():
    r = evaluar_respuesta(hacer_caso(), {"nombre": "Aceite de tomate", "kcal_100g": 20})
    assert r == Veredicto.FALSO_POSITIVO_IDENTIDAD


def test_nombre_correcto_con_kcal_imposibles_es_falso_positivo_nutricional():
    caso = hacer_caso(regex=r"^calabacin(es)?$", kcal=((12, 25),))
    assert evaluar_respuesta(caso, {"nombre": "Calabacin", "kcal_100g": 220}) == Veredicto.FALSO_POSITIVO_NUTRICIONAL
    assert evaluar_respuesta(caso, {"nombre": "Calabacines", "kcal_100g": 16}) == Veredicto.CORRECTO


def test_sin_kcal_con_rango_de_referencia_no_se_puede_dar_por_valido():
    r = evaluar_respuesta(hacer_caso(), {"nombre": "Tomate", "kcal_100g": None})
    assert r == Veredicto.FALSO_POSITIVO_NUTRICIONAL


def test_sin_rango_de_referencia_no_se_comprueban_las_kcal():
    caso = hacer_caso(kcal=None)
    assert evaluar_respuesta(caso, {"nombre": "Tomate", "kcal_100g": 9999}) == Veredicto.CORRECTO


def test_varios_intervalos_de_kcal():
    caso = hacer_caso(regex=r"^patatas fritas", kcal=((280, 350), (500, 580)))
    assert evaluar_respuesta(caso, {"nombre": "Patatas fritas", "kcal_100g": 300}) == Veredicto.CORRECTO
    assert evaluar_respuesta(caso, {"nombre": "Patatas fritas", "kcal_100g": 540}) == Veredicto.CORRECTO
    assert evaluar_respuesta(caso, {"nombre": "Patatas fritas", "kcal_100g": 53}) == Veredicto.FALSO_POSITIVO_NUTRICIONAL


def test_abstenerse_cuando_habia_respuesta_es_falso_negativo():
    assert evaluar_respuesta(hacer_caso(), None) == Veredicto.FALSO_NEGATIVO


def test_abstencion_aceptable_si_el_caso_la_admite():
    assert evaluar_respuesta(hacer_caso(abst=True), None) == Veredicto.ABSTENCION_ACEPTABLE
    assert evaluar_respuesta(hacer_caso(decision="ambiguo"), None) == Veredicto.ABSTENCION_ACEPTABLE


def test_abstencion_correcta_cuando_no_hay_respuesta_fiable():
    assert evaluar_respuesta(hacer_caso(decision="abstener", kcal=None), None) == Veredicto.ABSTENCION_CORRECTA


def test_responder_cuando_debia_abstenerse_es_falso_positivo():
    caso = hacer_caso(decision="abstener", kcal=None)
    assert evaluar_respuesta(caso, {"nombre": "Pad Thai", "kcal_100g": 171}) == Veredicto.FALSO_POSITIVO_IDENTIDAD


def test_responder_con_dato_imposible_cuando_no_hay_dato_fiable_es_nutricional():
    caso = hacer_caso(decision="abstener", kcal=((540, 640),))
    r = evaluar_respuesta(caso, {"nombre": "Almendras", "kcal_100g": 681})
    assert r == Veredicto.FALSO_POSITIVO_NUTRICIONAL


# ---------------------------------------------------------------------------
# Validación de los casos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "cambios",
    [
        {"decision_esperada": "quizas"},
        {"origen": "telepatia"},
        {"acepta_regex": None},
        {"acepta_regex": "(sin cerrar"},
        {"kcal_ref": ((30.0, 10.0),)},
        {"id": ""},
    ],
)
def test_caso_invalido_se_rechaza(cambios):
    datos = dict(id="x", consulta="tomate", categoria="generico", origen="texto",
                 decision_esperada="aceptar", acepta_regex=r"^tomate$", kcal_ref=((10.0, 30.0),))
    datos.update(cambios)
    with pytest.raises(ValueError):
        CasoEvaluacion(**datos)


def test_caso_abstener_no_admite_regex():
    with pytest.raises(ValueError):
        CasoEvaluacion(id="x", consulta="a", categoria="c", origen="texto",
                       decision_esperada="abstener", acepta_regex=r"^a$")


def test_cargar_casos_detecta_ids_repetidos_e_indica_la_linea(tmp_path):
    linea = json.dumps({"id": "a", "consulta": "tomate", "categoria": "g", "origen": "texto",
                        "decision_esperada": "aceptar", "acepta_regex": "^tomate$"})
    ruta = tmp_path / "casos.jsonl"
    ruta.write_text(linea + "\n" + linea + "\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        cargar_casos(ruta)
    assert "línea 2" in str(exc.value)


def test_cargar_casos_rechaza_archivo_vacio(tmp_path):
    ruta = tmp_path / "vacio.jsonl"
    ruta.write_text("\n\n", encoding="utf-8")
    with pytest.raises(ValueError):
        cargar_casos(ruta)


# ---------------------------------------------------------------------------
# percentil y resumir
# ---------------------------------------------------------------------------

def test_percentil_por_rango_mas_cercano():
    assert percentil([], 50) is None
    assert percentil([0.1, 0.2, 0.3, 0.4], 50) == 0.2
    assert percentil([0.1, 0.2, 0.3, 0.4], 95) == 0.4


def _resultado(veredicto, nombre="X", decision="aceptar", categoria="generico", segundos=0.1):
    return ResultadoCaso(
        caso_id="c", consulta="q", categoria=categoria, origen="texto",
        decision_esperada=decision, veredicto=veredicto,
        nombre_devuelto=nombre, segundos=segundos,
    )


def test_resumir_calcula_las_razones():
    resultados = [
        _resultado(Veredicto.CORRECTO),
        _resultado(Veredicto.FALSO_POSITIVO_IDENTIDAD),
        _resultado(Veredicto.FALSO_POSITIVO_NUTRICIONAL),
        _resultado(Veredicto.CORRECTO),
        _resultado(Veredicto.FALSO_NEGATIVO, nombre=None),
        _resultado(Veredicto.ABSTENCION_CORRECTA, nombre=None, decision="abstener"),
        _resultado(Veredicto.ERROR, nombre=None),
    ]
    r = resumir(resultados)
    assert r["total"] == 7 and r["errores"] == 1
    assert r["respuestas"] == 4 and r["abstenciones"] == 2
    assert r["correctos"] == 2
    assert r["precision_de_respuestas"] == 0.5
    assert r["tasa_falsos_positivos"] == 0.5
    assert r["tasa_falsos_positivos_nutricionales"] == 0.25
    # 5 casos con respuesta esperada (el de 'abstener' no cuenta): 2 correctos
    assert r["recall_respondibles"] == 2 / 5
    assert r["abstencion_correcta"] == 1.0
    assert r["decisiones_acertadas"] == 3 / 6


def test_resumir_sin_respuestas_no_divide_por_cero():
    r = resumir([_resultado(Veredicto.ABSTENCION_CORRECTA, nombre=None, decision="abstener")])
    assert r["precision_de_respuestas"] is None
    assert r["tasa_falsos_positivos"] is None
    assert r["abstencion_correcta"] == 1.0


# ---------------------------------------------------------------------------
# ejecutar y main con un sistema falso (no usa Qdrant)
# ---------------------------------------------------------------------------

def test_ejecutar_mide_y_recoge_errores():
    casos = [hacer_caso(id="a"), hacer_caso(id="b")]
    llamadas = []

    def sistema(consulta):
        llamadas.append(consulta)
        if len(llamadas) == 3:  # 1 = calentamiento, 2 = caso a, 3 = caso b
            raise RuntimeError("fallo simulado")
        return {"nombre": "Tomate", "kcal_100g": 25.0, "similitud": 0.9}

    resultados, carga = modulo_evaluar.ejecutar(sistema, casos)
    assert [r.veredicto for r in resultados] == [Veredicto.CORRECTO, Veredicto.ERROR]
    assert "fallo simulado" in resultados[1].error
    assert "segundos_de_carga" in carga and len(llamadas) == 3


def test_main_escribe_csv_y_json(tmp_path, capsys):
    def sistema(consulta):
        return {"nombre": "Tomate", "kcal_100g": 25.0, "similitud": 0.9}

    codigo = modulo_evaluar.main(
        ["--casos", str(FIXTURE), "--sistema", "falso", "--limite", "6", "--salida", str(tmp_path)],
        sistemas={"falso": sistema},
    )
    assert codigo == 0
    assert len(list(tmp_path.glob("*_falso.csv"))) == 1
    assert len(list(tmp_path.glob("*_falso.json"))) == 1
    assert "SISTEMA: falso" in capsys.readouterr().out


def test_verificar_rag_activo_aborta_si_el_rag_esta_desactivado(monkeypatch):
    from backend.rag import food_search

    monkeypatch.setattr(food_search, "_inicializar", lambda: False)
    with pytest.raises(RuntimeError) as exc:
        modulo_evaluar.verificar_rag_activo()
    assert "desactivado" in str(exc.value)


def test_verificar_rag_activo_devuelve_el_numero_de_puntos(monkeypatch):
    from types import SimpleNamespace

    from backend.rag import food_search

    cliente = SimpleNamespace(get_collection=lambda nombre: SimpleNamespace(points_count=126674))
    monkeypatch.setattr(food_search, "_inicializar", lambda: True)
    monkeypatch.setattr(food_search, "_cliente", cliente)
    assert modulo_evaluar.verificar_rag_activo() == 126674


def test_main_con_el_rag_desactivado_termina_con_codigo_2(monkeypatch, capsys):
    def desactivado():
        raise RuntimeError("El RAG está desactivado")

    monkeypatch.setattr(modulo_evaluar, "verificar_rag_activo", desactivado)
    assert modulo_evaluar.main(["--casos", str(FIXTURE), "--limite", "2"]) == 2
    assert "desactivado" in capsys.readouterr().out


def test_main_sin_casos_devuelve_error(tmp_path):
    codigo = modulo_evaluar.main(
        ["--casos", str(FIXTURE), "--categoria", "no_existe", "--salida", str(tmp_path)],
        sistemas={"falso": lambda q: None},
    )
    assert codigo == 1


# ---------------------------------------------------------------------------
# El conjunto de casos oficial
# ---------------------------------------------------------------------------

def test_el_conjunto_oficial_es_valido_y_equilibrado():
    casos = cargar_casos(FIXTURE)
    assert len(casos) >= 60
    categorias = {c.categoria for c in casos}
    assert {"generico", "preparacion", "sinonimo", "producto", "ausente_comida", "no_comida"} <= categorias
    assert {c.origen for c in casos} == {"texto", "vision"}
    assert sum(c.decision_esperada == "abstener" for c in casos) >= 8


def test_el_conjunto_oficial_tiene_solucion_en_el_catalogo():
    """Cada caso 'aceptar/ambiguo' debe tener al menos una entrada del catálogo con
    nombre correcto Y calorías plausibles; si no, el caso sería injusto."""
    if not CATALOGO.exists():
        pytest.skip("No está data/food_db/alimentos_limpios.csv")

    import pandas as pd

    catalogo = pd.read_csv(CATALOGO, low_memory=False, usecols=["nombre", "energy-kcal_100g"])
    nombres = catalogo["nombre"].map(normalizar)
    kcal = catalogo["energy-kcal_100g"]

    sin_solucion = []
    for caso in cargar_casos(FIXTURE):
        if caso.decision_esperada == "abstener":
            continue
        coincide = nombres.str.match(caso.acepta_regex)
        validas = coincide & kcal.map(caso.kcal_plausible)
        if not validas.any():
            sin_solucion.append(caso.id)
    assert sin_solucion == [], f"Casos sin respuesta correcta posible: {sin_solucion}"
