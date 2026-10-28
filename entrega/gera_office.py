"""Gera as versões editáveis dos entregáveis: .pptx (deck) e .docx (visão geral).

Os arquivos .html continuam sendo a fonte de maior fidelidade — estes existem
para edição rápida em PowerPoint / Word / Google Slides / Google Docs.
Todo texto entra como caixa de texto ou tabela de verdade, nunca como imagem;
só o gráfico é imagem (grafico_regime.png, regerável a partir do .svg).
"""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt as DPt, RGBColor as DRGB
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Pt

AQUI = Path(__file__).resolve().parent

# paleta — a mesma dos HTML
ESCURO   = RGBColor(0x0F, 0x2F, 0x4A)
AZUL     = RGBColor(0x0F, 0x5C, 0x8C)
AZUL_CL  = RGBColor(0x4D, 0xA3, 0xD8)
AZUL_PL  = RGBColor(0x7F, 0xB8, 0xDD)
AZUL_TX  = RGBColor(0xA9, 0xC4, 0xD8)
TINTA    = RGBColor(0x16, 0x20, 0x2B)
GRAFITE  = RGBColor(0x5B, 0x6D, 0x80)
CINZA    = RGBColor(0x8A, 0x9A, 0xA8)
GELO     = RGBColor(0xF2, 0xF6, 0xF9)
BORDA    = RGBColor(0xC3, 0xD4, 0xE0)
BORDA_CL = RGBColor(0xD8, 0xE3, 0xEC)
VERMELHO = RGBColor(0xB0, 0x2A, 0x37)
ROSA     = RGBColor(0xFD, 0xF3, 0xF4)
BRANCO   = RGBColor(0xFF, 0xFF, 0xFF)

FONTE = "Arial"   # universal; Inter não está instalada em toda máquina
MARGEM = 46


# ---------------------------------------------------------------- helpers ppt
def retangulo(slide, x, y, w, h, fill=None, linha=None, esp=0.75):
    from pptx.enum.shapes import MSO_SHAPE
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Pt(x), Pt(y), Pt(w), Pt(h))
    s.shadow.inherit = False
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if linha is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = linha
        s.line.width = Pt(esp)
    return s


def _runs(paragrafo, texto, tam, cor, negrito, fonte=FONTE):
    """Interpreta **negrito** e //itálico// dentro do texto."""
    import re
    for pedaco in re.split(r"(\*\*.+?\*\*|//.+?//)", texto):
        if not pedaco:
            continue
        r = paragrafo.add_run()
        if pedaco.startswith("**") and pedaco.endswith("**"):
            r.text, r.font.bold = pedaco[2:-2], True
        elif pedaco.startswith("//") and pedaco.endswith("//"):
            r.text, r.font.italic, r.font.bold = pedaco[2:-2], True, negrito
        else:
            r.text, r.font.bold = pedaco, negrito
        r.font.size, r.font.color.rgb, r.font.name = Pt(tam), cor, fonte


def texto(slide, x, y, w, h, linhas, tam=15, cor=TINTA, negrito=False,
          espaco=1.32, alinha=PP_ALIGN.LEFT, ancora=MSO_ANCHOR.TOP,
          espaco_antes=0, fonte=FONTE):
    cx = slide.shapes.add_textbox(Pt(x), Pt(y), Pt(w), Pt(h))
    tf = cx.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = ancora
    if isinstance(linhas, str):
        linhas = [linhas]
    for i, l in enumerate(linhas):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = alinha
        p.line_spacing = espaco
        if i:
            p.space_before = Pt(espaco_antes)
        _runs(p, l, tam, cor, negrito, fonte)
    return cx


def rodape(slide, n, total=7):
    retangulo(slide, MARGEM, 500, 960 - 2 * MARGEM, 0.75, fill=BORDA_CL)
    texto(slide, MARGEM, 506, 500, 14, "Gasto x Desempenho na Atenção Primária",
          tam=10, cor=CINZA)
    texto(slide, 960 - MARGEM - 100, 506, 100, 14, f"{n} / {total}", tam=10, cor=CINZA,
          alinha=PP_ALIGN.RIGHT)


def cabecalho(slide, eyebrow, titulo, tam_titulo=29):
    texto(slide, MARGEM, 40, 800, 16, eyebrow.upper(), tam=11, cor=AZUL, negrito=True)
    texto(slide, MARGEM, 58, 880, 40, titulo, tam=tam_titulo, negrito=True, espaco=1.08)
    retangulo(slide, MARGEM, 106, 96, 4, fill=AZUL)


def caixa_cor(slide, x, y, w, h, corpo, fundo, faixa, tam=14):
    retangulo(slide, x, y, w, h, fill=fundo)
    retangulo(slide, x, y, 5, h, fill=faixa)
    texto(slide, x + 18, y + 12, w - 32, h - 24, corpo, tam=tam, espaco=1.34)


def tabela(slide, x, y, w, colunas, linhas, larguras, destaque=None):
    n_l, n_c = len(linhas) + 1, len(colunas)
    alt_cab, alt_lin = 20, 26
    g = slide.shapes.add_table(n_l, n_c, Pt(x), Pt(y), Pt(w),
                               Pt(alt_cab + alt_lin * len(linhas))).table
    g.first_row = False
    for i, lg in enumerate(larguras):
        g.columns[i].width = Pt(lg)
    g.rows[0].height = Pt(alt_cab)
    for i in range(1, n_l):
        g.rows[i].height = Pt(alt_lin)

    for j, c in enumerate(colunas):
        cel = g.cell(0, j)
        cel.fill.solid(); cel.fill.fore_color.rgb = BRANCO
        cel.margin_left = cel.margin_right = Pt(4)
        cel.vertical_anchor = MSO_ANCHOR.BOTTOM
        p = cel.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT if j and c.startswith(">") else PP_ALIGN.LEFT
        _runs(p, c.lstrip(">").upper(), 10, GRAFITE, True)

    for i, linha in enumerate(linhas, start=1):
        realce = destaque is not None and i - 1 == destaque
        for j, v in enumerate(linha):
            cel = g.cell(i, j)
            cel.fill.solid()
            cel.fill.fore_color.rgb = RGBColor(0xEA, 0xF3, 0xF9) if realce else BRANCO
            cel.margin_left = cel.margin_right = Pt(4)
            cel.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cel.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT if j and colunas[j].startswith(">") else PP_ALIGN.LEFT
            _runs(p, v, 13, TINTA, realce)
    return g


# ------------------------------------------------------------------ o deck
# As sete lâminas espelham, uma a uma, as seções da visão geral, que por sua
# vez são os campos exigidos na entrega. Nenhuma apresenta resultado de
# análise: o trabalho é uma proposta.
def monta_pptx() -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Pt(960), Pt(540)
    vazio = prs.slide_layouts[6]
    meia = (960 - 2 * MARGEM - 26) / 2
    xd = MARGEM + meia + 26
    cheia = 960 - 2 * MARGEM
    TOT = 7

    # 1 — capa
    s = prs.slides.add_slide(vazio)
    retangulo(s, 0, 0, 960, 540, fill=ESCURO)
    texto(s, MARGEM, 42, 800, 16, "INF01006 · PROJETO DE BANCO DE DADOS · UFRGS",
          tam=11, cor=AZUL_PL, negrito=True)
    texto(s, MARGEM, 64, 820, 130, ["Gasto x Desempenho", "na Atenção Primária"],
          tam=46, cor=BRANCO, negrito=True, espaco=1.06)
    retangulo(s, MARGEM, 196, 96, 4, fill=AZUL_CL)
    texto(s, MARGEM, 214, 660, 80,
          ["Integração do gasto público municipal em Atenção Básica com os indicadores de "
           "desempenho da Atenção Primária do Ministério da Saúde.",
           "497 municípios do Rio Grande do Sul · 2020–2024"],
          tam=17, cor=AZUL_TX, espaco=1.34)
    texto(s, MARGEM, 452, 420, 14, "INTEGRANTES", tam=10, cor=AZUL_PL, negrito=True)
    texto(s, MARGEM, 470, 420, 20, "Vinícius Witt Herzog · Pedro Rocha · Eduardo Rosa",
          tam=16, cor=BRANCO)
    texto(s, 500, 452, 420, 14, "COOPERAÇÃO", tam=10, cor=AZUL_PL, negrito=True)
    texto(s, 500, 470, 420, 20, "Extensão PET-Saúde Digital — GAT05 Indicadores",
          tam=16, cor=BRANCO)

    # 2 — resumo
    s = prs.slides.add_slide(vazio)
    cabecalho(s, "Resumo", "Objetivo geral e objetivos específicos")
    texto(s, MARGEM, 124, 860, 70,
          "**Objetivo geral.** Integrar, numa única base de dados, quanto cada município gasta em "
          "Atenção Básica e como esse município é avaliado nos indicadores da Atenção Primária. "
          "A pergunta é se investir mais por habitante se traduz em melhor desempenho, e quanto da "
          "variação observada vem do serviço prestado ou da regra de cálculo.",
          tam=15, espaco=1.42)
    texto(s, MARGEM, 202, 400, 18, "Objetivos específicos", tam=13.5, negrito=True)
    texto(s, MARGEM, 226, meia, 200,
          ["**1.** Modelar e implementar um esquema relacional que integre as diferentes fontes, "
           "resolvendo chaves e granularidades incompatíveis.",
           "**2.** Construir a dimensão versionada a partir das Notas Técnicas do Ministério da "
           "Saúde.",
           "**3.** Quantificar, por faixas de investimento, a associação entre gasto per capita em "
           "Atenção Básica e desempenho nos sete indicadores."],
          tam=13, espaco=1.42, espaco_antes=10)
    texto(s, xd, 226, meia, 130,
          ["**4.** Separar, na variação da série, o desempenho real do efeito da mudança de regra: "
           "a troca de Nota Técnica e a escolha entre os denominadores concorrentes.",
           "**5.** Documentar a completude e a qualidade dos dados, produzindo uma base confiável e "
           "de fácil entendimento para as análises desenvolvidas."],
          tam=13, espaco=1.42, espaco_antes=10)
    caixa_cor(s, xd, 380, meia, 74,
              "A subfunção 10.301 reúne recurso próprio, federal e estadual, e o pagamento por "
              "desempenho corresponde a apenas parte do repasse federal. A relação investigada é "
              "de **associação, não de causalidade**.", GELO, AZUL, tam=13)
    rodape(s, 2, TOT)

    # 3 — base de dados
    s = prs.slides.add_slide(vazio)
    cabecalho(s, "Base de dados", "Três fontes oficiais")
    cartoes = [
        ("FINBRA", "Tesouro Nacional · SICONFI",
         "**O gasto.** Despesa por função, subfunção 10.301 — Atenção Básica, declarada "
         "anualmente por cada município.", "651.198", "linhas · 2020–2025"),
        ("SISAB", "Ministério da Saúde",
         "**Os indicadores.** Série histórica completa, por município e quadrimestre, um "
         "relatório por indicador.", "76.538", "linhas · 2018–2025"),
        ("API DEMAS", "Ministério da Saúde",
         "**Numerador e os três denominadores.** Única fonte com o cálculo aberto; cobre apenas "
         "2024.", "26.838", "linhas · 2024"),
    ]
    lc = (960 - 2 * MARGEM - 2 * 16) / 3
    for i, (nome, org, txt, qtd, un) in enumerate(cartoes):
        x = MARGEM + i * (lc + 16)
        retangulo(s, x, 128, lc, 178, fill=BRANCO, linha=BORDA_CL, esp=1)
        retangulo(s, x, 128, lc, 5, fill=AZUL)
        texto(s, x + 20, 144, lc - 36, 24, nome, tam=19, negrito=True)
        texto(s, x + 20, 168, lc - 36, 14, org, tam=11, cor=CINZA)
        texto(s, x + 20, 190, lc - 36, 66, txt, tam=13, espaco=1.32)
        texto(s, x + 20, 258, lc - 36, 26, qtd, tam=22, cor=AZUL, negrito=True)
        texto(s, x + 20, 282, lc - 36, 14, un, tam=11, cor=CINZA)
    caixa_cor(s, MARGEM, 326, cheia, 74,
              "A junção é feita por **cod_ibge7 / 10**: o FINBRA usa código IBGE de sete dígitos; "
              "SISAB e API, de seis. Testada nos 497 municípios do estado, que somam 754.574 "
              "linhas carregadas.", GELO, AZUL)
    rodape(s, 3, TOT)

    # 4 — modelo de dados
    s = prs.slides.add_slide(vazio)
    cabecalho(s, "Modelo de dados", "A definição do indicador vira uma dimensão versionada")
    dims = [("dim_municipio", "cod_ibge6 · cod_ibge7\nnome · uf", False),
            ("dim_periodo", "quadrimestre · ano\ncompetência · regime", False),
            ("dim_indicador", "código · regime\nnome · meta · peso\nvigência · nota técnica", True),
            ("dim_conta", "função · subfunção\nnível · residual", False),
            ("populacao_municipio", "ano · fonte\npopulação", False)]
    ld = (960 - 2 * MARGEM - 4 * 11) / 5
    for i, (nome, cols, versionada) in enumerate(dims):
        x = MARGEM + i * (ld + 11)
        retangulo(s, x, 128, ld, 88, fill=BRANCO,
                  linha=VERMELHO if versionada else BORDA, esp=2 if versionada else 1)
        texto(s, x + 12, 138, ld - 22, 16, nome, tam=13 if len(nome) <= 16 else 10.5,
              cor=VERMELHO if versionada else AZUL, negrito=True, fonte="Consolas")
        texto(s, x + 12, 158, ld - 22, 50, cols.split("\n"), tam=10.5, cor=GRAFITE, espaco=1.3)
    lf = (960 - 2 * MARGEM - 11) / 2
    retangulo(s, MARGEM, 228, lf, 76, fill=GELO, linha=AZUL, esp=1)
    texto(s, MARGEM + 14, 240, lf - 28, 16, "fato_despesa", tam=13, cor=ESCURO,
          negrito=True, fonte="Consolas")
    texto(s, MARGEM + 14, 262, lf - 28, 20,
          "município × exercício × estágio × conta → valor", tam=10.5, cor=GRAFITE, espaco=1.34)
    retangulo(s, MARGEM + lf + 11, 228, lf, 76, fill=GELO, linha=AZUL, esp=1)
    texto(s, MARGEM + lf + 25, 240, lf - 28, 16, "fato_indicador", tam=13, cor=ESCURO,
          negrito=True, fonte="Consolas")
    texto(s, MARGEM + lf + 25, 262, lf - 28, 30,
          ["município × quadrimestre × versão do indicador × visão × fonte",
           "percentual · numerador · den. identificado / estimado / utilizado"],
          tam=10.5, cor=GRAFITE, espaco=1.34)
    caixa_cor(s, MARGEM, 322, cheia, 108,
              "**Por que versionar.** A Nota Técnica 05/2020 vigorou até 2021Q3 e foi substituída pela 11/2022 a partir de 2022Q1. A mudança não foi apenas de redação: cinco dos sete indicadores passaram a ter outro nome no painel do SISAB. Tratar a série como contínua arrisca, portanto, comparar medidas diferentes sob o mesmo rótulo. Por isso cada fato aponta para uma versão datada do indicador, e a dim_indicador é montada a partir das próprias Notas Técnicas, já que nenhuma das três fontes publica nome, regra ou meta.", GELO, AZUL)
    rodape(s, 4, TOT)

    # 5 — o diferencial
    s = prs.slides.add_slide(vazio)
    cabecalho(s, "O diferencial", "Resultado real ou mudança de régua?")
    s.shapes.add_picture(str(AQUI / "linha_tempo.png"), Pt(MARGEM), Pt(124), width=Pt(cheia))
    texto(s, MARGEM, 268, 860, 18,
          "Os documentos oficiais que regem o cálculo dos indicadores, ao longo da vigência do "
          "Previne Brasil.", tam=12.5, cor=GRAFITE)
    caixa_cor(s, MARGEM, 300, cheia, 132,
              "**Um mesmo indicador pode ter dois valores: o publicado e o usado no cálculo do repasse.** A Portaria GM/MS nº 102/2022 determinou que, em indicadores e quadrimestres específicos, o alcance fosse considerado 100% **apenas para fins de financiamento**, enquanto o alcance medido era outro. Foi o caso da cobertura vacinal de Poliomielite e Pentavalente. A troca de Nota Técnica, por sua vez, atinge os 22 quadrimestres da série.", ROSA, VERMELHO)
    rodape(s, 5, TOT)

    # 6 — o que vamos perguntar à base
    s = prs.slides.add_slide(vazio)
    cabecalho(s, "O que vamos perguntar à base", "As operações previstas")
    texto(s, MARGEM, 128, meia, 20, "Básicas", tam=14, cor=AZUL, negrito=True)
    texto(s, MARGEM, 156, meia, 140,
          ["Gasto per capita por município e por ano",
           "Ranking de desempenho por indicador",
           "Evolução quadrimestral de cada indicador",
           "Composição do orçamento de saúde por subfunção",
           "Cobertura e completude dos dados por ano"],
          tam=13.5, espaco=1.5, espaco_antes=4)
    texto(s, xd, 128, meia, 20, "Avançadas", tam=14, cor=AZUL, negrito=True)
    texto(s, xd, 156, meia, 160,
          ["Faixas de gasto contra faixas de desempenho (NTILE)",
           "Variação ano a ano com funções de janela",
           "Comparação entre municípios de porte semelhante",
           "Recálculo do indicador sob cada um dos três denominadores",
           "Quanto da variação é serviço prestado e quanto é mudança de regra"],
          tam=13.5, espaco=1.5, espaco_antes=4)
    rodape(s, 6, TOT)

    # 7 — justificativa
    s = prs.slides.add_slide(vazio)
    cabecalho(s, "Justificativa", "Por que o tema cabe na disciplina")
    LARG_ROTULO, GOTEIRA = 212, 24
    larg_texto = 960 - 2 * MARGEM - LARG_ROTULO - GOTEIRA
    linhas = [
        ("Chaves e granularidades incompatíveis",
         "O código IBGE tem seis dígitos em duas fontes e sete na terceira; o gasto é anual e os "
         "indicadores são quadrimestrais; os formatos de arquivo diferem entre si. Sem tratamento "
         "prévio, a junção não retorna nenhuma linha.", 62),
        ("O indicador muda de definição",
         "A regra de cálculo mudou em 2022 e há denominadores concorrentes por registro. A "
         "definição do indicador torna-se uma **dimensão versionada**, com vigência e nota "
         "técnica próprias.", 44),
        ("Volume, domínio e operações",
         "Três bases oficiais e abertas sobre o gasto em saúde e o desempenho dos 497 municípios "
         "do Rio Grande do Sul, seguindo as normas de extensão estabelecidas pelo projeto "
         "PET-Saúde Digital. As consultas previstas empregam funções de janela, CTEs e agregação "
         "por faixa.", 62),
    ]
    y = 136
    for rotulo, txt, altura in linhas:
        texto(s, MARGEM, y, LARG_ROTULO, 20, rotulo, tam=13.5, cor=AZUL, negrito=True, espaco=1.3)
        texto(s, MARGEM + LARG_ROTULO + GOTEIRA, y, larg_texto, altura, txt,
              tam=13.5, espaco=1.46)
        y += altura + 18
    rodape(s, 7, TOT)

    destino = AQUI / "apresentacao.pptx"
    prs.save(destino)
    return destino


# ------------------------------------------------------------ a visão geral
def _sombra(celula, cor_hex):
    tc = celula._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), cor_hex)
    tc.append(sh)


def _p(cont, texto_, tam=8.1, cor=DRGB(0x16, 0x20, 0x2B), negrito=False,
       espaco=6, antes=0, alinha=WD_ALIGN_PARAGRAPH.LEFT):
    import re
    p = cont.add_paragraph() if hasattr(cont, "add_paragraph") else cont
    p.alignment = alinha
    pf = p.paragraph_format
    pf.space_after = DPt(espaco); pf.space_before = DPt(antes)
    pf.line_spacing = 1.02
    for pedaco in re.split(r"(\*\*.+?\*\*)", texto_):
        if not pedaco:
            continue
        r = p.add_run()
        if pedaco.startswith("**") and pedaco.endswith("**"):
            r.text, r.bold = pedaco[2:-2], True
        else:
            r.text, r.bold = pedaco, negrito
        r.font.size, r.font.color.rgb, r.font.name = DPt(tam), cor, "Arial"
    return p


def monta_docx() -> Path:
    AZ = DRGB(0x0F, 0x5C, 0x8C); GR = DRGB(0x5B, 0x6D, 0x80); VM = DRGB(0xB0, 0x2A, 0x37)
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
    for m in ("top_margin", "bottom_margin"):
        setattr(sec, m, Inches(0.42))
    sec.left_margin = sec.right_margin = Inches(0.55)

    _p(doc, "INF01006 · PROJETO DE BANCO DE DADOS · UFRGS",
       tam=7.8, cor=AZ, negrito=True, espaco=3)
    _p(doc, "Gasto x Desempenho na Atenção Primária", tam=17, negrito=True, espaco=2)
    _p(doc, "Integração do gasto público municipal em Atenção Básica com os indicadores de "
            "desempenho da Atenção Primária do Ministério da Saúde. 497 municípios do Rio Grande "
            "do Sul, 2020–2024.", tam=9, cor=GR, espaco=9)

    ident = doc.add_table(rows=2, cols=4)
    ident.style = "Table Grid"
    dados = [("INTEGRANTES", "Vinícius Witt Herzog · Pedro Rocha · Eduardo Rosa",
              "LÍDER", "a definir"),
             ("COOPERAÇÃO", "Extensão PET-Saúde Digital — GAT05 Indicadores",
              "TECNOLOGIAS", "PostgreSQL · Python · Git")]
    for i, linha in enumerate(dados):
        for j, v in enumerate(linha):
            cel = ident.cell(i, j)
            _sombra(cel, "F2F6F9")
            cel.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            rotulo = j % 2 == 0
            _p(cel.paragraphs[0], v, tam=7.4 if rotulo else 8.8,
               cor=GR if rotulo else DRGB(0x16, 0x20, 0x2B), negrito=rotulo, espaco=0)
            if v == "a definir":
                cel.paragraphs[0].runs[0].font.color.rgb = VM
                cel.paragraphs[0].runs[0].bold = True

    def secao(titulo):
        _p(doc, titulo.upper(), tam=7.8, cor=AZ, negrito=True, espaco=3, antes=8)

    secao("Resumo")
    _p(doc, "**Objetivo geral.** Integrar, numa única base de dados, quanto cada município gasta "
            "em Atenção Básica e como esse município é avaliado nos indicadores da Atenção "
            "Primária. A pergunta é se investir mais por habitante se traduz em melhor "
            "desempenho, e quanto da variação observada vem do serviço prestado ou da regra de "
            "cálculo.", alinha=WD_ALIGN_PARAGRAPH.JUSTIFY)
    _p(doc, "**Objetivos específicos:**", espaco=3)
    for i, o in enumerate([
        "Modelar e implementar um esquema relacional que integre as diferentes fontes, resolvendo "
        "chaves e granularidades incompatíveis.",
        "Construir a dimensão versionada a partir das Notas Técnicas do Ministério da Saúde.",
        "Quantificar, por faixas de investimento, a associação entre gasto per capita em Atenção "
        "Básica e desempenho nos sete indicadores.",
        "Separar, na variação da série, o desempenho real do efeito da mudança de regra: a troca "
        "de Nota Técnica e a escolha entre os denominadores concorrentes.",
        "Documentar a completude e a qualidade dos dados, produzindo uma base confiável e de fácil "
        "entendimento para as análises desenvolvidas.",
    ], 1):
        p = _p(doc, f"{i}. {o}", espaco=2, alinha=WD_ALIGN_PARAGRAPH.JUSTIFY)
        p.paragraph_format.left_indent = Inches(0.22)
    _p(doc, "A subfunção 10.301 reúne recurso próprio, federal e estadual, e o pagamento por "
            "desempenho corresponde a apenas parte do repasse federal. A relação investigada é de "
            "**associação, não de causalidade**.", tam=7.6, cor=GR, antes=2,
       alinha=WD_ALIGN_PARAGRAPH.JUSTIFY)

    secao("Base de dados")
    fontes = doc.add_table(rows=4, cols=4); fontes.style = "Table Grid"
    cab = ["FONTE", "PAPEL", "COBERTURA", "REGISTROS"]
    corpo = [["FINBRA — Tesouro Nacional", "o gasto — despesa por função, subfunção 10.301",
              "2020–2025 · município × ano", "651.198"],
             ["SISAB — Ministério da Saúde", "os indicadores — série histórica",
              "2018–2025 · município × quadrimestre", "76.538"],
             ["API DEMAS — Ministério da Saúde", "numerador e os três denominadores",
              "2024 · + visão de equipe", "26.838"]]
    for j, c in enumerate(cab):
        _p(fontes.cell(0, j).paragraphs[0], c, tam=7.2, cor=GR, negrito=True, espaco=0)
    for i, linha in enumerate(corpo, 1):
        for j, v in enumerate(linha):
            _p(fontes.cell(i, j).paragraphs[0], v, tam=7.8, espaco=0,
               alinha=WD_ALIGN_PARAGRAPH.RIGHT if j == 3 else WD_ALIGN_PARAGRAPH.LEFT)
    _p(doc, "Junção por **cod_ibge7 / 10**: o FINBRA usa código IBGE de sete dígitos; SISAB e API, "
            "de seis. Testada nos 497 municípios do estado, que somam 754.574 linhas carregadas.",
       tam=7.6, cor=GR, antes=3, alinha=WD_ALIGN_PARAGRAPH.JUSTIFY)

    secao("Modelo de dados")
    md = doc.add_table(rows=7, cols=2); md.style = "Table Grid"
    for j, c in enumerate(["TABELA", "GRÃO / ATRIBUTOS"]):
        _p(md.cell(0, j).paragraphs[0], c, tam=7.2, cor=GR, negrito=True, espaco=0)
    linhas_md = [("dim_municipio", "cod_ibge6 · cod_ibge7 · nome · uf"),
                 ("dim_periodo", "quadrimestre · ano · competência · regime"),
                 ("dim_indicador (versionada)",
                  "código · regime · nome · meta · peso · vigência · nota técnica"),
                 ("dim_conta", "função · subfunção · nível · residual"),
                 ("fato_despesa", "município × exercício × estágio × conta → valor"),
                 ("fato_indicador",
                  "município × quadrimestre × versão do indicador × visão × fonte")]
    for i, (a, b) in enumerate(linhas_md, 1):
        _p(md.cell(i, 0).paragraphs[0], f"**{a}**", tam=7.8, espaco=0)
        _p(md.cell(i, 1).paragraphs[0], b, tam=7.8, espaco=0)
    _p(doc, "Cada fato aponta para uma versão datada do indicador, de modo que 2021 e 2022 não sejam tratados como a mesma medida.", tam=7.6, cor=GR, antes=3,
       alinha=WD_ALIGN_PARAGRAPH.JUSTIFY)

    secao("Resultado real ou mudança de régua?")
    doc.add_picture(str(AQUI / "linha_tempo.png"), width=Inches(5.7))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.space_after = DPt(3)
    _p(doc, "**Os documentos oficiais que regem o cálculo dos indicadores.** A Portaria GM/MS nº 102/2022 determinou que, em indicadores e quadrimestres específicos, o alcance fosse considerado 100% apenas para fins de financiamento, enquanto o alcance medido era outro. Foi o caso da cobertura vacinal de Poliomielite e Pentavalente. Um mesmo indicador passa, assim, a ter dois valores: o publicado e o que entra no cálculo do repasse.",
       tam=7.6, cor=GR, alinha=WD_ALIGN_PARAGRAPH.JUSTIFY)

    secao("O que vamos perguntar à base")
    ops = doc.add_table(rows=1, cols=2)
    ops.autofit = True

    def _lista(celula, titulo, itens):
        primeiro = celula.paragraphs[0]
        primeiro.paragraph_format.space_after = DPt(1)
        primeiro.paragraph_format.line_spacing = 1.0
        _p(primeiro, f"**{titulo}**", tam=8.1, espaco=1)
        for it in itens:
            p_ = celula.add_paragraph(style="List Bullet")
            pf = p_.paragraph_format
            pf.space_after = pf.space_before = DPt(0)
            pf.line_spacing = 1.05
            pf.left_indent = Inches(0.18)
            _p(p_, it, tam=8.1, espaco=0)

    _lista(ops.cell(0, 0), "Básicas.",
           ["Gasto per capita por município e por ano",
            "Ranking de desempenho por indicador",
            "Evolução quadrimestral de cada indicador",
            "Composição do orçamento de saúde por subfunção",
            "Cobertura e completude dos dados por ano"])
    _lista(ops.cell(0, 1), "Avançadas.",
           ["Faixas de gasto contra faixas de desempenho (NTILE)",
            "Variação ano a ano com funções de janela",
            "Comparação entre municípios de porte semelhante",
            "Recálculo do indicador sob cada um dos três denominadores",
            "Quanto da variação é serviço prestado e quanto é mudança de regra"])

    secao("Justificativa — por que o tema cabe na disciplina")
    _p(doc, "**Chaves e granularidades incompatíveis.** O código IBGE tem seis dígitos em duas "
            "fontes e sete na terceira; o gasto é anual e os indicadores são quadrimestrais; os "
            "formatos de arquivo diferem entre si. Sem tratamento prévio, a junção não retorna "
            "nenhuma linha.", alinha=WD_ALIGN_PARAGRAPH.JUSTIFY, espaco=3)
    _p(doc, "**O indicador muda de definição.** A regra de cálculo mudou em 2022 e há "
            "denominadores concorrentes por registro. A definição do indicador torna-se uma "
            "**dimensão versionada**, com vigência e nota técnica próprias.",
       alinha=WD_ALIGN_PARAGRAPH.JUSTIFY, espaco=3)
    _p(doc, "**Volume, domínio e operações.** Três bases oficiais e abertas sobre o gasto em saúde "
            "e o desempenho dos 497 municípios do Rio Grande do Sul, seguindo as normas de "
            "extensão estabelecidas pelo projeto PET-Saúde Digital. As consultas previstas "
            "empregam funções de janela, CTEs e agregação por faixa.",
       alinha=WD_ALIGN_PARAGRAPH.JUSTIFY)

    destino = AQUI / "visao_geral.docx"
    doc.save(destino)
    return destino


if __name__ == "__main__":
    print("pptx →", monta_pptx())
    print("docx →", monta_docx())
