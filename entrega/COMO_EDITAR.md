# Entregáveis — o que é cada arquivo

## Entregas de outubro–dezembro

| Entrega | Para submeter | Fonte |
|---|---|---|
| **Relatório parcial** | `relatorio_parcial.pdf` | gerado de `relatorio_final.html` por `gera_parcial.py` |
| **Relatório final** | `relatorio_final.pdf` | `relatorio_final.html` |
| **Apresentação final** — 11 slides | `apresentacao_final.pdf` | `apresentacao_final.html` |

Todo número nesses documentos saiu de consulta à base (`sql/03_*`, `sql/04_*`)
ou de ato normativo citado. As figuras vêm de `docs/figuras.py` (lê o banco) e
as telas da aplicação, de capturas do Streamlit (`docs/img/app_*.png`).

**Antes de submeter:** preencher a seção "Responsabilidades" (em vermelho) do
relatório final — o parcial a herda ao ser regerado.

```bash
python docs/figuras.py                 # se a base mudou
python entrega/gera_parcial.py         # sempre que o relatório final mudar
cd entrega
chromium --headless --no-pdf-header-footer --print-to-pdf=relatorio_final.pdf relatorio_final.html
chromium --headless --no-pdf-header-footer --print-to-pdf=relatorio_parcial.pdf relatorio_parcial.html
chromium --headless --no-pdf-header-footer --print-to-pdf=apresentacao_final.pdf apresentacao_final.html
```

## Entrega 01 (agosto) — proposta

Duas submissões, cada uma em três formatos. **Os `.html` são a fonte de maior
fidelidade**; os `.pptx` / `.docx` existem para edição rápida em PowerPoint,
Word, Google Slides ou Google Docs, com pequenas diferenças de diagramação.

| Entrega | Para submeter | Para editar (Office/Google) | Fonte |
|---|---|---|---|
| **Visão geral** — 1 página | `visao_geral.pdf` | `visao_geral.docx` | `visao_geral.html` |
| **Apresentação** — 7 slides | `apresentacao.pdf` | `apresentacao.pptx` | `apresentacao.html` |

`linha_tempo.svg` / `.png` — a linha do tempo dos documentos oficiais, usada nas
duas peças.

## As duas peças têm as mesmas seções

Cada slide corresponde a uma seção da visão geral, que por sua vez corresponde a
um campo exigido na entrega:

1. Capa — identificação, integrantes, cooperação
2. **Resumo** — objetivo geral e objetivos específicos
3. **Base de dados** — as três fontes, volumes, a junção
4. **Modelo de dados** — o esquema, com `dim_indicador` versionada
5. **O diferencial** — resultado real ou mudança de régua?
6. **O que vamos perguntar à base** — as operações previstas
7. **Justificativa** — por que o tema cabe na disciplina

Ao editar, mantenha o paralelo: se uma seção mudar num arquivo, mude no outro.

## Escopo: os dois documentos são PROPOSTA, não relatório de resultados

A entrega é a apresentação inicial do projeto, e os campos que ela pede são
todos de proposta — não há campo de resultados.

Por isso as duas peças **caracterizam a base** (as fontes, os formatos, os
volumes, a regra de junção) e **motivam a pergunta**, mas não a respondem. O
diferencial é sustentado por **documentos oficiais** — Notas Técnicas 05/2020 e
11/2022, Portarias GM/MS 102/2022 e 3.493/2024 — e não por consulta nossa. A
linha do tempo mostra só esses documentos; não há nenhuma série de dados.

Ficaram de fora, deliberadamente, e devem voltar só quando o trabalho os
sustentar:

- a distribuição do gasto per capita (mínimo, mediana, máximo e a razão entre
  eles);
- o gráfico da série de cobertura vacinal e o salto de 48,4 pontos percentuais;
- a tabela de quintis de gasto contra desempenho, e a associação de 7,6 pontos;
- a prevalência dos denominadores (67% identificado / 28% estimado);
- o viés de adesão ao SISAB e o ruído de denominador pequeno.

Os dois últimos são o motivo mais forte para segurar os quintis: a associação
foi calculada sobre dados em que 44% das observações têm denominador menor que
30 e em que os zeros do SISAB caem de 34,8% para 1,0% ao longo da série.
Apresentar isso como resultado antes de tratar esses dois problemas expõe o
flanco mais frágil do trabalho. Tudo continua no banco, pronto para quando fizer
sentido.

## Regerar depois de editar

**Se editar o HTML** (resultado mais bonito — é o que gerou os PDFs entregues):

```bash
cd entrega
chromium --headless --no-pdf-header-footer \
  --print-to-pdf=visao_geral.pdf  visao_geral.html
chromium --headless --no-pdf-header-footer \
  --print-to-pdf=apresentacao.pdf apresentacao.html
```

**Se editar o `.pptx` / `.docx`** — exporte o PDF pelo próprio programa
(Arquivo → Exportar como PDF), ou pela linha de comando:

```bash
libreoffice --headless --convert-to pdf apresentacao.pptx visao_geral.docx
```

**Se editar o script** que gera os arquivos de escritório:

```bash
python entrega/gera_office.py     # recria .pptx e .docx do zero
```

**Se editar a linha do tempo** (`linha_tempo.svg`):

```bash
rsvg-convert -w 2640 -o linha_tempo.png linha_tempo.svg
```

## Cuidados

- **O líder está como "a definir"**, em vermelho, nos dois documentos. Trocar
  antes de submeter.
- Os `.pptx` / `.docx` usam **Arial**, que existe em qualquer máquina. Os
  `.html` usam Inter com Arial como reserva — se instalar a Inter, os PDFs
  gerados pelo Chromium ficam mais próximos do desenho original.
- **Todo número nos documentos veio de consulta ao banco ou de documento
  oficial.** Se recarregar os dados ou mudar o recorte, reconferir antes de
  reafirmar qualquer valor.

## Registro de revisão

`visao_geral_modificada.docx` é a versão editada à mão pelo Eduardo, mantida
como referência. Ela **não** é gerada por script e não deve ser sobrescrita.
As mudanças dela foram incorporadas às fontes (`.html` e `gera_office.py`):

- título passou a **Gasto x Desempenho na Atenção Primária**;
- registro mais formal em todo o texto;
- tecnologias sem número de versão (PostgreSQL · Python · Git), porque as
  versões mudam ao longo do projeto;
- fora os detalhes de implementação que ainda podem mudar: formato dos
  arquivos de origem, encoding, forma de paginação da API;
- fora os azulejos de números no topo.

Três pontos foram acrescentados de volta, e podem ser cortados se vocês
discordarem:

1. **A limitação metodológica** ("a subfunção 10.301 reúne recurso próprio,
   federal e estadual … associação, não de causalidade"). É a limitação
   assumida no CONTEXTO.md §6; sem ela o trabalho promete mais do que pode
   entregar.
2. **A menção às operações** dentro de "Volume, domínio e operações" — sem
   ela o título prometia algo que o parágrafo não continha.
3. **O campo Cooperação** no cabeçalho, que a entrega exige explicitamente.
