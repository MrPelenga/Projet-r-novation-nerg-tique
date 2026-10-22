"""
Phase 5 — Valeurs de référence du simulateur, calculées sur les vrais DPE d'Île-de-France.

Plutôt que des moyennes nationales génériques, le simulateur s'appuie sur ce que disent
les DPE franciliens eux-mêmes. Ce script interroge l'API ADEME (agrégations côté serveur,
sans tout télécharger) et produit 4 tables dans data/processed/ :

1. reference_consommation.csv : pour chaque (type de logement, étiquette, énergie),
   la consommation de chauffage par m² et la consommation totale en énergie primaire par m² ;
2. reference_deperditions.csv : pour chaque (type, étiquette), la part de chaque paroi
   (murs, toiture, fenêtres, plancher bas) dans les pertes de chaleur ;
3. reference_isolation.csv : de combien les pertes d'une paroi baissent quand elle est
   « très bien » isolée plutôt qu'« insuffisamment » isolée (par m² habitable) ;
4. reference_rendement.csv : rendement moyen des chauffages (chaleur utile / énergie consommée).

Usage : python src/references_simulateur.py
"""

from pathlib import Path

import pandas as pd
import requests

URL = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/metric_agg"
DOSSIER = Path(__file__).resolve().parents[1] / "data" / "processed"

# Filtre commun : Île-de-France, surfaces plausibles (mêmes règles que le nettoyage),
# pertes de chaleur plausibles pour un logement (exclut les valeurs saisies à l'échelle d'un immeuble)
BASE_FILTRE = ("code_region_ban:11 AND surface_habitable_logement:[8 TO 500] "
               "AND deperditions_enveloppe:[1 TO 3000]")

TYPES = ["maison", "appartement"]
ETIQUETTES = list("ABCDEFG")
# Les 4 énergies proposées dans le simulateur (99 % des DPE d'IDF)
ENERGIES = ["Électricité", "Gaz naturel", "Fioul domestique", "Réseau de Chauffage urbain"]

# Paroi → (colonne de pertes de chaleur, colonne de qualité d'isolation)
PAROIS = {
    "murs": ("deperditions_murs", "qualite_isolation_murs"),
    "toiture": ("deperditions_planchers_hauts", "qualite_isolation_plancher_haut_comble_perdu"),
    "fenetres": ("deperditions_baies_vitrees", "qualite_isolation_menuiseries"),
    "plancher_bas": ("deperditions_planchers_bas", "qualite_isolation_plancher_bas"),
}


def agreger(champ: str, filtre: str, mesure: str = "median") -> tuple[float | None, int]:
    """Moyenne ou médiane d'un champ sur les DPE correspondant au filtre. Renvoie (valeur, nb de DPE)."""
    params = {"field": champ, "qs": f"{BASE_FILTRE} AND {filtre}"}
    if mesure == "median":
        params.update(metric="percentiles", percents="50")
    else:
        params["metric"] = "avg"
    reponse = requests.get(URL, params=params, timeout=120)
    reponse.raise_for_status()
    resultat = reponse.json()
    valeur = resultat["metric"][0]["value"] if mesure == "median" else resultat["metric"]
    return valeur, resultat["total"]


def table_consommation() -> pd.DataFrame:
    lignes = []
    for type_batiment in TYPES:
        for etiquette in ETIQUETTES:
            for energie in ENERGIES:
                filtre = (f'type_batiment:{type_batiment} AND etiquette_dpe:{etiquette} '
                          f'AND type_energie_principale_chauffage:"{energie}"')
                conso_chauffage, nb = agreger("conso_chauffage_ef", filtre)
                surface, _ = agreger("surface_habitable_logement", filtre)
                conso_ep_m2, _ = agreger("conso_5_usages_par_m2_ep", filtre)
                lignes.append({
                    "type_batiment": type_batiment, "etiquette": etiquette, "energie": energie,
                    "nb_dpe": nb,
                    # Ratio des médianes : consommation de chauffage (énergie finale) par m²
                    "conso_chauffage_ef_m2": conso_chauffage / surface if nb and surface else None,
                    "conso_totale_ep_m2": conso_ep_m2,
                })
            print(f"  consommation : {type_batiment} {etiquette}")
    return pd.DataFrame(lignes)


def table_deperditions() -> pd.DataFrame:
    """Parts des pertes de chaleur. Moyennes (et non médianes) : elles s'additionnent."""
    lignes = []
    for type_batiment in TYPES:
        for etiquette in ETIQUETTES:
            filtre = f"type_batiment:{type_batiment} AND etiquette_dpe:{etiquette}"
            total, nb = agreger("deperditions_enveloppe", filtre, "avg")
            ligne = {"type_batiment": type_batiment, "etiquette": etiquette, "nb_dpe": nb}
            for paroi, (colonne, _) in PAROIS.items():
                valeur, _ = agreger(colonne, filtre, "avg")
                ligne[f"part_{paroi}"] = valeur / total
            lignes.append(ligne)
        print(f"  déperditions : {type_batiment}")
    return pd.DataFrame(lignes)


def table_isolation() -> pd.DataFrame:
    """
    Baisse des pertes d'une paroi quand elle passe d'« insuffisante » à « très bonne »,
    mesurée sur les DPE : pertes de la paroi par m² habitable, médiane de chaque groupe.
    """
    lignes = []
    for type_batiment in TYPES:
        for paroi, (colonne, qualite) in PAROIS.items():
            pertes_m2 = {}
            for niveau in ["insuffisante", "très bonne"]:
                filtre = f'type_batiment:{type_batiment} AND {qualite}:"{niveau}"'
                pertes, nb = agreger(colonne, filtre)
                surface, _ = agreger("surface_habitable_logement", filtre)
                pertes_m2[niveau] = (pertes / surface, nb)
            lignes.append({
                "type_batiment": type_batiment, "paroi": paroi,
                "pertes_m2_insuffisante": pertes_m2["insuffisante"][0],
                "pertes_m2_tres_bonne": pertes_m2["très bonne"][0],
                "nb_dpe_insuffisante": pertes_m2["insuffisante"][1],
                "nb_dpe_tres_bonne": pertes_m2["très bonne"][1],
                "reduction_pertes": 1 - pertes_m2["très bonne"][0] / pertes_m2["insuffisante"][0],
            })
        print(f"  isolation : {type_batiment}")
    return pd.DataFrame(lignes)


def table_rendement() -> pd.DataFrame:
    """
    Rendement = besoin de chaleur / énergie consommée pour le chauffage (médianes).
    Calculé sur les maisons uniquement : pour les appartements, le besoin est souvent
    renseigné à l'échelle de l'immeuble et n'est pas exploitable.
    """
    lignes = []
    for energie in ENERGIES[:3]:  # pas de chaudière à remplacer pour le chauffage urbain
        filtre = f'type_batiment:maison AND type_energie_principale_chauffage:"{energie}"'
        besoin, nb = agreger("besoin_chauffage", filtre)
        conso, _ = agreger("conso_chauffage_ef", filtre)
        lignes.append({"energie": energie, "nb_dpe": nb, "rendement": besoin / conso})
    return pd.DataFrame(lignes)


if __name__ == "__main__":
    DOSSIER.mkdir(parents=True, exist_ok=True)
    for nom, fonction in [("reference_consommation", table_consommation),
                          ("reference_deperditions", table_deperditions),
                          ("reference_isolation", table_isolation),
                          ("reference_rendement", table_rendement)]:
        print(f"{nom}...")
        table = fonction()
        table.round(4).to_csv(DOSSIER / f"{nom}.csv", index=False, encoding="utf-8")
        print(table.round(3).to_string(index=False), "\n")
