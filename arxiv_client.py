# arxiv_client.py
import os
import time
import requests
from urllib.parse import quote_plus
from sanitizar import slugify

class ArxivClient:
    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self, downloads_dir: str = "downloads"):
        self.downloads_dir = downloads_dir
        os.makedirs(self.downloads_dir, exist_ok=True)

    def _build_url(self, query: str, start: int = 0, max_results: int = 50) -> str:
        q = quote_plus(query)  # maneja espacios y caracteres seguros
        return f"{self.BASE_URL}?search_query=all:{q}&start={start}&max_results={max_results}"

    def fetch_and_save(self, query: str, start: int = 0, max_results: int = 50) -> str:
        """Descarga el XML de arXiv y lo guarda en downloads/. Devuelve la ruta del archivo."""
        url = self._build_url(query, start, max_results)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        stamp = int(time.time())
        fname = f"arxiv_{slugify(query)}_{start}_{max_results}_{stamp}.xml"
        fpath = os.path.join(self.downloads_dir, fname)

        print(f"DEBUG - Guardando XML en: {fpath}")  # DEBUG
        print(f"DEBUG - Ruta absoluta: {os.path.abspath(fpath)}")  # DEBUG

        with open(fpath, "wb") as f:
            f.write(resp.content)

        print(f"DEBUG - Archivo guardado exitosamente: {os.path.exists(fpath)}")  # DEBUG
        
        return os.path.abspath(fpath)  # Devolver ruta absoluta