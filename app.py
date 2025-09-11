# app.py CORREGIDO CON SERVICIO DE IMÁGENES MEJORADO
from flask import Flask, request, render_template, jsonify, send_from_directory
import os
import json
import threading
import time

from arxiv_client import ArxivClient
from arxiv_parser import parse_counts
from procesador import ProcesadorArticulos
from almacen import AlmacenMongo   # conexión a Mongo

app = Flask(__name__)

# ============================
# CONFIG
# ============================
def load_config(path="config.json"):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

CFG = load_config()
DOWNLOADS_DIR = CFG.get("downloads_dir", "downloads")
DEFAULT_MAX = int(CFG.get("rf1_max_results", 50))

client = ArxivClient(DOWNLOADS_DIR)

# Mongo
mongo_cfg = CFG.get("mongo", {})
almacen = AlmacenMongo(
    uri=mongo_cfg.get("uri", "mongodb://localhost:27017"),
    db_name=mongo_cfg.get("db_name", "cecar_articulos"),
    collection_name=mongo_cfg.get("collection", "articulos")
)

# ============================
# VARIABLES GLOBALES RF2 - CON THREAD SAFETY
# ============================
procesador_obj = None
procesador_thread = None
start_time = None
# LOCK PARA VARIABLES GLOBALES
global_lock = threading.Lock()

# ============================
# RUTAS RF1
# ============================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/buscar")
def buscar():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("index.html", error="Ingresa un criterio de búsqueda.")

    start = int(request.args.get("start", 0))
    max_results = int(request.args.get("max", DEFAULT_MAX))

    # se descarga el XML y se devuelve la ruta absoluta
    xml_path = client.fetch_and_save(q, start=start, max_results=max_results)
    counts = parse_counts(xml_path)

    return render_template(
        "resultados.html",
        query=q,
        xml_path=os.path.abspath(xml_path).replace("\\", "/"),
        total=counts["total_results"],
        returned=counts["returned_results"],
        start=start,
        max_results=max_results
    )

# ============================
# RUTAS RF2 - CON THREAD SAFETY
# ============================
@app.route("/procesar")
def procesar():
    global procesador_obj, procesador_thread, start_time

    xml_path = request.args.get("xml_path")
    if not xml_path or not os.path.exists(xml_path):
        return jsonify({"error": f"XML no encontrado en {xml_path}"}), 400

    # THREAD SAFE: verificar si ya hay procesamiento
    with global_lock:
        if procesador_thread and procesador_thread.is_alive():
            return jsonify({"status": "Ya hay un procesamiento en curso"}), 400

        procesador_obj = ProcesadorArticulos(CFG, xml_path)
        start_time = time.time()

        def run_proc():
            procesador_obj.run()

        procesador_thread = threading.Thread(target=run_proc, daemon=True)
        procesador_thread.start()

    return jsonify({"status": "Procesamiento iniciado", "xml": xml_path})

@app.route("/progreso")
def progreso():
    global procesador_obj, start_time

    # THREAD SAFE: leer variables globales
    with global_lock:
        if not procesador_obj:
            return jsonify({"error": "No hay procesamiento en curso"}), 400

        elapsed = int(time.time() - start_time) if start_time else 0
        # Usar el método thread-safe del procesador
        progreso_data = procesador_obj.get_progreso()

    is_done = progreso_data["procesados"] >= progreso_data["total"]
    
    return jsonify({
        "procesados": progreso_data["procesados"],
        "total": progreso_data["total"],
        "elapsed": elapsed,
        "done": is_done,
        "articulos_url": "/articulos" if is_done else None  # URL para ver artículos
    })

# ============================
# RUTAS RF3 - FUNCIÓN CORREGIDA DE CONVERSIÓN DE IMÁGENES
# ============================
def convertir_rutas_imagenes(articulos):
    """Convierte rutas absolutas de imágenes a URLs web para servir desde Flask"""
    images_dir = os.path.abspath(CFG.get("images_dir", "downloads/images"))
    
    # Si articulos es un solo diccionario, convertirlo a lista
    es_lista = isinstance(articulos, list)
    if not es_lista:
        articulos = [articulos]
    
    for articulo in articulos:
        if articulo.get("images"):
            web_images = []
            for img_path in articulo["images"]:
                try:
                    print(f"DEBUG - Procesando imagen: {img_path}")
                    print(f"DEBUG - Images dir: {images_dir}")
                    
                    # Normalizar la ruta de la imagen
                    img_path_norm = os.path.abspath(img_path)
                    
                    # Verificar que el archivo existe
                    if not os.path.exists(img_path_norm):
                        print(f"WARN - Imagen no existe: {img_path_norm}")
                        continue
                    
                    # Calcular ruta relativa desde el directorio de imágenes
                    try:
                        rel_path = os.path.relpath(img_path_norm, images_dir)
                        print(f"DEBUG - Ruta relativa calculada: {rel_path}")
                        
                        # Convertir separadores de Windows a URL
                        url_path = rel_path.replace("\\", "/")
                        
                        # Asegurarnos de que no comience con ../
                        if url_path.startswith("../"):
                            # Si la imagen no está en el directorio esperado,
                            # intentar extraer solo el nombre de la carpeta del artículo y la imagen
                            parts = img_path_norm.replace("\\", "/").split("/")
                            if len(parts) >= 2:
                                # Buscar la carpeta "images" en la ruta
                                try:
                                    images_index = parts.index("images")
                                    # Tomar todo después de "images"
                                    url_path = "/".join(parts[images_index + 1:])
                                except ValueError:
                                    # Si no encuentra "images", usar los últimos 2 elementos
                                    url_path = "/".join(parts[-2:])
                            else:
                                url_path = parts[-1]
                        
                        web_url = "/images/" + url_path
                        print(f"DEBUG - URL web final: {web_url}")
                        
                        # Verificar que la URL resultante corresponde a un archivo real
                        check_path = os.path.join(images_dir, url_path.replace("/", os.sep))
                        if os.path.exists(check_path):
                            web_images.append(web_url)
                            print(f"SUCCESS - Imagen agregada: {web_url}")
                        else:
                            print(f"ERROR - Archivo no encontrado para URL: {web_url} -> {check_path}")
                            
                    except Exception as e:
                        print(f"ERROR - Calculando ruta relativa para {img_path}: {e}")
                        continue
                        
                except Exception as e:
                    print(f"ERROR - Procesando imagen {img_path}: {e}")
                    continue
            
            articulo["images"] = web_images
            print(f"DEBUG - Imágenes finales para artículo: {web_images}")
    
    return articulos if es_lista else articulos[0]

@app.route("/articulos")
def listar_articulos():
    page = int(request.args.get("page", 1))
    per_page = 20
    skip = (page - 1) * per_page

    cursor = almacen.col.find().skip(skip).limit(per_page)
    articulos = list(cursor)

    # CONVERTIR RUTAS DE IMÁGENES A URLs WEB
    articulos = convertir_rutas_imagenes(articulos)

    total = almacen.col.count_documents({})
    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "articulos.html",
        articulos=articulos,
        page=page,
        total_pages=total_pages,
        prev_page=page - 1 if page > 1 else None,
        next_page=page + 1 if page < total_pages else None
    )

@app.route("/articulo/<arxiv_id>")
def ver_articulo(arxiv_id):
    articulo = almacen.col.find_one({"arxiv_id": arxiv_id})
    if not articulo:
        return "Artículo no encontrado", 404

    # CONVERTIR RUTAS DE IMÁGENES A URLs WEB PARA EL DETALLE
    articulo = convertir_rutas_imagenes(articulo)

    return render_template("articulo_detalle.html", articulo=articulo)

# ============================
# RUTA PARA SERVIR IMÁGENES - MEJORADA
# ============================
@app.route("/images/<path:filename>")
def serve_images(filename):
    """Sirve las imágenes extraídas desde el directorio de imágenes"""
    images_dir = os.path.abspath(CFG.get("images_dir", "downloads/images"))
    
    # Construir ruta completa del archivo
    file_path = os.path.join(images_dir, filename.replace("/", os.sep))
    
    print(f"DEBUG - Solicitando imagen: {filename}")
    print(f"DEBUG - Ruta completa: {file_path}")
    print(f"DEBUG - Archivo existe: {os.path.exists(file_path)}")
    
    if not os.path.exists(file_path):
        print(f"ERROR - Imagen no encontrada: {file_path}")
        # Listar contenido del directorio para debug
        try:
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir):
                print(f"DEBUG - Contenido de {parent_dir}: {os.listdir(parent_dir)}")
        except Exception as e:
            print(f"DEBUG - Error listando directorio: {e}")
        return "Imagen no encontrada", 404
    
    try:
        return send_from_directory(images_dir, filename)
    except Exception as e:
        print(f"ERROR - Sirviendo imagen {filename}: {e}")
        return "Error sirviendo imagen", 500

# ============================
# RUTA DE DEBUG PARA INSPECCIONAR ESTRUCTURA
# ============================
@app.route("/debug/images")
def debug_images():
    """Ruta de debug para inspeccionar la estructura de imágenes"""
    images_dir = os.path.abspath(CFG.get("images_dir", "downloads/images"))
    
    if not os.path.exists(images_dir):
        return jsonify({"error": f"Directorio de imágenes no existe: {images_dir}"})
    
    def scan_directory(path, max_depth=3, current_depth=0):
        items = []
        if current_depth >= max_depth:
            return items
            
        try:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    items.append({
                        "name": item,
                        "type": "directory",
                        "children": scan_directory(item_path, max_depth, current_depth + 1)
                    })
                else:
                    items.append({
                        "name": item,
                        "type": "file",
                        "size": os.path.getsize(item_path)
                    })
        except PermissionError:
            pass
        
        return items
    
    structure = scan_directory(images_dir)
    
    return jsonify({
        "images_dir": images_dir,
        "exists": os.path.exists(images_dir),
        "structure": structure
    })

# ============================
if __name__ == "__main__":
    app.run(debug=True)