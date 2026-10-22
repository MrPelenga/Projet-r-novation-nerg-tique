-- Part de passoires selon le type de logement (maison / appartement × type de chauffage)
SELECT
    type_logement,
    count(*)                                   AS nb_dpe,
    count(*) FILTER (WHERE est_passoire)       AS nb_passoires,
    round(100 * avg(est_passoire::INT), 1)     AS pct_passoires,
    round(median(surface_m2))                  AS surface_mediane_m2
FROM dpe_filtre
GROUP BY type_logement
ORDER BY pct_passoires DESC;
