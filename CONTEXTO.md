# Projeto de BD — estado atual e próximo passo

**Disciplina:** INF01006 — Projeto de Banco de Dados (UFRGS)
**Cooperação:** Extensão PET-Saúde Digital — GAT05 Indicadores
**Entrega 01:** PDF/apresentação de 1 página — grupo, líder, título, resumo
**Apresentação em aula:** 25/08

---

## 1. O tema

Cruzar **quanto cada município gasta em Atenção Básica** com **o desempenho
desse município nos indicadores da Atenção Primária do Ministério da Saúde**.

Pergunta central: municípios que investem mais por habitante alcançam
melhores indicadores? E quanto da variação de desempenho é resultado real
e quanto é efeito da regra de cálculo?

Recorte: 497 municípios do RS. Porto Alegre como caso destacado.

---

## 2. As fontes — o que foi confirmado em campo

### 2.1 FINBRA / Tesouro Nacional — o dinheiro  ✅ CONFIRMADO

https://siconfi.tesouro.gov.br/siconfi/index.jsf
→ Consultas > Consultar Finbra > Contas Anuais

- Escopo: Municípios do Estado → RS
- Tabela: **Despesas por Função (Anexo I-E)** — NÃO "Despesas Orçamentárias"
  (só a classificação funcional tem a subfunção 10.301)
- Exercício: um download por ano

Formato: CSV zipado, **latin-1**, separador `;`, decimal `,`, **3 linhas de
cabeçalho** antes do header real.

Colunas: `Instituição, Cod.IBGE, UF, População, Coluna, Conta,
Identificador da Conta, Valor`

Filtros de interesse:
- `Conta = '10.301 - Atenção Básica'`
- `Coluna = 'Despesas Empenhadas'` (há 5 estágios)

Verificado no arquivo de 2025:
- 114.448 linhas, 497 municípios, 10.301 presente em 100% deles
- 180 contas distintas (todas as 28 funções de governo, não só saúde)
- 8 subfunções de saúde: 10, 10.122, 10.301, 10.302, 10.303, 10.304,
  10.305, 10.306
- **Cuidado:** existem linhas `FU10 - Demais Subfunções` (resíduo). Não somar
  junto com as subfunções nomeadas — `10 - Saúde` já é o total.
- Códigos IBGE de 7 dígitos, sem colisão ao truncar para 6
- Gasto AB per capita 2025: mín R$ 24,66 | mediana R$ 1.349,78 | máx R$ 5.166,65
- Porto Alegre: R$ 488 mi em Atenção Básica x R$ 2,28 bi em Assistência
  Hospitalar (≈16% x 76%) — está entre os 5% que menos gastam per capita no RS.
  **Investigar se é achado real ou artefato contábil antes de afirmar.**

### 2.2 SISAB — os indicadores, série histórica  ✅ CONFIRMADO, É A FONTE PRINCIPAL

Sem login. Botão **Download**. Baixa em XLS / CSV / ODS.

- **2018–2021:** https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/federal/indicadores/indicadorPainel2021.xhtml
- **2022–2024:** https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/federal/indicadores/indicadorPainel.xhtml

Filtros: Indicador · Nível de visualização (usar **Município**) · Estado (RS) ·
Opção de quadrimestre · Visão das Equipes.

**Comportamento descoberto — importante:**

| Modo | Linhas | Colunas | Cobertura |
|---|---|---|---|
| `Indicador = Visão geral` | 489 municípios | os 7 indicadores | **incompleta** |
| `Indicador = <um específico>` | **497 municípios** | os **quadrimestres** | completa |

→ A visão geral omite silenciosamente 8 municípios (provável inner join entre
indicadores). **Extrair por indicador, não pela visão geral.**
→ Como as colunas viram quadrimestres, **1 download = série temporal inteira
daquele indicador**. São ~7 downloads por relatório, 14 no total.
→ A omissão dos 8 municípios é, ela mesma, um achado para a seção de
qualidade de dados.

Baixar também os documentos linkados no topo da página (Notas Técnicas,
Documento Orientador) — são a base da `dim_indicador` e atendem ao critério
de dicionário de dados (15%).

### 2.3 API DEMAS — só 2024, mas tem os denominadores  ⚠️ USO SECUNDÁRIO

https://apidadosabertos.saude.gov.br/v1/
endpoint `/atencao-primaria/indicador-desempenho-programa-previne-brasil`

Envelope da resposta: `sisab_indicador_desempenho`

**Descobertas em campo (contrariam a documentação):**
- `offset` é **ÍNDICE DE REGISTRO**, não número de página. Usar `offset += limit`.
- A ordem dos resultados **é determinística** (duas chamadas idênticas batem),
  então paginar por offset é seguro.
- **Só existem 2024Q1, 2024Q2 e 2024Q3.** Anos anteriores respondem 200 com
  lista vazia — não é erro, o dado não está lá.

Campos por registro: `uf, municipio, codigo_municipio, codigo_tipo_indicador,
numerador, denominador_utilizador, denominador_identificado,
denominador_estimado, percentual_quadrimestre, percentual, visao_equipe,
cadastro, base_externa, populacao, quadrimestre, competencia`

**Papel no projeto:** é a única fonte com numerador e os três denominadores.
Como só cobre 2024, vira um estudo de caso dentro da série histórica, não a
espinha dorsal.

---

## 3. Armadilhas já identificadas

1. **Códigos IBGE não batem direto.** SISAB e API usam 6 dígitos; FINBRA usa 7
   (o último é dígito verificador). Junção: `codigo_municipio = cod_ibge / 10`
   (divisão inteira). Validado nos 497, zero colisões.
   Aceguá: `430003` x `4300034`. Porto Alegre: `431490` x `4314902`.

2. **`visao_equipe` triplica os registros na API** — `geral`, `homologadas`,
   `validas` com números idênticos. Filtrar por `homologadas` (visão ligada ao
   financiamento) e justificar na metodologia.

3. **`percentual_quadrimestre` ≠ `percentual`.** O primeiro é o resultado do
   indicador (numerador/denominador_utilizador — conferido). O segundo é outra
   coisa e passa de 100. Não usar antes de achar a definição no dicionário.

4. **A visão geral do SISAB perde 8 municípios** (ver 2.2).

5. **Granularidade temporal.** FINBRA é anual; indicadores são quadrimestrais.
   Decidir e documentar: agregar indicadores para o ano (média) ou repetir o
   gasto anual nos três quadrimestres.

---

## 4. O diferencial do trabalho

A regra de cálculo dos indicadores mudou no meio da série, e isso está
documentado oficialmente:

- **Nota Técnica nº 05/2020 (DESF/SAPS/MS)** — vigente até Q3-2021
- **Nota Técnica nº 11/2022**, de 15/02/2022 — vale a partir de Q1-2022
- **Portaria GM/MS nº 102, de 20/01/2022** — forçou alcance de 100% em
  indicadores específicos, em quadrimestres específicos, **apenas para fins de
  financiamento**, enquanto o alcance real era outro (caso da cobertura vacinal
  de Poliomielite e Pentavalente)
- **Portaria GM/MS nº 3.493, de 10/04/2024** — encerra o Previne Brasil

Ou seja: existe um caso documentado em que **o número divulgado e o número que
pagou são diferentes**. É por isso que o governo separou os relatórios em dois.

Na API (2024), os três denominadores divergem município a município:

| Município | identificado | estimado | utilizado | qual venceu |
|---|---|---|---|---|
| Pinheiro Machado | 22 | 27 | 27 | estimado |
| Aceguá | 25 | 19 | 25 | identificado |

→ A **definição do indicador** vira uma dimensão versionada. Isso é modelagem
temporal, não apenas análise — e é o que separa este trabalho de um dashboard
descritivo.

---

## 5. Modelo de dados (rascunho)

```
dim_municipio   (cod_ibge7, cod_ibge6, nome, uf, populacao_finbra, populacao_sisab)
dim_indicador   (codigo, nome, regra_numerador, regra_denominador, meta, peso,
                 nota_tecnica, vigencia_inicio, vigencia_fim)
dim_periodo     (quadrimestre, ano, competencia)
dim_conta       (conta, funcao, subfuncao)

fato_despesa    (cod_ibge7, exercicio, coluna, conta, valor)
fato_indicador  (cod_ibge6, quadrimestre, codigo_indicador, visao_equipe,
                 percentual, numerador, den_identificado, den_estimado,
                 den_utilizado, fonte)   -- fonte: 'sisab' | 'api'
```

`dim_indicador` é construída à mão a partir das Notas Técnicas — nenhuma fonte
entrega isso pronto. É modelagem nossa, e conta como tal na avaliação.

---

## 6. Limitação assumida explicitamente

A subfunção 10.301 é o gasto **total** do município em atenção básica: recurso
próprio + federal + estadual. O pagamento por desempenho do Previne é só uma
fatia do federal.

Portanto **não** afirmamos que "o incentivo funcionou". Afirmamos: *municípios
que investem mais em atenção básica per capita apresentam desempenho
melhor/pior nos indicadores*. Associação, não causalidade.

---

## 7. Trabalho relacionado

Cabreira, Ritter, Aguiar & Celeste (2019). *Despesas municipais em atenção
primária à saúde no Rio Grande do Sul: um estudo ecológico.* Cad. Saúde Pública.
https://doi.org/10.1590/0102-311x00150117

Cobre os 496 municípios do RS, 2011–2013, e pergunta o que **explica** o gasto.
Diferencial nosso: período 2018–2024, pergunta invertida (o gasto prevê o
desempenho?), e a análise das regras de denominador, que não existiam à época.

Faltam de 2 a 4 trabalhos para fechar o critério (10% da nota).

---

## 8. Estado dos artefatos

| Arquivo | Situação |
|---|---|
| `Entrega01_ProjetoBD.pptx` | pronto — **faltam nomes dos integrantes e do líder** |
| `extrai_previne.py` | corrigido (offset por registro) — só serve para 2024 |
| `verifica_01_api.py` | rodou; achou que só existe 2024 |
| `diagnostico_api.py` | rodou; confirmou offset por registro e ordem estável |
| `verifica_02_finbra.py` | rodou e passou no arquivo de 2025 |
| `verifica_03_juncao.py` | **ainda não rodou** — precisa dos dados baixados |

**Atenção:** a apresentação diz "~800 mil linhas brutas". Recalcular quando os
downloads do SISAB estiverem prontos e corrigir o número antes de apresentar.

---

## 9. Próximos passos

1. Baixar os 7 indicadores do relatório 2018–2021 (nível Município, RS)
2. Baixar os 7 indicadores do relatório 2022–2024 (mesma configuração)
3. Baixar as Notas Técnicas e o Documento Orientador
4. Baixar FINBRA 2018–2024 (Despesas por Função, RS) — 7 arquivos
5. Rodar `extrai_previne.py` para os 3 quadrimestres de 2024
6. Escrever o loader que despivota o formato largo do SISAB
7. Rodar `verifica_03_juncao.py`
8. Preencher nomes na apresentação e entregar

---

