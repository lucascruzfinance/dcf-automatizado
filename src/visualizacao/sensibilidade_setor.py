"""Sensibilidade setorial do Target Price.

Construcao (DIRR3): Margem EBITDA x intensidade de capital de giro. O VSO
(velocidade de vendas) nao e observavel no modelo v1.0; a intensidade de NWC
e usada como proxy inverso documentado — VSO alto significa menos capital
preso em estoque/recebiveis, ou seja, fator de NWC menor.

Varejo e demais setores (MGLU3): Margem EBITDA x intensidade de CAPEX,
os dois drivers setoriais genericos disponiveis no motor.
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
        normalizar_texto,
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
        normalizar_texto,
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


def _configuracao(raiz: Path) -> tuple[list[float], list[float]]:
    """Le passos de margem e fatores de intensidade do config central."""
    parametros = carregar_json(raiz / "config" / "parametros.json")
    sensibilidade = parametros.get("sensibilidade", {})
    passos_margem = [
        float(passo)
        for passo in sensibilidade.get(
            "margem_passos_pp",
            [-0.02, -0.01, 0.0, 0.01, 0.02],
        )
    ]
    fatores = [
        float(fator)
        for fator in sensibilidade.get(
            "fatores_intensidade",
            [0.8, 0.9, 1.0, 1.1, 1.2],
        )
    ]
    return passos_margem, fatores


def _rotulo_delta(passo: float) -> str:
    """Rotulo de delta em pontos percentuais."""
    texto = f"{passo * 100:+.1f}pp".replace(".", ",")
    return texto if passo != 0 else "base"


def _rotulo_fator(fator: float) -> str:
    """Rotulo de fator multiplicativo de intensidade."""
    if fator == 1.0:
        return "base"
    return f"{fator:.2f}x".replace(".", ",")


def gerar_sensibilidade_setor(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera a sensibilidade setorial do ticker e salva HTML + PNG."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    conteudo = carregar_projecao(ticker_normalizado, raiz)
    passos_margem, fatores = _configuracao(raiz)

    setor = normalizar_texto(conteudo.get("setor"))
    eh_construcao = "construcao" in setor
    target_base = obter_float_obrigatorio(
        conteudo["ev_equity"], "target_price", "ev_equity"
    )

    if eh_construcao:
        titulo_y = "Intensidade de capital de giro (proxy inverso de VSO)"
        nota = (
            "VSO alto = vende mais rapido = menos NWC preso; "
            "fator 0,80x equivale a VSO melhor que o caso base"
        )

        def calcular_celula(
            fator: float,
            passo_margem: float,
        ) -> dict[str, Any] | None:
            return recalcular_cenario(
                conteudo,
                delta_margem_pp=passo_margem,
                fator_nwc=fator,
            )

    else:
        titulo_y = "Intensidade de CAPEX (fator sobre o caso base)"
        nota = "sensibilidade generica de varejo: margem x investimento"

        def calcular_celula(
            fator: float,
            passo_margem: float,
        ) -> dict[str, Any] | None:
            return recalcular_cenario(
                conteudo,
                delta_margem_pp=passo_margem,
                fator_capex=fator,
            )

    matriz_target, matriz_upside, _ = montar_matrizes(
        fatores,
        passos_margem,
        calcular_celula,
    )

    rotulos_x = [_rotulo_delta(passo) for passo in passos_margem]
    rotulos_y = [_rotulo_fator(fator) for fator in fatores]

    figura = go.Figure(
        trace_heatmap_target(matriz_target, matriz_upside, rotulos_x, rotulos_y)
    )
    if 0.0 in passos_margem and 1.0 in fatores:
        destacar_caso_base(
            figura,
            passos_margem.index(0.0),
            fatores.index(1.0),
        )

    rotulo_setor = (
        "Construcao: Margem x VSO (proxy)"
        if eh_construcao
        else ("Varejo: Margem x CAPEX")
    )
    subtitulo = (
        f"{nota} | caso base {formatar_moeda_brl(target_base)} | "
        "verde = COMPRA, amarelo = NEUTRO, vermelho = VENDA"
    )
    figura.update_layout(
        **layout_institucional(
            f"Sensibilidade Setorial ({rotulo_setor}) — {ticker_normalizado}",
            subtitulo,
            altura=520,
        )
    )
    eixos_heatmap(figura, "Delta margem EBITDA (pp)", titulo_y)

    caminhos = salvar_grafico(figura, raiz, ticker_normalizado, "sensibilidade_setor")
    caminhos["figura"] = figura
    return caminhos


def main() -> None:
    """Gera a sensibilidade setorial para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        caminhos = gerar_sensibilidade_setor(ticker)
        print(f"{ticker}: {caminhos['html']} | png={caminhos['png']}")


if __name__ == "__main__":
    main()
