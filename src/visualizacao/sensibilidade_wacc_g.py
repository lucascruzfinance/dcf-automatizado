"""Sensibilidade do Target Price a WACC x g (perpetuidade).

Grade de WACC (base -1,5pp a +1,5pp, passo 0,5pp) por g (base -1pp a +1pp,
passo 0,5pp), com formatacao condicional pelos limiares de recomendacao,
caso base com borda dourada e segunda tabela com o % do EV na perpetuidade.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from plotly.subplots import make_subplots

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

try:
    from src.projecao.projetor_dre import (
        carregar_json,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
    from src.visualizacao.apoio_cenarios import carregar_projecao, recalcular_cenario
    from src.visualizacao.apoio_heatmap import (
        destacar_caso_base,
        eixos_heatmap,
        montar_matrizes,
        trace_heatmap_percentual,
        trace_heatmap_target,
    )
    from src.visualizacao.tema_institucional import (
        formatar_moeda_brl,
        formatar_percentual_br,
        layout_institucional,
        salvar_grafico,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.projecao.projetor_dre import (
        carregar_json,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
    from src.visualizacao.apoio_cenarios import carregar_projecao, recalcular_cenario
    from src.visualizacao.apoio_heatmap import (
        destacar_caso_base,
        eixos_heatmap,
        montar_matrizes,
        trace_heatmap_percentual,
        trace_heatmap_target,
    )
    from src.visualizacao.tema_institucional import (
        formatar_moeda_brl,
        formatar_percentual_br,
        layout_institucional,
        salvar_grafico,
    )


def _passos_sensibilidade(raiz: Path) -> tuple[list[float], list[float]]:
    """Le os passos de WACC e g do config central."""
    parametros = carregar_json(raiz / "config" / "parametros.json")
    sensibilidade = parametros.get("sensibilidade", {})
    passos_wacc = [
        float(passo)
        for passo in sensibilidade.get(
            "wacc_passos_pp",
            [-0.015, -0.01, -0.005, 0.0, 0.005, 0.01, 0.015],
        )
    ]
    passos_g = [
        float(passo)
        for passo in sensibilidade.get(
            "g_passos_pp",
            [-0.01, -0.005, 0.0, 0.005, 0.01],
        )
    ]
    return passos_wacc, passos_g


def gerar_sensibilidade_wacc_g(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera as tabelas de sensibilidade WACC x g e salva HTML + PNG."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    conteudo = carregar_projecao(ticker_normalizado, raiz)
    passos_wacc, passos_g = _passos_sensibilidade(raiz)

    wacc_base = obter_float_obrigatorio(conteudo["wacc"], "wacc", "wacc")
    g_base = obter_float_obrigatorio(conteudo["valor_terminal"], "g", "valor_terminal")
    target_base = obter_float_obrigatorio(
        conteudo["ev_equity"], "target_price", "ev_equity"
    )

    rotulos_wacc = [
        formatar_percentual_br(wacc_base + passo, 2) for passo in passos_wacc
    ]
    rotulos_g = [formatar_percentual_br(g_base + passo, 2) for passo in passos_g]

    def calcular_celula(passo_g: float, passo_wacc: float) -> dict[str, Any] | None:
        """Recalcula o cenario da celula com os deltas de WACC e g."""
        return recalcular_cenario(
            conteudo,
            delta_wacc=passo_wacc,
            delta_g=passo_g,
        )

    matriz_target, matriz_upside, matriz_pct = montar_matrizes(
        passos_g,
        passos_wacc,
        calcular_celula,
    )

    figura = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.5, 0.5],
        vertical_spacing=0.18,
        subplot_titles=(
            "Target Price (R$/acao)",
            "% do EV na perpetuidade",
        ),
    )
    figura.add_trace(
        trace_heatmap_target(matriz_target, matriz_upside, rotulos_wacc, rotulos_g),
        row=1,
        col=1,
    )
    figura.add_trace(
        trace_heatmap_percentual(matriz_pct, rotulos_wacc, rotulos_g),
        row=2,
        col=1,
    )

    indice_wacc_base = passos_wacc.index(0.0) if 0.0 in passos_wacc else None
    indice_g_base = passos_g.index(0.0) if 0.0 in passos_g else None
    if indice_wacc_base is not None and indice_g_base is not None:
        destacar_caso_base(figura, indice_wacc_base, indice_g_base, eixo="")
        destacar_caso_base(figura, indice_wacc_base, indice_g_base, eixo="2")

    subtitulo = (
        f"Caso base: WACC {formatar_percentual_br(wacc_base, 2)}, "
        f"g {formatar_percentual_br(g_base, 2)}, "
        f"target {formatar_moeda_brl(target_base)} | "
        "verde = COMPRA, amarelo = NEUTRO, vermelho = VENDA"
    )
    figura.update_layout(
        **layout_institucional(
            f"Sensibilidade WACC x g — {ticker_normalizado}",
            subtitulo,
            altura=780,
        )
    )
    eixos_heatmap(figura, "WACC", "g (perpetuidade)", eixo="")
    eixos_heatmap(figura, "WACC", "g (perpetuidade)", eixo="2")

    caminhos = salvar_grafico(figura, raiz, ticker_normalizado, "sensibilidade_wacc_g")
    caminhos["figura"] = figura
    return caminhos


def main() -> None:
    """Gera a sensibilidade WACC x g para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        caminhos = gerar_sensibilidade_wacc_g(ticker)
        print(f"{ticker}: {caminhos['html']} | png={caminhos['png']}")


if __name__ == "__main__":
    main()
