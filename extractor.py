# extractor.py
import os
import fitz  # pymupdf
import base64

class ExtractorPDF:
    def __init__(self, images_dir="downloads/images"):
        self.images_dir = images_dir
        os.makedirs(self.images_dir, exist_ok=True)

    def extract(self, pdf_path: str, article_slug: str):
        """
        Extrae texto completo y guarda imágenes en una carpeta por artículo.
        Devuelve: {"text": <texto largo>, "images": [<ruta1>, <ruta2>, ...]}
        """
        doc = fitz.open(pdf_path)
        full_text_parts = []
        saved_images = []
        art_img_dir = os.path.join(self.images_dir, article_slug)
        os.makedirs(art_img_dir, exist_ok=True)

        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            text = page.get_text("text")
            if text:
                full_text_parts.append(text)

            # extraer imágenes de la página
            images = page.get_images(full=True)
            for img_index, img in enumerate(images):
                xref = img[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n < 5:  # RGB or GRAY
                        img_ext = "png"
                        img_name = f"p{page_index+1}_img{img_index+1}.{img_ext}"
                        out_path = os.path.join(art_img_dir, img_name)
                        pix.save(out_path)
                        saved_images.append(out_path)
                        pix = None
                    else:  # CMYK: convert to RGB first
                        pix0 = fitz.Pixmap(fitz.csRGB, pix)
                        img_ext = "png"
                        img_name = f"p{page_index+1}_img{img_index+1}.{img_ext}"
                        out_path = os.path.join(art_img_dir, img_name)
                        pix0.save(out_path)
                        saved_images.append(out_path)
                        pix0 = None
                        pix = None
                except Exception:
                    # si falla con esta imagen, la ignoramos
                    continue

        doc.close()
        full_text = "\n".join(full_text_parts)
        return {"text": full_text, "images": saved_images}
