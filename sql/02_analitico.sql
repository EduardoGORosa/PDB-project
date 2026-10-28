-- =====================================================================
-- CAMADA ANALÍTICA
-- Visões e visões materializadas consumidas pelas consultas e pela
-- aplicação. As escolhas metodológicas da seção 4 do anteprojeto ficam
-- aqui, uma única vez:
--   * despesa no estágio 'Despesas Liquidadas';
--   * desempenho na visão "todas as equipes" (a única carregada);
--   * desempenho anual = média dos quadrimestres do ano, associada à
--     despesa do mesmo exercício;
--   * nenhuma média atravessa o corte entre regimes metodológicos.
-- =====================================================================
SET search_path TO pbd, public;

-- Faixas de porte populacional (classes usuais do IBGE). Usadas para
-- excluir os municípios pequenos, onde o percentual oscila por ter poucos
-- casos, e para descrever os grupos de referência.
CREATE OR REPLACE FUNCTION faixa_porte(pop INTEGER) RETURNS TEXT
LANGUAGE SQL IMMUTABLE AS $$
    SELECT CASE
        WHEN pop <    5000 THEN '1. até 5 mil'
        WHEN pop <   10000 THEN '2. 5 a 10 mil'
        WHEN pop <   20000 THEN '3. 10 a 20 mil'
        WHEN pop <   50000 THEN '4. 20 a 50 mil'
        WHEN pop <  100000 THEN '5. 50 a 100 mil'
        ELSE                    '6. mais de 100 mil'
    END
$$;

-- Município com região e coordenadoria já resolvidas.
CREATE VIEW vw_municipio AS
SELECT m.cod_ibge7, m.cod_ibge6, m.nome,
       r.regiao_codigo, r.nome AS regiao_nome,
       c.crs_numero, c.crs_numero || 'ª CRS – ' || c.sede AS crs
  FROM dim_municipio m
  LEFT JOIN dim_regiao_saude  r ON r.regiao_codigo = m.regiao_codigo
  LEFT JOIN dim_coordenadoria c ON c.crs_numero    = r.crs_numero;


-- ---------------------------------------------------------------------
-- Gasto em Atenção Básica por município e exercício.
-- Materializada: varre as ~700 mil linhas de fato_despesa.
-- gasto_ab é NULL quando o município não declarou a 10.301 no ano
-- (declaração truncada) — nunca zero, que seria afirmar gasto nulo.
-- ---------------------------------------------------------------------
CREATE MATERIALIZED VIEW mv_gasto_anual AS
WITH saude AS (
    SELECT d.cod_ibge7, d.exercicio,
           SUM(d.valor) FILTER (WHERE c.codigo = '10.301') AS gasto_ab,
           SUM(d.valor) FILTER (WHERE c.nivel = 'funcao')  AS gasto_saude
      FROM fato_despesa d
      JOIN dim_conta c ON c.conta = d.conta
     WHERE d.estagio = 'Despesas Liquidadas'
       AND c.funcao  = '10'
       AND c.nivel  IN ('funcao', 'subfuncao')
     GROUP BY d.cod_ibge7, d.exercicio
)
SELECT p.cod_ibge7,
       m.cod_ibge6,
       p.exercicio,
       p.populacao,
       faixa_porte(p.populacao)                          AS porte,
       s.gasto_ab,
       s.gasto_saude,
       ROUND(s.gasto_ab / p.populacao, 2)                AS gasto_ab_pc,
       ROUND(100 * s.gasto_ab / NULLIF(s.gasto_saude, 0), 1) AS pct_ab_na_saude
  FROM pop_municipio p
  JOIN dim_municipio m ON m.cod_ibge7 = p.cod_ibge7
  LEFT JOIN saude    s ON s.cod_ibge7 = p.cod_ibge7 AND s.exercicio = p.exercicio;

CREATE UNIQUE INDEX ON mv_gasto_anual (cod_ibge7, exercicio);


-- ---------------------------------------------------------------------
-- Desempenho anual por município e indicador: média dos quadrimestres do
-- ano. n_quadrimestres expõe a completude — uma média sobre menos
-- períodos aparece como diferença de desempenho se não for mostrada.
-- n_ajustados conta os quadrimestres em que o valor que pagou foi fixado
-- por portaria (tratados à parte nas análises).
-- ---------------------------------------------------------------------
CREATE MATERIALIZED VIEW mv_desempenho_anual AS
SELECT f.cod_ibge6,
       p.ano,
       i.codigo,
       i.ordem,
       f.regime,
       ROUND(AVG(f.percentual), 2)                         AS percentual,
       count(f.percentual)                                 AS n_quadrimestres,
       count(a.quadrimestre)                               AS n_ajustados
  FROM fato_indicador f
  JOIN dim_periodo   p ON p.quadrimestre = f.quadrimestre
  JOIN dim_indicador i ON i.id_indicador = f.id_indicador
  LEFT JOIN ajuste_financiamento a
         ON a.id_indicador = f.id_indicador AND a.quadrimestre = f.quadrimestre
 GROUP BY f.cod_ibge6, p.ano, i.codigo, i.ordem, f.regime;

CREATE UNIQUE INDEX ON mv_desempenho_anual (cod_ibge6, ano, codigo);


-- ---------------------------------------------------------------------
-- Painel anual: gasto e desempenho do mesmo município no mesmo exercício.
-- É a tabela que responde à pergunta central. Linhas sem gasto (2025, ou
-- declaração truncada) ficam de fora pelo INNER JOIN, de propósito.
-- ---------------------------------------------------------------------
CREATE VIEW vw_painel_anual AS
SELECT d.cod_ibge6, g.cod_ibge7, m.nome AS municipio,
       m.regiao_codigo, m.regiao_nome, m.crs_numero, m.crs,
       d.ano, d.codigo, d.ordem, d.regime,
       d.percentual, d.n_quadrimestres, d.n_ajustados,
       g.populacao, g.porte, g.gasto_ab, g.gasto_ab_pc, g.pct_ab_na_saude
  FROM mv_desempenho_anual d
  JOIN mv_gasto_anual g ON g.cod_ibge6 = d.cod_ibge6 AND g.exercicio = d.ano
  JOIN vw_municipio   m ON m.cod_ibge6 = d.cod_ibge6
 WHERE g.gasto_ab IS NOT NULL;


-- ---------------------------------------------------------------------
-- Desempenho composto: média dos 7 indicadores no ano. Não é o ISF oficial
-- (que pondera por peso e limita pela meta); serve só para ordenar
-- municípios quando não se escolhe um indicador. O ISF-like ponderado está
-- em isf_anual, abaixo.
-- ---------------------------------------------------------------------
CREATE VIEW vw_desempenho_composto AS
SELECT cod_ibge6, ano, regime,
       ROUND(AVG(percentual), 2) AS percentual,
       count(*)                  AS indicadores
  FROM mv_desempenho_anual
 GROUP BY cod_ibge6, ano, regime;


-- ---------------------------------------------------------------------
-- Indicador sintético no estilo do ISF do Previne Brasil: cada indicador
-- vale min(resultado/meta, 1) × 10, ponderado pelo peso da versão vigente.
-- Calculado sobre o ALCANCE REAL publicado no SISAB, e não sobre o valor
-- fixado por portaria — por isso não reproduz o ISF que pagou.
-- ---------------------------------------------------------------------
CREATE VIEW vw_isf_anual AS
SELECT d.cod_ibge6, d.ano, d.regime,
       ROUND(SUM(LEAST(d.percentual / i.meta, 1) * 10 * i.peso)
             / SUM(i.peso), 2)                          AS isf,
       count(*)                                         AS indicadores
  FROM mv_desempenho_anual d
  JOIN dim_indicador i ON i.codigo = d.codigo AND i.regime = d.regime
 WHERE i.meta > 0 AND i.peso IS NOT NULL
 GROUP BY d.cod_ibge6, d.ano, d.regime;


-- Série estadual por indicador e quadrimestre, com média simples e média
-- ponderada pela população do exercício lado a lado (anteprojeto, seção 4).
CREATE MATERIALIZED VIEW mv_serie_estadual AS
SELECT f.quadrimestre, p.ano, p.numero_quadrimestre, f.regime,
       i.codigo, i.ordem, i.meta,
       ROUND(AVG(f.percentual), 2)                                    AS media_simples,
       ROUND(SUM(f.percentual * g.populacao) / SUM(g.populacao), 2)   AS media_ponderada,
       ROUND(AVG(f.percentual) FILTER (WHERE g.populacao >= 5000), 2) AS media_sem_pequenos,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.percentual)      AS mediana,
       count(*) FILTER (WHERE f.percentual = 0)                       AS zeros,
       count(f.percentual)                                            AS municipios,
       bool_or(a.quadrimestre IS NOT NULL)                            AS ajustado_portaria
  FROM fato_indicador f
  JOIN dim_periodo   p ON p.quadrimestre = f.quadrimestre
  JOIN dim_indicador i ON i.id_indicador = f.id_indicador
  JOIN dim_municipio m ON m.cod_ibge6    = f.cod_ibge6
  -- a população do exercício; para anos sem FINBRA, a do exercício mais próximo
  JOIN LATERAL (
        SELECT pm.populacao FROM pop_municipio pm
         WHERE pm.cod_ibge7 = m.cod_ibge7
         ORDER BY abs(pm.exercicio - p.ano), pm.exercicio
         LIMIT 1) g ON TRUE
  LEFT JOIN ajuste_financiamento a
         ON a.id_indicador = f.id_indicador AND a.quadrimestre = f.quadrimestre
 GROUP BY f.quadrimestre, p.ano, p.numero_quadrimestre, f.regime, i.codigo, i.ordem, i.meta;

CREATE UNIQUE INDEX ON mv_serie_estadual (quadrimestre, codigo);


-- ---------------------------------------------------------------------
-- Grupo de referência por porte (junção reflexiva).
-- Cada município é comparado aos 20 municípios de população mais próxima no
-- mesmo ano, pela distância |ln(pop_b / pop_a)|. Uma faixa fixa (p. ex.
-- 2/3 a 3/2 da população) deixaria as maiores cidades sem grupo: nenhum
-- município do RS tem entre 2/3 e 3/2 da população de Porto Alegre.
-- ---------------------------------------------------------------------
CREATE MATERIALIZED VIEW mv_grupo_referencia AS
WITH painel AS (
    SELECT g.cod_ibge6, g.exercicio AS ano, g.populacao
      FROM mv_gasto_anual g
     WHERE g.gasto_ab_pc IS NOT NULL
),
distancias AS (
    SELECT a.cod_ibge6, a.ano, b.cod_ibge6 AS cod_par,
           ROW_NUMBER() OVER (PARTITION BY a.cod_ibge6, a.ano
                              ORDER BY abs(ln(b.populacao::numeric / a.populacao)), b.cod_ibge6) AS ordem
      FROM painel a
      JOIN painel b ON b.ano = a.ano AND b.cod_ibge6 <> a.cod_ibge6
)
SELECT cod_ibge6, ano, cod_par, ordem
  FROM distancias
 WHERE ordem <= 20;

CREATE UNIQUE INDEX ON mv_grupo_referencia (cod_ibge6, ano, cod_par);

-- Posição percentual do município no gasto e no desempenho dentro do seu
-- grupo, e os casos em que as duas posições caem em quartis opostos.
CREATE VIEW vw_posicao_no_grupo AS
WITH painel AS (
    SELECT g.cod_ibge6, g.exercicio AS ano, g.populacao, g.gasto_ab_pc,
           c.percentual AS desempenho
      FROM mv_gasto_anual g
      JOIN vw_desempenho_composto c ON c.cod_ibge6 = g.cod_ibge6 AND c.ano = g.exercicio
     WHERE g.gasto_ab_pc IS NOT NULL
),
pares AS (
    SELECT a.cod_ibge6, a.ano, a.populacao, a.gasto_ab_pc, a.desempenho,
           count(*)                                              AS tamanho_grupo,
           MIN(b.populacao) || ' – ' || MAX(b.populacao)         AS faixa_populacao_grupo,
           count(*) FILTER (WHERE b.gasto_ab_pc < a.gasto_ab_pc) AS abaixo_no_gasto,
           count(*) FILTER (WHERE b.desempenho  < a.desempenho)  AS abaixo_no_desempenho,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY b.gasto_ab_pc) AS gasto_mediano_grupo,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY b.desempenho)  AS desempenho_mediano_grupo
      FROM painel a
      JOIN mv_grupo_referencia r ON r.cod_ibge6 = a.cod_ibge6 AND r.ano = a.ano
      JOIN painel b              ON b.cod_ibge6 = r.cod_par   AND b.ano = r.ano
     GROUP BY a.cod_ibge6, a.ano, a.populacao, a.gasto_ab_pc, a.desempenho
)
SELECT p.*,
       ROUND(100.0 * abaixo_no_gasto      / tamanho_grupo, 0) AS posicao_gasto,
       ROUND(100.0 * abaixo_no_desempenho / tamanho_grupo, 0) AS posicao_desempenho,
       CASE
         WHEN 100.0 * abaixo_no_gasto / tamanho_grupo >= 75
          AND 100.0 * abaixo_no_desempenho / tamanho_grupo <= 25 THEN 'gasta mais, rende menos'
         WHEN 100.0 * abaixo_no_gasto / tamanho_grupo <= 25
          AND 100.0 * abaixo_no_desempenho / tamanho_grupo >= 75 THEN 'gasta menos, rende mais'
       END AS discrepancia
  FROM pares p;


-- ---------------------------------------------------------------------
-- Gasto atípico: per capita abaixo de 10% da mediana estadual do ano.
-- Valores assim (R$ 0,71 por habitante em 2021) indicam declaração com a
-- despesa classificada em outra subfunção, não ausência de atenção básica.
-- Vieira et al. (2022) documentam essa subestimação da 10.301.
-- ---------------------------------------------------------------------
CREATE VIEW vw_gasto_atipico AS
WITH mediana AS (
    SELECT exercicio, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gasto_ab_pc) AS med
      FROM mv_gasto_anual GROUP BY exercicio
)
SELECT g.cod_ibge7, m.nome, g.exercicio, g.populacao, g.gasto_ab, g.gasto_ab_pc,
       ROUND(md.med::numeric, 2) AS mediana_estadual, g.pct_ab_na_saude
  FROM mv_gasto_anual g
  JOIN mediana md USING (exercicio)
  JOIN dim_municipio m USING (cod_ibge7)
 WHERE g.gasto_ab_pc < 0.1 * md.med;
