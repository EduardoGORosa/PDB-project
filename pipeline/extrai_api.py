"""Extração dos indicadores do Previne Brasil na API DEMAS / Ministério da Saúde.

Substitui `extrai_previne.py` e `api.py`, que estavam ambos incorretos.

Três correções sobre o que estava escrito:

1. O prefixo `/v1` da URL devolve 404. A base é a raiz do host.

2. A paginação por `offset` é INUTILIZÁVEL, e não apenas mal documentada.
   O CONTEXTO.md registra que a ordem dos resultados seria determinística.
   Não é: seis chamadas idênticas a `offset=0&limit=5` devolveram duas
   janelas diferentes, deslocadas em um registro. Paginar por offset
   duplica e perde linhas silenciosamente.

   A saída é paginar por `codigo_municipio`, que a API aceita como filtro.
   Uma chamada por município devolve o conjunto completo daquele município
   (18 registros = 6 indicadores x 3 visões) e é estável: seis chamadas
   idênticas devolveram exatamente o mesmo conjunto.

3. O envelope da resposta é `sisab_indicador_desempenho`.

Só existem 2024Q1, 2024Q2 e 2024Q3. Anos anteriores respondem 200 com lista
vazia — o dado não está lá.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.comum import API_BASE, API_ENVELOPE, DADOS_API  # noqa: E402
from pipeline.leitura_sisab import codigos_ibge6_do_sisab  # noqa: E402

UF = "RS"
PAUSA = 0.15  # segundos entre requisições
LIMITE = 1000  # teto da API; um município cabe folgadamente
QUADRIMESTRES = ["2024Q1", "2024Q2", "2024Q3"]


def busca_municipio(
    sessao: requests.Session, quadrimestre: str, cod_ibge6: int
) -> list[dict]:
    """Todos os registros de um município num quadrimestre.

    Se a resposta encostar no limite, o conjunto pode ter sido truncado por
    uma fronteira de janela — que é justamente onde a API é instável. Nesse
    caso falhamos alto em vez de gravar dado incompleto.
    """
    resposta = sessao.get(
        API_BASE,
        params={
            "uf": UF,
            "quadrimestre": quadrimestre,
            "codigo_municipio": cod_ibge6,
            "limit": LIMITE,
            "offset": 0,
        },
        timeout=60,
    )
    resposta.raise_for_status()
    registros = resposta.json()[API_ENVELOPE]
    if len(registros) >= LIMITE:
        raise RuntimeError(
            f"{quadrimestre}/{cod_ibge6}: {len(registros)} registros encostaram "
            f"no limite {LIMITE}; a resposta pode estar truncada."
        )
    return registros


def baixa_quadrimestre(
    sessao: requests.Session, quadrimestre: str, municipios: list[int]
) -> list[dict]:
    registros: list[dict] = []
    for i, cod in enumerate(municipios, 1):
        registros.extend(busca_municipio(sessao, quadrimestre, cod))
        if i % 50 == 0 or i == len(municipios):
            print(
                f"  {quadrimestre}: {i:>3}/{len(municipios)} municípios, "
                f"{len(registros):>5} registros",
                flush=True,
            )
        time.sleep(PAUSA)
    return registros


def main() -> None:
    DADOS_API.mkdir(parents=True, exist_ok=True)
    municipios = sorted(codigos_ibge6_do_sisab())
    print(f"{len(municipios)} municípios do RS (lista vinda dos arquivos SISAB)\n")

    sessao = requests.Session()
    for quadrimestre in QUADRIMESTRES:
        destino = DADOS_API / f"previne_{UF}_{quadrimestre}.json"
        if destino.exists():
            print(f"{quadrimestre}: já baixado, pulando.")
            continue

        print(f"{quadrimestre}:")
        registros = baixa_quadrimestre(sessao, quadrimestre, municipios)
        if not registros:
            print("  vazio — quadrimestre não publicado nesta API.\n")
            continue

        destino.write_text(
            json.dumps(registros, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  salvo: {len(registros)} registros em {destino.name}\n")


if __name__ == "__main__":
    main()
