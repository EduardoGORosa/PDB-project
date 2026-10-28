"""Capturas de tela das quatro visões da aplicação, para os relatórios.

    streamlit run app/app.py --server.headless true --server.port 8599 &
    uv run --with playwright python docs/capturas.py

Usa o Chromium do sistema (/usr/bin/chromium); grava docs/img/app_*.png e
falha se alguma página exibir exceção.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

SAIDA = Path(__file__).parent / "img"
URL = "http://localhost:8599"
PAGINAS = {"panorama": "", "municipio": "municipio", "indicadores": "indicadores",
           "qualidade": "qualidade"}


def main() -> None:
    SAIDA.mkdir(exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/usr/bin/chromium")
        pagina = navegador.new_page(viewport={"width": 1500, "height": 1100})
        for nome, caminho in PAGINAS.items():
            pagina.goto(f"{URL}/{caminho}")
            pagina.wait_for_selector('[data-testid="stMain"]', timeout=60000)
            pagina.wait_for_timeout(9000)  # gráficos do plotly renderizam depois
            erros = pagina.locator('[data-testid="stException"]').all_inner_texts()
            if erros:
                raise RuntimeError(f"{nome}: {erros[0][:300]}")
            pagina.screenshot(path=SAIDA / f"app_{nome}.png", full_page=True)
            print(f"app_{nome}.png")
        navegador.close()


if __name__ == "__main__":
    main()
