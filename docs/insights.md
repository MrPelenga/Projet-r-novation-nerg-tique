# Insights — phase 3

*Données : 3 137 735 DPE de logements d'Île-de-France après nettoyage (juillet 2021 – octobre 2026).*
*Graphiques : `docs/rapport_analyse.html` (regénéré par `python src/analyse.py`). Requêtes : `sql/analyse/`.*

## Les 5 insights clés (pour le README)

1. **11,4 % des logements diagnostiqués sont des passoires (F ou G), soit 357 140 logements.**
   Les plus fréquentes sont les étiquettes C (34 %) et D (32 %). Seuls 3,4 % des logements sont classés A ou B.

2. **Le profil type de la passoire : un petit logement ancien.** Les logements construits avant 1975 et de moins de 50 m² représentent **26 % des DPE mais 55 % des passoires**.
   - Construits avant 1975 : 96 % des passoires. Avant 1948, 26,6 % sont F ou G, contre 0,3 % après 1989. La première réglementation thermique date de 1974.
   - Moins de 20 m² : 20 % de F+G. Une partie de cet écart vient du calcul lui-même : l'eau chaude est ramenée au m², ce qui pénalise les petites surfaces. Une correction est entrée en vigueur le 1er juillet 2024 (arrêté du 25 mars 2024).

3. **Paris concentre 37 % des passoires d'Île-de-France** (131 843 logements). C'est aussi le département le plus touché en proportion (16,9 %, contre 7,5 % pour l'Essonne). Les 15e, 17e, 18e et 16e arrondissements comptent chacun plus de 11 000 passoires.
   À type de logement égal, Paris reste environ deux fois plus touché que le reste de la région : 20 % contre 10 % pour un appartement en chauffage individuel. C'est un effet du bâti ancien (haussmannien et d'avant-guerre).

4. **Le mode de chauffage compte autant que l'âge du bâtiment.**
   - Fioul : 64 % de passoires, et même 70 % pour les maisons chauffées au fioul.
   - Chauffage urbain : seulement 3,4 %.
   - Appartement en chauffage individuel : 14 % de passoires, contre 7,8 % en chauffage collectif.
   - Mais en **volume**, l'électricité et le gaz regroupent 83 % des passoires.

5. **Deux géographies différentes.** En volume, les passoires sont dans le cœur urbain (Paris et la petite couronne). En proportion, les communes les plus touchées sont rurales : sur les 151 communes qui dépassent 25 % de passoires (avec au moins 30 DPE), **89 sont en Seine-et-Marne**. Ce sont des maisons anciennes, souvent chauffées au fioul. À l'inverse, les villes nouvelles (Bussy-Saint-Georges, Serris, Lognes...) comptent moins de 1 % de passoires.

## Insights secondaires
- **Maisons** : 20,6 % de passoires, contre 7,8 % pour un appartement en chauffage collectif.
- **Consommation** : la médiane est de 198 kWh/m²/an, soit une étiquette D. 12 % des logements dépassent 330 kWh/m²/an, le seuil de F.
- **Évolution dans le temps : à interpréter avec prudence.** La part de passoires parmi les DPE réalisés baisse de 22 % en 2021 à 8 % en 2024, puis remonte à 13 % en 2026. Cette remontée vient surtout de la **composition** : les logements d'avant 1948 passent de 23 % des DPE en 2024 à 33 % en 2026. Hypothèse : la loi Climat (location des G interdite depuis 2025, puis des F en 2028) pousse les propriétaires de logements anciens à faire diagnostiquer. Ce n'est pas une dégradation du parc.

## Vérification sur la réforme de 2026
Depuis le 1er janvier 2026, le coefficient de conversion de l'électricité est passé de 2,3 à 1,9. On s'attendait donc à ce que les anciens DPE de logements chauffés à l'électricité soient plus sévères que les récents. **Ce n'est pas le cas dans la base.** Pour ces logements, le rapport énergie primaire / énergie finale vaut 1,90 en médiane pour chaque année de 2022 à 2026. Plus de 99 % des DPE établis depuis 2022 sont sous 2,1. **L'ADEME semble donc publier les anciens DPE déjà recalculés avec le nouveau coefficient** (seuls 7,6 % des DPE de 2021 font exception). Les étiquettes sont comparables dans le temps, et la colonne `apres_reforme_2026` sert surtout de contrôle.

## Pistes de recommandations (à affiner en phase 6)
Pour une collectivité ou un acteur de la rénovation (comme GreenFlex) :
1. **Cible « volume » : les petits appartements anciens en chauffage individuel**, à Paris et en petite couronne. C'est là que se trouve la majorité des passoires. Ce sont aussi les logements les plus exposés à l'interdiction de louer, car les petites surfaces sont surtout des locations. Leviers : isolation, ventilation, remplacement des convecteurs électriques.
2. **Cible « taux » : les maisons rurales chauffées au fioul** (Seine-et-Marne, Vexin), avec 70 % de passoires. Le levier est clair : remplacer la chaudière fioul par une pompe à chaleur, en combinant avec l'isolation et les aides MaPrimeRénov'.
3. **Copropriétés en chauffage collectif** : un seul chantier traite des dizaines de logements. Le taux de passoires y est faible, mais l'effet de levier est fort.
