# Scripts antigos

Mantidos só como registro da fase exploratória (agosto/2026). Não fazem parte
do pipeline e alguns não rodam mais contra o esquema atual:

- `api.py`, `extrai_previne.py` — cópias idênticas; paginam a API DEMAS por
  `offset=pagina`, o que perde e duplica registros. Substituídos por
  `pipeline/extrai_api.py`.
- `verifica_01_api.py`, `verifica_02_finbra.py`, `verifica_03_juncao.py` —
  verificações de campo das fontes, antes do pipeline existir. O que elas
  conferiam hoje é garantido pela carga (`carrega.py`) e pelo relatório de
  verificação (`pipeline/verifica.py`).
- `main.py` — esqueleto gerado pelo `uv init`.
