"""
Phase 2 — Collecte des DPE d'Île-de-France via l'API de l'ADEME.

Pour chacun des 8 départements :
- on ne demande que les colonnes utiles (paramètre `select`) pour limiter le volume ;
- on filtre côté serveur sur le département (paramètre `qs`) ;
- on parcourt toutes les pages (10 000 lignes max par page, curseur `after`) ;
- on demande le format CSV, environ 3 fois plus rapide à télécharger que le JSON
  (le JSON répète le nom de chaque colonne sur chaque ligne) ;
- on enregistre un fichier Parquet par département dans data/raw/.

Le script est "reprenable" : un département déjà téléchargé n'est pas re-téléchargé
(utile si la connexion coupe en plein milieu). Utiliser --force pour tout refaire.

On récupère aussi le référentiel des communes (noms officiels, population, contours)
depuis l'API Géo, car les noms de communes de l'ADEME sont mal saisis.

Usage : python src/collecte.py [codes départements...] [--force]
"""

import sys
import time
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import duckdb
import pandas as pd
import requests

URL_DATASET = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"
URL_API_GEO = "https://geo.api.gouv.fr"

DEPARTEMENTS_IDF = ["75", "77", "78", "91", "92", "93", "94", "95"]
TAILLE_PAGE = 10_000

# Colonnes retenues après l'exploration (voir docs/phase1_exploration.md)
COLONNES = [
    # Identification et date
    "numero_dpe", "date_etablissement_dpe",
    # Résultat du DPE
    "etiquette_dpe", "etiquette_ges",
    "conso_5_usages_par_m2_ep", "conso_5_usages_par_m2_ef", "emission_ges_5_usages_par_m2",
    "cout_total_5_usages", "cout_chauffage",
    # Caractéristiques du logement
    "type_batiment", "surface_habitable_logement",
    "annee_construction", "periode_construction",
    "type_energie_principale_chauffage", "type_installation_chauffage",
    "qualite_isolation_murs", "qualite_isolation_menuiseries",
    "qualite_isolation_plancher_haut_comble_perdu", "qualite_isolation_plancher_bas",
    # Localisation (identifiant_ban + étage servent à repérer les doublons)
    "code_insee_ban", "code_postal_ban", "code_departement_ban",
    "identifiant_ban", "numero_etage_appartement", "_geopoint",
]

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_RAW = RACINE / "data" / "raw"


def requete_avec_reessais(url: str, params: dict, essais: int = 5) -> requests.Response:
    """GET avec ré-essais : en cas d'erreur réseau, on attend de plus en plus longtemps."""
    for tentative in range(1, essais + 1):
        try:
            reponse = requests.get(url, params=params, timeout=300)
            reponse.raise_for_status()
            return reponse
        except requests.RequestException as erreur:
            if tentative == essais:
                raise
            attente = 10 * tentative
            print(f"\n    erreur ({erreur}), nouvel essai dans {attente} s...")
            time.sleep(attente)


def collecter_departement(code_dep: str, fichier_parquet: Path) -> None:
    """Télécharge tous les DPE actifs d'un département et les enregistre en Parquet."""
    filtre = {"qs": f"code_departement_ban:{code_dep}"}
    # Le format CSV ne donne pas le total : on le demande à part (size=0 → aucune ligne)
    total = requete_avec_reessais(f"{URL_DATASET}/lines", {**filtre, "size": 0}).json()["total"]

    # Les pages CSV sont écrites à la suite dans un fichier temporaire
    fichier_csv = fichier_parquet.with_suffix(".csv.part")
    nb_pages, after = 0, None
    with open(fichier_csv, "w", encoding="utf-8", newline="") as f:
        while True:
            params = {**filtre, "size": TAILLE_PAGE, "format": "csv", "select": ",".join(COLONNES)}
            if after:
                params["after"] = after
            reponse = requete_avec_reessais(f"{URL_DATASET}/lines", params)
            texte = reponse.content.decode("utf-8-sig")  # utf-8-sig retire le BOM du début

            entete, _, lignes = texte.partition("\n")
            if nb_pages == 0:
                # L'en-tête n'est écrit qu'une seule fois. L'API y remplace parfois un "_"
                # par une espace (ex. "conso_5 usages_par_m2_ef") : on remet les "_".
                f.write(entete.replace(" ", "_") + "\n")
            if not lignes.strip():
                break  # page vide : on a tout récupéré
            f.write(lignes if lignes.endswith("\n") else lignes + "\n")
            nb_pages += 1
            print(f"    page {nb_pages} / {-(-total // TAILLE_PAGE)}", end="\r")

            # En CSV, le lien vers la page suivante est dans l'en-tête HTTP "Link".
            # On réapplique le curseur sur l'URL d'origine pour garder les mêmes filtres.
            suivante = reponse.links.get("next", {}).get("url")
            if not suivante:
                break
            after = parse_qs(urlparse(suivante).query)["after"][0]
    print()

    # Conversion CSV → Parquet avec DuckDB. Les codes (INSEE, postal...) sont forcés en texte
    # pour ne pas perdre les zéros ni confondre "2A" et un nombre.
    con = duckdb.connect()
    types_texte = {c: "VARCHAR" for c in ["code_insee_ban", "code_postal_ban",
                                          "code_departement_ban", "identifiant_ban", "numero_dpe"]}
    con.execute(f"""
        COPY (SELECT * FROM read_csv('{fichier_csv.as_posix()}', header = true, types = {types_texte}))
        TO '{fichier_parquet.as_posix()}' (FORMAT parquet)
    """)
    nb_lignes = con.execute(f"SELECT count(*) FROM '{fichier_parquet.as_posix()}'").fetchone()[0]
    con.close()
    fichier_csv.unlink()

    # Contrôle : on doit avoir récupéré exactement le nombre annoncé par l'API
    if nb_lignes != total:
        print(f"    ATTENTION : {nb_lignes} lignes reçues pour {total} annoncées")
    print(f"    {nb_lignes:,} DPE enregistrés".replace(",", " "))


def collecter_communes() -> None:
    """
    Référentiel des communes d'IDF depuis l'API Géo :
    - communes_idf.csv : code INSEE, nom officiel, département, population ;
    - communes_idf.geojson : contours pour la carte.
    Paris est découpé en 20 arrondissements (codes 75101 à 75120), comme dans l'ADEME.
    """
    communes, contours = [], []
    for code_dep in DEPARTEMENTS_IDF:
        for type_commune in ["commune-actuelle", "arrondissement-municipal"]:
            params = {"codeDepartement": code_dep, "type": type_commune,
                      "fields": "nom,code,codeDepartement,population,contour",
                      "format": "geojson", "geometry": "contour"}
            geo = requete_avec_reessais(f"{URL_API_GEO}/communes", params).json()
            for entite in geo["features"]:
                p = entite["properties"]
                # Paris : on garde les arrondissements, pas la commune "Paris" entière
                if p["code"] == "75056":
                    continue
                communes.append({"code_insee": p["code"], "nom_commune": p["nom"],
                                 "code_departement": p["codeDepartement"],
                                 "population": p.get("population")})
                contours.append(entite)

    pd.DataFrame(communes).drop_duplicates("code_insee").to_csv(
        DOSSIER_RAW / "communes_idf.csv", index=False, encoding="utf-8")
    with open(DOSSIER_RAW / "communes_idf.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": contours}, f, ensure_ascii=False)
    print(f"  {len(communes)} communes / arrondissements enregistrés")


if __name__ == "__main__":
    forcer = "--force" in sys.argv
    # On peut limiter la collecte à certains départements (ex. : python src/collecte.py 75 92)
    # pour lancer plusieurs collectes en parallèle et gagner du temps.
    departements = [a for a in sys.argv[1:] if a in DEPARTEMENTS_IDF] or DEPARTEMENTS_IDF
    DOSSIER_RAW.mkdir(parents=True, exist_ok=True)

    if forcer or not (DOSSIER_RAW / "communes_idf.csv").exists():
        print("Référentiel des communes (API Géo)...")
        collecter_communes()

    for code_dep in departements:
        fichier = DOSSIER_RAW / f"dpe_{code_dep}.parquet"
        if fichier.exists() and not forcer:
            print(f"Département {code_dep} : déjà téléchargé, on passe.")
            continue
        print(f"Département {code_dep} :")
        debut = time.time()
        collecter_departement(code_dep, fichier)
        print(f"    terminé en {(time.time() - debut) / 60:.0f} min")

    # Date d'extraction : affichée dans la page Méthodologie
    (DOSSIER_RAW / "date_extraction.txt").write_text(date.today().isoformat(), encoding="utf-8")
    print("Collecte terminée.")
