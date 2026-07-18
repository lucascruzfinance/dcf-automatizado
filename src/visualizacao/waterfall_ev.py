# CONGELADO v2.1 (Prompt 9.0.0 - Enxugamento): fora do nucleo, nao-mantido.
# Removido do caminho critico (app/pipeline/main); reversivel. Ver a lista
# do congelado em Humano_revisar.md (D-053).
"""Waterfall do Enterprise Value: VP(FCFF) ano a ano + VP(VT) -> EV.

Mostra o peso de cada ano explicito e da perpetuidade na composicao do EV,
com o percentual de cada bloco e aviso quando VP(VT) passa de 80% do EV.
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
        normalizar_ticker,
        resolver_raiz,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
    from src.visualizacao.apoio_cenarios import carregar_projecao
    from src.visualizacao.tema_institucional import (
        COR_ACENTO,
        COR_AMARELO_NEUTRO,
        COR_AZUL_ANCORA,
        COR_AZUL_CLARO,
        COR_TEXTO,
        COR_VERMELHO_DOWNSIDE,
        FONTE_MONO,
        eixo_institucional,
        formatar_compacto,
        formatar_percentual_br,
        layout_institucional,
        salvar_grafico,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
    from src.visualizacao.apoio_cenarios import carregar_projecao
    from src.visualizacao.tema_institucional import (
        COR_ACENTO,
        COR_AMARELO_NEUTRO,
        COR_AZUL_ANCORA,
        COR_AZUL_CLARO,
        COR_TEXTO,
        COR_VERMELHO_DOWNSIDE,
        FONTE_MONO,
        eixo_institucional,
        formatar_compacto,
        formatar_percentual_br,
        layout_institucional,
        salvar_grafico,
    )

LIMITE_AVISO_PERPETUIDADE = 0.80


def gerar_waterfall_ev(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera o waterfall de composicao do EV e salva HTML + PNG."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    conteudo = carregar_projecao(ticker_normalizado, raiz)

    wacc = obter_float_obrigatorio(conteudo["wacc"], "wacc", "wacc")
    vp_vt = obter_float_obrigatorio(
        conteudo["valor_terminal"], "vp_vt", "valor_terminal"
    )
    ev = obter_float_obrigatorio(conteudo["ev_equity"], "ev", "ev_equity")

    rotulos = []
    valores = []
    percentuais = []
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave = f"ano{ano}"
        fluxo = obter_float_obrigatorio(conteudo["fcff"][chave], "fcff", chave)
        # Formula: VP(FCFF_t) = FCFF_t / (1 + WACC)^t.
        vp = fluxo / (1 + wacc) ** ano
        rotulos.append(f"VP FCFF a{ano}")
        valores.append(vp)
        percentuais.append(vp / ev if ev != 0 else 0.0)

    rotulos.append("VP(VT)")
    valores.append(vp_vt)
    pct_perpetuidade = vp_vt / ev if ev != 0 else 0.0
    percentuais.append(pct_perpetuidade)

    rotulos.append("EV")
    valores.append(ev)
    percentuais.append(1.0)

    medidas = ["relative"] * (HORIZONTE_PROJECAO + 1) + ["total"]
    textos = [
        f"{formatar_compacto(valor)}<br>{formatar_percentual_br(pct)}"
        for valor, pct in zip(valores, percentuais)
    ]

    figura = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=medidas,
            x=rotulos,
            y=valores,
            text=textos,
            textposition="outside",
            textfont={"family": FONTE_MONO, "size": 11, "color": COR_TEXTO},
            connector={"line": {"color": COR_AZUL_CLARO, "width": 1}},
            increasing={"marker": {"color": COR_AZUL_ANCORA}},
            decreasing={"marker": {"color": COR_VERMELHO_DOWNSIDE}},
            totals={"marker": {"color": COR_ACENTO}},
            hovertemplate="%{x}: %{y:,.0f}<extra></extra>",
        )
    )

    subtitulo = (
        f"WACC {formatar_percentual_br(wacc, 2)} | "
        f"perpetuidade = {formatar_percentual_br(pct_perpetuidade)} do EV"
    )
    figura.update_layout(
        **layout_institucional(
            f"Composicao do Enterprise Value — {ticker_normalizado}",
            subtitulo,
            altura=560,
        ),
        xaxis=eixo_institucional(None),
        yaxis=eixo_institucional("Valor presente (R$ mil)", tickformat=",.0f"),
        showlegend=False,
    )

    # Aviso semantico quando a perpetuidade domina o valuation.
    if pct_perpetuidade > LIMITE_AVISO_PERPETUIDADE:
        figura.add_annotation(
            xref="paper",
            yref="paper",
            x=0.99,
            y=0.02,
            xanchor="right",
            showarrow=False,
            text=(
                "AVISO: VP(VT) acima de 80% do EV — o valuation depende "
                "demais da perpetuidade"
            ),
            font={
                "family": FONTE_MONO,
                "size": 12,
                "color": COR_AMARELO_NEUTRO,
            },
            bgcolor="rgba(180,83,9,0.15)",
            bordercolor=COR_AMARELO_NEUTRO,
        )

    caminhos = salvar_grafico(figura, raiz, ticker_normalizado, "waterfall_ev")
    caminhos["figura"] = figura
    return caminhos


def main() -> None:
    """Gera o waterfall para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        caminhos = gerar_waterfall_ev(ticker)
        print(f"{ticker}: {caminhos['html']} | png={caminhos['png']}")


if __name__ == "__main__":
    main()
