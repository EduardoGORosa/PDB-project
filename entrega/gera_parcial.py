"""Gera o relatório parcial a partir do relatório final.

    python entrega/gera_parcial.py

O parcial cobre o que o cronograma do anteprojeto previa até 26/10: fontes,
dimensão de indicadores, modelo, carga e qualidade, consultas básicas e
trabalhos relacionados. As seções são recortadas do relatório final, para que
os dois documentos não divirjam; muda só o resumo e entram os próximos passos.
"""

from __future__ import annotations

import re
from pathlib import Path

PASTA = Path(__file__).parent
final = (PASTA / "relatorio_final.html").read_text(encoding="utf-8")


def secao(titulo: str) -> str:
    """Do <h2> cujo texto começa com `titulo` até o próximo <h2>."""
    m = re.search(r'<h2[^>]*>' + re.escape(titulo), final)
    if not m:
        raise ValueError(f"seção não encontrada: {titulo}")
    fim = final.find("<h2", m.end())
    return final[m.start(): fim if fim != -1 else final.rindex("</html>")]


def renumera(html: str, numero: int) -> str:
    return re.sub(r"(<h2[^>]*>)\d+\.", rf"\g<1>{numero}.", html, count=1)


cabecalho = final[: final.index('<div class="resumo">')]
cabecalho = cabecalho.replace("<title>Relatório final", "<title>Relatório parcial")
cabecalho = cabecalho.replace("Relatório final.</p>", "Relatório parcial.</p>")

resumo = """<div class="resumo">
<p><b>Resumo.</b> Este relatório parcial documenta a construção da base: a extração das duas fontes
(FINBRA/SICONFI e SISAB), a dimensão de indicadores construída a partir das Notas Técnicas e Portarias, o
modelo relacional, a carga com suas verificações de integração e qualidade, as consultas básicas e o
levantamento de trabalhos relacionados. A base integra os 497 municípios do RS de 2018 a 2024; a junção
pelo código IBGE casa os municípios nos dois sentidos em todos os exercícios, e a mudança de regra de 2022
fica garantida no esquema por chaves estrangeiras compostas. Ao reconstituir os atos normativos,
verificamos que o resultado dos indicadores só determinou integralmente o repasse em 2022Q2–2023Q3, o que
passa a ser marcado em cada quadrimestre. As análises da pergunta central (consultas avançadas) e a
aplicação ficam para a etapa final.</p>
</div>
"""

proximos = """<h2>9. Próximos passos</h2>
<ul>
<li><b>Consultas avançadas</b> (02/11): quintis de gasto com <code>NTILE</code>, variação anual com
<code>LAG</code> por regime, grupos de referência por porte com junção reflexiva, agregações por
coordenadoria com CTEs encadeadas, médias ponderadas e análise sem municípios pequenos.</li>
<li><b>Controle do porte.</b> As consultas básicas já mostram que o gasto per capita cai fortemente com o
porte do município; a análise por quintis precisa ser repetida dentro de cada faixa de porte para não
atribuir à gestão o que decorre da escala.</li>
<li><b>Aplicação de visualização</b> (30/11): as quatro visões do anteprojeto, sobre as visões
materializadas do banco.</li>
<li><b>Apresentação e relatório final</b> (01/12).</li>
</ul>
"""

partes = [
    cabecalho, resumo,
    secao("1. Objetivo"), secao("2. Fontes"), secao("3. A regra"), secao("4. Modelo"),
    secao("5. Carga"), secao("6. Consultas básicas"),
    renumera(secao("9. Trabalhos relacionados"), 7),
    renumera(secao("10. Limitações"), 8),
    proximos,
    renumera(secao("12. Responsabilidades"), 10),
    secao("Referências"),
    "</html>\n",
]
html = "".join(partes)
# o parágrafo final de "Trabalhos relacionados" cita resultados; no parcial, só a proposta
html = html.replace("pela análise por quintis e por grupos de referência de porte em vez de correlação simples",
                    "pela análise por quintis e por grupos de referência de porte prevista em vez de correlação simples")
(PASTA / "relatorio_parcial.html").write_text(html, encoding="utf-8")
print("relatorio_parcial.html gerado")
