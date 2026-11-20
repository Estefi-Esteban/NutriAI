"""
Casos de evaluación: una consulta y cuál es la respuesta correcta.

El conjunto de casos es una etiqueta humana (no código del buscador): vive en
tests/fixtures/eval_alimentos.jsonl y debe revisarse por una persona.

Cada línea del JSONL es un caso:

    id                   identificador único
    consulta             texto que se le pasa al buscador
    categoria            generico | preparacion | sinonimo | producto | plato |
                         ausente_comida | no_comida | sin_datos_fiables
    origen               texto | vision  (de dónde vendría la consulta)
    decision_esperada    aceptar   -> existe una respuesta correcta
                         ambiguo   -> varias válidas con valores muy dispersos
                         abstener  -> no hay respuesta fiable: lo correcto es no responder
    acepta_regex         expresión sobre el nombre NORMALIZADO (sin tildes, minúsculas)
                         que deben cumplir las respuestas correctas (obligatoria si
                         decision_esperada != abstener)
    kcal_ref             lista de intervalos [min, max] de kcal/100 g plausibles
    abstencion_aceptable True si no responder es una opción razonable (no es error grave)
    notas                comentario libre
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DECISIONES = ("aceptar", "ambiguo", "abstener")
ORIGENES = ("texto", "vision")


@dataclass(frozen=True)
class CasoEvaluacion:
    id: str
    consulta: str
    categoria: str
    origen: str
    decision_esperada: str
    acepta_regex: str | None = None
    kcal_ref: tuple[tuple[float, float], ...] | None = None
    abstencion_aceptable: bool = False
    notas: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.consulta:
            raise ValueError("id y consulta son obligatorios.")
        if self.decision_esperada not in DECISIONES:
            raise ValueError(
                f"{self.id}: decision_esperada debe ser una de {DECISIONES}, "
                f"no '{self.decision_esperada}'."
            )
        if self.origen not in ORIGENES:
            raise ValueError(f"{self.id}: origen debe ser uno de {ORIGENES}.")

        if self.decision_esperada == "abstener":
            if self.acepta_regex is not None:
                raise ValueError(f"{self.id}: un caso 'abstener' no lleva acepta_regex.")
        else:
            if not self.acepta_regex:
                raise ValueError(f"{self.id}: falta acepta_regex.")
            try:
                re.compile(self.acepta_regex)
            except re.error as exc:
                raise ValueError(f"{self.id}: acepta_regex no es válida: {exc}") from exc

        for intervalo in self.kcal_ref or ():
            minimo, maximo = intervalo
            if not 0 <= minimo <= maximo:
                raise ValueError(f"{self.id}: intervalo kcal_ref inválido {intervalo}.")

    def kcal_plausible(self, kcal: float | None) -> bool:
        """True si no hay rango de referencia o la kcal cae dentro de alguno."""
        if not self.kcal_ref:
            return True
        if kcal is None:
            return False
        return any(minimo <= kcal <= maximo for minimo, maximo in self.kcal_ref)


def cargar_casos(ruta: str | Path) -> list[CasoEvaluacion]:
    """Lee un JSONL de casos. Lanza ValueError indicando la línea defectuosa."""
    casos: list[CasoEvaluacion] = []
    ids: set[str] = set()

    for numero, linea in enumerate(Path(ruta).read_text(encoding="utf-8").splitlines(), 1):
        if not linea.strip():
            continue
        try:
            datos = json.loads(linea)
            kcal = datos.get("kcal_ref")
            datos["kcal_ref"] = (
                tuple((float(a), float(b)) for a, b in kcal) if kcal else None
            )
            caso = CasoEvaluacion(**datos)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"{ruta}, línea {numero}: {exc}") from exc

        if caso.id in ids:
            raise ValueError(f"{ruta}, línea {numero}: id repetido '{caso.id}'.")
        ids.add(caso.id)
        casos.append(caso)

    if not casos:
        raise ValueError(f"{ruta}: no contiene ningún caso.")
    return casos
