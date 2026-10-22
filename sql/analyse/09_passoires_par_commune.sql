-- Indicateurs par commune (Paris : par arrondissement), pour la carte.
-- Le seuil de fiabilité (au moins 30 DPE) est appliqué dans l'application, pas ici,
-- pour pouvoir afficher les petites communes en gris avec leur effectif.
SELECT
    code_insee,
    any_value(nom_commune)                                      AS nom_commune,
    any_value(code_departement)                                 AS code_departement,
    count(*)                                                    AS nb_dpe,
    count(*) FILTER (WHERE est_passoire)                        AS nb_passoires,
    round(100 * avg(est_passoire::INT), 1)                      AS pct_passoires,
    round(avg(conso_ep_m2))                                     AS conso_moyenne_kwh_m2,
    -- Répartition A → G en % (une colonne par étiquette, pour l'infobulle de la carte)
    round(100 * avg((etiquette_dpe = 'A')::INT), 1)             AS pct_A,
    round(100 * avg((etiquette_dpe = 'B')::INT), 1)             AS pct_B,
    round(100 * avg((etiquette_dpe = 'C')::INT), 1)             AS pct_C,
    round(100 * avg((etiquette_dpe = 'D')::INT), 1)             AS pct_D,
    round(100 * avg((etiquette_dpe = 'E')::INT), 1)             AS pct_E,
    round(100 * avg((etiquette_dpe = 'F')::INT), 1)             AS pct_F,
    round(100 * avg((etiquette_dpe = 'G')::INT), 1)             AS pct_G
FROM dpe_filtre
GROUP BY code_insee
ORDER BY pct_passoires DESC;
