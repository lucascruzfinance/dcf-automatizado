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
EPSILON = 1e-12


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
    """Define aliquota do NOPAT, evitando dupla tributacao em construtoras RET.

    Aliquota MARGINAL (34% IR/CSLL) por decisao documentada: a aliquota
    efetiva historica (que embute impostos diferidos, JCP e beneficios
    fiscais) fica exposta nas metricas historicas como ancora; o analista
    pode sobrescreve-la nas premissas quando a diferenca for estrutural.
    Construtoras RET usam 0% aqui porque o IR ja foi cobrado sobre a
    receita bruta na DRE (evita dupla tributacao no NOPAT).
    """
    premissas = carregar_premissas(ticker, raiz_projeto)
    metadados = carregar_metadados(ticker, raiz_projeto)
    if empresa_usa_ret(premissas, metadados):
        return 0.0
    return ALIQUOTA_IR_GERAL


def _obter_float_opcional(
    dados: dict[str, Any],
    campo: str,
    padrao: float = 0.0,
) -> float:
    """Le campo numerico opcional sem aceitar booleano como numero."""
    valor = dados.get(campo)
    if valor is None:
        return padrao
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"Campo numerico opcional invalido: {campo}")
    return float(valor)


def _calcular_capital_giro_roic(linha_wk: dict[str, Any]) -> float:
    """Calcula o capital de giro usado no ROIC conforme contrato analitico.

    Formula: WC = Estoques + Contas a Receber - Fornecedores - obrigacoes
    sociais/trabalhistas. A ultima linha ainda nao e projetada no schedule
    atual; quando ausente, entra como zero de forma explicita.
    """
    contas_receber = obter_float_obrigatorio(
        linha_wk,
        "contas_receber",
        str(linha_wk.get("ano_projecao", "wk")),
    )
    estoques = obter_float_obrigatorio(
        linha_wk,
        "estoques",
        str(linha_wk.get("ano_projecao", "wk")),
    )
    fornecedores = obter_float_obrigatorio(
        linha_wk,
        "fornecedores",
        str(linha_wk.get("ano_projecao", "wk")),
    )
    obrigacoes_sociais = _obter_float_opcional(
        linha_wk,
        "obrigacoes_sociais_trabalhistas",
        0.0,
    )
    return contas_receber + estoques - abs(fornecedores) - abs(obrigacoes_sociais)


def _capital_investido_ano0(conteudo: dict[str, Any]) -> float | None:
    """Calcula IC do ano 0 quando os blocos historicos existem."""
    ano0 = conteudo.get("ano0")
    if not isinstance(ano0, dict):
        return None
    wk = ano0.get("wk")
    ppe = ano0.get("ppe")
    if not isinstance(wk, dict) or not isinstance(ppe, dict):
        return None

    capital_giro = _calcular_capital_giro_roic(wk)
    imobilizado = obter_float_obrigatorio(ppe, "imobilizado", "ano0.ppe")
    intangivel = _obter_float_opcional(ppe, "intangivel", 0.0)
    # Formula: IC = Working Capital + PP&E + Intangivel.
    return capital_giro + imobilizado + intangivel


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
    capital_investido_por_ano: dict[int, float] = {}
    capital_investido_inicial = _capital_investido_ano0(conteudo)
    if capital_investido_inicial is not None:
        capital_investido_por_ano[0] = capital_investido_inicial
    nopat_por_ano: dict[int, float] = {}

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
        capital_giro = _calcular_capital_giro_roic(wk[chave_ano])
        imobilizado = obter_float_obrigatorio(ppe[chave_ano], "imobilizado", chave_ano)
        intangivel = _obter_float_opcional(ppe[chave_ano], "intangivel", 0.0)
        # Formula: IC = Working Capital + PP&E + Intangivel.
        capital_investido = capital_giro + imobilizado + intangivel
        # Formula: ROIC = NOPAT / IC.
        roic = None if abs(capital_investido) < EPSILON else nopat / capital_investido

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
            "capital_giro_operacional": capital_giro,
            "imobilizado": imobilizado,
            "intangivel": intangivel,
            "capital_investido": capital_investido,
            "roic": roic,
            "roiic": None,
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
        capital_investido_por_ano[ano] = capital_investido
        nopat_por_ano[ano] = nopat

    for ano in range(2, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        if (
            ano - 1 not in capital_investido_por_ano
            or ano - 2 not in capital_investido_por_ano
        ):
            fcff[chave_ano]["roiic"] = None
            continue
        delta_capital_previo = (
            capital_investido_por_ano[ano - 1] - capital_investido_por_ano[ano - 2]
        )
        if abs(delta_capital_previo) < EPSILON:
            roiic = None
        else:
            # Formula: ROIIC_t = Delta NOPAT_t / Delta IC_(t-1).
            # O denominador usa o capital comprometido no periodo anterior.
            roiic = (nopat_por_ano[ano] - nopat_por_ano[ano - 1]) / delta_capital_previo
        fcff[chave_ano]["roiic"] = roiic

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
    cabecalho = (
        f"{'Ano':<6} {'NOPAT':>18} {'ROIC':>10} {'ROIIC':>10} "
        f"{'FCFF':>18} {'FCFE':>18}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        roic = resultado["fcff"][chave_ano].get("roic")
        roiic = resultado["fcff"][chave_ano].get("roiic")
        texto_roic = f"{float(roic):.1%}" if roic is not None else "n/d"
        texto_roiic = f"{float(roiic):.1%}" if roiic is not None else "n/d"
        print(
            f"{chave_ano:<6} "
            f"{formatar_numero(float(resultado['fcff'][chave_ano]['nopat'])):>18} "
            f"{texto_roic:>10} "
            f"{texto_roiic:>10} "
            f"{formatar_numero(float(resultado['fcff'][chave_ano]['fcff'])):>18} "
            f"{formatar_numero(float(resultado['fcfe'][chave_ano]['fcfe'])):>18}"
        )


def main() -> None:
    """Executa o calculo padrao para DIRR3."""
    imprimir_tabela_fcff(calcular_fcff("DIRR3"))


if __name__ == "__main__":
    main()
