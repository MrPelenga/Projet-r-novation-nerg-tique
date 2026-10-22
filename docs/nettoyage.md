# Règles de nettoyage des DPE

*Extraction du 22/10/2026. Code : `sql/nettoyage.sql`, exécuté par `src/nettoyage.py`.*
*Le journal chiffré est régénéré à chaque exécution dans `data/processed/journal_nettoyage.csv`.*

## Bilan

| Étape | Lignes restantes | Lignes retirées | % du brut |
|---|---:|---:|---:|
| Données brutes (8 départements) | 3 372 843 | – | – |
| 1. Champs obligatoires | 3 372 843 | 0 | 0 % |
| 2. Exclusion des DPE « immeuble » | 3 289 763 | 83 080 | 2,5 % |
| 3. Valeurs plausibles | 3 283 794 | 5 969 | 0,2 % |
| 4. Codes INSEE mis à jour | 3 283 794 | 0 | 0 % |
| 5. Logements re-diagnostiqués | **3 137 735** | 146 059 | 4,3 % |

**Au final, 93 % des DPE bruts sont conservés.**

## Les règles, une par une

### 1. Champs obligatoires
On garde un DPE seulement s'il a une étiquette valide (A à G), un code INSEE et une date d'établissement.
*Aucune ligne retirée : ces champs sont toujours remplis dans la source.*

### 2. Exclusion des DPE « immeuble »
Un DPE « immeuble » évalue un bâtiment entier (surface médiane d'environ 1 400 m²), pas un logement. Le garder reviendrait à compter un immeuble de 50 appartements comme un seul logement. On le retire donc des statistiques, qui raisonnent en nombre de logements.

### 3. Valeurs plausibles
| Variable | Plage conservée | Raison |
|---|---|---|
| Surface habitable | 8 à 500 m² | En dessous de 8 m², la loi interdit de louer un local comme logement. Au-delà de 500 m², on a presque toujours une erreur de saisie (ex. : 3 909 m² pour un appartement). |
| Consommation (énergie primaire) | > 0 et ≤ 1 500 kWh/m²/an | Le seuil de G est 420. Au-delà de 1 500, on a une erreur de saisie (maximum observé : 151 314). |

Deux autres valeurs sont **mises à vide** plutôt que de faire supprimer la ligne, car l'étiquette du DPE reste exploitable :
- `annee_construction` hors de la plage 1700-2026. On s'appuie surtout sur `periode_construction`, toujours remplie, alors que l'année manque dans 40 % des cas.
- Les coûts annuels supérieurs à 300 €/m²/an. Même un G à 1 000 kWh/m² payé 0,25 €/kWh coûterait 250 €/m².

### 4. Codes INSEE mis à jour
Certains DPE portent un code de commune qui n'existe plus. Plutôt que de les perdre, on les rattache à la commune actuelle :
| Ancien code | Nouveau code | DPE concernés | Motif |
|---|---|---:|---|
| 93059 Pierrefitte-sur-Seine | 93066 Saint-Denis | 5 372 | Fusion au 01/01/2025 |
| 95282 Gouzangrez | 95169 Commeny | 9 | Fusion au 01/01/2024 |
| 75056 « Paris » | 751xx (arrondissement) | 410 | Arrondissement déduit du code postal |

Le nom officiel de la commune vient de l'API Géo. Le nom saisi dans le DPE n'est pas utilisable : on trouve plusieurs orthographes pour une même commune, avec des accents cassés (« CrÃ©teil »).

### 5. Logements re-diagnostiqués
Un même logement peut avoir plusieurs DPE, par exemple s'il a été vendu puis loué, ou si son propriétaire a refait le diagnostic après des travaux. On considère que deux DPE concernent **le même logement** quand ils ont la même adresse précise (numéro + rue, d'après l'identifiant BAN), la même surface, le même étage et le même type (maison ou appartement).

**Point important découvert pendant le nettoyage.** Une première version de la règle (« garder le DPE le plus récent de chaque groupe ») retirait **1,14 million de lignes (34 %)**. En regardant de plus près, beaucoup de groupes contenaient des dizaines de DPE établis **le même jour**, jusqu'à 839 à une seule adresse. Ce ne sont pas des doublons. Ce sont des appartements identiques d'un même immeuble, souvent du logement social, diagnostiqués en lot. Les supprimer aurait fait passer le taux de passoires de 12,1 % à 14,5 %, à tort.

**Règle retenue.** On ne fusionne un groupe que si **chacun de ses DPE a une date différente**, ce qui signe un vrai re-diagnostic. On garde alors le DPE le plus récent. Les groupes avec plusieurs DPE le même jour sont conservés en entier, tout comme les DPE dont l'adresse est imprécise (sans numéro).

| Variante testée | Lignes conservées | % F+G |
|---|---:|---:|
| Aucun dédoublonnage | 3 289 763 | 12,1 % |
| Le plus récent partout (première version) | 2 148 984 | 14,5 % |
| **Seulement si toutes les dates diffèrent (retenue)** | **3 143 491** | **11,4 %** |

*Ces variantes ont été mesurées avant la correction des codes INSEE, d'où un léger écart avec le total final.*

## Colonnes calculées dans la table finale `dpe`
- `est_passoire` : étiquette F ou G.
- `apres_reforme_2026` : DPE établi à partir du 01/01/2026. À cette date, le coefficient de conversion de l'électricité est passé de 2,3 à 1,9 (arrêté du 13 août 2025). L'analyse de la phase 3 montre que les DPE antérieurs semblent déjà recalculés avec ce coefficient dans la base (voir `docs/insights.md`). Cette colonne sert donc de contrôle.
- `energie_chauffage_groupe` : les 15 libellés de l'ADEME regroupés en 6 familles (gaz, électricité, chauffage urbain, fioul, bois, autres).
- `type_logement` : maison, ou appartement en chauffage collectif, individuel ou mixte.
- `tranche_surface` : 6 tranches, de moins de 20 m² à 120 m² et plus.
- `latitude`, `longitude` : extraites de `_geopoint`.

## Limites connues
- **Biais de sélection.** Un DPE est obligatoire surtout lors d'une vente ou d'une location. La base décrit donc les logements mis sur le marché depuis juillet 2021, et non l'ensemble du parc. Le logement occupé par son propriétaire depuis longtemps y est sous-représenté.
- **Réformes du calcul.** Deux réformes ont changé le calcul : les seuils des petites surfaces (≤ 40 m²) au 01/07/2024, et le coefficient électricité au 01/01/2026. Le coefficient électricité semble déjà appliqué rétroactivement dans la base. Pour les seuils des petites surfaces, on ne sait pas si les attestations de nouvelle étiquette sont prises en compte.
- **Dédoublonnage imparfait.** Deux appartements identiques au même étage, diagnostiqués à des dates différentes, sont fusionnés à tort. À l'inverse, un logement dont la surface a été saisie différemment d'un DPE à l'autre n'est pas reconnu comme doublon.
- **Géolocalisation.** Environ 18 % des DPE ne sont géocodés qu'à la commune ou à la rue. C'est sans effet sur la carte, qui est faite par commune.
