"""Page 4 — Simulateur : économies et retour sur investissement d'une rénovation énergétique."""

import copy

import pandas as pd
import streamlit as st

import graphiques
from insights import _nombre
from simulateur import (
    ENERGIES, ENERGIES_REMPLACABLES_PAR_PAC, ETIQUETTES, GESTES_PAR_TYPE, Logement, References,
    SimulationImpossible, charger_hypotheses, quantite, simuler_gestes, simuler_saut,
)

LIBELLES_GESTES = {
    "murs_exterieur": "Isolation des murs par l'extérieur",
    "murs_interieur": "Isolation des murs par l'intérieur",
    "toiture": "Isolation des combles / de la toiture",
    "fenetres": "Remplacement des fenêtres",
    "plancher_bas": "Isolation du plancher bas",
    "pac": "Pompe à chaleur air/eau (remplace la chaudière)",
}


@st.cache_data
def hypotheses_par_defaut() -> dict:
    return charger_hypotheses()


@st.cache_resource
def references() -> References:
    return References.charger()


def euros(valeur: float) -> str:
    return f"{_nombre(valeur)} €"


def source(element: dict) -> str:
    """Infobulle : source de l'hypothèse, et avertissement si elle est à vérifier."""
    texte = element.get("source", "Hypothèse de modélisation, sans source publiée.")
    if element.get("remarque"):
        texte += f" — {element['remarque']}"
    if element.get("a_verifier"):
        texte += " ⚠️ À vérifier."
    return texte


def hypotheses_avancees() -> dict:
    """Section repliable : chaque hypothèse chiffrée peut être modifiée. Renvoie une copie modifiée."""
    h = copy.deepcopy(hypotheses_par_defaut())
    with st.expander("⚙️ Hypothèses avancées (prix de l'énergie, coûts des travaux…)"):
        st.caption("Valeurs par défaut issues de config/hypotheses.yaml. Survolez le « ? » pour voir la source. "
                   "⚠️ = valeur sans source officielle, à vérifier.")
        colonne_1, colonne_2, colonne_3 = st.columns(3)
        with colonne_1:
            st.markdown("**Prix de l'énergie (€/kWh)**")
            for energie in ENERGIES:
                prix = h["prix_energie"][energie]
                prix["valeur"] = st.number_input(energie + (" ⚠️" if prix.get("a_verifier") else ""),
                                                 value=float(prix["valeur"]), min_value=0.0, step=0.005,
                                                 format="%.4f", help=source(prix), key=f"prix_{energie}")
            evolution = h["evolution_prix_energie"]
            evolution["valeur"] = st.number_input("Hausse annuelle des prix (%/an) ⚠️",
                                                  value=float(evolution["valeur"]) * 100, step=0.5,
                                                  help=source(evolution), key="evolution") / 100
        with colonne_2:
            st.markdown("**Coûts des travaux (€ TTC, pose comprise)**")
            for geste, cout in h["couts_travaux"].items():
                cout["valeur"] = st.number_input(
                    f"{cout['libelle']} ({cout['unite']})" + (" ⚠️" if cout.get("a_verifier") else ""),
                    value=float(cout["valeur"]), min_value=0.0, step=5.0,
                    help=source(cout) + f" Fourchette : {cout['min']} à {cout['max']}.", key=f"cout_{geste}")
            pac = h["pompe_a_chaleur"]["cout"]
            pac["valeur"] = st.number_input("Pompe à chaleur air/eau (€)", value=float(pac["valeur"]),
                                            min_value=0.0, step=500.0, help=source(pac), key="cout_pac")
            ampleur = h["renovation_ampleur"]["cout_moyen"]
            ampleur["valeur"] = st.number_input("Rénovation d'ampleur, mode « étiquette visée » (€)",
                                                value=float(ampleur["valeur"]), min_value=0.0, step=1000.0,
                                                help=source(ampleur), key="cout_ampleur")
        with colonne_3:
            st.markdown("**Performance**")
            scop = h["pompe_a_chaleur"]["scop"]
            scop["valeur"] = st.number_input("Rendement saisonnier de la PAC (SCOP)", value=float(scop["valeur"]),
                                             min_value=1.0, max_value=6.0, step=0.1, help=source(scop), key="scop")
            st.markdown("**Durée affichée**")
            h["simulation"]["duree_annees"] = st.slider("Années", 10, 30, h["simulation"]["duree_annees"],
                                                        key="duree")
            st.caption("Les gains d'isolation et les consommations de référence sont calculés sur les DPE "
                       "franciliens (voir la méthodologie) : ils ne sont pas modifiables ici.")
    return h


# --- Page ---------------------------------------------------------------------------------
st.title("Simulateur de rénovation")
st.warning("**Estimation pédagogique** : ce simulateur ne remplace pas un audit énergétique réalisé "
           "par un professionnel. Les montants sont des ordres de grandeur.", icon="⚠️")

refs = references()
colonne_saisie, colonne_resultat = st.columns([1, 1.6], gap="large")

with colonne_saisie:
    st.subheader("1. Votre logement")
    type_batiment = st.radio("Type", ["maison", "appartement"], horizontal=True, format_func=str.capitalize)
    surface = st.number_input("Surface habitable (m²)", min_value=8, max_value=500,
                              value=100 if type_batiment == "maison" else 50, step=5)
    etiquette = st.select_slider("Étiquette DPE actuelle", options=ETIQUETTES, value="F")
    energie = st.selectbox("Énergie de chauffage", ENERGIES, index=1)
    logement = Logement(type_batiment, float(surface), etiquette, energie)

    st.subheader("2. Les travaux")
    mode = st.radio("Décrire les travaux…", ["par gestes", "par étiquette visée"], horizontal=True)
    quantites = {}
    if mode == "par gestes":
        possibles = [g for g in GESTES_PAR_TYPE[type_batiment]
                     if g != "pac" or energie in ENERGIES_REMPLACABLES_PAR_PAC]
        murs = st.radio("Murs", ["aucune", "par l'extérieur", "par l'intérieur"], horizontal=True)
        gestes = {"par l'extérieur": ["murs_exterieur"], "par l'intérieur": ["murs_interieur"]}.get(murs, [])
        for geste in possibles:
            if not geste.startswith("murs") and st.checkbox(LIBELLES_GESTES[geste], key=f"geste_{geste}"):
                gestes.append(geste)
        if type_batiment == "appartement":
            st.caption("En appartement, seuls les murs et les fenêtres sont proposés.")
        if energie not in ENERGIES_REMPLACABLES_PAR_PAC:
            st.caption("La pompe à chaleur est proposée en remplacement d'une chaudière gaz ou fioul.")
        hypotheses = hypotheses_par_defaut()
        if gestes:
            with st.expander("Ajuster les quantités (estimées d'après la surface)"):
                for geste in [g for g in gestes if g != "pac"]:
                    valeur, unite = quantite(geste, logement, hypotheses)
                    quantites[geste] = st.number_input(f"{LIBELLES_GESTES[geste]} ({unite})",
                                                       value=float(round(valeur)), min_value=0.0, step=1.0,
                                                       key=f"quantite_{geste}")
    else:
        meilleures = ETIQUETTES[:ETIQUETTES.index(etiquette)]
        cible = st.select_slider("Étiquette visée", options=meilleures or ["A"],
                                 value=meilleures[min(2, len(meilleures) - 1)] if meilleures else "A",
                                 disabled=not meilleures)
        st.caption("Coût : moyenne nationale d'une rénovation d'ampleur aidée par MaPrimeRénov' (Anah, 2025).")
    aides = st.number_input("Aides attendues (MaPrimeRénov', CEE…) en €", min_value=0, value=0, step=500,
                            help="Le montant dépend de vos revenus : à saisir vous-même (simulateur officiel : "
                                 "france-renov.gouv.fr).")

hypotheses = hypotheses_avancees()

with colonne_resultat:
    st.subheader("3. Résultat")
    try:
        if mode == "par gestes":
            resultat = simuler_gestes(logement, gestes, hypotheses, refs, aides=aides, quantites=quantites)
        else:
            resultat = simuler_saut(logement, cible, hypotheses, refs, aides=aides)
    except SimulationImpossible as erreur:
        st.info(str(erreur))
        st.stop()

    evolution = hypotheses["evolution_prix_energie"]["valeur"]
    retour = resultat.temps_retour(evolution)
    c1, c2, c3 = st.columns(3)
    c1.metric("Économie par an", euros(resultat.economie_annuelle),
              f"−{resultat.baisse_conso_pct:.0f} % de consommation de chauffage".replace(".", ","),
              delta_color="off", delta_arrow="off")
    c2.metric("Coût des travaux", euros(resultat.cout_net),
              f"avant aides : {euros(resultat.cout_travaux)}" if resultat.aides else None,
              delta_color="off", delta_arrow="off")
    c3.metric("Temps de retour", f"{retour:.1f} ans".replace(".", ",") if retour is not None else "—",
              help="Coût net ÷ économie annuelle (avec la hausse des prix choisie).")

    c4, c5, c6 = st.columns(3)
    c4.metric("Facture chauffage avant, par an", euros(resultat.facture_avant),
              f"{_nombre(resultat.conso_avant_kwh)} kWh/an ({resultat.energie_avant.lower()})",
              delta_color="off", delta_arrow="off")
    c5.metric("Facture chauffage après, par an", euros(resultat.facture_apres),
              f"{_nombre(resultat.conso_apres_kwh)} kWh/an ({resultat.energie_apres.lower()})",
              delta_color="off", delta_arrow="off")
    c6.metric("Étiquette", f"{resultat.etiquette_avant} → {resultat.etiquette_apres}",
              help="Estimée sur la consommation d'énergie primaire seule : le seuil d'émissions de CO₂ "
                   "du DPE n'est pas modélisé (il peut dégrader l'étiquette au fioul ou au gaz).")

    duree = hypotheses["simulation"]["duree_annees"]
    st.plotly_chart(graphiques.retour_investissement(resultat.economies_cumulees(duree, evolution),
                                                     resultat.cout_net, retour),
                    use_container_width=True, config={"displayModeBar": False})
    if retour is None or retour > duree:
        st.info(f"Avec ces hypothèses, les travaux ne sont pas remboursés en {duree} ans par les seules "
                "économies d'énergie. Le confort, la valeur du bien et le droit de louer comptent aussi.")

    if mode == "par gestes":
        detail = pd.DataFrame({
            "Geste": [LIBELLES_GESTES[g] for g in resultat.detail_couts],
            "Baisse du chauffage": [f"{100 * resultat.detail_gains.get(g, 0):.0f} %" for g in resultat.detail_couts],
            "Coût estimé": [euros(c) for c in resultat.detail_couts.values()],
        })
        st.dataframe(detail, hide_index=True, use_container_width=True)
        st.caption("Les baisses des gestes d'isolation s'additionnent. Celle de la pompe à chaleur "
                   "s'applique ensuite, sur la consommation restante.")

with st.expander("Comment sont faits ces calculs ?"):
    st.markdown(
        "- **Consommation avant** : consommation de chauffage médiane par m² des logements franciliens "
        "comparables (même type, même étiquette, même énergie) d'après les DPE de l'ADEME.\n"
        "- **Gain d'un geste d'isolation** : part de la paroi dans les pertes de chaleur des logements "
        "comparables × baisse des pertes de cette paroi observée entre les DPE « isolation insuffisante » "
        "et « très bonne isolation ».\n"
        "- **Pompe à chaleur** : la chaleur utile (consommation × rendement observé des chaudières) est "
        "produite avec SCOP fois moins d'électricité.\n"
        "- **Étiquette visée** : consommation médiane des logements comparables ayant déjà cette étiquette.\n"
        "- **Limites** : le DPE calcule une consommation *conventionnelle*. Les occupants de passoires "
        "chauffent souvent moins que ce que prévoit le DPE, et les économies réelles peuvent donc être plus "
        "faibles. Les abonnements, l'entretien et les aides ne sont pas modélisés (aides : à saisir)."
    )
