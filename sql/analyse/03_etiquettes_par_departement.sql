-- Répartition des étiquettes A → G par département (en % des DPE du département),
-- avec la part de passoires du département pour les trier du plus au moins touché
WITH par_etiquette AS (
    SELECT code_departement, etiquette_dpe, count(*) AS nb_dpe
    FROM dpe_filtre
    GROUP BY code_departement, etiquette_dpe
)
SELECT
    code_departement,
    etiquette_dpe,
    nb_dpe,
    round(100 * nb_dpe / sum(nb_dpe) OVER (PARTITION BY code_departement), 1) AS pct,
    round(100 * sum(CASE WHEN etiquette_dpe IN ('F', 'G') THEN nb_dpe ELSE 0 END)
                    OVER (PARTITION BY code_departement)
              / sum(nb_dpe) OVER (PARTITION BY code_departement), 1)          AS pct_passoires_dep
FROM par_etiquette
ORDER BY code_departement, etiquette_dpe;
