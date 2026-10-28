-- =====================================================================
-- CONSULTAS BÁSICAS
-- Seleção, projeção, junção, agregação simples e ordenação.
-- =====================================================================
SET search_path TO pbd, public;

-- ---------------------------------------------------------------------
-- B1. Dicionário dos indicadores: as duas versões de cada um.
--     A mudança de nome entre as Notas Técnicas é a mudança de regra
--     aparecendo no próprio dado.
-- ---------------------------------------------------------------------
SELECT codigo_indicador,
       regime,
       vigencia_inicio || ' .. ' || vigencia_fim AS cobertura,
       nota_tecnica,
       nome
  FROM dim_indicador
 ORDER BY codigo_indicador, vigencia_inicio;


-- ---------------------------------------------------------------------
-- B2. Os 10 municípios que mais gastaram em Atenção Básica em 2024,
--     em valor absoluto.
-- ---------------------------------------------------------------------
SELECT municipio, populacao, gasto_ab, gasto_ab_per_capita
  FROM vw_gasto_ab
 WHERE exercicio = 2024
 ORDER BY gasto_ab DESC
 LIMIT 10;


-- ---------------------------------------------------------------------
-- B3. Distribuição do gasto per capita em Atenção Básica, por exercício.
--     Note o salto de cobertura: 2018 e 2019 não existem no FINBRA
--     baixado, e a série de gasto começa em 2020.
-- ---------------------------------------------------------------------
SELECT exercicio,
       count(*)                                       AS municipios,
       MIN(gasto_ab_per_capita)                       AS minimo,
       ROUND(AVG(gasto_ab_per_capita), 2)             AS media,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gasto_ab_per_capita) AS mediana,
       MAX(gasto_ab_per_capita)                       AS maximo
  FROM vw_gasto_ab
 GROUP BY exercicio
 ORDER BY exercicio;


-- ---------------------------------------------------------------------
-- B4. Porto Alegre: composição do gasto em saúde por subfunção, 2024.
--     Só o nível 'subfuncao' — misturar com o nível 'funcao' contaria
--     o mesmo real duas vezes.
-- ---------------------------------------------------------------------
SELECT c.codigo,
       c.nome                                         AS subfuncao,
       d.valor,
       ROUND(100.0 * d.valor / SUM(d.valor) OVER (), 1) AS pct_da_saude
  FROM fato_despesa d
  JOIN dim_conta     c ON c.conta     = d.conta
  JOIN dim_municipio m ON m.cod_ibge6 = d.cod_ibge6
 WHERE m.nome     = 'Porto Alegre'
   AND d.exercicio = 2024
   AND d.estagio   = 'Despesas Empenhadas'
   AND c.funcao    = '10'
   AND c.nivel     = 'subfuncao'
 ORDER BY d.valor DESC;


-- ---------------------------------------------------------------------
-- B5. Desempenho médio do RS por indicador e quadrimestre.
-- ---------------------------------------------------------------------
SELECT quadrimestre,
       regime,
       codigo_indicador,
       ROUND(AVG(percentual), 1) AS media_rs,
       MIN(percentual)           AS pior,
       MAX(percentual)           AS melhor
  FROM vw_serie_sisab
 GROUP BY quadrimestre, regime, codigo_indicador
 ORDER BY codigo_indicador, quadrimestre;


-- ---------------------------------------------------------------------
-- B6. Os 15 municípios com pior cobertura vacinal no último quadrimestre
--     de 2024.
-- ---------------------------------------------------------------------
SELECT municipio, percentual
  FROM vw_serie_sisab
 WHERE codigo_indicador = 'cobertura_vacinal'
   AND quadrimestre     = '2024Q3'
 ORDER BY percentual ASC, municipio
 LIMIT 15;


-- ---------------------------------------------------------------------
-- B7. Quantos municípios cada faixa de desempenho contém, por indicador,
--     em 2024Q3.
-- ---------------------------------------------------------------------
SELECT codigo_indicador,
       count(*) FILTER (WHERE percentual <  25) AS ate_25,
       count(*) FILTER (WHERE percentual >= 25 AND percentual < 50) AS de_25_a_50,
       count(*) FILTER (WHERE percentual >= 50 AND percentual < 75) AS de_50_a_75,
       count(*) FILTER (WHERE percentual >= 75) AS acima_de_75
  FROM vw_serie_sisab
 WHERE quadrimestre = '2024Q3'
 GROUP BY codigo_indicador
 ORDER BY codigo_indicador;


-- ---------------------------------------------------------------------
-- B8. SISAB x API: as duas fontes concordam sobre 2024?
--     Mesmo município, mesmo indicador, mesmo quadrimestre, métodos
--     diferentes. A divergência é achado, não erro de carga.
-- ---------------------------------------------------------------------
SELECT i.codigo_indicador,
       count(*)                                                       AS pares,
       count(*) FILTER (WHERE s.percentual = a.percentual)            AS identicos,
       ROUND(100.0 * count(*) FILTER (WHERE s.percentual = a.percentual)
             / count(*), 1)                                           AS pct_identicos,
       ROUND(AVG(ABS(s.percentual - a.percentual)), 2)                AS erro_medio_pp,
       MAX(ABS(s.percentual - a.percentual))                          AS maior_diferenca_pp
  FROM fato_indicador s
  JOIN fato_indicador a
    ON  a.cod_ibge6    = s.cod_ibge6
    AND a.quadrimestre = s.quadrimestre
    AND a.id_indicador = s.id_indicador
    AND a.fonte        = 'api'
    AND a.visao_equipe = 'homologadas'
  JOIN dim_indicador i ON i.id_indicador = s.id_indicador
 WHERE s.fonte = 'sisab'
 GROUP BY i.codigo_indicador
 ORDER BY pct_identicos;


-- ---------------------------------------------------------------------
-- B9. As três visões de equipe da API são iguais entre si?
--     O CONTEXTO.md supunha que sim. Esta consulta responde com dado.
-- ---------------------------------------------------------------------
SELECT count(*)                                                AS grupos,
       count(*) FILTER (WHERE geral = homologadas
                          AND validas = homologadas)           AS identicos_nas_3,
       count(*) FILTER (WHERE geral <> homologadas)             AS geral_difere,
       count(*) FILTER (WHERE validas <> homologadas)           AS validas_difere,
       MAX(ABS(geral - homologadas))                            AS maior_dif_geral_pp
  FROM (SELECT cod_ibge6, quadrimestre, id_indicador,
               MAX(percentual) FILTER (WHERE visao_equipe = 'geral')       AS geral,
               MAX(percentual) FILTER (WHERE visao_equipe = 'homologadas') AS homologadas,
               MAX(percentual) FILTER (WHERE visao_equipe = 'validas')     AS validas
          FROM fato_indicador
         WHERE fonte = 'api'
         GROUP BY cod_ibge6, quadrimestre, id_indicador) t;


-- ---------------------------------------------------------------------
-- B10. Qual denominador a regra usou, por indicador (2024, homologadas).
--      É o insumo da análise de regime de denominador.
-- ---------------------------------------------------------------------
SELECT codigo_indicador,
       regime_denominador,
       count(*) AS municipios_quadrimestres
  FROM vw_indicador_api
 GROUP BY codigo_indicador, regime_denominador
 ORDER BY codigo_indicador, count(*) DESC;
