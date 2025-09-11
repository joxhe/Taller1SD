# keywords.py
import subprocess
import json

def generar_keywords(texto: str, modelo: str = "gemma3:1b") -> list:
    """
    Genera keywords a partir de un texto usando Ollama.
    - texto: título + resumen (+ fragmento del texto completo).
    - modelo: modelo local de Ollama (ej: 'gemma3:1b', 'mistral', etc.)
    """
    prompt = f"""
    Analiza el siguiente texto y devuelve EXACTAMENTE una lista JSON de 5 palabras clave en español.
    - SOLO devuelve una lista JSON de strings, nada de explicaciones, sin clave 'keywords'.
    - Ejemplo de salida válida: ["inteligencia artificial", "aprendizaje automático", "control óptimo", "ataques adversariales", "optimización"]

    Texto:
    {texto}
    """

    try:
        result = subprocess.run(
            ["ollama", "run", modelo, prompt],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
    except Exception as e:
        print(f"[ERROR] No se pudo ejecutar Ollama: {e}")
        return ["IA", "machine learning", "control", "sistemas", "optimización"]

    if result.returncode != 0:
        print(f"[OLLAMA ERROR] {result.stderr}")
        return ["IA", "machine learning", "control", "sistemas", "optimización"]

    output_clean = result.stdout.strip()
    print(f"[OLLAMA RAW OUTPUT]\n{output_clean}\n")

    # Intentar parsear como JSON
    try:
        keywords = json.loads(output_clean)
        if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
            return keywords[:5]
    except json.JSONDecodeError:
        print("[WARN] Ollama no devolvió JSON válido")

    # Si no es JSON válido, intentar rescatar palabras separadas por coma o salto de línea
    candidates = [kw.strip() for kw in output_clean.replace("\n", ",").split(",") if kw.strip()]
    candidates = [kw for kw in candidates if len(kw) > 2]

    # fallback por si no se obtiene nada
    if not candidates:
        candidates = ["IA", "machine learning", "control", "sistemas", "optimización"]

    return candidates[:5]
