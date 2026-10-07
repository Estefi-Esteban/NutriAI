from backend.rag.food_search import corregir_ingrediente


ingredientes = [
    {
        "nombre": "plátano",
        "cantidad": 120,
        "unidad": "g",
    },
    {
        "nombre": "pechuga de pollo",
        "cantidad": 150,
        "unidad": "g",
    },
    {
        "nombre": "arroz integral",
        "cantidad": 80,
        "unidad": "g",
    },
    {
        "nombre": "huevo",
        "cantidad": 60,
        "unidad": "g",
    },
]


for ingrediente in ingredientes:

    resultado = corregir_ingrediente(ingrediente)

    print("\n" + "=" * 60)
    print("INGREDIENTE ORIGINAL:")
    print(ingrediente)

    print("\nRESULTADO:")
    print(resultado)