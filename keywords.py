import subprocess
import json

def generar_keywords(texto: str, modelo: str = "mistral") -> list:
    """
    Genera keywords a partir de un texto usando Ollama.
    - texto: título + resumen (y texto completo si quieres).
    - modelo: modelo local de Ollama (ej: 'mistral', 'llama2', etc.)
    """
    prompt = f"Extrae entre 5 y 10 palabras clave representativas del siguiente texto en español:\n\n{texto}\n\nDevuélvelas en formato JSON como una lista de strings."

    # Ejecuta ollama desde Python
    result = subprocess.run(
        ["ollama", "run", modelo, prompt],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Ollama error: {result.stderr}")

    # Intenta parsear la salida como JSON
    try:
        keywords = json.loads(result.stdout.strip())
        if isinstance(keywords, list):
            return keywords
    except:
        pass

    # Si no vino en JSON válido, devolver la salida como lista de palabras
    return [kw.strip() for kw in result.stdout.split(",") if kw.strip()]
