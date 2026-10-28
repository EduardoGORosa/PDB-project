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
# Regimes metodológicos
# --------------------------------------------------------------------------
# Nota Técnica nº 05/2020 (DESF/SAPS/MS) — vigente até 2021Q3
# Nota Técnica nº 11/2022, de 15/02/2022 — vigente a partir de 2022Q1
REGIME_NT05 = "NT 05/2020"
REGIME_NT11 = "NT 11/2022"
CORTE_REGIME = "2022Q1"  # primeiro quadrimestre sob a NT 11/2022

REGIMES = {
    REGIME_NT05: dict(
        inicio="2018Q1", fim="2021Q3",
        descricao="Regra original dos 7 indicadores de pagamento por desempenho "
                  "(Portaria GM/MS nº 3.222/2019; Nota Técnica nº 5/2020-DESF/SAPS/MS). "
                  "O painel do SISAB apresenta 2018–2019 calculados com a mesma regra, "
                  "antes da vigência do programa."),
    REGIME_NT11: dict(
        inicio="2022Q1", fim=None,
        descricao="Regra revista a partir de 2022 (Portaria GM/MS nº 102/2022; Notas "
                  "Técnicas nº 11/2022 e nº 12/2022-SAPS/MS; fichas NT 13 a 19/2022): "
                  "contagem restrita à APS, 1ª consulta de pré-natal até a 12ª semana, "
                  "janela semestral para hipertensão e diabetes, meta de pré-natal de "
                  "60% para 45% e denominador identificado só com cobertura ≥ 85% do "
                  "estimado."),
}


def efeito_financeiro(quadrimestre: str) -> str:
    """Se o resultado do quadrimestre de dados influiu no repasse do Previne.

    Defasagem de um quadrimestre entre dado e parcela (NT 11/2022, §5.6):
      até 2019Q3      o programa não existia (valores recalculados pelo painel)
      2020Q1–2021Q2   parcelas fixadas (transição; Portarias 166 e 2.396/2021)
      2021Q3, 2022Q1  parte dos indicadores fixada (Portaria 102/2022, art. 6º-A)
      2022Q2–2023Q3   resultado real pago integralmente
      2024Q1 em diante  Portaria 3.493/2024: novo modelo a partir de maio/2024
    """
    if quadrimestre < "2020Q1":
        return "anterior ao programa"
    if quadrimestre < "2021Q3":
        return "sem efeito"
    if quadrimestre <= "2022Q1":
        return "parcial"
    if quadrimestre <= "2023Q3":
        return "pleno"
    return "posterior ao programa"


def regime_do_quadrimestre(quadrimestre: str) -> str:
    """'2018Q1' -> 'NT 05/2020';  '2022Q1' -> 'NT 11/2022'."""
    return REGIME_NT05 if quadrimestre < CORTE_REGIME else REGIME_NT11


# --------------------------------------------------------------------------
# API DEMAS
# --------------------------------------------------------------------------
# O prefixo /v1 que aparece na documentação devolve 404 desde a verificação de
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
