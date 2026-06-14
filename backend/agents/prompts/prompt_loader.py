from pathlib import Path

def load_prompt(nombre_archivo: str) -> str:
    """
    Carga un prompt desde la carpeta prompts/.
    Uso: load_prompt("profile_prompt.md")
    """
    ruta = Path(__file__).parent / nombre_archivo

    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el prompt: {nombre_archivo}")

    return ruta.read_text(encoding="utf-8")