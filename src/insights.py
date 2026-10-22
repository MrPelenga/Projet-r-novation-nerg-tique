"""
Phrases d'insight affichées sous chaque graphique.

Elles sont calculées à partir des résultats des requêtes, et non écrites en dur : dans
l'application, elles s'adaptent donc automatiquement aux filtres choisis.
"""

import pandas as pd

from graphiques import SEUILS_CONSO
from requetes import NOMS_DEPARTEMENTS


def _pct(valeur: float) -> str:
    """Format français : 11.4 → '11,4 %'."""
    return f"{valeur:.1f} %".replace(".", ",")


def _nombre(valeur: float) -> str:
    """Format français : 357140 → '357 140'."""
    return f"{valeur:,.0f}".replace(",", " ")


def etiquettes(df: pd.DataFrame) -> str:
    total = df["nb_dpe"].sum()
    nb_fg = df.loc[df["etiquette_dpe"].isin(["F", "G"]), "nb_dpe"].sum()
    if total == 0:
        return "Aucun DPE ne correspond aux filtres."
    principale = df.loc[df["nb_dpe"].idxmax()]
    return (f"{_pct(100 * nb_fg / total)} des logements diagnostiqués sont des passoires (F ou G), "
            f"soit {_nombre(nb_fg)} logements. L'étiquette la plus fréquente est "
            f"{principale['etiquette_dpe']} ({_pct(principale['pct'])}).")


def etiquettes_par_departement(df: pd.DataFrame) -> str:
    deps = df.groupby("code_departement").agg(
        pct=("pct_passoires_dep", "first"),
        nb_fg=("nb_dpe", lambda s: s[df.loc[s.index, "etiquette_dpe"].isin(["F", "G"])].sum()),
    )
    if len(deps) < 2:
        return "Sélectionnez au moins deux départements pour les comparer."
    haut, bas = deps["pct"].idxmax(), deps["pct"].idxmin()
    part_haut = 100 * deps.loc[haut, "nb_fg"] / deps["nb_fg"].sum()
    return (f"Département le plus touché : {NOMS_DEPARTEMENTS[haut]}, avec {_pct(deps.loc[haut, 'pct'])} "
            f"de passoires. Il concentre à lui seul {_pct(part_haut)} des passoires de la sélection. "
            f"Le moins touché : {NOMS_DEPARTEMENTS[bas]} ({_pct(deps.loc[bas, 'pct'])}).")


def passoires_par_periode(df: pd.DataFrame) -> str:
    avant_1975 = df["periode_construction"].isin(["avant 1948", "1948-1974"])
    part = df.loc[avant_1975, "part_du_total_passoires"].sum()
    avant_1948 = df.loc[df["periode_construction"] == "avant 1948", "pct_passoires"]
    recents = df[df["periode_construction"].isin(["1989-2000", "2001-2005", "2006-2012", "2013-2021", "après 2021"])]
    pct_recents = 100 * recents["nb_passoires"].sum() / max(recents["nb_dpe"].sum(), 1)
    phrase = f"Les logements construits avant 1975 représentent {_pct(part)} des passoires."
    if not avant_1948.empty:
        phrase += (f" Avant 1948, {_pct(avant_1948.iloc[0])} des logements sont F ou G, "
                   f"contre {_pct(pct_recents)} pour ceux construits après 1989.")
    return phrase + " La première réglementation thermique date de 1974 : c'est la vraie ligne de partage."


def passoires_par_chauffage(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    haut = df.loc[df["pct_passoires"].idxmax()]
    bas = df.loc[df["pct_passoires"].idxmin()]
    total_fg = df["nb_passoires"].sum()
    elec_gaz = df.loc[df["energie_chauffage_groupe"].isin(["Électricité", "Gaz"]), "nb_passoires"].sum()
    return (f"Taux le plus élevé : {haut['energie_chauffage_groupe'].lower()}, avec {_pct(haut['pct_passoires'])} "
            f"de passoires, contre {_pct(bas['pct_passoires'])} pour le {bas['energie_chauffage_groupe'].lower()}. "
            f"Mais en volume, l'électricité et le gaz regroupent {_pct(100 * elec_gaz / max(total_fg, 1))} des passoires.")


def passoires_par_type_logement(df: pd.DataFrame) -> str:
    valeurs = df.set_index("type_logement")["pct_passoires"]
    morceaux = []
    if "Maison" in valeurs:
        morceaux.append(f"Les maisons sont les plus touchées ({_pct(valeurs['Maison'])})")
    ind, col = "Appartement, chauffage individuel", "Appartement, chauffage collectif"
    if ind in valeurs and col in valeurs:
        morceaux.append(f"un appartement en chauffage individuel l'est presque deux fois plus souvent "
                        f"({_pct(valeurs[ind])}) qu'en chauffage collectif ({_pct(valeurs[col])})")
    return " ; ".join(morceaux) + "." if morceaux else ""


def passoires_par_surface(df: pd.DataFrame) -> str:
    petits = df[df["tranche_surface"].str[:1].isin(["1", "2", "3"])]
    if petits.empty:
        return ""
    moins_20 = df.loc[df["tranche_surface"].str.startswith("1."), "pct_passoires"]
    phrase = f"Les logements de moins de 50 m² représentent {_pct(petits['part_du_total_passoires'].sum())} des passoires."
    if not moins_20.empty:
        phrase += (f" Sous 20 m², {_pct(moins_20.iloc[0])} sont F ou G. Le calcul du DPE ramène l'eau chaude "
                   "au m² : il pénalise mécaniquement les petites surfaces, malgré une correction en 2024.")
    return phrase


def distribution_conso(df: pd.DataFrame) -> str:
    total = df["nb_dpe"].sum()
    if total == 0:
        return ""
    cumul = df["nb_dpe"].cumsum() / total
    mediane = df.loc[cumul >= 0.5, "tranche_debut"].iloc[0]
    au_dela_f = 100 * df.loc[df["tranche_debut"] >= 330, "nb_dpe"].sum() / total
    etiquette_mediane = next((e for e, s in SEUILS_CONSO.items() if mediane < s), "G")
    return (f"La consommation médiane se situe entre {mediane:.0f} et {mediane + 10:.0f} kWh/m²/an "
            f"(étiquette {etiquette_mediane}). {_pct(au_dela_f)} des logements dépassent 330 kWh/m²/an, "
            "le seuil de l'étiquette F.")


def evolution_trimestrielle(df: pd.DataFrame) -> str:
    # Phrase de contexte fixe (constat fait sur l'ensemble de l'IDF, voir docs/insights.md)
    return ("La part de passoires dépend de l'échantillon de logements diagnostiqués chaque trimestre. "
            "Elle a baissé de 2021 à 2024, puis remonte depuis 2025. En 2026, un tiers des DPE "
            "concernent des logements d'avant 1948, contre moins d'un quart en 2024. C'est probablement "
            "un effet du calendrier de la loi Climat (location des G interdite depuis 2025), et non une "
            "dégradation du parc.")
