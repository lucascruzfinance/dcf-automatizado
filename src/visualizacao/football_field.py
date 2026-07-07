"""Football Field: faixas de valuation por 7 metodologias.

Metodologias: DCF Bear, DCF Base, DCF Bull, Comps EV/EBITDA (placeholder ate
o modulo de comparaveis da v2.0), Comps P/L (placeholder), Multiplo de Saida e
Faixa de 52 semanas. O preco atual entra como linha vertical vermelha.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

try:
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
    from src.visualizacao.apoio_cenarios import (
        carregar_mercado,
        carregar_projecao,
        recalcular_cenario,
        target_por_multiplo_saida,
    )
    from src.visualizacao.tema_institucional import (
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
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
    from src.visualizacao.apoio_cenarios import (
        carregar_mercado,
        carregar_projecao,
        recalcular_cenario,
        target_por_multiplo_saida,
    )
    from src.visualizacao.tema_institucional import (
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


def _parametros_football(raiz: Path) -> dict[str, Any]:
    """Le os parametros do Football Field do config central."""
    parametros = carregar_json(raiz / "config" / "parametros.json")
    return parametros.get("football_field", {})


def _target_comps_placeholder(
    conteudo: dict[str, Any],
    multiplos: list[float],
    base: str,
) -> tuple[float, float] | None:
    """Faixa placeholder de comps aplicando multiplos ao ano 1 projetado.

    ``base`` e "ev_ebitda" (bridge completo) ou "pl" (direto no lucro).
    Placeholder v1.0: os multiplos reais de peers chegam com o modulo de
    comparaveis (backlog v2.0).
    """
    if len(multiplos) != 2:
        return None
    ev_equity = conteudo["ev_equity"]
    acoes = obter_float_obrigatorio(ev_equity, "acoes_fully_diluted", "ev_equity")
    fator_escala = float(ev_equity.get("fator_escala_moeda", 1.0))
    ajustes = ev_equity.get("ajustes_bridge", {})

    precos = []
    for multiplo in multiplos:
        if base == "ev_ebitda":
            ebitda_ano1 = obter_float_obrigatorio(
                conteudo["dre"]["ano1"], "ebitda", "ano1"
            )
            # EV por multiplo -> Equity pelo mesmo bridge do motor.
            ev = multiplo * ebitda_ano1
            equity = (
                ev
                - float(ajustes.get("divida_bruta", 0.0))
                + float(ajustes.get("caixa_equivalentes", 0.0))
                + float(ajustes.get("aplicacoes_financeiras", 0.0))
                - float(ajustes.get("participacoes_minoritarias", 0.0))
                + float(ajustes.get("investimentos_coligadas", 0.0))
                + float(ajustes.get("ativos_nao_operacionais", 0.0))
            )
        else:
            lucro_ano1 = obter_float_obrigatorio(
                conteudo["dre"]["ano1"], "lucro_liquido", "ano1"
            )
            # P/L direto no lucro: Equity = multiplo x LL.
            equity = multiplo * lucro_ano1
        precos.append(equity * fator_escala / acoes)

    faixa = (min(precos), max(precos))
    if faixa[1] <= 0:
        return None
    return faixa


def montar_metodologias(
    conteudo: dict[str, Any],
    mercado: dict[str, Any],
    parametros: dict[str, Any],
) -> list[dict[str, Any]]:
    """Monta as 7 metodologias com faixa (min, max) e marcador base."""
    ev_equity = conteudo["ev_equity"]
    target_base = obter_float_obrigatorio(ev_equity, "target_price", "ev_equity")

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

    metodologias: list[dict[str, Any]] = []

    def adicionar(
        rotulo: str,
        faixa: tuple[float, float] | None,
        marcador: float | None = None,
        observacao: str = "",
    ) -> None:
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

    if bear is not None:
        adicionar(
            "DCF Bear",
            (min(bear["target_price"], target_base), target_base),
            bear["target_price"],
            "crescimento -20%, margem -2pp, WACC +1pp, g -0,5pp",
        )
    adicionar(
        "DCF Base",
        (target_base * 0.98, target_base * 1.02),
        target_base,
        "caso base do motor",
    )
    if bull is not None:
        adicionar(
            "DCF Bull",
            (target_base, max(bull["target_price"], target_base)),
            bull["target_price"],
            "espelho do Bear",
        )

    adicionar(
        "Comps EV/EBITDA*",
        _target_comps_placeholder(
            conteudo,
            list(parametros.get("comps_placeholder_ev_ebitda", [4.0, 8.0])),
            "ev_ebitda",
        ),
        observacao="*placeholder ate o modulo de comparaveis (v2.0)",
    )
    adicionar(
        "Comps P/L*",
        _target_comps_placeholder(
            conteudo,
            list(parametros.get("comps_placeholder_pl", [6.0, 12.0])),
            "pl",
        ),
        observacao="*placeholder ate o modulo de comparaveis (v2.0)",
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

    minimo_52s = mercado.get("preco_minimo_52s")
    maximo_52s = mercado.get("preco_maximo_52s")
    if isinstance(minimo_52s, (int, float)) and isinstance(maximo_52s, (int, float)):
        adicionar(
            "Faixa 52 semanas",
            (float(minimo_52s), float(maximo_52s)),
            observacao="min/max de fechamento em 12 meses",
        )

    return metodologias


def gerar_football_field(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera o Football Field do ticker e salva HTML + PNG."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    conteudo = carregar_projecao(ticker_normalizado, raiz)
    mercado = carregar_mercado(ticker_normalizado, raiz)
    parametros = _parametros_football(raiz)

    metodologias = montar_metodologias(conteudo, mercado, parametros)
    if not metodologias:
        raise RuntimeError(f"Nenhuma metodologia calculavel para {ticker_normalizado}")

    ev_equity = conteudo["ev_equity"]
    preco_atual = obter_float_obrigatorio(ev_equity, "preco_atual", "ev_equity")
    target_base = obter_float_obrigatorio(ev_equity, "target_price", "ev_equity")

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

    # Marcadores do valor central (Bear/Base/Bull) em dourado sobrio.
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
                name="Target do cenario",
                hovertemplate="%{y}: %{x:,.2f}<extra></extra>",
            )
        )

    # Preco atual: linha vertical vermelha (uso semantico, nao decorativo).
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

    subtitulo = (
        f"Target base {formatar_moeda_brl(target_base)} | "
        f"horizonte de {HORIZONTE_PROJECAO} anos | "
        "*Comps sao placeholders ate o modulo de comparaveis (v2.0)"
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
