# app.py
from flask import Flask, request, render_template, jsonify
import os
import json
import threading
import time

from arxiv_client import ArxivClient
from arxiv_parser import parse_counts
from procesador import ProcesadorArticulos

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

# ============================
# VARIABLES GLOBALES RF2
# ============================
procesador_obj = None
procesador_thread = None
start_time = None

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

    xml_path = client.fetch_and_save(q, start=start, max_results=max_results)
    counts = parse_counts(xml_path)

    return render_template(
        "resultados.html",
        query=q,
        xml_path=xml_path,
        xml_filename=os.path.basename(xml_path),
        total=counts["total_results"],
        returned=counts["returned_results"],
        start=start,
        max_results=max_results
    )

# ============================
# RUTAS RF2
# ============================
@app.route("/procesar")
def procesar():
    global procesador_obj, procesador_thread, start_time

    # DEBUG para ver qué está llegando
    print(f"DEBUG - Todos los parámetros recibidos: {dict(request.args)}")
    
    # En lugar de recibir el nombre del archivo, buscar el XML más reciente
    query = request.args.get("query")  # Recibiremos el query de búsqueda
    
    print(f"DEBUG - Query recibido: '{query}'")
    
    if not query:
        return jsonify({"error": "No se especificó el query de búsqueda"}), 400
    
    # Buscar archivos XML que coincidan con el query
    if not os.path.exists(DOWNLOADS_DIR):
        return jsonify({"error": "Directorio downloads no existe"}), 400
    
    xml_files = []
    query_normalized = query.replace(' ', '-').lower()
    
    print(f"DEBUG - Buscando archivos que contengan: arxiv_{query_normalized}")
    
    for file in os.listdir(DOWNLOADS_DIR):
        print(f"DEBUG - Examinando archivo: {file}")
        if file.startswith("arxiv_") and file.endswith(".xml"):
            # Buscar archivos XML que contengan el query normalizado
            if query_normalized in file.lower():
                file_path = os.path.join(DOWNLOADS_DIR, file)
                file_time = os.path.getmtime(file_path)
                xml_files.append((file_path, file_time))
                print(f"DEBUG - Archivo coincide: {file}")
    
    print(f"DEBUG - Archivos XML encontrados: {len(xml_files)}")
    
    if not xml_files:
        return jsonify({"error": f"No se encontró XML para el query: {query}. Archivos disponibles: {[f for f in os.listdir(DOWNLOADS_DIR) if f.endswith('.xml')]}"}), 400
    
    # Obtener el archivo más reciente
    xml_path = max(xml_files, key=lambda x: x[1])[0]
    
    # DEBUG: Agregar estas líneas temporalmente
    print(f"DEBUG - query recibido: '{query}'")
    print(f"DEBUG - xml_path encontrado: '{xml_path}'")
    print(f"DEBUG - xml_path existe: {os.path.exists(xml_path)}")
    print(f"DEBUG - archivos XML encontrados: {[f[0] for f in xml_files]}")
    
    if not os.path.exists(xml_path):
        return jsonify({"error": f"XML no encontrado: '{xml_path}'"}), 400

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

    if not procesador_obj:
        return jsonify({"error": "No hay procesamiento en curso"}), 400

    elapsed = int(time.time() - start_time) if start_time else 0
    return jsonify({
        "procesados": procesador_obj.procesados,
        "total": procesador_obj.total_a_procesar,
        "elapsed": elapsed,
        "done": procesador_obj.procesados >= procesador_obj.total_a_procesar
    })

# ============================
if __name__ == "__main__":
    app.run(debug=True)