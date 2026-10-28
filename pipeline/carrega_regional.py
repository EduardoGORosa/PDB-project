"""Carga da divisão regional da saúde: dim_coordenadoria, dim_regiao_saude e
a região de cada município.

Fonte: data_ref/crs_municipios.csv, montado a partir de
  * DATASUS, base territorial jun/2026 (município -> região de saúde), e
  * Portaria SES-RS nº 320/2025, Anexo I (região -> coordenadoria, 18 CRS).
"""

from __future__ import annotations

import csv

from pipeline.bd import copia
from pipeline.comum import RAIZ

ARQUIVO = RAIZ / "data_ref" / "crs_municipios.csv"

# O DATASUS ainda traz um nome provisório para a R28; o nome oficial é o da
# Portaria SES-RS nº 320/2025.
NOMES_OFICIAIS = {28: "Vale do Rio Pardo"}

# Casos em que a fonte antiga do DATASUS (rl_municip_divadm, numeração de 19
# CRS) diverge da divisão adotada. Registrados, não corrigidos.
DIVERGENCIAS = {
    430605: "Cristal: DATASUS (tabela antiga de CRS) aponta a CRS de Pelotas; "
             "a Portaria SES-RS 320/2025 lista o município na R9, 1ª CRS. Adotada a Portaria.",
    432220: "Tupanciretã: DATASUS (tabela antiga de CRS) aponta a CRS de Cruz Alta; "
             "a região R1 pertence à 4ª CRS (Santa Maria). Adotada a região.",
}


def carrega(con) -> dict:
    with ARQUIVO.open(encoding="utf-8") as fh:
        linhas = list(csv.DictReader(fh))

    crs, regioes, municipio_regiao = {}, {}, {}
    for l in linhas:
        reg = int(l["regiao_saude_codigo"].lstrip("R"))
        crs[int(l["crs_numero"])] = l["crs_sede"]
        regioes[reg] = (NOMES_OFICIAIS.get(reg, l["regiao_saude_nome"]),
                        int(l["crs_numero"]))
        municipio_regiao[int(l["cod_ibge6"])] = reg

    copia(con, "dim_coordenadoria", ["crs_numero", "sede"], sorted(crs.items()))
    copia(con, "dim_regiao_saude", ["regiao_codigo", "nome", "crs_numero"],
          [(r, n, c) for r, (n, c) in sorted(regioes.items())])

    with con.cursor() as cur:
        cur.executemany(
            "UPDATE dim_municipio SET regiao_codigo = %s WHERE cod_ibge6 = %s",
            [(r, c6) for c6, r in municipio_regiao.items()])
        sem = cur.execute(
            "SELECT count(*) FROM dim_municipio WHERE regiao_codigo IS NULL").fetchone()[0]
    if sem:
        raise RuntimeError(f"{sem} municípios sem região de saúde")

    with con.cursor() as cur:
        cur.executemany(
            """INSERT INTO log_qualidade (fonte, tipo, cod_ibge7, descricao)
               SELECT 'regional', 'divergencia_entre_fontes', cod_ibge7, %s
                 FROM dim_municipio WHERE cod_ibge6 = %s""",
            [(d, c6) for c6, d in DIVERGENCIAS.items()])
    return dict(coordenadorias=len(crs), regioes=len(regioes),
                municipios=len(municipio_regiao))
