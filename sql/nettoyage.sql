-- =====================================================================
-- Nettoyage des DPE d'Île-de-France (exécuté par src/nettoyage.py)
--
-- Chaque étape crée une table à partir de la précédente.
-- La ligne "-- @etape <table> | <description>" permet au script Python
-- de compter les lignes après chaque règle (journal de nettoyage).
-- Les règles sont expliquées dans docs/nettoyage.md.
-- =====================================================================


-- @etape etape_0_brut | Données brutes des 8 départements
CREATE OR REPLACE TABLE etape_0_brut AS
SELECT * FROM read_parquet('data/raw/dpe_*.parquet');


-- @etape etape_1_champs_obligatoires | Règle 1 : étiquette, commune et date renseignées
CREATE OR REPLACE TABLE etape_1_champs_obligatoires AS
SELECT *
FROM etape_0_brut
WHERE etiquette_dpe IN ('A', 'B', 'C', 'D', 'E', 'F', 'G')
  AND code_insee_ban IS NOT NULL
  AND date_etablissement_dpe IS NOT NULL;


-- @etape etape_2_logements | Règle 2 : exclusion des DPE « immeuble » (un DPE pour tout un bâtiment)
CREATE OR REPLACE TABLE etape_2_logements AS
SELECT *
FROM etape_1_champs_obligatoires
WHERE type_batiment IN ('appartement', 'maison');


-- @etape etape_3_valeurs_plausibles | Règle 3 : surface entre 8 et 500 m², conso entre 0 et 1 500 kWh/m²/an
CREATE OR REPLACE TABLE etape_3_valeurs_plausibles AS
SELECT *
FROM etape_2_logements
WHERE surface_habitable_logement BETWEEN 8 AND 500
  AND conso_5_usages_par_m2_ep > 0
  AND conso_5_usages_par_m2_ep <= 1500;


-- @etape etape_4_communes_idf | Règle 4 : codes INSEE mis à jour (fusions de communes) puis rattachés au référentiel IDF
-- Certains DPE portent un code INSEE qui n'existe plus :
--   - 93059 Pierrefitte-sur-Seine : fusionnée dans Saint-Denis (93066) le 01/01/2025 ;
--   - 95282 Gouzangrez : fusionnée dans Commeny (95169) le 01/01/2024 ;
--   - 75056 "Paris" sans arrondissement : on retrouve l'arrondissement grâce au code postal
--     (75011 → 75111, 75116 → 75116...).
CREATE OR REPLACE TABLE etape_4_communes_idf AS
WITH codes_a_jour AS (
    SELECT * REPLACE (
        CASE
            WHEN code_insee_ban = '93059' THEN '93066'
            WHEN code_insee_ban = '95282' THEN '95169'
            WHEN code_insee_ban = '75056' AND code_postal_ban LIKE '750__'
                 THEN '751' || right(code_postal_ban, 2)
            ELSE code_insee_ban
        END AS code_insee_ban
    )
    FROM etape_3_valeurs_plausibles
)
SELECT d.*, c.nom_commune, c.code_departement
FROM codes_a_jour AS d
INNER JOIN read_csv('data/raw/communes_idf.csv', types = {'code_insee': 'VARCHAR', 'code_departement': 'VARCHAR'}) AS c
        ON d.code_insee_ban = c.code_insee;


-- @etape etape_5_dedoublonnage | Règle 5 : un logement re-diagnostiqué n'est compté qu'une fois (DPE le plus récent)
-- Groupe "même logement" = même adresse précise + même surface + même étage + même type.
-- On ne fusionne un groupe QUE si :
--   - l'adresse contient un numéro (identifiant BAN en 3 parties : commune_rue_numéro),
--     sinon deux logements différents de la même rue seraient fusionnés ;
--   - chaque DPE du groupe a une date différente. Plusieurs DPE identiques le même jour
--     correspondent à des appartements distincts d'un immeuble diagnostiqués en lot
--     (jusqu'à 839 à la même adresse) : on les garde tous.
CREATE OR REPLACE TABLE etape_5_dedoublonnage AS
SELECT * EXCLUDE (adresse_precise, nb_dpe, nb_dates, rang)
FROM (
    SELECT *,
           len(string_split(identifiant_ban, '_')) >= 3                AS adresse_precise,
           count(*) OVER logement                                       AS nb_dpe,
           count(DISTINCT date_etablissement_dpe) OVER logement         AS nb_dates,
           row_number() OVER (logement ORDER BY date_etablissement_dpe DESC, numero_dpe DESC) AS rang
    FROM etape_4_communes_idf
    WINDOW logement AS (PARTITION BY identifiant_ban, surface_habitable_logement,
                                     coalesce(numero_etage_appartement, -1), type_batiment)
)
WHERE NOT adresse_precise      -- adresse imprécise : on ne peut pas juger, on garde
   OR nb_dates < nb_dpe        -- au moins deux DPE le même jour : lot d'appartements, on garde
   OR rang = 1;                -- vrai re-diagnostic : on ne garde que le plus récent


-- @etape dpe | Table finale : colonnes renommées, types corrigés, indicateurs calculés
CREATE OR REPLACE TABLE dpe AS
SELECT
    numero_dpe,
    CAST(date_etablissement_dpe AS DATE)                      AS date_dpe,
    year(CAST(date_etablissement_dpe AS DATE))                AS annee_dpe,
    -- Réforme du 1er janvier 2026 : coefficient électricité passé de 2,3 à 1,9
    CAST(date_etablissement_dpe AS DATE) >= DATE '2026-01-01' AS apres_reforme_2026,

    etiquette_dpe,
    etiquette_ges,
    etiquette_dpe IN ('F', 'G')                               AS est_passoire,
    conso_5_usages_par_m2_ep                                  AS conso_ep_m2,
    conso_5_usages_par_m2_ef                                  AS conso_ef_m2,
    emission_ges_5_usages_par_m2                              AS ges_m2,
    -- Coûts annuels estimés par le DPE : mis à vide si > 300 €/m²/an (saisie aberrante)
    CASE WHEN cout_total_5_usages / surface_habitable_logement <= 300
         THEN cout_total_5_usages END                         AS cout_annuel_total,
    CASE WHEN cout_chauffage / surface_habitable_logement <= 300
         THEN cout_chauffage END                              AS cout_annuel_chauffage,

    type_batiment,
    surface_habitable_logement                                AS surface_m2,
    -- Année de construction : mise à vide si hors de [1700 ; 2026]
    CASE WHEN annee_construction BETWEEN 1700 AND 2026
         THEN annee_construction END                          AS annee_construction,
    -- Tranche de surface (le préfixe numérique sert à trier les tranches dans l'ordre)
    CASE
        WHEN surface_habitable_logement < 20  THEN '1. moins de 20 m²'
        WHEN surface_habitable_logement < 30  THEN '2. 20 à 30 m²'
        WHEN surface_habitable_logement < 50  THEN '3. 30 à 50 m²'
        WHEN surface_habitable_logement < 80  THEN '4. 50 à 80 m²'
        WHEN surface_habitable_logement < 120 THEN '5. 80 à 120 m²'
        ELSE '6. 120 m² et plus'
    END                                                       AS tranche_surface,
    periode_construction,
    type_energie_principale_chauffage                         AS energie_chauffage,
    -- Énergies regroupées : les 15 libellés de l'ADEME en 6 familles lisibles
    CASE
        WHEN type_energie_principale_chauffage = 'Gaz naturel'                THEN 'Gaz'
        WHEN type_energie_principale_chauffage LIKE 'Électricité%'            THEN 'Électricité'
        WHEN type_energie_principale_chauffage = 'Réseau de Chauffage urbain' THEN 'Chauffage urbain'
        WHEN type_energie_principale_chauffage = 'Fioul domestique'           THEN 'Fioul'
        WHEN type_energie_principale_chauffage LIKE 'Bois%'                   THEN 'Bois'
        ELSE 'Autres (GPL, charbon...)'
    END                                                       AS energie_chauffage_groupe,
    coalesce(type_installation_chauffage, 'non renseigné')    AS installation_chauffage,
    -- Type de logement détaillé : pour un appartement, le chauffage collectif change tout
    CASE
        WHEN type_batiment = 'maison' THEN 'Maison'
        WHEN type_installation_chauffage = 'collectif'  THEN 'Appartement, chauffage collectif'
        WHEN type_installation_chauffage = 'individuel' THEN 'Appartement, chauffage individuel'
        ELSE 'Appartement, chauffage mixte'
    END                                                       AS type_logement,
    qualite_isolation_murs,
    qualite_isolation_menuiseries,
    qualite_isolation_plancher_haut_comble_perdu              AS qualite_isolation_combles,
    qualite_isolation_plancher_bas,

    code_insee_ban                                            AS code_insee,
    nom_commune,
    code_departement,
    CAST(string_split(_geopoint, ',')[1] AS DOUBLE)           AS latitude,
    CAST(string_split(_geopoint, ',')[2] AS DOUBLE)           AS longitude
FROM etape_5_dedoublonnage;


-- Table des communes (nom officiel, population) pour les jointures dans l'application
CREATE OR REPLACE TABLE communes AS
SELECT * FROM read_csv('data/raw/communes_idf.csv', types = {'code_insee': 'VARCHAR', 'code_departement': 'VARCHAR'});
