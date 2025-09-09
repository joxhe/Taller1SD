import re
import unicodedata

def slugify(texto: str) -> str:
    """Convierte un texto en una versión segura para nombres de archivo."""
    if not texto:
        return "query"
    txt = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    txt = re.sub(r"[^a-zA-Z0-9\-_\s]+", "", txt)
    txt = re.sub(r"\s+", "-", txt).strip("-").lower()
    return txt or "query"
