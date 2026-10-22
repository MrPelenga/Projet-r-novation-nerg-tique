"""Page 2 — Carte interactive : part de passoires (F+G) par commune (arrondissements pour Paris)."""

import math

import pandas as pd
import pydeck as pdk
import streamlit as st

import graphiques
from donnees import contours, resultats
from filtres import barre_filtres, resume
from insights import _nombre, _pct

# En dessous de 30 DPE, un pourcentage n'est pas fiable : la commune est affichée en gris
SEUIL_FIABILITE = 30

# Classes de couleur : rampe séquentielle à une seule teinte (bleu clair → bleu foncé)
CLASSES = [
    (5, "moins de 5 %", "#cde2fb"),
    (10, "5 à 10 %", "#9ec5f4"),
    (15, "10 à 15 %", "#6da7ec"),
    (20, "15 à 20 %", "#3987e5"),
    (25, "20 à 25 %", "#256abf"),
    (35, "25 à 35 %", "#184f95"),
    (101, "35 % et plus", "#0d366b"),
]
GRIS = "#c3c2b7"


def hex_vers_rgb(couleur: str) -> list[int]:
    return [int(couleur[i:i + 2], 16) for i in (1, 3, 5)]


def couleur_commune(pct: float, nb_dpe: int) -> list[int]:
    if nb_dpe < SEUIL_FIABILITE:
        return hex_vers_rgb(GRIS) + [160]
    for borne, _, couleur in CLASSES:
        if pct < borne:
            return hex_vers_rgb(couleur) + [215]
    return hex_vers_rgb(CLASSES[-1][2]) + [215]


@st.cache_data
def preparer_geojson(communes: pd.DataFrame) -> dict:
    """Ajoute à chaque contour ses indicateurs (couleur, infobulle). Communes sans DPE : gris."""
    indicateurs = communes.set_index("code_insee")
    entites = []
    for entite in contours()["features"]:
        code = entite["properties"]["code_insee"]
        if code not in indicateurs.index:
            continue  # commune sans aucun DPE dans la sélection : non dessinée
        c = indicateurs.loc[code]
        repartition = " · ".join(f"{e} {c[f'pct_{e}']:.0f} %" for e in "ABCDEFG")
        fiable = c["nb_dpe"] >= SEUIL_FIABILITE
        entites.append({
            "type": "Feature",
            "geometry": entite["geometry"],
            "properties": {
                "code_insee": code,
                "nom_commune": c["nom_commune"],
                "couleur": couleur_commune(c["pct_passoires"], c["nb_dpe"]),
                # Texte brut : pydeck échappe le HTML contenu dans les propriétés
                "ligne_pct": (f"Passoires (F+G) : {_pct(c['pct_passoires'])}" if fiable
                              else f"Moins de {SEUIL_FIABILITE} DPE : pourcentage non fiable"),
                "ligne_nb": f"{_nombre(c['nb_dpe'])} DPE · conso moyenne {c['conso_moyenne_kwh_m2']:.0f} kWh/m²/an",
                "ligne_repartition": repartition,
            },
        })
    return {"type": "FeatureCollection", "features": entites}


def cadrage(geojson: dict, largeur_px: int = 650, hauteur_px: int = 560) -> pdk.ViewState:
    """
    Centre et zoom qui font tenir toutes les communes affichées dans la carte.
    Au zoom z, le monde entier mesure 512 × 2^z pixels de large : on en déduit le zoom
    pour que l'étendue (en longitude, et en latitude corrigée de la projection) tienne à l'écran.
    """
    lons, lats = [], []

    def parcourir(coordonnees):
        if isinstance(coordonnees[0], (int, float)):
            lons.append(coordonnees[0])
            lats.append(coordonnees[1])
        else:
            for c in coordonnees:
                parcourir(c)

    for entite in geojson["features"]:
        parcourir(entite["geometry"]["coordinates"])
    lat_centre = (min(lats) + max(lats)) / 2
    etendue_lon = max(max(lons) - min(lons), 0.01) * 1.15  # 15 % de marge
    etendue_lat = max(max(lats) - min(lats), 0.01) * 1.15 / math.cos(math.radians(lat_centre))
    zoom = min(math.log2(largeur_px * 360 / (512 * etendue_lon)),
               math.log2(hauteur_px * 360 / (512 * etendue_lat)))
    return pdk.ViewState(latitude=lat_centre, longitude=(min(lons) + max(lons)) / 2, zoom=min(zoom, 12))


def legende() -> str:
    """Légende HTML de la carte (une pastille + un libellé par classe)."""
    cases = "".join(
        f'<span style="display:inline-flex;align-items:center;margin:0 12px 4px 0;">'
        f'<span style="width:14px;height:14px;border-radius:3px;background:{couleur};margin-right:6px;"></span>'
        f"{libelle}</span>"
        for _, libelle, couleur in CLASSES
    )
    cases += (f'<span style="display:inline-flex;align-items:center;margin:0 12px 4px 0;">'
              f'<span style="width:14px;height:14px;border-radius:3px;background:{GRIS};margin-right:6px;"></span>'
              f"moins de {SEUIL_FIABILITE} DPE</span>")
    return f'<div style="font-size:14px;line-height:1.6;">{cases}</div>'


# --- Page ---------------------------------------------------------------------------------
filtres = barre_filtres()
communes = resultats(filtres)["09_passoires_par_commune"]

st.title("Où sont les passoires thermiques ?")
st.caption(resume(filtres))

if communes.empty:
    st.warning("Aucun DPE ne correspond à ces filtres.")
    st.stop()

colonne_carte, colonne_detail = st.columns([3, 1.3])

with colonne_carte:
    st.markdown("**Part de logements classés F ou G, par commune**"
                " (Paris : par arrondissement). Survolez une commune pour le détail, cliquez pour la sélectionner.")
    geojson = preparer_geojson(communes)
    couche = pdk.Layer(
        "GeoJsonLayer", data=geojson, id="communes",
        pickable=True, stroked=True, filled=True,
        get_fill_color="properties.couleur", get_line_color=[255, 255, 255, 200], line_width_min_pixels=0.5,
        auto_highlight=True, highlight_color=[235, 104, 52, 230],
    )
    carte = pdk.Deck(
        layers=[couche],
        initial_view_state=cadrage(geojson),
        map_style="light",
        tooltip={
            "html": "<b>{nom_commune}</b><br/>{ligne_pct}<br/>{ligne_nb}<br/>"
                    "<span style='font-size:12px'>{ligne_repartition}</span>",
            "style": {"backgroundColor": "white", "color": "#0b0b0b", "fontSize": "13px",
                      "border": "1px solid rgba(11,11,11,0.1)", "borderRadius": "6px"},
        },
    )
    evenement = st.pydeck_chart(carte, on_select="rerun", selection_mode="single-object",
                                key="carte_communes", height=560)
    st.markdown(legende(), unsafe_allow_html=True)

with colonne_detail:
    selection = evenement.selection.objects.get("communes", []) if evenement else []
    if selection:
        code = selection[0]["properties"]["code_insee"]
        c = communes.set_index("code_insee").loc[code]
        st.subheader(c["nom_commune"])
        st.metric("Passoires (F+G)", _pct(c["pct_passoires"]),
                  f"{_nombre(c['nb_passoires'])} logements", delta_color="off", delta_arrow="off")
        st.metric("DPE dans la sélection", _nombre(c["nb_dpe"]))
        st.metric("Consommation moyenne", f"{c['conso_moyenne_kwh_m2']:.0f} kWh/m²/an")
        repartition = pd.DataFrame({
            "etiquette_dpe": list("ABCDEFG"),
            "pct": [c[f"pct_{e}"] for e in "ABCDEFG"],
            "nb_dpe": [round(c[f"pct_{e}"] * c["nb_dpe"] / 100) for e in "ABCDEFG"],
        })
        fig = graphiques.etiquettes(repartition)
        fig.update_layout(title=None, height=260, margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        if c["nb_dpe"] < 30:
            st.caption("⚠️ Moins de 30 DPE : chiffres à interpréter avec prudence.")
    else:
        st.info("Cliquez sur une commune pour afficher sa répartition A → G.")

st.subheader("Classement des communes")
fiables = communes[communes["nb_dpe"] >= SEUIL_FIABILITE]
tri = st.radio("Trier par", ["Part de passoires", "Nombre de passoires"], horizontal=True)
colonne_tri = "pct_passoires" if tri == "Part de passoires" else "nb_passoires"
st.dataframe(
    fiables.sort_values(colonne_tri, ascending=False)[
        ["nom_commune", "code_departement", "nb_dpe", "nb_passoires", "pct_passoires", "conso_moyenne_kwh_m2"]
    ].head(50),
    hide_index=True, use_container_width=True,
    column_config={
        "nom_commune": "Commune", "code_departement": "Dépt",
        "nb_dpe": st.column_config.NumberColumn("DPE", format="localized"),
        "nb_passoires": st.column_config.NumberColumn("Passoires", format="localized"),
        "pct_passoires": st.column_config.ProgressColumn("% F+G", format="%.1f %%", min_value=0, max_value=100),
        "conso_moyenne_kwh_m2": st.column_config.NumberColumn("Conso moy. (kWh/m²/an)", format="%d"),
    },
)
st.caption(f"Communes avec au moins {SEUIL_FIABILITE} DPE dans la sélection ({len(fiables)} sur {len(communes)}). "
           "50 premières affichées.")
