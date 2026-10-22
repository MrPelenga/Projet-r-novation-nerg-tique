"""Page 5 — Méthodologie : source, extraction, nettoyage, limites et hypothèses du simulateur."""

import pandas as pd
import streamlit as st

from donnees import date_extraction, journal_nettoyage, resultats
from insights import _nombre
from simulateur import charger_hypotheses

cles = resultats(filtres=())["01_chiffres_cles"].iloc[0]

st.title("Méthodologie")

st.header("Source des données")
st.markdown(
    f"""
- **Jeu de données** : [DPE Logements existants (depuis juillet 2021)](https://www.data.gouv.fr/datasets/dpe-logements-existants-depuis-juillet-2021/), ADEME, licence ouverte.
- **Accès** : API data-fair de l'ADEME (jeu `dpe03existant`), filtrée côté serveur sur les 8 départements d'Île-de-France.
- **Date d'extraction** : {date_extraction()} — DPE établis du {cles['premier_dpe']:%d/%m/%Y} au {cles['dernier_dpe']:%d/%m/%Y}.
- **Contours des communes** : [API Géo](https://geo.api.gouv.fr) (Paris découpé en 20 arrondissements), simplifiés à environ 50 m près.
- **Volume** : 3 372 843 DPE téléchargés, **{_nombre(cles['nb_dpe'])} logements** après nettoyage.
"""
)

st.header("Chaîne de traitement")
st.markdown(
    """
| Étape | Outil | Fichier |
|---|---|---|
| 1. Collecte (API, pages de 10 000 lignes, contrôle du total) | Python, requests | `src/collecte.py` |
| 2. Nettoyage et chargement | **SQL** (DuckDB) | `sql/nettoyage.sql` |
| 3. Indicateurs (une requête par question) | **SQL** (DuckDB) | `sql/analyse/*.sql` |
| 4. Graphiques et phrases d'insight | Plotly, pandas | `src/graphiques.py`, `src/insights.py` |
| 5. Simulateur (logique testée) | Python, pytest | `src/simulateur.py`, `tests/` |
| 6. Application | Streamlit, pydeck | `app/` |
"""
)

st.header("Règles de nettoyage")
journal = journal_nettoyage()
st.dataframe(
    journal[["description", "lignes", "lignes_retirees", "pct_retire"]],
    hide_index=True, use_container_width=True,
    column_config={
        "description": "Étape",
        "lignes": st.column_config.NumberColumn("Lignes restantes", format="localized"),
        "lignes_retirees": st.column_config.NumberColumn("Lignes retirées", format="localized"),
        "pct_retire": st.column_config.NumberColumn("% du brut", format="%.2f %%"),
    },
)
st.markdown(
    """
- **DPE « immeuble » exclus** : un seul DPE couvre tout un bâtiment ; les statistiques comptent des logements.
- **Valeurs aberrantes** : surface hors 8–500 m², consommation ≤ 0 ou > 1 500 kWh/m²/an.
- **Fusions de communes** : les anciens codes sont rattachés à la commune actuelle (Pierrefitte-sur-Seine → Saint-Denis, Gouzangrez → Commeny ; « Paris » sans arrondissement → arrondissement déduit du code postal).
- **Logements re-diagnostiqués** : même adresse précise, même surface, même étage et même type, avec des dates **toutes différentes** → on garde le DPE le plus récent. Plusieurs DPE identiques **le même jour** sont des appartements distincts d'un immeuble diagnostiqués en lot (jusqu'à 839 à une adresse) : ils sont tous conservés. Une règle « garder le plus récent » appliquée sans ce garde-fou aurait supprimé 34 % des données et gonflé la part de passoires de 11,4 % à 14,5 %.
"""
)

st.header("Définitions")
st.markdown(
    """
- **Passoire thermique** : logement classé **F ou G** au DPE.
- **Étiquette DPE** : déterminée par la consommation d'énergie primaire **et** les émissions de CO₂ par m² (la plus mauvaise des deux).
- **Consommation** : énergie primaire, 5 usages (chauffage, eau chaude, refroidissement, éclairage, auxiliaires), en kWh/m²/an.
"""
)

st.header("Limites")
st.markdown(
    """
- **Biais de sélection** : un DPE est surtout réalisé lors d'une vente ou d'une location. La base décrit les logements mis sur le marché depuis 2021, pas l'ensemble du parc (les propriétaires occupants de longue date y sont sous-représentés).
- **Composition dans le temps** : la part de logements anciens parmi les DPE réalisés varie selon les années (elle augmente depuis 2025). Les évolutions sont à interpréter avec prudence.
- **Réformes du calcul** : coefficient de l'électricité abaissé de 2,3 à 1,9 au 1er janvier 2026 (les DPE antérieurs semblent déjà recalculés dans la base publiée) ; seuils relevés pour les logements de 40 m² ou moins au 1er juillet 2024.
- **Dédoublonnage imparfait** : deux appartements identiques au même étage diagnostiqués à des dates différentes sont fusionnés à tort.
- **Petites communes** : en dessous de 30 DPE, le pourcentage n'est pas affiché sur la carte.
"""
)

st.header("Hypothèses du simulateur")
st.markdown(
    "Toutes les hypothèses sont dans `config/hypotheses.yaml` et modifiables dans la page Simulateur. "
    "Les gains d'isolation, les consommations de référence et les rendements des chaudières sont "
    "**calculés sur les DPE franciliens** (`src/references_simulateur.py`)."
)
h = charger_hypotheses()
lignes = []
for energie, prix in h["prix_energie"].items():
    lignes.append((f"Prix : {energie}", f"{prix['valeur']} €/kWh", prix["source"], prix.get("a_verifier", False)))
for cout in h["couts_travaux"].values():
    lignes.append((cout["libelle"], f"{cout['valeur']} {cout['unite']} ({cout['min']} à {cout['max']})",
                   cout["source"], cout.get("a_verifier", False)))
lignes += [
    ("Pompe à chaleur : coût", f"{h['pompe_a_chaleur']['cout']['valeur']} €", h["pompe_a_chaleur"]["cout"]["source"], False),
    ("Pompe à chaleur : SCOP", str(h["pompe_a_chaleur"]["scop"]["valeur"]), h["pompe_a_chaleur"]["scop"]["source"], False),
    ("Rénovation d'ampleur : coût", f"{h['renovation_ampleur']['cout_moyen']['valeur']} €",
     h["renovation_ampleur"]["cout_moyen"]["source"], False),
    ("Quantités de travaux (m² de murs, de combles, nombre de fenêtres)", "déduites de la surface",
     "Géométrie simplifiée, sans source", True),
    ("Hausse annuelle des prix de l'énergie", "0 %/an", "Choix : prix constants", True),
]
st.dataframe(
    pd.DataFrame(lignes, columns=["Hypothèse", "Valeur", "Source", "À vérifier"]),
    hide_index=True, use_container_width=True,
    column_config={"À vérifier": st.column_config.CheckboxColumn("⚠️ À vérifier")},
)
st.caption("Le simulateur est une estimation pédagogique : il ne remplace pas un audit énergétique.")
