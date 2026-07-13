"""Valuation FCFE/Ke para a trilha financeira (v2.0, Onda 2).

Formulas (ROTEIRO Secao 2 + Prompt 2 da v2.0):
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
