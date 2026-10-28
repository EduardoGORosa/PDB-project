"""Conexão e utilidades de carga."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Sequence

import psycopg

from pipeline.comum import DATABASE_URL


@contextmanager
def conecta(autocommit: bool = False):
    with psycopg.connect(DATABASE_URL, autocommit=autocommit) as con:
        con.execute("SET search_path TO pbd, public")
        yield con


def copia(con, tabela: str, colunas: Sequence[str], linhas: Iterable[tuple]) -> int:
    """Carrega via COPY. Devolve o número de linhas gravadas."""
    alvo = f"{tabela} ({', '.join(colunas)})"
    n = 0
    with con.cursor().copy(f"COPY {alvo} FROM STDIN") as cp:
        for linha in linhas:
            cp.write_row(linha)
            n += 1
    return n


def conta(con, tabela: str, onde: str = "") -> int:
    sql = f"SELECT count(*) FROM {tabela}" + (f" WHERE {onde}" if onde else "")
    return con.execute(sql).fetchone()[0]
