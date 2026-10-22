"""
Point d'entrée de l'application Streamlit.

Lancement (depuis la racine du projet) : streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

import streamlit as st

# Les modules du dossier src/ (requêtes, graphiques, insights) sont partagés avec l'analyse
RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))
sys.path.insert(0, str(RACINE / "app"))

st.set_page_config(page_title="Passoires thermiques en Île-de-France", page_icon="🏠", layout="wide")

DOSSIER_PAGES = Path(__file__).parent / "pages"
pages = [
    st.Page(DOSSIER_PAGES / "accueil.py", title="Accueil", icon="🏠", default=True),
    st.Page(DOSSIER_PAGES / "carte.py", title="Carte", icon="🗺️"),
    st.Page(DOSSIER_PAGES / "analyse.py", title="Analyse", icon="📊"),
    st.Page(DOSSIER_PAGES / "simulateur.py", title="Simulateur", icon="🧮"),
    st.Page(DOSSIER_PAGES / "methodologie.py", title="Méthodologie", icon="📖"),
]
st.navigation(pages).run()
