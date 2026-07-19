"""Valuation FCFE/Ke: trilha financeira (v2.0) + nao-financeiras (9.0.3).

Trilha FINANCEIRA (ROTEIRO Secao 2 + Prompt 2 da v2.0):
    FCFE_t = LL_t - ΔCapital Regulatorio Minimo Retido_t
    VT     = FCFE_8 x (1 + g) / (Ke - g)
    Equity = Σ VP(FCFE_t; Ke) + VP(VT; Ke)      [DIRETO, sem bridge EV->Equity]
    Target Price = Equity x fator_escala / acoes fully diluted

Salvaguardas: g >= Ke bloqueia (Gordon explode); FCFE_8 <= 0 usa o payout
sustentavel LL_8 x (1 - g/ROE_8) como base do VT (Damodaran), com aviso.
Consome os blocos ``dre``/``capital_regulatorio`` do ``projetor_financeiro``
e o bloco ``ke`` do ``calculador_wacc.calcular_ke``. O bloco
``valor_terminal`` persiste a taxa tambem sob a chave ``wacc`` por
compatibilidade com o checklist universal (U1/U4) — rotulada como Ke.

Trilha NAO-FINANCEIRA (Prompt 9.0.3.1): ``calcular_fcfe_naofinanceira``
enriquece as linhas do bloco ``fcfe`` (ja calculadas pelo ``calculador_fcff``
como LL + D&A - ΔWK - CAPEX + ΔDivida) com a decomposicao a partir do FCFF
(``FCFE_t = FCFF_t - juros apos IR + receita financeira apos IR + ΔDivida +
residuo de regime tributario/minoritarios``), desconta ao Ke do CAPM Brasil
(``wacc.ke_brl``) e persiste ``fcfe_valuation``: um Equity Value DIRETO que
CONFERE o Equity do bridge FCFF/WACC — divergencia acima do limiar da config
e AVISO, nunca erro (o bridge continua sendo o metodo primario do target).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.projecao.projetor_dre import (
    HORIZONTE_PROJECAO,
    carregar_json,
    formatar_numero,
    formatar_percentual,
    normalizar_ticker,
    resolver_raiz,
    salvar_json,
)
from src.projecao.schedule_divida import obter_float_obrigatorio
from src.valuation.calculador_ev import (
    classificar_recomendacao,
    obter_acoes_fully_diluted,
    obter_fator_escala_moeda,
    obter_preco_atual,
)
from src.valuation.calculador_vt import (
    LIMITE_G_BRL,
    carregar_convencao_desconto,
    expoente_desconto,
)
from src.valuation.calculador_wacc import ler_premissa_numerica

logger = logging.getLogger(__name__)


def carregar_projecao_fcfe(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[Path, dict[str, Any]]:
    """Carrega a projecao financeira e valida os blocos exigidos."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    for bloco in ("dre", "capital_regulatorio", "ke"):
        if not isinstance(conteudo.get(bloco), dict):
            raise RuntimeError(
                f"Bloco obrigatorio ausente em {caminho}: {bloco}. Rode "
                "projetor_financeiro e calcular_ke antes do FCFE."
            )
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        for bloco in ("dre", "capital_regulatorio"):
            if not isinstance(conteudo[bloco].get(chave_ano), dict):
                raise RuntimeError(f"Bloco {bloco} sem {chave_ano} em {caminho}")
    return caminho, conteudo


def calcular_linhas_fcfe(
    conteudo: dict[str, Any],
) -> dict[str, dict[str, float | str]]:
    """FCFE_t = LL_t - ΔCapital Regulatorio_t, com payout implicito."""
    dre = conteudo["dre"]
    capital = conteudo["capital_regulatorio"]
    linhas: dict[str, dict[str, float | str]] = {}
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        lucro = obter_float_obrigatorio(dre[chave_ano], "lucro_liquido", chave_ano)
        delta_capital = obter_float_obrigatorio(
            capital[chave_ano],
            "delta_capital_regulatorio",
            chave_ano,
        )
        # Formula: FCFE = LL - ΔCapital Regulatorio Minimo Retido.
        fcfe = lucro - delta_capital
        payout_implicito = fcfe / lucro if lucro > 0 else None
        linhas[chave_ano] = {
            "ano_projecao": chave_ano,
            "lucro_liquido": lucro,
            "delta_capital_regulatorio": delta_capital,
            "fcfe": fcfe,
            "payout_implicito": payout_implicito,
        }
    return linhas


def calcular_fcfe_financeira(
    ticker: str,
    raiz_projeto: Path | None = None,
    preco_atual: float | None = None,
    acoes_fully_diluted: float | None = None,
    fator_escala_moeda: float | None = None,
) -> dict[str, Any]:
    """Executa o valuation FCFE/Ke e persiste valor_terminal + ev_equity."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    caminho, conteudo = carregar_projecao_fcfe(ticker_normalizado, raiz)
    premissas = carregar_json(
        raiz / "data" / "premissas" / f"{ticker_normalizado}_premissas.json"
    )

    ke = obter_float_obrigatorio(conteudo["ke"], "ke_brl", "ke")
    g = ler_premissa_numerica(
        premissas,
        ("crescimento_perpetuidade", "crescimento_perpetuidade_g"),
    )
    if g >= ke:
        raise ValueError(
            f"g ({g:.2%}) >= Ke ({ke:.2%}): perpetuidade de Gordon explode. "
            "Reduza g ou reveja o Ke."
        )
    if g > LIMITE_G_BRL:
        logger.warning(
            "g=%.2f%% acima de 5%% nominal BRL; justifique com o crescimento "
            "de longo prazo da economia.",
            g * 100,
        )

    fcfe = calcular_linhas_fcfe(conteudo)
    conteudo["fcfe"] = fcfe

    convencao = carregar_convencao_desconto(raiz)
    soma_vp_fcfe = 0.0
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        fluxo = float(fcfe[f"ano{ano}"]["fcfe"])
        # Formula: VP(FCFE_t) = FCFE_t / (1 + Ke)^t (convencao configuravel).
        soma_vp_fcfe += fluxo / (1 + ke) ** expoente_desconto(ano, convencao)

    fcfe_ano8 = float(fcfe["ano8"]["fcfe"])
    lucro_ano8 = float(fcfe["ano8"]["lucro_liquido"])
    roe_ano8 = conteudo["capital_regulatorio"]["ano8"].get("roe_projetado")

    if fcfe_ano8 > 0:
        base_vt = fcfe_ano8
        origem_base = "fcfe_ano8"
    else:
        # Payout sustentavel de Damodaran: b = g/ROE -> payout = 1 - g/ROE.
        if not isinstance(roe_ano8, (int, float)) or roe_ano8 <= g:
            raise ValueError(
                "FCFE do ano 8 nao positivo e ROE terminal <= g: nao ha "
                "base de perpetuidade sustentavel. Reveja crescimento e "
                "capital regulatorio."
            )
        base_vt = lucro_ano8 * (1 - g / float(roe_ano8))
        origem_base = "payout_sustentavel_ll8"
        logger.warning("FCFE ano 8 <= 0; VT usa payout sustentavel LL8 x (1 - g/ROE8).")

    # Formula: VT = base x (1 + g) / (Ke - g); VP no expoente do ano 8.
    vt_bruto = base_vt * (1 + g) / (ke - g)
    vp_vt = vt_bruto / (1 + ke) ** expoente_desconto(HORIZONTE_PROJECAO, convencao)

    equity_value = soma_vp_fcfe + vp_vt
    pct_perpetuidade = vp_vt / equity_value if equity_value != 0 else None

    acoes = obter_acoes_fully_diluted(
        premissas,
        ticker_normalizado,
        raiz,
        acoes_fully_diluted,
    )
    if fator_escala_moeda is None:
        fator_escala_moeda = obter_fator_escala_moeda(ticker_normalizado, raiz)
    equity_absoluto = equity_value * fator_escala_moeda
    target_price = equity_absoluto / acoes
    preco = obter_preco_atual(premissas, ticker_normalizado, raiz, preco_atual)
    upside = target_price / preco - 1
    recomendacao = classificar_recomendacao(upside)

    conteudo["valor_terminal"] = {
        "ticker": ticker_normalizado,
        "g": g,
        # Compatibilidade com o checklist universal (U1/U4): a taxa de
        # desconto da trilha financeira e o Ke, persistido tambem em "wacc".
        "wacc": ke,
        "ke": ke,
        "taxa_desconto_rotulo": "Ke (FCFE, trilha financeira)",
        "usar_convencao_meio_periodo": convencao["usar_convencao_meio_periodo"],
        "fracao_ano_stub": convencao["fracao_ano_stub"],
        "fcfe_ano8": fcfe_ano8,
        "base_vt": origem_base,
        "base_utilizada": base_vt,
        "vt_bruto": vt_bruto,
        "vp_vt": vp_vt,
        "soma_vp_fcfe": soma_vp_fcfe,
        "pct_ev_perpetuidade": pct_perpetuidade,
    }
    conteudo["ev_equity"] = {
        "ticker": ticker_normalizado,
        "metodo_valuation": "fcfe_direto_sem_bridge",
        "soma_vp_fcfe": soma_vp_fcfe,
        "vp_vt": vp_vt,
        "equity_value": equity_value,
        "fator_escala_moeda": fator_escala_moeda,
        "equity_value_absoluto": equity_absoluto,
        "acoes_fully_diluted": acoes,
        "target_price": target_price,
        "preco_atual": preco,
        "upside": upside,
        "recomendacao": recomendacao,
    }
    salvar_json(caminho, conteudo)

    return {
        "ticker": ticker_normalizado,
        "ke": ke,
        "g": g,
        "fcfe": fcfe,
        "valor_terminal": conteudo["valor_terminal"],
        "ev_equity": conteudo["ev_equity"],
        "caminho_saida": caminho,
    }


LIMIAR_DIVERGENCIA_BRIDGE_PADRAO = 0.15


def _carregar_limiar_divergencia(raiz_projeto: Path) -> float:
    """Limiar de aviso da divergencia FCFE vs bridge (config, default 15%)."""
    try:
        parametros = carregar_json(raiz_projeto / "config" / "parametros.json")
    except RuntimeError:
        return LIMIAR_DIVERGENCIA_BRIDGE_PADRAO
    bloco = parametros.get("fcfe_naofinanceira", {})
    valor = bloco.get("limiar_divergencia_vs_bridge")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor <= 0:
        return LIMIAR_DIVERGENCIA_BRIDGE_PADRAO
    return float(valor)


def carregar_projecao_fcfe_naofinanceira(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[Path, dict[str, Any]]:
    """Carrega a projecao integrada e valida os blocos da trilha FCFE NF."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    for bloco in ("dre", "fcff", "fcfe", "divida", "wacc", "ev_equity", "balanco"):
        if not isinstance(conteudo.get(bloco), dict):
            raise RuntimeError(
                f"Bloco obrigatorio ausente em {caminho}: {bloco}. Rode a "
                "cadeia FCFF -> WACC -> VT -> EV antes do FCFE nao-financeira."
            )
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        for bloco in ("fcff", "fcfe", "divida"):
            if not isinstance(conteudo[bloco].get(chave_ano), dict):
                raise RuntimeError(f"Bloco {bloco} sem {chave_ano} em {caminho}")
    return caminho, conteudo


def decompor_fcfe_naofinanceira(conteudo: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Enriquece as linhas do bloco ``fcfe`` com a decomposicao via FCFF.

    Formula (Prompt 9.0.3): FCFE_t = FCFF_t - (juros divida + juros
    arrendamento) x (1 - aliquota_t) + receita financeira x (1 - aliquota_t)
    + ΔDivida_t + residuo. O valor CANONICO de ``fcfe`` segue o ja persistido
    (LL + D&A - ΔWK - CAPEX + ΔDivida); o ``residuo_regime_tributario``
    captura exatamente o que separa as duas formas: RET (IR sobre a receita
    bruta, nao sobre o EBT), IR zerado com EBT <= 0, vetor de aliquota anual
    diferente da aliquota do NOPAT e participacao de minoritarios.
    """
    fcff = conteudo["fcff"]
    fcfe = conteudo["fcfe"]
    divida = conteudo["divida"]
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_fcfe = fcfe[chave_ano]
        linha_fcff = fcff[chave_ano]
        linha_divida = divida[chave_ano]

        valor_fcff = obter_float_obrigatorio(linha_fcff, "fcff", chave_ano)
        aliquota = obter_float_obrigatorio(linha_fcff, "aliquota_ir_nopat", chave_ano)
        juros_divida = obter_float_obrigatorio(linha_divida, "juros", chave_ano)
        juros_arrendamento = float(linha_divida.get("juros_arrendamento") or 0.0)
        receita_financeira = float(linha_divida.get("receita_financeira_caixa") or 0.0)
        delta_divida = obter_float_obrigatorio(linha_fcfe, "delta_divida", chave_ano)
        valor_fcfe = obter_float_obrigatorio(linha_fcfe, "fcfe", chave_ano)

        # Formula: juros apos IR = (juros divida + juros arrendamento) x (1-t).
        juros_apos_ir = (juros_divida + juros_arrendamento) * (1 - aliquota)
        receita_financeira_apos_ir = receita_financeira * (1 - aliquota)
        fcfe_via_fcff = (
            valor_fcff - juros_apos_ir + receita_financeira_apos_ir + delta_divida
        )

        linha_fcfe.update(
            {
                "fcff": valor_fcff,
                "aliquota_fcfe": aliquota,
                "juros_divida": juros_divida,
                "juros_arrendamento": juros_arrendamento,
                "juros_apos_ir": juros_apos_ir,
                "receita_financeira": receita_financeira,
                "receita_financeira_apos_ir": receita_financeira_apos_ir,
                "fcfe_via_fcff": fcfe_via_fcff,
                # Residuo = efeitos de regime tributario (RET, EBT<=0, vetor
                # anual) + minoritarios; zero no caso marginal puro.
                "residuo_regime_tributario": valor_fcfe - fcfe_via_fcff,
            }
        )
    return fcfe


def _roe_terminal_naofinanceira(conteudo: dict[str, Any]) -> float | None:
    """ROE do ano 8 (LL final / PL do balanco projetado), se disponivel."""
    balanco_ano8 = conteudo.get("balanco", {}).get("ano8")
    dre_ano8 = conteudo.get("dre", {}).get("ano8")
    if not isinstance(balanco_ano8, dict) or not isinstance(dre_ano8, dict):
        return None
    patrimonio = balanco_ano8.get("patrimonio_liquido")
    lucro = dre_ano8.get("lucro_liquido")
    if (
        isinstance(patrimonio, bool)
        or not isinstance(patrimonio, (int, float))
        or isinstance(lucro, bool)
        or not isinstance(lucro, (int, float))
        or float(patrimonio) <= 0
    ):
        return None
    # Formula: ROE_8 = LL_8 / PL_8 (base do payout sustentavel de Damodaran).
    return float(lucro) / float(patrimonio)


def calcular_fcfe_naofinanceira(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """FCFE de nao-financeiras descontado ao Ke, conferindo o bridge (9.0.3).

    Enriquece o bloco ``fcfe`` com a decomposicao via FCFF e persiste
    ``fcfe_valuation``: Σ VP(FCFE; Ke) + VP(VT; Ke) = Equity DIRETO, com
    ``ke = wacc.ke_brl`` (CAPM Brasil ja calculado no build-up do WACC) e a
    MESMA convencao de desconto do bridge. Divergencia vs o Equity do bridge
    FCFF/WACC e AVISO (nunca erro): o bridge continua sendo o metodo
    primario do target price. Sem base de perpetuidade viavel (FCFE_8 <= 0 e
    ROE_8 <= g), o valuation e persistido com equity None + aviso — FCFF/LL
    negativos sao validos e nao travam o pipeline.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    caminho, conteudo = carregar_projecao_fcfe_naofinanceira(
        ticker_normalizado,
        raiz,
    )
    premissas = carregar_json(
        raiz / "data" / "premissas" / f"{ticker_normalizado}_premissas.json"
    )

    ke = obter_float_obrigatorio(conteudo["wacc"], "ke_brl", "wacc")
    g = ler_premissa_numerica(
        premissas,
        ("crescimento_perpetuidade", "crescimento_perpetuidade_g"),
    )
    if g >= ke:
        raise ValueError(
            f"g ({g:.2%}) >= Ke ({ke:.2%}): perpetuidade de Gordon explode. "
            "Reduza g ou reveja o Ke."
        )

    fcfe = decompor_fcfe_naofinanceira(conteudo)
    convencao = carregar_convencao_desconto(raiz)
    soma_vp_fcfe = 0.0
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        fluxo = float(fcfe[f"ano{ano}"]["fcfe"])
        # Formula: VP(FCFE_t) = FCFE_t / (1 + Ke)^t (convencao configuravel).
        soma_vp_fcfe += fluxo / (1 + ke) ** expoente_desconto(ano, convencao)

    fcfe_ano8 = float(fcfe["ano8"]["fcfe"])
    lucro_ano8 = float(fcfe["ano8"]["lucro_liquido"])
    roe_ano8 = _roe_terminal_naofinanceira(conteudo)
    aviso: str | None = None

    # Base do VT com ΔDivida NORMALIZADA: perpetuar a amortizacao (ou a
    # captacao) do ano 8 levaria a divida a explodir/ficar negativa. Na
    # perpetuidade a estrutura e estavel e a divida cresce com g
    # (Damodaran): ΔDivida_perp = g x Divida_8.
    delta_divida_8 = float(fcfe["ano8"]["delta_divida"])
    divida_bruta_8 = float(conteudo["divida"]["ano8"].get("divida_bruta") or 0.0)
    delta_divida_perpetuidade = g * divida_bruta_8
    fcfe_ano8_normalizado = fcfe_ano8 - delta_divida_8 + delta_divida_perpetuidade

    if fcfe_ano8_normalizado > 0:
        base_vt: float | None = fcfe_ano8_normalizado
        origem_base = "fcfe_ano8_delta_divida_normalizada"
    elif roe_ano8 is not None and roe_ano8 > g and lucro_ano8 > 0:
        # Payout sustentavel de Damodaran: b = g/ROE -> payout = 1 - g/ROE.
        base_vt = lucro_ano8 * (1 - g / roe_ano8)
        origem_base = "payout_sustentavel_ll8"
        logger.warning(
            "FCFE ano 8 normalizado <= 0 em %s; VT usa payout sustentavel "
            "LL8 x (1 - g/ROE8).",
            ticker_normalizado,
        )
    else:
        base_vt = None
        origem_base = "sem_base_perpetuidade"
        aviso = (
            "FCFE_8 normalizado <= 0 e sem ROE terminal viavel: valuation "
            "FCFE nao computado (checagem secundaria; o bridge FCFF permanece)."
        )
        logger.warning("%s: %s", ticker_normalizado, aviso)

    equity_bridge = float(conteudo["ev_equity"].get("equity_value") or 0.0)
    limiar = _carregar_limiar_divergencia(raiz)

    if base_vt is not None:
        # Formula: VT = base x (1 + g) / (Ke - g); VP no expoente do ano 8.
        vt_bruto = base_vt * (1 + g) / (ke - g)
        vp_vt = vt_bruto / (1 + ke) ** expoente_desconto(HORIZONTE_PROJECAO, convencao)
        equity_fcfe = soma_vp_fcfe + vp_vt
    else:
        vt_bruto = None
        vp_vt = None
        equity_fcfe = None

    divergencia = None
    divergencia_acima_limiar = False
    if equity_fcfe is not None and abs(equity_bridge) > 1e-9:
        # Formula: divergencia = Equity FCFE/Ke / Equity bridge FCFF - 1.
        divergencia = equity_fcfe / equity_bridge - 1
        divergencia_acima_limiar = abs(divergencia) > limiar
        if divergencia_acima_limiar:
            logger.warning(
                "FCFE/Ke diverge do bridge FCFF em %.1f%% (> %.0f%%) para %s: "
                "estruturas de desconto diferentes (Ke unico vs WACC) — "
                "explicar, nao travar.",
                divergencia * 100,
                limiar * 100,
                ticker_normalizado,
            )

    acoes = float(conteudo["ev_equity"].get("acoes_fully_diluted") or 0.0)
    fator_escala = float(conteudo["ev_equity"].get("fator_escala_moeda") or 1.0)
    preco_atual = conteudo["ev_equity"].get("preco_atual")
    target_price_fcfe = None
    if equity_fcfe is not None and acoes > 0:
        target_price_fcfe = equity_fcfe * fator_escala / acoes

    valuation = {
        "ticker": ticker_normalizado,
        "metodo": "fcfe_naofinanceira_ke_capm_brasil",
        "ke": ke,
        "g": g,
        "usar_convencao_meio_periodo": convencao["usar_convencao_meio_periodo"],
        "fracao_ano_stub": convencao["fracao_ano_stub"],
        "soma_vp_fcfe": soma_vp_fcfe,
        "fcfe_ano8": fcfe_ano8,
        "fcfe_ano8_normalizado": fcfe_ano8_normalizado,
        "delta_divida_perpetuidade": delta_divida_perpetuidade,
        "base_vt": origem_base,
        "base_utilizada": base_vt,
        "roe_terminal": roe_ano8,
        "vt_bruto": vt_bruto,
        "vp_vt": vp_vt,
        "equity_value_fcfe": equity_fcfe,
        "target_price_fcfe": target_price_fcfe,
        "equity_value_bridge": equity_bridge,
        "divergencia_vs_bridge": divergencia,
        "limiar_divergencia": limiar,
        "divergencia_acima_limiar": divergencia_acima_limiar,
        "preco_atual": preco_atual,
        "aviso": aviso,
    }

    conteudo["fcfe"] = fcfe
    conteudo["fcfe_valuation"] = valuation
    salvar_json(caminho, conteudo)

    return {
        "ticker": ticker_normalizado,
        "fcfe": fcfe,
        "fcfe_valuation": valuation,
        "caminho_saida": caminho,
    }


def imprimir_fcfe_naofinanceira(resultado: dict[str, Any]) -> None:
    """Imprime o FCFE nao-financeira e a checagem contra o bridge."""
    valuation = resultado["fcfe_valuation"]
    print("\n" + "=" * 72)
    print(f"FCFE nao-financeira (checagem do bridge) - {resultado['ticker']}")
    print(
        f"Ke = {formatar_percentual(valuation['ke'])} | "
        f"g = {formatar_percentual(valuation['g'])} | base VT: "
        f"{valuation['base_vt']}"
    )
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        linha = resultado["fcfe"][f"ano{ano}"]
        print(
            f"  ano{ano}: FCFF={formatar_numero(float(linha['fcff'])):>15} | "
            f"FCFE={formatar_numero(float(linha['fcfe'])):>15} | "
            f"ΔDivida={formatar_numero(float(linha['delta_divida'])):>15}"
        )
    equity_fcfe = valuation["equity_value_fcfe"]
    if equity_fcfe is None:
        print(f"  {valuation['aviso']}")
        return
    print(
        f"  Equity FCFE/Ke : R$ {formatar_numero(equity_fcfe)} | "
        f"Equity bridge: R$ {formatar_numero(valuation['equity_value_bridge'])}"
    )
    divergencia = valuation["divergencia_vs_bridge"]
    if divergencia is not None:
        marcador = " (AVISO)" if valuation["divergencia_acima_limiar"] else ""
        print(f"  Divergencia    : {formatar_percentual(divergencia)}{marcador}")


def imprimir_fcfe(resultado: dict[str, Any]) -> None:
    """Imprime o valuation FCFE para validacao visual."""
    print("\n" + "=" * 72)
    print(f"Valuation FCFE/Ke - {resultado['ticker']}")
    print(
        f"Ke = {formatar_percentual(resultado['ke'])} | "
        f"g = {formatar_percentual(resultado['g'])}"
    )
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        linha = resultado["fcfe"][f"ano{ano}"]
        print(
            f"  ano{ano}: LL={formatar_numero(float(linha['lucro_liquido'])):>15} | "
            f"ΔCapital={formatar_numero(float(linha['delta_capital_regulatorio'])):>15}"
            f" | FCFE={formatar_numero(float(linha['fcfe'])):>15}"
        )
    ev_equity = resultado["ev_equity"]
    print(
        f"  Equity: R$ {formatar_numero(ev_equity['equity_value'])} | "
        f"Target: R$ {formatar_numero(ev_equity['target_price'])} | "
        f"Upside: {formatar_percentual(ev_equity['upside'])} "
        f"({ev_equity['recomendacao']})"
    )


def main() -> None:
    """Executa o valuation FCFE para ITUB4 e BBAS3."""
    for ticker in ("ITUB4", "BBAS3"):
        try:
            imprimir_fcfe(calcular_fcfe_financeira(ticker))
        except (RuntimeError, ValueError) as erro:
            print(f"Falha no FCFE de {ticker}: {erro}")


if __name__ == "__main__":
    main()
