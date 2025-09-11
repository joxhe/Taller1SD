import threading
import time
import os
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

from descargador import Descargador
from extractor import ExtractorPDF
from almacen import AlmacenMongo
from keywords import generar_keywords

# Namespaces para arXiv Atom
ATOM_NS = "http://www.w3.org/2005/Atom"
OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"
NS = {"atom": ATOM_NS, "opensearch": OPENSEARCH_NS}


class ProcesadorArticulos:
    def __init__(self, config: dict, xml_path: str):
        self.config = config
        self.xml_path = xml_path
        self.concurrency = int(self.config.get("concurrency", 4))
        self.downloads_dir = self.config.get("downloads_dir", "downloads")
        self.images_dir = self.config.get("images_dir", "downloads/images")

        self.descargador = Descargador(self.downloads_dir)
        self.extractor = ExtractorPDF(self.images_dir)
        mongo_cfg = self.config.get("mongo", {})
        self.almacen = AlmacenMongo(
            uri=mongo_cfg.get("uri", "mongodb://localhost:27017"),
            db_name=mongo_cfg.get("db_name", "cecar_articulos"),
            collection_name=mongo_cfg.get("collection", "articulos")
        )

        # THREAD SAFE: progreso compartido con lock
        self.total_a_procesar = 0
        self._procesados = 0  # variable privada
        self.progress_lock = threading.Lock()  # lock específico para progreso
        self.stop_monitor = threading.Event()

        # Thread pool para conexiones de BD separadas
        self.almacenes_por_hilo = {}  # dict thread_id -> almacen instance
        self.almacenes_lock = threading.Lock()

    def _get_almacen_for_thread(self):
        """Obtiene una instancia de almacén específica para el hilo actual"""
        thread_id = threading.get_ident()
        
        with self.almacenes_lock:
            if thread_id not in self.almacenes_por_hilo:
                mongo_cfg = self.config.get("mongo", {})
                self.almacenes_por_hilo[thread_id] = AlmacenMongo(
                    uri=mongo_cfg.get("uri", "mongodb://localhost:27017"),
                    db_name=mongo_cfg.get("db_name", "cecar_articulos"),
                    collection_name=mongo_cfg.get("collection", "articulos")
                )
        
        return self.almacenes_por_hilo[thread_id]

    def increment_procesados(self):
        """Thread-safe increment del contador"""
        with self.progress_lock:
            self._procesados += 1

    def get_progreso(self):
        """Thread-safe getter del progreso"""
        with self.progress_lock:
            return {
                "procesados": self._procesados,
                "total": self.total_a_procesar
            }

    @property
    def procesados(self):
        """Propiedad thread-safe para compatibilidad"""
        return self.get_progreso()["procesados"]

    def _parse_xml_entries(self):
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        entries = []
        for e in root.findall("atom:entry", NS):
            title = e.findtext("atom:title", default="", namespaces=NS).strip()
            summary = e.findtext("atom:summary", default="", namespaces=NS).strip()
            published = e.findtext("atom:published", default="", namespaces=NS).strip()
            # authors
            authors = [a.findtext("atom:name", default="", namespaces=NS).strip()
                       for a in e.findall("atom:author", NS)]
            # categories
            categories = [c.attrib.get("term") for c in e.findall("atom:category", NS)
                          if c.attrib.get("term")]
            # id (ej: http://arxiv.org/abs/2301.01234v1) -> construir link pdf
            id_text = e.findtext("atom:id", default="", namespaces=NS).strip()
            arxiv_id = None
            pdf_url = None
            if id_text:
                arxiv_id = id_text.rsplit("/", 1)[-1]
                # construir URL pdf
                pdf_url = (id_text.replace("/abs/", "/pdf/") + ".pdf"
                           if "/abs/" in id_text
                           else f"http://arxiv.org/pdf/{arxiv_id}.pdf")

            entries.append({
                "title": title,
                "summary": summary,
                "published": published,
                "authors": authors,
                "categories": categories,
                "arxiv_id": arxiv_id,
                "pdf_url": pdf_url,
                "xml_source": os.path.abspath(self.xml_path)
            })
        return entries

    def _procesar_un_articulo(self, metadata: dict):
        """
        Función que ejecutan los hilos: descargar, extraer y guardar.
        CORREGIDO: manejo thread-safe del progreso y conexiones BD
        """
        thread_id = threading.get_ident()
        print(f"[HILO-{thread_id}] Iniciando procesamiento de {metadata.get('arxiv_id', 'unknown')}")
        
        try:
            # 1) Descargar PDF
            pdf_url = metadata.get("pdf_url")
            slug = (metadata.get("arxiv_id") or metadata.get("title", ""))\
                .replace("/", "_").replace(" ", "_")[:120]
            pdf_name = f"{slug}.pdf"
            pdf_path = None
            
            if pdf_url:
                try:
                    pdf_path = self.descargador.descargar_pdf(pdf_url, dest_name=pdf_name)
                    print(f"[HILO-{thread_id}] PDF descargado: {pdf_path}")
                except Exception as e:
                    print(f"[HILO-{thread_id}] [ERROR] No se pudo descargar PDF: {e}")
                    pdf_path = None

            # 2) Extraer texto e imágenes
            text = ""
            images = []
            if pdf_path:
                try:
                    res = self.extractor.extract(pdf_path, article_slug=slug or "sin_slug")
                    text = res.get("text", "")
                    images = res.get("images", [])
                    print(f"[HILO-{thread_id}] Texto e imágenes extraídos para {slug}")
                except Exception as e:
                    print(f"[HILO-{thread_id}] [ERROR] No se pudo extraer PDF: {e}")
                    text = ""
                    images = []

            # 3) Generar keywords con Ollama
            texto_base = " ".join(filter(None, [
                metadata.get("title", ""),
                metadata.get("summary", ""),
                text[:1500]
            ]))
            
            try:
                keywords = generar_keywords(texto_base, modelo="gemma3:1b")
                print(f"[HILO-{thread_id}] Keywords generadas para {slug}: {keywords}")
            except Exception as e:
                print(f"[HILO-{thread_id}] [ERROR] Generando keywords con Ollama: {e}")
                keywords = []

            # 4) Guardar en Mongo - USANDO CONEXIÓN ESPECÍFICA DEL HILO
            try:
                almacen_hilo = self._get_almacen_for_thread()
                almacen_hilo.guardar_articulo(metadata, text, images, keywords)
                print(f"[HILO-{thread_id}] Artículo guardado en Mongo: {slug}")
            except Exception as e:
                print(f"[HILO-{thread_id}] [ERROR] Guardando en Mongo: {e}")

            # THREAD SAFE: update progreso
            self.increment_procesados()
            return True
            
        except Exception as e:
            print(f"[HILO-{thread_id}] [ERROR] Fallo inesperado en procesar artículo: {e}")
            # Incrementar contador incluso en caso de error
            self.increment_procesados()
            return False

    def _monitor(self, start_ts):
        """Monitor thread-safe del progreso"""
        while not self.stop_monitor.is_set():
            progreso = self.get_progreso()
            p = progreso["procesados"]
            t = progreso["total"]
            
            elapsed = int(time.time() - start_ts)
            print(f"[Monitor] Procesados: {p}/{t} — Tiempo transcurrido: {elapsed}s")
            
            if p >= t:
                break
            
            self.stop_monitor.wait(timeout=1)

    def run(self):
        entries = self._parse_xml_entries()
        self.total_a_procesar = len(entries)
        
        if self.total_a_procesar == 0:
            print("No hay artículos para procesar en el XML.")
            return

        print(f"Iniciando procesamiento de {self.total_a_procesar} artículos con {self.concurrency} hilos.")

        start_ts = time.time()
        monitor_thread = threading.Thread(target=self._monitor, args=(start_ts,), daemon=True)
        monitor_thread.start()

        # Usar ThreadPoolExecutor para mejor control de concurrencia
        with ThreadPoolExecutor(max_workers=self.concurrency, thread_name_prefix="ArticleProcessor") as executor:
            # Enviar todas las tareas
            futures = [executor.submit(self._procesar_un_articulo, entry) for entry in entries]
            
            # Procesar resultados conforme se completan
            for fut in as_completed(futures):
                try:
                    resultado = fut.result()
                    if not resultado:
                        print("[WARNING] Un hilo falló en el procesamiento")
                except Exception as e:
                    print(f"[ERROR] Excepción en hilo: {e}")

        # Finalizar monitor
        self.stop_monitor.set()
        monitor_thread.join(timeout=2)
        
        total_time = int(time.time() - start_ts)
        final_progress = self.get_progreso()
        print(f"Procesamiento finalizado. Procesados: {final_progress['procesados']}/{final_progress['total']}. Tiempo total: {total_time}s")

        # Limpiar conexiones de hilos
        with self.almacenes_lock:
            for almacen in self.almacenes_por_hilo.values():
                try:
                    almacen.client.close()
                except:
                    pass
            self.almacenes_por_hilo.clear()