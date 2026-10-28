"""Carga do SISAB e da dimensão de indicadores.

    dim_regime, dim_periodo        — derivados dos próprios arquivos
    dim_indicador                  — data_ref/indicadores.csv (Notas Técnicas)
    ajuste_financiamento           — data_ref/ajustes_financiamento.csv (Portarias)
    fato_indicador                 — os 14 arquivos do SISAB, despivotados

dim_indicador não vem de nenhuma base: é construída à mão a partir das Notas
Técnicas, e o CSV em data_ref/ é a fonte versionada dessa construção. O nome
de cada versão, porém, é lido do próprio arquivo do SISAB — o loader exige que
cada arquivo tenha uma linha correspondente no dicionário.
"""

from __future__ import annotations

import csv

from pipeline.bd import copia
from pipeline.comum import RAIZ, REGIMES, efeito_financeiro, regime_do_quadrimestre
from pipeline.leitura_sisab import le_todos

INDICADORES = RAIZ / "data_ref" / "indicadores.csv"
AJUSTES = RAIZ / "data_ref" / "ajustes_financiamento.csv"


def _le_csv(caminho):
    with caminho.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _nulo(v: str):
    return v.strip() or None


def carrega(con) -> dict:
    arquivos = le_todos()

    # --- dim_regime / dim_periodo ------------------------------------
    quadrimestres = sorted({q for a in arquivos for q in a.quadrimestres})
    copia(con, "dim_regime", ["regime", "descricao", "inicio", "fim"],
          [(r, d["descricao"], d["inicio"], d["fim"]) for r, d in REGIMES.items()])
    copia(con, "dim_periodo",
          ["quadrimestre", "ano", "numero_quadrimestre", "regime_metodologico",
           "efeito_financeiro"],
          [(q, int(q[:4]), int(q[-1]), regime_do_quadrimestre(q), efeito_financeiro(q))
           for q in quadrimestres])

    # --- dim_indicador -----------------------------------------------
    dicionario = {(l["codigo"], l["regime"]): l for l in _le_csv(INDICADORES)}
    faltam = {(a.codigo_indicador, a.regime) for a in arquivos} - set(dicionario)
    if faltam:
        raise RuntimeError(f"indicadores sem entrada em {INDICADORES.name}: {sorted(faltam)}")

    ids: dict[tuple[str, str], int] = {}
    with con.cursor() as cur:
        for a in sorted(arquivos, key=lambda x: (int(dicionario[(x.codigo_indicador, x.regime)]["ordem"]), x.regime)):
            d = dicionario[(a.codigo_indicador, a.regime)]
            fim = REGIMES[a.regime]["fim"]
            cur.execute(
                """INSERT INTO dim_indicador
                     (codigo, ordem, nome, regra_numerador, regra_denominador,
                      meta, peso, nota_tecnica, regime, vigencia_inicio, vigencia_fim)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id_indicador""",
                (a.codigo_indicador, int(d["ordem"]), a.nome_indicador,
                 d["regra_numerador"], d["regra_denominador"],
                 _nulo(d["meta"]), _nulo(d["peso"]), d["nota_tecnica"], a.regime,
                 a.quadrimestres[0],
                 fim if fim and fim in quadrimestres else None))
            ids[(a.codigo_indicador, a.regime)] = cur.fetchone()[0]

    # --- ajuste_financiamento ----------------------------------------
    ajustes = []
    for l in _le_csv(AJUSTES):
        regime = regime_do_quadrimestre(l["quadrimestre"])
        ajustes.append((ids[(l["codigo"], regime)], l["quadrimestre"],
                        l["regra"], l["ato_normativo"], _nulo(l["observacao"])))
    copia(con, "ajuste_financiamento",
          ["id_indicador", "quadrimestre", "regra", "ato_normativo", "observacao"],
          ajustes)

    # --- fato_indicador ----------------------------------------------
    linhas = [(l.cod_ibge6, l.quadrimestre, ids[(a.codigo_indicador, a.regime)],
               a.regime, l.percentual)
              for a in arquivos for l in a.linhas]
    n = copia(con, "fato_indicador",
              ["cod_ibge6", "quadrimestre", "id_indicador", "regime", "percentual"], linhas)

    return dict(arquivos=len(arquivos), versoes=len(ids), ajustes=len(ajustes),
                periodo=(quadrimestres[0], quadrimestres[-1]), linhas=n)
