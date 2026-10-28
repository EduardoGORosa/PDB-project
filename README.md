# Gasto × Desempenho na Atenção Primária — RS, 2018–2024

INF01006 — Projeto de Banco de Dados (UFRGS) · Extensão PET-Saúde Digital, GAT05 Indicadores
Eduardo Rosa, Rafael Stephanou e Vinícius Herzog (líder)

Base de dados que integra, para os 497 municípios do Rio Grande do Sul, o gasto
municipal em Atenção Básica (FINBRA/SICONFI, subfunção 10.301) com o desempenho
nos indicadores do Previne Brasil (SISAB), com a mudança de regra de cálculo de
2022 modelada numa dimensão de indicadores versionada. O escopo e as decisões
metodológicas estão no anteprojeto (`entrega/Anteprojeto.pdf`).

| Documento | Onde |
|---|---|
| Relatório final | `entrega/relatorio_final.pdf` (fonte: `.html`) |
| Apresentação final | `entrega/apresentacao_final.pdf` (fonte: `.html`) |
| Relatório parcial | `entrega/relatorio_parcial.pdf` (fonte: `.html`) |
| Dicionário de dados | `docs/dicionario_dados.md` |
| Modelo ER | `docs/img/modelo_er.png` (fonte: `docs/modelo_er.dot`) |
| Trabalhos relacionados | `docs/trabalhos_relacionados.md` |

---

## Como rodar

```bash
# 1. banco (porta 5433)
docker run -d --name pbd-postgres \
  -e POSTGRES_USER=pbd -e POSTGRES_PASSWORD=pbd -e POSTGRES_DB=pbd \
  -p 127.0.0.1:5433:5432 -v pbd-pgdata:/var/lib/postgresql postgres:18
#    (já criado: docker start pbd-postgres)

# 2. dependências
uv sync

# 3. dados que não vêm do portal (os CSV do SISAB e do FINBRA 2020+ são baixados à mão)
python -m pipeline.extrai_finbra 2018 2019   # ~50 min, API do SICONFI
python -m pipeline.extrai_api                # opcional, só para confere_visao

# 4. carga completa (~20 s, idempotente: recria o esquema pbd)
python carrega.py
python carrega.py --verifica                 # só o relatório de verificação

# 5. consultas
psql "$DATABASE_URL" -f sql/03_consultas_basicas.sql
psql "$DATABASE_URL" -f sql/04_consultas_avancadas.sql

# 6. aplicação
streamlit run app/app.py
```

A conexão vem de `DATABASE_URL` (padrão `postgresql://pbd:pbd@127.0.0.1:5433/pbd`).

## Estrutura

```
carrega.py                 orquestrador da carga
pipeline/
  comum.py                 formatos das fontes, regimes, efeito financeiro
  leitura_finbra.py        parsing dos CSV anuais (latin-1, ';', 3 linhas de preâmbulo)
  leitura_sisab.py         despivota o formato largo do SISAB
  extrai_finbra.py         FINBRA pela API do SICONFI, no formato do CSV do portal
  carrega_finbra.py        município, população, contas, estágios, despesa
  carrega_regional.py      regiões de saúde e coordenadorias
  carrega_sisab.py         regimes, períodos, dimensão de indicadores, ajustes, desempenho
  verifica.py              relatório de verificação
  extrai_api.py            download da API DEMAS (2024)
  confere_visao.py         identifica a visão de equipes dos arquivos do SISAB
data_ref/
  indicadores.csv          dimensão de indicadores, construída a partir das Notas Técnicas
  ajustes_financiamento.csv quadrimestres fixados por portaria
  crs_municipios.csv       município -> região de saúde -> CRS
sql/
  01_schema.sql            DDL
  02_analitico.sql         visões e visões materializadas
  03_consultas_basicas.sql B1–B10
  04_consultas_avancadas.sql A1–A9
app/app.py                 Streamlit, quatro visões
docs/                      dicionário, modelo ER, trabalhos relacionados, figuras
entrega/                   documentos entregues
legado/                    scripts da fase exploratória
```

## Decisões de modelagem

1. **Dimensão de indicadores versionada.** Cada indicador tem uma linha por
   regime (NT 5/2020 e NT 11/2022), com regra, meta, peso, nota técnica e
   vigência. A chave é `id_indicador`, porque `codigo` se repete.
2. **Duas FKs compostas por `regime`** em `fato_indicador` impedem,
   declarativamente, que um resultado aponte para uma versão do indicador que
   não estava vigente no seu quadrimestre.
3. **`efeito_financeiro` em `dim_periodo` e `ajuste_financiamento`** registram
   quando o resultado de fato influiu no repasse. Só 2022Q2–2023Q3 tiveram
   pagamento pleno pelo resultado real (ver relatório final, seção 3).
4. **Município com duas chaves**: `cod_ibge7` (PK, FINBRA) e `cod_ibge6`
   (UNIQUE, SISAB), ligadas por `CHECK (cod_ibge7 / 10 = cod_ibge6)`.
5. **População como fato datado** (`pop_municipio`), não atributo do município.
6. **Coordenadoria como atributo da região**, não do município: impede dois
   municípios da mesma região em CRS diferentes.
7. **`dim_conta.nivel`** impede somar função e subfunção juntas.
8. **A API DEMAS ficou fora do modelo**: só cobre 2024. É usada apenas para
   confirmar que os arquivos do SISAB estão na visão "todas as equipes"
   (8.946 de 8.946 valores coincidem).

## Achados de qualidade de dados

- FINBRA 2018–2019 não estava no portal baixado; veio da API do SICONFI, que
  reproduz o CSV do portal linha a linha (3.239/3.239 numa amostra de 2020).
- Barão de Cotegipe (2021) e Tenente Portela (2023) não declararam a 10.301
  (declarações truncadas, 21 e 18 linhas). `gasto_ab` fica NULL, não zero.
- Gastos per capita implausíveis (R$ 0,71 por habitante) indicam despesa de AB
  classificada em outra subfunção (Vieira et al., 2022): `vw_gasto_atipico`.
- A consulta "Visão geral" do SISAB devolve 489 municípios; por indicador, 497.
- A proporção de resultados iguais a zero no SISAB cai de 34% (2018Q1) para
  1% (2023+): adesão ao registro, não atendimento.
- `FU10 - Demais Subfunções` pertence ao total da saúde: as subfunções com o
  resíduo reproduzem a função 10 ao centavo.
- A paginação por `offset` da API DEMAS é instável; `extrai_api.py` pagina por
  município.
- A divisão regional do DATASUS ainda usa a numeração antiga de 19 CRS;
  adotada a da Portaria SES-RS 320/2025 (18 CRS). Cristal e Tupanciretã
  divergem entre as duas fontes (registrado em `log_qualidade`).
