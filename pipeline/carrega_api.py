"""Carga da API DEMAS: fato_indicador (fonte 'api'), população e competências.

A API é a única fonte com numerador e os três denominadores — identificado,
estimado e utilizado. Só cobre 2024Q1..2024Q3, então é um estudo de caso
dentro da série histórica do SISAB, não a espinha dorsal.

Duas decisões desta carga, ambas contra o que o CONTEXTO.md previa:

* As TRÊS visões de equipe são carregadas, não só 'homologadas'.
  O CONTEXTO.md registra que `visao_equipe` replicaria cada registro três
  vezes "com números idênticos", e por isso mandava filtrar na carga. Medido
  nos 8.946 grupos (município x quadrimestre x indicador) de 2024: as três
  visões coincidem em 83,5% dos casos e DIVERGEM em 16,5% — 'geral' difere de
  'homologadas' em 13,2% e 'validas' em 5,8%, com diferença de até 79 pontos
  percentuais. Não são cópias; são três medições diferentes.
  Descartar duas delas na carga jogaria fora dado real. Como `visao_equipe`
  faz parte da chave primária de fato_indicador, nenhum total pode triplicar
  por acidente: toda agregação é obrigada a escolher uma visão. A escolha
  metodológica do projeto ('homologadas', a visão ligada ao financiamento)
  fica na visão vw_indicador_api, não na carga.

* O mapeamento entre `codigo_tipo_indicador` e os indicadores do SISAB foi
  DERIVADO DOS DADOS, comparando `percentual_quadrimestre` com o percentual
  do SISAB nos mesmos 497 municípios e 3 quadrimestres — não suposto a partir
  da ordem dos códigos. Cada código bate com um indicador em 92%-96% dos
  pares, contra 2,7%-20% do segundo colocado. É reconferido a cada carga.
"""

from __future__ import annotations

import collections
import json

from pipeline.bd import conecta, copia
from pipeline.comum import DADOS_API, REGIME_NT11, regime_do_quadrimestre

QUADRIMESTRES = ["2024Q1", "2024Q2", "2024Q3"]

# codigo_tipo_indicador -> codigo_indicador do SISAB. Derivado empiricamente;
# ver docstring. O código 60 não existe na API: 'hipertensao_pa_aferida' é o
# único dos 7 indicadores do SISAB sem contraparte lá.
MAPA_API = {
    10: "prenatal_6_consultas",
    20: "gestante_sifilis_hiv",
    30: "gestante_odontologico",
    40: "citopatologico",
    50: "cobertura_vacinal",
    70: "diabetes_hemoglobina",
}
CONCORDANCIA_MINIMA = 85.0  # % de pares idênticos exigido para aceitar o mapa


def le_json() -> list[dict]:
    registros = []
    for q in QUADRIMESTRES:
        caminho = DADOS_API / f"previne_RS_{q}.json"
        if not caminho.exists():
            raise FileNotFoundError(
                f"{caminho} — rode `python -m pipeline.extrai_api` antes."
            )
        registros += json.loads(caminho.read_text(encoding="utf-8"))
    return registros


def confere_mapeamento(con, registros: list[dict]) -> dict[int, float]:
    """Reconfere o MAPA_API contra o SISAB já carregado. Falha se não bater."""
    sisab: dict[tuple, dict[str, float]] = collections.defaultdict(dict)
    for mun, quad, slug, pct in con.execute(
        """SELECT f.cod_ibge6, f.quadrimestre, i.codigo_indicador, f.percentual
             FROM fato_indicador f JOIN dim_indicador i USING (id_indicador)
            WHERE f.fonte = 'sisab' AND f.quadrimestre = ANY(%s)""",
        (QUADRIMESTRES,),
    ):
        sisab[(mun, quad.strip())][slug] = float(pct)

    placar = {}
    for cod, slug in MAPA_API.items():
        n = ok = 0
        for r in registros:
            if r["visao_equipe"] != "homologadas" or r["codigo_tipo_indicador"] != cod:
                continue
            ref = sisab.get((r["codigo_municipio"], r["quadrimestre"]), {}).get(slug)
            if ref is None:
                continue
            n += 1
            ok += abs(r["percentual_quadrimestre"] - ref) < 0.51
        placar[cod] = 100 * ok / n if n else 0.0
        if placar[cod] < CONCORDANCIA_MINIMA:
            raise RuntimeError(
                f"codigo_tipo_indicador {cod} concorda com '{slug}' em apenas "
                f"{placar[cod]:.1f}% dos pares (mínimo {CONCORDANCIA_MINIMA}%). "
                "O mapeamento API<->SISAB precisa ser refeito."
            )
    return placar


def carrega(con) -> dict:
    registros = le_json()
    placar = confere_mapeamento(con, registros)

    ids = {
        (slug, regime): id_
        for id_, slug, regime in con.execute(
            "SELECT id_indicador, codigo_indicador, regime FROM dim_indicador"
        )
    }

    # dim_indicador.codigo_api e dim_periodo.competencia
    for cod, slug in MAPA_API.items():
        con.execute(
            "UPDATE dim_indicador SET codigo_api=%s WHERE codigo_indicador=%s",
            (cod, slug),
        )
    competencias = {(r["quadrimestre"], r["competencia"]) for r in registros}
    for quad, comp in competencias:
        con.execute(
            "UPDATE dim_periodo SET competencia=%s WHERE quadrimestre=%s",
            (comp, quad),
        )

    # população: a API informa por registro; tem de ser única por município/ano
    pop: dict[tuple[int, int], set[int]] = collections.defaultdict(set)
    for r in registros:
        pop[(r["codigo_municipio"], int(r["quadrimestre"][:4]))].add(r["populacao"])
    ambiguos = {k: v for k, v in pop.items() if len(v) != 1}
    if ambiguos:
        raise RuntimeError(f"população ambígua na API: {list(ambiguos)[:3]}")
    copia(con, "populacao_municipio", ["cod_ibge6", "ano", "fonte", "populacao"],
          [(m, a, "api", v.pop()) for (m, a), v in sorted(pop.items())])

    linhas = []
    for r in registros:
        quad = r["quadrimestre"]
        linhas.append((
            r["codigo_municipio"], quad,
            ids[(MAPA_API[r["codigo_tipo_indicador"]], regime_do_quadrimestre(quad))],
            r["visao_equipe"], "api", REGIME_NT11,
            r["percentual_quadrimestre"], r["numerador"],
            r["denominador_identificado"], r["denominador_estimado"],
            r["denominador_utilizador"], r["percentual"],
            r["cadastro"], r["base_externa"],
        ))
    n = copia(con, "fato_indicador",
              ["cod_ibge6", "quadrimestre", "id_indicador", "visao_equipe", "fonte",
               "regime", "percentual", "numerador", "den_identificado",
               "den_estimado", "den_utilizado", "percentual_api_indefinido",
               "cadastro", "base_externa"], linhas)

    return dict(registros=len(registros), linhas=n, placar=placar,
                competencias=sorted(competencias))


def main() -> None:
    with conecta() as con:
        r = carrega(con)
        con.commit()
    print("API DEMAS carregada:")
    print(f"  registros JSON ........... {r['registros']}")
    print(f"  linhas em fato_indicador . {r['linhas']}")
    print(f"  competências ............. {r['competencias']}")
    print("  concordância do mapeamento API<->SISAB (% de pares idênticos):")
    for cod, pct in sorted(r["placar"].items()):
        print(f"    codigo_tipo_indicador {cod:>2} -> {MAPA_API[cod]:24} {pct:5.1f}%")


if __name__ == "__main__":
    main()
