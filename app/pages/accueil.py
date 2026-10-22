"""Page 1 — Accueil : contexte, question business et chiffres clés (Île-de-France entière)."""

import streamlit as st

from donnees import date_extraction, resultats
from insights import _nombre, _pct
from requetes import NOMS_DEPARTEMENTS

# Chiffres clés calculés sans filtre : c'est la photo de toute l'Île-de-France
donnees = resultats(filtres=())
cles = donnees["01_chiffres_cles"].iloc[0]
departements = donnees["03_etiquettes_par_departement"].drop_duplicates("code_departement")
plus_touche = departements.loc[departements["pct_passoires_dep"].idxmax()]

st.title("Passoires thermiques en Île-de-France")
st.markdown(
    "La loi Climat et Résilience interdit progressivement de louer les logements les moins "
    "performants : **G depuis 2025, F en 2028, E en 2034**. Combien de logements sont concernés en "
    "Île-de-France, où se trouvent-ils, et une rénovation est-elle rentable pour leur propriétaire ?"
)
st.markdown(
    "Cette application analyse les **diagnostics de performance énergétique (DPE)** publiés par "
    "l'ADEME, réalisés depuis juillet 2021 sur les logements existants de la région."
)

colonne_1, colonne_2, colonne_3 = st.columns(3)
colonne_1.metric("DPE analysés", _nombre(cles["nb_dpe"]),
                 help="Logements uniques après nettoyage (voir la méthodologie).")
colonne_2.metric("Passoires thermiques (F ou G)", _pct(cles["pct_passoires"]),
                 help=f"Soit {_nombre(cles['nb_passoires'])} logements.")
colonne_3.metric("Département le plus touché", NOMS_DEPARTEMENTS[plus_touche["code_departement"]],
                 f"{_pct(plus_touche['pct_passoires_dep'])} de passoires", delta_color="off", delta_arrow="off")

st.subheader("Calendrier de la loi Climat et Résilience")
st.markdown(
    "| Depuis le | Logements interdits à la location |\n"
    "|---|---|\n"
    "| 1er janvier 2025 | Étiquette G |\n"
    "| 1er janvier 2028 | Étiquettes F et G |\n"
    "| 1er janvier 2034 | Étiquettes E, F et G |"
)

st.subheader("Dans cette application")
st.page_link("pages/carte.py", label="**Carte** : la part de passoires commune par commune", icon="🗺️")
st.page_link("pages/analyse.py", label="**Analyse** : quels logements sont les plus concernés ?", icon="📊")
st.page_link("pages/simulateur.py", label="**Simulateur** : combien coûte et rapporte une rénovation ?", icon="🧮")

st.caption(f"Source : ADEME, DPE logements existants (données extraites le {date_extraction()}).")
