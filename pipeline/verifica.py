"""Relatório de verificação da carga: contagens, cobertura e taxa de nulos.

Roda depois de cada carga. Distingue o que é ESPERADO (a API não publica o
indicador de hipertensão; o SISAB não publica denominadores) do que é
DIVERGÊNCIA a investigar.
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
            SELECT 'dim_municipio' AS tabela, count(*) AS linhas FROM dim_municipio
            UNION ALL SELECT 'dim_periodo',   count(*) FROM dim_periodo
            UNION ALL SELECT 'dim_indicador', count(*) FROM dim_indicador
            UNION ALL SELECT 'dim_conta',     count(*) FROM dim_conta
            UNION ALL SELECT 'dim_estagio_despesa', count(*) FROM dim_estagio_despesa
            UNION ALL SELECT 'populacao_municipio', count(*) FROM populacao_municipio
            UNION ALL SELECT 'fato_despesa',   count(*) FROM fato_despesa
            UNION ALL SELECT 'fato_indicador', count(*) FROM fato_indicador
            ORDER BY 1""")

        _tabela(con, "2. FINBRA — linhas e cobertura por exercício", """
            SELECT exercicio,
                   count(*) AS linhas,
                   count(DISTINCT cod_ibge6) AS municipios,
                   %s - count(DISTINCT cod_ibge6) AS faltando
              FROM fato_despesa GROUP BY 1 ORDER BY 1""", (MUNICIPIOS_RS,))

        _tabela(con, "3. FINBRA — cobertura da subfunção 10.301 (Despesas Empenhadas)", """
            SELECT d.exercicio,
                   count(*) AS municipios,
                   %s - count(*) AS faltando,
                   ROUND(100.0 * count(*) / %s, 2) AS pct
              FROM fato_despesa d JOIN dim_conta c ON c.conta = d.conta
             WHERE c.codigo = '10.301' AND d.estagio = 'Despesas Empenhadas'
             GROUP BY 1 ORDER BY 1""", (MUNICIPIOS_RS, MUNICIPIOS_RS))

        _tabela(con, "4. FINBRA — municípios sem 10.301 (declaração truncada no SICONFI)", """
            SELECT m.cod_ibge7, m.nome, a.exercicio,
                   (SELECT count(*) FROM fato_despesa f
                     WHERE f.cod_ibge6 = m.cod_ibge6 AND f.exercicio = a.exercicio)
                       AS linhas_declaradas
              FROM dim_municipio m
             CROSS JOIN (SELECT DISTINCT exercicio FROM fato_despesa) a
             WHERE NOT EXISTS (
                   SELECT 1 FROM fato_despesa d JOIN dim_conta c ON c.conta = d.conta
                    WHERE d.cod_ibge6 = m.cod_ibge6 AND d.exercicio = a.exercicio
                      AND c.codigo = '10.301' AND d.estagio = 'Despesas Empenhadas')
             ORDER BY a.exercicio""")

        _tabela(con, "5. SISAB — linhas, cobertura e nulos por quadrimestre", """
            SELECT f.quadrimestre, f.regime,
                   count(*) AS linhas,
                   count(DISTINCT f.cod_ibge6) AS municipios,
                   count(DISTINCT f.id_indicador) AS indicadores,
                   count(*) FILTER (WHERE f.percentual IS NULL) AS nulos
              FROM fato_indicador f WHERE f.fonte = 'sisab'
             GROUP BY 1, 2 ORDER BY 1""")

        _tabela(con, "6. API — linhas, cobertura e nulos por quadrimestre e visão", """
            SELECT quadrimestre, visao_equipe,
                   count(*) AS linhas,
                   count(DISTINCT cod_ibge6) AS municipios,
                   count(DISTINCT id_indicador) AS indicadores,
                   count(*) FILTER (WHERE numerador IS NULL) AS nulos_numerador,
                   count(*) FILTER (WHERE den_utilizado IS NULL) AS nulos_den
              FROM fato_indicador WHERE fonte = 'api'
             GROUP BY 1, 2 ORDER BY 1, 2""")

        _tabela(con, "7. Taxa de nulos em fato_indicador (nulos ESPERADOS entre parênteses)", """
            SELECT fonte,
                   count(*) AS linhas,
                   ROUND(100.0*count(*) FILTER (WHERE percentual IS NULL)/count(*), 2)
                       AS pct_nulo_percentual,
                   ROUND(100.0*count(*) FILTER (WHERE numerador IS NULL)/count(*), 2)
                       AS "pct_nulo_numerador (100 no sisab)",
                   ROUND(100.0*count(*) FILTER (WHERE den_utilizado IS NULL)/count(*), 2)
                       AS "pct_nulo_den_util (100 no sisab)"
              FROM fato_indicador GROUP BY 1 ORDER BY 1""")

        _tabela(con, "8. Indicadores: as duas versões e a contraparte na API", """
            SELECT codigo_indicador, regime,
                   vigencia_inicio || '..' || vigencia_fim AS cobertura,
                   COALESCE(codigo_api::text, '— ausente na API') AS codigo_api,
                   left(nome, 58) AS nome
              FROM dim_indicador ORDER BY codigo_indicador, regime""")

        _tabela(con, "9. Junção FINBRA x SISAB — municípios que casam", """
            SELECT count(*) FILTER (WHERE tem_despesa AND tem_indicador) AS ambos,
                   count(*) FILTER (WHERE tem_despesa AND NOT tem_indicador) AS so_finbra,
                   count(*) FILTER (WHERE NOT tem_despesa AND tem_indicador) AS so_sisab
              FROM (SELECT m.cod_ibge6,
                           EXISTS (SELECT 1 FROM fato_despesa d WHERE d.cod_ibge6 = m.cod_ibge6)
                               AS tem_despesa,
                           EXISTS (SELECT 1 FROM fato_indicador f WHERE f.cod_ibge6 = m.cod_ibge6)
                               AS tem_indicador
                      FROM dim_municipio m) s""")

        _tabela(con, "10. Anos com indicador mas SEM gasto correspondente", """
            SELECT p.ano,
                   count(DISTINCT f.cod_ibge6) AS municipios_com_indicador,
                   COALESCE((SELECT count(DISTINCT d.cod_ibge6) FROM fato_despesa d
                              WHERE d.exercicio = p.ano), 0) AS municipios_com_despesa
              FROM fato_indicador f JOIN dim_periodo p USING (quadrimestre)
             GROUP BY p.ano ORDER BY p.ano""")

        print()


if __name__ == "__main__":
    main()
