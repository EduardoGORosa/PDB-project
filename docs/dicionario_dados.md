# Dicionário de dados

Esquema `pbd` (PostgreSQL). DDL em `sql/01_schema.sql`; camada analítica em
`sql/02_analitico.sql`. Diagrama: `docs/modelo_er.dot`
(`dot -Tpng docs/modelo_er.dot -o modelo_er.png`).

**Convenções.** PK = chave primária; FK = chave estrangeira; *nulável* indica
que o campo aceita NULL. Quadrimestres no formato `AAAAQn` (`2022Q1`).
Códigos IBGE: 7 dígitos no FINBRA (o último é verificador), 6 no SISAB.

---

## Fontes

| Fonte | Órgão | Acesso | Conteúdo usado | Período |
|---|---|---|---|---|
| FINBRA — Despesas por Função (Anexo I-E) | Tesouro Nacional / SICONFI | CSV do portal (2020–2025); API `apidatalake.tesouro.gov.br/ords/siconfi/tt/dca` (2018–2019) | despesa por função e subfunção, cinco estágios; população | 2018–2025 |
| Painel de Indicadores do SISAB | Ministério da Saúde / SAPS | CSV, um por indicador e regime, nível Município, UF RS, visão "todas as equipes" | percentual alcançado | 2018Q1–2025Q1 |
| Notas Técnicas e Portarias | Ministério da Saúde | NT 5/2020-DESF/SAPS; NT 11/2022 e 12/2022-SAPS; fichas NT 13–19/2022; Portarias GM/MS 3.222/2019, 2.979/2019, 166/2021, 2.396/2021, 102/2022, 3.493/2024 | regras, metas, pesos e ajustes de financiamento | — |
| Regiões de saúde | DATASUS (base territorial jun/2026) e SES-RS (Portaria SES-RS nº 320/2025, Anexo I) | arquivos territoriais e PDF | município → região → coordenadoria | vigente |
| API DEMAS (dados abertos) | Ministério da Saúde | `apidadosabertos.saude.gov.br` | **não entra no modelo**; usada só para identificar a visão de equipes do SISAB | 2024Q1–Q3 |

---

## Divisão regional

### `dim_coordenadoria` — 18 linhas
Coordenadorias Regionais de Saúde (CRS) da SES-RS.

| Coluna | Tipo | Descrição |
|---|---|---|
| `crs_numero` | smallint, PK | Número da CRS (1 a 18). |
| `sede` | text | Município-sede. |

### `dim_regiao_saude` — 30 linhas
Regiões de saúde da Resolução CIB/RS nº 555/2012. Cada região pertence a uma
única CRS.

| Coluna | Tipo | Descrição |
|---|---|---|
| `regiao_codigo` | smallint, PK | Número da região (R1 a R30). |
| `nome` | text | Nome da região. R28 usa o nome da Portaria SES-RS 320/2025 ("Vale do Rio Pardo"). |
| `crs_numero` | smallint, FK → `dim_coordenadoria` | Coordenadoria responsável. |

---

## Município e população

### `dim_municipio` — 497 linhas

| Coluna | Tipo | Descrição | Origem |
|---|---|---|---|
| `cod_ibge7` | integer, PK | Código IBGE de 7 dígitos. | FINBRA |
| `cod_ibge6` | integer, UNIQUE | Código de 6 dígitos (`cod_ibge7 / 10`, garantido por `CHECK`). Alvo da FK de `fato_indicador`. | derivado |
| `nome` | text | Nome do município (exercício mais recente do FINBRA). | FINBRA |
| `uf` | char(2) | Sempre `RS`. | — |
| `regiao_codigo` | smallint, FK → `dim_regiao_saude`, nulável | Região de saúde. | DATASUS |

### `pop_municipio` — 497 × exercícios
População informada pelo FINBRA em cada exercício. Separada do município para
que o per capita de cada ano use a população daquele ano.

| Coluna | Tipo | Descrição |
|---|---|---|
| `cod_ibge7` | integer, PK, FK → `dim_municipio` | Município. |
| `exercicio` | smallint, PK | Ano. |
| `populacao` | integer (`> 0`) | Habitantes. |

---

## Tempo e regras

### `dim_regime` — 2 linhas
Regimes metodológicos dos indicadores.

| Coluna | Tipo | Descrição |
|---|---|---|
| `regime` | text, PK | `NT 05/2020` ou `NT 11/2022`. |
| `descricao` | text | O que define o regime e o que mudou. |
| `inicio`, `fim` | char(6) | Primeiro e último quadrimestre de vigência (`fim` NULL = vigente). |

### `dim_periodo` — 22 linhas (2018Q1–2025Q1)

| Coluna | Tipo | Descrição |
|---|---|---|
| `quadrimestre` | char(6), PK | `AAAAQn`. |
| `ano`, `numero_quadrimestre` | smallint | Decomposição, coerência garantida por `CHECK`. |
| `regime_metodologico` | text, FK → `dim_regime` | Regra vigente. `UNIQUE (quadrimestre, regime_metodologico)` é alvo da FK composta de `fato_indicador`. |
| `efeito_financeiro` | text | Se o resultado deste quadrimestre de dados influiu no repasse: `anterior ao programa` (2018–2019), `sem efeito` (2020Q1–2021Q2: repasses fixados), `parcial` (2021Q3, 2022Q1: Portaria 102/2022), `pleno` (2022Q2–2023Q3), `posterior ao programa` (2024Q1 em diante). |

### `dim_indicador` — 14 linhas (7 indicadores × 2 regimes)
**Dimensão versionada**, construída a partir das Notas Técnicas
(`data_ref/indicadores.csv`). Cada versão é uma linha; `codigo` liga as versões
do mesmo indicador e se repete, por isso a chave é `id_indicador`.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_indicador` | smallint, PK (identity) | Versão do indicador. |
| `codigo` | text | Identificador estável (`cobertura_vacinal`). `UNIQUE (codigo, regime)`. |
| `ordem` | smallint | Número oficial do indicador (1 a 7). |
| `nome` | text | Nome exato do indicador **naquela versão**, lido do arquivo do SISAB. |
| `regra_numerador`, `regra_denominador` | text | Regra de cálculo resumida da Nota Técnica. |
| `meta` | numeric(5,2) | Meta (%). Pré-natal: 60% → 45% em 2022; demais inalteradas. |
| `peso` | smallint | Peso no Indicador Sintético Final (soma 10). |
| `nota_tecnica` | text | Documento que define a versão. |
| `regime` | text, FK → `dim_regime` | Regime da versão. `UNIQUE (id_indicador, regime)` é alvo da FK composta. |
| `vigencia_inicio`, `vigencia_fim` | char(6), FK → `dim_periodo` | Intervalo de vigência (`fim` NULL = vigente). |

| # | Indicador | Meta NT 5/2020 | Meta NT 11/2022 | Peso |
|---|---|---|---|---|
| 1 | Pré-natal: ≥ 6 consultas, 1ª até a 20ª → 12ª semana | 60 | 45 | 1 |
| 2 | Gestantes com exames de sífilis e HIV | 60 | 60 | 1 |
| 3 | Gestantes com atendimento odontológico | 60 | 60 | 2 |
| 4 | Citopatológico (mulheres 25–64) | 40 | 40 | 1 |
| 5 | Vacinação: Pólio e Pentavalente | 95 | 95 | 2 |
| 6 | Hipertensos com PA aferida (12 → 6 meses, com consulta) | 50 | 50 | 2 |
| 7 | Diabéticos com hemoglobina glicada (12 → 6 meses, com consulta) | 50 | 50 | 1 |

### `ajuste_financiamento` — 42 linhas
Quadrimestres de dados em que um ato normativo fixou o resultado de um
indicador **apenas para o pagamento**. O percentual em `fato_indicador`
continua sendo o alcance real. Fonte: `data_ref/ajustes_financiamento.csv`.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_indicador` | smallint, PK, FK → `dim_indicador` | Versão do indicador. |
| `quadrimestre` | char(6), PK, FK → `dim_periodo` | Quadrimestre de **dados** (o pagamento ocorre no quadrimestre seguinte). |
| `regra` | text | O que foi considerado no pagamento. |
| `ato_normativo` | text | Portaria e artigo. |
| `observacao` | text, nulável | Contexto e grau de certeza. |

---

## Despesa

### `dim_estagio` — 5 linhas
Estágios da execução: Empenhadas, Liquidadas, Pagas, Inscrição de Restos a
Pagar Processados e Não Processados. **As análises usam `Despesas Liquidadas`.**
Somar estágios conta o mesmo real mais de uma vez.

### `dim_conta` — 193 linhas
Classificação funcional, tal como rotulada no FINBRA.

| Coluna | Tipo | Descrição |
|---|---|---|
| `conta` | text, PK | Rótulo original (`10.301 - Atenção Básica`). |
| `nivel` | text | `total`, `funcao` ou `subfuncao`. **Toda soma filtra um único nível**: as subfunções (com o resíduo `FU10`) somam exatamente a função `10 - Saúde`. |
| `codigo` | text, nulável | `10`, `10.301`, `FU10`. |
| `funcao`, `subfuncao` | text, nulável | Partes do código. |
| `nome` | text | Nome da conta. |
| `eh_residual` | boolean | `TRUE` nas contas `FUnn - Demais Subfunções`. |

### `fato_despesa` — 853.864 linhas (2018–2025)
Grão: município × exercício × estágio × conta.

| Coluna | Tipo | Descrição |
|---|---|---|
| `cod_ibge7` | integer, PK, FK → `dim_municipio` | Município. |
| `exercicio` | smallint, PK | Ano. |
| `estagio` | text, PK, FK → `dim_estagio` | Estágio da despesa. |
| `conta` | text, PK, FK → `dim_conta` | Conta. |
| `valor` | numeric(18,2) | Valor em reais correntes. |

---

## Desempenho

### `fato_indicador` — 76.538 linhas
Grão: município × quadrimestre × versão do indicador. Percentual publicado pelo
SISAB na visão "todas as equipes".

| Coluna | Tipo | Descrição |
|---|---|---|
| `cod_ibge6` | integer, PK, FK → `dim_municipio(cod_ibge6)` | Município. |
| `quadrimestre` | char(6), PK | Quadrimestre de dados. |
| `id_indicador` | smallint, PK | Versão do indicador. |
| `regime` | text | Participa das duas FKs compostas: `(quadrimestre, regime)` → `dim_periodo` e `(id_indicador, regime)` → `dim_indicador`. Assim, **um fato não consegue apontar para uma versão do indicador que não estava vigente no seu quadrimestre.** |
| `percentual` | numeric(6,2), 0–100, nulável | Resultado publicado. Nenhum nulo na carga atual. |

---

## Registro de qualidade

### `log_qualidade`
Inconsistências encontradas pela carga, exibidas na aplicação.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | integer, PK | — |
| `fonte` | text | `finbra`, `sisab`, `regional`, `integracao`. |
| `tipo` | text | `sem_subfuncao_10301`, `sem_declaracao`, `divergencia_entre_fontes`. |
| `cod_ibge7` | integer, FK, nulável | Município afetado. |
| `periodo` | text, nulável | Exercício ou quadrimestre. |
| `descricao` | text | Detalhe. |

---

## Camada analítica (`sql/02_analitico.sql`)

| Objeto | Tipo | Conteúdo |
|---|---|---|
| `faixa_porte(pop)` | função | Classe de porte (até 5 mil … mais de 100 mil). |
| `vw_municipio` | visão | Município com região e CRS. |
| `mv_gasto_anual` | visão materializada | Por município e exercício: população, porte, gasto liquidado em AB (10.301) e em saúde (função 10), per capita e participação da AB. `gasto_ab` NULL = 10.301 não declarada. |
| `mv_desempenho_anual` | visão materializada | Média anual dos quadrimestres por município e indicador, com `n_quadrimestres` (completude) e `n_ajustados` (quadrimestres fixados por portaria). |
| `vw_painel_anual` | visão | Gasto e desempenho do mesmo município no mesmo exercício. |
| `vw_desempenho_composto` | visão | Média dos 7 indicadores no ano. |
| `vw_isf_anual` | visão | Indicador sintético no estilo do ISF: Σ min(resultado/meta, 1) × 10 × peso / Σ peso, sobre o alcance real. |
| `mv_serie_estadual` | visão materializada | Série estadual por indicador e quadrimestre: média simples, ponderada pela população, sem municípios até 5 mil, mediana, zeros e marcação de ajuste. |
| `mv_grupo_referencia` | visão materializada | Junção reflexiva: os 20 municípios de população mais próxima de cada município, por ano. |
| `vw_posicao_no_grupo` | visão | Posição no gasto e no desempenho dentro do grupo de referência; marca discrepâncias. |
| `vw_gasto_atipico` | visão | Gasto per capita abaixo de 10% da mediana estadual do ano. |
