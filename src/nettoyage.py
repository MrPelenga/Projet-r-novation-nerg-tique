"""
Phase 2 — Nettoyage des DPE et chargement dans DuckDB.

Le nettoyage est écrit en SQL (sql/nettoyage.sql) : DuckDB traite les 3,4 millions
de lignes en quelques secondes, sans tout charger en mémoire comme pandas.

Ce script :
1. exécute sql/nettoyage.sql étape par étape ;
2. compte les lignes après chaque règle → journal de nettoyage (docs + page Méthodologie) ;
3. n'enregistre dans data/processed/dpe_idf.duckdb que les tables finales `dpe` et `communes`.

Usage : python src/nettoyage.py   (à lancer depuis la racine du projet)
"""

import os
import re
from pathlib import Path

import duckdb
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
FICHIER_SQL = RACINE / "sql" / "nettoyage.sql"
BASE = RACINE / "data" / "processed" / "dpe_idf.duckdb"
JOURNAL = RACINE / "data" / "processed" / "journal_nettoyage.csv"


def decouper_etapes(script: str) -> list[tuple[str, str, str]]:
    """Découpe le script SQL en étapes (table, description, requête) grâce aux balises @etape."""
    morceaux = re.split(r"^-- @etape ", script, flags=re.MULTILINE)
    etapes = []
    for morceau in morceaux[1:]:
        entete, requete = morceau.split("\n", 1)
        table, description = [x.strip() for x in entete.split("|", 1)]
        etapes.append((table, description, requete))
    return etapes


if __name__ == "__main__":
    # Les chemins du fichier SQL sont relatifs à la racine du projet
    os.chdir(RACINE)
    BASE.parent.mkdir(parents=True, exist_ok=True)
    # Les étapes intermédiaires sont calculées en mémoire : écrites dans le fichier,
    # elles le gonfleraient (DuckDB ne libère pas l'espace des tables supprimées).
    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")

    journal = []
    for table, description, requete in decouper_etapes(FICHIER_SQL.read_text(encoding="utf-8")):
        con.execute(requete)
        nb_lignes = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        journal.append({"etape": table, "description": description, "lignes": nb_lignes})
        print(f"{nb_lignes:>10,}  {description}".replace(",", " "))

    # Nombre de lignes retirées par chaque règle
    df_journal = pd.DataFrame(journal)
    df_journal["lignes_retirees"] = (-df_journal["lignes"].diff()).fillna(0).astype(int)
    df_journal["pct_retire"] = (100 * df_journal["lignes_retirees"] / df_journal["lignes"].iloc[0]).round(2)
    df_journal.to_csv(JOURNAL, index=False, encoding="utf-8")

    # Seules les tables finales sont écrites dans la base DuckDB (fichier recréé à neuf)
    BASE.unlink(missing_ok=True)
    con.execute(f"ATTACH '{BASE.as_posix()}' AS base")
    for table in ["dpe", "communes"]:
        con.execute(f"CREATE TABLE base.{table} AS SELECT * FROM {table}")
    con.execute("DETACH base")
    con.close()

    taille_mo = BASE.stat().st_size / 1e6
    print(f"\nBase DuckDB : {BASE.relative_to(RACINE)} ({taille_mo:.0f} Mo)")
    print(f"Journal : {JOURNAL.relative_to(RACINE)}")
