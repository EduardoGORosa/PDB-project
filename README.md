# Gasto em Atenção Básica x desempenho na Atenção Primária — RS, 2018–2024

Pipeline de ingestão e esquema relacional em PostgreSQL para o projeto da
disciplina INF01006 (UFRGS). Integra três fontes com papéis diferentes:

| Fonte | Papel | Cobertura | Granularidade |
|---|---|---|---|
| **FINBRA / Tesouro** | o gasto | 2020–2025 (ver ressalva) | município × ano |
| **SISAB** | os indicadores — espinha dorsal | 2018Q1–2025Q1 | município × quadrimestre × indicador |
| **API DEMAS / MS** | numerador e os três denominadores | 2024Q1–2024Q3 | município × quadrimestre × indicador × visão |

O contexto do projeto, as fontes e a limitação metodológica assumida estão em
[`CONTEXTO.md`](CONTEXTO.md). Este README cobre o pipeline e registra as
divergências encontradas entre o que o CONTEXTO.md previa e o que os dados
mostraram.

---

## Como rodar

```bash
# 1. banco (o container usa a porta 5433; a 5432 já está ocupada nesta máquina)
docker run -d --name pbd-postgres \
  -e POSTGRES_USER=pbd -e POSTGRES_PASSWORD=pbd -e POSTGRES_DB=pbd \
  -p 127.0.0.1:5433:5432 -v pbd-pgdata:/var/lib/postgresql postgres:18

# 2. dependências
uv sync

# 3. dados da API (os do FINBRA e do SISAB são baixados à mão dos portais)
python -m pipeline.extrai_api      # ~8 min, 1.491 requisições

# 4. carga completa — recria o esquema e carrega as três fontes
python carrega.py

# 5. só o relatório de verificação
python carrega.py --verifica

# 6. consultas
psql "$DATABASE_URL" -f sql/02_consultas_basicas.sql
psql "$DATABASE_URL" -f sql/03_consultas_avancadas.sql
```

A conexão vem de `DATABASE_URL` (padrão `postgresql://pbd:pbd@127.0.0.1:5433/pbd`).
A carga completa leva ~14 s e é idempotente: `carrega.py` derruba e recria o
esquema `pbd`.

---

## Estrutura

```
pipeline/
  comum.py           constantes de formato, regimes, códigos IBGE
  bd.py              conexão e COPY
  leitura_finbra.py  parsing dos CSV anuais (latin-1, ';', 3 linhas de preâmbulo)
  leitura_sisab.py   despivota o formato largo -> longo
  extrai_api.py      download da API DEMAS (pagina por município)
  carrega_finbra.py  dim_municipio, dim_conta, dim_estagio, fato_despesa
  carrega_sisab.py   dim_periodo, dim_indicador, fato_indicador (sisab)
  carrega_api.py     fato_indicador (api), população, competências
  verifica.py        relatório de contagens, cobertura e nulos
sql/
  01_schema.sql            DDL + visões de apoio
  02_consultas_basicas.sql B1–B10
  03_consultas_avancadas.sql A1–A8 (janelas, CTEs, NTILE)
carrega.py           orquestrador
```

### Volume carregado

| Tabela | Linhas |
|---|---|
| `fato_despesa` | 651.198 |
| `fato_indicador` | 103.376 (76.538 SISAB + 26.838 API) |
| `dim_conta` | 191 |
| `dim_municipio` | 497 |
| `dim_periodo` | 22 |
| `dim_indicador` | 14 (7 indicadores × 2 regimes) |
| `populacao_municipio` | 3.479 |

---

## Desvios deliberados do modelo do CONTEXTO.md §5

1. **A chave do município é o código de 6 dígitos**, não o de 7. A divisão
   `cod_ibge7 / 10` é resolvida uma vez, na carga; o código de 7 dígitos fica
   preservado em `dim_municipio.cod_ibge7`, com `CHECK` garantindo a coerência.
   Assim nenhuma consulta precisa lembrar da regra.

2. **A população saiu de `dim_municipio` para `populacao_municipio`.** Ela muda
   a cada exercício no FINBRA e a cada quadrimestre na API — é fato datado, não
   atributo do município. Como coluna única, obrigaria a escolher em silêncio
   um ano de referência.

3. **`fonte` entra na chave primária de `fato_indicador`.** SISAB e API
   descrevem 2024 ao mesmo tempo, por métodos diferentes; as duas medidas
   precisam coexistir para que a comparação entre elas seja possível — ela é
   parte do trabalho (consulta B8), não um conflito a resolver na carga.

---

## Divergências entre o CONTEXTO.md e os dados

Cada item abaixo foi medido, não suposto. São achados do trabalho.

### 1. O FINBRA baixado não cobre 2018 e 2019

`data/` tem os exercícios **2020 a 2025**. O recorte do projeto é 2018–2024.
Consequência: os indicadores de 2018 e 2019 (497 municípios, 7 indicadores,
6 quadrimestres) ficam sem contrapartida de gasto. A consulta 10 do relatório
de verificação torna isso explícito. Para fechar o recorte, faltam baixar dois
exercícios do SICONFI; sobra o de 2025.

### 2. A subfunção 10.301 não está em 100% dos municípios

O CONTEXTO.md §2.1 afirma cobertura total, com base no arquivo de 2025.
Ano a ano (estágio *Despesas Empenhadas*):

| Exercício | Municípios com 10.301 |
|---|---|
| 2020 | 497 |
| **2021** | **496** |
| 2022 | 497 |
| **2023** | **496** |
| 2024 | 497 |
| 2025 | 497 |

Os faltantes são **Barão de Cotegipe (4301701) em 2021** e **Tenente Portela
(4321402) em 2023**. Não é gasto zero: são declarações truncadas no SICONFI.
Barão de Cotegipe declarou 21 linhas no exercício inteiro (o normal é ~200) e
nenhuma linha da função saúde; Tenente Portela declarou 18 linhas e R$ 8,9
milhões de despesa total para 13.385 habitantes.

### 3. `visao_equipe` **não** replica os registros com números idênticos

O CONTEXTO.md §3 (armadilha 2) trata `geral`, `homologadas` e `validas` como
cópias, e por isso manda filtrar na carga. Medido nos 8.946 grupos
(município × quadrimestre × indicador) de 2024:

| | grupos | % |
|---|---|---|
| idênticos nas três visões | 7.474 | 83,5% |
| `geral` difere de `homologadas` | 1.184 | 13,2% |
| `validas` difere de `homologadas` | 522 | 5,8% |

A diferença é pequena na maioria dos casos (mediana 0 pp, média 2 pp) mas
chega a **79 pontos percentuais**. São três medições diferentes, não cópias.

**O que o pipeline faz:** carrega as três visões e coloca `visao_equipe` na
chave primária de `fato_indicador`, o que torna a triplicação silenciosa
impossível — qualquer agregação é obrigada a escolher uma visão. A escolha
metodológica do projeto (`homologadas`, a visão ligada ao financiamento) está
na visão `vw_indicador_api`, explícita e reversível numa linha. Filtrar na
carga, como previa o CONTEXTO.md, descartaria 16,5% de dado real.

### 4. A paginação por `offset` da API é inutilizável

O CONTEXTO.md §2.3 registra que `offset` é índice de registro (e não página) e
que a ordem dos resultados seria determinística. A segunda parte não se
sustenta: **seis chamadas idênticas a `offset=0&limit=5` devolveram duas
janelas diferentes**, deslocadas em um registro. Com ordem instável, paginar
por offset duplica e perde linhas sem erro visível.

`pipeline/extrai_api.py` pagina por **`codigo_municipio`**, que a API aceita
como filtro. Uma chamada por município devolve 18 registros (6 indicadores × 3
visões) e é estável — seis chamadas idênticas devolveram exatamente o mesmo
conjunto. São 1.491 requisições, ~8 min.

### 5. O prefixo `/v1` da URL da API deixou de existir

`https://apidadosabertos.saude.gov.br/v1/atencao-primaria/...` devolve **404**.
A base correta é a raiz do host. O Swagger está em
`https://apidadosabertos.saude.gov.br/static/swagger.json` e não declara
`basePath`.

### 6. `extrai_previne.py` e `api.py` nunca foram corrigidos

O CONTEXTO.md §8 dá `extrai_previne.py` como "corrigido (offset por registro)".
Os dois arquivos são cópias idênticas e **ambos ainda passam `offset=pagina`**;
nenhum dos dois procura a chave de envelope `sisab_indicador_desempenho`.
Foram substituídos por `pipeline/extrai_api.py` e mantidos no repositório sem
alteração — removê-los é decisão de vocês.

### 7. O header do SISAB não está em linha fixa

Linha 12 nos painéis 2022+, linha 13 nos históricos, que trazem uma linha
"Departamento de Saúde da família DESF" a mais. O loader localiza o header pela
própria linha, não por posição.

### 8. Os arquivos do SISAB trazem 2025 Q1

Fora do recorte 2018–2024. São carregados (o dado bruto fica íntegro) e
filtrados por ano nas consultas.

### 9. `FU10 - Demais Subfunções` não é resíduo a descartar

O CONTEXTO.md §2.1 diz para não somá-lo junto com as subfunções nomeadas.
Medido em Porto Alegre/2024: subfunções nomeadas **mais** FU10 reproduzem
`10 - Saúde` ao centavo (R$ 2.799.019.820,54). FU10 **pertence** ao total. A
armadilha real é somar o nível `funcao` junto com o nível `subfuncao` — e é
por isso que `dim_conta.nivel` existe.

---

## O que foi confirmado

- A junção `cod_ibge7 / 10` casa **497 ↔ 497** em todos os exercícios, sem
  sobra dos dois lados.
- Os 14 arquivos do SISAB têm exatamente o mesmo conjunto de 497 códigos IBGE,
  e **zero valores faltantes** nas 76.538 células.
- FINBRA é latin-1, `;`, decimal `,`, 3 linhas de preâmbulo, `(município,
  coluna, conta)` único.
- Gasto AB per capita em 2025: mín **R$ 24,66** · mediana **R$ 1.349,78** ·
  máx **R$ 5.166,65** — os três números batem com a verificação em campo
  registrada no CONTEXTO.md.
- Porto Alegre 2024: 15,7% do gasto em saúde na Atenção Básica contra 76,2% em
  Assistência Hospitalar — o "≈16% × 76%" do CONTEXTO.md.
- Os denominadores divergem município a município, e o caso citado no
  CONTEXTO.md §4 reproduz: Aceguá 25/19/25 → venceu o **identificado**;
  Pinheiro Machado 22/27/27 → venceu o **estimado**.
- `percentual_quadrimestre` = numerador / denominador_utilizador em 8.940 de
  8.946 casos (os 6 restantes têm denominador zero).

## O que continua em aberto

- **O campo `percentual` da API segue sem definição.** Vai a 1.100 e passa de
  100 em 3.931 dos 8.946 registros. Testei a hipótese de ser o indicador
  calculado sobre o denominador estimado: bate em apenas **14,3%** dos casos
  (contra 2,3% para o identificado e 5,7% para o utilizado). Não é isso.
  A coluna se chama `percentual_api_indefinido` para impedir uso acidental.
- **`meta`, `peso`, `regra_numerador` e `regra_denominador` estão NULL em
  `dim_indicador`.** Dependem das Notas Técnicas, que não estão no repositório
  (não há `docs/`). Preencher com valor plausível seria inventar dado.
- **Os campos `vigencia_inicio`/`vigencia_fim` são a cobertura observada** dos
  painéis, lida dos próprios arquivos — não datas extraídas das Notas Técnicas.
  Note que o painel histórico começa em 2018Q1, mas o Previne Brasil só entrou
  em vigor em 2020: rotular 2018–2019 como regime "NT 05/2020" é uma
  simplificação herdada do CONTEXTO.md §4 que convém revisar.
- **Porto Alegre está entre os 5% que menos gastam per capita a partir de
  2022** (percentil 4,2, 22º de 497), mas não em 2020 (8,1) e 2021 (6,7). A
  estabilidade da posição sugere padrão estrutural, mas decidir entre achado
  real e artefato contábil exige a fonte do financiamento, que o FINBRA não
  separa.

---

## Consultas

**Básicas** (`sql/02_consultas_basicas.sql`) — seleção, junção, agregação:
dicionário dos indicadores, maiores gastos, distribuição per capita por ano,
composição do gasto de Porto Alegre, desempenho médio por indicador, piores
coberturas, faixas de desempenho, SISAB × API, as três visões da API, e o
denominador que cada regra usou.

**Avançadas** (`sql/03_consultas_avancadas.sql`) — funções de janela, CTEs e
NTILE, sem biblioteca estatística externa:

- **A1** `NTILE(5)` — quintis de gasto per capita × desempenho médio. É a
  pergunta central do trabalho.
- **A2** `LAG()` — compara a variação típica entre quadrimestres com o salto no
  corte de regime metodológico.
- **A3** `PERCENT_RANK()`, `RANK()` — Porto Alegre na distribuição estadual.
- **A4** `AVG() OVER (ROWS BETWEEN 2 PRECEDING …)` — média móvel de 3
  quadrimestres, reiniciada a cada regime.
- **A5** `NTILE(4)` — quartis de sensibilidade ao denominador escolhido.
- **A6** os casos em que a escolha do denominador mais pesou.
- **A7** `LAG()`, `FIRST_VALUE()` — trajetória do gasto desde 2020.
- **A8** `CORR()` + `NTILE(5)` — correlação gasto × desempenho por indicador.

### Dois resultados que valem destaque

**A1 — a resposta à pergunta central (2024):** o desempenho médio sobe de forma
monotônica com o quintil de gasto, mas o efeito é modesto.

| Quintil | Faixa de gasto per capita | Desempenho médio |
|---|---|---|
| 1 | R$ 88 – 652 | 49,9% |
| 2 | R$ 658 – 1.043 | 51,1% |
| 3 | R$ 1.045 – 1.470 | 54,1% |
| 4 | R$ 1.476 – 2.006 | 55,7% |
| 5 | R$ 2.020 – 4.841 | 57,5% |

7,6 pontos percentuais entre o quintil mais pobre e o mais rico. A8 dá
correlações de 0,06 a 0,21 — associação fraca e positiva, coerente com a
limitação assumida no CONTEXTO.md §6.

**A2 — o diferencial do trabalho:** no corte entre as Notas Técnicas, a
cobertura vacinal saltou **48,4 pontos percentuais de 2021Q3 para 2022Q1** —
**8,5 vezes** a variação típica entre quadrimestres do mesmo regime (5,7 pp).
Nenhum sistema de saúde muda tanto em quatro meses. Em Porto Alegre a série
vai de 20% em 2021Q3 para 78% em 2022Q1. É a mudança de regra, não o serviço,
e é exatamente o caso da Portaria GM/MS nº 102/2022 citada no CONTEXTO.md §4.
Dois indicadores caem no corte (`diabetes_hemoglobina` −8,4 pp,
`prenatal_6_consultas` −5,8 pp), o que reforça que se trata de redefinição e
não de tendência.

**A série 2018–2025 não pode ser lida como contínua.** É por isso que
`dim_indicador` é versionada por regime e que todo fato aponta para uma versão
específica do indicador, nunca para o indicador em abstrato.
