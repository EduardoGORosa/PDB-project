"""Qual "visão das equipes" gerou os arquivos do SISAB?

    python -m pipeline.confere_visao

O painel do SISAB permite escolher entre todas as equipes, só as válidas ou só
as homologadas, mas o arquivo baixado não diz qual foi usada. Os dados abertos
da API DEMAS (2024Q1–Q3) trazem as três visões; comparando o percentual do
SISAB com cada uma, a visão do arquivo fica identificada pelo próprio dado.

A API não entra no modelo (só cobre 2024); este script é a única coisa que a
usa, e só para essa verificação. Os JSON vêm de `python -m pipeline.extrai_api`.
"""

from __future__ import annotations

import collections
import json

from pipeline.comum import DADOS_API
from pipeline.leitura_sisab import le_todos

QUADRIMESTRES = ["2024Q1", "2024Q2", "2024Q3"]

# codigo_tipo_indicador -> codigo_indicador do SISAB. Derivado empiricamente,
# comparando com o SISAB (92–96% de concordância contra no máximo 20% do
# segundo colocado). O código 60 não existe na API: 'hipertensao_pa_aferida' é o
# único dos 7 indicadores do SISAB sem contraparte lá.
MAPA_API = {
    10: "prenatal_6_consultas",
    20: "gestante_sifilis_hiv",
    30: "gestante_odontologico",
    40: "citopatologico",
    50: "cobertura_vacinal",
    70: "diabetes_hemoglobina",
}

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




def main() -> None:
    sisab = {(l.cod_ibge6, l.quadrimestre, a.codigo_indicador): l.percentual
             for a in le_todos() for l in a.linhas}
    pares = collections.Counter()
    iguais = collections.Counter()
    for r in le_json():
        codigo = MAPA_API.get(r["codigo_tipo_indicador"])
        if codigo is None:
            continue
        q = r["quadrimestre"].strip()
        chave = (int(r["codigo_municipio"]), q, codigo)
        if chave not in sisab or r["percentual_quadrimestre"] is None:
            continue
        pares[r["visao_equipe"]] += 1
        if abs(float(r["percentual_quadrimestre"]) - sisab[chave]) < 1:
            iguais[r["visao_equipe"]] += 1
    for visao in sorted(pares):
        print(f"{visao:12s} {iguais[visao]:6d} / {pares[visao]:6d} "
              f"({100 * iguais[visao] / pares[visao]:5.1f}%) a menos de 1 p.p.")


if __name__ == "__main__":
    main()
