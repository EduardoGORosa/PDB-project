"""Carga do FINBRA: dim_municipio, pop_municipio, dim_conta, dim_estagio e
fato_despesa. Registra em log_qualidade os municípios sem a subfunção 10.301.
"""

from __future__ import annotations

from pipeline.bd import conecta, copia
from pipeline.comum import anos_finbra
from pipeline.leitura_finbra import classifica_conta, le_ano
from pipeline.leitura_sisab import codigos_ibge6_do_sisab

ORDEM_ESTAGIOS = [
    "Despesas Empenhadas",
    "Despesas Liquidadas",
    "Despesas Pagas",
    "Inscrição de Restos a Pagar Processados",
    "Inscrição de Restos a Pagar Não Processados",
]
ESTAGIO_ANALISE = "Despesas Liquidadas"   # anteprojeto, seção 4


def carrega(con) -> dict:
    anos = anos_finbra()
    if not anos:
        raise RuntimeError("nenhum arquivo do FINBRA encontrado em data/")

    municipios: dict[int, str] = {}
    populacoes: dict[tuple[int, int], int] = {}
    contas: dict[str, dict] = {}
    estagios: set[str] = set()
    despesas: list[tuple] = []
    linhas_por_ano: dict[tuple[int, int], int] = {}
    tem_ab: set[tuple[int, int]] = set()

    for ano in anos:
        for r in le_ano(ano):
            # o nome do exercício mais recente prevalece
            municipios[r.cod_ibge7] = r.municipio
            populacoes[(r.cod_ibge7, ano)] = r.populacao
            contas.setdefault(r.conta, classifica_conta(r.conta))
            estagios.add(r.estagio)
            despesas.append((r.cod_ibge7, ano, r.estagio, r.conta, r.valor))
            linhas_por_ano[(r.cod_ibge7, ano)] = linhas_por_ano.get((r.cod_ibge7, ano), 0) + 1
            if r.estagio == ESTAGIO_ANALISE and r.conta.startswith("10.301"):
                tem_ab.add((r.cod_ibge7, ano))

    # Os municípios do FINBRA têm de ser exatamente os do SISAB. Se divergirem,
    # a junção cod_ibge7/10 quebrou e nada adiante faz sentido.
    do_sisab = codigos_ibge6_do_sisab()
    do_finbra = {c // 10 for c in municipios}
    if do_finbra != do_sisab:
        raise RuntimeError(
            f"municípios divergem: só FINBRA {sorted(do_finbra - do_sisab)[:5]}, "
            f"só SISAB {sorted(do_sisab - do_finbra)[:5]}")

    inesperados = sorted(set(ORDEM_ESTAGIOS) ^ estagios)
    if inesperados:
        raise RuntimeError(f"estágios inesperados no FINBRA: {inesperados}")

    copia(con, "dim_estagio", ["estagio", "ordem"],
          [(e, i + 1) for i, e in enumerate(ORDEM_ESTAGIOS)])
    copia(con, "dim_municipio", ["cod_ibge7", "cod_ibge6", "nome"],
          [(c7, c7 // 10, nome) for c7, nome in sorted(municipios.items())])
    copia(con, "pop_municipio", ["cod_ibge7", "exercicio", "populacao"],
          [(c7, ano, pop) for (c7, ano), pop in sorted(populacoes.items())])
    copia(con, "dim_conta",
          ["conta", "nivel", "codigo", "funcao", "subfuncao", "nome", "eh_residual"],
          [(conta, d["nivel"], d["codigo"], d["funcao"], d["subfuncao"],
            d["nome"], d["eh_residual"]) for conta, d in sorted(contas.items())])
    n = copia(con, "fato_despesa",
              ["cod_ibge7", "exercicio", "estagio", "conta", "valor"], despesas)

    # Lacunas: município sem declaração no ano, ou declaração sem 10.301.
    log = []
    for c7 in sorted(municipios):
        for ano in anos:
            linhas = linhas_por_ano.get((c7, ano), 0)
            if linhas == 0:
                log.append(("finbra", "sem_declaracao", c7, str(ano),
                            "Município sem nenhuma linha no FINBRA do exercício."))
            elif (c7, ano) not in tem_ab:
                log.append(("finbra", "sem_subfuncao_10301", c7, str(ano),
                            f"Declaração com {linhas} linhas e sem a subfunção 10.301 "
                            f"em '{ESTAGIO_ANALISE}' (declaração típica: ~200 linhas)."))
    copia(con, "log_qualidade",
          ["fonte", "tipo", "cod_ibge7", "periodo", "descricao"], log)

    return dict(anos=anos, municipios=len(municipios), contas=len(contas),
                linhas_despesa=n, lacunas=len(log))


def main() -> None:
    with conecta() as con:
        r = carrega(con)
        con.commit()
    print(r)


if __name__ == "__main__":
    main()
