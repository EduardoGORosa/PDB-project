"""Reconstrói o banco do zero: esquema, FINBRA, divisão regional, SISAB e a
camada analítica.

    python -m pipeline.carrega            # recria tudo e roda a verificação
    python -m pipeline.carrega --verifica # só o relatório de verificação

A conexão vem de DATABASE_URL (padrão: postgresql://pbd:pbd@127.0.0.1:5433/pbd).
FINBRA 2018–2019 são baixados pela API do SICONFI:

    python -m pipeline.extrai_finbra 2018 2019
"""

from __future__ import annotations

import sys
import time

from pipeline import carrega_finbra, carrega_regional, carrega_sisab, verifica
from pipeline.bd import conecta
from pipeline.comum import SQL


def executa_sql(con, arquivo: str) -> None:
    con.execute((SQL / arquivo).read_text(encoding="utf-8"))


def main() -> None:
    if "--verifica" in sys.argv:
        verifica.main()
        return

    inicio = time.time()
    with conecta() as con:
        print("== esquema ==")
        executa_sql(con, "01_schema.sql")

        print("== FINBRA ==")
        r = carrega_finbra.carrega(con)
        print(f"   {r['linhas_despesa']} linhas, exercícios {r['anos']}, "
              f"{r['lacunas']} lacunas registradas")

        print("== divisão regional ==")
        r = carrega_regional.carrega(con)
        print(f"   {r['municipios']} municípios, {r['regioes']} regiões, "
              f"{r['coordenadorias']} coordenadorias")

        print("== SISAB ==")
        r = carrega_sisab.carrega(con)
        print(f"   {r['linhas']} linhas, {r['periodo'][0]}..{r['periodo'][1]}, "
              f"{r['versoes']} versões de indicador, {r['ajustes']} ajustes de portaria")

        print("== camada analítica ==")
        executa_sql(con, "02_analitico.sql")
        con.commit()

    print(f"\nconcluído em {time.time() - inicio:.1f}s\n")
    verifica.main()


if __name__ == "__main__":
    main()
