#!/usr/bin/env python
"""Reconstrói o banco do zero: esquema, FINBRA, SISAB e API.

    python carrega.py            # recria tudo
    python carrega.py --verifica # só roda o relatório de verificação

A conexão vem de DATABASE_URL (padrão: postgresql://pbd:pbd@127.0.0.1:5433/pbd).
Os JSON da API precisam existir em data/api/; para baixá-los:

    python -m pipeline.extrai_api
"""

from __future__ import annotations

import sys
import time

from pipeline import carrega_api, carrega_finbra, carrega_sisab, verifica
from pipeline.bd import conecta
from pipeline.comum import SQL


def aplica_esquema(con) -> None:
    con.execute(open(SQL / "01_schema.sql", encoding="utf-8").read())


def main() -> None:
    if "--verifica" in sys.argv:
        verifica.main()
        return

    inicio = time.time()
    with conecta() as con:
        print("== esquema ==")
        aplica_esquema(con)
        con.commit()

        print("\n== FINBRA ==")
        r = carrega_finbra.carrega(con)
        con.commit()
        print(f"   {r['linhas_despesa']} linhas, exercícios {r['anos']}")

        print("\n== SISAB ==")
        r = carrega_sisab.carrega(con)
        con.commit()
        print(f"   {r['linhas']} linhas, {r['periodo'][0]}..{r['periodo'][1]}")

        print("\n== API DEMAS ==")
        r = carrega_api.carrega(con)
        con.commit()
        print(f"   {r['linhas']} linhas, 2024Q1..2024Q3")

    print(f"\nconcluído em {time.time() - inicio:.1f}s\n")
    verifica.main()


if __name__ == "__main__":
    main()
