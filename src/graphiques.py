"""
Graphiques Plotly du projet. Chaque fonction prend le DataFrame renvoyé par une requête
de sql/analyse/ et renvoie une figure. Les mêmes fonctions servent au rapport d'analyse
(phase 3) et à l'application Streamlit (phase 4).

Choix de couleurs :
- étiquettes A → G : les couleurs officielles du DPE, connues de tous. Elles sont peu
  contrastées (le jaune D surtout) : la lettre est donc toujours écrite à côté de la couleur ;
- tous les autres graphiques n'ont qu'une série : une seule couleur (bleu), pas d'arc-en-ciel.
"""

import pandas as pd
import plotly.graph_objects as go

from requetes import NOMS_DEPARTEMENTS

COULEURS_DPE = {
    "A": "#009C6D", "B": "#52B153", "C": "#A5CC74", "D": "#F4E70F",
    "E": "#F0B40F", "F": "#EB8235", "G": "#D7221F",
}
# Seuils officiels de consommation (énergie primaire, kWh/m²/an) : borne haute de chaque étiquette
SEUILS_CONSO = {"A": 70, "B": 110, "C": 180, "D": 250, "E": 330, "F": 420}

BLEU = "#2a78d6"
ENCRE = "#0b0b0b"
ENCRE_SECONDAIRE = "#52514e"
GRILLE = "#e1e0d9"
POLICE = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _mise_en_page(fig: go.Figure, titre: str, hauteur: int = 380) -> go.Figure:
    """Style commun : fond transparent, grille discrète, police système."""
    fig.update_layout(
        title=dict(text=titre, font=dict(size=16, color=ENCRE), x=0, xanchor="left"),
        font=dict(family=POLICE, size=13, color=ENCRE_SECONDAIRE),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=hauteur, margin=dict(l=10, r=30, t=60, b=10),
        hoverlabel=dict(bgcolor="white", font=dict(family=POLICE, color=ENCRE)),
        separators=", ",  # format français : virgule décimale, espace pour les milliers
    )
    fig.update_xaxes(gridcolor=GRILLE, linecolor=GRILLE, zeroline=False)
    fig.update_yaxes(gridcolor=GRILLE, linecolor=GRILLE, zeroline=False)
    return fig


def etiquettes(df: pd.DataFrame) -> go.Figure:
    """Répartition A → G (requête 02_etiquettes)."""
    fig = go.Figure(go.Bar(
        x=df["etiquette_dpe"], y=df["pct"],
        marker=dict(color=[COULEURS_DPE[e] for e in df["etiquette_dpe"]], cornerradius=4),
        text=[f"{p:.1f} %".replace(".", ",") for p in df["pct"]], textposition="outside", cliponaxis=False,
        customdata=df["nb_dpe"],
        hovertemplate="Étiquette %{x}<br>%{y:.1f} % des DPE<br>%{customdata:,.0f} logements<extra></extra>",
    ))
    fig.update_yaxes(title="% des DPE", ticksuffix=" %")
    fig.update_xaxes(title=None, showgrid=False)
    return _mise_en_page(fig, "Répartition des étiquettes DPE")


def etiquettes_par_departement(df: pd.DataFrame) -> go.Figure:
    """Barres empilées à 100 % par département, triées par part de passoires (requête 03)."""
    df = df.assign(departement=df["code_departement"].map(lambda c: f"{NOMS_DEPARTEMENTS[c]} ({c})"))
    ordre = (df.drop_duplicates("departement").sort_values("pct_passoires_dep")["departement"].tolist())
    fig = go.Figure()
    for etiquette, couleur in COULEURS_DPE.items():
        d = df[df["etiquette_dpe"] == etiquette].set_index("departement").reindex(ordre)
        fig.add_trace(go.Bar(
            name=etiquette, y=ordre, x=d["pct"], orientation="h",
            # Fine bordure couleur du fond = 2 px d'espace entre les segments
            marker=dict(color=couleur, line=dict(color="white", width=2)),
            # Lettre écrite dans le segment seulement s'il est assez large
            text=[etiquette if p >= 6 else "" for p in d["pct"].fillna(0)],
            textposition="inside", insidetextanchor="middle", textfont=dict(color=ENCRE),
            customdata=d[["nb_dpe", "pct_passoires_dep"]].values,
            hovertemplate=("%{y}<br>Étiquette " + etiquette + " : %{x:.1f} %"
                           "<br>%{customdata[0]:,.0f} logements"
                           "<br>F+G du département : %{customdata[1]:.1f} %<extra></extra>"),
        ))
    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=1.08, x=0, traceorder="normal"))
    fig.update_xaxes(title="% des DPE du département", ticksuffix=" %", range=[0, 100])
    fig.update_yaxes(title=None, showgrid=False)
    return _mise_en_page(fig, "Étiquettes par département (du plus au moins touché, de haut en bas)", 420)


def barres_pct_passoires(df: pd.DataFrame, colonne: str, titre: str,
                         horizontal: bool = False, ordre_donnees: bool = True) -> go.Figure:
    """
    Barres « % de passoires (F+G) » pour une dimension (période, énergie, type, surface).
    Une seule série → une seule couleur. Les valeurs sont écrites au bout des barres.
    """
    if not ordre_donnees:
        df = df.sort_values("pct_passoires", ascending=horizontal)
    # Le préfixe de tri "1. " des tranches de surface est retiré à l'affichage
    libelles = df[colonne].astype(str).str.replace(r"^\d\. ", "", regex=True)
    axe_cat, axe_val = (libelles, df["pct_passoires"])
    barre = go.Bar(
        x=axe_val if horizontal else axe_cat, y=axe_cat if horizontal else axe_val,
        orientation="h" if horizontal else "v",
        marker=dict(color=BLEU, cornerradius=4),
        text=[f"{p:.1f} %".replace(".", ",") for p in df["pct_passoires"]], textposition="outside", cliponaxis=False,
        customdata=df[["nb_dpe"]].values,
        hovertemplate=(("%{y}" if horizontal else "%{x}")
                       + "<br>Passoires (F+G) : " + ("%{x:.1f}" if horizontal else "%{y:.1f}")
                       + " %<br>%{customdata[0]:,.0f} logements<extra></extra>"),
    )
    fig = go.Figure(barre)
    axe_valeurs = fig.update_xaxes if horizontal else fig.update_yaxes
    axe_categories = fig.update_yaxes if horizontal else fig.update_xaxes
    axe_valeurs(title="% de passoires (F+G)", ticksuffix=" %")
    axe_categories(title=None, showgrid=False)
    return _mise_en_page(fig, titre, 360 if horizontal else 380)


def distribution_conso(df: pd.DataFrame) -> go.Figure:
    """
    Histogramme de la consommation (requête 08). Chaque barre prend la couleur de l'étiquette
    correspondant à sa consommation (seuils énergie seuls ; l'étiquette réelle tient aussi
    compte des émissions de CO₂).
    """
    def etiquette_de(conso: float) -> str:
        for etiquette, seuil in SEUILS_CONSO.items():
            if conso < seuil:
                return etiquette
        return "G"

    fig = go.Figure(go.Bar(
        x=df["tranche_debut"] + 5, y=df["pct"], width=8,
        marker=dict(color=[COULEURS_DPE[etiquette_de(c)] for c in df["tranche_debut"]]),
        customdata=pd.DataFrame({"debut": df["tranche_debut"], "fin": df["tranche_debut"] + 10,
                                 "nb": df["nb_dpe"]}).values,
        hovertemplate=("%{customdata[0]:.0f} à %{customdata[1]:.0f} kWh/m²/an"
                       "<br>%{y:.2f} % des DPE (%{customdata[2]:,.0f})<extra></extra>"),
    ))
    # Seuils des étiquettes en traits fins + lettre en haut de chaque zone
    bornes = [0] + list(SEUILS_CONSO.values()) + [810]
    for i, etiquette in enumerate(COULEURS_DPE):
        fig.add_annotation(x=(bornes[i] + bornes[i + 1]) / 2, y=1.02, yref="paper", text=f"<b>{etiquette}</b>",
                           showarrow=False, font=dict(color=ENCRE_SECONDAIRE))
    for seuil in SEUILS_CONSO.values():
        fig.add_vline(x=seuil, line=dict(color=ENCRE_SECONDAIRE, width=1))
    fig.update_xaxes(title="Consommation d'énergie primaire (kWh/m²/an) — la dernière barre regroupe 800 et plus",
                     range=[0, 810], showgrid=False)
    fig.update_yaxes(title="% des DPE", ticksuffix=" %")
    fig = _mise_en_page(fig, "Distribution de la consommation par m²", 400)
    fig.update_layout(margin=dict(t=80))
    return fig


def retour_investissement(economies_cumulees: list[float], cout_net: float,
                          temps_retour: float | None) -> go.Figure:
    """Simulateur : économies cumulées année après année, comparées au coût net des travaux."""
    annees = list(range(len(economies_cumulees)))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=annees, y=economies_cumulees, name="Économies cumulées", mode="lines",
        line=dict(color=BLEU, width=2), fill="tozeroy", fillcolor="rgba(42,120,214,0.10)",
        hovertemplate="Année %{x}<br>Économies cumulées : %{y:,.0f} €<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=annees, y=[cout_net] * len(annees), name="Coût net des travaux", mode="lines",
        line=dict(color=ENCRE_SECONDAIRE, width=2),
        hovertemplate="Coût net : %{y:,.0f} €<extra></extra>",
    ))
    if temps_retour is not None and temps_retour <= annees[-1]:
        fig.add_trace(go.Scatter(
            x=[temps_retour], y=[cout_net], mode="markers", showlegend=False,
            marker=dict(size=10, color=BLEU, line=dict(color="white", width=2)),
            hovertemplate=f"Travaux remboursés après {temps_retour:.1f} ans<extra></extra>",
        ))
        fig.add_annotation(x=temps_retour, y=cout_net, text=f"Remboursé en {temps_retour:.1f} ans".replace(".", ","),
                           showarrow=False, yshift=18, font=dict(color=ENCRE))
    fig.update_xaxes(title="Années après les travaux", showgrid=False, dtick=2)
    fig.update_yaxes(title="€", tickformat=",.0f", rangemode="tozero")
    fig.update_layout(legend=dict(orientation="h", y=1.1, x=0), hovermode="x unified")
    return _mise_en_page(fig, "Économies cumulées et coût des travaux", 380)


def evolution_trimestrielle(df: pd.DataFrame) -> go.Figure:
    """Part de passoires parmi les DPE réalisés chaque trimestre (requête 10)."""
    fig = go.Figure(go.Scatter(
        x=df["trimestre"], y=df["pct_passoires"], mode="lines+markers",
        line=dict(color=BLEU, width=2), marker=dict(size=8, color=BLEU, line=dict(color="white", width=2)),
        customdata=df[["nb_dpe"]].values,
        hovertemplate="Trimestre du %{x|%d/%m/%Y}<br>Passoires : %{y:.1f} %<br>%{customdata[0]:,.0f} DPE<extra></extra>",
    ))
    fig.update_yaxes(title="% de passoires (F+G)", ticksuffix=" %", rangemode="tozero")
    fig.update_xaxes(title=None, showgrid=False)
    fig.update_layout(hovermode="x")
    return _mise_en_page(fig, "Part de passoires parmi les DPE réalisés, par trimestre")
