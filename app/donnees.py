"""
Accès aux données pour l'application, avec mise en cache Streamlit.

- La connexion DuckDB est ouverte une seule fois (st.cache_resource).
- Les résultats des requêtes sont mis en cache pour chaque combinaison de filtres
  (st.cache_data) : revenir sur une sélection déjà vue est instantané.
- Chaque calcul utilise son propre curseur DuckDB : deux visiteurs qui filtrent en même
  temps ont chacun leur table `dpe_filtre`, sans interférence.
"""

import json

import duckdb
import pandas as pd
import streamlit as st

from requetes import COLONNES_FILTRABLES, RACINE, appliquer_filtres, executer, ouvrir_base

CONTOURS = RACINE / "data" / "processed" / "communes_idf_simplifie.geojson"
DATE_EXTRACTION = RACINE / "data" / "processed" / "date_extraction.txt"
JOURNAL_NETTOYAGE = RACINE / "data" / "processed" / "journal_nettoyage.csv"

REQUETES = [
    "01_chiffres_cles", "02_etiquettes", "03_etiquettes_par_departement",
    "04_passoires_par_periode", "05_passoires_par_chauffage", "06_passoires_par_type_logement",
    "07_passoires_par_surface", "08_distribution_conso", "09_passoires_par_commune",
    "10_evolution_trimestrielle",
]


@st.cache_resource
def connexion() -> duckdb.DuckDBPyConnection:
    return ouvrir_base()


@st.cache_data
def journal_nettoyage() -> pd.DataFrame:
    return pd.read_csv(JOURNAL_NETTOYAGE)


@st.cache_data(show_spinner="Calcul des indicateurs…")
def resultats(filtres: tuple) -> dict[str, pd.DataFrame]:
    """
    Exécute toutes les requêtes d'analyse pour une combinaison de filtres.
    `filtres` est un tuple de (nom_filtre, tuple_de_valeurs) : un tuple, et non un dict,
    car le cache de Streamlit a besoin d'arguments « hachables ».
    """
    curseur = connexion().cursor()
    appliquer_filtres(curseur, **{nom: list(valeurs) for nom, valeurs in filtres})
    return {nom: executer(curseur, nom) for nom in REQUETES}


@st.cache_data
def valeurs_possibles() -> dict[str, list[str]]:
    """Valeurs proposées dans chaque filtre, triées dans un ordre lisible."""
    con = connexion()
    valeurs = {}
    for nom, colonne in COLONNES_FILTRABLES.items():
        liste = [v for (v,) in con.execute(f"SELECT DISTINCT {colonne} FROM dpe").fetchall()]
        if colonne == "periode_construction":
            # Ordre chronologique plutôt qu'alphabétique
            liste.sort(key=lambda p: "0" if p == "avant 1948" else "9" if p == "après 2021" else p)
        else:
            liste.sort()
        valeurs[nom] = liste
    return valeurs


@st.cache_data
def contours() -> dict:
    return json.loads(CONTOURS.read_text(encoding="utf-8"))


@st.cache_data
def date_extraction() -> str:
    annee, mois, jour = DATE_EXTRACTION.read_text(encoding="utf-8").strip().split("-")
    return f"{jour}/{mois}/{annee}"
