"""Calculador de FCFF e FCFE projetados."""

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
        carregar_metadados,
        empresa_usa_ret,
        formatar_numero,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        formatar_numero,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio

ALIQUOTA_IR_GERAL = 0.34


def validar_bloco_anual(
    conteudo: dict[str, Any],
    caminho: Path,
    bloco: str,
) -> None:
    """Valida que um bloco da projecao integrada traz os 8 anos esperados."""
    dados_bloco = conteudo.get(bloco)
    if not isinstance(dados_bloco, dict):
        raise RuntimeError(f"Bloco obrigatorio ausente em {caminho}: {bloco}")

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        if not isinstance(dados_bloco.get(chave_ano), dict):
            raise RuntimeError(f"Bloco {bloco} sem {chave_ano} em {caminho}")


def carregar_projecao_fcff(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[Path, dict[str, Any]]:
    """Carrega a projecao integrada que alimenta o FCFF."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    for bloco in ("dre", "wk", "ppe", "divida"):
        validar_bloco_anual(conteudo, caminho, bloco)
    return caminho, conteudo


def carregar_premissas(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega premissas para detectar regra tributaria RET."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    return carregar_json(caminho)


def obter_aliquota_nopat(ticker: str, raiz_projeto: Path) -> float:
    """Define aliquota do NOPAT, evitando dupla tributacao em construtoras RET."""
    premissas = carregar_premissas(ticker, raiz_projeto)
    metadados = carregar_metadados(ticker, raiz_projeto)
    if empresa_usa_ret(premissas, metadados):
        return 0.0
    return ALIQUOTA_IR_GERAL


def calcular_linhas_fcff(
    conteudo: dict[str, Any],
    aliquota_ir: float,
) -> tuple[dict[str, dict[str, float | str]], dict[str, dict[str, float | str]]]:
    """Calcula FCFF e FCFE por ano.

    Formulas:
    NOPAT = EBIT x (1 - aliquota_ir)
    FCFF = NOPAT + D&A - Delta NWC - abs(CAPEX)
    FCFE = lucro_liquido + D&A - Delta NWC - abs(CAPEX) + Delta Divida
    """
    dre = conteudo["dre"]
    wk = conteudo["wk"]
    ppe = conteudo["ppe"]
    divida = conteudo["divida"]
    fcff = {}
    fcfe = {}

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        ebit = obter_float_obrigatorio(dre[chave_ano], "ebit", chave_ano)
        depreciacao = obter_float_obrigatorio(
            dre[chave_ano],
            "depreciacao_amortizacao",
            chave_ano,
        )
        lucro_liquido = obter_float_obrigatorio(
            dre[chave_ano],
            "lucro_liquido",
            chave_ano,
        )
        delta_nwc = obter_float_obrigatorio(wk[chave_ano], "delta_nwc", chave_ano)
        capex = obter_float_obrigatorio(ppe[chave_ano], "capex", chave_ano)
        delta_divida = obter_float_obrigatorio(
            divida[chave_ano],
            "delta_divida",
            chave_ano,
        )

        # Formula: NOPAT = EBIT x (1 - aliquota_ir).
        nopat = ebit * (1 - aliquota_ir)
        capex_saida_caixa = abs(capex)

        # Formula: FCFF = NOPAT + D&A - Delta NWC - CAPEX.
        # Delta NWC positivo representa consumo de caixa no projeto.
        valor_fcff = nopat + depreciacao - delta_nwc - capex_saida_caixa

        # Formula: FCFE = LL + D&A - Delta NWC - CAPEX + Delta Divida.
        # Delta NWC positivo tambem reduz o fluxo ao acionista.
        valor_fcfe = (
            lucro_liquido + depreciacao - delta_nwc - capex_saida_caixa + delta_divida
        )

        fcff[chave_ano] = {
            "ano_projecao": chave_ano,
            "aliquota_ir_nopat": aliquota_ir,
            "nopat": nopat,
            "depreciacao_amortizacao": depreciacao,
            "delta_nwc": delta_nwc,
            "capex": capex,
            "capex_saida_caixa": capex_saida_caixa,
            "fcff": valor_fcff,
        }
        fcfe[chave_ano] = {
            "ano_projecao": chave_ano,
            "lucro_liquido": lucro_liquido,
            "depreciacao_amortizacao": depreciacao,
            "delta_nwc": delta_nwc,
            "capex": capex,
            "capex_saida_caixa": capex_saida_caixa,
            "delta_divida": delta_divida,
            "fcfe": valor_fcfe,
        }

    return fcff, fcfe


def calcular_fcff(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Calcula e persiste os blocos fcff e fcfe da projecao integrada."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    caminho, conteudo = carregar_projecao_fcff(ticker_normalizado, raiz)
    aliquota_ir = obter_aliquota_nopat(ticker_normalizado, raiz)
    fcff, fcfe = calcular_linhas_fcff(conteudo, aliquota_ir)
    conteudo["fcff"] = fcff
    conteudo["fcfe"] = fcfe
    salvar_json(caminho, conteudo)
    return {
        "ticker": ticker_normalizado,
        "aliquota_ir_nopat": aliquota_ir,
        "fcff": fcff,
        "fcfe": fcfe,
        "caminho_saida": caminho,
    }


def imprimir_tabela_fcff(resultado: dict[str, Any]) -> None:
    """Imprime FCFF e FCFE projetados para validacao visual."""
    print("\n" + "=" * 120)
    print(
        f"FCFF / FCFE - {resultado['ticker']} | "
        f"aliquota NOPAT={resultado['aliquota_ir_nopat']:.2%}"
    )
    cabecalho = f"{'Ano':<6} {'NOPAT':>18} {'FCFF':>18} {'FCFE':>18}"
    print(cabecalho)
    print("-" * len(cabecalho))
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        print(
            f"{chave_ano:<6} "
            f"{formatar_numero(float(resultado['fcff'][chave_ano]['nopat'])):>18} "
            f"{formatar_numero(float(resultado['fcff'][chave_ano]['fcff'])):>18} "
            f"{formatar_numero(float(resultado['fcfe'][chave_ano]['fcfe'])):>18}"
        )


def main() -> None:
    """Executa o calculo padrao para DIRR3."""
    imprimir_tabela_fcff(calcular_fcff("DIRR3"))


if __name__ == "__main__":
    main()
