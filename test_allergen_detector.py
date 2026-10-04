"""
test_allergen_detector.py
-------------------------
Pruebas unitarias para el detector de alérgenos automático.
"""
import os
from backend.utils.allergen_detector import detectar_alergenos_texto, detectar_alergenos_comida, detectar_alergenos_dia

def test_detectar_alergenos_texto():
    # Gluten y lácteos
    texto_1 = "Pan de trigo con queso cheddar fundido"
    resultado_1 = detectar_alergenos_texto(texto_1)
    assert "gluten" in resultado_1
    assert "lacteos" in resultado_1
    assert len(resultado_1) == 2

    # Cacahuetes y sésamo
    texto_2 = "Ensalada con aliño de tahini y cacahuetes picados"
    resultado_2 = detectar_alergenos_texto(texto_2)
    assert "sesamo" in resultado_2
    assert "cacahuetes" in resultado_2
    assert len(resultado_2) == 2

    # Ninguno
    texto_3 = "Manzana verde y pechuga de pollo hervida"
    resultado_3 = detectar_alergenos_texto(texto_3)
    assert len(resultado_3) == 0


def test_detectar_alergenos_comida():
    comida_test = {
        "nombre": "Tortilla de patatas con gambas",
        "ingredientes": [
            {"nombre": "huevo campero", "cantidad": "3 unidades"},
            {"nombre": "patata monalisa", "cantidad": "200g"},
            "gambas peladas 100g",
            "aceite de oliva"
        ]
    }
    resultado = detectar_alergenos_comida(comida_test)
    assert "huevos" in resultado
    assert "crustaceos" in resultado
    assert len(resultado) == 2


def test_detectar_alergenos_dia():
    menu_dia = {
        "dia": "Lunes",
        "comidas": {
            "desayuno": {
                "nombre": "Tostada de pan de espelta con aguacate",
                "ingredientes": ["pan de espelta 60g", "aguacate 50g"]
            },
            "comida": {
                "nombre": "Salmón a la plancha con brócoli al vapor",
                "ingredientes": ["salmón fresco 150g", "brócoli 150g"]
            },
            "cena": {
                "nombre": "Tortilla de claras con queso feta",
                "ingredientes": ["claras de huevo 150ml", "queso feta 30g"]
            }
        }
    }
    resultado = detectar_alergenos_dia(menu_dia)
    
    # Comprobamos alérgenos por comida
    assert "gluten" in resultado["comidas"]["desayuno"]["alergenos"]
    assert "pescado" in resultado["comidas"]["comida"]["alergenos"]
    assert "huevos" in resultado["comidas"]["cena"]["alergenos"]
    assert "lacteos" in resultado["comidas"]["cena"]["alergenos"]

    # Comprobamos el consolidado del día completo
    assert "gluten" in resultado["alergenos_dia"]
    assert "pescado" in resultado["alergenos_dia"]
    assert "huevos" in resultado["alergenos_dia"]
    assert "lacteos" in resultado["alergenos_dia"]
    assert len(resultado["alergenos_dia"]) == 4
