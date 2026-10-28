"""Relatório de verificação da carga: contagens, cobertura e taxa de nulos.

Roda depois de cada carga: volumes, cobertura de cada fonte por período,
nulos, a dimensão de indicadores e o registro de inconsistências.
"""

from __future__ import annotations

from pipeline.bd import conecta

MUNICIPIOS_RS = 497


def _tabela(con, titulo: str, sql: str, params=()) -> None:
    print(f"\n{titulo}")
    print("-" * len(titulo))
    cur = con.execute(sql, params)
    cols = [d.name for d in cur.description]
    linhas = cur.fetchall()
    larg = [
        max(len(c), *(len(str(l[i])) for l in linhas)) if linhas else len(c)
        for i, c in enumerate(cols)
    ]
    print("  " + "  ".join(c.ljust(larg[i]) for i, c in enumerate(cols)))
    for l in linhas:
        print("  " + "  ".join(str(v).ljust(larg[i]) for i, v in enumerate(l)))


def main() -> None:
    with conecta() as con:
        print("=" * 72)
        print("RELATÓRIO DE VERIFICAÇÃO DA CARGA")
        print("=" * 72)

        _tabela(con, "1. Volume por tabela", """
            SELECT relname AS tabela, n_live_tup AS linhas
              FROM pg_stat_user_tables WHERE schemaname = 'pbd' ORDER BY 1""")

        _tabela(con, "2. FINBRA — cobertura por exercício (estágio Liquidadas)", """
            SELECT exercicio,
                   count(*)                                 AS municipios,
                   count(gasto_ab)                          AS com_10301,
                   %s - count(gasto_ab)                     AS sem_10301,
                   MIN(gasto_ab_pc)                         AS pc_min,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gasto_ab_pc)::numeric(10,2)
                                                            AS pc_mediana,
                   MAX(gasto_ab_pc)                         AS pc_max
              FROM mv_gasto_anual GROUP BY 1 ORDER BY 1""", (MUNICIPIOS_RS,))

        _tabela(con, "3. SISAB — cobertura, nulos e zeros por ano", """
            SELECT p.ano, f.regime,
                   count(DISTINCT f.cod_ibge6)                     AS municipios,
                   count(*)                                        AS linhas,
                   count(*) FILTER (WHERE f.percentual IS NULL)    AS nulos,
                   ROUND(100.0 * count(*) FILTER (WHERE f.percentual = 0) / count(*), 1)
                                                                   AS pct_zeros
              FROM fato_indicador f JOIN dim_periodo p USING (quadrimestre)
             GROUP BY 1, 2 ORDER BY 1""")

        _tabela(con, "4. dim_indicador — versões e vigência", """
            SELECT ordem, codigo, regime, vigencia_inicio, vigencia_fim,
                   meta, peso, left(nota_tecnica, 40) AS nota_tecnica
              FROM dim_indicador ORDER BY ordem, regime""")

        _tabela(con, "5. Efeito financeiro de cada quadrimestre e ajustes por portaria", """
            SELECT p.quadrimestre, p.efeito_financeiro,
                   string_agg(i.ordem::text, ',' ORDER BY i.ordem) AS indicadores_fixados,
                   min(a.ato_normativo) AS ato_normativo
              FROM dim_periodo p
              LEFT JOIN ajuste_financiamento a USING (quadrimestre)
              LEFT JOIN dim_indicador i USING (id_indicador)
             GROUP BY 1, 2 ORDER BY 1""")

        _tabela(con, "6. Divisão regional", """
            SELECT c.crs_numero, c.sede,
                   count(DISTINCT r.regiao_codigo) AS regioes,
                   count(m.cod_ibge7)              AS municipios
              FROM dim_coordenadoria c
              JOIN dim_regiao_saude r USING (crs_numero)
              JOIN dim_municipio    m USING (regiao_codigo)
             GROUP BY 1, 2 ORDER BY 1""")

        _tabela(con, "7. Integração — anos com desempenho e com gasto", """
            SELECT d.ano,
                   count(DISTINCT d.cod_ibge6)                    AS com_desempenho,
                   count(DISTINCT d.cod_ibge6) FILTER (WHERE g.gasto_ab IS NOT NULL)
                                                                  AS com_gasto
              FROM mv_desempenho_anual d
              LEFT JOIN mv_gasto_anual g
                     ON g.cod_ibge6 = d.cod_ibge6 AND g.exercicio = d.ano
             GROUP BY 1 ORDER BY 1""")

        _tabela(con, "8. Registro de qualidade", """
            SELECT l.fonte, l.tipo, l.periodo, m.nome, left(l.descricao, 70) AS descricao
              FROM log_qualidade l LEFT JOIN dim_municipio m USING (cod_ibge7)
             ORDER BY l.fonte, l.periodo""")
        print()


if __name__ == "__main__":
    main()
