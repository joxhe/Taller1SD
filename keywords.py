import subprocess
import json

def generar_keywords(texto: str, modelo: str = "mistral") -> list:
    """
    Genera keywords a partir de un texto usando Ollama.
    - texto: título + resumen (y texto completo si quieres).
    - modelo: modelo local de Ollama (ej: 'mistral', 'llama2', etc.)
    """
    prompt = f"Extrae entre 5 y 10 palabras clave representativas del siguiente texto en español:\n\n{texto}\n\nDevuélvelas en formato JSON como una lista de strings."

    # Ejecuta ollama desde Python con codificación UTF-8
    try:
        result = subprocess.run(
            ["ollama", "run", modelo, prompt],
            capture_output=True,
            text=True,
            encoding='utf-8',  # Especificar UTF-8 explícitamente
            errors='replace'   # Reemplazar caracteres problemáticos
        )
    except Exception as e:
        print(f"Error ejecutando Ollama: {e}")
        return []

    if result.returncode != 0:
        print(f"Ollama error (stderr): {result.stderr}")
        return []

    # Intenta parsear la salida como JSON
    try:
        output_clean = result.stdout.strip()
        keywords = json.loads(output_clean)
        if isinstance(keywords, list):
            return keywords
    except json.JSONDecodeError:
        print(f"No se pudo parsear como JSON: {result.stdout[:100]}...")

    # Si no vino en JSON válido, devolver la salida como lista de palabras
    # Limpiar caracteres problemáticos
    output_clean = result.stdout.replace('\x8f', '').replace('\x90', '').strip()
    keywords = [kw.strip() for kw in output_clean.split(",") if kw.strip()]
    
    # Filtrar keywords vacías o muy cortas
    keywords = [kw for kw in keywords if len(kw) > 2]
    
    return keywords[:5]  # Máximo 5 keywords