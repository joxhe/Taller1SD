# descargador.py
import os
import requests
from urllib.parse import urlparse

class Descargador:
    def __init__(self, downloads_dir="downloads"):
        self.downloads_dir = downloads_dir
        os.makedirs(self.downloads_dir, exist_ok=True)

    def _nombre_desde_url(self, url: str) -> str:
        # intenta extraer nombre del path; si no, crea uno seguro
        p = urlparse(url)
        base = os.path.basename(p.path)
        if not base:
            base = "documento.pdf"
        if not base.endswith(".pdf"):
            base = base + ".pdf"
        return base

    def descargar_pdf(self, pdf_url: str, dest_name: str | None = None) -> str:
        """
        Descarga el pdf_url y lo guarda en downloads_dir.
        devuelve la ruta del archivo guardado.
        """
        if dest_name:
            fname = dest_name
        else:
            fname = self._nombre_desde_url(pdf_url)

        dest_path = os.path.join(self.downloads_dir, fname)

        # descarga en streaming
        with requests.get(pdf_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return dest_path
