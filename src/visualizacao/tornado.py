"""Tornado chart: impacto de cada premissa no Target Price (Onda 4).

Aplica choques padronizados e simetricos a cada premissa-chave usando o
``apoio_cenarios.recalcular_cenario`` (derivacao rapida sobre o caso base
persistido — o caso base continua nascendo exclusivamente do motor) e
ordena as barras pela amplitude do impacto. Verde = choque favoravel,
vermelho = desfavoravel (semantica estrita do projeto).

Aplicavel a trilha nao-financeira (FCFF); para financeiras o app usa os
cenarios completos do motor.
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
from src.projecao.schedule_divida import obter_float_obrigatorio  # noqa: E402
from src.visualizacao.apoio_cenarios import (  # noqa: E402
    carregar_projecao,
    recalcular_cenario,
)
from src.visualizacao.tema_institucional import (  # noqa: E402
    COR_TEXTO_SECUNDARIO,
    COR_VERDE_UPSIDE,
    COR_VERMELHO_DOWNSIDE,
    eixo_institucional,
    formatar_moeda_brl,
    layout_institucional,
    salvar_grafico,
)

# (rotulo, kwargs do choque desfavoravel, kwargs do choque favoravel)
CHOQUES_PADRAO: tuple[tuple[str, dict[str, float], dict[str, float]], ...] = (
    ("WACC +/- 1pp", {"delta_wacc": 0.01}, {"delta_wacc": -0.01}),
    ("g +/- 0,5pp", {"delta_g": -0.005}, {"delta_g": 0.005}),
    (
        "Crescimento +/- 10%",
        {"fator_crescimento": 0.9},
        {"fator_crescimento": 1.1},
    ),
    (
        "Margem EBITDA +/- 1pp",
        {"delta_margem_pp": -0.01},
        {"delta_margem_pp": 0.01},
    ),
    ("Capital de giro +/- 10%", {"fator_nwc": 1.1}, {"fator_nwc": 0.9}),
    ("CAPEX +/- 10%", {"fator_capex": 1.1}, {"fator_capex": 0.9}),
)


def calcular_impactos(
    conteudo: dict[str, Any],
) -> list[dict[str, Any]]:
    """Impactos (down/up) no Target Price por premissa, ordenados.

    Devolve itens ``{rotulo, target_down, target_up, amplitude}``; choque
    que bloqueia o Gordon (g >= WACC) vira None e a barra e omitida.
    """
    target_base = obter_float_obrigatorio(
        conteudo["ev_equity"],
        "target_price",
        "ev_equity",
    )
    impactos = []
    for rotulo, choque_down, choque_up in CHOQUES_PADRAO:
        down = recalcular_cenario(conteudo, **choque_down)
        up = recalcular_cenario(conteudo, **choque_up)
        if down is None or up is None:
            continue
        target_down = float(down["target_price"])
        target_up = float(up["target_price"])
        impactos.append(
            {
                "rotulo": rotulo,
                "target_down": target_down,
                "target_up": target_up,
                "amplitude": abs(target_up - target_down),
                "target_base": target_base,
            }
        )
    impactos.sort(key=lambda item: item["amplitude"], reverse=True)
    return impactos


def gerar_tornado(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera o tornado chart do ticker e salva HTML + PNG."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    conteudo = carregar_projecao(ticker_normalizado, raiz)
    impactos = calcular_impactos(conteudo)
    if not impactos:
        raise RuntimeError(
            f"Nenhum choque calculavel para o tornado de {ticker_normalizado}."
        )

    target_base = impactos[0]["target_base"]
    rotulos = [item["rotulo"] for item in impactos]

    figura = go.Figure()
    figura.add_trace(
        go.Bar(
            y=rotulos,
            x=[item["target_down"] - target_base for item in impactos],
            base=target_base,
            orientation="h",
            marker={"color": COR_VERMELHO_DOWNSIDE},
            name="Choque desfavoravel",
            customdata=[[formatar_moeda_brl(i["target_down"])] for i in impactos],
            hovertemplate="%{y}<br>Target: %{customdata[0]}<extra></extra>",
        )
    )
    figura.add_trace(
        go.Bar(
            y=rotulos,
            x=[item["target_up"] - target_base for item in impactos],
            base=target_base,
            orientation="h",
            marker={"color": COR_VERDE_UPSIDE},
            name="Choque favoravel",
            customdata=[[formatar_moeda_brl(i["target_up"])] for i in impactos],
            hovertemplate="%{y}<br>Target: %{customdata[0]}<extra></extra>",
        )
    )
    figura.add_vline(
        x=target_base,
        line_color=COR_TEXTO_SECUNDARIO,
        line_dash="dash",
        annotation_text=f"Base {formatar_moeda_brl(target_base)}",
        annotation_position="top",
    )
    figura.update_layout(
        **layout_institucional(
            f"Tornado — sensibilidade do Target Price — {ticker_normalizado}",
            "Choques padronizados por premissa, ordenados pela amplitude "
            "de impacto (derivados do caso base do motor)",
            altura=460,
        ),
        barmode="overlay",
        xaxis=eixo_institucional("Target Price (R$)", tickformat=",.2f"),
        yaxis=eixo_institucional(
            None,
            autorange="reversed",
            tickfont={"size": 13, "color": COR_TEXTO_SECUNDARIO},
        ),
    )

    caminhos = salvar_grafico(figura, raiz, ticker_normalizado, "tornado")
    caminhos["figura"] = figura
    return caminhos


def main() -> None:
    """Gera o tornado para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        caminhos = gerar_tornado(ticker)
        print(f"{ticker}: {caminhos['html']}")


if __name__ == "__main__":
    main()
