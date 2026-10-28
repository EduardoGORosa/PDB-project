-- =====================================================================
-- CONSULTAS AVANÇADAS — a pergunta central
-- (anteprojeto, seção 4, segundo conjunto)
-- Funções de janela (NTILE, LAG, PERCENT_RANK), CTEs encadeadas, junção
-- reflexiva e agregação ponderada. Sem biblioteca estatística: tudo é SQL.
--
-- Convenções (camada analítica, 02_analitico.sql): despesa liquidada;
-- desempenho anual = média dos quadrimestres; nenhuma série atravessa o corte
-- entre regimes; associação, não causalidade.
-- =====================================================================
SET search_path TO pbd, public;


-- ---------------------------------------------------------------------
-- A1. QUINTIS DE GASTO × DESEMPENHO
--     O gasto per capita é assimétrico, e numa distribuição assim a
--     correlação é dominada pelos extremos. NTILE(5) divide os municípios em
--     quintis de gasto dentro de cada ano; em cada quintil, a MEDIANA do
--     desempenho composto, a média ponderada pela população e a mediana do
--     indicador sintético (ISF). Se o gasto se converte em resultado, os
--     quintis progridem.
-- ---------------------------------------------------------------------
WITH composto AS (
    SELECT c.cod_ibge6, c.ano, c.regime, c.percentual, i.isf
      FROM vw_desempenho_composto c
      JOIN vw_isf_anual i USING (cod_ibge6, ano, regime)
),
quintis AS (
    SELECT g.cod_ibge6, g.exercicio AS ano, g.populacao, g.gasto_ab_pc,
           NTILE(5) OVER (PARTITION BY g.exercicio ORDER BY g.gasto_ab_pc) AS quintil
      FROM mv_gasto_anual g
     WHERE g.gasto_ab_pc IS NOT NULL
)
SELECT q.ano, c.regime, q.quintil,
       count(*)                                                     AS municipios,
       MIN(q.gasto_ab_pc) || ' – ' || MAX(q.gasto_ab_pc)            AS faixa_gasto_pc,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.percentual)::numeric(5,1)
                                                                    AS mediana_desempenho,
       ROUND(SUM(c.percentual * q.populacao) / SUM(q.populacao), 1) AS media_ponderada,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.isf)::numeric(4,2)
                                                                    AS mediana_isf
  FROM quintis q
  JOIN composto c ON c.cod_ibge6 = q.cod_ibge6 AND c.ano = q.ano
 WHERE q.ano BETWEEN 2018 AND 2024
 GROUP BY q.ano, c.regime, q.quintil
 ORDER BY q.ano, q.quintil;


-- ---------------------------------------------------------------------
-- A1b. OS MESMOS QUINTIS, DENTRO DE CADA FAIXA DE PORTE
--      O gasto per capita cai com o porte (mediana de R$ 1.815 nos
--      municípios até 5 mil contra R$ 328 acima de 100 mil, em 2024) e o
--      desempenho também varia com o porte. Quintis estaduais misturam os
--      dois efeitos. Aqui o NTILE é particionado por ano E porte: cada
--      município é comparado só com os de mesmo porte.
-- ---------------------------------------------------------------------
WITH base AS (
    SELECT c.ano, c.regime, g.porte, c.percentual,
           NTILE(5) OVER (PARTITION BY c.ano, g.porte ORDER BY g.gasto_ab_pc) AS quintil_no_porte
      FROM vw_desempenho_composto c
      JOIN mv_gasto_anual g ON g.cod_ibge6 = c.cod_ibge6 AND g.exercicio = c.ano
     WHERE g.gasto_ab_pc IS NOT NULL AND c.ano <= 2024
)
SELECT ano, regime, quintil_no_porte,
       count(*)                                                                AS municipios,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY percentual)::numeric(5,1)   AS mediana_desempenho
  FROM base
 GROUP BY ano, regime, quintil_no_porte
 ORDER BY ano, quintil_no_porte;

--      Mediana do gasto e do desempenho por porte, para ver os dois efeitos.
SELECT g.porte,
       count(*)                                                                  AS municipios,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY g.gasto_ab_pc)::numeric(8,0)  AS gasto_pc_mediano,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY g.pct_ab_na_saude)::numeric(5,1) AS pct_ab_na_saude,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.percentual)::numeric(5,1)   AS desempenho_mediano
  FROM mv_gasto_anual g
  JOIN vw_desempenho_composto c ON c.cod_ibge6 = g.cod_ibge6 AND c.ano = g.exercicio
 WHERE g.exercicio = 2024
 GROUP BY g.porte
 ORDER BY g.porte;


-- ---------------------------------------------------------------------
-- A2. QUINTIS POR INDICADOR (2023, último ano com pagamento pleno)
--     Diferença de mediana entre o 5º e o 1º quintil, por indicador, com e
--     sem os municípios de até 5 mil habitantes.
-- ---------------------------------------------------------------------
WITH base AS (
    SELECT p.*,
           NTILE(5) OVER (PARTITION BY p.ano, p.codigo ORDER BY p.gasto_ab_pc) AS q_todos,
           CASE WHEN p.populacao >= 5000 THEN
               NTILE(5) OVER (PARTITION BY p.ano, p.codigo, p.populacao >= 5000
                                  ORDER BY p.gasto_ab_pc) END                 AS q_sem_pequenos
      FROM vw_painel_anual p
     WHERE p.ano = 2023
),
medianas AS (
    SELECT codigo, ordem,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY percentual)
               FILTER (WHERE q_todos = 1)         AS q1,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY percentual)
               FILTER (WHERE q_todos = 5)         AS q5,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY percentual)
               FILTER (WHERE q_sem_pequenos = 1)  AS q1_sem_pequenos,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY percentual)
               FILTER (WHERE q_sem_pequenos = 5)  AS q5_sem_pequenos
      FROM base
     GROUP BY codigo, ordem
)
SELECT codigo,
       q1::numeric(5,1), q5::numeric(5,1),
       (q5 - q1)::numeric(5,1)                               AS dif_q5_q1,
       q1_sem_pequenos::numeric(5,1), q5_sem_pequenos::numeric(5,1),
       (q5_sem_pequenos - q1_sem_pequenos)::numeric(5,1)     AS dif_sem_pequenos
  FROM medianas
 ORDER BY ordem;


-- ---------------------------------------------------------------------
-- A3. CADA MUNICÍPIO COMO SUA PRÓPRIA REFERÊNCIA
--     LAG() dá a variação anual do gasto per capita e do desempenho composto
--     do mesmo município. A janela é particionada pelo regime: a variação
--     2021→2022 não é calculada, porque mede a troca de regra.
--     Pergunta: quem aumentou mais o gasto melhorou mais o desempenho?
-- ---------------------------------------------------------------------
WITH serie AS (
    SELECT c.cod_ibge6, c.ano, c.regime, c.percentual, g.gasto_ab_pc,
           c.percentual - LAG(c.percentual)  OVER w   AS var_desempenho,
           100.0 * (g.gasto_ab_pc / NULLIF(LAG(g.gasto_ab_pc) OVER w, 0) - 1)
                                                      AS var_gasto_pct
      FROM vw_desempenho_composto c
      JOIN mv_gasto_anual g ON g.cod_ibge6 = c.cod_ibge6 AND g.exercicio = c.ano
     WHERE c.ano <= 2024
    WINDOW w AS (PARTITION BY c.cod_ibge6, c.regime ORDER BY c.ano)
),
classificada AS (
    SELECT *, NTILE(4) OVER (PARTITION BY ano ORDER BY var_gasto_pct) AS quartil_var_gasto
      FROM serie
     WHERE var_desempenho IS NOT NULL AND var_gasto_pct IS NOT NULL
)
SELECT ano, regime, quartil_var_gasto,
       count(*)                                                      AS municipios,
       ROUND(AVG(var_gasto_pct), 1)                                  AS var_gasto_media_pct,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY var_desempenho)::numeric(5,1)
                                                                     AS var_desempenho_mediana_pp,
       ROUND(100.0 * count(*) FILTER (WHERE var_desempenho > 0) / count(*), 1)
                                                                     AS pct_que_melhorou
  FROM classificada
 GROUP BY ano, regime, quartil_var_gasto
 ORDER BY ano, quartil_var_gasto;


-- ---------------------------------------------------------------------
-- A4. GRUPO DE REFERÊNCIA POR PORTE (junção reflexiva)
--     Cada município é comparado aos 20 municípios de população mais
--     próxima no mesmo ano (mv_grupo_referencia: junção da tabela de
--     municípios com ela mesma, ordenada por ROW_NUMBER). Dentro do grupo, a
--     posição percentual no gasto e no desempenho; interessam os casos em
--     que as duas posições caem em quartis opostos.
-- ---------------------------------------------------------------------
-- A visão vw_posicao_no_grupo (02_analitico.sql) faz a junção reflexiva;
-- aqui, os casos discrepantes de 2023.

--      Resumo: a posição no gasto prevê a posição no desempenho dentro do
--      grupo? Correlação entre as duas posições, por ano.
SELECT ano,
       ROUND(CORR(posicao_gasto, posicao_desempenho)::numeric, 3)               AS corr_posicoes,
       ROUND(AVG(posicao_desempenho) FILTER (WHERE posicao_gasto >= 75), 1)     AS desempenho_quem_mais_gasta,
       ROUND(AVG(posicao_desempenho) FILTER (WHERE posicao_gasto <= 25), 1)     AS desempenho_quem_menos_gasta
  FROM vw_posicao_no_grupo
 WHERE ano <= 2024
 GROUP BY ano ORDER BY ano;

SELECT m.nome, m.crs, v.populacao, v.faixa_populacao_grupo,
       v.gasto_ab_pc, v.posicao_gasto, v.desempenho, v.posicao_desempenho, v.discrepancia
  FROM vw_posicao_no_grupo v
  JOIN vw_municipio m USING (cod_ibge6)
 WHERE v.ano = 2023 AND v.discrepancia IS NOT NULL
 ORDER BY v.discrepancia, abs(v.posicao_gasto - v.posicao_desempenho) DESC;


-- ---------------------------------------------------------------------
-- A5. AS DISCREPÂNCIAS SE CONCENTRAM EM ALGUMA REGIÃO? (CTEs encadeadas)
--     casos -> por CRS -> comparação com a participação da CRS no estado.
-- ---------------------------------------------------------------------
WITH casos AS (
    SELECT v.cod_ibge6, v.discrepancia
      FROM vw_posicao_no_grupo v
     WHERE v.ano BETWEEN 2022 AND 2024
),
por_municipio AS (
    -- recorrente: o município aparece discrepante em pelo menos 2 dos 3 anos
    SELECT cod_ibge6,
           count(*) FILTER (WHERE discrepancia = 'gasta mais, rende menos') AS anos_mais_menos,
           count(*) FILTER (WHERE discrepancia = 'gasta menos, rende mais') AS anos_menos_mais
      FROM casos GROUP BY cod_ibge6
),
por_crs AS (
    SELECT m.crs_numero, m.crs,
           count(*)                                       AS municipios,
           count(*) FILTER (WHERE p.anos_mais_menos >= 2) AS recorrentes_mais_menos,
           count(*) FILTER (WHERE p.anos_menos_mais >= 2) AS recorrentes_menos_mais
      FROM por_municipio p JOIN vw_municipio m USING (cod_ibge6)
     GROUP BY m.crs_numero, m.crs
),
estado AS (
    SELECT SUM(municipios) AS n, SUM(recorrentes_mais_menos) AS mm,
           SUM(recorrentes_menos_mais) AS mn
      FROM por_crs
)
SELECT c.crs, c.municipios,
       c.recorrentes_mais_menos,
       ROUND(100.0 * c.recorrentes_mais_menos / c.municipios, 1) AS pct_mais_menos,
       c.recorrentes_menos_mais,
       ROUND(100.0 * c.recorrentes_menos_mais / c.municipios, 1) AS pct_menos_mais,
       ROUND(100.0 * e.mm / e.n, 1)                              AS pct_mais_menos_rs,
       ROUND(100.0 * e.mn / e.n, 1)                              AS pct_menos_mais_rs
  FROM por_crs c CROSS JOIN estado e
 ORDER BY c.crs_numero;


-- ---------------------------------------------------------------------
-- A6. MÉDIA SIMPLES × MÉDIA PONDERADA × SEM PEQUENOS MUNICÍPIOS
--     A média simples dá a um município de mil habitantes o mesmo peso da
--     capital. As três medidas lado a lado, por indicador e ano.
-- ---------------------------------------------------------------------
SELECT ano, regime, codigo,
       ROUND(AVG(media_simples), 1)      AS media_simples,
       ROUND(AVG(media_ponderada), 1)    AS media_ponderada,
       ROUND(AVG(media_sem_pequenos), 1) AS sem_ate_5mil,
       ROUND(AVG(media_ponderada - media_simples), 1) AS efeito_ponderacao_pp
  FROM mv_serie_estadual
 WHERE ano <= 2024
 GROUP BY ano, regime, codigo, ordem
 ORDER BY ordem, ano;


-- ---------------------------------------------------------------------
-- A7. A MUDANÇA DE REGRA: a série analisada dentro de cada regime
--     LAG() sobre a série estadual ponderada. A variação típica entre
--     quadrimestres do mesmo regime é comparada à variação no corte
--     2021Q3 -> 2022Q1. Uma razão muito acima de 1 indica que a variação
--     mede a régua, não o atendimento.
-- ---------------------------------------------------------------------
WITH variacao AS (
    SELECT codigo, ordem, quadrimestre, regime,
           media_ponderada,
           media_ponderada - LAG(media_ponderada) OVER (PARTITION BY codigo ORDER BY quadrimestre)
               AS var_pp,
           regime <> LAG(regime) OVER (PARTITION BY codigo ORDER BY quadrimestre)
               AS e_corte
      FROM mv_serie_estadual
     WHERE quadrimestre <= '2024Q3'
)
SELECT codigo,
       ROUND(AVG(ABS(var_pp)) FILTER (WHERE NOT e_corte), 1)   AS var_tipica_pp,
       MAX(var_pp) FILTER (WHERE e_corte)                      AS var_no_corte_pp,
       ROUND(ABS(MAX(var_pp) FILTER (WHERE e_corte))
             / NULLIF(AVG(ABS(var_pp)) FILTER (WHERE NOT e_corte), 0), 1) AS razao
  FROM variacao
 GROUP BY codigo, ordem
 ORDER BY ordem;


-- ---------------------------------------------------------------------
-- A8. O DINHEIRO EM JOGO MUDOU O DESEMPENHO?
--     Dentro do regime de 2022 (mesma régua), o desempenho médio ponderado
--     por situação financeira do quadrimestre: parcial (2022Q1),
--     pleno (2022Q2–2023Q3) e posterior ao programa (2024).
--     Os quadrimestres em que a portaria fixou o resultado ficam à parte.
-- ---------------------------------------------------------------------
SELECT s.codigo, p.efeito_financeiro,
       count(*)                                  AS quadrimestres,
       ROUND(AVG(s.media_ponderada), 1)          AS media_ponderada,
       bool_or(s.ajustado_portaria)              AS contem_ajuste
  FROM mv_serie_estadual s
  JOIN dim_periodo p USING (quadrimestre)
 WHERE s.regime = 'NT 11/2022' AND s.ano <= 2024
 GROUP BY s.codigo, s.ordem, p.efeito_financeiro
 ORDER BY s.ordem, MIN(s.quadrimestre);


-- ---------------------------------------------------------------------
-- A9. PORTO ALEGRE NA DISTRIBUIÇÃO ESTADUAL E NO SEU GRUPO
--     PERCENT_RANK do gasto per capita e do desempenho, ano a ano.
-- ---------------------------------------------------------------------
WITH ranking AS (
    SELECT c.cod_ibge6, c.ano, g.gasto_ab_pc, g.pct_ab_na_saude, c.percentual,
           ROUND(100 * PERCENT_RANK() OVER (PARTITION BY c.ano ORDER BY g.gasto_ab_pc)::numeric, 1)
               AS pctil_gasto,
           ROUND(100 * PERCENT_RANK() OVER (PARTITION BY c.ano ORDER BY c.percentual)::numeric, 1)
               AS pctil_desempenho
      FROM vw_desempenho_composto c
      JOIN mv_gasto_anual g ON g.cod_ibge6 = c.cod_ibge6 AND g.exercicio = c.ano
     WHERE g.gasto_ab_pc IS NOT NULL
)
SELECT r.ano, r.gasto_ab_pc, r.pct_ab_na_saude, r.pctil_gasto,
       r.percentual AS desempenho, r.pctil_desempenho
  FROM ranking r JOIN dim_municipio m USING (cod_ibge6)
 WHERE m.nome = 'Porto Alegre'
 ORDER BY r.ano;
