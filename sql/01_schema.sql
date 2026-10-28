-- =====================================================================
-- INF01006 — Projeto de Banco de Dados (UFRGS)
-- Gasto municipal em Atenção Básica x desempenho na Atenção Primária
-- 497 municípios do Rio Grande do Sul, 2018–2024
--
-- Esquema relacional, conforme a seção 3 do anteprojeto.
-- Fontes: FINBRA/SICONFI (gasto), SISAB (indicadores), Notas Técnicas e
-- Portarias do Ministério da Saúde (regras dos indicadores) e SES-RS
-- (regiões de saúde e coordenadorias).
-- =====================================================================

DROP SCHEMA IF EXISTS pbd CASCADE;
CREATE SCHEMA pbd;
SET search_path TO pbd, public;


-- ---------------------------------------------------------------------
-- DIVISÃO REGIONAL DA SAÚDE (SES-RS)
-- Nenhuma das duas fontes traz a região; ela vem da divisão oficial da
-- Secretaria Estadual da Saúde. Cada região de saúde pertence a uma única
-- coordenadoria (CRS), por isso a coordenadoria é atributo da região e não
-- do município — guardá-la no município permitiria dois municípios da mesma
-- região em coordenadorias diferentes.
-- ---------------------------------------------------------------------
CREATE TABLE dim_coordenadoria (
    crs_numero  SMALLINT PRIMARY KEY CHECK (crs_numero BETWEEN 1 AND 18),
    sede        TEXT     NOT NULL
);

CREATE TABLE dim_regiao_saude (
    regiao_codigo SMALLINT PRIMARY KEY CHECK (regiao_codigo BETWEEN 1 AND 30),
    nome          TEXT     NOT NULL,
    crs_numero    SMALLINT NOT NULL REFERENCES dim_coordenadoria
);


-- ---------------------------------------------------------------------
-- MUNICÍPIO
-- O FINBRA identifica o município pelo código IBGE de 7 dígitos (o último é
-- verificador); o SISAB, pelo de 6. A relação cod_ibge6 = cod_ibge7 / 10 é
-- garantida por CHECK, e cod_ibge6 é UNIQUE para poder ser alvo de chave
-- estrangeira da tabela de desempenho.
-- ---------------------------------------------------------------------
CREATE TABLE dim_municipio (
    cod_ibge7     INTEGER  PRIMARY KEY,
    cod_ibge6     INTEGER  NOT NULL UNIQUE,
    nome          TEXT     NOT NULL,
    uf            CHAR(2)  NOT NULL DEFAULT 'RS',
    regiao_codigo SMALLINT REFERENCES dim_regiao_saude,
    CONSTRAINT municipio_codigos_coerentes CHECK (cod_ibge7 / 10 = cod_ibge6),
    CONSTRAINT municipio_rs CHECK (cod_ibge7 BETWEEN 4300000 AND 4399999)
);

-- A população muda a cada exercício. Como atributo fixo do município, todo o
-- gasto per capita da série seria calculado sobre a mesma base.
CREATE TABLE pop_municipio (
    cod_ibge7  INTEGER  NOT NULL REFERENCES dim_municipio,
    exercicio  SMALLINT NOT NULL,
    populacao  INTEGER  NOT NULL CHECK (populacao > 0),
    PRIMARY KEY (cod_ibge7, exercicio)
);


-- ---------------------------------------------------------------------
-- TEMPO E REGIME METODOLÓGICO
-- ---------------------------------------------------------------------
CREATE TABLE dim_regime (
    regime        TEXT    PRIMARY KEY,
    descricao     TEXT    NOT NULL,
    inicio        CHAR(6) NOT NULL,
    fim           CHAR(6)                 -- NULL = até o fim da série
);

CREATE TABLE dim_periodo (
    quadrimestre        CHAR(6)  PRIMARY KEY,           -- '2018Q1'
    ano                 SMALLINT NOT NULL,
    numero_quadrimestre SMALLINT NOT NULL CHECK (numero_quadrimestre BETWEEN 1 AND 3),
    regime_metodologico TEXT     NOT NULL REFERENCES dim_regime,
    -- Se o resultado deste quadrimestre de DADOS influiu no repasse federal.
    -- O pagamento usa o dado com um quadrimestre de defasagem (NT 11/2022,
    -- §5.6); de 2020 a 2021 os repasses foram fixados em 100% do potencial,
    -- e o Previne deixou de pagar por desempenho em maio/2024.
    efeito_financeiro   TEXT     NOT NULL CHECK (efeito_financeiro IN
                            ('anterior ao programa', 'sem efeito', 'parcial',
                             'pleno', 'posterior ao programa')),
    CONSTRAINT periodo_formato CHECK (quadrimestre ~ '^\d{4}Q[1-3]$'),
    CONSTRAINT periodo_coerente CHECK (
        ano = LEFT(quadrimestre, 4)::SMALLINT
        AND numero_quadrimestre = RIGHT(quadrimestre, 1)::SMALLINT),
    -- alvo da FK composta de fato_indicador
    UNIQUE (quadrimestre, regime_metodologico)
);


-- ---------------------------------------------------------------------
-- INDICADOR — dimensão VERSIONADA
-- Nenhuma fonte entrega esta tabela: ela é construída a partir das Notas
-- Técnicas. A regra de cálculo mudou em 2022, então cada versão de um
-- indicador é uma linha própria, com sua regra, sua meta, seu intervalo de
-- vigência e o documento que a definiu. `codigo` é o identificador estável
-- que liga as versões; a chave é `id_indicador`, porque `codigo` se repete.
-- ---------------------------------------------------------------------
CREATE TABLE dim_indicador (
    id_indicador      SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo            TEXT     NOT NULL,      -- 'cobertura_vacinal'
    ordem             SMALLINT NOT NULL CHECK (ordem BETWEEN 1 AND 7),
    nome              TEXT     NOT NULL,      -- como a fonte o nomeia na versão
    regra_numerador   TEXT     NOT NULL,
    regra_denominador TEXT     NOT NULL,
    meta              NUMERIC(5,2) CHECK (meta BETWEEN 0 AND 100),
    peso              SMALLINT CHECK (peso > 0),
    nota_tecnica      TEXT     NOT NULL,
    regime            TEXT     NOT NULL REFERENCES dim_regime,
    vigencia_inicio   CHAR(6)  NOT NULL REFERENCES dim_periodo,
    vigencia_fim      CHAR(6)  REFERENCES dim_periodo,   -- NULL = vigente
    CHECK (vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio),
    UNIQUE (codigo, regime),
    UNIQUE (id_indicador, regime)          -- alvo da FK composta
);

-- Quadrimestres em que um ato normativo fixou o resultado de um indicador
-- APENAS para fins de financiamento (Portarias GM/MS nº 166/2021,
-- nº 2.396/2021 e nº 102/2022, art. 6º-A).
-- O percentual publicado no SISAB continua sendo o alcance real; esta tabela
-- registra que o valor que pagou foi outro, para que esses períodos possam
-- ser identificados e tratados à parte. É uma entidade fraca de
-- dim_indicador × dim_periodo.
CREATE TABLE ajuste_financiamento (
    id_indicador       SMALLINT NOT NULL REFERENCES dim_indicador,
    quadrimestre       CHAR(6)  NOT NULL REFERENCES dim_periodo,
    regra              TEXT     NOT NULL,   -- o que foi considerado no pagamento
    ato_normativo      TEXT     NOT NULL,
    observacao         TEXT,
    PRIMARY KEY (id_indicador, quadrimestre)
);


-- ---------------------------------------------------------------------
-- DESPESA
-- ---------------------------------------------------------------------
-- Estágios da execução. O FINBRA traz os cinco e cada despesa aparece em
-- mais de um: somá-los contaria o mesmo real várias vezes.
CREATE TABLE dim_estagio (
    estagio  TEXT     PRIMARY KEY,
    ordem    SMALLINT NOT NULL UNIQUE
);

-- Classificação funcional. `nivel` impede a dupla contagem: a soma das
-- subfunções (incluindo o resíduo 'FU10 - Demais Subfunções') reproduz a
-- função '10 - Saúde' ao centavo; misturar os dois níveis dobra o valor.
CREATE TABLE dim_conta (
    conta       TEXT    PRIMARY KEY,       -- rótulo original do CSV
    nivel       TEXT    NOT NULL CHECK (nivel IN ('total', 'funcao', 'subfuncao')),
    codigo      TEXT,                      -- '10', '10.301', 'FU10'
    funcao      TEXT,                      -- '10'
    subfuncao   TEXT,                      -- '301'
    nome        TEXT    NOT NULL,
    eh_residual BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE fato_despesa (
    cod_ibge7  INTEGER       NOT NULL REFERENCES dim_municipio,
    exercicio  SMALLINT      NOT NULL,
    estagio    TEXT          NOT NULL REFERENCES dim_estagio,
    conta      TEXT          NOT NULL REFERENCES dim_conta,
    valor      NUMERIC(18,2) NOT NULL,
    PRIMARY KEY (cod_ibge7, exercicio, estagio, conta)
);


-- ---------------------------------------------------------------------
-- DESEMPENHO
-- O SISAB publica só o percentual alcançado, na visão "todas as equipes"
-- (conferido contra os dados abertos de 2024: 8.946 de 8.946 valores
-- coincidem com a visão 'geral').
--
-- As duas FKs compostas por `regime` garantem, de forma declarativa, que cada
-- registro aponta para a versão do indicador VIGENTE no seu quadrimestre:
-- um valor de 2021 não consegue referenciar a regra de 2022.
-- ---------------------------------------------------------------------
CREATE TABLE fato_indicador (
    cod_ibge6     INTEGER      NOT NULL REFERENCES dim_municipio (cod_ibge6),
    quadrimestre  CHAR(6)      NOT NULL,
    id_indicador  SMALLINT     NOT NULL,
    regime        TEXT         NOT NULL,
    percentual    NUMERIC(6,2) CHECK (percentual BETWEEN 0 AND 100),
    PRIMARY KEY (cod_ibge6, quadrimestre, id_indicador),
    FOREIGN KEY (quadrimestre, regime)
        REFERENCES dim_periodo (quadrimestre, regime_metodologico),
    FOREIGN KEY (id_indicador, regime)
        REFERENCES dim_indicador (id_indicador, regime)
);

CREATE INDEX ix_despesa_conta_ano  ON fato_despesa (conta, estagio, exercicio);
CREATE INDEX ix_indicador_periodo  ON fato_indicador (quadrimestre, id_indicador);


-- ---------------------------------------------------------------------
-- REGISTRO DE QUALIDADE
-- Inconsistências encontradas durante a carga. Gravadas pelo pipeline, lidas
-- pela visão de qualidade da aplicação.
-- ---------------------------------------------------------------------
CREATE TABLE log_qualidade (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fonte       TEXT    NOT NULL CHECK (fonte IN ('finbra', 'sisab', 'regional', 'integracao')),
    tipo        TEXT    NOT NULL,
    cod_ibge7   INTEGER REFERENCES dim_municipio,
    periodo     TEXT,
    descricao   TEXT    NOT NULL
);
