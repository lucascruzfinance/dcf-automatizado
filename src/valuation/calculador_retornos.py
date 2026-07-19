"""Painel de Retornos do acionista (Prompt 9.0.3.3, padrao D@G do Smartfit).

Tres visoes persistidas no bloco ``retornos`` da projecao integrada:

1. **Multiplos implicitos por ano** (no preco atual e no target): EV/EBITDA,
   EV/Receita e P/L para nao-financeiras; P/L e P/VP para financeiras (sem
   EV/EBITDA — divida de banco e insumo operacional). Denominador nao
   positivo -> multiplo ``None`` (nao significativo), nunca erro.
2. **TIR do acionista**: fluxo = -preco atual no ano 0; +dividendos/acao nos
   anos 1..N; +preco de saida no ano N (default N=5, config ``retornos``).
   Preco de saida = target price do bridge FCFF, TRUNCADO em zero quando o
   target e negativo (responsabilidade limitada: o acionista nao paga para
   sair). TIR por bissecao; sem mudanca de sinal -> ``None`` com nota.
3. **MOIC** = (soma dos dividendos/acao + preco de saida) / preco atual, e a
   grade Bear/Base/Bull variando o preco de saida em +/- a variacao da
   config (o motor de cenarios completo esta CONGELADO desde o 9.0.0; a
   grade aqui e uma sensibilidade de saida, nao um re-run do valuation).

Consumidor puro: le blocos ja persistidos (dre, dfc, ev_equity, fcfe) e NAO
recalcula FCFF/WACC/VT — o motor calcula uma vez (regra do projeto).
"""

from __future__ import annotations

import logging
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
        formatar_numero,
        formatar_percentual,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        formatar_numero,
        formatar_percentual,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )

HORIZONTE_TIR_PADRAO = 5
VARIACAO_TARGET_PADRAO = 0.20
TOLERANCIA_TIR = 1e-9
MAX_ITERACOES_TIR = 200

logger = logging.getLogger(__name__)


def _numero_ou_none(valor: Any) -> float | None:
    """Converte para float sem aceitar booleanos; invalido vira None."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def carregar_parametros_retornos(raiz_projeto: Path) -> dict[str, float]:
    """Le o bloco ``retornos`` de config/parametros.json com defaults."""
    try:
        parametros = carregar_json(raiz_projeto / "config" / "parametros.json")
    except RuntimeError:
        parametros = {}
    bloco = parametros.get("retornos", {}) if isinstance(parametros, dict) else {}
    horizonte = _numero_ou_none(bloco.get("horizonte_tir_anos"))
    variacao = _numero_ou_none(bloco.get("variacao_target_bear_bull"))
    if horizonte is None or not 1 <= int(horizonte) <= HORIZONTE_PROJECAO:
        horizonte = HORIZONTE_TIR_PADRAO
    if variacao is None or variacao <= 0:
        variacao = VARIACAO_TARGET_PADRAO
    return {
        "horizonte_tir_anos": int(horizonte),
        "variacao_target_bear_bull": float(variacao),
    }


def carregar_projecao_retornos(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[Path, dict[str, Any]]:
    """Carrega a projecao integrada e valida os blocos minimos do painel."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    for bloco in ("dre", "ev_equity"):
        if not isinstance(conteudo.get(bloco), dict):
            raise RuntimeError(
                f"Bloco obrigatorio ausente em {caminho}: {bloco}. Rode o "
                "valuation (EV/Equity) antes do painel de retornos."
            )
    return caminho, conteudo


def _razao_ou_none(numerador: float, denominador: float | None) -> float | None:
    """Multiplo = numerador/denominador; denominador nao positivo -> None.

    Multiplos com denominador negativo ou nulo nao sao significativos
    (convencao de mercado: "n.m."); o painel persiste None e o front-end
    exibe n/d. LL/EBITDA negativos continuam VALIDOS no motor.
    """
    if denominador is None or denominador <= 0:
        return None
    return numerador / denominador


def _equity_no_preco(ev_equity: dict[str, Any]) -> tuple[float, float, float]:
    """Devolve (equity no preco atual, acoes, fator) na escala das DFs.

    Formula: equity_preco = preco atual x acoes / fator_escala — leva o
    market cap para a MESMA escala (MIL/MILHAO) dos demonstrativos, onde
    vivem EBITDA/receita/dividendos.
    """
    preco = float(ev_equity["preco_atual"])
    acoes = float(ev_equity["acoes_fully_diluted"])
    fator = float(ev_equity.get("fator_escala_moeda") or 1.0)
    return preco * acoes / fator, acoes, fator


def _ev_das_pontas(
    conteudo: dict[str, Any],
) -> tuple[float | None, float | None]:
    """EV implicito no preco atual e no target (escala das DFs).

    EV(equity) = equity + divida bruta - caixa - aplicacoes + minoritarios -
    coligadas - ativos nao operacionais (o INVERSO do bridge persistido em
    ``ev_equity.ajustes_bridge``). No target, o EV e o proprio ``ev``
    persistido; no preco atual, ajusta o EV pela diferenca de equity.
    """
    ev_equity = conteudo["ev_equity"]
    ev_target = _numero_ou_none(ev_equity.get("ev"))
    equity_target = _numero_ou_none(ev_equity.get("equity_value"))
    if ev_target is None or equity_target is None:
        return None, None
    equity_preco, _, _ = _equity_no_preco(ev_equity)
    # Mesmo bridge, equity diferente: EV_preco = EV_target + (E_preco - E_target).
    return ev_target + (equity_preco - equity_target), ev_target


def montar_multiplos_implicitos(
    conteudo: dict[str, Any],
    tipo: str,
) -> dict[str, dict[str, Any]]:
    """Multiplos implicitos por ano nas duas pontas (preco atual e target).

    Nao-financeiras: EV/EBITDA, EV/Receita e P/L. Financeiras: P/L e P/VP
    (PL projetado do ``capital_regulatorio`` quando existir).
    """
    dre = conteudo["dre"]
    ev_equity = conteudo["ev_equity"]
    equity_preco, acoes, fator = _equity_no_preco(ev_equity)
    equity_target = _numero_ou_none(ev_equity.get("equity_value"))
    preco = float(ev_equity["preco_atual"])
    target = _numero_ou_none(ev_equity.get("target_price"))
    ev_preco, ev_target = (None, None)
    if tipo != "financeira":
        ev_preco, ev_target = _ev_das_pontas(conteudo)

    capital_regulatorio = conteudo.get("capital_regulatorio", {})
    multiplos: dict[str, dict[str, Any]] = {}
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_dre = dre.get(chave_ano, {})
        if not isinstance(linha_dre, dict):
            linha_dre = {}
        ebitda = _numero_ou_none(linha_dre.get("ebitda"))
        receita = _numero_ou_none(linha_dre.get("receita_liquida"))
        lucro = _numero_ou_none(linha_dre.get("lucro_liquido"))
        lpa = _numero_ou_none(linha_dre.get("lpa"))

        # P/L: preco/LPA quando o LPA existe; senao equity/LL (identico).
        if lpa is not None:
            p_l_preco = _razao_ou_none(preco, lpa * fator)
            p_l_target = (
                _razao_ou_none(target, lpa * fator) if target is not None else None
            )
        else:
            p_l_preco = _razao_ou_none(equity_preco, lucro)
            p_l_target = (
                _razao_ou_none(equity_target, lucro)
                if equity_target is not None
                else None
            )

        linha: dict[str, Any] = {
            "ano_projecao": chave_ano,
            "p_l_preco_atual": p_l_preco,
            "p_l_target": p_l_target,
        }
        if tipo == "financeira":
            linha_capital = capital_regulatorio.get(chave_ano, {})
            # PL projetado da trilha financeira = capital retido do schedule
            # regulatorio (parte do PL contabil do Ano 0) — proxy do VPA.
            patrimonio = _numero_ou_none(
                linha_capital.get("capital_regulatorio")
                if isinstance(linha_capital, dict)
                else None
            )
            # Formula: VPA_t = PL_t / acoes (escala das DFs); P/VP = preco/VPA.
            vpa = patrimonio * fator / acoes if patrimonio is not None else None
            linha["vpa"] = vpa
            linha["p_vp_preco_atual"] = _razao_ou_none(preco, vpa)
            linha["p_vp_target"] = (
                _razao_ou_none(target, vpa) if target is not None else None
            )
        else:
            linha["ev_ebitda_preco_atual"] = (
                _razao_ou_none(ev_preco, ebitda) if ev_preco is not None else None
            )
            linha["ev_ebitda_target"] = (
                _razao_ou_none(ev_target, ebitda) if ev_target is not None else None
            )
            linha["ev_receita_preco_atual"] = (
                _razao_ou_none(ev_preco, receita) if ev_preco is not None else None
            )
            linha["ev_receita_target"] = (
                _razao_ou_none(ev_target, receita) if ev_target is not None else None
            )
        multiplos[chave_ano] = linha
    return multiplos


def calcular_tir(fluxos: list[float]) -> float | None:
    """TIR por bissecao em (-99,99%, 1000%); sem raiz -> None.

    Formula: NPV(r) = soma fluxo_t / (1 + r)^t = 0. Robusta a fluxos sem
    mudanca de sinal (retorna None em vez de explodir) — target negativo ou
    dividendos zero sao casos reais do motor.
    """

    def npv(taxa: float) -> float:
        return sum(fluxo / (1 + taxa) ** ano for ano, fluxo in enumerate(fluxos))

    baixo, alto = -0.9999, 10.0
    npv_baixo, npv_alto = npv(baixo), npv(alto)
    if npv_baixo == 0:
        return baixo
    if npv_alto == 0:
        return alto
    if npv_baixo * npv_alto > 0:
        return None
    for _ in range(MAX_ITERACOES_TIR):
        meio = (baixo + alto) / 2
        npv_meio = npv(meio)
        if abs(npv_meio) < TOLERANCIA_TIR or (alto - baixo) / 2 < TOLERANCIA_TIR:
            return meio
        if npv_baixo * npv_meio < 0:
            alto, npv_alto = meio, npv_meio
        else:
            baixo, npv_baixo = meio, npv_meio
    return (baixo + alto) / 2


def _dividendos_por_acao(
    conteudo: dict[str, Any],
    tipo: str,
    acoes: float,
    fator: float,
    horizonte: int,
) -> tuple[dict[str, float], str]:
    """Dividendos/acao dos anos 1..N (R$/acao) e a origem da serie.

    Nao-financeiras: linha ``dividendos`` do DFC (payout do schedule de
    divida). Financeiras: FCFE_t (capacidade de distribuicao) truncado em
    zero — nao ha DFC projetado na trilha bancaria.
    """
    dividendos: dict[str, float] = {}
    if tipo == "financeira":
        fcfe = conteudo.get("fcfe", {})
        for ano in range(1, horizonte + 1):
            linha = fcfe.get(f"ano{ano}", {}) if isinstance(fcfe, dict) else {}
            valor = _numero_ou_none(linha.get("fcfe")) or 0.0
            dividendos[f"ano{ano}"] = max(valor, 0.0) * fator / acoes
        return dividendos, "fcfe_financeira_truncado_em_zero"

    dfc = conteudo.get("dfc", {})
    for ano in range(1, horizonte + 1):
        linha = dfc.get(f"ano{ano}", {}) if isinstance(dfc, dict) else {}
        valor = _numero_ou_none(linha.get("dividendos")) or 0.0
        # Formula: dividendos/acao_t = dividendos_t x fator_escala / acoes.
        dividendos[f"ano{ano}"] = abs(valor) * fator / acoes
    return dividendos, "dividendos_do_dfc"


def montar_tir_moic(
    conteudo: dict[str, Any],
    tipo: str,
    parametros: dict[str, float],
) -> dict[str, Any]:
    """TIR e MOIC do acionista na grade Bear/Base/Bull de preco de saida.

    Fluxo (D@G do Smartfit, traduzido): -preco atual no ano 0; +dividendos/
    acao nos anos 1..N; +preco de saida no ano N. Preco de saida = target
    price (bridge FCFF) truncado em ZERO quando negativo (responsabilidade
    limitada). Bear/Bull variam o preco de saida em -/+ a variacao da config.
    MOIC = (soma dividendos + saida) / preco.
    """
    ev_equity = conteudo["ev_equity"]
    preco = float(ev_equity["preco_atual"])
    target = float(ev_equity.get("target_price") or 0.0)
    _, acoes, fator = _equity_no_preco(ev_equity)
    horizonte = int(parametros["horizonte_tir_anos"])
    variacao = float(parametros["variacao_target_bear_bull"])

    dividendos, origem_dividendos = _dividendos_por_acao(
        conteudo, tipo, acoes, fator, horizonte
    )
    soma_dividendos = sum(dividendos.values())

    cenarios: dict[str, dict[str, Any]] = {}
    for nome, fator_cenario in (
        ("bear", 1 - variacao),
        ("base", 1.0),
        ("bull", 1 + variacao),
    ):
        saida_bruta = target * fator_cenario
        preco_saida = max(saida_bruta, 0.0)
        fluxos = [-preco]
        for ano in range(1, horizonte + 1):
            fluxo = dividendos[f"ano{ano}"]
            if ano == horizonte:
                fluxo += preco_saida
            fluxos.append(fluxo)
        tir = calcular_tir(fluxos)
        # Formula: MOIC = (dividendos recebidos + preco de saida) / preco pago.
        moic = (soma_dividendos + preco_saida) / preco if preco > 0 else None
        cenarios[nome] = {
            "preco_saida": preco_saida,
            "preco_saida_truncado_em_zero": saida_bruta < 0,
            "tir_acionista": tir,
            "moic": moic,
        }
        if tir is None:
            logger.warning(
                "TIR sem raiz no cenario %s (fluxos sem mudanca de sinal); "
                "persistindo None.",
                nome,
            )

    return {
        "horizonte_tir_anos": horizonte,
        "preco_entrada": preco,
        "target_price_base": target,
        "dividendos_por_acao": dividendos,
        "origem_dividendos": origem_dividendos,
        "variacao_target_bear_bull": variacao,
        "cenarios": cenarios,
    }


def calcular_retornos(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Calcula e persiste o bloco ``retornos`` na projecao integrada."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    caminho, conteudo = carregar_projecao_retornos(ticker_normalizado, raiz)
    parametros = carregar_parametros_retornos(raiz)
    tipo = str(conteudo.get("tipo", "nao_financeira"))

    retornos = {
        "ticker": ticker_normalizado,
        "tipo": tipo,
        "parametros": {
            **parametros,
            "metodo_preco_saida": "target_price_bridge_truncado_em_zero",
        },
        "multiplos": montar_multiplos_implicitos(conteudo, tipo),
        "tir_moic": montar_tir_moic(conteudo, tipo, parametros),
    }

    conteudo["retornos"] = retornos
    salvar_json(caminho, conteudo)
    retornos["caminho_saida"] = caminho
    return retornos


def imprimir_retornos(resultado: dict[str, Any]) -> None:
    """Imprime o painel de retornos para validacao visual."""
    print("\n" + "=" * 72)
    print(f"Painel de Retornos - {resultado['ticker']} ({resultado['tipo']})")
    tir_moic = resultado["tir_moic"]
    print(
        f"Entrada R$ {formatar_numero(tir_moic['preco_entrada'])} | "
        f"target base R$ {formatar_numero(tir_moic['target_price_base'])} | "
        f"N = {tir_moic['horizonte_tir_anos']} anos"
    )
    for nome in ("bear", "base", "bull"):
        cenario = tir_moic["cenarios"][nome]
        tir = cenario["tir_acionista"]
        texto_tir = formatar_percentual(tir) if tir is not None else "n/d"
        moic = cenario["moic"]
        texto_moic = f"{moic:.2f}x" if moic is not None else "n/d"
        print(
            f"  {nome:<5} saida R$ {formatar_numero(cenario['preco_saida']):>10} | "
            f"TIR {texto_tir:>10} | MOIC {texto_moic:>7}"
        )
    multiplos_ano1 = resultado["multiplos"]["ano1"]
    if "ev_ebitda_preco_atual" in multiplos_ano1:
        valor = multiplos_ano1["ev_ebitda_preco_atual"]
        texto = f"{valor:.2f}x" if valor is not None else "n/d"
        print(f"  EV/EBITDA ano1 (preco atual): {texto}")


def main() -> None:
    """Executa o painel padrao para DIRR3."""
    imprimir_retornos(calcular_retornos("DIRR3"))


if __name__ == "__main__":
    main()
