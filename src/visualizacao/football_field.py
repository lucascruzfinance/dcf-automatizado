"""Football Field: faixas de valuation por metodologia (v2.0, Onda 3).

Metodologias: DCF Bear/Base/Bull (derivados do caso base persistido pelo
motor), Comps REAIS por multiplos de peers (Q1-mediana-Q3 vindos de
``data/processed/<TICKER>_comparaveis.json`` — os placeholders da v1.0 foram
eliminados), Multiplo de Saida e Faixa de 52 semanas. O preco atual entra
como linha vertical vermelha.

As barras sao OPCIONAIS por disponibilidade de dados: um ticker sem
valuation DCF persistido (ex.: banco antes da Onda 2) ainda renderiza as
faixas de comps reais e de 52 semanas.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.projecao.projetor_dre import (  # noqa: E402
    HORIZONTE_PROJECAO,
    carregar_json,
    normalizar_ticker,
    resolver_raiz,
)
from src.projecao.schedule_divida import obter_float_obrigatorio  # noqa: E402
from src.valuation.comparaveis import (  # noqa: E402
    ROTULOS_MULTIPLOS,
    carregar_comparaveis,
)
from src.visualizacao.apoio_cenarios import (  # noqa: E402
    carregar_mercado,
    carregar_projecao,
    recalcular_cenario,
    target_por_multiplo_saida,
)
from src.visualizacao.tema_institucional import (  # noqa: E402
    COR_ACENTO,
    COR_AZUL_ANCORA,
    COR_AZUL_CLARO,
    COR_TEXTO,
    COR_TEXTO_SECUNDARIO,
    COR_VERMELHO_DOWNSIDE,
    FONTE_MONO,
    eixo_institucional,
    formatar_moeda_brl,
    layout_institucional,
    salvar_grafico,
)

logger = logging.getLogger(__name__)


def _parametros_football(raiz: Path) -> dict[str, Any]:
    """Le os parametros do Football Field do config central."""
    parametros = carregar_json(raiz / "config" / "parametros.json")
    return parametros.get("football_field", {})


def _targets_bear_bull(
    conteudo: dict[str, Any],
    parametros: dict[str, Any],
) -> tuple[float | None, float | None, str]:
    """Targets Bear/Bull: motor de cenarios (Onda 2) > derivacao rapida.

    O bloco ``cenarios`` persistido pelo ``motor_cenarios`` roda o pipeline
    completo por cenario; a derivacao via ``recalcular_cenario`` fica como
    fallback quando os cenarios ainda nao foram executados.
    """
    cenarios = conteudo.get("cenarios")
    if isinstance(cenarios, dict):
        bear = cenarios.get("bear", {}).get("target_price")
        bull = cenarios.get("bull", {}).get("target_price")
        if isinstance(bear, (int, float)) and isinstance(bull, (int, float)):
            return float(bear), float(bull), "motor_cenarios (pipeline completo)"

    # A derivacao rapida re-deriva FCFF: so existe na trilha nao-financeira.
    if not isinstance(conteudo.get("fcff"), dict):
        return None, None, "sem cenarios persistidos (trilha financeira)"

    bear_cfg = parametros.get("cenario_bear", {})
    fator_crescimento = float(bear_cfg.get("fator_crescimento", 0.8))
    delta_margem = float(bear_cfg.get("delta_margem_pp", -0.02))
    delta_wacc = float(bear_cfg.get("delta_wacc_pp", 0.01))
    delta_g = float(bear_cfg.get("delta_g_pp", -0.005))

    bear = recalcular_cenario(
        conteudo,
        delta_wacc=delta_wacc,
        delta_g=delta_g,
        fator_crescimento=fator_crescimento,
        delta_margem_pp=delta_margem,
    )
    # Bull e o espelho do Bear (ROTEIRO, Etapa 4).
    bull = recalcular_cenario(
        conteudo,
        delta_wacc=-delta_wacc,
        delta_g=-delta_g,
        fator_crescimento=2.0 - fator_crescimento,
        delta_margem_pp=-delta_margem,
    )
    return (
        None if bear is None else float(bear["target_price"]),
        None if bull is None else float(bull["target_price"]),
        "derivacao rapida (rode o motor_cenarios para cenarios completos)",
    )


def _metodologias_dcf(
    conteudo: dict[str, Any],
    parametros: dict[str, Any],
    adicionar: Any,
) -> None:
    """Barras de DCF Bear/Base/Bull e Multiplo de Saida (exigem valuation)."""
    ev_equity = conteudo["ev_equity"]
    target_base = obter_float_obrigatorio(ev_equity, "target_price", "ev_equity")

    target_bear, target_bull, origem = _targets_bear_bull(conteudo, parametros)

    if target_bear is not None:
        adicionar(
            "DCF Bear",
            (min(target_bear, target_base), target_base),
            target_bear,
            f"cenario pessimista — {origem}",
        )
    adicionar(
        "DCF Base",
        (target_base * 0.98, target_base * 1.02),
        target_base,
        "caso base do motor",
    )
    if target_bull is not None:
        adicionar(
            "DCF Bull",
            (target_base, max(target_bull, target_base)),
            target_bull,
            f"cenario otimista — {origem}",
        )

    vt = conteudo.get("valor_terminal", {})
    multiplo_base = vt.get("multiplo_saida_implicito")
    variacao = float(parametros.get("multiplo_saida_variacao", 0.2))
    if isinstance(multiplo_base, (int, float)) and multiplo_base > 0:
        precos_multiplo = sorted(
            (
                target_por_multiplo_saida(conteudo, multiplo_base * (1 - variacao)),
                target_por_multiplo_saida(conteudo, multiplo_base * (1 + variacao)),
            )
        )
        adicionar(
            "Multiplo de Saida",
            (precos_multiplo[0], precos_multiplo[1]),
            observacao=f"EV/EBITDA de saida {multiplo_base:.1f}x +/- 20%",
        )


def _metodologias_comps(
    comparaveis: dict[str, Any],
    adicionar: Any,
) -> None:
    """Barras de comps REAIS: Q1-Q3 dos multiplos principais dos peers."""
    precos = comparaveis.get("precos_implicitos", {})
    principais = comparaveis.get("multiplos_principais", [])
    quantidade_peers = len(comparaveis.get("peers_validos", []))
    subtipo = comparaveis.get("subtipo", "n/d")
    for multiplo in principais:
        faixa = precos.get(multiplo)
        if not faixa:
            continue
        estatistica = comparaveis.get("estatisticas", {}).get(multiplo, {})
        n = int(estatistica.get("n", quantidade_peers))
        rotulo = ROTULOS_MULTIPLOS.get(multiplo, multiplo)
        adicionar(
            f"Comps {rotulo}",
            (min(faixa["q1"], faixa["q3"]), max(faixa["q1"], faixa["q3"])),
            faixa["mediana"],
            f"Q1-Q3 de {n} peers reais do subtipo {subtipo}",
        )


def montar_metodologias(
    conteudo: dict[str, Any] | None,
    mercado: dict[str, Any],
    parametros: dict[str, Any],
    comparaveis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Monta as metodologias disponiveis com faixa (min, max) e marcador.

    ``conteudo`` (projecao do motor) e ``comparaveis`` sao opcionais: cada
    bloco de barras so entra quando a fonte correspondente existe.
    """
    metodologias: list[dict[str, Any]] = []

    def adicionar(
        rotulo: str,
        faixa: tuple[float, float] | None,
        marcador: float | None = None,
        observacao: str = "",
    ) -> None:
        """Adiciona uma metodologia ao football field, ignorando faixas nulas."""
        if faixa is None:
            return
        metodologias.append(
            {
                "rotulo": rotulo,
                "minimo": faixa[0],
                "maximo": faixa[1],
                "marcador": marcador,
                "observacao": observacao,
            }
        )

    if conteudo is not None:
        _metodologias_dcf(conteudo, parametros, adicionar)
    if comparaveis:
        _metodologias_comps(comparaveis, adicionar)

    minimo_52s = mercado.get("preco_minimo_52s")
    maximo_52s = mercado.get("preco_maximo_52s")
    if isinstance(minimo_52s, (int, float)) and isinstance(maximo_52s, (int, float)):
        adicionar(
            "Faixa 52 semanas",
            (float(minimo_52s), float(maximo_52s)),
            observacao="min/max de fechamento em 12 meses",
        )

    return metodologias


def _preco_atual_disponivel(
    conteudo: dict[str, Any] | None,
    comparaveis: dict[str, Any],
    mercado: dict[str, Any],
) -> float | None:
    """Preco atual na ordem: valuation persistido > comparaveis > mercado."""
    if conteudo is not None:
        preco = conteudo.get("ev_equity", {}).get("preco_atual")
        if isinstance(preco, (int, float)) and preco > 0:
            return float(preco)
    preco = comparaveis.get("alvo", {}).get("preco_atual")
    if isinstance(preco, (int, float)) and preco > 0:
        return float(preco)
    preco = mercado.get("preco_atual")
    if isinstance(preco, (int, float)) and preco > 0:
        return float(preco)
    return None


def gerar_football_field(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera o Football Field do ticker e salva HTML + PNG.

    Nao exige valuation DCF: um ticker so com comparaveis (ex.: banco antes
    da Onda 2) renderiza as faixas disponiveis.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)

    conteudo: dict[str, Any] | None
    try:
        # Valida os blocos da trilha nao-financeira (fcff/wacc/...).
        conteudo = carregar_projecao(ticker_normalizado, raiz)
    except RuntimeError:
        # Trilha financeira (FCFE/Ke) nao tem fcff/wacc: aceita a projecao
        # direta quando ha ev_equity persistido (barras DCF vem do bloco
        # cenarios do motor). Sem valuation nenhum, field parcial.
        caminho_projecao = (
            raiz / "data" / "processed" / f"{ticker_normalizado}_projecao.json"
        )
        conteudo = None
        if caminho_projecao.exists():
            bruto = carregar_json(caminho_projecao)
            if isinstance(bruto.get("ev_equity"), dict):
                conteudo = bruto
        if conteudo is None:
            logger.warning(
                "Sem valuation persistido para %s; Football Field parcial "
                "(comps reais + faixa 52s).",
                ticker_normalizado,
            )

    comparaveis = carregar_comparaveis(ticker_normalizado, raiz)
    mercado = carregar_mercado(ticker_normalizado, raiz)
    parametros = _parametros_football(raiz)

    metodologias = montar_metodologias(conteudo, mercado, parametros, comparaveis)
    if not metodologias:
        raise RuntimeError(
            f"Nenhuma metodologia calculavel para {ticker_normalizado}. "
            "Rode o pipeline (motor) e/ou os comparaveis antes."
        )

    preco_atual = _preco_atual_disponivel(conteudo, comparaveis, mercado)

    rotulos = [item["rotulo"] for item in metodologias]
    figura = go.Figure()

    # Barras horizontais: base invisivel + faixa visivel (min -> max).
    figura.add_trace(
        go.Bar(
            y=rotulos,
            x=[item["minimo"] for item in metodologias],
            orientation="h",
            marker={"color": "rgba(0,0,0,0)"},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figura.add_trace(
        go.Bar(
            y=rotulos,
            x=[item["maximo"] - item["minimo"] for item in metodologias],
            orientation="h",
            marker={
                "color": COR_AZUL_ANCORA,
                "line": {"color": COR_AZUL_CLARO, "width": 1},
            },
            customdata=[
                [
                    formatar_moeda_brl(item["minimo"]),
                    formatar_moeda_brl(item["maximo"]),
                    item["observacao"],
                ]
                for item in metodologias
            ],
            hovertemplate=(
                "%{y}<br>Faixa: %{customdata[0]} a %{customdata[1]}"
                "<br>%{customdata[2]}<extra></extra>"
            ),
            showlegend=False,
        )
    )

    # Marcadores do valor central (cenarios e medianas) em dourado sobrio.
    marcadores = [
        (item["rotulo"], item["marcador"])
        for item in metodologias
        if item["marcador"] is not None
    ]
    if marcadores:
        figura.add_trace(
            go.Scatter(
                y=[rotulo for rotulo, _ in marcadores],
                x=[valor for _, valor in marcadores],
                mode="markers",
                marker={
                    "symbol": "diamond",
                    "size": 11,
                    "color": COR_ACENTO,
                    "line": {"color": COR_TEXTO, "width": 1},
                },
                name="Centro da metodologia",
                hovertemplate="%{y}: %{x:,.2f}<extra></extra>",
            )
        )

    # Preco atual: linha vertical vermelha (uso semantico, nao decorativo).
    if preco_atual is not None:
        figura.add_vline(
            x=preco_atual,
            line_color=COR_VERMELHO_DOWNSIDE,
            line_width=2,
            annotation_text=f"Preco atual {formatar_moeda_brl(preco_atual)}",
            annotation_position="top",
            annotation_font={
                "family": FONTE_MONO,
                "size": 12,
                "color": COR_VERMELHO_DOWNSIDE,
            },
        )

    quantidade_peers = len(comparaveis.get("peers_validos", []))
    if conteudo is not None:
        target_base = obter_float_obrigatorio(
            conteudo["ev_equity"], "target_price", "ev_equity"
        )
        subtitulo = (
            f"Target base {formatar_moeda_brl(target_base)} | "
            f"horizonte de {HORIZONTE_PROJECAO} anos | "
            f"comps reais de {quantidade_peers} peers"
        )
    else:
        subtitulo = (
            "Sem DCF persistido (trilha de valuation pendente) | "
            f"comps reais de {quantidade_peers} peers + faixa 52 semanas"
        )

    figura.update_layout(
        **layout_institucional(
            f"Football Field — {ticker_normalizado}",
            subtitulo,
            altura=520,
        ),
        barmode="stack",
        xaxis=eixo_institucional("Preco por acao (R$)", tickformat=",.2f"),
        yaxis=eixo_institucional(
            None,
            autorange="reversed",
            tickfont={"size": 13, "color": COR_TEXTO_SECUNDARIO},
        ),
    )

    caminhos = salvar_grafico(figura, raiz, ticker_normalizado, "football_field")
    caminhos["figura"] = figura
    return caminhos


def main() -> None:
    """Gera o Football Field para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        caminhos = gerar_football_field(ticker)
        print(f"{ticker}: {caminhos['html']} | png={caminhos['png']}")


if __name__ == "__main__":
    main()
