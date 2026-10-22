"""
Accès à la base DuckDB et exécution des requêtes SQL du dossier sql/analyse/.

Toutes les requêtes lisent la vue `dpe_filtre`. Cette vue est (re)définie ici à partir
des filtres choisis : c'est ce qui permettra à l'application de filtrer tous les
graphiques d'un coup (département, type de logement, période, chauffage).
"""

import os
from pathlib import Path

import duckdb
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "processed" / "dpe_idf.duckdb"
# Version allégée versionnée sur GitHub, utilisée en ligne (voir src/preparer_deploiement.py)
PARQUET_APPLICATION = RACINE / "data" / "processed" / "dpe_idf_app.parquet"
DOSSIER_SQL = RACINE / "sql" / "analyse"

NOMS_DEPARTEMENTS = {
    "75": "Paris", "77": "Seine-et-Marne", "78": "Yvelines", "91": "Essonne",
    "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis", "94": "Val-de-Marne", "95": "Val-d'Oise",
}

# Filtres possibles : nom du filtre → colonne de la table dpe
COLONNES_FILTRABLES = {
    "departements": "code_departement",
    "types_logement": "type_logement",
    "periodes": "periode_construction",
    "energies": "energie_chauffage_groupe",
}


def ouvrir_base() -> duckdb.DuckDBPyConnection:
    """
    Ouvre la base DuckDB complète si elle existe (en local, après le nettoyage).
    Sinon (en ligne), charge en mémoire la version allégée en Parquet.
    La variable d'environnement DPE_SOURCE=parquet force la version allégée (pour la tester).
    """
    if BASE.exists() and os.environ.get("DPE_SOURCE") != "parquet":
        return duckdb.connect(str(BASE), read_only=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE dpe AS SELECT * FROM read_parquet('{PARQUET_APPLICATION.as_posix()}')")
    return con


def connexion() -> duckdb.DuckDBPyConnection:
    """Ouvre la base et crée la table `dpe_filtre` sans filtre."""
    con = ouvrir_base()
    appliquer_filtres(con)
    return con


def appliquer_filtres(con: duckdb.DuckDBPyConnection, **filtres: list[str]) -> None:
    """
    Redéfinit la vue `dpe_filtre`. Exemple : appliquer_filtres(con, departements=["75", "92"]).
    Une liste vide ou absente = pas de filtre sur cette colonne.
    Les valeurs sont passées en paramètres SQL ($1, $2...) et jamais collées dans la requête :
    c'est la bonne pratique contre les injections SQL.
    """
    conditions, valeurs = [], []
    for nom, liste in filtres.items():
        if liste:
            colonne = COLONNES_FILTRABLES[nom]
            conditions.append(f"{colonne} IN (SELECT unnest(${len(valeurs) + 1}::VARCHAR[]))")
            valeurs.append(list(liste))
    where = " AND ".join(conditions) or "TRUE"
    # Une vue ne peut pas contenir de paramètres : on matérialise le résultat filtré
    # dans une table temporaire (rapide avec DuckDB, quelques dixièmes de seconde).
    con.execute(f"CREATE OR REPLACE TEMP TABLE dpe_filtre AS SELECT * FROM dpe WHERE {where}", valeurs)


def executer(con: duckdb.DuckDBPyConnection, nom_fichier: str) -> pd.DataFrame:
    """Exécute un fichier de sql/analyse/ (ex. "04_passoires_par_periode") et renvoie un DataFrame."""
    requete = (DOSSIER_SQL / f"{nom_fichier}.sql").read_text(encoding="utf-8")
    return con.execute(requete).df()
