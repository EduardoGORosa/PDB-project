"""Download de exercícios do FINBRA pela API do SICONFI (DCA, Anexo I-E).

    python -m pipeline.extrai_finbra 2018 2019
    python -m pipeline.extrai_finbra --confere 2020   # compara API x CSV do portal

O portal do SICONFI entrega um CSV por exercício; a API entrega o mesmo
conteúdo, mas por ente. Para não ter dois parsers, este script grava o
resultado no MESMO formato do CSV do portal (latin-1, ';', decimal ',', três
linhas de preâmbulo), em data/finbra_..._<ano>/finbra.csv. O leitor
(leitura_finbra.py) não sabe de que caminho o arquivo veio.

A lista de entes é a dos 497 municípios do exercício mais recente já baixado.
"""

from __future__ import annotations

import csv
import sys
import time
from decimal import Decimal

import requests

from pipeline.comum import FINBRA_ENCODING, FINBRA_SEP, anos_finbra, caminho_finbra
from pipeline.leitura_finbra import le_ano

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca"
ANEXO = "DCA-Anexo I-E"
PAUSA = 0.4  # a API limita a taxa; abaixo disso começa a devolver 429


def baixa_ente(sessao: requests.Session, ano: int, cod7: int) -> list[dict]:
    for tentativa in range(6):
        try:
            r = sessao.get(API, params=dict(an_exercicio=ano, no_anexo=ANEXO,
                                            id_ente=cod7), timeout=60)
        except requests.RequestException:
            time.sleep(2 ** tentativa)
            continue
        if r.status_code == 200:
            corpo = r.json()
            if corpo.get("hasMore"):
                raise RuntimeError(f"{cod7}/{ano}: resposta paginada inesperada")
            return corpo["items"]
        time.sleep(2 ** tentativa)
    raise RuntimeError(f"{cod7}/{ano}: API não respondeu após 6 tentativas")


def _valor_br(v: float) -> str:
    return format(Decimal(str(v)), "f").replace(".", ",")


def extrai(ano: int) -> None:
    entes = sorted({l.cod_ibge7 for l in le_ano(max(anos_finbra()))})
    destino = caminho_finbra(ano)
    destino.parent.mkdir(parents=True, exist_ok=True)

    sessao = requests.Session()
    linhas, vazios = [], []
    for i, cod7 in enumerate(entes, 1):
        itens = baixa_ente(sessao, ano, cod7)
        if not itens:
            vazios.append(cod7)
        for it in itens:
            linhas.append([it["instituicao"], it["cod_ibge"], it["uf"],
                           it["populacao"], it["coluna"], it["conta"],
                           f"siconfi-cor_{it['cod_conta']}", _valor_br(it["valor"])])
        if i % 50 == 0:
            print(f"  {ano}: {i}/{len(entes)} entes, {len(linhas)} linhas", flush=True)
        time.sleep(PAUSA)

    with destino.open("w", encoding=FINBRA_ENCODING, newline="") as fh:
        fh.write(f"Exercício: {ano}\r\n")
        fh.write("Escopo: Municípios do Estado - RS\r\n")
        fh.write("Tabela: Despesas por Função (Anexo I-E) - via API SICONFI/DCA\r\n")
        w = csv.writer(fh, delimiter=FINBRA_SEP, lineterminator="\r\n")
        w.writerow(["Instituição", "Cod.IBGE", "UF", "População", "Coluna",
                    "Conta", "Identificador da Conta", "Valor"])
        w.writerows(linhas)
    print(f"{ano}: {len(linhas)} linhas -> {destino}")
    if vazios:
        print(f"  {len(vazios)} entes sem declaração: {vazios}")


def confere(ano: int, amostra: int = 15) -> None:
    """Compara a API com o CSV do portal num exercício que temos dos dois."""
    portal = {(l.cod_ibge7, l.estagio, l.conta): l.valor for l in le_ano(ano)}
    entes = sorted({k[0] for k in portal})[:: max(1, 497 // amostra)]
    sessao = requests.Session()
    iguais = difs = 0
    for cod7 in entes:
        api = {(it["cod_ibge"], it["coluna"], it["conta"]): Decimal(str(it["valor"]))
               for it in baixa_ente(sessao, ano, cod7)}
        do_portal = {k: v for k, v in portal.items() if k[0] == cod7}
        for k in set(api) | set(do_portal):
            if api.get(k) == do_portal.get(k):
                iguais += 1
            else:
                difs += 1
                print("  difere:", k, api.get(k), do_portal.get(k))
        time.sleep(PAUSA)
    print(f"{ano}: {len(entes)} entes, {iguais} linhas iguais, {difs} diferentes")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--confere":
        confere(int(args[1]))
    else:
        for a in args:
            extrai(int(a))
