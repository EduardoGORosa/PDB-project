"""
VERIFICAÇÃO 3 — as duas bases realmente se juntam?

Este é o teste que decide o projeto. Roda a junção de verdade e mede:
  1. Quantos municípios casam entre FINBRA e API, ano a ano
  2. Quantas linhas de análise sobram no fim
  3. Se gasto e desempenho variam o suficiente para haver o que analisar
  4. Se há relação aparente entre gasto per capita e desempenho
  5. Se as duas fontes concordam sobre a população de cada município

Pré-requisitos:
  - arquivos finbra_AAAA.csv no diretório (verificados pelo script 02)
  - dados_brutos/previne_RS_AAAAQN.json (gerados por extrai_previne.py)

Uso:  python verifica_03_juncao.py
"""

import glob
import json
import sys
from pathlib import Path

import pandas as pd

CONTA_AB = "10.301 - Atenção Básica"
COLUNA = "Despesas Empenhadas"
VISAO = "homologadas"          # evita a triplicação por visao_equipe

OK, ATN, ERR = [], [], []


# ------------------------------------------------------------------- carregar
def carrega_finbra():
    linhas = []
    for arq in sorted(glob.glob("finbra_*.csv")):
        ano = int(Path(arq).stem.split("_")[-1])
        df = pd.read_csv(arq, sep=";", encoding="latin1", skiprows=3, decimal=",")
        df = df[(df["Coluna"] == COLUNA) & (df["Conta"] == CONTA_AB)]
        df = df[["Cod.IBGE", "Instituição", "População", "Valor"]].copy()
        df.columns = ["cod_ibge7", "municipio_finbra", "pop_finbra", "gasto_ab"]
        df["ano"] = ano
        df["cod_ibge6"] = df["cod_ibge7"] // 10          # <<< a junção
        linhas.append(df)
    if not linhas:
        raise FileNotFoundError("nenhum finbra_AAAA.csv encontrado")
    return pd.concat(linhas, ignore_index=True)


def carrega_api():
    linhas = []
    for arq in sorted(glob.glob("dados_brutos/previne_*.json")):
        registros = json.loads(Path(arq).read_text(encoding="utf-8"))
        linhas.extend(registros)
    if not linhas:
        raise FileNotFoundError("nenhum JSON em dados_brutos/ — rode extrai_previne.py")
    df = pd.DataFrame(linhas)
    df["ano"] = df["quadrimestre"].str[:4].astype(int)
    return df


try:
    fin = carrega_finbra()
    api = carrega_api()
except FileNotFoundError as e:
    print(f"FALHA: {e}")
    sys.exit(1)

print(f"FINBRA : {len(fin):>8,} linhas  |  anos {sorted(fin['ano'].unique())}"
      .replace(",", "."))
print(f"API    : {len(api):>8,} linhas  |  anos {sorted(api['ano'].unique())}"
      .replace(",", "."))


# ------------------------------------------------------- 1. filtro e agregação
antes = len(api)
api = api[api["visao_equipe"] == VISAO]
print(f"\n=== 1. Filtro visao_equipe='{VISAO}' ===")
print(f"  {antes:,} -> {len(api):,} linhas".replace(",", "."))
if len(api) < antes:
    OK.append(f"triplicação removida ({antes} -> {len(api)})")

dupes = api.duplicated(
    ["codigo_municipio", "quadrimestre", "codigo_tipo_indicador"]).sum()
if dupes:
    print(f"  ATENÇÃO: ainda restam {dupes} duplicatas na chave natural")
    ATN.append(f"{dupes} duplicatas após o filtro — investigar")
else:
    OK.append("chave natural única após o filtro")

anual = (api.groupby(["codigo_municipio", "ano", "codigo_tipo_indicador"],
                     as_index=False)
            .agg(desempenho=("percentual_quadrimestre", "mean"),
                 quadris=("quadrimestre", "nunique"),
                 pop_sisab=("populacao", "max")))
print(f"  agregado por município × ano × indicador: {len(anual):,} linhas"
      .replace(",", "."))


# ---------------------------------------------------------------- 2. a junção
print("\n=== 2. Junção pelo código IBGE ===")
jun = anual.merge(fin, left_on=["codigo_municipio", "ano"],
                  right_on=["cod_ibge6", "ano"], how="inner")
print(f"  linhas resultantes: {len(jun):,}".replace(",", "."))

for ano in sorted(set(fin["ano"]) & set(anual["ano"])):
    m_api = set(anual.loc[anual["ano"] == ano, "codigo_municipio"])
    m_fin = set(fin.loc[fin["ano"] == ano, "cod_ibge6"])
    inter = m_api & m_fin
    pct = 100 * len(inter) / max(len(m_api | m_fin), 1)
    print(f"  {ano}:  API {len(m_api):>3}  FINBRA {len(m_fin):>3}  "
          f"casam {len(inter):>3}  ({pct:.1f}%)")
    if pct >= 90:
        OK.append(f"{ano}: {pct:.0f}% dos municípios casam")
    elif pct >= 60:
        ATN.append(f"{ano}: só {pct:.0f}% casam")
    else:
        ERR.append(f"{ano}: apenas {pct:.0f}% casam — junção quebrada")

if jun.empty:
    ERR.append("junção vazia — verificar cod_ibge6 = cod_ibge7 // 10")
    print("\nJUNÇÃO VAZIA. Causa quase certa: chave de município.")


# ----------------------------------------------------------- 3-5. sanidade
if not jun.empty:
    jun["gasto_pc"] = jun["gasto_ab"] / jun["pop_finbra"]

    print("\n=== 3. Há variação para analisar? ===")
    print(f"  gasto per capita : {jun['gasto_pc'].min():>8.2f}  |  "
          f"mediana {jun['gasto_pc'].median():>8.2f}  |  "
          f"{jun['gasto_pc'].max():>8.2f}")
    print(f"  desempenho (%)   : {jun['desempenho'].min():>8.2f}  |  "
          f"mediana {jun['desempenho'].median():>8.2f}  |  "
          f"{jun['desempenho'].max():>8.2f}")
    if jun["desempenho"].std() > 1 and jun["gasto_pc"].std() > 1:
        OK.append("ambas as variáveis têm dispersão suficiente")
    else:
        ATN.append("pouca variação — análise pode ficar sem contraste")

    print("\n=== 4. Gasto × desempenho, por quintil de gasto ===")
    for cod, g in jun.groupby("codigo_tipo_indicador"):
        if len(g) < 25:
            continue
        g = g.copy()
        g["quintil"] = pd.qcut(g["gasto_pc"], 5, labels=[1, 2, 3, 4, 5],
                               duplicates="drop")
        med = g.groupby("quintil", observed=True)["desempenho"].median()
        corr = g["gasto_pc"].corr(g["desempenho"], method="spearman")
        traco = "  ".join(f"Q{q}:{v:5.1f}" for q, v in med.items())
        print(f"  indicador {cod:>3}   {traco}   (rho={corr:+.2f})")
    OK.append("consulta avançada (quintis) executa sobre os dados reais")

    print("\n=== 5. As duas fontes concordam sobre a população? ===")
    pop = jun.dropna(subset=["pop_sisab", "pop_finbra"]).copy()
    if not pop.empty:
        pop["dif"] = (pop["pop_sisab"] - pop["pop_finbra"]).abs() / pop["pop_finbra"]
        print(f"  divergência mediana: {100*pop['dif'].median():.1f}%")
        print(f"  acima de 20%: {int((pop['dif'] > .2).sum())} linhas")
        if pop["dif"].median() < 0.15:
            OK.append("populações das duas fontes são compatíveis")
        else:
            ATN.append("populações divergem — escolher e documentar uma fonte")

    Path("saida").mkdir(exist_ok=True)
    jun.to_csv("saida/base_analise.csv", index=False)
    print(f"\n  base de análise salva: saida/base_analise.csv "
          f"({len(jun):,} linhas)".replace(",", "."))


print("\n" + "=" * 62)
for t, itens in (("OK      ", OK), ("ATENÇÃO ", ATN), ("FALHA   ", ERR)):
    for i in itens:
        print(f"{t} {i}")
print("=" * 62)
if ERR:
    print("VEREDITO: o projeto NÃO fecha como está. Resolver as falhas.")
    sys.exit(1)
print("VEREDITO: o projeto é viável — as bases se juntam e há o que analisar.")
