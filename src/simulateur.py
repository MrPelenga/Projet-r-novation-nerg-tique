"""
Phase 5 — Logique de calcul du simulateur de rénovation (indépendante de Streamlit,
donc testable : voir tests/test_simulateur.py).

Principe, pour un logement (type, surface, étiquette, énergie de chauffage) :

1. Consommation de chauffage AVANT : celle des logements franciliens comparables
   (même type, même étiquette, même énergie), d'après les DPE (reference_consommation.csv).
2. Deux façons de décrire les travaux :
   - par GESTES (murs, toiture, fenêtres, plancher bas, pompe à chaleur) :
     chaque paroi isolée réduit le chauffage de « part de la paroi dans les pertes de
     chaleur » × « baisse des pertes de cette paroi quand elle est très bien isolée »,
     deux valeurs mesurées sur les DPE (reference_deperditions.csv, reference_isolation.csv) ;
   - par SAUT D'ÉTIQUETTE : la consommation après travaux est celle des logements
     comparables ayant l'étiquette visée.
3. Facture = consommation × prix de l'énergie ; économie = facture avant − facture après ;
   temps de retour = coût net des travaux ÷ économie annuelle.

Estimation pédagogique : elle ne remplace pas un audit énergétique.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

RACINE = Path(__file__).resolve().parents[1]
FICHIER_HYPOTHESES = RACINE / "config" / "hypotheses.yaml"
DOSSIER_REFERENCES = RACINE / "data" / "processed"

ETIQUETTES = list("ABCDEFG")
ENERGIES = ["Électricité", "Gaz naturel", "Fioul domestique", "Réseau de Chauffage urbain"]

# Gestes possibles : identifiant → paroi isolée (None pour la pompe à chaleur)
GESTES = {
    "murs_exterieur": "murs",
    "murs_interieur": "murs",
    "toiture": "toiture",
    "fenetres": "fenetres",
    "plancher_bas": "plancher_bas",
    "pac": None,
}
# Toiture et plancher bas : seulement pour les maisons (dans un appartement, ils ne concernent
# que le dernier étage ou le rez-de-chaussée, et les DPE ne permettent pas de les mesurer).
GESTES_PAR_TYPE = {
    "maison": list(GESTES),
    "appartement": ["murs_exterieur", "murs_interieur", "fenetres"],
}
# La pompe à chaleur air/eau remplace une chaudière gaz ou fioul
ENERGIES_REMPLACABLES_PAR_PAC = ["Gaz naturel", "Fioul domestique"]


class SimulationImpossible(ValueError):
    """Combinaison de saisies que le simulateur ne sait pas traiter (message affichable)."""


# --- Chargement des données -------------------------------------------------------------

def charger_hypotheses(chemin: Path = FICHIER_HYPOTHESES) -> dict:
    with open(chemin, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class References:
    """Valeurs de référence calculées sur les DPE franciliens (src/references_simulateur.py)."""
    consommation: pd.DataFrame
    deperditions: pd.DataFrame
    isolation: pd.DataFrame
    rendement: pd.DataFrame

    @classmethod
    def charger(cls, dossier: Path = DOSSIER_REFERENCES) -> "References":
        lire = lambda nom: pd.read_csv(dossier / f"reference_{nom}.csv")
        return cls(lire("consommation"), lire("deperditions"), lire("isolation"), lire("rendement"))


# --- Entrées et résultats ---------------------------------------------------------------

@dataclass
class Logement:
    type_batiment: str      # "maison" ou "appartement"
    surface_m2: float
    etiquette: str          # "A" à "G"
    energie: str            # une des ENERGIES

    def verifier(self) -> None:
        if self.type_batiment not in GESTES_PAR_TYPE:
            raise SimulationImpossible(f"Type de logement inconnu : {self.type_batiment}")
        if not 8 <= self.surface_m2 <= 500:
            raise SimulationImpossible("La surface doit être comprise entre 8 et 500 m².")
        if self.etiquette not in ETIQUETTES:
            raise SimulationImpossible(f"Étiquette inconnue : {self.etiquette}")
        if self.energie not in ENERGIES:
            raise SimulationImpossible(f"Énergie non prise en charge : {self.energie}")


@dataclass
class Resultat:
    conso_avant_kwh: float          # chauffage, énergie finale, par an
    conso_apres_kwh: float
    energie_avant: str
    energie_apres: str
    facture_avant: float            # € par an (chauffage seul, hors abonnement)
    facture_apres: float
    cout_travaux: float             # € TTC
    aides: float                    # € saisis par l'utilisateur
    etiquette_avant: str
    etiquette_apres: str            # estimée sur la seule consommation d'énergie primaire
    detail_couts: dict = field(default_factory=dict)
    detail_gains: dict = field(default_factory=dict)   # geste → % de baisse du chauffage

    @property
    def economie_annuelle(self) -> float:
        return self.facture_avant - self.facture_apres

    @property
    def cout_net(self) -> float:
        return max(self.cout_travaux - self.aides, 0.0)

    @property
    def baisse_conso_pct(self) -> float:
        return 100 * (1 - self.conso_apres_kwh / self.conso_avant_kwh)

    def temps_retour(self, evolution_prix: float = 0.0, horizon: int = 100) -> float | None:
        """
        Nombre d'années pour que les économies cumulées remboursent le coût net.
        Avec des prix constants, c'est simplement coût net ÷ économie annuelle.
        None si les travaux ne font pas économiser (ou pas avant `horizon` années).
        """
        if self.economie_annuelle <= 0:
            return None
        if evolution_prix == 0:
            return self.cout_net / self.economie_annuelle
        cumul = 0.0
        for annee in range(1, horizon + 1):
            economie = self.economie_annuelle * (1 + evolution_prix) ** (annee - 1)
            if cumul + economie >= self.cout_net:
                # Interpolation dans l'année où le seuil est franchi
                return annee - 1 + (self.cout_net - cumul) / economie
            cumul += economie
        return None

    def economies_cumulees(self, duree: int, evolution_prix: float = 0.0) -> list[float]:
        """Économies cumulées à la fin de chaque année, de l'année 0 (0 €) à `duree`."""
        cumul, serie = 0.0, [0.0]
        for annee in range(1, duree + 1):
            cumul += self.economie_annuelle * (1 + evolution_prix) ** (annee - 1)
            serie.append(cumul)
        return serie


# --- Briques de calcul ------------------------------------------------------------------

def prix_kwh(energie: str, hypotheses: dict) -> float:
    return hypotheses["prix_energie"][energie]["valeur"]


def reference_consommation(refs: References, hypotheses: dict, type_batiment: str,
                           etiquette: str, energie: str) -> pd.Series:
    """Ligne de référence pour un groupe de logements ; erreur si trop peu de DPE comparables."""
    ligne = refs.consommation[(refs.consommation["type_batiment"] == type_batiment)
                              & (refs.consommation["etiquette"] == etiquette)
                              & (refs.consommation["energie"] == energie)]
    minimum = hypotheses["simulation"]["nb_dpe_minimum_reference"]
    if ligne.empty or ligne.iloc[0]["nb_dpe"] < minimum:
        nb = 0 if ligne.empty else int(ligne.iloc[0]["nb_dpe"])
        raise SimulationImpossible(
            f"Trop peu de DPE de référence en Île-de-France ({nb}) pour un(e) {type_batiment} "
            f"classé(e) {etiquette} chauffé(e) à : {energie.lower()}. Minimum requis : {minimum}.")
    return ligne.iloc[0]


def etiquette_depuis_ep(conso_ep_m2: float, hypotheses: dict) -> str:
    """Étiquette correspondant à une consommation d'énergie primaire (seuils énergie seuls)."""
    for etiquette, seuil in hypotheses["seuils_etiquettes_ep"]["valeurs"].items():
        if conso_ep_m2 < seuil:
            return etiquette
    return "G"


def gain_isolation(refs: References, type_batiment: str, etiquette: str, paroi: str) -> float:
    """Part de la consommation de chauffage économisée en isolant une paroi (entre 0 et 1)."""
    parts = refs.deperditions[(refs.deperditions["type_batiment"] == type_batiment)
                              & (refs.deperditions["etiquette"] == etiquette)].iloc[0]
    reduction = refs.isolation[(refs.isolation["type_batiment"] == type_batiment)
                               & (refs.isolation["paroi"] == paroi)].iloc[0]["reduction_pertes"]
    return parts[f"part_{paroi}"] * reduction


def quantite(geste: str, logement: Logement, hypotheses: dict) -> tuple[float, str]:
    """Quantité de travaux déduite de la surface habitable (hypothèses de géométrie simplifiée)."""
    q = hypotheses["quantites"]
    s, t = logement.surface_m2, logement.type_batiment
    if geste in ("murs_exterieur", "murs_interieur"):
        return s * q["murs_m2_par_m2_habitable"][t], "m² de mur"
    if geste == "toiture":
        return s * q["toiture_m2_par_m2_habitable"][t], "m² de combles"
    if geste == "plancher_bas":
        return s * q["plancher_bas_m2_par_m2_habitable"][t], "m² de plancher"
    if geste == "fenetres":
        return max(1, round(s / q["m2_habitables_par_fenetre"]["valeur"])), "fenêtres"
    return 1, "installation"


# --- Les deux modes de simulation -------------------------------------------------------

def simuler_gestes(logement: Logement, gestes: list[str], hypotheses: dict, refs: References,
                   aides: float = 0.0, quantites: dict | None = None) -> Resultat:
    """
    Simulation par gestes de travaux. `quantites` permet de remplacer les quantités
    estimées (ex. {"fenetres": 8}).
    """
    logement.verifier()
    if not gestes:
        raise SimulationImpossible("Choisissez au moins un geste de travaux.")
    interdits = [g for g in gestes if g not in GESTES_PAR_TYPE[logement.type_batiment]]
    if interdits:
        raise SimulationImpossible(f"Geste(s) non proposé(s) pour un(e) {logement.type_batiment} : "
                                   f"{', '.join(interdits)}.")
    if "murs_exterieur" in gestes and "murs_interieur" in gestes:
        raise SimulationImpossible("Choisissez l'isolation des murs par l'intérieur OU par l'extérieur.")
    if "pac" in gestes and logement.energie not in ENERGIES_REMPLACABLES_PAR_PAC:
        raise SimulationImpossible("La pompe à chaleur est proposée en remplacement d'une chaudière gaz ou fioul.")

    ref = reference_consommation(refs, hypotheses, logement.type_batiment, logement.etiquette, logement.energie)
    conso_avant = ref["conso_chauffage_ef_m2"] * logement.surface_m2

    # 1. Isolation : les gains des différentes parois s'additionnent (pertes de chaleur additives)
    detail_gains = {}
    for geste in gestes:
        paroi = GESTES[geste]
        if paroi:
            detail_gains[geste] = gain_isolation(refs, logement.type_batiment, logement.etiquette, paroi)
    baisse_isolation = min(sum(detail_gains.values()), 0.9)  # garde-fou : jamais plus de 90 %
    conso_apres = conso_avant * (1 - baisse_isolation)
    energie_apres = logement.energie

    # 2. Pompe à chaleur : la chaleur utile (consommation × rendement de la chaudière)
    #    est produite avec SCOP fois moins d'électricité
    if "pac" in gestes:
        rendement = refs.rendement.set_index("energie").loc[logement.energie, "rendement"]
        conso_sans_pac = conso_apres
        conso_apres = conso_apres * rendement / hypotheses["pompe_a_chaleur"]["scop"]["valeur"]
        energie_apres = "Électricité"
        detail_gains["pac"] = 1 - conso_apres / conso_sans_pac  # baisse en kWh consommés

    # 3. Coûts des travaux
    quantites = quantites or {}
    detail_couts = {}
    for geste in gestes:
        if geste == "pac":
            detail_couts[geste] = hypotheses["pompe_a_chaleur"]["cout"]["valeur"]
        else:
            nombre = quantites.get(geste, quantite(geste, logement, hypotheses)[0])
            detail_couts[geste] = nombre * hypotheses["couts_travaux"][geste]["valeur"]

    # 4. Étiquette estimée : on retire le chauffage économisé de l'énergie primaire totale
    coef = hypotheses["coefficients_energie_primaire"]["valeurs"]
    ep_apres_m2 = (ref["conso_totale_ep_m2"]
                   - ref["conso_chauffage_ef_m2"] * coef[logement.energie]
                   + conso_apres / logement.surface_m2 * coef[energie_apres])

    return Resultat(
        conso_avant_kwh=conso_avant, conso_apres_kwh=conso_apres,
        energie_avant=logement.energie, energie_apres=energie_apres,
        facture_avant=conso_avant * prix_kwh(logement.energie, hypotheses),
        facture_apres=conso_apres * prix_kwh(energie_apres, hypotheses),
        cout_travaux=sum(detail_couts.values()), aides=aides,
        etiquette_avant=logement.etiquette, etiquette_apres=etiquette_depuis_ep(ep_apres_m2, hypotheses),
        detail_couts=detail_couts, detail_gains=detail_gains,
    )


def simuler_saut(logement: Logement, etiquette_cible: str, hypotheses: dict, refs: References,
                 aides: float = 0.0) -> Resultat:
    """Simulation par saut d'étiquette : consommation des logements comparables déjà à l'étiquette visée."""
    logement.verifier()
    if etiquette_cible not in ETIQUETTES or etiquette_cible >= logement.etiquette:
        raise SimulationImpossible("L'étiquette visée doit être meilleure que l'étiquette actuelle.")

    avant = reference_consommation(refs, hypotheses, logement.type_batiment, logement.etiquette, logement.energie)
    apres = reference_consommation(refs, hypotheses, logement.type_batiment, etiquette_cible, logement.energie)
    conso_avant = avant["conso_chauffage_ef_m2"] * logement.surface_m2
    conso_apres = apres["conso_chauffage_ef_m2"] * logement.surface_m2
    prix = prix_kwh(logement.energie, hypotheses)
    cout = hypotheses["renovation_ampleur"]["cout_moyen"]["valeur"]

    return Resultat(
        conso_avant_kwh=conso_avant, conso_apres_kwh=conso_apres,
        energie_avant=logement.energie, energie_apres=logement.energie,
        facture_avant=conso_avant * prix, facture_apres=conso_apres * prix,
        cout_travaux=cout, aides=aides,
        etiquette_avant=logement.etiquette, etiquette_apres=etiquette_cible,
        detail_couts={"renovation_ampleur": cout},
    )
