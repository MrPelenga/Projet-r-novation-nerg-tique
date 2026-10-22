-- Chiffres clés : nombre de DPE, nombre et part de passoires (F+G), consommation médiane
-- Toutes les requêtes d'analyse lisent la vue `dpe_filtre`. Par défaut elle contient
-- tous les DPE ; l'application la redéfinit selon les filtres choisis par l'utilisateur.
SELECT
    count(*)                                   AS nb_dpe,
    count(*) FILTER (WHERE est_passoire)       AS nb_passoires,
    round(100 * avg(est_passoire::INT), 1)     AS pct_passoires,
    round(median(conso_ep_m2))                 AS conso_mediane_kwh_m2,
    min(date_dpe)                              AS premier_dpe,
    max(date_dpe)                              AS dernier_dpe
FROM dpe_filtre;
