"""Constantes, caminhos e utilidades compartilhadas pelo pipeline.

Tudo que é específico do formato das fontes mora aqui, para que os loaders
falem apenas de dados.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "data"
DADOS_API = RAIZ / "data" / "api"
SQL = RAIZ / "sql"

# --------------------------------------------------------------------------
# Conexão
# --------------------------------------------------------------------------
# Repontável por variável de ambiente; o padrão é o cluster local do projeto.
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://pbd:pbd@127.0.0.1:5433/pbd"
)

# --------------------------------------------------------------------------
# FINBRA
# --------------------------------------------------------------------------
FINBRA_ENCODING = "latin-1"
FINBRA_SEP = ";"
FINBRA_DECIMAL = ","
FINBRA_LINHAS_PREAMBULO = 3  # "Exercício:", "Escopo:", "Tabela:" antes do header
FINBRA_GLOB = "finbra_MUNEST_DespesasporFuncao(AnexoI-E)_*/finbra.csv"

# --------------------------------------------------------------------------
# SISAB
# --------------------------------------------------------------------------
SISAB_ENCODING = "latin-1"
SISAB_SEP = ";"
# O header NÃO está numa linha fixa: 12 nos painéis 2022+, 13 nos históricos
# (que trazem uma linha "Departamento de Saúde da família DESF" a mais).
# Detectamos pela própria linha.
SISAB_HEADER_RE = re.compile(r"^\"?uf\s*;\s*ibge\s*;", re.IGNORECASE)
SISAB_QUADRIMESTRE_RE = re.compile(r"^(\d{4})\s*Q([1-3])\s*\(%\)$")

# --------------------------------------------------------------------------
# Regimes metodológicos (CONTEXTO.md §4)
# --------------------------------------------------------------------------
# Nota Técnica nº 05/2020 (DESF/SAPS/MS) — vigente até 2021Q3
# Nota Técnica nº 11/2022, de 15/02/2022 — vigente a partir de 2022Q1
REGIME_NT05 = "NT 05/2020"
REGIME_NT11 = "NT 11/2022"
CORTE_REGIME = "2022Q1"  # primeiro quadrimestre sob a NT 11/2022


def regime_do_quadrimestre(quadrimestre: str) -> str:
    """'2018Q1' -> 'NT 05/2020';  '2022Q1' -> 'NT 11/2022'."""
    return REGIME_NT05 if quadrimestre < CORTE_REGIME else REGIME_NT11


# --------------------------------------------------------------------------
# API DEMAS
# --------------------------------------------------------------------------
# O prefixo /v1 documentado no CONTEXTO.md devolve 404 desde a verificação de
# 2026-08-31; a base correta é a raiz do host. O Swagger vive em
# https://apidadosabertos.saude.gov.br/static/swagger.json e não declara basePath.
API_BASE = (
    "https://apidadosabertos.saude.gov.br"
    "/atencao-primaria/indicador-desempenho-programa-previne-brasil"
)
API_ENVELOPE = "sisab_indicador_desempenho"
API_VISAO_FINANCIAMENTO = "homologadas"


# --------------------------------------------------------------------------
# Códigos IBGE
# --------------------------------------------------------------------------
def ibge7_para_ibge6(cod7: int | str) -> int:
    """FINBRA usa 7 dígitos (o último é verificador); SISAB e API usam 6."""
    return int(cod7) // 10


def normaliza_nome(nome: str) -> str:
    """Maiúsculas sem acento, para comparar nomes entre fontes."""
    sem_acento = "".join(
        c
        for c in unicodedata.normalize("NFKD", nome)
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def anos_finbra() -> list[int]:
    """Anos com arquivo FINBRA presente em data/, em ordem."""
    anos = []
    for caminho in DADOS.glob(FINBRA_GLOB):
        m = re.search(r"_(\d{4})/finbra\.csv$", str(caminho))
        if m:
            anos.append(int(m.group(1)))
    return sorted(anos)


def caminho_finbra(ano: int) -> Path:
    return DADOS / f"finbra_MUNEST_DespesasporFuncao(AnexoI-E)_{ano}" / "finbra.csv"
