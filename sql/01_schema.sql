-- =====================================================================
-- INF01006 — Projeto de Banco de Dados (UFRGS)
-- Gasto municipal em Atenção Básica x desempenho na Atenção Primária
-- 497 municípios do Rio Grande do Sul
--
-- Esquema relacional. Segue o modelo do CONTEXTO.md §5, com três desvios
-- deliberados, marcados adiante com "DESVIO DO CONTEXTO.md".
-- =====================================================================

DROP SCHEMA IF EXISTS pbd CASCADE;
CREATE SCHEMA pbd;
SET search_path TO pbd, public;


-- ---------------------------------------------------------------------
-- DIMENSÕES
-- ---------------------------------------------------------------------

-- DESVIO DO CONTEXTO.md (1/3): a chave do município é o código de 6 dígitos,
-- não o de 7. FINBRA usa 7 dígitos (o último é verificador); SISAB e API usam
-- 6. Resolver `cod_ibge7 / 10` uma única vez, na carga, e chavear tudo por
-- cod_ibge6 evita que a divisão tenha de ser repetida — e lembrada — em cada
-- consulta. O código de 7 dígitos fica preservado na coluna cod_ibge7.
CREATE TABLE dim_municipio (
    cod_ibge6   INTEGER     PRIMARY KEY,
    cod_ibge7   INTEGER     NOT NULL UNIQUE,
    nome        TEXT        NOT NULL,
    uf          CHAR(2)     NOT NULL,
    CONSTRAINT municipio_codigos_coerentes CHECK (cod_ibge7 / 10 = cod_ibge6),
    CONSTRAINT municipio_ibge6_rs CHECK (cod_ibge6 BETWEEN 430000 AND 439999)
);

-- DESVIO DO CONTEXTO.md (2/3): o CONTEXTO.md põe `populacao_finbra` e
-- `populacao_sisab` como colunas de dim_municipio. Mas a população do FINBRA
-- muda a cada exercício e a da API muda a cada quadrimestre — não são
-- atributos do município, são fatos datados. Guardar como coluna única
-- obrigaria a escolher em silêncio um ano de referência.
CREATE TABLE populacao_municipio (
    cod_ibge6   INTEGER  NOT NULL REFERENCES dim_municipio,
    ano         SMALLINT NOT NULL,
    fonte       TEXT     NOT NULL CHECK (fonte IN ('finbra', 'api')),
    populacao   INTEGER  NOT NULL CHECK (populacao > 0),
    PRIMARY KEY (cod_ibge6, ano, fonte)
);

CREATE TABLE dim_periodo (
    quadrimestre        CHAR(6)  PRIMARY KEY,   -- '2018Q1'
    ano                 SMALLINT NOT NULL,
    numero_quadrimestre SMALLINT NOT NULL CHECK (numero_quadrimestre BETWEEN 1 AND 3),
    -- Competência de referência (AAAAMM). Só a API informa; NULL onde só o
    -- SISAB cobre o período. Não é inferida.
    competencia         INTEGER,
    -- Regime metodológico vigente. NT 05/2020 até 2021Q3; NT 11/2022 a partir
    -- de 2022Q1 (CONTEXTO.md §4).
    regime              TEXT     NOT NULL CHECK (regime IN ('NT 05/2020', 'NT 11/2022')),
    CONSTRAINT periodo_formato CHECK (quadrimestre ~ '^\d{4}Q[1-3]$'),
    CONSTRAINT periodo_coerente CHECK (
        ano = LEFT(quadrimestre, 4)::SMALLINT
        AND numero_quadrimestre = RIGHT(quadrimestre, 1)::SMALLINT
    ),
    CONSTRAINT periodo_regime_coerente CHECK (
        regime = CASE WHEN quadrimestre < '2022Q1'
                      THEN 'NT 05/2020' ELSE 'NT 11/2022' END
    )
);

-- A dim_indicador NÃO existe em nenhuma fonte: nem o SISAB nem a API entregam
-- nome, regra ou meta. É tabela mantida por nós, a partir das Notas Técnicas.
--
-- É VERSIONADA: cada indicador tem uma linha por regime metodológico, porque
-- a regra de cálculo mudou no meio da série. O `codigo_indicador` é o slug
-- estável que liga as duas versões do mesmo indicador; o `id_indicador` é a
-- chave de uma versão específica. Um fato aponta para a VERSÃO, nunca para o
-- indicador em abstrato — é isso que impede comparar 2021 com 2022 como se
-- fossem a mesma medida.
CREATE TABLE dim_indicador (
    id_indicador     SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_indicador TEXT     NOT NULL,   -- slug estável entre regimes
    regime           TEXT     NOT NULL CHECK (regime IN ('NT 05/2020', 'NT 11/2022')),
    nome             TEXT     NOT NULL,   -- como a fonte o nomeia NAQUELE regime
    -- `codigo_tipo_indicador` da API DEMAS. Preenchido apenas onde a
    -- correspondência foi verificada contra os valores do SISAB; NULL onde a
    -- API não publica o indicador.
    codigo_api       SMALLINT,
    -- Os quatro campos abaixo dependem das Notas Técnicas, que não estão no
    -- repositório (não há docs/). Ficam NULL até que os documentos entrem —
    -- preencher com valor plausível seria inventar dado.
    regra_numerador   TEXT,
    regra_denominador TEXT,
    meta              NUMERIC(5,2),
    peso              NUMERIC(5,3),
    nota_tecnica      TEXT     NOT NULL,
    vigencia_inicio   CHAR(6)  NOT NULL,
    vigencia_fim      CHAR(6),             -- NULL = vigente no fim da série
    UNIQUE (codigo_indicador, regime)
);

-- Estágios da execução da despesa. O FINBRA traz os cinco; somá-los seria
-- contar o mesmo empenho várias vezes.
CREATE TABLE dim_estagio_despesa (
    estagio  TEXT PRIMARY KEY,
    ordem    SMALLINT NOT NULL UNIQUE
);

-- Classificação funcional da despesa.
--
-- `nivel` é o que impede a dupla contagem. A hierarquia do FINBRA é:
--     total     'Despesas Exceto Intraorçamentárias'
--     funcao    '10 - Saúde'
--     subfuncao '10.301 - Atenção Básica', ..., 'FU10 - Demais Subfunções'
--
-- Verificado em Porto Alegre/2024: a soma das subfunções nomeadas MAIS o
-- resíduo FU10 reproduz '10 - Saúde' ao centavo (R$ 2.799.019.820,54). Ou
-- seja, FU10 pertence ao total, e a armadilha não é somá-lo com as demais
-- subfunções — é somar o nível 'funcao' junto com o nível 'subfuncao'.
-- Toda consulta deve filtrar por um único nivel.
CREATE TABLE dim_conta (
    conta       TEXT    PRIMARY KEY,       -- rótulo original, como vem do CSV
    nivel       TEXT    NOT NULL CHECK (nivel IN ('total', 'funcao', 'subfuncao')),
    codigo      TEXT,                      -- '10', '10.301', 'FU10'; NULL nos totais
    funcao      TEXT,                      -- '10'
    subfuncao   TEXT,                      -- '301'; NULL na função e nos totais
    nome        TEXT    NOT NULL,          -- 'Atenção Básica'
    eh_residual BOOLEAN NOT NULL DEFAULT FALSE   -- as contas 'FUnn - Demais Subfunções'
);


-- ---------------------------------------------------------------------
-- FATOS
-- ---------------------------------------------------------------------

-- Granularidade: município x exercício x estágio x conta.
-- Verificado: (cod_ibge, coluna, conta) é único dentro de cada arquivo anual.
CREATE TABLE fato_despesa (
    cod_ibge6  INTEGER       NOT NULL REFERENCES dim_municipio,
    exercicio  SMALLINT      NOT NULL,
    estagio    TEXT          NOT NULL REFERENCES dim_estagio_despesa,
    conta      TEXT          NOT NULL REFERENCES dim_conta,
    valor      NUMERIC(18,2) NOT NULL,
    PRIMARY KEY (cod_ibge6, exercicio, estagio, conta)
);

-- Granularidade: município x quadrimestre x versão do indicador x visão x fonte.
--
-- DESVIO DO CONTEXTO.md (3/3): `fonte` entra na chave primária. SISAB e API
-- descrevem 2024 ao mesmo tempo, com métodos diferentes, e as duas medidas
-- precisam coexistir para que a comparação entre elas seja possível — ela é
-- parte do trabalho, não um conflito a resolver na carga.
--
-- O SISAB só publica o percentual alcançado. A API é a única fonte com
-- numerador e os três denominadores, e só cobre 2024. Daí as colunas
-- nuláveis: não são dado faltante, são a fronteira entre as duas fontes.
CREATE TABLE fato_indicador (
    cod_ibge6        INTEGER  NOT NULL REFERENCES dim_municipio,
    quadrimestre     CHAR(6)  NOT NULL REFERENCES dim_periodo,
    id_indicador     SMALLINT NOT NULL REFERENCES dim_indicador,
    -- 'geral' | 'homologadas' | 'validas' na API; 'nao_informado' no SISAB,
    -- que não expõe qual visão gerou o relatório baixado.
    visao_equipe     TEXT     NOT NULL,
    fonte            TEXT     NOT NULL CHECK (fonte IN ('sisab', 'api')),
    -- Regime metodológico da linha. Redundante com dim_periodo e com
    -- dim_indicador, e mantido de propósito: é a informação que não pode ser
    -- perdida ao ler uma linha isolada da série.
    regime           TEXT     NOT NULL CHECK (regime IN ('NT 05/2020', 'NT 11/2022')),

    -- Resultado do indicador. No SISAB, o percentual publicado. Na API,
    -- `percentual_quadrimestre` (= numerador / denominador_utilizador).
    percentual       NUMERIC(6,2) CHECK (percentual BETWEEN 0 AND 100),

    -- Só a API preenche daqui para baixo.
    numerador        NUMERIC(14,2),
    den_identificado NUMERIC(14,2),
    den_estimado     NUMERIC(14,2),
    den_utilizado    NUMERIC(14,2),
    -- Campo `percentual` da API. NÃO é o resultado do indicador: passa de 100
    -- e sua definição não foi encontrada em nenhum dicionário. Carregado como
    -- veio, com nome que impeça o uso acidental.
    percentual_api_indefinido NUMERIC(10,2),
    cadastro         NUMERIC(14,2),
    base_externa     INTEGER,

    PRIMARY KEY (cod_ibge6, quadrimestre, id_indicador, visao_equipe, fonte),

    -- O SISAB não tem numerador nem denominadores; a API sempre tem.
    CONSTRAINT indicador_fonte_coerente CHECK (
        (fonte = 'sisab' AND numerador IS NULL AND den_utilizado IS NULL)
        OR fonte = 'api'
    )
);

CREATE INDEX ix_despesa_conta      ON fato_despesa (conta, exercicio);
CREATE INDEX ix_despesa_exercicio  ON fato_despesa (exercicio);
CREATE INDEX ix_indicador_periodo  ON fato_indicador (quadrimestre, id_indicador);
CREATE INDEX ix_indicador_fonte    ON fato_indicador (fonte);


-- ---------------------------------------------------------------------
-- VISÕES DE APOIO
-- ---------------------------------------------------------------------

-- Gasto empenhado em Atenção Básica (subfunção 10.301) por município e ano,
-- com a população do exercício e o gasto per capita já resolvidos.
-- Encapsula as três escolhas que a consulta crua exigiria repetir: estágio
-- 'Despesas Empenhadas', conta '10.301', nível 'subfuncao'.
CREATE VIEW vw_gasto_ab AS
SELECT d.cod_ibge6,
       m.nome            AS municipio,
       d.exercicio,
       d.valor           AS gasto_ab,
       p.populacao,
       ROUND(d.valor / p.populacao, 2) AS gasto_ab_per_capita
  FROM fato_despesa d
  JOIN dim_municipio m       ON m.cod_ibge6 = d.cod_ibge6
  JOIN dim_conta     c       ON c.conta     = d.conta
  LEFT JOIN populacao_municipio p
         ON p.cod_ibge6 = d.cod_ibge6
        AND p.ano       = d.exercicio
        AND p.fonte     = 'finbra'
 WHERE d.estagio = 'Despesas Empenhadas'
   AND c.codigo  = '10.301';

-- Série do SISAB — a espinha dorsal: 7 indicadores x 2018..2025, com o slug
-- estável e o regime já resolvidos.
CREATE VIEW vw_serie_sisab AS
SELECT f.cod_ibge6,
       m.nome              AS municipio,
       f.quadrimestre,
       p.ano,
       i.codigo_indicador,
       i.nome              AS nome_indicador,
       f.regime,
       f.percentual
  FROM fato_indicador f
  JOIN dim_municipio m ON m.cod_ibge6    = f.cod_ibge6
  JOIN dim_periodo   p ON p.quadrimestre = f.quadrimestre
  JOIN dim_indicador i ON i.id_indicador = f.id_indicador
 WHERE f.fonte = 'sisab';

-- Recorte da API sob a visão de equipes ligada ao financiamento.
--
-- É AQUI que a escolha metodológica por 'homologadas' é feita — e não na
-- carga, porque as três visões não são cópias uma da outra: coincidem em
-- 83,5% dos grupos (município x quadrimestre x indicador) de 2024 e divergem
-- em 16,5%, com até 79 pontos percentuais de diferença. Filtrar na carga
-- destruiria dado; filtrar aqui deixa a escolha explícita e reversível.
CREATE VIEW vw_indicador_api AS
SELECT f.cod_ibge6,
       m.nome  AS municipio,
       f.quadrimestre,
       i.codigo_indicador,
       i.codigo_api,
       f.percentual        AS percentual_quadrimestre,
       f.numerador,
       f.den_identificado,
       f.den_estimado,
       f.den_utilizado,
       -- Qual dos três denominadores a regra efetivamente usou. É a pergunta
       -- do "regime de denominador": o utilizado não é sempre o mesmo dos
       -- outros dois, e qual deles vence muda de município para município.
       CASE
           WHEN f.den_utilizado IS NULL                    THEN NULL
           WHEN f.den_utilizado = f.den_identificado
            AND f.den_utilizado = f.den_estimado           THEN 'coincidem'
           WHEN f.den_utilizado = f.den_identificado       THEN 'identificado'
           WHEN f.den_utilizado = f.den_estimado           THEN 'estimado'
           ELSE 'nenhum'
       END AS regime_denominador
  FROM fato_indicador f
  JOIN dim_municipio m ON m.cod_ibge6    = f.cod_ibge6
  JOIN dim_indicador i ON i.id_indicador = f.id_indicador
 WHERE f.fonte = 'api'
   AND f.visao_equipe = 'homologadas';
