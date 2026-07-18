# CONGELADO v2.1 (Prompt 9.0.0 - Enxugamento): fora do nucleo, nao-mantido.
# Removido do caminho critico (app/pipeline/main); reversivel. Ver a lista
# do congelado em Humano_revisar.md (D-053).
"""Historico vs. Projetado em grade 2x2.

Paineis: Receita Liquida, EBITDA, Margem EBITDA e Lucro Liquido. A serie
historica vem de ``data/processed/<TICKER>_metricas.json`` (exercicios anuais
da CVM) e a projetada de ``data/processed/<TICKER>_projecao.json`` (motor).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

try:
    from src.metricas.metricas_historicas import calcular_metricas_historicas
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
    from src.visualizacao.apoio_cenarios import carregar_metricas, carregar_projecao
    from src.visualizacao.tema_institucional import (
        COR_ACENTO,
        COR_AZUL_CLARO,
        eixo_institucional,
        layout_institucional,
        salvar_grafico,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.metricas.metricas_historicas import calcular_metricas_historicas
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
    from src.visualizacao.apoio_cenarios import carregar_metricas, carregar_projecao
    from src.visualizacao.tema_institucional import (
        COR_ACENTO,
        COR_AZUL_CLARO,
        eixo_institucional,
        layout_institucional,
        salvar_grafico,
    )

PAINEIS = (
    ("receita_liquida", "Receita Liquida", False),
    ("ebitda", "EBITDA", False),
    ("margem_ebitda", "Margem EBITDA", True),
    ("lucro_liquido", "Lucro Liquido", False),
)


def _series_historicas(
    metricas: dict,
) -> dict[str, tuple[list[int], list[float]]]:
    """Extrai as series historicas anuais usadas na grade."""
    por_ano = metricas.get("metricas_por_ano", {})
    series: dict[str, tuple[list[int], list[float]]] = {}
    for campo, _, _ in PAINEIS:
        anos: list[int] = []
        valores: list[float] = []
        for ano in sorted(por_ano):
            valor = por_ano[ano].get(campo)
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                anos.append(int(ano))
                valores.append(float(valor))
        series[campo] = (anos, valores)
    return series


def _series_projetadas(
    conteudo: dict,
    ano_final_historico: int,
) -> dict[str, tuple[list[int], list[float]]]:
    """Extrai as series projetadas da DRE do motor."""
    dre = conteudo["dre"]
    series: dict[str, tuple[list[int], list[float]]] = {}
    for campo, _, _ in PAINEIS:
        anos: list[int] = []
        valores: list[float] = []
        for indice in range(1, HORIZONTE_PROJECAO + 1):
            chave = f"ano{indice}"
            valor = obter_float_obrigatorio(dre[chave], campo, chave)
            anos.append(ano_final_historico + indice)
            valores.append(valor)
        series[campo] = (anos, valores)
    return series


def gerar_historico_vs_projetado(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera a grade 2x2 historico vs projetado e salva HTML + PNG."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    conteudo = carregar_projecao(ticker_normalizado, raiz)

    metricas = carregar_metricas(ticker_normalizado, raiz)
    if not metricas.get("metricas_por_ano"):
        # Metricas ainda nao persistidas: calcula na hora a partir da CVM.
        metricas = calcular_metricas_historicas(ticker_normalizado, raiz)

    historicas = _series_historicas(metricas)
    anos_historicos = historicas.get("receita_liquida", ([], []))[0]
    if not anos_historicos:
        raise RuntimeError(f"Sem serie historica de receita para {ticker_normalizado}.")
    ano_final = anos_historicos[-1]
    projetadas = _series_projetadas(conteudo, ano_final)

    figura = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[titulo for _, titulo, _ in PAINEIS],
        vertical_spacing=0.16,
        horizontal_spacing=0.10,
    )

    posicoes = [(1, 1), (1, 2), (2, 1), (2, 2)]
    for (campo, titulo, eh_percentual), (linha, coluna) in zip(PAINEIS, posicoes):
        anos_hist, valores_hist = historicas[campo]
        anos_proj, valores_proj = projetadas[campo]

        # Conecta o ultimo historico ao primeiro projetado para leitura fluida.
        if anos_hist:
            anos_proj = [anos_hist[-1]] + anos_proj
            valores_proj = [valores_hist[-1]] + valores_proj

        figura.add_trace(
            go.Scatter(
                x=anos_hist,
                y=valores_hist,
                mode="lines+markers",
                name="Historico",
                legendgroup="hist",
                showlegend=(campo == "receita_liquida"),
                line={"color": COR_AZUL_CLARO, "width": 2},
                marker={"size": 6},
                hovertemplate="%{x}: %{y:,.1f}<extra>Historico</extra>",
            ),
            row=linha,
            col=coluna,
        )
        figura.add_trace(
            go.Scatter(
                x=anos_proj,
                y=valores_proj,
                mode="lines+markers",
                name="Projetado",
                legendgroup="proj",
                showlegend=(campo == "receita_liquida"),
                line={"color": COR_ACENTO, "width": 2, "dash": "dash"},
                marker={"size": 6, "symbol": "diamond"},
                hovertemplate="%{x}: %{y:,.1f}<extra>Projetado</extra>",
            ),
            row=linha,
            col=coluna,
        )

        formato = ",.1%" if eh_percentual else ",.0f"
        figura.update_yaxes(
            eixo_institucional(None, tickformat=formato),
            row=linha,
            col=coluna,
        )
        figura.update_xaxes(
            eixo_institucional(None, dtick=2),
            row=linha,
            col=coluna,
        )

    subtitulo = (
        f"Exercicios anuais CVM ate {ano_final} | projecao do motor "
        f"({HORIZONTE_PROJECAO} anos) em linha tracejada"
    )
    figura.update_layout(
        **layout_institucional(
            f"Historico vs. Projetado — {ticker_normalizado}",
            subtitulo,
            altura=680,
        )
    )

    caminhos = salvar_grafico(
        figura, raiz, ticker_normalizado, "historico_vs_projetado"
    )
    caminhos["figura"] = figura
    return caminhos


def main() -> None:
    """Gera a grade 2x2 para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        caminhos = gerar_historico_vs_projetado(ticker)
        print(f"{ticker}: {caminhos['html']} | png={caminhos['png']}")


if __name__ == "__main__":
    main()
