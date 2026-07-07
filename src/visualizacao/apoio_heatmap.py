"""Apoio compartilhado para as tabelas de sensibilidade em heatmap.

A formatacao condicional segue os limiares de recomendacao do motor:
verde = upside > 20% (COMPRA), amarelo = entre -5% e +20% (NEUTRO),
vermelho = downside < -5% (VENDA). Celulas bloqueadas (g >= WACC) ficam
apagadas com "n/d". O caso base recebe borda dourada.
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
    from src.visualizacao.tema_institucional import (
        COR_ACENTO,
        COR_FUNDO,
        COR_TEXTO,
        FONTE_MONO,
        eixo_institucional,
        formatar_moeda_brl,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.visualizacao.tema_institucional import (
        COR_ACENTO,
        COR_FUNDO,
        COR_TEXTO,
        FONTE_MONO,
        eixo_institucional,
        formatar_moeda_brl,
    )

LIMITE_COMPRA = 0.20
LIMITE_VENDA = -0.05

# Escala discreta: 0 = VENDA (vermelho), 1 = NEUTRO (amarelo), 2 = COMPRA
# (verde), com transparencia para nao ofuscar o texto do target price.
ESCALA_RECOMENDACAO = [
    [0.0, "rgba(220,38,38,0.55)"],
    [0.33, "rgba(220,38,38,0.55)"],
    [0.34, "rgba(180,83,9,0.55)"],
    [0.66, "rgba(180,83,9,0.55)"],
    [0.67, "rgba(22,163,74,0.55)"],
    [1.0, "rgba(22,163,74,0.55)"],
]


def _categoria_upside(upside: float | None) -> float | None:
    """Categoria de cor pelo limiar de recomendacao do motor."""
    if upside is None:
        return None
    if upside > LIMITE_COMPRA:
        return 2.0
    if upside < LIMITE_VENDA:
        return 0.0
    return 1.0


def trace_heatmap_target(
    matriz_target: list[list[float | None]],
    matriz_upside: list[list[float | None]],
    rotulos_x: list[str],
    rotulos_y: list[str],
) -> go.Heatmap:
    """Monta o heatmap de target price com formatacao condicional."""
    z = [[_categoria_upside(upside) for upside in linha] for linha in matriz_upside]
    texto = [
        [formatar_moeda_brl(valor) if valor is not None else "n/d" for valor in linha]
        for linha in matriz_target
    ]
    return go.Heatmap(
        z=z,
        x=rotulos_x,
        y=rotulos_y,
        text=texto,
        texttemplate="%{text}",
        textfont={"family": FONTE_MONO, "size": 12, "color": COR_TEXTO},
        colorscale=ESCALA_RECOMENDACAO,
        zmin=0,
        zmax=2,
        showscale=False,
        hovertemplate="%{x} | %{y}<br>Target %{text}<extra></extra>",
        xgap=2,
        ygap=2,
    )


def trace_heatmap_percentual(
    matriz_pct: list[list[float | None]],
    rotulos_x: list[str],
    rotulos_y: list[str],
) -> go.Heatmap:
    """Monta o heatmap secundario de % do EV na perpetuidade."""
    texto = [
        [
            f"{valor * 100:,.1f}%".replace(".", ",") if valor is not None else "n/d"
            for valor in linha
        ]
        for linha in matriz_pct
    ]
    return go.Heatmap(
        z=matriz_pct,
        x=rotulos_x,
        y=rotulos_y,
        text=texto,
        texttemplate="%{text}",
        textfont={"family": FONTE_MONO, "size": 12, "color": COR_TEXTO},
        colorscale=[
            [0.0, COR_FUNDO],
            [1.0, "rgba(27,79,140,0.9)"],
        ],
        showscale=False,
        hovertemplate="%{x} | %{y}<br>Perpetuidade %{text}<extra></extra>",
        xgap=2,
        ygap=2,
    )


def destacar_caso_base(
    figura: go.Figure,
    indice_x: int,
    indice_y: int,
    eixo: str = "",
) -> None:
    """Desenha borda dourada na celula do caso base (indices do heatmap)."""
    figura.add_shape(
        type="rect",
        x0=indice_x - 0.5,
        x1=indice_x + 0.5,
        y0=indice_y - 0.5,
        y1=indice_y + 0.5,
        xref=f"x{eixo}",
        yref=f"y{eixo}",
        line={"color": COR_ACENTO, "width": 3},
    )


def eixos_heatmap(
    figura: go.Figure,
    titulo_x: str,
    titulo_y: str,
    eixo: str = "",
) -> None:
    """Aplica eixos institucionais categoricos ao heatmap."""
    figura.update_layout(
        {
            f"xaxis{eixo}": eixo_institucional(titulo_x, showgrid=False),
            f"yaxis{eixo}": eixo_institucional(
                titulo_y, showgrid=False, autorange="reversed"
            ),
        }
    )


def montar_matrizes(
    valores_y: list[Any],
    valores_x: list[Any],
    calcular_celula: Any,
) -> tuple[
    list[list[float | None]], list[list[float | None]], list[list[float | None]]
]:
    """Varre a grade chamando ``calcular_celula(y, x)`` por celula.

    ``calcular_celula`` devolve o dicionario do cenario ou None (bloqueado).
    Devolve (matriz_target, matriz_upside, matriz_pct_perpetuidade).
    """
    matriz_target: list[list[float | None]] = []
    matriz_upside: list[list[float | None]] = []
    matriz_pct: list[list[float | None]] = []
    for valor_y in valores_y:
        linha_target: list[float | None] = []
        linha_upside: list[float | None] = []
        linha_pct: list[float | None] = []
        for valor_x in valores_x:
            cenario = calcular_celula(valor_y, valor_x)
            if cenario is None:
                linha_target.append(None)
                linha_upside.append(None)
                linha_pct.append(None)
            else:
                linha_target.append(cenario["target_price"])
                linha_upside.append(cenario["upside"])
                linha_pct.append(cenario["pct_ev_perpetuidade"])
        matriz_target.append(linha_target)
        matriz_upside.append(linha_upside)
        matriz_pct.append(linha_pct)
    return matriz_target, matriz_upside, matriz_pct
