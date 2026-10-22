-- Part de passoires selon la période de construction,
-- et contribution de chaque période au total des passoires
SELECT
    periode_construction,
    count(*)                                                                    AS nb_dpe,
    count(*) FILTER (WHERE est_passoire)                                        AS nb_passoires,
    round(100 * avg(est_passoire::INT), 1)                                      AS pct_passoires,
    round(100 * count(*) FILTER (WHERE est_passoire)
              / sum(count(*) FILTER (WHERE est_passoire)) OVER (), 1)           AS part_du_total_passoires
FROM dpe_filtre
GROUP BY periode_construction
-- Ordre chronologique : "avant 1948" en premier, "après 2021" en dernier
ORDER BY CASE periode_construction WHEN 'avant 1948' THEN '0' WHEN 'après 2021' THEN '9' ELSE periode_construction END;
