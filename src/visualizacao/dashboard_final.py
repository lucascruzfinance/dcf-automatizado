# DESCONGELADO na Semana 10 (revisao de 20/07/2026): re-alinhado ao motor
# 9.0.x e coberto por teste. A re-integracao ao app (sub-abas de graficos) e a
# entrega do Prompt 10.0.4. Ver Humano_revisar.md (D-078, reverte D-053).
"""Dashboard executivo final: decisao em destaque + suporte agrupado.

Hierarquia institucional: a decisao (Target Price, Upside, Recomendacao) fica
na faixa superior em KPIs; o suporte (FCFF por ano, ponte EV -> Equity,
receita e margem historico vs projetado) fica agrupado abaixo. Consome apenas
resultados persistidos pelo motor — nada e recalculado aqui.
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
        COR_AZUL_ANCORA,
        COR_AZUL_CLARO,
        COR_TEXTO,
        COR_TEXTO_SECUNDARIO,
        COR_VERDE_UPSIDE,
        COR_VERMELHO_DOWNSIDE,
        FONTE_MONO,
        eixo_institucional,
        formatar_moeda_brl,
        formatar_percentual_br,
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
        COR_AZUL_ANCORA,
        COR_AZUL_CLARO,
        COR_TEXTO,
        COR_TEXTO_SECUNDARIO,
        COR_VERDE_UPSIDE,
        COR_VERMELHO_DOWNSIDE,
        FONTE_MONO,
        eixo_institucional,
        formatar_moeda_brl,
        formatar_percentual_br,
        layout_institucional,
        salvar_grafico,
    )


def _cor_semantica(upside: float) -> str:
    """Verde para upside, vermelho para downside (uso semantico estrito)."""
    return COR_VERDE_UPSIDE if upside >= 0 else COR_VERMELHO_DOWNSIDE


def _anotacao_kpi(
    figura: go.Figure,
    posicao_x: float,
    titulo: str,
    valor: str,
    cor_valor: str,
) -> None:
    """Adiciona um KPI textual na faixa de decisao (anotacoes no papel)."""
    figura.add_annotation(
        xref="paper",
        yref="paper",
        x=posicao_x,
        y=1.16,
        xanchor="center",
        yanchor="top",
        showarrow=False,
        text=(
            f"<span style='font-size:14px;color:{COR_TEXTO_SECUNDARIO}'>"
            f"{titulo}</span><br>"
            f"<span style='font-family:{FONTE_MONO};font-size:28px;"
            f"color:{cor_valor}'><b>{valor}</b></span>"
        ),
        align="center",
    )


def gerar_dashboard_final(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera o dashboard executivo e salva HTML + PNG."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    conteudo = carregar_projecao(ticker_normalizado, raiz)

    ev_equity = conteudo["ev_equity"]
    vt = conteudo["valor_terminal"]
    target = obter_float_obrigatorio(ev_equity, "target_price", "ev_equity")
    preco = obter_float_obrigatorio(ev_equity, "preco_atual", "ev_equity")
    upside = obter_float_obrigatorio(ev_equity, "upside", "ev_equity")
    recomendacao = str(ev_equity.get("recomendacao", "n/d"))
    wacc = obter_float_obrigatorio(conteudo["wacc"], "wacc", "wacc")
    g = obter_float_obrigatorio(vt, "g", "valor_terminal")
    pct_perpetuidade = float(vt.get("pct_ev_perpetuidade", 0.0))

    figura = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{}, {"type": "waterfall"}],
            [{}, {}],
        ],
        row_heights=[0.5, 0.5],
        vertical_spacing=0.16,
        horizontal_spacing=0.08,
        subplot_titles=(
            "FCFF projetado por ano",
            "Ponte EV -> Equity",
            "Receita: historico vs projetado",
            "Margem EBITDA: historico vs projetado",
        ),
    )

    # Faixa de decisao: 4 KPIs com cor semantica no upside/recomendacao.
    cor_upside = _cor_semantica(upside)
    _anotacao_kpi(figura, 0.08, "Target Price", formatar_moeda_brl(target), COR_TEXTO)
    _anotacao_kpi(
        figura,
        0.38,
        f"Upside vs {formatar_moeda_brl(preco)}",
        formatar_percentual_br(upside),
        cor_upside,
    )
    _anotacao_kpi(figura, 0.64, "Recomendacao", recomendacao, cor_upside)
    _anotacao_kpi(
        figura,
        0.90,
        "WACC | g",
        f"{formatar_percentual_br(wacc)} | {formatar_percentual_br(g)}",
        COR_TEXTO,
    )

    # FCFF por ano: negativo em vermelho (saida), positivo em azul ancora.
    anos = [f"ano{indice}" for indice in range(1, HORIZONTE_PROJECAO + 1)]
    fluxos = [
        obter_float_obrigatorio(conteudo["fcff"][chave], "fcff", chave)
        for chave in anos
    ]
    figura.add_trace(
        go.Bar(
            x=anos,
            y=fluxos,
            marker={
                "color": [
                    COR_AZUL_ANCORA if fluxo >= 0 else COR_VERMELHO_DOWNSIDE
                    for fluxo in fluxos
                ]
            },
            showlegend=False,
            hovertemplate="%{x}: %{y:,.0f}<extra>FCFF</extra>",
        ),
        row=1,
        col=1,
    )

    # Ponte EV -> Equity com os ajustes persistidos pelo motor.
    ajustes = ev_equity.get("ajustes_bridge", {})
    ev = obter_float_obrigatorio(ev_equity, "ev", "ev_equity")
    equity = obter_float_obrigatorio(ev_equity, "equity_value", "ev_equity")
    figura.add_trace(
        go.Waterfall(
            x=[
                "EV",
                "Divida Bruta",
                "Caixa",
                "Aplicacoes",
                "Minoritarios",
                "Equity",
            ],
            measure=[
                "absolute",
                "relative",
                "relative",
                "relative",
                "relative",
                "total",
            ],
            y=[
                ev,
                -float(ajustes.get("divida_bruta", 0.0)),
                float(ajustes.get("caixa_equivalentes", 0.0)),
                float(ajustes.get("aplicacoes_financeiras", 0.0)),
                -float(ajustes.get("participacoes_minoritarias", 0.0)),
                equity,
            ],
            connector={"line": {"color": COR_AZUL_CLARO, "width": 1}},
            increasing={"marker": {"color": COR_AZUL_ANCORA}},
            decreasing={"marker": {"color": COR_VERMELHO_DOWNSIDE}},
            totals={"marker": {"color": COR_ACENTO}},
            showlegend=False,
            hovertemplate="%{x}: %{y:,.0f}<extra></extra>",
        ),
        row=1,
        col=2,
    )

    # Historico vs projetado (receita e margem EBITDA).
    metricas = carregar_metricas(ticker_normalizado, raiz)
    if not metricas.get("metricas_por_ano"):
        metricas = calcular_metricas_historicas(ticker_normalizado, raiz)
    por_ano = metricas.get("metricas_por_ano", {})
    anos_hist = sorted(por_ano)
    ano_final = int(anos_hist[-1]) if anos_hist else 0

    def _serie_hist(campo: str) -> tuple[list[int], list[float]]:
        """Serie historica (anos, valores) de uma metrica anual."""
        eixo_x: list[int] = []
        valores: list[float] = []
        for ano in anos_hist:
            valor = por_ano[ano].get(campo)
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                eixo_x.append(int(ano))
                valores.append(float(valor))
        return eixo_x, valores

    def _serie_proj(campo: str) -> tuple[list[int], list[float]]:
        """Serie projetada (anos, valores) de um campo da DRE."""
        eixo_x = [ano_final + indice for indice in range(1, HORIZONTE_PROJECAO + 1)]
        valores = [
            obter_float_obrigatorio(conteudo["dre"][chave], campo, chave)
            for chave in anos
        ]
        return eixo_x, valores

    for coluna, campo, formato in (
        (1, "receita_liquida", ",.0f"),
        (2, "margem_ebitda", ",.1%"),
    ):
        x_hist, y_hist = _serie_hist(campo)
        x_proj, y_proj = _serie_proj(campo)
        if x_hist:
            x_proj = [x_hist[-1]] + x_proj
            y_proj = [y_hist[-1]] + y_proj
        figura.add_trace(
            go.Scatter(
                x=x_hist,
                y=y_hist,
                mode="lines+markers",
                line={"color": COR_AZUL_CLARO, "width": 2},
                showlegend=False,
                hovertemplate="%{x}: %{y:,.1f}<extra>Historico</extra>",
            ),
            row=2,
            col=coluna,
        )
        figura.add_trace(
            go.Scatter(
                x=x_proj,
                y=y_proj,
                mode="lines+markers",
                line={"color": COR_ACENTO, "width": 2, "dash": "dash"},
                marker={"symbol": "diamond"},
                showlegend=False,
                hovertemplate="%{x}: %{y:,.1f}<extra>Projetado</extra>",
            ),
            row=2,
            col=coluna,
        )
        figura.update_yaxes(
            eixo_institucional(None, tickformat=formato), row=2, col=coluna
        )
        figura.update_xaxes(eixo_institucional(None, dtick=2), row=2, col=coluna)

    figura.update_yaxes(eixo_institucional(None, tickformat=",.0f"), row=1, col=1)
    figura.update_xaxes(eixo_institucional(None), row=1, col=1)
    figura.update_yaxes(eixo_institucional(None, tickformat=",.0f"), row=1, col=2)
    figura.update_xaxes(eixo_institucional(None), row=1, col=2)

    subtitulo = (
        f"Perpetuidade = {formatar_percentual_br(pct_perpetuidade)} do EV | "
        "fonte unica: motor de calculo (data/processed)"
    )
    layout = layout_institucional(
        f"Dashboard Executivo — {ticker_normalizado}",
        subtitulo,
        altura=980,
    )
    # Margem superior ampliada para acomodar a faixa de KPIs da decisao.
    layout["margin"] = {"l": 70, "r": 40, "t": 230, "b": 60}
    figura.update_layout(**layout)

    caminhos = salvar_grafico(figura, raiz, ticker_normalizado, "dashboard_final")
    caminhos["figura"] = figura
    return caminhos


def main() -> None:
    """Gera o dashboard final para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        caminhos = gerar_dashboard_final(ticker)
        print(f"{ticker}: {caminhos['html']} | png={caminhos['png']}")


if __name__ == "__main__":
    main()
