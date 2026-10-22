-- Distribution de la consommation d'énergie primaire (kWh/m²/an), par tranches de 10 kWh.
-- Pas de 10 : les seuils des étiquettes (70, 110, 180, 250, 330, 420) tombent pile entre deux tranches.
-- Au-delà de 800 kWh/m²/an, tout est regroupé dans la dernière tranche (environ 0,5 % des DPE).
SELECT
    least(floor(conso_ep_m2 / 10) * 10, 800)          AS tranche_debut,
    count(*)                                          AS nb_dpe,
    round(100 * count(*) / sum(count(*)) OVER (), 2)  AS pct
FROM dpe_filtre
GROUP BY tranche_debut
ORDER BY tranche_debut;
