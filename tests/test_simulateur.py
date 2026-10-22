"""
Tests du simulateur (lancer depuis la racine du projet : python -m pytest).

Les tests vérifient la logique de calcul (formules, cas limites, erreurs) sur les vraies
hypothèses (config/hypotheses.yaml) et les vraies références DPE (data/processed/).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from simulateur import (  # noqa: E402
    Logement, References, Resultat, SimulationImpossible, charger_hypotheses,
    etiquette_depuis_ep, gain_isolation, quantite, simuler_gestes, simuler_saut,
)


@pytest.fixture(scope="module")
def hypotheses():
    return charger_hypotheses()


@pytest.fixture(scope="module")
def refs():
    return References.charger()


@pytest.fixture
def maison_gaz_f():
    return Logement(type_batiment="maison", surface_m2=100, etiquette="F", energie="Gaz naturel")


def resultat_simple(economie: float, cout: float, aides: float = 0.0) -> Resultat:
    """Résultat construit à la main pour tester les calculs financiers isolément."""
    return Resultat(conso_avant_kwh=10_000, conso_apres_kwh=5_000, energie_avant="Gaz naturel",
                    energie_apres="Gaz naturel", facture_avant=economie + 500, facture_apres=500,
                    cout_travaux=cout, aides=aides, etiquette_avant="F", etiquette_apres="D")


# --- Calculs financiers -----------------------------------------------------------------

def test_temps_retour_prix_constants():
    assert resultat_simple(economie=1_000, cout=10_000).temps_retour() == pytest.approx(10)


def test_les_aides_reduisent_le_temps_de_retour():
    assert resultat_simple(economie=1_000, cout=10_000, aides=4_000).temps_retour() == pytest.approx(6)


def test_aides_superieures_au_cout_donnent_un_cout_net_nul():
    resultat = resultat_simple(economie=1_000, cout=5_000, aides=8_000)
    assert resultat.cout_net == 0
    assert resultat.temps_retour() == 0


def test_pas_de_temps_de_retour_sans_economie():
    assert resultat_simple(economie=0, cout=10_000).temps_retour() is None


def test_hausse_des_prix_raccourcit_le_temps_de_retour():
    resultat = resultat_simple(economie=1_000, cout=10_000)
    assert resultat.temps_retour(evolution_prix=0.03) < resultat.temps_retour()


def test_economies_cumulees():
    serie = resultat_simple(economie=1_000, cout=10_000).economies_cumulees(duree=20)
    assert len(serie) == 21  # de l'année 0 à l'année 20
    assert serie[0] == 0 and serie[20] == pytest.approx(20_000)


def test_temps_de_retour_coherent_avec_la_courbe_des_economies():
    resultat = resultat_simple(economie=1_000, cout=10_000)
    retour = resultat.temps_retour(evolution_prix=0.05)
    serie = resultat.economies_cumulees(duree=20, evolution_prix=0.05)
    assert serie[int(retour)] < resultat.cout_net <= serie[int(retour) + 1]


# --- Étiquettes -------------------------------------------------------------------------

@pytest.mark.parametrize("conso_ep, attendu", [(50, "A"), (70, "B"), (179.9, "C"), (330, "F"), (421, "G")])
def test_etiquette_depuis_ep(hypotheses, conso_ep, attendu):
    assert etiquette_depuis_ep(conso_ep, hypotheses) == attendu


# --- Simulation par gestes --------------------------------------------------------------

def test_isolation_des_murs(hypotheses, refs, maison_gaz_f):
    resultat = simuler_gestes(maison_gaz_f, ["murs_exterieur"], hypotheses, refs)
    gain = gain_isolation(refs, "maison", "F", "murs")
    assert 0 < gain < 1
    assert resultat.conso_apres_kwh == pytest.approx(resultat.conso_avant_kwh * (1 - gain))
    assert resultat.energie_apres == "Gaz naturel"
    # Coût = surface de murs estimée × prix au m²
    surface_murs, _ = quantite("murs_exterieur", maison_gaz_f, hypotheses)
    assert resultat.cout_travaux == pytest.approx(surface_murs * hypotheses["couts_travaux"]["murs_exterieur"]["valeur"])
    assert resultat.economie_annuelle == pytest.approx(
        (resultat.conso_avant_kwh - resultat.conso_apres_kwh) * hypotheses["prix_energie"]["Gaz naturel"]["valeur"])


def test_les_gains_des_parois_s_additionnent(hypotheses, refs, maison_gaz_f):
    murs = simuler_gestes(maison_gaz_f, ["murs_exterieur"], hypotheses, refs)
    toiture = simuler_gestes(maison_gaz_f, ["toiture"], hypotheses, refs)
    les_deux = simuler_gestes(maison_gaz_f, ["murs_exterieur", "toiture"], hypotheses, refs)
    economie_separee = (murs.conso_avant_kwh - murs.conso_apres_kwh) + (toiture.conso_avant_kwh - toiture.conso_apres_kwh)
    assert les_deux.conso_avant_kwh - les_deux.conso_apres_kwh == pytest.approx(economie_separee)
    assert les_deux.cout_travaux == pytest.approx(murs.cout_travaux + toiture.cout_travaux)


def test_plus_de_travaux_meilleure_etiquette(hypotheses, refs, maison_gaz_f):
    resultat = simuler_gestes(maison_gaz_f, ["murs_exterieur", "toiture", "fenetres", "plancher_bas", "pac"],
                              hypotheses, refs)
    assert resultat.etiquette_apres < "F"
    assert resultat.baisse_conso_pct > 50


def test_pompe_a_chaleur(hypotheses, refs, maison_gaz_f):
    resultat = simuler_gestes(maison_gaz_f, ["pac"], hypotheses, refs)
    assert resultat.energie_apres == "Électricité"
    assert resultat.conso_apres_kwh < resultat.conso_avant_kwh / 2  # SCOP 2,9 et rendement chaudière < 1
    assert resultat.cout_travaux == hypotheses["pompe_a_chaleur"]["cout"]["valeur"]


def test_quantites_saisies_remplacent_les_estimations(hypotheses, refs, maison_gaz_f):
    resultat = simuler_gestes(maison_gaz_f, ["fenetres"], hypotheses, refs, quantites={"fenetres": 3})
    assert resultat.cout_travaux == pytest.approx(3 * hypotheses["couts_travaux"]["fenetres"]["valeur"])


def test_les_hypotheses_modifiees_sont_prises_en_compte(hypotheses, refs, maison_gaz_f):
    import copy
    modifiees = copy.deepcopy(hypotheses)
    modifiees["prix_energie"]["Gaz naturel"]["valeur"] *= 2
    normal = simuler_gestes(maison_gaz_f, ["murs_exterieur"], hypotheses, refs)
    double = simuler_gestes(maison_gaz_f, ["murs_exterieur"], modifiees, refs)
    assert double.economie_annuelle == pytest.approx(2 * normal.economie_annuelle)


# --- Saisies refusées -------------------------------------------------------------------

@pytest.mark.parametrize("logement, gestes", [
    (Logement("appartement", 50, "F", "Gaz naturel"), ["toiture"]),           # pas de toiture en appartement
    (Logement("maison", 100, "F", "Électricité"), ["pac"]),                   # PAC : gaz ou fioul seulement
    (Logement("maison", 100, "F", "Gaz naturel"), ["murs_exterieur", "murs_interieur"]),
    (Logement("maison", 100, "F", "Gaz naturel"), []),
    (Logement("maison", 3, "F", "Gaz naturel"), ["fenetres"]),                # surface invalide
    (Logement("maison", 100, "A", "Fioul domestique"), ["fenetres"]),         # aucun DPE de référence
])
def test_saisies_refusees(hypotheses, refs, logement, gestes):
    with pytest.raises(SimulationImpossible):
        simuler_gestes(logement, gestes, hypotheses, refs)


# --- Simulation par saut d'étiquette ----------------------------------------------------

def test_saut_d_etiquette(hypotheses, refs, maison_gaz_f):
    resultat = simuler_saut(maison_gaz_f, "C", hypotheses, refs)
    assert resultat.etiquette_apres == "C"
    assert resultat.conso_apres_kwh < resultat.conso_avant_kwh
    assert resultat.cout_travaux == hypotheses["renovation_ampleur"]["cout_moyen"]["valeur"]


def test_un_saut_plus_grand_economise_plus(hypotheses, refs, maison_gaz_f):
    vers_d = simuler_saut(maison_gaz_f, "D", hypotheses, refs)
    vers_b = simuler_saut(maison_gaz_f, "B", hypotheses, refs)
    assert vers_b.economie_annuelle > vers_d.economie_annuelle


@pytest.mark.parametrize("cible", ["F", "G", "Z"])
def test_saut_vers_une_etiquette_non_meilleure_refuse(hypotheses, refs, maison_gaz_f, cible):
    with pytest.raises(SimulationImpossible):
        simuler_saut(maison_gaz_f, cible, hypotheses, refs)


# --- Le fichier d'hypothèses lui-même ---------------------------------------------------

def test_chaque_prix_d_energie_est_source(hypotheses):
    for energie, prix in hypotheses["prix_energie"].items():
        assert prix.get("source"), f"Prix sans source : {energie}"
        assert 0 < prix["valeur"] < 1, f"Prix incohérent (€/kWh) : {energie}"


def test_chaque_cout_est_source_ou_signale(hypotheses):
    for geste, cout in hypotheses["couts_travaux"].items():
        assert cout.get("source") or cout.get("a_verifier"), f"Coût sans source ni signalement : {geste}"
        assert cout["min"] <= cout["valeur"] <= cout["max"]
