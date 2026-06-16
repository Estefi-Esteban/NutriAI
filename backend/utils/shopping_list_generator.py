"""
shopping_list_generator.py
--------------------------
Genera una lista de la compra semanal a partir del plan de menú JSON
producido por el Agente Dietista.

Lógica pura, sin IA:
  1. Recorre los 7 días → 5 comidas por día → N ingredientes por comida.
  2. Normaliza y agrupa ingredientes con el mismo nombre.
  3. Acumula cantidades (misma unidad) o las lista por separado (unidades distintas).
  4. Clasifica cada ingrediente en una categoría de supermercado.

Uso:
    from backend.utils.shopping_list_generator import generar_lista_compra
    lista = generar_lista_compra(plan.plan_semanal)
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict


# ---------------------------------------------------------------------------
# Diccionario de categorías
# ---------------------------------------------------------------------------
# Cada clave es la categoría de supermercado.
# Los valores son palabras clave: si el nombre del ingrediente contiene
# cualquiera de ellas (en minúsculas sin tildes), pertenece a esa categoría.
# El orden importa — se evalúa de arriba a abajo y se asigna la primera
# categoría que coincida.

CATEGORIAS: dict[str, list[str]] = {
    "🥩 Proteínas": [
        "pollo", "pechuga", "contramuslo", "muslo",
        "atun", "salmon", "merluza", "bacalao", "sardina",
        "ternera", "cerdo", "pavo", "jamon",
        "huevo", "clara",
        "tofu", "tempeh", "seitan",
        "gambas", "mejillones",
    ],
    "🥛 Lácteos": [
        "leche", "yogur", "queso", "requesson",
        "kefir", "nata", "mantequilla",
    ],
    "🌾 Cereales y Legumbres": [
        "avena", "arroz", "pasta", "macarron", "espagueti", "fideo",
        "pan", "harina", "quinoa", "cuscus", "granola",
        "lenteja", "garbanzo", "judía", "judia", "alubia",
        "maiz",
    ],
    "🥦 Frutas y Verduras": [
        "platano", "manzana", "naranja", "pera", "fresa",
        "kiwi", "uva", "melon", "sandia", "piña", "pina",
        "brocoli", "brecol", "espinaca", "kale", "lechuga",
        "tomate", "pepino", "zanahoria", "cebolla", "ajo", "puerro",
        "pimiento", "calabacin", "berenjena", "coliflor",
        "patata", "boniato", "calabaza",
        "aguacate", "limon", "lima",
        "fruta", "champiñon", "champinon", "seta",
    ],
    "🥜 Frutos Secos y Semillas": [
        "almendra", "nuez", "nueces", "anacardo", "pistach", "cacahuete", "cacahuate",
        "semilla", "chia", "sesamo", "lino",
        "tahini",
    ],
    "🫙 Aceites, Salsas y Condimentos": [
        "aceite", "vinagre", "sal", "pimienta", "oregano",
        "comino", "canela", "curcuma", "paprika", "pimenton",
        "salsa", "mostaza", "ketchup", "mayonesa",
        "caldo", "miso",
    ],
    "🍫 Extras y Dulces": [
        "cacao", "chocolate", "miel", "mermelada", "azucar",
        "sirope", "proteina",
    ],
}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

# Adjetivos que el modelo añade pero no cambian el ingrediente base.
# Se eliminan antes de comparar para mejorar la agrupación.
_ADJETIVOS_GENERICOS = [
    "fresco", "fresca", "frescos", "frescas",
    "entero", "entera", "integral",
    "cocido", "cocida",
    "troceado", "picado", "rallado",
    "natural",
]


def _normalizar_nombre(nombre: str) -> str:
    """
    Convierte a minúsculas, elimina tildes, quita el contenido entre paréntesis,
    elimina adjetivos genéricos y colapsa espacios.

    Ejemplos:
        "Pechuga de Pollo"              → "pechuga de pollo"
        "Avena"                         → "avena"
        "Huevos"                        → "huevo"   (plural simple eliminado)
        "brócoli fresco"                → "brocoli"
        "frutas (fresas, plátano, etc)" → "frutas"
    """
    # Minúsculas y strip
    texto = nombre.lower().strip()

    # Eliminar contenido entre paréntesis (ej: "nueces (almendras)" → "nueces")
    texto = re.sub(r"\(.*?\)", "", texto)

    # Eliminar tildes: descomponemos en NFD y descartamos combinadores
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")

    # Eliminar adjetivos genéricos para mejorar la fusión
    for adj in _ADJETIVOS_GENERICOS:
        texto = re.sub(rf"\b{adj}\b", "", texto)

    # Plural simple: si termina en 's' y tiene más de 4 chars, quitar la 's'
    # Heurística básica para: huevos→huevo, espinacas→espinaca
    texto = texto.strip()
    if len(texto) > 4 and texto.endswith("s") and not texto.endswith("ss"):
        texto = texto[:-1]

    # Colapsar espacios múltiples
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def _categorizar(nombre_ingrediente: str) -> str:
    """
    Devuelve la categoría de supermercado para un ingrediente.
    Compara el nombre normalizado contra las palabras clave del diccionario.
    Si no hay coincidencia, devuelve '🛒 Otros'.
    """
    nombre_norm = _normalizar_nombre(nombre_ingrediente)

    for categoria, palabras_clave in CATEGORIAS.items():
        for kw in palabras_clave:
            # Normalizar también la palabra clave por consistencia
            kw_norm = _normalizar_nombre(kw)
            if kw_norm in nombre_norm:
                return categoria

    return "🛒 Otros"


def _clave_ingrediente(nombre: str) -> str:
    """
    Genera una clave de agrupación para acumular el mismo ingrediente
    cuando aparece con nombres ligeramente distintos.

    Estrategia MVP: normalizar nombre completo.
    Si "pechuga de pollo" y "pollo pechuga" aparecen, quedarán separados —
    suficiente para un MVP. Refinable con fuzzy matching más adelante.
    """
    return _normalizar_nombre(nombre)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def generar_lista_compra(plan_semanal: dict) -> dict:
    """
    Genera una lista de la compra semanal agrupada por categoría.

    Parámetros:
        plan_semanal: Dict con la estructura del Agente Dietista:
            {
                "Lunes":   {"comidas": {"desayuno": {...}, ...}},
                "Martes":  {...},
                ...
            }

    Devuelve:
        Dict con categorías como claves y listas de ingredientes como valores:
        {
            "🥩 Proteínas": [
                {"nombre": "pechuga de pollo", "cantidad_total": 480, "unidad": "g"},
                ...
            ],
            "🌾 Cereales y Legumbres": [
                {"nombre": "avena", "cantidad_total": 280, "unidad": "g"},
                ...
            ],
            ...
        }

        Solo se incluyen categorías que tienen al menos un ingrediente.
    """
    # acumulador: {clave_ingrediente: {nombre_display, unidad, cantidad_total}}
    # Si un ingrediente aparece con dos unidades distintas (ej: "g" y "unidad"),
    # se crea una entrada separada por unidad para no mezclar magnitudes.
    acumulador: dict[str, dict] = {}

    for dia, contenido_dia in plan_semanal.items():
        comidas = contenido_dia.get("comidas", {})

        for toma, datos_comida in comidas.items():
            if not isinstance(datos_comida, dict):
                continue

            ingredientes = datos_comida.get("ingredientes", [])

            for ingrediente in ingredientes:
                if not isinstance(ingrediente, dict):
                    continue

                nombre_raw = ingrediente.get("nombre", "").strip()
                cantidad = ingrediente.get("cantidad", 0)
                unidad = (ingrediente.get("unidad") or "").strip().lower()

                if not nombre_raw:
                    continue

                # Clave compuesta: nombre normalizado + unidad
                # Así "avena g" y "avena unidad" no se fusionan
                clave = f"{_clave_ingrediente(nombre_raw)}|{unidad}"

                if clave in acumulador:
                    # Acumular cantidad si la unidad coincide
                    try:
                        acumulador[clave]["cantidad_total"] += float(cantidad)
                    except (TypeError, ValueError):
                        pass  # cantidad no numérica → ignorar
                else:
                    acumulador[clave] = {
                        "nombre": nombre_raw,             # nombre original (primer aparición)
                        "nombre_norm": _clave_ingrediente(nombre_raw),
                        "cantidad_total": float(cantidad) if cantidad else 0.0,
                        "unidad": unidad,
                        "categoria": _categorizar(nombre_raw),
                    }

    # Agrupar por categoría
    por_categoria: dict[str, list] = defaultdict(list)

    for entry in acumulador.values():
        categoria = entry["categoria"]
        por_categoria[categoria].append({
            "nombre": entry["nombre"],
            "cantidad_total": round(entry["cantidad_total"]),
            "unidad": entry["unidad"],
        })

    # Ordenar ingredientes dentro de cada categoría por nombre
    for categoria in por_categoria:
        por_categoria[categoria].sort(key=lambda x: x["nombre"].lower())

    # Ordenar categorías según el orden definido en CATEGORIAS (+ Otros al final)
    orden_categorias = list(CATEGORIAS.keys()) + ["🛒 Otros"]
    resultado: dict[str, list] = {}
    for cat in orden_categorias:
        if cat in por_categoria:
            resultado[cat] = por_categoria[cat]

    return resultado


# ---------------------------------------------------------------------------
# Ejecución directa: python -m backend.utils.shopping_list_generator
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import io
    import json

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("  TEST — Generador de Lista de la Compra")
    print("=" * 60)

    # Leer el plan activo de Marta desde Supabase
    from backend.database.connection import SessionLocal
    from backend.database.repositories.plan_repository import obtener_plan_activo

    USER_ID = 5  # Marta Test

    with SessionLocal() as db:
        plan = obtener_plan_activo(db, user_id=USER_ID)

    if plan is None:
        print("❌ No se encontró plan activo para user_id=5")
        sys.exit(1)

    print(f"\n✅ Plan cargado: {list(plan.plan_semanal.keys())}")

    lista = generar_lista_compra(plan.plan_semanal)

    print(f"\n🛒 Lista de la compra — semana de Marta\n")
    total_ingredientes = 0
    for categoria, ingredientes in lista.items():
        print(f"\n  {categoria}")
        print(f"  {'─' * 45}")
        for item in ingredientes:
            cantidad_str = f"{item['cantidad_total']} {item['unidad']}"
            print(f"    • {item['nombre']:35s} {cantidad_str:>12}")
            total_ingredientes += 1

    print(f"\n{'─' * 60}")
    print(f"  Total: {total_ingredientes} ingredientes en {len(lista)} categorías")
    print(f"{'─' * 60}\n")
