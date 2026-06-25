import os
from backend.utils.pdf_generator import generar_pdf_reporte

def test():
    print("=" * 60)
    print("  TEST — Generación de Reporte PDF NutriAI")
    print("=" * 60)

    # 1. Mock de datos
    perfil_marta = {
        "nombre": "Marta Gómez",
        "edad": 28,
        "sexo": "mujer",
        "peso_kg": 68.5,
        "altura_cm": 165.0,
        "porcentaje_grasa": 24.2,
        "objetivo_principal": "perder_grasa",
        "objetivo_secundario": "mejorar energía y salud cardiovascular",
        "velocidad_objetivo": "moderado",
        "nivel_actividad": "moderado",
        "dias_entrenamiento": 4,
        "tipo_entrenamiento": "fuerza",
        "dieta_tipo": "omnivora",
        "alergias": ["Mariscos"],
        "intolerancias": ["Lactosa"],
        "presupuesto_semanal": 80.0,
        "tiempo_cocina_min": 30,
        "personas_en_casa": 2,
        "medicacion": "Ninguna",
        "patologias": ["Colesterol Alto", "Fatiga Leve"]
    }

    plan_marta = {
        "calorias_objetivo": 1650.0,
        "proteinas_g": 130.0,
        "carbos_g": 150.0,
        "grasas_g": 55.0,
        "plan_semanal": {}
    }

    protocolo_marta = {
        "alimentos_prohibidos": ["Mantequilla", "Embutidos grasos", "Mariscos"],
        "alimentos_prioritarios": ["Avena", "Nueces", "Lino", "Pollo magro"],
        "notas_dietista": "Priorizar fuentes de fibra soluble y grasas saludables (insaturadas). Evitar totalmente los mariscos por su alergia."
    }

    suplementos_marta = {
        "suplementos_necesarios": [
            {"nombre": "Omega 3", "dosis": "1000mg diaria"},
            {"nombre": "Vitamina D3", "dosis": "2000 UI diaria"}
        ],
        "suplementos_opcionales": [
            {"nombre": "Proteína de suero (Whey)", "dosis": "30g post-entreno"}
        ],
        "suplementos_innecesarios": [
            {"nombre": "Quemadores de grasa", "dosis": "Evitar por falta de evidencia"}
        ]
    }

    evidencias_marta = [
        {
            "titulo": "Effect of dietary fat and fiber intake on LDL cholesterol reduction",
            "año": 2024,
            "fuente": "PubMed",
            "tipo": "estudio_cientifico",
            "doi": "10.1016/j.clnu.2024.01.002",
            "autores": "Smith J., Johnson R., et al.",
            "texto": "Un ensayo aleatorizado controlado demostró que el aumento de 10g diarios de fibra soluble de avena reduce significativamente el colesterol LDL en pacientes con dislipemia leve, con un impacto adicional si se complementa con ácidos grasos omega-3."
        },
        {
            "titulo": "Protein requirements during caloric restriction in active adults",
            "año": 2023,
            "fuente": "PubMed",
            "tipo": "estudio_cientifico",
            "doi": "10.1123/ijsnem.2023-0112",
            "autores": "Phillips S. M., et al.",
            "texto": "Esta revisión de guías clínicas establece que para atletas y adultos activos en déficit calórico, un aporte de proteína de 1.8 a 2.2 g/kg es necesario para atenuar la pérdida de masa muscular y mejorar la recomposición corporal."
        }
    ]

    # 2. Generar PDF
    print("[*] Generando PDF en memoria...")
    pdf_bytes = generar_pdf_reporte(
        perfil=perfil_marta,
        plan=plan_marta,
        protocolo=protocolo_marta,
        suplementos=suplementos_marta,
        evidencias=evidencias_marta
    )

    # 3. Guardar archivo
    output_path = "reporte_prueba_marta.pdf"
    print(f"[*] Guardando archivo PDF en: {output_path}...")
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)
        
    print(f"Success! The PDF was successfully generated at: {os.path.abspath(output_path)}")
    print(f"    File size: {len(pdf_bytes)} bytes")

if __name__ == "__main__":
    test()
