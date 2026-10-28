"""
Extração dos indicadores de desempenho do Programa Previne Brasil
Fonte: API DEMAS / Ministério da Saúde
  https://apidadosabertos.saude.gov.br/v1/atencao-primaria/indicador-desempenho-programa-previne-brasil

ATENÇÃO: o parâmetro `offset` é o NÚMERO DA PÁGINA (começa em 0),
não o índice do registro. Com limit=1000, offset=1 retorna os
registros 1000-1999.
"""

import json
import time
from pathlib import Path

import requests

BASE = (
    "https://apidadosabertos.saude.gov.br/v1"
    "/atencao-primaria/indicador-desempenho-programa-previne-brasil"
)

UF = "RS"
LIMIT = 1000
PAUSA = 0.5  # segundos entre requisições — seja educado com a API
SAIDA = Path("dados_brutos")

# Previne Brasil: 3 quadrimestres por ano, 2020 a 2024
QUADRIMESTRES = [f"{ano}Q{q}" for ano in range(2020, 2025) for q in (1, 2, 3)]


def busca_pagina(quadrimestre: str, pagina: int) -> list:
    """Retorna a lista de registros de uma página, ou [] se acabou."""
    resposta = requests.get(
        BASE,
        params={
            "uf": UF,
            "quadrimestre": quadrimestre,
            "limit": LIMIT,
            "offset": pagina,  # PÁGINA, não deslocamento de registros
        },
        timeout=60,
    )
    resposta.raise_for_status()
    corpo = resposta.json()

    # A API pode devolver uma lista pura ou um envelope com os dados
    # dentro de alguma chave. Trata os dois casos.
    if isinstance(corpo, list):
        return corpo
    for chave in (
        "indicador_desempenho_programa_previne_brasil",
        "dados",
        "data",
        "results",
        "items",
    ):
        if isinstance(corpo.get(chave), list):
            return corpo[chave]
    raise ValueError(f"Formato inesperado. Chaves: {list(corpo.keys())}")


def baixa_quadrimestre(quadrimestre: str) -> list:
    registros, pagina = [], 0
    while True:
        lote = busca_pagina(quadrimestre, pagina)
        if not lote:
            break
        registros.extend(lote)
        print(
            f"  {quadrimestre} pág.{pagina:>3} -> "
            f"{len(lote):>5} reg. (acum. {len(registros)})"
        )
        if len(lote) < LIMIT:  # última página
            break
        pagina += 1
        time.sleep(PAUSA)
    return registros


def main() -> None:
    SAIDA.mkdir(exist_ok=True)
    total = 0

    for quadrimestre in QUADRIMESTRES:
        destino = SAIDA / f"previne_{UF}_{quadrimestre}.json"
        if destino.exists():
            print(f"{quadrimestre}: já baixado, pulando.")
            continue

        print(f"{quadrimestre}:")
        try:
            registros = baixa_quadrimestre(quadrimestre)
        except Exception as erro:
            print(f"  FALHOU: {erro}")
            continue

        if not registros:
            print("  vazio — quadrimestre provavelmente não publicado.")
            continue

        destino.write_text(json.dumps(registros, ensure_ascii=False), encoding="utf-8")
        total += len(registros)
        print(f"  salvo: {len(registros)} registros\n")

    print(f"\nTotal geral: {total} registros em {SAIDA}/")


if __name__ == "__main__":
    main()
