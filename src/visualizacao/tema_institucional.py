# RETIDO no nucleo (Prompt 9.0.0): NAO e chart. Suporte do exportador Excel
# legado (formatacao/cores/derivacao de cenario) ate a reescrita do 9.0.5.
# Nao importado por app.py (que usa src/apresentacao/formatacao.py).
"""Tema visual institucional compartilhado por todos os graficos Plotly.

Paleta e tipografia definidas no ROTEIRO (Etapa 4): fundo navy, azul ancora,
verde/vermelho com uso semantico estrito (upside/downside, nunca decorativo),
texto em sans e numeros em fonte monoespacada. Todos os modulos de
``src/visualizacao/`` importam daqui — nenhum grafico define cor propria.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

# Paleta institucional (ROTEIRO, secao Etapa 4 — Design institucional).
COR_FUNDO = "#0A1628"
COR_SUPERFICIE = "#0F1E33"
COR_AZUL_ANCORA = "#1B4F8C"
COR_AZUL_CLARO = "#5B8DC9"
COR_ACENTO = "#C9A227"
COR_VERDE_UPSIDE = "#16A34A"
COR_VERMELHO_DOWNSIDE = "#DC2626"
COR_AMARELO_NEUTRO = "#B45309"
COR_TEXTO = "#E6EDF5"
COR_TEXTO_SECUNDARIO = "#8FA3BC"
COR_GRADE = "#1E3350"

FONTE_SANS = "Inter, 'IBM Plex Sans', 'Segoe UI', sans-serif"
FONTE_MONO = "'IBM Plex Mono', Consolas, monospace"

LARGURA_PNG = 1280
ALTURA_PNG = 720
ESCALA_PNG = 2

logger = logging.getLogger(__name__)


def layout_institucional(
    titulo: str,
    subtitulo: str | None = None,
    altura: int | None = None,
) -> dict[str, Any]:
    """Monta o layout base institucional aplicado a todos os graficos."""
    texto_titulo = f"<b>{titulo}</b>"
    if subtitulo:
        texto_titulo += (
            f"<br><span style='font-size:13px;color:{COR_TEXTO_SECUNDARIO}'>"
            f"{subtitulo}</span>"
        )
    layout: dict[str, Any] = {
        "paper_bgcolor": COR_FUNDO,
        "plot_bgcolor": COR_SUPERFICIE,
        "font": {"family": FONTE_SANS, "color": COR_TEXTO, "size": 13},
        "title": {
            "text": texto_titulo,
            "x": 0.02,
            "xanchor": "left",
            "font": {"family": FONTE_SANS, "size": 20, "color": COR_TEXTO},
        },
        "margin": {"l": 70, "r": 40, "t": 90, "b": 60},
        "hoverlabel": {
            "bgcolor": COR_SUPERFICIE,
            "bordercolor": COR_AZUL_ANCORA,
            "font": {"family": FONTE_MONO, "color": COR_TEXTO, "size": 12},
        },
        "legend": {
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"size": 12, "color": COR_TEXTO_SECUNDARIO},
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.0,
            "xanchor": "right",
            "x": 1.0,
        },
    }
    if altura is not None:
        layout["height"] = altura
    return layout


def eixo_institucional(titulo: str | None = None, **extras: Any) -> dict[str, Any]:
    """Configura um eixo com grade discreta e numeros em fonte mono."""
    eixo: dict[str, Any] = {
        "gridcolor": COR_GRADE,
        "zerolinecolor": COR_GRADE,
        "linecolor": COR_GRADE,
        "tickfont": {"family": FONTE_MONO, "size": 12, "color": COR_TEXTO_SECUNDARIO},
    }
    if titulo:
        eixo["title"] = {
            "text": titulo,
            "font": {"family": FONTE_SANS, "size": 13, "color": COR_TEXTO_SECUNDARIO},
        }
    eixo.update(extras)
    return eixo


def formatar_moeda_brl(valor: float, casas: int = 2) -> str:
    """Formata valor em R$ no padrao brasileiro (ponto milhar, virgula decimal)."""
    texto = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def formatar_percentual_br(valor: float, casas: int = 1) -> str:
    """Formata decimal como percentual brasileiro."""
    texto = f"{valor * 100:,.{casas}f}".replace(",", "X")
    texto = texto.replace(".", ",").replace("X", ".")
    return f"{texto}%"


def formatar_compacto(valor: float) -> str:
    """Formata numero grande em notacao compacta (mil/mi/bi) para rotulos."""
    magnitude = abs(valor)
    if magnitude >= 1_000_000_000:
        return f"{valor / 1_000_000_000:,.1f} bi".replace(".", ",")
    if magnitude >= 1_000_000:
        return f"{valor / 1_000_000:,.1f} mi".replace(".", ",")
    if magnitude >= 1_000:
        return f"{valor / 1_000:,.1f} mil".replace(".", ",")
    return f"{valor:,.1f}".replace(".", ",")


def pasta_graficos(raiz_projeto: Path) -> Path:
    """Devolve (criando) a pasta padrao de saida dos graficos."""
    pasta = raiz_projeto / "outputs" / "graficos"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def salvar_grafico(
    figura: go.Figure,
    raiz_projeto: Path,
    ticker: str,
    nome: str,
) -> dict[str, Path | None]:
    """Salva o grafico em HTML e PNG em ``outputs/graficos/``.

    O HTML e obrigatorio; o PNG depende do kaleido e falha com aviso em vez
    de derrubar o pipeline (maquinas sem Chrome nao geram PNG).
    """
    pasta = pasta_graficos(raiz_projeto)
    caminho_html = pasta / f"{ticker}_{nome}.html"
    caminho_png: Path | None = pasta / f"{ticker}_{nome}.png"

    figura.write_html(
        str(caminho_html),
        include_plotlyjs="cdn",
        full_html=True,
    )
    try:
        figura.write_image(
            str(caminho_png),
            width=LARGURA_PNG,
            height=ALTURA_PNG,
            scale=ESCALA_PNG,
        )
    except Exception as erro:  # pragma: no cover - depende do kaleido/Chrome.
        logger.warning("Falha ao exportar PNG de %s_%s: %s", ticker, nome, erro)
        caminho_png = None

    return {"html": caminho_html, "png": caminho_png}
