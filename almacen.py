# almacen.py
from pymongo import MongoClient
import os
from datetime import datetime

class AlmacenMongo:
    def __init__(self, uri="mongodb://localhost:27017", db_name="cecar_articulos", collection_name="articulos"):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.col = self.db[collection_name]
        # crear índices útiles
        self.col.create_index("arxiv_id", unique=True, sparse=True)

    def guardar_articulo(self, metadata: dict, text: str, image_paths: list, keywords: list):
        """
        metadata debe contener: title, authors, published, categories, summary, arxiv_id, pdf_url, xml_source (ruta del xml)
        """
        doc = {
            "title": metadata.get("title"),
            "authors": metadata.get("authors", []),
            "published": metadata.get("published"),
            "categories": metadata.get("categories", []),
            "summary": metadata.get("summary"),
            "arxiv_id": metadata.get("arxiv_id"),
            "pdf_url": metadata.get("pdf_url"),
            "xml_source": metadata.get("xml_source"),
            "full_text": text,
            "images": image_paths,
            "keywords": keywords,
            "created_at": datetime.utcnow()
        }
        # upsert por arxiv_id si existe, si no insertar
        query = {}
        if doc.get("arxiv_id"):
            query = {"arxiv_id": doc["arxiv_id"]}
            self.col.update_one(query, {"$set": doc}, upsert=True)
        else:
            self.col.insert_one(doc)
        return True
