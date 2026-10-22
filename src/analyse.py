"""
Phase 3 — Analyse : exécute les requêtes de sql/analyse/, produit les graphiques et
les phrases d'insight, et les assemble dans un rapport HTML (docs/rapport_analyse.html).

Usage : python src/analyse.py
"""

from pathlib import Path

import graphiques
import insights
from requetes import RACINE, connexion, executer

RAPPORT = RACINE / "docs" / "rapport_analyse.html"

# (requête SQL, fonction graphique, fonction insight, arguments du graphique)
SECTIONS = [
    ("02_etiquettes", graphiques.etiquettes, insights.etiquettes, {}),
    ("03_etiquettes_par_departement", graphiques.etiquettes_par_departement, insights.etiquettes_par_departement, {}),
    ("04_passoires_par_periode", graphiques.barres_pct_passoires, insights.passoires_par_periode,
     dict(colonne="periode_construction", titre="Part de passoires selon la période de construction")),
    ("05_passoires_par_chauffage", graphiques.barres_pct_passoires, insights.passoires_par_chauffage,
     dict(colonne="energie_chauffage_groupe", titre="Part de passoires selon l'énergie de chauffage",
          horizontal=True, ordre_donnees=False)),
    ("06_passoires_par_type_logement", graphiques.barres_pct_passoires, insights.passoires_par_type_logement,
     dict(colonne="type_logement", titre="Part de passoires selon le type de logement",
          horizontal=True, ordre_donnees=False)),
    ("07_passoires_par_surface", graphiques.barres_pct_passoires, insights.passoires_par_surface,
     dict(colonne="tranche_surface", titre="Part de passoires selon la surface")),
    ("08_distribution_conso", graphiques.distribution_conso, insights.distribution_conso, {}),
    ("10_evolution_trimestrielle", graphiques.evolution_trimestrielle, insights.evolution_trimestrielle, {}),
]

GABARIT = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analyse DPE Île-de-France</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: #f9f9f7;
         color: #0b0b0b; margin: 0; padding: 24px 16px; }}
  main {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 26px; margin-bottom: 4px; }}
  .sous-titre {{ color: #52514e; margin-top: 0; }}
  .chiffres {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 24px 0; }}
  .chiffre {{ background: #fcfcfb; border: 1px solid rgba(11,11,11,0.10); border-radius: 8px; padding: 16px; }}
  .chiffre .valeur {{ font-size: 30px; font-weight: 600; }}
  .chiffre .libelle {{ color: #52514e; font-size: 14px; }}
  section {{ background: #fcfcfb; border: 1px solid rgba(11,11,11,0.10); border-radius: 8px;
            padding: 16px; margin-bottom: 16px; }}
  .insight {{ border-left: 3px solid #2a78d6; padding: 4px 12px; margin: 8px 0 0; }}
  .source {{ color: #898781; font-size: 12px; margin: 6px 0 0; }}
</style></head>
<body><main>
<h1>Passoires thermiques en Île-de-France</h1>
<p class="sous-titre">Analyse des DPE ADEME (logements existants, juillet 2021 – {dernier_dpe}) · phase 3</p>
<div class="chiffres">
  <div class="chiffre"><div class="valeur">{nb_dpe}</div><div class="libelle">logements analysés</div></div>
  <div class="chiffre"><div class="valeur">{pct_passoires}</div><div class="libelle">de passoires (F ou G)</div></div>
  <div class="chiffre"><div class="valeur">{nb_passoires}</div><div class="libelle">passoires thermiques</div></div>
  <div class="chiffre"><div class="valeur">{conso} kWh</div><div class="libelle">consommation médiane par m² et par an</div></div>
</div>
{sections}
</main></body></html>
"""


if __name__ == "__main__":
    con = connexion()
    cles = executer(con, "01_chiffres_cles").iloc[0]

    blocs = []
    for requete, fonction_graphique, fonction_insight, arguments in SECTIONS:
        df = executer(con, requete)
        fig = fonction_graphique(df, **arguments)
        phrase = fonction_insight(df)
        print(f"- {phrase}")
        blocs.append(
            "<section>"
            + fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False})
            + f'<p class="insight">{phrase}</p>'
            + f'<p class="source">Requête : sql/analyse/{requete}.sql</p></section>'
        )

    RAPPORT.write_text(GABARIT.format(
        dernier_dpe=cles["dernier_dpe"].strftime("%d/%m/%Y"),
        nb_dpe=insights._nombre(cles["nb_dpe"]),
        pct_passoires=insights._pct(cles["pct_passoires"]),
        nb_passoires=insights._nombre(cles["nb_passoires"]),
        conso=f"{cles['conso_mediane_kwh_m2']:.0f}",
        sections="\n".join(blocs),
    ), encoding="utf-8")
    print(f"\nRapport : {RAPPORT.relative_to(RACINE)}")
