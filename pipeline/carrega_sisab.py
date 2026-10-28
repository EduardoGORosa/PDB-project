"""Carga do SISAB: dim_periodo, dim_indicador e fato_indicador (fonte 'sisab').

O SISAB é a espinha dorsal — 7 indicadores, série 2018–2025, 497 municípios.
Cada arquivo é um indicador num regime; a carga despivota o formato largo e
marca cada linha com o regime metodológico de onde ela veio.
"""

from __future__ import annotations

from pipeline.bd import conecta, copia
from pipeline.comum import REGIME_NT05, REGIME_NT11, regime_do_quadrimestre
from pipeline.leitura_sisab import le_todos

# Nota Técnica de cada regime, conforme CONTEXTO.md §4.
NOTA_TECNICA = {
    REGIME_NT05: "Nota Técnica nº 05/2020 (DESF/SAPS/MS)",
    REGIME_NT11: "Nota Técnica nº 11/2022, de 15/02/2022 (DESF/SAPS/MS)",
}


def carrega(con) -> dict:
    arquivos = le_todos()

    # --- dim_periodo -------------------------------------------------
    quadrimestres = sorted({q for a in arquivos for q in a.quadrimestres})
    copia(con, "dim_periodo",
          ["quadrimestre", "ano", "numero_quadrimestre", "regime"],
          [(q, int(q[:4]), int(q[-1]), regime_do_quadrimestre(q))
           for q in quadrimestres])

    # --- dim_indicador -----------------------------------------------
    # vigencia_inicio/fim são a COBERTURA OBSERVADA do painel naquele regime,
    # lida dos próprios arquivos — não uma data extraída das Notas Técnicas,
    # que não estão no repositório.
    ids: dict[tuple[str, str], int] = {}
    with con.cursor() as cur:
        for a in sorted(arquivos, key=lambda x: (x.codigo_indicador, x.regime)):
            cur.execute(
                """INSERT INTO dim_indicador
                     (codigo_indicador, regime, nome, nota_tecnica,
                      vigencia_inicio, vigencia_fim)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id_indicador""",
                (a.codigo_indicador, a.regime, a.nome_indicador,
                 NOTA_TECNICA[a.regime], a.quadrimestres[0], a.quadrimestres[-1]),
            )
            ids[(a.codigo_indicador, a.regime)] = cur.fetchone()[0]

    # --- fato_indicador ----------------------------------------------
    linhas = []
    for a in arquivos:
        id_ind = ids[(a.codigo_indicador, a.regime)]
        for l in a.linhas:
            linhas.append((l.cod_ibge6, l.quadrimestre, id_ind,
                           "nao_informado", "sisab", a.regime, l.percentual))

    n = copia(con, "fato_indicador",
              ["cod_ibge6", "quadrimestre", "id_indicador", "visao_equipe",
               "fonte", "regime", "percentual"], linhas)

    return dict(arquivos=len(arquivos), indicadores=len(ids),
                quadrimestres=len(quadrimestres),
                periodo=(quadrimestres[0], quadrimestres[-1]), linhas=n)


def main() -> None:
    with conecta() as con:
        r = carrega(con)
        con.commit()
    print("SISAB carregado:")
    print(f"  arquivos lidos ........... {r['arquivos']} (7 indicadores x 2 regimes)")
    print(f"  versões em dim_indicador . {r['indicadores']}")
    print(f"  quadrimestres ............ {r['quadrimestres']} "
          f"({r['periodo'][0]} a {r['periodo'][1]})")
    print(f"  linhas em fato_indicador . {r['linhas']}")


if __name__ == "__main__":
    main()
