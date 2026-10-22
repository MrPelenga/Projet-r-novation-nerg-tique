# Phase 1 — Exploration des données DPE (ADEME)

*Date d'exploration : 22/10/2026 — script : `src/exploration.py`*

## 1. L'API

| Élément | Valeur constatée |
|---|---|
| URL | `https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant` (inchangée) |
| Lignes (France) | 15 854 388 DPE |
| Dernière mise à jour | 21/10/2026 (mise à jour régulière) |
| Colonnes | 230 |
| Filtre automatique | l'API n'expose que les DPE **actifs** (`dpe_desactive = 0`) : les DPE annulés ou remplacés sont déjà exclus |
| Pagination | 10 000 lignes max par page, page suivante via le paramètre `after` |
| Filtrage serveur | `qs=code_departement_ban:94` → on ne télécharge que l'Île-de-France |

**Volume pour l'Île-de-France : 3 372 843 DPE**

| Dépt | 75 | 92 | 93 | 94 | 78 | 91 | 77 | 95 |
|---|---|---|---|---|---|---|---|---|
| DPE | 857 357 | 500 011 | 415 811 | 405 249 | 342 771 | 302 243 | 278 952 | 270 449 |

Avec ~25 colonnes utiles, ça fait environ 740 Mo en CSV, soit à peu près 100 Mo en Parquet/DuckDB.

## 2. L'échantillon

20 000 DPE **tirés au hasard** (`sort=_rand`) dans le Val-de-Marne (94).
Vérification de représentativité : F+G = **10,9 %** dans l'échantillon, contre **11,0 %** sur les 405 249 DPE du 94 (comptage fait par l'API).

## 3. Colonnes retenues et qualité

| Besoin du cahier des charges | Colonne réelle | Vides | Remarque |
|---|---|---|---|
| Étiquette DPE / GES | `etiquette_dpe`, `etiquette_ges` | 0 % | A→G, propre |
| Conso par m²/an | `conso_5_usages_par_m2_ep` (primaire), `_ef` (finale) | 0 % | 3 valeurs > 1 000 kWh/m² (max 151 314 : aberrant) |
| Surface | `surface_habitable_logement` | 2,6 % | 20 valeurs < 10 m², 5 > 500 m² |
| Année de construction | `annee_construction` | **38,5 %** | trop lacunaire, on utilisera plutôt ↓ |
| Période de construction | `periode_construction` | 0 % | 10 tranches, propre |
| Type de bâtiment | `type_batiment` | 0 % | appartement 89 %, maison 8 %, **immeuble 2,6 %** |
| Énergie de chauffage | `type_energie_principale_chauffage` | 0 % | Gaz 40 %, Chauffage urbain 34 %, Électricité 24 %, Fioul 2 % |
| Chauffage collectif/individuel | `type_installation_chauffage` | 8 % | vide = surtout les maisons |
| Commune | `code_insee_ban` | 0 % | 47 communes, ce qui correspond bien au 94 |
| Nom de commune | `nom_commune_ban` | 0 % | **inexploitable** : 68 variantes (majuscules, accents cassés « CrÃ©teil ») |
| Coordonnées | `_geopoint` (lat,lon) | 0 % | 18 % géocodés seulement à la commune, pas à l'adresse |
| Date du DPE | `date_etablissement_dpe` | 0 % | de juillet 2021 à octobre 2026 |
| Coût annuel estimé | `cout_total_5_usages`, `cout_chauffage` | 0 % | utile pour calibrer le simulateur ; quelques valeurs aberrantes (max 339 543 €) |
| Bonus pour le simulateur | `qualite_isolation_murs`, `_menuiseries`, `_plancher_haut_comble_perdu` | — | permet de dire *quel poste* est défaillant |

Contrôle de cohérence : la conso médiane par étiquette respecte bien les seuils officiels (A 65 → G 495 kWh/m²).

## 4. Problèmes de qualité repérés et règles de nettoyage proposées

1. **Noms de communes** : on les ignore. On prend le code INSEE et on récupère le nom officiel depuis l'API Géo.
2. **Valeurs aberrantes** : on exclut les surfaces < 8 m² ou > 500 m², les consos ≤ 0 ou > 1 500 kWh/m² et les années de construction hors 1700-2026.
3. **Logements diagnostiqués plusieurs fois** : ~23 % des lignes partagent adresse + surface + étage avec une autre. Sans traitement, un logement vendu deux fois compte double.
4. **DPE « immeuble »** : un seul DPE couvre tout un bâtiment (surface médiane 1 433 m²). Il ne se compare pas à un DPE de logement.
5. **Biais de la source** (à écrire dans les limites) : on fait un DPE lors d'une vente ou d'une location. La base décrit donc les logements **mis sur le marché depuis 2021**, pas tout le parc.
6. **Réforme 2026** (à vérifier en phase 2) : depuis le 1er janvier 2026, le coefficient de conversion de l'électricité est passé de 2,3 à 1,9. Les DPE antérieurs de logements chauffés à l'électricité seraient donc un peu pénalisés par rapport aux DPE récents.
