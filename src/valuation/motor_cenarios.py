"""Motor de cenarios de primeira classe: Bear / Base / Bull (v2.0, Onda 2).

Cada cenario RODA O PIPELINE COMPLETO do motor com um conjunto ajustado de
premissas (nao e ajuste linear de grafico): os vetores anuais de
crescimento sao multiplicados por ``fator_crescimento``, a margem recebe
``delta_margem_pp``, o g recebe ``delta_g_pp`` e a taxa de desconto recebe
``delta_wacc_pp`` (aplicado ao bloco persistido antes de VT/EV, ja que WACC
e Ke nascem de beta/Kd e nao sao premissas diretas). Parametros por cenario
em ``config/parametros.json`` (bloco ``cenarios``).

Fluxo: faz backup das premissas do analista -> roda cada cenario -> restaura
as premissas -> RE-RODA o caso base (o disco sempre termina no caso base)
-> persiste o bloco ``cenarios`` na projecao. Preco atual e Rf sao lidos dos
JSONs de mercado persistidos (sem rede e sem preco vivo, para os cenarios
serem reproduziveis).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from src.projecao.gerador_premissas import HORIZONTE_PROJECAO
from src.projecao.projetor_dre import (
    carregar_json,
    carregar_metadados,
    normalizar_ticker,
    resolver_raiz,
    salvar_json,
)
from src.projecao.projetor_financeiro import projetar_financeiro
from src.projecao.schedule_divida import projetar_divida
from src.projecao.schedule_ppe import projetar_ppe
from src.projecao.schedule_wk import projetar_wk
from src.valuation.calculador_ev import calcular_ev
from src.valuation.calculador_fcfe import calcular_fcfe_financeira
from src.valuation.calculador_fcff import calcular_fcff
from src.valuation.calculador_vt import calcular_valor_terminal
from src.valuation.calculador_wacc import calcular_ke, calcular_wacc

logger = logging.getLogger(__name__)

CENARIOS_ORDEM = ("bear", "base", "bull")


def carregar_parametros_cenarios(raiz: Path) -> dict[str, dict[str, float]]:
    """Le os parametros Bear/Bull do config central (base = sem ajuste)."""
    parametros = carregar_json(raiz / "config" / "parametros.json")
    cenarios = parametros.get("cenarios", {})
    return {
        "bear": dict(cenarios.get("bear", {})),
        "base": {},
        "bull": dict(cenarios.get("bull", {})),
    }


def _mercado(ticker: str, raiz: Path) -> dict[str, Any]:
    """JSON de mercado persistido (preco/rf reproduziveis para cenarios)."""
    caminho = raiz / "data" / "raw" / "mercado" / f"{ticker}_mercado.json"
    if not caminho.exists():
        return {}
    return carregar_json(caminho)


def ajustar_premissas_cenario(
    premissas: dict[str, Any],
    ajustes: dict[str, float],
    financeira: bool,
) -> dict[str, Any]:
    """Aplica os ajustes do cenario as premissas (funcao pura)."""
    novas = dict(premissas)
    fator = float(ajustes.get("fator_crescimento", 1.0))
    delta_margem = float(ajustes.get("delta_margem_pp", 0.0))
    delta_g = float(ajustes.get("delta_g_pp", 0.0))

    campo_margem = "margem_resultado_bruto" if financeira else "margem_ebitda"
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        campo_crescimento = f"crescimento_receita_ano{ano}"
        if campo_crescimento in novas and novas[campo_crescimento] is not None:
            novas[campo_crescimento] = float(novas[campo_crescimento]) * fator
        campo = f"{campo_margem}_ano{ano}"
        if campo in novas and novas[campo] is not None:
            novas[campo] = float(novas[campo]) + delta_margem

    if novas.get("crescimento_perpetuidade_g") is not None:
        novas["crescimento_perpetuidade_g"] = (
            float(novas["crescimento_perpetuidade_g"]) + delta_g
        )
    return novas


def _aplicar_delta_taxa_desconto(
    ticker: str,
    raiz: Path,
    delta: float,
    financeira: bool,
) -> None:
    """Aplica delta_wacc_pp ao bloco de taxa persistido (antes de VT/EV).

    WACC/Ke nao sao premissas diretas (nascem de beta, Kd e estrutura);
    o delta do cenario e aplicado ao bloco persistido, e VT/EV consomem o
    valor ajustado — mantendo o motor como unica fonte de calculo.
    """
    if delta == 0.0:
        return
    caminho = raiz / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    if financeira:
        conteudo["ke"]["ke_brl"] = float(conteudo["ke"]["ke_brl"]) + delta
        conteudo["ke"]["delta_cenario_pp"] = delta
    else:
        conteudo["wacc"]["wacc"] = float(conteudo["wacc"]["wacc"]) + delta
        conteudo["wacc"]["delta_cenario_pp"] = delta
    salvar_json(caminho, conteudo)


def _rodar_cadeia(
    ticker: str,
    raiz: Path,
    financeira: bool,
    ajustes: dict[str, float],
) -> dict[str, Any]:
    """Roda a cadeia completa do motor para o estado atual das premissas."""
    mercado = _mercado(ticker, raiz)
    rf = mercado.get("rf_usd_tbond10y")
    preco = mercado.get("preco_atual")
    delta_taxa = float(ajustes.get("delta_wacc_pp", 0.0))

    if financeira:
        projetar_financeiro(ticker, raiz)
        calcular_ke(ticker, raiz, rf_usd=rf)
        _aplicar_delta_taxa_desconto(ticker, raiz, delta_taxa, financeira=True)
        resultado = calcular_fcfe_financeira(ticker, raiz, preco_atual=preco)
        ev_equity = resultado["ev_equity"]
        taxa = float(resultado["ke"]) + delta_taxa
    else:
        from src.projecao.projetor_dre import projetar_dre

        projetar_dre(ticker, raiz)
        projetar_wk(ticker, raiz)
        projetar_ppe(ticker, raiz)
        projetar_divida(ticker, raiz)
        calcular_fcff(ticker, raiz)
        calcular_wacc(ticker, raiz, rf_usd=rf)
        _aplicar_delta_taxa_desconto(ticker, raiz, delta_taxa, financeira=False)
        calcular_valor_terminal(ticker, raiz)
        ev_equity = calcular_ev(ticker, raiz, preco_atual=preco)
        caminho = raiz / "data" / "processed" / f"{ticker}_projecao.json"
        taxa = float(carregar_json(caminho)["wacc"]["wacc"])

    caminho = raiz / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    valor_terminal = conteudo.get("valor_terminal", {})
    return {
        "target_price": float(ev_equity["target_price"]),
        "upside": (
            float(ev_equity["upside"]) if ev_equity.get("upside") is not None else None
        ),
        "recomendacao": ev_equity.get("recomendacao"),
        "taxa_desconto": taxa,
        "g": valor_terminal.get("g"),
        "equity_value": float(ev_equity["equity_value"]),
        "pct_ev_perpetuidade": valor_terminal.get("pct_ev_perpetuidade"),
    }


def executar_cenarios(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Roda Bear/Base/Bull pelo pipeline e persiste o bloco ``cenarios``.

    As premissas do analista sao SEMPRE restauradas; o disco termina com o
    caso base recalculado + o bloco de cenarios na projecao.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    metadados = carregar_metadados(ticker_normalizado, raiz)
    financeira = str(metadados.get("tipo")) == "financeira"
    parametros_cenarios = carregar_parametros_cenarios(raiz)

    caminho_premissas = (
        raiz / "data" / "premissas" / f"{ticker_normalizado}_premissas.json"
    )
    premissas_base = carregar_json(caminho_premissas)
    caminho_backup = caminho_premissas.with_suffix(".json.cenario_backup")
    shutil.copy2(caminho_premissas, caminho_backup)

    resultados: dict[str, Any] = {}
    try:
        for nome in ("bear", "bull"):
            ajustes = parametros_cenarios[nome]
            premissas_cenario = ajustar_premissas_cenario(
                premissas_base,
                ajustes,
                financeira,
            )
            salvar_json(caminho_premissas, premissas_cenario)
            resultados[nome] = _rodar_cadeia(
                ticker_normalizado,
                raiz,
                financeira,
                ajustes,
            )
            resultados[nome]["ajustes"] = ajustes
    finally:
        # Restaura as premissas do analista aconteca o que acontecer.
        shutil.copy2(caminho_backup, caminho_premissas)
        caminho_backup.unlink(missing_ok=True)

    # O caso base fecha por ultimo: o estado em disco volta a ser o oficial.
    resultados["base"] = _rodar_cadeia(ticker_normalizado, raiz, financeira, {})
    resultados["base"]["ajustes"] = {}

    caminho_projecao = (
        raiz / "data" / "processed" / f"{ticker_normalizado}_projecao.json"
    )
    conteudo = carregar_json(caminho_projecao)
    conteudo["cenarios"] = {
        nome: resultados[nome] for nome in CENARIOS_ORDEM if nome in resultados
    }
    salvar_json(caminho_projecao, conteudo)

    return conteudo["cenarios"]


def main() -> None:
    """Roda os cenarios para os tickers padrao."""
    import argparse

    parser = argparse.ArgumentParser(description="Motor de cenarios Bear/Base/Bull.")
    parser.add_argument("tickers", nargs="*", default=["DIRR3", "MGLU3"])
    argumentos = parser.parse_args()
    for ticker in argumentos.tickers:
        try:
            cenarios = executar_cenarios(ticker)
        except (RuntimeError, ValueError) as erro:
            print(f"Falha nos cenarios de {ticker}: {erro}")
            continue
        partes = [
            f"{nome}: R$ {dados['target_price']:.2f}"
            for nome, dados in cenarios.items()
        ]
        print(f"{ticker} -> " + " | ".join(partes))


if __name__ == "__main__":
    main()
