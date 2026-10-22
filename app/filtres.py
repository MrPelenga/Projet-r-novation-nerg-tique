"""
Filtres partagés entre les pages Carte et Analyse (barre latérale).

Streamlit efface l'état d'un widget quand on change de page. Pour que les filtres
choisis sur la Carte soient conservés sur l'Analyse, on recopie leur valeur dans une
clé « permanente » de st.session_state (préfixe `garde_`).
"""

import streamlit as st

from donnees import valeurs_possibles
from requetes import NOMS_DEPARTEMENTS

LIBELLES = {
    "departements": "Département",
    "types_logement": "Type de logement",
    "periodes": "Période de construction",
    "energies": "Énergie de chauffage",
}


def _memoriser(nom: str) -> None:
    st.session_state[f"garde_{nom}"] = st.session_state[f"filtre_{nom}"]


def barre_filtres() -> tuple:
    """Affiche les filtres dans la barre latérale et renvoie la sélection (format attendu par le cache)."""
    options = valeurs_possibles()
    st.sidebar.header("Filtres")
    st.sidebar.caption("Aucune sélection = tout est inclus.")
    selection = []
    for nom, libelle in LIBELLES.items():
        if f"garde_{nom}" in st.session_state:
            st.session_state[f"filtre_{nom}"] = st.session_state[f"garde_{nom}"]
        valeurs = st.sidebar.multiselect(
            libelle, options[nom], key=f"filtre_{nom}", on_change=_memoriser, args=(nom,),
            format_func=(lambda c: f"{NOMS_DEPARTEMENTS[c]} ({c})") if nom == "departements" else str,
            placeholder="Tous",
        )
        selection.append((nom, tuple(valeurs)))
    if st.sidebar.button("Réinitialiser les filtres", use_container_width=True):
        for nom in LIBELLES:
            st.session_state.pop(f"garde_{nom}", None)
            st.session_state[f"filtre_{nom}"] = []
        st.rerun()
    return tuple(selection)


def resume(filtres: tuple) -> str:
    """Phrase courte décrivant la sélection active (affichée en haut des pages)."""
    def libelle(nom: str, valeur: str) -> str:
        return NOMS_DEPARTEMENTS[valeur] if nom == "departements" else valeur

    actifs = [f"{LIBELLES[nom].lower()} : {', '.join(libelle(nom, v) for v in valeurs)}"
              for nom, valeurs in filtres if valeurs]
    return "Sélection : " + " · ".join(actifs) if actifs else "Sélection : tous les logements d'Île-de-France"
