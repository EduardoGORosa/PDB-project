"""Leitura dos CSVs anuais do FINBRA / Tesouro Nacional.

Formato, confirmado nos seis arquivos presentes: latin-1, separador ';',
decimal ',' e TRÊS linhas de preâmbulo ("Exercício:", "Escopo:", "Tabela:")
antes do header real. Ler com os defaults do CSV devolve lixo, não erro.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from decimal import Decimal

from pipeline.comum import (
    FINBRA_ENCODING,
    FINBRA_LINHAS_PREAMBULO,
    FINBRA_SEP,
    caminho_finbra,
    ibge7_para_ibge6,
)

HEADER_ESPERADO = [
    "Instituição", "Cod.IBGE", "UF", "População",
    "Coluna", "Conta", "Identificador da Conta", "Valor",
]

# 'Prefeitura Municipal de Cotiporã - RS' -> 'Cotiporã'
RE_INSTITUICAO = re.compile(r"^Prefeitura Municipal de\s+(.*?)\s*-\s*[A-Z]{2}$")
RE_SUBFUNCAO = re.compile(r"^(\d{2})\.(\d{3})\s+-\s+(.*)$")
RE_FUNCAO = re.compile(r"^(\d{2})\s+-\s+(.*)$")
RE_RESIDUAL = re.compile(r"^FU(\d{2})\s+-\s+(.*)$")


@dataclass(frozen=True)
class LinhaFinbra:
    cod_ibge7: int
    cod_ibge6: int
    municipio: str
    uf: str
    populacao: int
    estagio: str
    conta: str
    valor: Decimal


def classifica_conta(conta: str) -> dict:
    """Decompõe o rótulo da conta na hierarquia funcional.

    Quatro formas ocorrem nos dados:
      'Despesas Exceto Intraorçamentárias'  -> total
      '10 - Saúde'                          -> funcao
      '10.301 - Atenção Básica'             -> subfuncao
      'FU10 - Demais Subfunções'            -> subfuncao residual
    """
    if m := RE_SUBFUNCAO.match(conta):
        funcao, sub, nome = m.groups()
        return dict(nivel="subfuncao", codigo=f"{funcao}.{sub}", funcao=funcao,
                    subfuncao=sub, nome=nome.strip(), eh_residual=False)
    if m := RE_RESIDUAL.match(conta):
        funcao, nome = m.groups()
        return dict(nivel="subfuncao", codigo=f"FU{funcao}", funcao=funcao,
                    subfuncao=None, nome=nome.strip(), eh_residual=True)
    if m := RE_FUNCAO.match(conta):
        funcao, nome = m.groups()
        return dict(nivel="funcao", codigo=funcao, funcao=funcao,
                    subfuncao=None, nome=nome.strip(), eh_residual=False)
    return dict(nivel="total", codigo=None, funcao=None, subfuncao=None,
                nome=conta.strip(), eh_residual=False)


def _decimal_br(bruto: str) -> Decimal:
    """'25805436,34' -> Decimal('25805436.34'). O separador de milhar não
    aparece no arquivo, mas é removido por segurança."""
    return Decimal(bruto.strip().replace(".", "").replace(",", "."))


def le_ano(ano: int) -> list[LinhaFinbra]:
    caminho: Path = caminho_finbra(ano)
    with caminho.open(encoding=FINBRA_ENCODING, newline="") as fh:
        linhas = fh.read().splitlines()

    preambulo, resto = linhas[:FINBRA_LINHAS_PREAMBULO], linhas[FINBRA_LINHAS_PREAMBULO:]
    if not preambulo[0].startswith("Exercício:"):
        raise ValueError(f"{caminho}: preâmbulo inesperado: {preambulo[0]!r}")
    ano_declarado = int(preambulo[0].split(":")[1])
    if ano_declarado != ano:
        raise ValueError(
            f"{caminho}: arquivo diz exercício {ano_declarado}, esperado {ano}"
        )

    leitor = csv.reader(resto, delimiter=FINBRA_SEP)
    header = [c.strip() for c in next(leitor)]
    if header != HEADER_ESPERADO:
        raise ValueError(f"{caminho}: header inesperado {header}")

    registros: list[LinhaFinbra] = []
    for r in leitor:
        if len(r) != 8 or not r[1].strip().isdigit():
            continue
        cod7 = int(r[1])
        instituicao = r[0].strip()
        m = RE_INSTITUICAO.match(instituicao)
        registros.append(
            LinhaFinbra(
                cod_ibge7=cod7,
                cod_ibge6=ibge7_para_ibge6(cod7),
                municipio=(m.group(1) if m else instituicao),
                uf=r[2].strip(),
                populacao=int(r[3]),
                estagio=r[4].strip().strip('"'),
                conta=r[5].strip().strip('"'),
                valor=_decimal_br(r[7]),
            )
        )
    return registros
