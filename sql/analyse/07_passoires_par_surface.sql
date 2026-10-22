-- Part de passoires selon la surface, et contribution de chaque tranche au total des passoires
SELECT
    tranche_surface,
    count(*)                                                                    AS nb_dpe,
    round(100 * avg(est_passoire::INT), 1)                                      AS pct_passoires,
    round(100 * count(*) FILTER (WHERE est_passoire)
              / sum(count(*) FILTER (WHERE est_passoire)) OVER (), 1)           AS part_du_total_passoires
FROM dpe_filtre
GROUP BY tranche_surface
ORDER BY tranche_surface;
