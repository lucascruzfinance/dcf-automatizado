# DESCONGELADO na Semana 10 (revisao de 20/07/2026): re-alinhado ao motor
# 9.0.x e coberto por teste. A re-integracao ao app (sub-abas de graficos) e a
# entrega do Prompt 10.0.4. Ver Humano_revisar.md (D-078, reverte D-053).
"""ROIC e ROIIC historico vs projetado como reality check.

O grafico torna explicitos ROIC e ROIIC nos anos de forecast, comparando com
media e mediana historicas quando disponiveis. Ele apenas apresenta metricas
ja calculadas pelo motor e pela camada de metricas historicas.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

try:
    from src.metricas.metricas_historicas import calcular_metricas_historicas
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.visualizacao.apoio_cenarios import carregar_metricas, carregar_projecao
    from src.visualizacao.tema_institucional import (
        COR_ACENTO,
        COR_AMARELO_NEUTRO,
        COR_AZUL_CLARO,
        COR_TEXTO_SECUNDARIO,
        eixo_institucional,
        formatar_percentual_br,
        layout_institucional,
        salvar_grafico,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.metricas.metricas_historicas import calcular_metricas_historicas
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.visualizacao.apoio_cenarios import carregar_metricas, carregar_projecao
    from src.visualizacao.tema_institucional import (
        COR_ACENTO,
        COR_AMARELO_NEUTRO,
        COR_AZUL_CLARO,
        COR_TEXTO_SECUNDARIO,
        eixo_institucional,
        formatar_percentual_br,
        layout_institucional,
        salvar_grafico,
    )

PAINEIS = (("roic", "ROIC"), ("roiic", "ROIIC"))


def _numero_opcional(valor: Any) -> float | None:
    """Converte numero opcional sem aceitar booleano."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def _serie_historica(
    metricas: dict[str, Any], campo: str
) -> tuple[list[int], list[float]]:
    """Extrai serie anual historica de uma metrica."""
    anos: list[int] = []
    valores: list[float] = []
    for ano in sorted(metricas.get("metricas_por_ano", {})):
        linha = metricas["metricas_por_ano"][ano]
        valor = _numero_opcional(linha.get(campo))
        if valor is None:
            continue
        anos.append(int(ano))
        valores.append(valor)
    return anos, valores


def _serie_projetada(
    conteudo: dict[str, Any],
    campo: str,
    ano_final_historico: int,
) -> tuple[list[int], list[float]]:
    """Extrai ROIC/ROIIC projetado do bloco FCFF persistido."""
    anos: list[int] = []
    valores: list[float] = []
    fcff = conteudo["fcff"]
    for indice in range(1, HORIZONTE_PROJECAO + 1):
        chave = f"ano{indice}"
        valor = _numero_opcional(fcff[chave].get(campo))
        if valor is None:
            continue
        anos.append(ano_final_historico + indice)
        valores.append(valor)
    return anos, valores


def _adicionar_linha_referencia(
    figura: go.Figure,
    *,
    row: int,
    col: int,
    anos: list[int],
    valor: float | None,
    nome: str,
    cor: str,
) -> None:
    """Adiciona linha horizontal de media/mediana historica."""
    if valor is None or not anos:
        return
    figura.add_trace(
        go.Scatter(
            x=[min(anos), max(anos)],
            y=[valor, valor],
            mode="lines",
            name=nome,
            line={"color": cor, "width": 1.5, "dash": "dot"},
            hovertemplate=(
                f"{nome}: {formatar_percentual_br(valor, 2)}<extra></extra>"
            ),
            showlegend=(row == 1),
        ),
        row=row,
        col=col,
    )


def gerar_roic_roiic(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera grafico de ROIC e ROIIC historico vs projetado."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    conteudo = carregar_projecao(ticker_normalizado, raiz)

    metricas = carregar_metricas(ticker_normalizado, raiz)
    agregados = metricas.get("agregados", {})
    if not metricas.get("metricas_por_ano") or "roiic_media_3a" not in agregados:
        metricas = calcular_metricas_historicas(ticker_normalizado, raiz)

    anos_historicos_receita = sorted(metricas.get("metricas_por_ano", {}))
    if not anos_historicos_receita:
        raise RuntimeError(f"Sem metricas historicas para {ticker_normalizado}.")
    ano_final_historico = int(anos_historicos_receita[-1])

    figura = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("ROIC", "ROIIC"),
        vertical_spacing=0.16,
    )

    agregados = metricas.get("agregados", {})
    for linha, (campo, titulo) in enumerate(PAINEIS, start=1):
        anos_hist, valores_hist = _serie_historica(metricas, campo)
        anos_proj, valores_proj = _serie_projetada(
            conteudo,
            campo,
            ano_final_historico,
        )
        todos_anos = anos_hist + anos_proj

        figura.add_trace(
            go.Scatter(
                x=anos_hist,
                y=valores_hist,
                mode="lines+markers",
                name=f"{titulo} historico",
                legendgroup=f"{campo}_hist",
                line={"color": COR_AZUL_CLARO, "width": 2},
                marker={"size": 6},
                hovertemplate="%{x}: %{y:.2%}<extra>Historico</extra>",
                showlegend=(linha == 1),
            ),
            row=linha,
            col=1,
        )
        figura.add_trace(
            go.Scatter(
                x=anos_proj,
                y=valores_proj,
                mode="lines+markers",
                name=f"{titulo} projetado",
                legendgroup=f"{campo}_proj",
                line={"color": COR_ACENTO, "width": 2, "dash": "dash"},
                marker={"size": 6, "symbol": "diamond"},
                hovertemplate="%{x}: %{y:.2%}<extra>Projetado</extra>",
                showlegend=(linha == 1),
            ),
            row=linha,
            col=1,
        )
        _adicionar_linha_referencia(
            figura,
            row=linha,
            col=1,
            anos=todos_anos,
            valor=_numero_opcional(agregados.get(f"{campo}_media_3a")),
            nome=f"{titulo} media historica 3a",
            cor=COR_TEXTO_SECUNDARIO,
        )
        _adicionar_linha_referencia(
            figura,
            row=linha,
            col=1,
            anos=todos_anos,
            valor=_numero_opcional(agregados.get(f"{campo}_mediana_3a")),
            nome=f"{titulo} mediana historica 3a",
            cor=COR_AMARELO_NEUTRO,
        )
        figura.update_yaxes(
            eixo_institucional(None, tickformat=".1%"),
            row=linha,
            col=1,
        )
        figura.update_xaxes(eixo_institucional(None, dtick=1), row=linha, col=1)

    subtitulo = (
        "Reality check: ROIC = NOPAT / IC; ROIIC usa Delta NOPAT_t sobre "
        "Delta IC_(t-1), sem forcar trajetoria"
    )
    figura.update_layout(
        **layout_institucional(
            f"ROIC e ROIIC — {ticker_normalizado}",
            subtitulo,
            altura=780,
        )
    )

    caminhos = salvar_grafico(figura, raiz, ticker_normalizado, "roic_roiic")
    caminhos["figura"] = figura
    return caminhos


def main() -> None:
    """Gera ROIC/ROIIC para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        caminhos = gerar_roic_roiic(ticker)
        print(f"{ticker}: {caminhos['html']} | png={caminhos['png']}")


if __name__ == "__main__":
    main()
