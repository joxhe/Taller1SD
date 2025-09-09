# arxiv_parser.py
import xml.etree.ElementTree as ET

ATOM_NS = "http://www.w3.org/2005/Atom"
OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"

NS = {
    "atom": ATOM_NS,
    "opensearch": OPENSEARCH_NS,
}

def parse_counts(xml_path: str) -> dict:
    """
    Devuelve:
    - total_results: total global (opensearch:totalResults)
      - returned_results: items devueltos en *esta* respuesta (conteo de <entry>)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    total_text = root.findtext("opensearch:totalResults", default="0", namespaces=NS)
    try:
        total_results = int(total_text)
    except (ValueError, TypeError):
        total_results = 0

    returned_results = len(root.findall("atom:entry", NS))

    return {
        "total_results": total_results,
        "returned_results": returned_results,
    }

# opcional: función para obtener títulos (útil después)
def parse_titles(xml_path: str):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    titles = []
    for e in root.findall("atom:entry", NS):
        t = e.findtext("atom:title", default="", namespaces=NS)
        titles.append(t.strip())
    return titles
