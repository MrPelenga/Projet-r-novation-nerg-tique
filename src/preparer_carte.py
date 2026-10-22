"""
Phase 4 — Simplification des contours de communes pour la carte.

Les contours de l'API Géo sont très détaillés (7 Mo pour l'Île-de-France). Pour une carte
à l'échelle régionale, une précision d'environ 50 m suffit : on simplifie les polygones
(algorithme de Douglas-Peucker) et on arrondit les coordonnées, pour un fichier bien plus
léger qui s'affiche vite dans le navigateur.

Usage : python src/preparer_carte.py
"""

import json
from pathlib import Path

from shapely.geometry import mapping, shape

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "data" / "raw" / "communes_idf.geojson"
CIBLE = RACINE / "data" / "processed" / "communes_idf_simplifie.geojson"

TOLERANCE_DEGRES = 0.0005  # environ 50 m à la latitude de Paris
DECIMALES = 5              # environ 1 m : au-delà, la précision est inutile


def arrondir(coordonnees):
    """Arrondit récursivement toutes les coordonnées d'une géométrie."""
    if isinstance(coordonnees[0], (int, float)):
        return [round(c, DECIMALES) for c in coordonnees]
    return [arrondir(c) for c in coordonnees]


if __name__ == "__main__":
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    entites = []
    for entite in source["features"]:
        geometrie = shape(entite["geometry"]).simplify(TOLERANCE_DEGRES, preserve_topology=True)
        geo = mapping(geometrie)
        entites.append({
            "type": "Feature",
            # On ne garde que le code INSEE : les indicateurs sont ajoutés par l'application
            "properties": {"code_insee": entite["properties"]["code"]},
            "geometry": {"type": geo["type"], "coordinates": arrondir(geo["coordinates"])},
        })

    CIBLE.parent.mkdir(parents=True, exist_ok=True)
    CIBLE.write_text(json.dumps({"type": "FeatureCollection", "features": entites},
                                separators=(",", ":")), encoding="utf-8")
    print(f"{len(entites)} communes : {SOURCE.stat().st_size / 1e6:.1f} Mo → {CIBLE.stat().st_size / 1e6:.1f} Mo")
