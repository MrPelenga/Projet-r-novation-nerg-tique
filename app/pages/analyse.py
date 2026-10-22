"""Page 3 — Analyse : quels logements sont des passoires ? Graphiques + phrase d'insight."""

import streamlit as st

import graphiques
import insights
from donnees import resultats
from filtres import barre_filtres, resume
from requetes import DOSSIER_SQL


def bloc(df, fonction_graphique, fonction_insight, nom_requete: str, **arguments) -> None:
    """Un graphique, sa phrase d'insight, et (repliés) les chiffres et la requête SQL utilisée."""
    st.plotly_chart(fonction_graphique(df, **arguments), use_container_width=True,
                    config={"displaylogo": False})
    phrase = fonction_insight(df)
    if phrase:
        st.info(phrase, icon="💡")
    with st.expander("Voir les chiffres et la requête SQL"):
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.code(texte_sql(nom_requete), language="sql")


@st.cache_data
def texte_sql(nom_requete: str) -> str:
    return (DOSSIER_SQL / f"{nom_requete}.sql").read_text(encoding="utf-8")


filtres = barre_filtres()
donnees = resultats(filtres)
cles = donnees["01_chiffres_cles"].iloc[0]

st.title("Quels logements sont des passoires ?")
st.caption(resume(filtres))

if cles["nb_dpe"] == 0:
    st.warning("Aucun DPE ne correspond à ces filtres.")
    st.stop()

colonne_1, colonne_2, colonne_3 = st.columns(3)
colonne_1.metric("DPE dans la sélection", insights._nombre(cles["nb_dpe"]))
colonne_2.metric("Passoires (F ou G)", insights._pct(cles["pct_passoires"]),
                 f"{insights._nombre(cles['nb_passoires'])} logements", delta_color="off", delta_arrow="off")
colonne_3.metric("Consommation médiane", f"{cles['conso_mediane_kwh_m2']:.0f} kWh/m²/an")

onglet_1, onglet_2, onglet_3 = st.tabs(["Vue d'ensemble", "Profil des passoires", "Consommation et évolution"])

with onglet_1:
    bloc(donnees["02_etiquettes"], graphiques.etiquettes, insights.etiquettes, "02_etiquettes")
    bloc(donnees["03_etiquettes_par_departement"], graphiques.etiquettes_par_departement,
         insights.etiquettes_par_departement, "03_etiquettes_par_departement")

with onglet_2:
    bloc(donnees["04_passoires_par_periode"], graphiques.barres_pct_passoires, insights.passoires_par_periode,
         "04_passoires_par_periode", colonne="periode_construction",
         titre="Part de passoires selon la période de construction")
    gauche, droite = st.columns(2)
    with gauche:
        bloc(donnees["05_passoires_par_chauffage"], graphiques.barres_pct_passoires,
             insights.passoires_par_chauffage, "05_passoires_par_chauffage",
             colonne="energie_chauffage_groupe", titre="Selon l'énergie de chauffage",
             horizontal=True, ordre_donnees=False)
    with droite:
        bloc(donnees["06_passoires_par_type_logement"], graphiques.barres_pct_passoires,
             insights.passoires_par_type_logement, "06_passoires_par_type_logement",
             colonne="type_logement", titre="Selon le type de logement", horizontal=True, ordre_donnees=False)
    bloc(donnees["07_passoires_par_surface"], graphiques.barres_pct_passoires, insights.passoires_par_surface,
         "07_passoires_par_surface", colonne="tranche_surface", titre="Part de passoires selon la surface")

with onglet_3:
    bloc(donnees["08_distribution_conso"], graphiques.distribution_conso, insights.distribution_conso,
         "08_distribution_conso")
    bloc(donnees["10_evolution_trimestrielle"], graphiques.evolution_trimestrielle,
         insights.evolution_trimestrielle, "10_evolution_trimestrielle")
