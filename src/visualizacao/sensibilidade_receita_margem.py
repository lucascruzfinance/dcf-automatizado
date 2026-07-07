"""Sensibilidade do Target Price a crescimento de receita x margem EBITDA.

Grade de deltas em pontos percentuais aplicados a TODOS os anos da projecao
(crescimento aditivo por ano; margem aditiva por ano), com formatacao
condicional pelos limiares de recomendacao e caso base destacado.
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
        trace_heatmap_target,
    )
    from src.visualizacao.tema_institucional import (
        formatar_moeda_brl,
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
        trace_heatmap_target,
    )
    from src.visualizacao.tema_institucional import (
        formatar_moeda_brl,
        layout_institucional,
        salvar_grafico,
    )


def _passos(raiz: Path) -> tuple[list[float], list[float]]:
    """Le os passos de crescimento e margem do config central."""
    parametros = carregar_json(raiz / "config" / "parametros.json")
    sensibilidade = parametros.get("sensibilidade", {})
    passos_crescimento = [
        float(passo)
        for passo in sensibilidade.get(
            "crescimento_passos_pp",
            [-0.02, -0.01, 0.0, 0.01, 0.02],
        )
    ]
    passos_margem = [
        float(passo)
        for passo in sensibilidade.get(
            "margem_passos_pp",
            [-0.02, -0.01, 0.0, 0.01, 0.02],
        )
    ]
    return passos_crescimento, passos_margem


def _rotulo_delta(passo: float) -> str:
    """Rotulo de delta em pontos percentuais (ex.: +1,0pp)."""
    texto = f"{passo * 100:+.1f}pp".replace(".", ",")
    return texto if passo != 0 else "base"


def gerar_sensibilidade_receita_margem(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera a sensibilidade crescimento x margem e salva HTML + PNG."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    conteudo = carregar_projecao(ticker_normalizado, raiz)
    passos_crescimento, passos_margem = _passos(raiz)

    target_base = obter_float_obrigatorio(
        conteudo["ev_equity"], "target_price", "ev_equity"
    )

    def calcular_celula(
        passo_margem: float,
        passo_crescimento: float,
    ) -> dict[str, Any] | None:
        return recalcular_cenario(
            conteudo,
            delta_crescimento_pp=passo_crescimento,
            delta_margem_pp=passo_margem,
        )

    matriz_target, matriz_upside, _ = montar_matrizes(
        passos_margem,
        passos_crescimento,
        calcular_celula,
    )

    rotulos_x = [_rotulo_delta(passo) for passo in passos_crescimento]
    rotulos_y = [_rotulo_delta(passo) for passo in passos_margem]

    figura = go.Figure(
        trace_heatmap_target(matriz_target, matriz_upside, rotulos_x, rotulos_y)
    )
    if 0.0 in passos_crescimento and 0.0 in passos_margem:
        destacar_caso_base(
            figura,
            passos_crescimento.index(0.0),
            passos_margem.index(0.0),
        )

    subtitulo = (
        f"Deltas aplicados aos 8 anos | caso base "
        f"{formatar_moeda_brl(target_base)} | verde = COMPRA, "
        "amarelo = NEUTRO, vermelho = VENDA"
    )
    figura.update_layout(
        **layout_institucional(
            f"Sensibilidade Crescimento x Margem — {ticker_normalizado}",
            subtitulo,
            altura=520,
        )
    )
    eixos_heatmap(
        figura,
        "Delta crescimento de receita (pp/ano)",
        "Delta margem EBITDA (pp)",
    )

    caminhos = salvar_grafico(
        figura, raiz, ticker_normalizado, "sensibilidade_receita_margem"
    )
    caminhos["figura"] = figura
    return caminhos


def main() -> None:
    """Gera a sensibilidade para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        caminhos = gerar_sensibilidade_receita_margem(ticker)
        print(f"{ticker}: {caminhos['html']} | png={caminhos['png']}")


if __name__ == "__main__":
    main()
