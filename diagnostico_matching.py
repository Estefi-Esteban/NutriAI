from backend.rag.food_search import _cargar_indice_alimentos, _normalizar_texto

indice = _cargar_indice_alimentos()
if not indice:
    print('No se ha podido cargar el índice de Qdrant.')
    raise SystemExit(1)

print(f'ALIMENTOS CARGADOS DESDE QDRANT: {len(indice)}')

consultas = {
    'GRANOLA': ['granola'],
    'CACAHUETE CON SIN AZUCAR': ['cacahuete'],
}

for titulo, terminos in consultas.items():
    print('\n' + '=' * 110)
    print(titulo)
    print('=' * 110)
    encontrados = []
    for item in indice:
        nombre = _normalizar_texto(item.get('nombre', ''))
        if not any(t in nombre for t in terminos):
            continue
        if titulo == 'CACAHUETE CON SIN AZUCAR' and not any(x in nombre for x in ('sin azucar', 'sin azucares', 'sin azuc')):
            continue
        encontrados.append(item)

    print(f'Candidatos: {len(encontrados)}')
    for item in encontrados[:60]:
        print(
            f"- {item.get('nombre')} | kcal={item.get('kcal_100g')} "
            f"P={item.get('proteinas_100g')} C={item.get('carbos_100g')} "
            f"G={item.get('grasas_100g')} | outlier={item.get('outlier_nutricional')} "
            f"| calidad={item.get('score_calidad')}"
        )
