-- =====================================================================
-- CONSULTAS BÁSICAS — conhecer os dados e verificar a integração
-- (anteprojeto, seção 4, primeiro conjunto)
-- Seleção, projeção, junção, agregação e ordenação.
-- =====================================================================
SET search_path TO pbd, public;

-- ---------------------------------------------------------------------
-- B1. Dicionário dos indicadores: cada versão, sua regra e sua vigência.
-- ---------------------------------------------------------------------
SELECT i.ordem, i.codigo, i.regime, i.vigencia_inicio, i.vigencia_fim,
       i.meta, i.peso, i.nota_tecnica, i.nome
  FROM dim_indicador i
 ORDER BY i.ordem, i.vigencia_inicio;


-- ---------------------------------------------------------------------
-- B2. Gasto em Atenção Básica por habitante, por município e exercício.
--     Despesa liquidada na subfunção 10.301 sobre a população do próprio
--     exercício (pop_municipio).
-- ---------------------------------------------------------------------
SELECT m.nome AS municipio, d.exercicio, p.populacao,
       d.valor                               AS gasto_ab,
       ROUND(d.valor / p.populacao, 2)       AS gasto_ab_per_capita
  FROM fato_despesa d
  JOIN dim_conta     c ON c.conta = d.conta
  JOIN dim_municipio m ON m.cod_ibge7 = d.cod_ibge7
  JOIN pop_municipio p ON p.cod_ibge7 = d.cod_ibge7 AND p.exercicio = d.exercicio
 WHERE c.codigo  = '10.301'
   AND d.estagio = 'Despesas Liquidadas'
 ORDER BY m.nome, d.exercicio;


-- ---------------------------------------------------------------------
-- B3. Distribuição do gasto per capita por exercício (assimetria).
--     A razão média/mediana e o p90/p10 mostram por que a análise usa
--     quintis e não um coeficiente de correlação.
-- ---------------------------------------------------------------------
SELECT exercicio,
       count(gasto_ab_pc)                                                     AS municipios,
       MIN(gasto_ab_pc)                                                       AS minimo,
       PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY gasto_ab_pc)::numeric(10,2) AS p10,
       PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY gasto_ab_pc)::numeric(10,2) AS mediana,
       ROUND(AVG(gasto_ab_pc), 2)                                             AS media,
       PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY gasto_ab_pc)::numeric(10,2) AS p90,
       MAX(gasto_ab_pc)                                                       AS maximo
  FROM mv_gasto_anual
 GROUP BY exercicio
 ORDER BY exercicio;


-- ---------------------------------------------------------------------
-- B4. Composição do orçamento municipal de saúde por subfunção (RS, 2024).
--     Só o nível 'subfuncao' — somar com o nível 'funcao' contaria o mesmo
--     real duas vezes.
-- ---------------------------------------------------------------------
SELECT c.codigo, c.nome AS subfuncao,
       SUM(d.valor)                                          AS liquidado,
       ROUND(100 * SUM(d.valor) / SUM(SUM(d.valor)) OVER (), 1) AS pct_da_saude
  FROM fato_despesa d
  JOIN dim_conta c ON c.conta = d.conta
 WHERE d.exercicio = 2024
   AND d.estagio   = 'Despesas Liquidadas'
   AND c.funcao    = '10'
   AND c.nivel     = 'subfuncao'
 GROUP BY c.codigo, c.nome
 ORDER BY liquidado DESC;


-- ---------------------------------------------------------------------
-- B5. A mesma composição para Porto Alegre, ao longo da série.
-- ---------------------------------------------------------------------
SELECT d.exercicio, c.codigo, c.nome AS subfuncao, d.valor,
       ROUND(100 * d.valor / SUM(d.valor) OVER (PARTITION BY d.exercicio), 1) AS pct
  FROM fato_despesa d
  JOIN dim_conta     c ON c.conta = d.conta
  JOIN dim_municipio m ON m.cod_ibge7 = d.cod_ibge7
 WHERE m.nome = 'Porto Alegre'
   AND d.estagio = 'Despesas Liquidadas'
   AND c.funcao = '10' AND c.nivel = 'subfuncao'
 ORDER BY d.exercicio, d.valor DESC;


-- ---------------------------------------------------------------------
-- B6. Resultado de cada indicador por município e quadrimestre, com a
--     versão do indicador vigente naquele quadrimestre.
-- ---------------------------------------------------------------------
SELECT m.nome AS municipio, f.quadrimestre, i.codigo, i.regime,
       f.percentual, i.meta,
       f.percentual >= i.meta AS atingiu_meta
  FROM fato_indicador f
  JOIN dim_indicador i ON i.id_indicador = f.id_indicador
  JOIN dim_municipio m ON m.cod_ibge6    = f.cod_ibge6
 WHERE m.nome = 'Porto Alegre'
 ORDER BY i.ordem, f.quadrimestre;


-- ---------------------------------------------------------------------
-- B7. Ordenação dos municípios por desempenho composto (média dos 7
--     indicadores) em 2024, com o gasto per capita ao lado.
-- ---------------------------------------------------------------------
SELECT m.nome AS municipio, g.porte, d.percentual AS desempenho_medio,
       g.gasto_ab_pc
  FROM vw_desempenho_composto d
  JOIN dim_municipio  m ON m.cod_ibge6 = d.cod_ibge6
  JOIN mv_gasto_anual g ON g.cod_ibge6 = d.cod_ibge6 AND g.exercicio = d.ano
 WHERE d.ano = 2024
 ORDER BY d.percentual DESC
 LIMIT 20;


-- ---------------------------------------------------------------------
-- B8. Evolução de cada indicador ao longo dos quadrimestres: média simples,
--     ponderada pela população e mediana, lado a lado.
-- ---------------------------------------------------------------------
SELECT codigo, quadrimestre, regime, meta,
       media_simples, media_ponderada, mediana, ajustado_portaria
  FROM mv_serie_estadual
 ORDER BY ordem, quadrimestre;


-- ---------------------------------------------------------------------
-- B9. Cobertura e completude de cada fonte.
--     a) FINBRA: municípios com a subfunção 10.301 declarada, por exercício.
-- ---------------------------------------------------------------------
SELECT exercicio,
       count(*)                         AS municipios,
       count(gasto_ab)                  AS com_gasto_ab,
       count(*) - count(gasto_ab)       AS lacunas
  FROM mv_gasto_anual
 GROUP BY exercicio ORDER BY exercicio;

--     b) SISAB: células preenchidas, nulas e zeradas por quadrimestre.
--        O percentual de zeros cai ao longo da série — reflexo da adesão ao
--        registro no SISAB, não de piora ou melhora assistencial.
SELECT f.quadrimestre,
       count(*)                                          AS celulas,
       count(*) FILTER (WHERE f.percentual IS NULL)      AS nulas,
       count(*) FILTER (WHERE f.percentual = 0)          AS zeradas,
       ROUND(100.0 * count(*) FILTER (WHERE f.percentual = 0) / count(*), 1) AS pct_zeradas
  FROM fato_indicador f
 GROUP BY f.quadrimestre ORDER BY f.quadrimestre;

--     c) Completude da média anual: municípios-indicador com menos de três
--        quadrimestres no ano.
SELECT ano, count(*) FILTER (WHERE n_quadrimestres < 3) AS medias_incompletas,
       count(*) AS medias
  FROM mv_desempenho_anual
 GROUP BY ano ORDER BY ano;


-- ---------------------------------------------------------------------
-- B10. Municípios e regiões: quantos municípios e quanta população em cada
--      coordenadoria regional de saúde (2024).
-- ---------------------------------------------------------------------
SELECT m.crs, count(*) AS municipios, SUM(g.populacao) AS populacao,
       ROUND(SUM(g.gasto_ab) / SUM(g.populacao), 2) AS gasto_ab_pc_regional
  FROM vw_municipio m
  JOIN mv_gasto_anual g ON g.cod_ibge7 = m.cod_ibge7 AND g.exercicio = 2024
 GROUP BY m.crs_numero, m.crs
 ORDER BY m.crs_numero;
