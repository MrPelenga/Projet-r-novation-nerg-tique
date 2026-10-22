"""
Phase 1 — Exploration de l'API DPE de l'ADEME.

Ce script :
1. récupère les métadonnées du jeu de données (nombre de lignes, schéma) ;
2. télécharge un échantillon ALÉATOIRE de DPE pour un département ;
3. l'enregistre dans data/raw/ pour l'analyse de qualité.

Usage : python src/exploration.py [code_departement] [taille_echantillon]
"""

import sys
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pandas as pd
import requests

# URL de l'API data-fair de l'ADEME (jeu "DPE Logements existants depuis juillet 2021")
URL_DATASET = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"

# L'API limite chaque page à 10 000 lignes maximum
TAILLE_PAGE_MAX = 10_000

DOSSIER_RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def recuperer_metadonnees() -> dict:
    """Retourne les métadonnées du jeu de données (schéma, nombre de lignes...)."""
    reponse = requests.get(URL_DATASET, timeout=60)
    reponse.raise_for_status()
    return reponse.json()


def telecharger_echantillon(code_departement: str, taille: int) -> pd.DataFrame:
    """
    Télécharge `taille` DPE tirés au hasard dans un département.

    - `sort=_rand` : l'API trie les lignes selon un nombre aléatoire pré-calculé,
      ce qui donne un échantillon représentatif (et non les DPE les plus anciens).
    - La pagination se fait avec le paramètre `after` renvoyé par l'API.
      On le réapplique sur l'URL d'origine pour garder exactement les mêmes filtres.
    """
    lignes = []
    after = None
    while len(lignes) < taille:
        params = {
            "qs": f"code_departement_ban:{code_departement}",
            "size": min(TAILLE_PAGE_MAX, taille - len(lignes)),
            "sort": "_rand",
        }
        if after:
            params["after"] = after

        reponse = requests.get(f"{URL_DATASET}/lines", params=params, timeout=120)
        reponse.raise_for_status()
        page = reponse.json()
        lignes.extend(page["results"])
        print(f"  {len(lignes):>6} / {taille} lignes téléchargées")

        if not page.get("next"):
            break  # plus de pages disponibles
        after = parse_qs(urlparse(page["next"]).query)["after"][0]

    return pd.DataFrame(lignes)


if __name__ == "__main__":
    departement = sys.argv[1] if len(sys.argv) > 1 else "94"
    taille = int(sys.argv[2]) if len(sys.argv) > 2 else 20_000

    meta = recuperer_metadonnees()
    print(f"Jeu de données : {meta['title']}")
    print(f"Nombre total de DPE (France) : {meta['count']:,}".replace(",", " "))
    print(f"Dernière mise à jour des données : {meta.get('dataUpdatedAt')}")
    print(f"Nombre de colonnes : {len(meta['schema'])}")

    DOSSIER_RAW.mkdir(parents=True, exist_ok=True)
    # On garde une copie du schéma : utile pour documenter les colonnes
    with open(DOSSIER_RAW / "schema_dpe03existant.json", "w", encoding="utf-8") as f:
        json.dump(meta["schema"], f, ensure_ascii=False, indent=2)

    print(f"\nTéléchargement d'un échantillon de {taille} DPE du département {departement}...")
    df = telecharger_echantillon(departement, taille)
    chemin = DOSSIER_RAW / f"echantillon_{departement}.csv"
    df.to_csv(chemin, index=False, encoding="utf-8")
    print(f"Échantillon enregistré : {chemin} ({len(df)} lignes, {df.shape[1]} colonnes)")
