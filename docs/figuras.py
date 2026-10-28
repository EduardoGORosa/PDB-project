"""Figuras estáticas dos relatórios, lidas da camada analítica do banco.

    python docs/figuras.py      # grava docs/img/fig_*.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.bd import conecta  # noqa: E402

SAIDA = Path(__file__).parent / "img"
AZUL, AZUL_CLARO, LARANJA = "#2a78d6", "#9fb7d6", "#eb6834"
TINTA, TINTA2, GRADE = "#0b0b0b", "#52514e", "#e4e3df"
NOMES = {
    "prenatal_6_consultas": "1. Pré-natal (6 consultas)",
    "gestante_sifilis_hiv": "2. Gestantes: sífilis e HIV",
    "gestante_odontologico": "3. Gestantes: odontologia",
    "citopatologico": "4. Citopatológico",
    "cobertura_vacinal": "5. Vacinação (Pólio/Penta)",
    "hipertensao_pa_aferida": "6. Hipertensão: PA aferida",
    "diabetes_hemoglobina": "7. Diabetes: hemoglobina glicada",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRADE,
    "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.titlesize": 9.5, "axes.titlecolor": TINTA, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRADE,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "figure.dpi": 200,
})


def df(sql: str) -> pd.DataFrame:
    with conecta() as con:
        cur = con.execute(sql)
        d = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    for c in d.columns:
        valores = d[c].dropna()
        if d[c].dtype == object and len(valores) and type(valores.iloc[0]).__name__ == "Decimal":
            d[c] = d[c].astype(float)
    return d


def fig_quintis() -> None:
    sql = """
        WITH q AS (
            SELECT g.cod_ibge6, g.exercicio AS ano,
                   NTILE(5) OVER (PARTITION BY g.exercicio {particao} ORDER BY g.gasto_ab_pc) AS quintil
              FROM mv_gasto_anual g WHERE g.gasto_ab_pc IS NOT NULL)
        SELECT q.ano, q.quintil,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.percentual) AS mediana
          FROM q JOIN vw_desempenho_composto c ON c.cod_ibge6 = q.cod_ibge6 AND c.ano = q.ano
         WHERE q.ano <= 2024 GROUP BY 1, 2 ORDER BY 1, 2"""
    linhas = [("quintis estaduais", df(sql.format(particao=""))),
              ("quintis dentro do porte", df(sql.format(particao=", g.porte")))]
    anos = sorted(linhas[0][1].ano.unique())
    fig, eixos = plt.subplots(2, len(anos), figsize=(10.5, 5), sharey=True)
    for i, (rotulo, d) in enumerate(linhas):
        for ax, ano in zip(eixos[i], anos):
            s = d[d.ano == ano]
            ax.bar(s.quintil, s.mediana, color=AZUL if ano >= 2022 else AZUL_CLARO, width=0.72)
            for x, y in zip(s.quintil, s.mediana):
                if x in (1, 5):
                    ax.text(x, y + 1, f"{y:.0f}", ha="center", fontsize=7.5, color=TINTA2)
            if i == 0:
                ax.set_title(f"{ano}\n" + ("NT 5/2020" if ano < 2022 else "NT 11/2022"))
            ax.set_xticks([1, 2, 3, 4, 5])
            ax.set_ylim(0, 68)
            ax.grid(axis="x", visible=False)
        eixos[i][0].set_ylabel(f"{rotulo}\n\nmediana do desempenho (%)", fontsize=8.5)
    fig.supxlabel("quintil de gasto em Atenção Básica por habitante (1 = menor)",
                  fontsize=8.5, color=TINTA2)
    fig.tight_layout()
    fig.savefig(SAIDA / "fig_quintis.png", bbox_inches="tight")


def fig_series() -> None:
    d = df("""SELECT s.quadrimestre, s.codigo, s.ordem, s.media_ponderada, s.meta,
                     p.efeito_financeiro, s.ajustado_portaria
                FROM mv_serie_estadual s JOIN dim_periodo p USING (quadrimestre)
               WHERE s.quadrimestre <= '2024Q3' ORDER BY s.ordem, s.quadrimestre""")
    qs = sorted(d.quadrimestre.unique())
    idx = {q: i for i, q in enumerate(qs)}
    faixas = d.drop_duplicates("quadrimestre")[["quadrimestre", "efeito_financeiro"]]
    bandas = [("sem efeito", "#efeee9"), ("parcial", "#fde6cc"), ("pleno", "#d9eedf")]

    fig, eixos = plt.subplots(2, 4, figsize=(11, 5), sharex=True)
    eixos = eixos.ravel()
    for ax, (_, s) in zip(eixos, d.groupby("ordem")):
        for efeito, cor in bandas:
            f = faixas[faixas.efeito_financeiro == efeito].quadrimestre.map(idx)
            if len(f):
                ax.axvspan(f.min() - 0.5, f.max() + 0.5, color=cor, lw=0)
        ax.plot(s.quadrimestre.map(idx), s.media_ponderada, color=AZUL, lw=2, marker="o", ms=2.8)
        aj = s[s.ajustado_portaria & (s.efeito_financeiro == "parcial")]
        ax.plot(aj.quadrimestre.map(idx), aj.media_ponderada, "x", color=TINTA, ms=6, mew=1.6)
        ax.axvline(idx["2022Q1"] - 0.5, color=LARANJA, lw=1.2, ls="--")
        for depois, grupo in s.groupby(s.quadrimestre >= "2022Q1"):
            xs = grupo.quadrimestre.map(idx)
            ax.hlines(grupo.meta.iloc[0], xs.min() - 0.4, xs.max() + 0.4,
                      color=TINTA2, lw=0.9, ls=":")
        ax.set_title(NOMES[s.codigo.iloc[0]], loc="left")
        ax.set_ylim(0, 100)
    eixos[-1].axis("off")
    eixos[-1].legend(handles=[
        Line2D([], [], color=AZUL, lw=2, label="média ponderada pela população"),
        Line2D([], [], color=TINTA2, lw=0.9, ls=":", label="meta da versão vigente"),
        Line2D([], [], color=LARANJA, lw=1.2, ls="--", label="troca de regra (NT 11/2022)"),
        Line2D([], [], color=TINTA, marker="x", lw=0, label="resultado fixado por portaria"),
        Patch(color=bandas[0][1], label="pagamento fixado (2020Q1–2021Q2)"),
        Patch(color=bandas[1][1], label="pagamento parcial (Portaria 102/2022)"),
        Patch(color=bandas[2][1], label="pagamento pelo resultado real"),
    ], loc="center", frameon=False, fontsize=8)
    ticks = [(idx[q], q[:4]) for q in qs if q.endswith("Q1")]
    for a in eixos[:7]:
        a.set_xticks([t for t, _ in ticks], [r for _, r in ticks], fontsize=7.5)
        a.tick_params(axis="x", labelbottom=True)
    fig.tight_layout()
    fig.savefig(SAIDA / "fig_series.png", bbox_inches="tight")


def fig_dispersao() -> None:
    d = df("""SELECT g.gasto_ab_pc, c.percentual, m.nome,
                     NTILE(5) OVER (ORDER BY g.gasto_ab_pc) AS quintil
                FROM vw_desempenho_composto c
                JOIN mv_gasto_anual g ON g.cod_ibge6 = c.cod_ibge6 AND g.exercicio = c.ano
                JOIN dim_municipio m ON m.cod_ibge6 = c.cod_ibge6
               WHERE c.ano = 2024 AND g.gasto_ab_pc IS NOT NULL""")
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.scatter(d.gasto_ab_pc, d.percentual, s=10, color=AZUL_CLARO, lw=0, label="município")
    med = d.groupby("quintil").agg(x=("gasto_ab_pc", "median"), y=("percentual", "median"))
    ax.plot(med.x, med.y, color=AZUL, lw=2, marker="o", ms=6, label="mediana de cada quintil")
    poa = d[d.nome == "Porto Alegre"].iloc[0]
    ax.scatter([poa.gasto_ab_pc], [poa.percentual], s=45, color=LARANJA, zorder=3,
               edgecolor="white", lw=1.5)
    ax.annotate("Porto Alegre", (poa.gasto_ab_pc, poa.percentual), xytext=(8, -12),
                textcoords="offset points", fontsize=8, color=TINTA)
    ax.set_xscale("log")
    ax.set_xlabel("gasto liquidado em Atenção Básica por habitante, 2024 (R$, escala log)")
    ax.set_ylabel("desempenho médio (%)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(SAIDA / "fig_dispersao.png", bbox_inches="tight")


def fig_zeros() -> None:
    d = df("""SELECT quadrimestre,
                     100.0 * count(*) FILTER (WHERE percentual = 0) / count(*) AS pct
                FROM fato_indicador GROUP BY 1 ORDER BY 1""")
    fig, ax = plt.subplots(figsize=(7, 2.4))
    ax.bar(range(len(d)), d.pct, color=AZUL, width=0.72)
    ax.set_xticks(range(len(d)), d.quadrimestre, rotation=90, fontsize=7)
    ax.set_ylabel("% de resultados = 0")
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(SAIDA / "fig_zeros.png", bbox_inches="tight")


if __name__ == "__main__":
    SAIDA.mkdir(exist_ok=True)
    for f in (fig_quintis, fig_series, fig_dispersao, fig_zeros):
        f()
    print("figuras em", SAIDA)
