"""
Phase 6 — Données allégées pour le déploiement (Streamlit Community Cloud).

La base DuckDB complète (≈ 140 Mo) dépasse la limite de 100 Mo par fichier de GitHub.
L'application n'a besoin que de 12 colonnes : on les exporte en Parquet compressé
(≈ 14 Mo), un fichier versionné avec le code. En ligne, l'application charge ce fichier
en mémoire au démarrage (voir src/requetes.py).

Usage : python src/preparer_deploiement.py   (après src/nettoyage.py)
"""

import shutil
from pathlib import Path

import duckdb

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "processed" / "dpe_idf.duckdb"
PARQUET = RACINE / "data" / "processed" / "dpe_idf_app.parquet"

# Colonnes lues par les requêtes de sql/analyse/ et par les filtres de l'application
COLONNES_APPLICATION = [
    "date_dpe", "etiquette_dpe", "est_passoire", "conso_ep_m2", "surface_m2",
    "code_insee", "nom_commune", "code_departement",
    "periode_construction", "tranche_surface", "type_logement", "energie_chauffage_groupe",
]

if __name__ == "__main__":
    con = duckdb.connect(str(BASE), read_only=True)
    con.execute("SET enable_progress_bar = false")
    # Trier par commune regroupe les valeurs identiques : la compression est bien meilleure
    con.execute(f"""
        COPY (SELECT {', '.join(COLONNES_APPLICATION)} FROM dpe ORDER BY code_insee, date_dpe)
        TO '{PARQUET.as_posix()}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 19)
    """)
    nb = con.execute(f"SELECT count(*) FROM '{PARQUET.as_posix()}'").fetchone()[0]
    con.close()
    # La date d'extraction est affichée dans l'application : on la copie à côté des données versionnées
    shutil.copy(RACINE / "data" / "raw" / "date_extraction.txt", RACINE / "data" / "processed" / "date_extraction.txt")
    print(f"{nb:,} DPE → {PARQUET.relative_to(RACINE)} ({PARQUET.stat().st_size / 1e6:.0f} Mo)".replace(",", " "))
