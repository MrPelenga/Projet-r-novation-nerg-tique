-- Répartition des étiquettes A → G sur l'ensemble des DPE
SELECT
    etiquette_dpe,
    count(*)                                                    AS nb_dpe,
    round(100 * count(*) / sum(count(*)) OVER (), 1)            AS pct
FROM dpe_filtre
GROUP BY etiquette_dpe
ORDER BY etiquette_dpe;
