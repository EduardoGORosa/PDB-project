"""
DIAGNÓSTICO — por que 2020-2023 não retornou nada?

Distingue três causas que o script 01 confundia:
  (a) a API responde 200 com lista vazia  -> o dado realmente não existe
  (b) a API responde erro (4xx/5xx)       -> problema de requisição
  (c) timeout                             -> problema de rede/servidor

Também testa se a ordem dos resultados é estável entre chamadas idênticas —
se não for, a paginação por offset é insegura.

Uso: python diagnostico_api.py
"""

import json

import requests

BASE = ("https://apidadosabertos.saude.gov.br"
        "/atencao-primaria/indicador-desempenho-programa-previne-brasil")
CHAVE = "sisab_indicador_desempenho"


def bruto(**params):
    """Devolve (status, n_registros, trecho_do_corpo) sem engolir erros."""
    try:
        r = requests.get(BASE, params={"uf": "RS", **params}, timeout=90)
    except Exception as e:
        return ("TIMEOUT/REDE", None, str(e)[:140])
    try:
        corpo = r.json()
    except Exception:
        return (r.status_code, None, r.text[:140])
    if isinstance(corpo, dict) and CHAVE in corpo:
        return (r.status_code, len(corpo[CHAVE]), "")
    if isinstance(corpo, list):
        return (r.status_code, len(corpo), "")
    return (r.status_code, None, json.dumps(corpo)[:140])


print("=== A. Um ano que funciona x anos que não funcionam ===")
for qd in ["2024Q1", "2023Q3", "2023Q1", "2022Q1", "2021Q1", "2020Q1", "2019Q1"]:
    st, n, msg = bruto(quadrimestre=qd, limit=1, offset=0)
    marca = "OK " if n else ("VAZIO" if n == 0 else "ERRO ")
    print(f"  {qd}  status={str(st):<12} registros={str(n):<5} {marca} {msg}")

print("\n=== B. E se filtrar por competencia em vez de quadrimestre? ===")
# competencia é AAAAMM; 202404 apareceu junto de 2024Q1
for comp in [202404, 202308, 202304, 202204, 202104, 202004]:
    st, n, msg = bruto(competencia=comp, limit=1, offset=0)
    print(f"  competencia={comp}  status={str(st):<12} registros={str(n):<5} {msg}")

print("\n=== C. Sem nenhum filtro de período (o que vem por padrão?) ===")
st, n, msg = bruto(limit=5, offset=0)
print(f"  status={st}  registros={n}  {msg}")
try:
    r = requests.get(BASE, params={"uf": "RS", "limit": 5}, timeout=90).json()
    amostra = r[CHAVE] if isinstance(r, dict) else r
    print("  quadrimestres na amostra:",
          sorted({x.get("quadrimestre") for x in amostra}))
except Exception as e:
    print("  falhou:", e)

print("\n=== D. A ordem dos resultados é estável? ===")
def chaves(**p):
    r = requests.get(BASE, params={"uf": "RS", **p}, timeout=90).json()
    itens = r[CHAVE] if isinstance(r, dict) else r
    return [(x.get("codigo_municipio"), x.get("codigo_tipo_indicador"),
             x.get("visao_equipe")) for x in itens]

try:
    a = chaves(quadrimestre="2024Q1", limit=10, offset=0)
    b = chaves(quadrimestre="2024Q1", limit=10, offset=0)
    print(f"  duas chamadas idênticas devolvem a mesma ordem? {a == b}")
    if a != b:
        print("  -> A ORDEM NÃO É DETERMINÍSTICA.")
        print("     Paginar por offset pode pular ou repetir registros.")
        print("     Solução: baixar por município (codigo_municipio) em vez de páginas.")
    else:
        vinte = chaves(quadrimestre="2024Q1", limit=20, offset=0)
        p1 = chaves(quadrimestre="2024Q1", limit=10, offset=1)
        if p1 == vinte[10:20]:
            print("  offset = PÁGINA (offset=1 -> registros 10..19)")
        elif p1 == vinte[1:11]:
            print("  offset = REGISTRO (offset=1 -> registros 1..10)")
        else:
            print("  offset com comportamento próprio — inspecionar:")
            print("   página0:", a[:3])
            print("   página1:", p1[:3])
            print("   ref[10:]:", vinte[10:13])
except Exception as e:
    print("  falhou:", e)

print("\n=== E. Quantos registros existem em 2024Q1 no total? ===")
total, pagina = 0, 0
while pagina < 60:
    st, n, _ = bruto(quadrimestre="2024Q1", limit=1000, offset=pagina)
    if not n:
        break
    total += n
    pagina += 1
    if n < 1000:
        break
print(f"  páginas lidas: {pagina}   registros: {total:,}".replace(",", "."))
print("  (497 municípios × ~7 indicadores × 3 visões ≈ 10.000 esperados)")
