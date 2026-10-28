"""Leitura dos arquivos do SISAB: despivota o formato largo para longo.

Cada arquivo é UM indicador. As linhas são municípios e as colunas são
quadrimestres — então um arquivo é a série temporal inteira daquele indicador.

Dois detalhes do formato que não são óbvios:

* O header não está numa linha fixa. Os painéis 2022+ o trazem na linha 12;
  os históricos, na 13, porque têm uma linha "Departamento de Saúde da
  família DESF" a mais. Localizamos o header pela própria linha.

* Cada arquivo carrega o nome do indicador NAQUELE regime. O mesmo indicador
  muda de nome entre as Notas Técnicas — "Percentual de diabéticos com
  solicitação de hemoglobina glicada" (NT 05/2020) vira "Proporção de pessoas
  com diabetes, com consulta e hemoglobina glicada solicitada no semestre"
  (NT 11/2022). É a mudança de regra ficando visível no próprio dado.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from pipeline.comum import (
    DADOS,
    REGIME_NT05,
    REGIME_NT11,
    SISAB_ENCODING,
    SISAB_HEADER_RE,
    SISAB_QUADRIMESTRE_RE,
    SISAB_SEP,
    regime_do_quadrimestre,
)

# Os 7 indicadores, cada um com seus dois arquivos — um por regime.
# O pareamento é por conteúdo do indicador, não por nome de arquivo: o SISAB
# renomeou os arquivos entre os dois painéis.
INDICADORES_SISAB: dict[str, dict[str, str]] = {
    "prenatal_6_consultas": {
        REGIME_NT05: "paine-indicador_gestante_historico.csv",
        REGIME_NT11: "paine-indicador_gestante.csv",
    },
    "gestante_sifilis_hiv": {
        REGIME_NT05: "paine-indicador_gestante_sifilis_hiv_historico.csv",
        REGIME_NT11: "paine-indicador_sifilis_hiv.csv",
    },
    "gestante_odontologico": {
        REGIME_NT05: "paine-indicador_gestante_odontologico_historico.csv",
        REGIME_NT11: "paine-indicador_odontologico.csv",
    },
    "citopatologico": {
        REGIME_NT05: "paine-indicador_citopatologico_historico.csv",
        REGIME_NT11: "paine-indicador_citopatologico.csv",
    },
    "cobertura_vacinal": {
        REGIME_NT05: "paine-indicador_cobertura_vacinal_historico.csv",
        REGIME_NT11: "paine-indicador_vacinal.csv",
    },
    "hipertensao_pa_aferida": {
        REGIME_NT05: "paine-indicador_hipertensao_historico.csv",
        REGIME_NT11: "paine-indicador_hipertensao.csv",
    },
    "diabetes_hemoglobina": {
        REGIME_NT05: "paine-indicador_diabetes_historico.csv",
        REGIME_NT11: "paine-indicador_diabetes.csv",
    },
}


@dataclass(frozen=True)
class LinhaSisab:
    cod_ibge6: int
    municipio: str
    quadrimestre: str  # '2018Q1'
    percentual: float | None


@dataclass
class ArquivoSisab:
    caminho: Path
    codigo_indicador: str
    regime: str
    nome_indicador: str  # como o próprio arquivo o nomeia, naquele regime
    quadrimestres: list[str]
    linhas: list[LinhaSisab]


def _titulo_indicador(preambulo: list[str]) -> str:
    for linha in preambulo:
        m = re.match(r'^"?\s*Indicador:\s*(.*?)"?\s*$', linha)
        if m:
            return m.group(1).strip()
    raise ValueError("linha 'Indicador:' não encontrada no preâmbulo")


def _percentual(bruto: str) -> float | None:
    bruto = bruto.strip().replace(",", ".")
    if bruto in ("", "-", "--"):
        return None
    return float(bruto)


def le_arquivo(caminho: Path, codigo_indicador: str, regime: str) -> ArquivoSisab:
    texto = caminho.read_text(encoding=SISAB_ENCODING).splitlines()

    idx_header = next(
        (i for i, l in enumerate(texto) if SISAB_HEADER_RE.match(l)), None
    )
    if idx_header is None:
        raise ValueError(f"{caminho.name}: header 'UF;IBGE;...' não encontrado")

    nome = _titulo_indicador(texto[:idx_header])
    campos = next(csv.reader([texto[idx_header]], delimiter=SISAB_SEP))
    campos = [c.strip() for c in campos]

    # Colunas 0..2 são UF, IBGE, Município; da 3 em diante são quadrimestres.
    # A última é vazia (a linha termina em ';').
    quadrimestres: list[str] = []
    col_de_quadrimestre: dict[int, str] = {}
    for i, campo in enumerate(campos[3:], start=3):
        m = SISAB_QUADRIMESTRE_RE.match(campo)
        if m:
            q = f"{m.group(1)}Q{m.group(2)}"
            quadrimestres.append(q)
            col_de_quadrimestre[i] = q
        elif campo:
            raise ValueError(f"{caminho.name}: coluna inesperada {campo!r}")

    linhas: list[LinhaSisab] = []
    for registro in csv.reader(texto[idx_header + 1 :], delimiter=SISAB_SEP):
        if len(registro) < 4 or not re.fullmatch(r"\d{6}", registro[1].strip()):
            continue  # rodapé, linhas em branco
        cod6 = int(registro[1])
        municipio = registro[2].strip()
        for i, q in col_de_quadrimestre.items():
            linhas.append(
                LinhaSisab(cod6, municipio, q, _percentual(registro[i]))
            )

    # O regime declarado no arquivo tem que bater com o dos quadrimestres.
    incoerentes = {q for q in quadrimestres if regime_do_quadrimestre(q) != regime}
    if incoerentes:
        raise ValueError(
            f"{caminho.name}: quadrimestres {sorted(incoerentes)} não pertencem "
            f"ao regime {regime}"
        )

    return ArquivoSisab(
        caminho, codigo_indicador, regime, nome, quadrimestres, linhas
    )


def le_todos() -> list[ArquivoSisab]:
    arquivos = []
    for codigo, por_regime in INDICADORES_SISAB.items():
        for regime, nome_arquivo in por_regime.items():
            caminho = DADOS / nome_arquivo
            if not caminho.exists():
                raise FileNotFoundError(caminho)
            arquivos.append(le_arquivo(caminho, codigo, regime))
    return arquivos


def codigos_ibge6_do_sisab() -> set[int]:
    """Os 497 municípios do RS, tal como o SISAB os lista."""
    caminho = DADOS / INDICADORES_SISAB["diabetes_hemoglobina"][REGIME_NT11]
    arq = le_arquivo(caminho, "diabetes_hemoglobina", REGIME_NT11)
    return {l.cod_ibge6 for l in arq.linhas}
