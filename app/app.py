"""Aplicação de visualização — Gasto × Desempenho na Atenção Primária (RS).

    streamlit run app/app.py

Quatro visões (anteprojeto, seção 5): panorama estadual, ficha do município,
comparação entre indicadores e qualidade dos dados. Toda a lógica analítica
está no banco (sql/02_analitico.sql); a aplicação só filtra e desenha.
"""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg
import streamlit as st

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://pbd:pbd@127.0.0.1:5433/pbd")
CORTE_REGIME = "2022Q1"

NOMES = {
    "prenatal_6_consultas": "1. Pré-natal (6 consultas)",
    "gestante_sifilis_hiv": "2. Gestantes: sífilis e HIV",
    "gestante_odontologico": "3. Gestantes: odontologia",
    "citopatologico": "4. Citopatológico",
    "cobertura_vacinal": "5. Vacinação (Pólio/Penta)",
    "hipertensao_pa_aferida": "6. Hipertensão: PA aferida",
    "diabetes_hemoglobina": "7. Diabetes: hemoglobina glicada",
}
COMPOSTO, ISF = "Média dos 7 indicadores", "Indicador sintético (ISF)"

st.set_page_config(page_title="Gasto × Desempenho na APS — RS", layout="wide")


@st.cache_data(ttl=600)
def consulta(sql: str, params: tuple = ()) -> pd.DataFrame:
    with psycopg.connect(DATABASE_URL) as con:
        con.execute("SET search_path TO pbd, public")
        cur = con.execute(sql, params)
        df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    # NUMERIC chega como Decimal; o plotly quer float
    for c in df.columns:
        valores = df[c].dropna()
        if df[c].dtype == object and len(valores) and type(valores.iloc[0]).__name__ == "Decimal":
            df[c] = df[c].astype(float)
    return df


# =====================================================================
# 1. PANORAMA ESTADUAL
# =====================================================================
def panorama() -> None:
    st.header("Panorama estadual")
    st.caption("Cada ponto é um município: gasto liquidado em Atenção Básica (subfunção "
               "10.301) por habitante × desempenho médio do ano (média dos quadrimestres).")

    anos = consulta("SELECT DISTINCT ano FROM vw_painel_anual WHERE ano <= 2024 ORDER BY 1").ano.tolist()
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    medida = c1.selectbox("Indicador", [COMPOSTO, ISF] + list(NOMES.values()))
    ano = c2.selectbox("Exercício", anos, index=len(anos) - 1)
    cor = c3.selectbox("Cor", ["Porte", "Coordenadoria"])
    sem_pequenos = c4.checkbox("Excluir até 5 mil hab.", help=(
        "Em municípios pequenos o percentual oscila muito por ter poucos casos."))

    if medida == COMPOSTO:
        sql = """SELECT m.nome AS municipio, m.crs, g.porte, g.populacao, g.gasto_ab_pc,
                        c.percentual AS desempenho
                   FROM vw_desempenho_composto c
                   JOIN mv_gasto_anual g ON g.cod_ibge6 = c.cod_ibge6 AND g.exercicio = c.ano
                   JOIN vw_municipio m ON m.cod_ibge6 = c.cod_ibge6
                  WHERE c.ano = %s AND g.gasto_ab_pc IS NOT NULL"""
        df = consulta(sql, (ano,))
    elif medida == ISF:
        sql = """SELECT m.nome AS municipio, m.crs, g.porte, g.populacao, g.gasto_ab_pc,
                        i.isf AS desempenho
                   FROM vw_isf_anual i
                   JOIN mv_gasto_anual g ON g.cod_ibge6 = i.cod_ibge6 AND g.exercicio = i.ano
                   JOIN vw_municipio m ON m.cod_ibge6 = i.cod_ibge6
                  WHERE i.ano = %s AND g.gasto_ab_pc IS NOT NULL"""
        df = consulta(sql, (ano,))
    else:
        codigo = next(k for k, v in NOMES.items() if v == medida)
        df = consulta("""SELECT municipio, crs, porte, populacao, gasto_ab_pc,
                                percentual AS desempenho
                           FROM vw_painel_anual WHERE ano = %s AND codigo = %s""", (ano, codigo))
    if sem_pequenos:
        df = df[df.populacao >= 5000]

    no_porte = st.toggle("Quintis dentro de cada faixa de porte", help=(
        "O gasto per capita cai com o porte, e o desempenho também varia com o porte. "
        "Ligado, cada município só é comparado com os de mesmo porte."))
    grupos = df.groupby("porte") if no_porte else [(None, df)]
    df["quintil"] = pd.concat([
        pd.qcut(g.gasto_ab_pc.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
        for _, g in grupos])
    eixo_y = "ISF (0–10)" if medida == ISF else "desempenho (%)"

    fig = px.scatter(df, x="gasto_ab_pc", y="desempenho",
                     color="porte" if cor == "Porte" else "crs",
                     size="populacao", size_max=40, log_x=True, hover_name="municipio",
                     category_orders={"porte": sorted(df.porte.unique())},
                     labels={"gasto_ab_pc": "gasto em Atenção Básica por habitante (R$, escala log)",
                             "desempenho": eixo_y, "porte": "porte", "crs": "CRS"})
    fig.update_layout(height=560, legend=dict(font=dict(size=10)))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Quintis de gasto")
    st.caption("A distribuição do gasto é assimétrica; a mediana de cada quintil descreve a "
               "maioria dos municípios melhor que uma correlação, dominada pelos extremos.")
    tab = df.groupby("quintil").apply(lambda g: pd.Series({
        "municípios": len(g),
        "gasto per capita (R$)": f"{g.gasto_ab_pc.min():,.0f} – {g.gasto_ab_pc.max():,.0f}",
        "mediana do desempenho": round(g.desempenho.median(), 2),
        "média ponderada pela população": round((g.desempenho * g.populacao).sum() / g.populacao.sum(), 2),
    }), include_groups=False)
    st.dataframe(tab, use_container_width=True)
    regime = "NT 5/2020" if ano < 2022 else "NT 11/2022"
    st.info(f"Regra de cálculo vigente em {ano}: **{regime}**. Associação, não causalidade: "
            "a subfunção 10.301 reúne recurso próprio, estadual e federal.")


# =====================================================================
# 2. FICHA DO MUNICÍPIO
# =====================================================================
def ficha() -> None:
    st.header("Ficha do município")
    municipios = consulta("SELECT cod_ibge6, nome, crs, regiao_nome FROM vw_municipio ORDER BY nome")
    nome = st.selectbox("Município", municipios.nome,
                        index=int(municipios.index[municipios.nome == "Porto Alegre"][0]))
    m = municipios[municipios.nome == nome].iloc[0]
    cod = int(m.cod_ibge6)
    st.caption(f"{m.crs} · Região de saúde {m.regiao_nome}")

    gasto = consulta("""SELECT exercicio, populacao, porte, gasto_ab, gasto_ab_pc, pct_ab_na_saude
                          FROM mv_gasto_anual WHERE cod_ibge6 = %s ORDER BY exercicio""", (cod,))
    ult = gasto.dropna(subset=["gasto_ab_pc"]).iloc[-1]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("População", f"{int(ult.populacao):,}".replace(",", "."), help=f"exercício {ult.exercicio}")
    k2.metric("Porte", ult.porte[3:])
    k3.metric("Gasto AB por habitante", f"R$ {ult.gasto_ab_pc:,.2f}")
    k4.metric("Atenção Básica no gasto em saúde", f"{ult.pct_ab_na_saude:.1f}%")

    c1, c2 = st.columns(2)
    fig = px.bar(gasto, x="exercicio", y="gasto_ab_pc", text_auto=".0f",
                 labels={"exercicio": "exercício", "gasto_ab_pc": "R$ por habitante"},
                 title="Gasto liquidado em Atenção Básica por habitante")
    c1.plotly_chart(fig, use_container_width=True)

    serie = consulta("""SELECT f.quadrimestre, i.codigo, f.percentual, i.meta
                          FROM fato_indicador f JOIN dim_indicador i USING (id_indicador)
                         WHERE f.cod_ibge6 = %s ORDER BY f.quadrimestre""", (cod,))
    serie["indicador"] = serie.codigo.map(NOMES)
    fig = px.line(serie, x="quadrimestre", y="percentual", color="indicador", markers=True,
                  title="Desempenho por quadrimestre", labels={"percentual": "%"},
                  category_orders={"indicador": list(NOMES.values())})
    _marca_corte(fig)
    fig.update_layout(legend=dict(font=dict(size=9)))
    c2.plotly_chart(fig, use_container_width=True)

    st.subheader("Comparação com municípios de porte semelhante")
    st.caption("Grupo de referência: os 20 municípios de população mais próxima, no mesmo ano "
               "(junção reflexiva no banco). Posição = % do grupo abaixo do município.")
    grupo = consulta("""SELECT ano, faixa_populacao_grupo, gasto_ab_pc,
                               ROUND(gasto_mediano_grupo::numeric, 2) AS gasto_mediano_grupo,
                               posicao_gasto, desempenho,
                               ROUND(desempenho_mediano_grupo::numeric, 2) AS desempenho_mediano_grupo,
                               posicao_desempenho, discrepancia
                          FROM vw_posicao_no_grupo WHERE cod_ibge6 = %s ORDER BY ano""", (cod,))
    if grupo.empty:
        st.warning("Município sem gasto declarado nos exercícios disponíveis.")
    else:
        st.dataframe(grupo, use_container_width=True, hide_index=True)
        ano = st.select_slider("Pares no ano", grupo.ano.tolist(), value=grupo.ano.max())
        pares = consulta("""
            SELECT m.nome, g.populacao, g.gasto_ab_pc, c.percentual AS desempenho,
                   g.cod_ibge6 = %s AS e_o_municipio
              FROM mv_gasto_anual g
              JOIN vw_desempenho_composto c ON c.cod_ibge6 = g.cod_ibge6 AND c.ano = g.exercicio
              JOIN dim_municipio m ON m.cod_ibge6 = g.cod_ibge6
             WHERE g.exercicio = %s
               AND (g.cod_ibge6 = %s OR g.cod_ibge6 IN (
                    SELECT cod_par FROM mv_grupo_referencia WHERE cod_ibge6 = %s AND ano = %s))""",
            (cod, ano, cod, cod, ano))
        fig = px.scatter(pares, x="gasto_ab_pc", y="desempenho", hover_name="nome",
                         color="e_o_municipio", color_discrete_map={True: "#d62728", False: "#9aa5b1"},
                         labels={"gasto_ab_pc": "R$ por habitante", "desempenho": "média dos 7 (%)",
                                 "e_o_municipio": nome})
        st.plotly_chart(fig, use_container_width=True)


# =====================================================================
# 3. COMPARAÇÃO ENTRE INDICADORES
# =====================================================================
def _marca_corte(fig) -> None:
    fig.add_vline(x=CORTE_REGIME, line_dash="dash", line_color="gray")
    fig.add_annotation(x=CORTE_REGIME, y=1, yref="paper", text="NT 11/2022", showarrow=False,
                       xanchor="left", font=dict(size=10, color="gray"))


def indicadores() -> None:
    st.header("Comparação entre indicadores")
    st.caption("Desempenho estadual por quadrimestre. A linha tracejada marca a troca da regra de "
               "cálculo (NT 5/2020 → NT 11/2022): a série não é contínua nesse ponto.")
    c1, c2 = st.columns([1, 2])
    medida = c1.radio("Média", ["ponderada pela população", "simples", "sem municípios até 5 mil"])
    coluna = {"ponderada pela população": "media_ponderada", "simples": "media_simples",
              "sem municípios até 5 mil": "media_sem_pequenos"}[medida]
    escolha = c2.multiselect("Indicadores", list(NOMES.values()), default=list(NOMES.values()))

    serie = consulta("""SELECT s.quadrimestre, s.codigo, s.meta, s.media_simples, s.media_ponderada,
                               s.media_sem_pequenos, s.ajustado_portaria, p.efeito_financeiro
                          FROM mv_serie_estadual s JOIN dim_periodo p USING (quadrimestre)
                         ORDER BY s.quadrimestre""")
    serie["indicador"] = serie.codigo.map(NOMES)
    serie = serie[serie.indicador.isin(escolha)]

    fig = px.line(serie, x="quadrimestre", y=coluna, color="indicador", markers=True,
                  labels={coluna: "%"}, category_orders={"indicador": list(NOMES.values())})
    _marca_corte(fig)
    # faixas do efeito financeiro: quando o resultado valia dinheiro
    cores = {"sem efeito": "rgba(150,150,150,0.10)", "parcial": "rgba(255,165,0,0.15)",
             "pleno": "rgba(44,160,44,0.12)"}
    periodos = serie.drop_duplicates("quadrimestre")[["quadrimestre", "efeito_financeiro"]]
    for efeito, cor in cores.items():
        qs = periodos[periodos.efeito_financeiro == efeito].quadrimestre.tolist()
        if qs:
            fig.add_vrect(x0=qs[0], x1=qs[-1], fillcolor=cor, line_width=0,
                          annotation_text=f"pagamento: {efeito}",
                          annotation_position="top left" if efeito == "parcial" else "bottom left",
                          annotation_font_size=9)
    ajustados = serie[serie.ajustado_portaria & (serie.efeito_financeiro == "parcial")]
    fig.add_trace(go.Scatter(x=ajustados.quadrimestre, y=ajustados[coluna], mode="markers",
                             marker=dict(symbol="x", size=11, color="black"),
                             name="resultado fixado por portaria"))
    fig.update_layout(height=560)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
**Como ler as faixas.** O repasse usa o dado com um quadrimestre de defasagem.
De 2020Q1 a 2021Q2 os repasses foram fixados em 100% do potencial (transição e
pandemia: Portarias 2.979/2019, 166/2021 e 2.396/2021). Em 2021Q3 e 2022Q1 a
Portaria GM/MS nº 102/2022 fixou parte dos indicadores (×). De 2022Q2 a 2023Q3
o resultado real foi pago integralmente. A partir de 2024 o Previne deixou de
pagar por desempenho (Portaria GM/MS nº 3.493/2024).
""")

    st.subheader("Dicionário dos indicadores")
    dic = consulta("""SELECT ordem, regime, nome, regra_numerador, regra_denominador, meta, peso,
                             nota_tecnica, vigencia_inicio, vigencia_fim
                        FROM dim_indicador ORDER BY ordem, regime""")
    st.dataframe(dic, use_container_width=True, hide_index=True)


# =====================================================================
# 4. QUALIDADE DOS DADOS
# =====================================================================
def qualidade() -> None:
    st.header("Qualidade dos dados")

    c1, c2 = st.columns(2)
    finbra = consulta("""SELECT exercicio, count(*) AS municipios, count(gasto_ab) AS com_10301
                           FROM mv_gasto_anual GROUP BY 1 ORDER BY 1""")
    finbra["sem_10301"] = finbra.municipios - finbra.com_10301
    c1.subheader("FINBRA — cobertura por exercício")
    c1.dataframe(finbra, hide_index=True, use_container_width=True)

    sisab = consulta("""SELECT quadrimestre, count(DISTINCT cod_ibge6) AS municipios,
                               count(*) FILTER (WHERE percentual IS NULL) AS nulos,
                               ROUND(100.0 * count(*) FILTER (WHERE percentual = 0) / count(*), 1)
                                   AS pct_zeros
                          FROM fato_indicador GROUP BY 1 ORDER BY 1""")
    c2.subheader("SISAB — cobertura por quadrimestre")
    fig = px.bar(sisab, x="quadrimestre", y="pct_zeros",
                 labels={"pct_zeros": "% de resultados iguais a zero"})
    _marca_corte(fig)
    c2.plotly_chart(fig, use_container_width=True)
    c2.caption("Os 497 municípios estão em todos os quadrimestres, sem valores nulos. A queda dos "
               "zeros acompanha a adesão ao registro no SISAB, e não necessariamente o atendimento.")

    st.subheader("Inconsistências registradas na carga")
    log = consulta("""SELECT l.fonte, l.tipo, l.periodo, m.nome AS municipio, l.descricao
                        FROM log_qualidade l LEFT JOIN dim_municipio m USING (cod_ibge7)
                       ORDER BY l.fonte, l.periodo""")
    st.dataframe(log, hide_index=True, use_container_width=True)

    st.subheader("Gasto atípico (abaixo de 10% da mediana estadual)")
    st.dataframe(consulta("SELECT * FROM vw_gasto_atipico ORDER BY exercicio, gasto_ab_pc"),
                 hide_index=True, use_container_width=True)

    st.subheader("Verificações de integração")
    st.markdown("""
- **Códigos IBGE:** FINBRA usa 7 dígitos, SISAB 6; `cod_ibge6 = cod_ibge7 / 10` casa os 497
  municípios nos dois sentidos, em todos os exercícios (garantido por `CHECK` e chave estrangeira).
- **Visão das equipes:** os arquivos do SISAB coincidem com a visão *todas as equipes* em 8.946
  de 8.946 valores de 2024 (conferido contra os dados abertos da API DEMAS;
  `python -m pipeline.confere_visao`).
- **Visão geral do SISAB:** a consulta "Visão geral" do painel devolve 489 municípios, contra
  497 na consulta por indicador. A carga usa a consulta por indicador.
- **FINBRA 2018–2019:** obtidos pela API do SICONFI; a API reproduz o CSV do portal linha a linha
  (3.239 de 3.239 linhas iguais numa amostra de 2020).
- **Subfunção 10.301:** o gasto declarado na 10.301 subestima o gasto em APS de parte dos
  municípios (Vieira et al., 2022) — ver a tabela de gasto atípico.
""")


pg = st.navigation([
    st.Page(panorama, title="Panorama estadual", icon="🗺️", default=True),
    st.Page(ficha, title="Ficha do município", icon="🏛️", url_path="municipio"),
    st.Page(indicadores, title="Comparação entre indicadores", icon="📈", url_path="indicadores"),
    st.Page(qualidade, title="Qualidade dos dados", icon="🔎", url_path="qualidade"),
])
st.sidebar.markdown("**Gasto × Desempenho na Atenção Primária**  \nRio Grande do Sul, 2018–2024  \n"
                    "INF01006 — UFRGS")
pg.run()
