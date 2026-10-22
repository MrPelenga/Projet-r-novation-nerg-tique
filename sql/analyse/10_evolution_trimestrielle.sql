-- Évolution trimestrielle de la part de passoires parmi les DPE réalisés.
-- Le trimestre en cours (incomplet) est exclu : il fausserait le dernier point.
SELECT
    date_trunc('quarter', date_dpe)            AS trimestre,
    count(*)                                   AS nb_dpe,
    round(100 * avg(est_passoire::INT), 1)     AS pct_passoires
FROM dpe_filtre
WHERE date_dpe < date_trunc('quarter', (SELECT max(date_dpe) FROM dpe_filtre))
GROUP BY trimestre
ORDER BY trimestre;
