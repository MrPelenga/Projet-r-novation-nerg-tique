-- Part de passoires selon l'énergie principale de chauffage (familles regroupées)
SELECT
    energie_chauffage_groupe,
    count(*)                                   AS nb_dpe,
    count(*) FILTER (WHERE est_passoire)       AS nb_passoires,
    round(100 * avg(est_passoire::INT), 1)     AS pct_passoires
FROM dpe_filtre
GROUP BY energie_chauffage_groupe
ORDER BY pct_passoires DESC;
