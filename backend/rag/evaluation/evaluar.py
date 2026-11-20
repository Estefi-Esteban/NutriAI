"""
Mide el buscador de alimentos actual con los casos de tests/fixtures/eval_alimentos.jsonl.

Necesita QDRANT_URL / QDRANT_API_KEY en el .env (solo LEE de Qdrant; no escribe nada).

    python -m backend.rag.evaluation.evaluar                       # todos los sistemas
    python -m backend.rag.evaluation.evaluar --sistema vision
    python -m backend.rag.evaluation.evaluar --categoria generico --limite 10

Guarda un CSV (un renglón por consulta) y un JSON (resumen) en logs/eval/.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.rag.evaluation.casos import CasoEvaluacion, cargar_casos
from backend.rag.evaluation.metricas import (
    ACIERTOS,
    ResultadoCaso,
    Veredicto,
    evaluar_respuesta,
    resumir,
)

Sistema = Callable[[str], "Mapping[str, Any] | None"]

CASOS_POR_DEFECTO = Path("tests/fixtures/eval_alimentos.jsonl")
SALIDA_POR_DEFECTO = Path("logs/eval")
CONSULTA_CALENTAMIENTO = "tomate"


def sistemas_actuales() -> dict[str, Sistema]:
    """Los dos puntos de entrada de producción que usan los agentes."""
    from backend.rag import food_search

    return {
        "mejor_match": food_search.buscar_mejor_match,
        "vision": food_search.buscar_mejor_match_vision,
    }


def verificar_rag_activo() -> int | None:
    """
    Comprueba que Qdrant responde y que existe la colección de alimentos.
    Devuelve el número de puntos de la colección.

    Con el RAG desactivado todas las consultas devolverían "sin resultado" y la
    medición no tendría ningún sentido, así que se aborta en lugar de continuar.
    """
    from backend.rag import food_search

    if not food_search._inicializar():
        raise RuntimeError(
            "El RAG está desactivado: revisa QDRANT_URL y QDRANT_API_KEY en el .env "
            f"y que exista la colección '{food_search.COLECCION}'. Con el RAG "
            "desactivado todas las consultas devolverían 'sin resultado' y la "
            "medición no tendría sentido."
        )
    return food_search._cliente.get_collection(food_search.COLECCION).points_count


def memoria_rss_mb() -> float | None:
    """Memoria residente del proceso en MB (requiere psutil; None si no está)."""
    try:
        import os

        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - es una medida opcional
        return None


def ejecutar(
    sistema: Sistema,
    casos: Sequence[CasoEvaluacion],
) -> tuple[list[ResultadoCaso], dict[str, float | None]]:
    """
    Ejecuta cada caso y mide el tiempo. Hace antes una consulta de calentamiento:
    su duración es el coste de carga (modelo de embeddings, índice...) y se
    informa aparte para que no distorsione la latencia por consulta.
    """
    inicio = time.perf_counter()
    try:
        sistema(CONSULTA_CALENTAMIENTO)
    except Exception:  # noqa: BLE001 - los errores reales se registran por caso
        pass
    carga = {
        "segundos_de_carga": time.perf_counter() - inicio,
        "memoria_mb": memoria_rss_mb(),
    }

    resultados: list[ResultadoCaso] = []
    for caso in casos:
        base = {
            "caso_id": caso.id,
            "consulta": caso.consulta,
            "categoria": caso.categoria,
            "origen": caso.origen,
            "decision_esperada": caso.decision_esperada,
        }
        inicio = time.perf_counter()
        try:
            respuesta = sistema(caso.consulta)
        except Exception as exc:  # noqa: BLE001
            resultados.append(
                ResultadoCaso(
                    **base,
                    veredicto=Veredicto.ERROR,
                    segundos=time.perf_counter() - inicio,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        segundos = time.perf_counter() - inicio

        resultados.append(
            ResultadoCaso(
                **base,
                veredicto=evaluar_respuesta(caso, respuesta),
                nombre_devuelto=(respuesta or {}).get("nombre") if respuesta else None,
                kcal_devuelta=(respuesta or {}).get("kcal_100g") if respuesta else None,
                similitud=(respuesta or {}).get("similitud") if respuesta else None,
                segundos=segundos,
            )
        )
    return resultados, carga


def _pct(valor: float | None) -> str:
    return "  n/d" if valor is None else f"{100 * valor:5.1f}%"


def imprimir_informe(
    nombre: str,
    resumen: Mapping[str, Any],
    resultados: Sequence[ResultadoCaso],
    carga: Mapping[str, float | None],
) -> None:
    print("\n" + "=" * 78)
    print(f"SISTEMA: {nombre}")
    print("=" * 78)
    print(
        f"casos {resumen['total']} | respuestas {resumen['respuestas']} | "
        f"abstenciones {resumen['abstenciones']} | errores {resumen['errores']}"
    )
    print(f"  correctos .......................... {resumen['correctos']}")
    print(f"  falsos positivos de identidad ..... {resumen['falsos_positivos_identidad']}")
    print(f"  falsos positivos nutricionales .... {resumen['falsos_positivos_nutricionales']}")
    print(f"  falsos negativos (se abstuvo mal) . {resumen['falsos_negativos']}")
    print(f"  abstenciones correctas ............ {resumen['abstenciones_correctas']}")
    print(f"  abstenciones aceptables ........... {resumen['abstenciones_aceptables']}")
    print()
    print(f"  precisión de las respuestas ........ {_pct(resumen['precision_de_respuestas'])}")
    print(f"  tasa de falsos positivos ........... {_pct(resumen['tasa_falsos_positivos'])}")
    print(f"  (de ellos, nutricionales) .......... {_pct(resumen['tasa_falsos_positivos_nutricionales'])}")
    print(f"  recall en casos con respuesta ...... {_pct(resumen['recall_respondibles'])}")
    print(f"  abstención correcta (casos vacíos) . {_pct(resumen['abstencion_correcta'])}")
    print(f"  decisiones acertadas (global) ...... {_pct(resumen['decisiones_acertadas'])}")

    p50, p95 = resumen["segundos_p50"], resumen["segundos_p95"]
    if p50 is not None:
        print(f"\n  tiempo por consulta: p50 {p50:.3f}s | p95 {p95:.3f}s")
    memoria = carga.get("memoria_mb")
    print(
        f"  carga inicial: {carga['segundos_de_carga']:.1f}s"
        + (f" | memoria del proceso: {memoria:.0f} MB" if memoria else " | memoria: instala psutil para medirla")
    )

    print("\n  por categoría:  total  ok  falsos+  falsos-  abst.ok")
    for categoria, f in resumen["por_categoria"].items():
        print(
            f"    {categoria:20s}{f['total']:5d}{f['correctos']:5d}"
            f"{f['falsos_positivos']:8d}{f['falsos_negativos']:8d}{f['abstenciones_ok']:8d}"
        )

    fallos = [r for r in resultados if r.veredicto not in ACIERTOS]
    if fallos:
        print(f"\n  FALLOS ({len(fallos)}):")
        for r in fallos:
            if r.veredicto == Veredicto.ERROR:
                detalle = r.error
            elif r.nombre_devuelto is None:
                detalle = "(se abstuvo)"
            else:
                detalle = f"-> {r.nombre_devuelto} ({r.kcal_devuelta} kcal)"
            print(f"    [{r.veredicto.value}] {r.caso_id}  \"{r.consulta}\"  {detalle}")


def guardar(
    carpeta: Path,
    nombre: str,
    resumen: Mapping[str, Any],
    resultados: Sequence[ResultadoCaso],
    carga: Mapping[str, float | None],
    casos: Sequence[CasoEvaluacion],
) -> tuple[Path, Path]:
    import csv

    carpeta.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_csv = carpeta / f"{marca}_{nombre}.csv"
    ruta_json = carpeta / f"{marca}_{nombre}.json"
    notas = {c.id: c.notas for c in casos}

    columnas = [
        "caso_id", "categoria", "origen", "consulta", "decision_esperada", "veredicto",
        "nombre_devuelto", "kcal_devuelta", "similitud", "segundos", "error", "notas",
    ]
    with ruta_csv.open("w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        for r in resultados:
            escritor.writerow({
                "caso_id": r.caso_id, "categoria": r.categoria, "origen": r.origen,
                "consulta": r.consulta, "decision_esperada": r.decision_esperada,
                "veredicto": r.veredicto.value, "nombre_devuelto": r.nombre_devuelto or "",
                "kcal_devuelta": "" if r.kcal_devuelta is None else r.kcal_devuelta,
                "similitud": "" if r.similitud is None else r.similitud,
                "segundos": round(r.segundos, 4), "error": r.error or "",
                "notas": notas.get(r.caso_id, ""),
            })

    ruta_json.write_text(
        json.dumps({"sistema": nombre, "carga": dict(carga), "resumen": dict(resumen)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ruta_csv, ruta_json


def main(
    argv: Sequence[str] | None = None,
    sistemas: Mapping[str, Sistema] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--casos", type=Path, default=CASOS_POR_DEFECTO)
    parser.add_argument("--sistema", default="todos", help="mejor_match | vision | todos")
    parser.add_argument("--categoria", help="Evalúa solo esta categoría")
    parser.add_argument("--limite", type=int, help="Evalúa solo los N primeros casos")
    parser.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO)
    args = parser.parse_args(argv)

    casos = cargar_casos(args.casos)
    if args.categoria:
        casos = [c for c in casos if c.categoria == args.categoria]
    if args.limite:
        casos = casos[: args.limite]
    if not casos:
        print("No hay casos que evaluar con esos filtros.")
        return 1

    if sistemas is None:
        try:
            puntos = verificar_rag_activo()
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 2
        print(f"Qdrant conectado: colección con {puntos:,} puntos".replace(",", "."))

    disponibles = dict(sistemas) if sistemas is not None else sistemas_actuales()
    elegidos = disponibles if args.sistema == "todos" else {args.sistema: disponibles[args.sistema]}

    print(f"Evaluando {len(casos)} casos con: {', '.join(elegidos)}")
    for nombre, funcion in elegidos.items():
        resultados, carga = ejecutar(funcion, casos)
        resumen = resumir(resultados)
        imprimir_informe(nombre, resumen, resultados, carga)
        ruta_csv, ruta_json = guardar(args.salida, nombre, resumen, resultados, carga, casos)
        print(f"\n  guardado: {ruta_csv}\n            {ruta_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
