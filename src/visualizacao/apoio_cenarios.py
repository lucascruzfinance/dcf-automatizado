# RETIDO no nucleo (Prompt 9.0.0): NAO e chart. Suporte do exportador Excel
# legado (formatacao/cores/derivacao de cenario) ate a reescrita do 9.0.5.
# Nao importado por app.py (que usa src/apresentacao/formatacao.py).
"""Apoio de cenarios para os graficos de valuation.

Recalcula o Target Price sob perturbacoes de premissas (crescimento, margem,
WACC, g, capital de giro, CAPEX) A PARTIR dos blocos ja persistidos pelo motor
em ``data/processed/<TICKER>_projecao.json``. Nao reexecuta o pipeline: o caso
base continua nascendo exclusivamente do motor (fonte unica de verdade); aqui
apenas derivamos cenarios em torno dele para Football Field e sensibilidades.

Aproximacao documentada: Delta NWC e CAPEX escalam proporcionalmente a receita
do cenario (intensidades constantes em relacao ao caso base); a D&A permanece
no valor absoluto do caso base. E a mesma simplificacao usada em modelos de
mesa para tabelas de sensibilidade rapidas.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

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

BLOCOS_NECESSARIOS = ("ano0", "dre", "fcff", "wacc", "valor_terminal", "ev_equity")


def carregar_projecao(ticker: str, raiz_projeto: Path | None = None) -> dict[str, Any]:
    """Carrega a projecao persistida validando os blocos usados nos graficos."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    caminho = raiz / "data" / "processed" / f"{ticker_normalizado}_projecao.json"
    conteudo = carregar_json(caminho)
    for bloco in BLOCOS_NECESSARIOS:
        if not isinstance(conteudo.get(bloco), dict):
            raise RuntimeError(
                f"Bloco obrigatorio ausente em {caminho}: {bloco}. "
                "Rode o pipeline da Semana 3 antes de gerar graficos."
            )
    return conteudo


def carregar_mercado(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Carrega o JSON de mercado coletado; vazio se nao existir."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    caminho = raiz / "data" / "raw" / "mercado" / f"{ticker_normalizado}_mercado.json"
    if not caminho.exists():
        return {}
    return carregar_json(caminho)


def carregar_metricas(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Carrega as metricas historicas persistidas; vazio se nao existirem."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    caminho = raiz / "data" / "processed" / f"{ticker_normalizado}_metricas.json"
    if not caminho.exists():
        return {}
    return carregar_json(caminho)


def _series_base(conteudo: dict[str, Any]) -> dict[str, list[float]]:
    """Extrai as series anuais do caso base usadas na re-derivacao."""
    dre = conteudo["dre"]
    fcff = conteudo["fcff"]
    series: dict[str, list[float]] = {
        "receita": [],
        "taxa_crescimento": [],
        "margem_ebitda": [],
        "depreciacao": [],
        "delta_nwc": [],
        "capex_saida": [],
    }
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave = f"ano{ano}"
        series["receita"].append(
            obter_float_obrigatorio(dre[chave], "receita_liquida", chave)
        )
        series["taxa_crescimento"].append(
            obter_float_obrigatorio(dre[chave], "taxa_crescimento_receita", chave)
        )
        series["margem_ebitda"].append(
            obter_float_obrigatorio(dre[chave], "margem_ebitda", chave)
        )
        series["depreciacao"].append(
            obter_float_obrigatorio(fcff[chave], "depreciacao_amortizacao", chave)
        )
        series["delta_nwc"].append(
            obter_float_obrigatorio(fcff[chave], "delta_nwc", chave)
        )
        series["capex_saida"].append(
            obter_float_obrigatorio(fcff[chave], "capex_saida_caixa", chave)
        )
    return series


def recalcular_cenario(
    conteudo: dict[str, Any],
    delta_wacc: float = 0.0,
    delta_g: float = 0.0,
    fator_crescimento: float = 1.0,
    delta_crescimento_pp: float = 0.0,
    delta_margem_pp: float = 0.0,
    fator_nwc: float = 1.0,
    fator_capex: float = 1.0,
) -> dict[str, Any] | None:
    """Recalcula Target Price sob um cenario derivado do caso base.

    Devolve None quando ``g' >= WACC'`` (celula bloqueada pelo Gordon) —
    o chamador decide como representar a celula invalida.
    """
    series = _series_base(conteudo)
    ano0 = conteudo["ano0"]
    fcff_base = conteudo["fcff"]
    wacc_base = obter_float_obrigatorio(conteudo["wacc"], "wacc", "wacc")
    g_base = obter_float_obrigatorio(conteudo["valor_terminal"], "g", "valor_terminal")
    ev_equity = conteudo["ev_equity"]
    ajustes = ev_equity.get("ajustes_bridge", {})
    acoes = obter_float_obrigatorio(ev_equity, "acoes_fully_diluted", "ev_equity")
    fator_escala = float(ev_equity.get("fator_escala_moeda", 1.0))
    preco_atual = float(ev_equity.get("preco_atual", 0.0))
    aliquota = float(fcff_base["ano1"].get("aliquota_ir_nopat", 0.34))

    wacc = wacc_base + delta_wacc
    g = g_base + delta_g
    # Salvaguarda de Gordon: g >= WACC explode a perpetuidade.
    if g >= wacc or wacc <= 0:
        return None

    receita_anterior = obter_float_obrigatorio(ano0, "receita_liquida", "ano0")
    fluxos: list[float] = []
    nopat_ano8 = 0.0
    ebitda_ano8 = 0.0
    for indice in range(HORIZONTE_PROJECAO):
        taxa = series["taxa_crescimento"][indice] * fator_crescimento
        taxa += delta_crescimento_pp
        margem = series["margem_ebitda"][indice] + delta_margem_pp
        receita = receita_anterior * (1 + taxa)

        # Intensidades do caso base escalam com a receita do cenario.
        receita_base = series["receita"][indice]
        escala_receita = receita / receita_base if receita_base != 0 else 1.0

        ebitda = receita * margem
        depreciacao = series["depreciacao"][indice]
        ebit = ebitda - depreciacao
        # Formula: NOPAT = EBIT x (1 - aliquota do NOPAT usada pelo motor).
        nopat = ebit * (1 - aliquota)
        delta_nwc = series["delta_nwc"][indice] * escala_receita * fator_nwc
        capex_saida = series["capex_saida"][indice] * escala_receita * fator_capex

        # Formula: FCFF = NOPAT + D&A - Delta NWC - CAPEX.
        fluxos.append(nopat + depreciacao - delta_nwc - capex_saida)
        receita_anterior = receita
        if indice == HORIZONTE_PROJECAO - 1:
            nopat_ano8 = nopat
            ebitda_ano8 = ebitda

    # Formula: VP(FCFF_t) = FCFF_t / (1 + WACC)^t.
    soma_vp_fcff = sum(
        fluxo / (1 + wacc) ** (indice + 1) for indice, fluxo in enumerate(fluxos)
    )

    # Base do VT: FCFF_8, ou NOPAT_8 normalizado quando FCFF_8 < 0.
    base_vt = fluxos[-1] if fluxos[-1] >= 0 else nopat_ano8
    # Formula: VT = base x (1 + g) / (WACC - g); VP(VT) = VT / (1 + WACC)^8.
    vt_bruto = base_vt * (1 + g) / (wacc - g)
    vp_vt = vt_bruto / (1 + wacc) ** HORIZONTE_PROJECAO

    ev = soma_vp_fcff + vp_vt
    # Bridge identico ao calculador_ev, com os ajustes persistidos pelo motor.
    equity = (
        ev
        - float(ajustes.get("divida_bruta", 0.0))
        + float(ajustes.get("caixa_equivalentes", 0.0))
        + float(ajustes.get("aplicacoes_financeiras", 0.0))
        - float(ajustes.get("participacoes_minoritarias", 0.0))
        + float(ajustes.get("investimentos_coligadas", 0.0))
        + float(ajustes.get("ativos_nao_operacionais", 0.0))
    )
    target_price = equity * fator_escala / acoes
    upside = target_price / preco_atual - 1 if preco_atual > 0 else None

    return {
        "wacc": wacc,
        "g": g,
        "fcff": fluxos,
        "soma_vp_fcff": soma_vp_fcff,
        "vt_bruto": vt_bruto,
        "vp_vt": vp_vt,
        "ev": ev,
        "equity": equity,
        "target_price": target_price,
        "upside": upside,
        "pct_ev_perpetuidade": vp_vt / ev if ev != 0 else None,
        "ebitda_ano8": ebitda_ano8,
    }


def target_por_multiplo_saida(
    conteudo: dict[str, Any],
    multiplo: float,
) -> float:
    """Target Price trocando o Gordon por um multiplo de saida EV/EBITDA.

    VT = multiplo x EBITDA_8; o restante do bridge permanece o do motor.
    """
    ev_equity = conteudo["ev_equity"]
    wacc = obter_float_obrigatorio(conteudo["wacc"], "wacc", "wacc")
    ebitda_ano8 = obter_float_obrigatorio(conteudo["dre"]["ano8"], "ebitda", "ano8")
    soma_vp_fcff = obter_float_obrigatorio(ev_equity, "soma_vp_fcff", "ev_equity")
    ajustes = ev_equity.get("ajustes_bridge", {})
    acoes = obter_float_obrigatorio(ev_equity, "acoes_fully_diluted", "ev_equity")
    fator_escala = float(ev_equity.get("fator_escala_moeda", 1.0))

    # Formula: VP(VT) = multiplo x EBITDA_8 / (1 + WACC)^8.
    vp_vt = multiplo * ebitda_ano8 / (1 + wacc) ** HORIZONTE_PROJECAO
    ev = soma_vp_fcff + vp_vt
    equity = (
        ev
        - float(ajustes.get("divida_bruta", 0.0))
        + float(ajustes.get("caixa_equivalentes", 0.0))
        + float(ajustes.get("aplicacoes_financeiras", 0.0))
        - float(ajustes.get("participacoes_minoritarias", 0.0))
        + float(ajustes.get("investimentos_coligadas", 0.0))
        + float(ajustes.get("ativos_nao_operacionais", 0.0))
    )
    return equity * fator_escala / acoes
