"""
allergen_detector.py
--------------------
Detector automático de los 14 alérgenos de declaración obligatoria en España
y la Unión Europea, basado en coincidencia de palabras clave en ingredientes.

Los 14 alérgenos son:
1. Gluten
2. Crustáceos
3. Huevos
4. Pescado
5. Cacahuetes
6. Soja
7. Lácteos (leche/derivados)
8. Frutos de cáscara
9. Apio
10. Mostaza
11. Sésamo
12. Sulfitos
13. Altramuces
14. Moluscos
"""

import re

# Diccionario de palabras clave en minúsculas asociadas a cada alérgeno
DICCIONARIO_ALERGENOS = {
    "gluten": [
        "trigo", "centeno", "cebada", "avena", "espelta", "kamut", "pan", "harina", "pasta", 
        "cuscús", "sémola", "tortilla de trigo", "galleta", "bizcocho", "cereal"
    ],
    "crustaceos": [
        "gamba", "langostino", "cangrejo", "bogavante", "nécora", "centollo", "langosta", "quisquilla"
    ],
    "huevos": [
        "huevo", "huevos", "clara", "claras", "yema", "yemas", "mayonesa"
    ],
    "pescado": [
        "pescado", "merluza", "salmón", "atún", "bacalao", "trucha", "sardina", "boquerón", 
        "dorada", "lubina", "gula", "anchoa", "bonito"
    ],
    "cacahuetes": [
        "cacahuete", "cacahuetes", "maní", "mantequilla de cacahuete"
    ],
    "soja": [
        "soja", "tofu", "tempeh", "edamame", "salsa de soja", "miso"
    ],
    "lacteos": [
        "leche", "queso", "yogur", "mantequilla", "nata", "quesito", "kéfir", "requesón",
        "suero de leche", "parmesano", "mozzarella", "cheddar", "feta"
    ],
    "frutos_cascara": [
        "almendra", "almendras", "nuez", "nueces", "avellana", "avellanas", "pistacho", 
        "pistachos", "anacardo", "anacardos", "piñón", "piñones", "castaña"
    ],
    "apio": [
        "apio"
    ],
    "mostaza": [
        "mostaza"
    ],
    "sesamo": [
        "sésamo", "ajonjolí", "tahini", "tahina"
    ],
    "sulfitos": [
        "sulfito", "sulfitos", "vino", "vinagre", "sidra"
    ],
    "altramuces": [
        "altramuz", "altramuces", "chocho", "chochos"
    ],
    "moluscos": [
        "mejillón", "mejillones", "almeja", "almejas", "pulpo", "calamar", "chipirón", 
        "sepia", "ostra", "ostras", "vieira", "vieiras", "caracol", "caracoles"
    ]
}


def detectar_alergenos_texto(texto: str) -> list[str]:
    """
    Analiza un texto en busca de ingredientes que contengan alérgenos.
    Devuelve una lista con las claves de los alérgenos detectados.
    """
    texto_limpio = texto.lower()
    alergenos_detectados = set()

    for alergeno, palabras_clave in DICCIONARIO_ALERGENOS.items():
        for palabra in palabras_clave:
            # Buscamos coincidencia como palabra completa o subpalabra lógica (ej: almendras coincide con almendra)
            patron = rf"\b{palabra}\w*\b"
            if re.search(patron, texto_limpio):
                alergenos_detectados.add(alergeno)
                break

    return sorted(list(alergenos_detectados))


def detectar_alergenos_comida(comida: dict) -> list[str]:
    """
    Analiza los ingredientes de una comida individual y devuelve la lista de alérgenos detectados.
    """
    ingredientes = comida.get("ingredientes", [])
    textos = []
    
    # Nombre del plato
    if comida.get("nombre"):
        textos.append(comida["nombre"])
        
    # Nombres de ingredientes
    for ing in ingredientes:
        if isinstance(ing, dict) and ing.get("nombre"):
            textos.append(ing["nombre"])
        elif isinstance(ing, str):
            textos.append(ing)

    texto_completo = " ".join(textos)
    return detectar_alergenos_texto(texto_completo)


def detectar_alergenos_dia(menu_dia: dict) -> dict:
    """
    Analiza todas las comidas de un día y añade:
    1. Una lista de alérgenos por comida.
    2. Una lista de alérgenos total consolidada para el día completo.
    
    Args:
        menu_dia: dict del día generado por el DietistAgent
        
    Returns:
        El mismo dict modificado con la sección de alérgenos.
    """
    menu_con_alergenos = menu_dia.copy()
    comidas = menu_con_alergenos.get("comidas", {})
    alergenos_dia_completo = set()

    for toma, comida in comidas.items():
        if isinstance(comida, dict):
            alergenos_comida = detectar_alergenos_comida(comida)
            comida["alergenos"] = alergenos_comida
            alergenos_dia_completo.update(alergenos_comida)

    menu_con_alergenos["alergenos_dia"] = sorted(list(alergenos_dia_completo))
    return menu_con_alergenos
