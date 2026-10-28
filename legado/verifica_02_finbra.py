"""
VERIFICAÇÃO 2 — os arquivos do FINBRA são consistentes entre os anos?

Responde:
  1. Todo ano tem as mesmas colunas? (deriva de esquema entre exercícios)
  2. A subfunção 10.301 (Atenção Básica) existe em todos os anos?
  3. Quantos municípios têm o dado preenchido, ano a ano?
  4. Os códigos IBGE são estáveis? Há colisão ao truncar para 6 dígitos?
  5. Quantos municípios têm gasto zero ou ausente? (candidatos a limpeza)

Uso:
  python verifica_02_finbra.py finbra_2020.csv finbra_2021.csv ...
  python verifica_02_finbra.py *.csv
"""

import sys
from pathlib import Path

import pandas as pd

CONTA_AB = "10.301 - Atenção Básica"
COLUNA = "Despesas Empenhadas"
ESPERADAS = ["Instituição", "Cod.IBGE", "UF", "População",
             "Coluna", "Conta", "Identificador da Conta", "Valor"]

OK, ATN, ERR = [], [], []


def le(caminho):
    """FINBRA: latin-1, separador ';', decimal ',', 3 linhas de cabeçalho."""
    for pular in (3, 0, 1, 2, 4):
        try:
            df = pd.read_csv(caminho, sep=";", encoding="latin1",
                             skiprows=pular, decimal=",")
            if "Cod.IBGE" in df.columns:
                return df, pular
        except Exception:
            continue
    raise ValueError(f"não consegui ler {caminho}")


arquivos = [Path(a) for a in sys.argv[1:]]
if not arquivos:
    print(__doc__)
    sys.exit(1)

perfis, todos_codigos = {}, {}

for arq in sorted(arquivos):
    print(f"\n{'='*62}\n{arq.name}")
    try:
        df, pular = le(arq)
    except Exception as e:
        print(f"  FALHOU: {e}")
        ERR.append(f"{arq.name}: ilegível")
        continue

    print(f"  linhas: {len(df):,}".replace(",", ".") +
          f"   colunas: {len(df.columns)}   (skiprows={pular})")

    faltando = [c for c in ESPERADAS if c not in df.columns]
    extras = [c for c in df.columns if c not in ESPERADAS]
    if faltando:
        print(f"  COLUNAS FALTANDO: {faltando}")
        ERR.append(f"{arq.name}: faltam colunas {faltando}")
    if extras:
        print(f"  colunas extras: {extras}")
        ATN.append(f"{arq.name}: colunas extras {extras}")
    perfis[arq.name] = tuple(df.columns)

    emp = df[df["Coluna"] == COLUNA]
    if emp.empty:
        print(f"  '{COLUNA}' ausente — valores presentes: "
              f"{sorted(df['Coluna'].dropna().unique())[:5]}")
        ERR.append(f"{arq.name}: sem '{COLUNA}'")
        continue

    ab = emp[emp["Conta"] == CONTA_AB]
    n_mun = emp["Cod.IBGE"].nunique()
    n_ab = ab["Cod.IBGE"].nunique()
    print(f"  municípios no arquivo: {n_mun}")
    print(f"  municípios com 10.301: {n_ab}  ({100*n_ab/max(n_mun,1):.1f}%)")
    if n_ab < n_mun * 0.9:
        ATN.append(f"{arq.name}: só {n_ab}/{n_mun} municípios têm 10.301")
    else:
        OK.append(f"{arq.name}: 10.301 presente em {n_ab} municípios")

    subs = sorted(emp.loc[emp["Conta"].str.startswith("10", na=False),
                          "Conta"].unique())
    print(f"  subfunções de saúde: {len(subs)}")
    for s in subs:
        print(f"     {s}")

    ab = ab.copy()
    ab["pc"] = ab["Valor"] / ab["População"]
    zero = int((ab["pc"].fillna(0) <= 0).sum())
    print(f"  gasto per capita — mín R$ {ab['pc'].min():,.2f} | "
          f"mediana R$ {ab['pc'].median():,.2f} | "
          f"máx R$ {ab['pc'].max():,.2f}".replace(",", "."))
    if zero:
        print(f"  {zero} municípios com gasto zero/nulo -> limpeza")
        ATN.append(f"{arq.name}: {zero} municípios com 10.301 zerado")

    cods = set(emp["Cod.IBGE"].dropna().astype(int))
    todos_codigos[arq.name] = cods
    tam = {len(str(c)) for c in cods}
    if tam != {7}:
        ATN.append(f"{arq.name}: códigos IBGE com tamanhos {tam}")
    if len({c // 10 for c in cods}) != len(cods):
        ERR.append(f"{arq.name}: COLISÃO ao truncar código para 6 dígitos")
    else:
        OK.append(f"{arq.name}: truncamento p/ 6 dígitos sem colisão")


# ----------------------------------------------------- consistência entre anos
print(f"\n{'='*62}\nCONSISTÊNCIA ENTRE OS ANOS")
if len(set(perfis.values())) == 1:
    print("  esquema idêntico em todos os arquivos")
    OK.append("esquema estável entre exercícios")
elif perfis:
    print("  ESQUEMA MUDA ENTRE ANOS:")
    for nome, cols in perfis.items():
        print(f"    {nome}: {len(cols)} colunas")
    ATN.append("esquema difere entre exercícios — tratar na carga")

if len(todos_codigos) > 1:
    comum = set.intersection(*todos_codigos.values())
    uniao = set.union(*todos_codigos.values())
    print(f"  municípios em todos os anos: {len(comum)} de {len(uniao)}")
    if len(comum) < len(uniao) * 0.95:
        ATN.append("conjunto de municípios varia entre anos")

print("\n" + "=" * 62)
for t, itens in (("OK      ", OK), ("ATENÇÃO ", ATN), ("FALHA   ", ERR)):
    for i in itens:
        print(f"{t} {i}")
print("=" * 62)
print("VEREDITO: bloqueado." if ERR else "VEREDITO: FINBRA utilizável.")
sys.exit(1 if ERR else 0)
