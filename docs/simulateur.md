# Simulateur de rénovation — méthode et hypothèses

*Code : `src/simulateur.py` (logique), `app/pages/simulateur.py` (interface), `tests/test_simulateur.py` (31 tests).*
*Hypothèses : `config/hypotheses.yaml`. Références DPE : `src/references_simulateur.py` → `data/processed/reference_*.csv`.*

> Estimation pédagogique : elle ne remplace pas un audit énergétique.

## Le principe
1. **Consommation de chauffage avant travaux.** C'est la médiane des logements franciliens comparables (même type, même étiquette, même énergie), calculée sur les DPE. Si moins de 30 DPE sont comparables, le simulateur refuse plutôt que d'inventer.
2. **Gain d'un geste d'isolation.** Il se calcule ainsi : part de la paroi dans les pertes de chaleur × baisse des pertes de cette paroi quand elle est très bien isolée. Les deux valeurs sont **mesurées sur les DPE d'Île-de-France** :

   | Maison classée F | Part des pertes | Baisse si très bien isolée | Gain sur le chauffage |
   |---|---:|---:|---:|
   | Murs | 41 % | 83 % | ≈ 34 % |
   | Toiture | 10 % | 80 % | ≈ 8 % |
   | Fenêtres | 10 % | 65 % | ≈ 7 % |
   | Plancher bas | 6 % | 63 % | ≈ 4 % |

   À noter : dans les DPE franciliens, les murs pèsent bien plus lourd que dans les chiffres génériques souvent cités (« toiture 25 à 30 %, murs 20 à 25 % »).
3. **Pompe à chaleur air/eau** (maisons au gaz ou au fioul). On calcule la chaleur utile : consommation × rendement observé des chaudières (0,83 au gaz, 0,78 au fioul, d'après les DPE de maisons). La pompe à chaleur produit cette chaleur avec SCOP fois moins d'électricité (SCOP = 2,9, mesuré par l'ADEME).
4. **Mode « étiquette visée ».** La consommation après travaux est celle des logements comparables qui ont déjà cette étiquette. Le coût retenu est celui d'une rénovation d'ampleur moyenne (Anah, 2025).
5. **Finances.** Le calcul se fait en trois étapes :
   - économie = (consommation avant × prix) − (consommation après × prix) ;
   - temps de retour = (coût − aides) ÷ économie annuelle ;
   - en option, une hausse annuelle des prix peut être ajoutée.

## Hypothèses sans source officielle (signalées ⚠️ dans l'application)
| Hypothèse | Valeur | Statut |
|---|---|---|
| Coût isolation des murs (extérieur / intérieur), toiture, fenêtres | fourchettes de comparateurs privés | Pas de barème officiel trouvé : milieu de fourchette |
| Prix de la chaleur des réseaux | 104,7 € HT/MWh (moyenne nationale 2024) | Prix TTC francilien non trouvé |
| Conversion surface habitable → m² de murs, de combles, nombre de fenêtres | 1,2 / 0,7 / 1 fenêtre pour 12 m² (maison) | Géométrie simplifiée, quantités modifiables |
| Hausse des prix de l'énergie | 0 %/an | Choix « prix constants », modifiable |

## Limites
- **Consommation conventionnelle.** Le DPE calcule la consommation pour un usage standard. Les occupants de passoires chauffent souvent moins que prévu (« effet prebound »), donc les économies réelles peuvent être plus faibles.
- **Chauffage uniquement.** L'eau chaude, la ventilation, les abonnements et l'entretien ne sont pas modélisés. Les aides dépendent des revenus et sont à saisir par l'utilisateur.
- **Étiquette après travaux.** Elle est estimée sur la seule énergie primaire. Le seuil d'émissions de CO₂ du DPE n'est pas modélisé, et les seuils spécifiques aux surfaces de 40 m² ou moins non plus.
- **Énergies couvertes.** Électricité, gaz, fioul et chauffage urbain, soit 99 % des DPE. Le bois et le GPL sont exclus, faute de prix sourcé.
- **Appartements.** Seuls les murs et les fenêtres sont proposés. Les DPE d'appartements ne permettent pas de mesurer l'effet de la toiture et du plancher bas, qui ne concernent que le dernier étage ou le rez-de-chaussée.
