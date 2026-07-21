# DESCONGELADO na Semana 10 (revisao de 20/07/2026): re-alinhado ao motor
# 9.0.x e coberto por teste. A re-integracao ao app (sub-abas de graficos) e a
# entrega do Prompt 10.0.4. Ver Humano_revisar.md (D-078, reverte D-053).
"""Tabela de comparaveis peer-a-peer com a empresa-alvo destacada (Onda 3).

Renderiza, no tema institucional, uma tabela Plotly com um peer por linha
(ticker, market cap e os multiplos aplicaveis ao tipo), a empresa-alvo
destacada em azul ancora e as linhas de Q1 / MEDIANA / Q3 do peer group ao
final. Consome exclusivamente ``data/processed/<TICKER>_comparaveis.json``
persistido por ``src/valuation/comparaveis.py`` — nenhum multiplo e
recalculado aqui.
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
    normalizar_ticker,
    resolver_raiz,
)
from src.valuation.comparaveis import (  # noqa: E402
    ROTULOS_MULTIPLOS,
    carregar_comparaveis,
)
from src.visualizacao.tema_institucional import (  # noqa: E402
    COR_AZUL_ANCORA,
    COR_FUNDO,
    COR_GRADE,
    COR_SUPERFICIE,
    COR_TEXTO,
    FONTE_MONO,
    FONTE_SANS,
    formatar_compacto,
    layout_institucional,
    salvar_grafico,
)


def _formatar_multiplo(valor: Any) -> str:
    """Formata multiplo como '7,3x'; ausente vira 'n/d'."""
    if not isinstance(valor, (int, float)):
        return "n/d"
    return f"{valor:,.1f}x".replace(".", ",")


def _formatar_market_cap(valor: Any) -> str:
    """Formata market cap compacto em R$; ausente vira 'n/d'."""
    if not isinstance(valor, (int, float)):
        return "n/d"
    return f"R$ {formatar_compacto(float(valor))}"


def montar_linhas_tabela(
    comparaveis: dict[str, Any],
) -> tuple[list[str], list[list[str]], list[str]]:
    """Monta cabecalho, linhas e cores de fundo da tabela de comparaveis.

    Ordem das linhas: peers validos -> empresa-alvo destacada -> Q1 /
    MEDIANA / Q3 do peer group. Funcao pura para testes.
    """
    multiplos = list(comparaveis.get("multiplos_aplicaveis", []))
    cabecalho = ["Ticker", "Market Cap"] + [
        ROTULOS_MULTIPLOS.get(multiplo, multiplo) for multiplo in multiplos
    ]

    linhas: list[list[str]] = []
    cores: list[str] = []

    por_peer = comparaveis.get("multiplos_por_peer", {})
    for peer in comparaveis.get("peers_validos", []):
        dados = por_peer.get(peer, {})
        linhas.append(
            [peer, _formatar_market_cap(dados.get("market_cap"))]
            + [_formatar_multiplo(dados.get(multiplo)) for multiplo in multiplos]
        )
        cores.append(COR_SUPERFICIE)

    alvo = comparaveis.get("multiplos_alvo")
    ticker_alvo = str(comparaveis.get("ticker", ""))
    if alvo:
        linhas.append(
            [f"► {ticker_alvo} (alvo)", _formatar_market_cap(alvo.get("market_cap"))]
            + [_formatar_multiplo(alvo.get(multiplo)) for multiplo in multiplos]
        )
        cores.append(COR_AZUL_ANCORA)

    estatisticas = comparaveis.get("estatisticas", {})
    for ponto, rotulo in (("q1", "Q1"), ("mediana", "MEDIANA"), ("q3", "Q3")):
        linha = [rotulo, "—"]
        for multiplo in multiplos:
            faixa = estatisticas.get(multiplo)
            linha.append(_formatar_multiplo(faixa[ponto]) if faixa else "n/d")
        linhas.append(linha)
        cores.append(COR_GRADE)

    return cabecalho, linhas, cores


def gerar_tabela_comparaveis(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera a tabela de comparaveis do ticker e salva HTML + PNG."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    comparaveis = carregar_comparaveis(ticker_normalizado, raiz)
    if not comparaveis:
        raise RuntimeError(
            f"Comparaveis nao gerados para {ticker_normalizado}. Rode "
            "python -m src.valuation.comparaveis antes da tabela."
        )

    cabecalho, linhas, cores = montar_linhas_tabela(comparaveis)
    if not linhas:
        raise RuntimeError(
            f"Nenhum peer valido para {ticker_normalizado}; tabela vazia."
        )

    colunas = list(map(list, zip(*linhas)))
    cores_por_coluna = [cores for _ in cabecalho]

    figura = go.Figure(
        data=[
            go.Table(
                header={
                    "values": [f"<b>{titulo}</b>" for titulo in cabecalho],
                    "fill_color": COR_AZUL_ANCORA,
                    "font": {"family": FONTE_SANS, "color": COR_TEXTO, "size": 13},
                    "align": ["left", "right"] + ["right"] * (len(cabecalho) - 2),
                    "height": 34,
                },
                cells={
                    "values": colunas,
                    "fill_color": cores_por_coluna,
                    "font": {
                        "family": FONTE_MONO,
                        "color": COR_TEXTO,
                        "size": 12,
                    },
                    "align": ["left", "right"] + ["right"] * (len(cabecalho) - 2),
                    "height": 28,
                },
            )
        ]
    )

    quantidade = len(comparaveis.get("peers_validos", []))
    excluidos = len(comparaveis.get("peers_excluidos", []))
    subtitulo = (
        f"{quantidade} peers validos ({comparaveis.get('subtipo', 'n/d')})"
        + (f" | {excluidos} excluido(s) — ver logs" if excluidos else "")
        + " | fonte: yfinance | alvo destacado em azul"
    )
    layout = layout_institucional(
        f"Comparaveis — {ticker_normalizado}",
        subtitulo,
        altura=120 + 30 * (len(linhas) + 1),
    )
    layout["paper_bgcolor"] = COR_FUNDO
    layout["margin"] = {"l": 20, "r": 20, "t": 90, "b": 20}
    figura.update_layout(**layout)

    caminhos = salvar_grafico(
        figura,
        raiz,
        ticker_normalizado,
        "tabela_comparaveis",
    )
    caminhos["figura"] = figura
    return caminhos


def main() -> None:
    """Gera a tabela de comparaveis para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        caminhos = gerar_tabela_comparaveis(ticker)
        print(f"{ticker}: {caminhos['html']} | png={caminhos['png']}")


if __name__ == "__main__":
    main()
