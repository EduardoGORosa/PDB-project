-- =====================================================================
-- CONSULTAS AVANÇADAS
-- Funções de janela, CTEs e agregação por faixa (NTILE).
-- Sem biblioteca estatística externa: tudo é SQL.
--
-- GRANULARIDADE TEMPORAL (CONTEXTO.md §3, armadilha 5): o gasto é anual e
-- os indicadores são quadrimestrais. A escolha adotada aqui é agregar os
-- indicadores para o ano pela MÉDIA dos quadrimestres, e não repetir o
-- gasto anual nos três quadrimestres. Repetir o gasto inflaria o n de
-- qualquer contagem por três sem acrescentar informação.
-- =====================================================================
SET search_path TO pbd, public;


-- ---------------------------------------------------------------------
-- A1. A PERGUNTA CENTRAL DO TRABALHO
--     Municípios que investem mais por habitante alcançam melhores
--     indicadores?
--
--     NTILE(5) divide os 497 municípios em quintis de gasto per capita
--     dentro de cada ano; para cada quintil, o desempenho médio.
--     Associação, não causalidade (CONTEXTO.md §6).
-- ---------------------------------------------------------------------
WITH desempenho_anual AS (
    -- indicadores quadrimestrais -> média anual, por município e indicador
    SELECT f.cod_ibge6,
           p.ano,
           i.codigo_indicador,
           AVG(f.percentual) AS percentual_medio
      FROM fato_indicador f
      JOIN dim_periodo   p ON p.quadrimestre = f.quadrimestre
      JOIN dim_indicador i ON i.id_indicador = f.id_indicador
     WHERE f.fonte = 'sisab'
     GROUP BY f.cod_ibge6, p.ano, i.codigo_indicador
),
quintis AS (
    SELECT g.cod_ibge6,
           g.exercicio,
           g.gasto_ab_per_capita,
           NTILE(5) OVER (PARTITION BY g.exercicio
                              ORDER BY g.gasto_ab_per_capita) AS quintil_gasto
      FROM vw_gasto_ab g
     WHERE g.gasto_ab_per_capita IS NOT NULL
)
SELECT q.exercicio,
       q.quintil_gasto,
       count(DISTINCT q.cod_ibge6)                       AS municipios,
       ROUND(MIN(q.gasto_ab_per_capita), 2)              AS gasto_min,
       ROUND(MAX(q.gasto_ab_per_capita), 2)              AS gasto_max,
       ROUND(AVG(d.percentual_medio)::numeric, 1)        AS desempenho_medio
  FROM quintis q
  JOIN desempenho_anual d
    ON d.cod_ibge6 = q.cod_ibge6 AND d.ano = q.exercicio
 WHERE q.exercicio = 2024
 GROUP BY q.exercicio, q.quintil_gasto
 ORDER BY q.exercicio, q.quintil_gasto;


-- ---------------------------------------------------------------------
-- A2. O DIFERENCIAL: quanto do salto de desempenho é regra, não serviço
--
--     LAG() compara cada quadrimestre com o anterior. O corte entre a NT
--     05/2020 e a NT 11/2022 cai entre 2021Q3 e 2022Q1. Se a variação
--     nesse corte for muito maior que a variação típica, o "ganho" é
--     efeito da mudança de regra — e a série não pode ser lida como
--     contínua.
-- ---------------------------------------------------------------------
WITH media_rs AS (
    SELECT i.codigo_indicador,
           f.quadrimestre,
           f.regime,
           AVG(f.percentual) AS media
      FROM fato_indicador f
      JOIN dim_indicador i ON i.id_indicador = f.id_indicador
     WHERE f.fonte = 'sisab'
     GROUP BY i.codigo_indicador, f.quadrimestre, f.regime
),
variacoes AS (
    SELECT codigo_indicador,
           quadrimestre,
           regime,
           media,
           LAG(media)  OVER j AS media_anterior,
           LAG(regime) OVER j AS regime_anterior,
           media - LAG(media) OVER j AS variacao_pp
      FROM media_rs
    WINDOW j AS (PARTITION BY codigo_indicador ORDER BY quadrimestre)
)
SELECT codigo_indicador,
       ROUND(AVG(ABS(variacao_pp)) FILTER (WHERE regime = regime_anterior), 2)
           AS variacao_tipica_pp,
       ROUND(MAX(variacao_pp)      FILTER (WHERE regime <> regime_anterior), 2)
           AS salto_na_troca_de_regime_pp,
       ROUND((MAX(variacao_pp) FILTER (WHERE regime <> regime_anterior))
             / NULLIF(AVG(ABS(variacao_pp)) FILTER (WHERE regime = regime_anterior), 0), 1)
           AS quantas_vezes_maior
  FROM variacoes
 WHERE media_anterior IS NOT NULL
 GROUP BY codigo_indicador
 ORDER BY quantas_vezes_maior DESC NULLS LAST;


-- ---------------------------------------------------------------------
-- A3. Porto Alegre como caso destacado
--
--     PERCENT_RANK() posiciona a capital na distribuição estadual de
--     gasto per capita, ano a ano. O CONTEXTO.md §2.1 registra a suspeita
--     de que ela esteja entre os 5% que menos gastam — esta consulta
--     responde com número, e para todos os anos, não só um.
-- ---------------------------------------------------------------------
WITH posicoes AS (
    SELECT exercicio,
           municipio,
           gasto_ab_per_capita,
           RANK()         OVER j AS posicao,
           count(*)       OVER (PARTITION BY exercicio) AS total,
           PERCENT_RANK() OVER j AS percentil
      FROM vw_gasto_ab
     WHERE gasto_ab_per_capita IS NOT NULL
    WINDOW j AS (PARTITION BY exercicio ORDER BY gasto_ab_per_capita)
)
SELECT exercicio,
       gasto_ab_per_capita,
       posicao || 'º de ' || total     AS posicao_no_rs,
       ROUND((100 * percentil)::numeric, 1)  AS percentil,
       CASE WHEN percentil <= 0.05 THEN 'sim' ELSE 'não' END
           AS entre_os_5pct_que_menos_gastam
  FROM posicoes
 WHERE municipio = 'Porto Alegre'
 ORDER BY exercicio;


-- ---------------------------------------------------------------------
-- A4. Média móvel de 3 quadrimestres, por município
--
--     Suaviza o ruído quadrimestral. A janela é reiniciada a cada
--     regime: atravessar o corte metodológico com a mesma média móvel
--     misturaria duas definições de indicador.
-- ---------------------------------------------------------------------
SELECT municipio,
       codigo_indicador,
       quadrimestre,
       regime,
       percentual,
       ROUND(AVG(percentual) OVER (
                 PARTITION BY cod_ibge6, codigo_indicador, regime
                 ORDER BY quadrimestre
                 ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1)
           AS media_movel_3q
  FROM vw_serie_sisab
 WHERE municipio        = 'Porto Alegre'
   AND codigo_indicador = 'cobertura_vacinal'
 ORDER BY quadrimestre;


-- ---------------------------------------------------------------------
-- A5. REGIME DE DENOMINADOR: quanto o resultado mudaria com outra regra
--
--     A API dá numerador e os três denominadores. Recalcular o indicador
--     com o denominador que a regra NÃO usou mede, em pontos percentuais,
--     o quanto do desempenho publicado é escolha de denominador.
--     Aritmética sobre os próprios campos — nada é inventado.
-- ---------------------------------------------------------------------
WITH contrafactual AS (
    SELECT municipio,
           codigo_indicador,
           quadrimestre,
           regime_denominador,
           percentual_quadrimestre                                   AS publicado,
           ROUND(100 * numerador / NULLIF(den_identificado, 0), 1)    AS se_identificado,
           ROUND(100 * numerador / NULLIF(den_estimado, 0), 1)        AS se_estimado,
           ABS(  ROUND(100 * numerador / NULLIF(den_identificado, 0), 1)
               - ROUND(100 * numerador / NULLIF(den_estimado, 0), 1)) AS amplitude_pp
      FROM vw_indicador_api
     WHERE numerador > 0
),
faixas AS (
    SELECT *,
           NTILE(4) OVER (ORDER BY amplitude_pp) AS quartil_sensibilidade
      FROM contrafactual
     WHERE amplitude_pp IS NOT NULL
)
SELECT quartil_sensibilidade,
       count(*)                        AS casos,
       ROUND(MIN(amplitude_pp), 1)     AS amplitude_min_pp,
       ROUND(AVG(amplitude_pp), 1)     AS amplitude_media_pp,
       ROUND(MAX(amplitude_pp), 1)     AS amplitude_max_pp
  FROM faixas
 GROUP BY quartil_sensibilidade
 ORDER BY quartil_sensibilidade;


-- ---------------------------------------------------------------------
-- A6. Os 15 casos em que a escolha do denominador mais pesou (2024)
-- ---------------------------------------------------------------------
SELECT municipio,
       codigo_indicador,
       quadrimestre,
       regime_denominador,
       numerador,
       den_identificado,
       den_estimado,
       percentual_quadrimestre                                  AS publicado,
       ROUND(100 * numerador / NULLIF(den_identificado, 0), 1)  AS se_identificado,
       ROUND(100 * numerador / NULLIF(den_estimado, 0), 1)      AS se_estimado
  FROM vw_indicador_api
 WHERE numerador > 0
   AND den_identificado > 0 AND den_estimado > 0
 ORDER BY ABS(  100 * numerador / den_identificado
              - 100 * numerador / den_estimado) DESC
 LIMIT 15;


-- ---------------------------------------------------------------------
-- A7. Trajetória do gasto: variação anual e acumulada desde 2020
--
--     LAG() para a variação ano a ano; FIRST_VALUE() para a base.
--     Os 10 municípios que mais expandiram o gasto per capita.
-- ---------------------------------------------------------------------
WITH serie AS (
    SELECT municipio,
           exercicio,
           gasto_ab_per_capita,
           LAG(gasto_ab_per_capita)         OVER j AS ano_anterior,
           FIRST_VALUE(gasto_ab_per_capita) OVER j AS base_2020
      FROM vw_gasto_ab
     WHERE gasto_ab_per_capita IS NOT NULL
    WINDOW j AS (PARTITION BY cod_ibge6 ORDER BY exercicio)
)
SELECT municipio,
       base_2020,
       gasto_ab_per_capita                                          AS em_2024,
       ROUND(100 * (gasto_ab_per_capita - ano_anterior) / ano_anterior, 1)
           AS var_sobre_2023_pct,
       ROUND(100 * (gasto_ab_per_capita - base_2020) / base_2020, 1)
           AS var_acumulada_pct
  FROM serie
 WHERE exercicio = 2024 AND base_2020 > 0
 ORDER BY var_acumulada_pct DESC
 LIMIT 10;


-- ---------------------------------------------------------------------
-- A8. Gasto x desempenho, quintil a quintil, com correlação
--
--     CORR() é agregado nativo do PostgreSQL — não é biblioteca externa.
--     Uma linha por indicador: a correlação entre gasto per capita e
--     desempenho em 2024, e o desempenho médio do quintil mais pobre
--     contra o do mais rico.
-- ---------------------------------------------------------------------
WITH base AS (
    SELECT g.cod_ibge6,
           g.gasto_ab_per_capita,
           i.codigo_indicador,
           AVG(f.percentual) AS desempenho
      FROM vw_gasto_ab g
      JOIN dim_periodo   p ON p.ano          = g.exercicio
      JOIN fato_indicador f ON f.cod_ibge6   = g.cod_ibge6
                           AND f.quadrimestre = p.quadrimestre
                           AND f.fonte        = 'sisab'
      JOIN dim_indicador i ON i.id_indicador = f.id_indicador
     WHERE g.exercicio = 2024 AND g.gasto_ab_per_capita IS NOT NULL
     GROUP BY g.cod_ibge6, g.gasto_ab_per_capita, i.codigo_indicador
),
com_quintil AS (
    SELECT *,
           NTILE(5) OVER (PARTITION BY codigo_indicador
                              ORDER BY gasto_ab_per_capita) AS quintil
      FROM base
)
SELECT codigo_indicador,
       count(*)                                                      AS municipios,
       ROUND(CORR(gasto_ab_per_capita, desempenho)::numeric, 3)      AS correlacao,
       ROUND(AVG(desempenho) FILTER (WHERE quintil = 1)::numeric, 1) AS q1_menor_gasto,
       ROUND(AVG(desempenho) FILTER (WHERE quintil = 5)::numeric, 1) AS q5_maior_gasto,
       ROUND((AVG(desempenho) FILTER (WHERE quintil = 5)
            - AVG(desempenho) FILTER (WHERE quintil = 1))::numeric, 1)
           AS diferenca_pp
  FROM com_quintil
 GROUP BY codigo_indicador
 ORDER BY correlacao DESC NULLS LAST;
