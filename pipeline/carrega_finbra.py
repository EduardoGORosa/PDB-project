"""Carga das dimensões de município/conta/estágio e do fato de despesa."""

from __future__ import annotations

from collections import defaultdict

from pipeline.bd import conecta, copia
from pipeline.comum import anos_finbra, normaliza_nome
from pipeline.leitura_finbra import classifica_conta, le_ano
from pipeline.leitura_sisab import codigos_ibge6_do_sisab

ORDEM_ESTAGIOS = [
    "Despesas Empenhadas",
    "Despesas Liquidadas",
    "Despesas Pagas",
    "Inscrição de Restos a Pagar Processados",
    "Inscrição de Restos a Pagar Não Processados",
]


def carrega(con) -> dict:
    anos = anos_finbra()
    if not anos:
        raise RuntimeError("nenhum arquivo do FINBRA encontrado em data/")

    municipios: dict[int, tuple[int, str, str]] = {}
    populacoes: dict[tuple[int, int], int] = {}
    contas: dict[str, dict] = {}
    estagios: set[str] = set()
    despesas: list[tuple] = []

    for ano in anos:
        for r in le_ano(ano):
            municipios[r.cod_ibge6] = (r.cod_ibge7, r.municipio, r.uf)
            populacoes[(r.cod_ibge6, ano)] = r.populacao
            contas.setdefault(r.conta, classifica_conta(r.conta))
            estagios.add(r.estagio)
            despesas.append((r.cod_ibge6, ano, r.estagio, r.conta, r.valor))

    # Os municípios do FINBRA têm de ser exatamente os do SISAB. Se divergirem,
    # a junção cod_ibge7/10 quebrou e nada adiante faz sentido.
    do_sisab = codigos_ibge6_do_sisab()
    if set(municipios) != do_sisab:
        so_finbra = sorted(set(municipios) - do_sisab)
        so_sisab = sorted(do_sisab - set(municipios))
        raise RuntimeError(
            f"municípios divergem: {len(so_finbra)} só no FINBRA {so_finbra[:5]}, "
            f"{len(so_sisab)} só no SISAB {so_sisab[:5]}"
        )

    faltantes = sorted(set(ORDEM_ESTAGIOS) ^ estagios)
    if faltantes:
        raise RuntimeError(f"estágios inesperados no FINBRA: {faltantes}")

    copia(con, "dim_estagio_despesa", ["estagio", "ordem"],
          [(e, i + 1) for i, e in enumerate(ORDEM_ESTAGIOS)])

    copia(con, "dim_municipio", ["cod_ibge6", "cod_ibge7", "nome", "uf"],
          [(c6, c7, nome, uf) for c6, (c7, nome, uf) in sorted(municipios.items())])

    copia(con, "populacao_municipio", ["cod_ibge6", "ano", "fonte", "populacao"],
          [(c6, ano, "finbra", pop) for (c6, ano), pop in sorted(populacoes.items())])

    copia(con, "dim_conta",
          ["conta", "nivel", "codigo", "funcao", "subfuncao", "nome", "eh_residual"],
          [(conta, d["nivel"], d["codigo"], d["funcao"], d["subfuncao"],
            d["nome"], d["eh_residual"]) for conta, d in sorted(contas.items())])

    n = copia(con, "fato_despesa",
              ["cod_ibge6", "exercicio", "estagio", "conta", "valor"], despesas)

    return dict(anos=anos, municipios=len(municipios), contas=len(contas),
                estagios=len(estagios), linhas_despesa=n)


def main() -> None:
    with conecta() as con:
        r = carrega(con)
        con.commit()
    print("FINBRA carregado:")
    print(f"  exercícios .......... {r['anos']}")
    print(f"  municípios .......... {r['municipios']}")
    print(f"  contas distintas .... {r['contas']}")
    print(f"  estágios ............ {r['estagios']}")
    print(f"  linhas em fato_despesa {r['linhas_despesa']}")


if __name__ == "__main__":
    main()
