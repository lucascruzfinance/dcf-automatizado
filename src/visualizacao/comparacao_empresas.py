# DESCONGELADO na Semana 10 (revisao de 20/07/2026): re-alinhado ao motor
# 9.0.x e coberto por teste. A re-integracao ao app (sub-abas de graficos) e a
# entrega do Prompt 10.0.4. Ver Humano_revisar.md (D-078, reverte D-053).
"""Comparacao multi-empresa: Target vs Preco e upside lado a lado (Onda 4).

Consome exclusivamente os JSONs persistidos pelo motor (projecao,
comparaveis e metricas) — nada e recalculado aqui. O grafico institucional
mostra barras agrupadas de Target Price vs Preco atual por empresa, com o
upside anotado na semantica verde/vermelho do projeto.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.projecao.projetor_dre import (  # noqa: E402
    carregar_json,
    normalizar_ticker,
    resolver_raiz,
)
from src.valuation.comparaveis import carregar_comparaveis  # noqa: E402
from src.visualizacao.tema_institucional import (  # noqa: E402
    COR_AZUL_ANCORA,
    COR_AZUL_CLARO,
    COR_VERDE_UPSIDE,
    COR_VERMELHO_DOWNSIDE,
    FONTE_MONO,
    eixo_institucional,
    formatar_percentual_br,
    layout_institucional,
    salvar_grafico,
)


def montar_painel_comparacao(
    tickers: list[str],
    raiz_projeto: Path | None = None,
) -> list[dict[str, Any]]:
    """Linhas comparativas por empresa a partir dos JSONs persistidos."""
    raiz = resolver_raiz(raiz_projeto)
    linhas: list[dict[str, Any]] = []
    for ticker in tickers:
        ticker_normalizado = normalizar_ticker(ticker)
        caminho = raiz / "data" / "processed" / f"{ticker_normalizado}_projecao.json"
        if not caminho.exists():
            continue
        projecao = carregar_json(caminho)
        ev_equity = projecao.get("ev_equity", {})
        if not ev_equity:
            continue
        valor_terminal = projecao.get("valor_terminal", {})
        comparaveis = carregar_comparaveis(ticker_normalizado, raiz)
        estatisticas = comparaveis.get("estatisticas", {})
        financeira = str(projecao.get("tipo")) == "financeira"
        taxa = (
            projecao.get("ke", {}).get("ke_brl")
            if financeira
            else projecao.get("wacc", {}).get("wacc")
        )

        roic_ano1 = None
        if not financeira:
            roic_ano1 = projecao.get("fcff", {}).get("ano1", {}).get("roic")
        spread = None
        if isinstance(roic_ano1, (int, float)) and isinstance(taxa, (int, float)):
            # Spread de criacao de valor: ROIC - WACC (MOAT quantitativo).
            spread = float(roic_ano1) - float(taxa)

        linhas.append(
            {
                "ticker": ticker_normalizado,
                "tipo": projecao.get("tipo"),
                "target_price": ev_equity.get("target_price"),
                "preco_atual": ev_equity.get("preco_atual"),
                "upside": ev_equity.get("upside"),
                "recomendacao": ev_equity.get("recomendacao"),
                "taxa_desconto": taxa,
                "g": valor_terminal.get("g"),
                "roic_ano1": roic_ano1,
                "spread_roic_taxa": spread,
                "ev_ebitda_mediana_peers": (
                    estatisticas.get("ev_ebitda", {}).get("mediana")
                ),
                "p_l_mediana_peers": estatisticas.get("p_l", {}).get("mediana"),
                "p_vp_mediana_peers": estatisticas.get("p_vp", {}).get("mediana"),
            }
        )
    return linhas


def gerar_comparacao_empresas(
    tickers: list[str],
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera o grafico de barras agrupadas Target vs Preco por empresa."""
    raiz = resolver_raiz(raiz_projeto)
    linhas = montar_painel_comparacao(tickers, raiz)
    if len(linhas) < 2:
        raise RuntimeError(
            "Comparacao exige ao menos 2 empresas com valuation persistido."
        )

    nomes = [linha["ticker"] for linha in linhas]
    targets = [float(linha["target_price"] or 0.0) for linha in linhas]
    precos = [float(linha["preco_atual"] or 0.0) for linha in linhas]

    figura = go.Figure()
    figura.add_trace(
        go.Bar(
            x=nomes,
            y=targets,
            name="Target Price",
            marker={"color": COR_AZUL_ANCORA},
        )
    )
    figura.add_trace(
        go.Bar(
            x=nomes,
            y=precos,
            name="Preco atual",
            marker={"color": COR_AZUL_CLARO},
        )
    )
    for linha in linhas:
        upside = linha.get("upside")
        if not isinstance(upside, (int, float)):
            continue
        cor = COR_VERDE_UPSIDE if upside >= 0 else COR_VERMELHO_DOWNSIDE
        figura.add_annotation(
            x=linha["ticker"],
            y=max(float(linha["target_price"] or 0), float(linha["preco_atual"] or 0)),
            text=f"<b>{formatar_percentual_br(float(upside))}</b>",
            showarrow=False,
            yshift=16,
            font={"family": FONTE_MONO, "size": 13, "color": cor},
        )

    figura.update_layout(
        **layout_institucional(
            "Comparacao entre empresas — Target vs Preco",
            "Upside anotado por empresa | motor Python como fonte unica",
            altura=460,
        ),
        barmode="group",
        xaxis=eixo_institucional(None),
        yaxis=eixo_institucional("R$ por acao", tickformat=",.2f"),
    )

    nome_arquivo = "comparacao_" + "_".join(nomes[:5])
    caminhos = salvar_grafico(figura, raiz, nome_arquivo, "empresas")
    caminhos["figura"] = figura
    caminhos["linhas"] = linhas
    return caminhos


def main() -> None:
    """Compara as empresas com valuation persistido no repositorio."""
    resultado = gerar_comparacao_empresas(["DIRR3", "MGLU3", "VALE3", "ITUB4"])
    for linha in resultado["linhas"]:
        print(
            f"{linha['ticker']}: target={linha['target_price']:.2f} "
            f"upside={linha['upside']:.1%} ({linha['recomendacao']})"
        )


if __name__ == "__main__":
    main()
