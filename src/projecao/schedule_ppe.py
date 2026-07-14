"""Schedule de PP&E e devolucao de D&A para a DRE projetada."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

try:
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        calcular_ir_csll,
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        formatar_numero,
        formatar_percentual,
        normalizar_ticker,
        normalizar_valor_json,
        resolver_raiz,
        salvar_json,
        selecionar_ultimo_exercicio,
        valor_numerico_obrigatorio,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from projetor_dre import (
        HORIZONTE_PROJECAO,
        calcular_ir_csll,
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        formatar_numero,
        formatar_percentual,
        normalizar_ticker,
        normalizar_valor_json,
        resolver_raiz,
        salvar_json,
        selecionar_ultimo_exercicio,
        valor_numerico_obrigatorio,
    )

CAMPO_VIDA_UTIL_PPE = "vida_util_ppe_anos"
CAPEX_EXPANSAO_PCT_PADRAO = 0.80
VIDA_UTIL_MIN_PADRAO = 3.0
VIDA_UTIL_MAX_PADRAO = 30.0


def obter_float_obrigatorio(
    dados: dict[str, Any],
    campo: str,
    contexto: str,
) -> float:
    """Le campo numerico obrigatorio de um dicionario de projecao."""
    valor = dados.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"Campo numerico obrigatorio invalido: {contexto}.{campo}")
    return float(valor)


def carregar_parametros_ppe(raiz_projeto: Path) -> dict[str, float]:
    """Carrega parametros globais usados pelo schedule PP&E (com safras 8.2)."""
    caminho = raiz_projeto / "config" / "parametros.json"
    parametros = carregar_json(caminho)
    valor = parametros.get(CAMPO_VIDA_UTIL_PPE)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"Parametro obrigatorio invalido: {CAMPO_VIDA_UTIL_PPE}")

    vida_util_anos = float(valor)
    if vida_util_anos <= 0:
        raise ValueError(f"Parametro precisa ser positivo: {CAMPO_VIDA_UTIL_PPE}")

    safras = parametros.get("ppe_safras", {})
    return {
        "vida_util_ppe_anos": vida_util_anos,
        "taxa_depreciacao_ppe": 1 / vida_util_anos,
        "vida_util_min_anos": float(safras.get("vida_util_min_anos", VIDA_UTIL_MIN_PADRAO)),
        "vida_util_max_anos": float(safras.get("vida_util_max_anos", VIDA_UTIL_MAX_PADRAO)),
        "capex_expansao_pct_padrao": float(
            safras.get("capex_expansao_pct_padrao", CAPEX_EXPANSAO_PCT_PADRAO)
        ),
    }


def derivar_vida_util(
    imobilizado_ano0: float,
    da_historica_ano0: float,
    parametros: dict[str, float],
) -> tuple[float, str]:
    """Vida util DERIVADA do historico: PP&E / D&A, clampada (Smartfit L339).

    Devolve ``(vida, origem)``. Sem D&A historica confiavel, cai na
    ``vida_util_ppe_anos`` da config (comportamento v2), tambem clampada.
    """
    minimo = parametros["vida_util_min_anos"]
    maximo = parametros["vida_util_max_anos"]
    if da_historica_ano0 > 0 and imobilizado_ano0 > 0:
        # Formula: vida util = PP&E / D&A (numero de anos implicito).
        vida = imobilizado_ano0 / da_historica_ano0
        return max(minimo, min(maximo, vida)), "derivada_pp&e/d&a"
    vida_config = parametros["vida_util_ppe_anos"]
    return max(minimo, min(maximo, vida_config)), "config_vida_util_ppe_anos"


def carregar_premissas_ppe(ticker: str, raiz_projeto: Path) -> dict[int, float]:
    """Carrega as oito premissas anuais obrigatorias de CAPEX/Receita."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    premissas = carregar_json(caminho)
    taxas_capex = {}

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        campo = f"capex_receita_ano{ano}"
        taxas_capex[ano] = valor_numerico_obrigatorio(premissas, campo)

    return taxas_capex


def carregar_premissas_completas(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega o arquivo integral de premissas para regras tributarias."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    return carregar_json(caminho)


def carregar_projecao_existente(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[Path, dict[str, Any], dict[str, dict[str, Any]]]:
    """Carrega a estrutura de projecao ja gerada pela DRE."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    dre = conteudo.get("dre")
    if not isinstance(dre, dict):
        raise RuntimeError(f"Projecao DRE ausente ou invalida em {caminho}")

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        if chave_ano not in dre or not isinstance(dre[chave_ano], dict):
            raise RuntimeError(f"DRE projetada sem {chave_ano} em {caminho}")

        linha = dre[chave_ano]
        obter_float_obrigatorio(linha, "receita_liquida", chave_ano)
        obter_float_obrigatorio(linha, "ebitda", chave_ano)
        obter_float_obrigatorio(linha, "resultado_financeiro", chave_ano)

    return caminho, conteudo, dre


def carregar_quadro_cvm(caminho: Path) -> pd.DataFrame:
    """Carrega JSON bruto da CVM em DataFrame validando estrutura minima."""
    registros = carregar_json(caminho)
    dados = pd.DataFrame(registros)
    if dados.empty:
        raise RuntimeError(f"Base historica vazia: {caminho}")
    return dados


def _valor_opcional_ano0(dados: pd.DataFrame, nome: str, padrao: float = 0.0) -> float:
    """Valor do Ano 0 para uma conta opcional; ausente vira o padrao."""
    try:
        linha = selecionar_ultimo_exercicio(dados, nome)
    except RuntimeError:
        return padrao
    valor = linha["valor_padronizado"]
    return float(valor) if pd.notna(valor) else padrao


def carregar_da_historica_ano0(ticker: str, raiz_projeto: Path) -> float:
    """|D&A| historica do Ano 0 via DFC (base da vida util derivada)."""
    caminho = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_dfc.json"
    if not caminho.exists():
        return 0.0
    dados = pd.DataFrame(carregar_json(caminho))
    if dados.empty:
        return 0.0
    return abs(_valor_opcional_ano0(dados, "depreciacao_amortizacao"))


def carregar_ano0_ppe(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega imobilizado, intangivel e D&A historicos do ultimo exercicio."""
    caminho = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_bp.json"
    dados = carregar_quadro_cvm(caminho)
    linha = selecionar_ultimo_exercicio(dados, "imobilizado")
    imobilizado = float(linha["valor_padronizado"])
    if imobilizado < 0:
        raise RuntimeError(
            f"Imobilizado historico negativo para {ticker}: {imobilizado}"
        )
    intangivel = max(_valor_opcional_ano0(dados, "intangivel"), 0.0)
    da_historica = carregar_da_historica_ano0(ticker, raiz_projeto)

    return {
        "fonte": str(caminho.relative_to(raiz_projeto)),
        "ano_arquivo": normalizar_valor_json(linha.get("ano_arquivo")),
        "data_exercicio": normalizar_valor_json(linha.get("DT_FIM_EXERC")),
        "ordem_exercicio": normalizar_valor_json(linha.get("ORDEM_EXERC")),
        "imobilizado": imobilizado,
        "intangivel": intangivel,
        "da_historica": da_historica,
    }


def calcular_depreciacao_amortizacao(
    imobilizado_anterior: float,
    capex: float,
    taxa_depreciacao: float,
) -> float:
    """Calcula D&A sem permitir depreciacao abaixo de zero.

    O CAPEX chega ASSINADO (negativo = saida de caixa, convencao do
    projeto); como INVESTIMENTO no ativo vale a magnitude. Correcao da
    v2.0: na v1 o capex assinado era somado ao PP&E, encolhendo o ativo, e
    o caixa-plug absorvia a inconsistencia silenciosamente.
    """
    investimento = abs(capex)
    base_disponivel = max(imobilizado_anterior + investimento, 0.0)

    # Formula: D&A_t = min(taxa x PP&E_(t-1), PP&E_(t-1) + |CAPEX_t|).
    # O min impede depreciar mais do que existe de base; o max final impede
    # D&A negativa.
    depreciacao = min(taxa_depreciacao * imobilizado_anterior, base_disponivel)
    return max(depreciacao, 0.0)


def carregar_capex_expansao_pcts(
    premissas: dict[str, Any],
    padrao: float,
) -> dict[int, float]:
    """Le a parcela de capex em expansao por ano (opcional; default 80%)."""
    pcts: dict[int, float] = {}
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        valor = premissas.get(f"capex_expansao_pct_ano{ano}")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            pcts[ano] = max(0.0, min(1.0, float(valor)))
        else:
            pcts[ano] = max(0.0, min(1.0, padrao))
    return pcts


def projetar_linhas_ppe(
    dre: dict[str, dict[str, Any]],
    taxas_capex_receita: dict[int, float],
    capex_expansao_pcts: dict[int, float],
    imobilizado_ano0: float,
    intangivel_ano0: float,
    vida_util: float,
    vida_util_intangivel: float,
) -> dict[str, dict[str, float | str]]:
    """Projeta CAPEX, D&A POR SAFRA e PP&E de ano1 a ano8 (Prompt 8.2).

    D&A do imobilizado = depreciacao do estoque EXISTENTE (linear ate zerar) +
    depreciacao das SAFRAS de capex (meia-quota no ano da safra, ``MIN(quota,
    saldo)`` nos anos seguintes — para quando a safra zera). Intangivel:
    amortizacao linear do saldo do Ano 0. Capex split expansao x manutencao.
    """
    linhas = {}
    quota_existente = imobilizado_ano0 / vida_util if vida_util > 0 else 0.0
    saldo_existente = imobilizado_ano0
    quota_intangivel = (
        intangivel_ano0 / vida_util_intangivel if vida_util_intangivel > 0 else 0.0
    )
    saldo_intangivel = intangivel_ano0
    safras: list[dict[str, float]] = []
    imobilizado_anterior = imobilizado_ano0

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_dre = dre[chave_ano]
        receita_liquida = obter_float_obrigatorio(
            linha_dre,
            "receita_liquida",
            chave_ano,
        )
        capex_receita = taxas_capex_receita[ano]
        # Formula: CAPEX_t = capex_receita_ano_t x Receita_t.
        capex = capex_receita * receita_liquida
        capex_abs = abs(capex)

        # Estoque existente do Ano 0: linear ate zerar (MIN(quota, saldo)).
        dep_existente = min(quota_existente, saldo_existente)
        saldo_existente = max(saldo_existente - dep_existente, 0.0)

        # Safras anteriores: quota cheia, parando no saldo remanescente.
        dep_safras = 0.0
        for safra in safras:
            quota_dep = min(safra["quota"], safra["saldo"])
            safra["saldo"] = max(safra["saldo"] - quota_dep, 0.0)
            dep_safras += quota_dep

        # Safra NOVA deste ano: meia-depreciacao (Smartfit L344).
        quota_nova = capex_abs / vida_util if vida_util > 0 else 0.0
        dep_nova = min(quota_nova / 2, capex_abs)
        safras.append({"quota": quota_nova, "saldo": max(capex_abs - dep_nova, 0.0)})
        dep_safras += dep_nova

        da_imobilizado = dep_existente + dep_safras

        # Intangivel: amortizacao linear do saldo do Ano 0.
        da_intangivel = min(quota_intangivel, saldo_intangivel)
        saldo_intangivel = max(saldo_intangivel - da_intangivel, 0.0)

        # Formula: PP&E_t = PP&E_(t-1) + |CAPEX_t| - D&A_imobilizado_t.
        imobilizado = max(imobilizado_anterior + capex_abs - da_imobilizado, 0.0)

        # Capex split expansao x manutencao (informativo; capex total inalterado).
        exp_pct = capex_expansao_pcts[ano]
        capex_expansao = capex * exp_pct
        capex_manutencao = capex - capex_expansao

        linhas[chave_ano] = {
            "ano_projecao": chave_ano,
            "capex_receita": capex_receita,
            "capex": capex,
            "capex_expansao_pct": exp_pct,
            "capex_expansao": capex_expansao,
            "capex_manutencao": capex_manutencao,
            "da_imobilizado_existente": dep_existente,
            "da_imobilizado_safras": dep_safras,
            "da_imobilizado": da_imobilizado,
            "da_intangivel": da_intangivel,
            # depreciacao_amortizacao aqui = imobilizado + intangivel; o
            # schedule de leasing soma da_direito_uso depois (ordem do chain).
            "depreciacao_amortizacao": da_imobilizado + da_intangivel,
            "imobilizado": imobilizado,
            "intangivel": saldo_intangivel,
        }
        imobilizado_anterior = imobilizado

    return linhas


def _da_memo_completa(linha_dre: dict[str, Any], depreciacao: float) -> float:
    """D&A total do memo no modo completo = imobilizado + direito uso + intang.

    No modo completo a D&A ja esta embutida em CPV/SG&A (o EBIT sai direto das
    margens); esta funcao devolve a D&A TOTAL do memo, usando a depreciacao do
    imobilizado recem-calculada pelo schedule PP&E e mantendo as demais
    componentes (direito de uso, intangivel) como estao (zeradas ate o 8.2).
    """
    da_direito_uso = float(linha_dre.get("da_direito_uso") or 0.0)
    da_intangivel = float(linha_dre.get("da_intangivel") or 0.0)
    return depreciacao + da_direito_uso + da_intangivel


def atualizar_dre_com_depreciacao(
    dre: dict[str, dict[str, Any]],
    ppe: dict[str, dict[str, float | str]],
    usa_ret: bool,
    modo_dre: str = "legado",
) -> None:
    """Fecha a D&A da DRE com a serie do schedule PP&E.

    Modo LEGADO: EBIT = EBITDA - D&A e recalcula EBT/IR/LL (a D&A reduz o
    lucro). Modo COMPLETO (Padrao Smartfit): a D&A ja esta embutida em
    CPV/SG&A, entao o EBIT permanece fixo e apenas a D&A do imobilizado e o
    EBITDA (= EBIT + D&A total) sao atualizados — EBT/IR/LL nao mudam aqui.
    """
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_dre = dre[chave_ano]
        linha_ppe = ppe[chave_ano]
        depreciacao = obter_float_obrigatorio(
            linha_ppe,
            "depreciacao_amortizacao",
            chave_ano,
        )

        if modo_dre == "completo":
            ebit = obter_float_obrigatorio(linha_dre, "ebit", chave_ano)
            da_total = _da_memo_completa(linha_dre, depreciacao)
            linha_dre["da_imobilizado"] = depreciacao
            linha_dre["depreciacao_amortizacao"] = da_total
            # Formula: EBITDA = EBIT + D&A total (EBIT ja e apos D&A embutida).
            linha_dre["ebitda"] = ebit + da_total
            continue

        receita_liquida = obter_float_obrigatorio(
            linha_dre,
            "receita_liquida",
            chave_ano,
        )
        ebitda = obter_float_obrigatorio(linha_dre, "ebitda", chave_ano)
        resultado_financeiro = obter_float_obrigatorio(
            linha_dre,
            "resultado_financeiro",
            chave_ano,
        )

        # Fecha o laco com o Prompt 1: a DRE deixa de usar o placeholder de
        # D&A e passa a receber a serie calculada pelo schedule PP&E.
        linha_dre["depreciacao_amortizacao"] = depreciacao
        linha_dre["ebit"] = ebitda - depreciacao
        linha_dre["ebt"] = linha_dre["ebit"] + resultado_financeiro
        linha_dre["ir_csll"] = calcular_ir_csll(
            ebt=float(linha_dre["ebt"]),
            receita_liquida=receita_liquida,
            usa_ret=usa_ret,
        )
        linha_dre["lucro_liquido"] = linha_dre["ebt"] + linha_dre["ir_csll"]


def atualizar_projecao_ppe(
    caminho: Path,
    conteudo: dict[str, Any],
    ano0_ppe: dict[str, Any],
    ppe: dict[str, dict[str, float | str]],
) -> None:
    """Grava o schedule PP&E dentro da estrutura unica de projecao."""
    ano0 = conteudo.get("ano0")
    if not isinstance(ano0, dict):
        ano0 = {}
    ano0["ppe"] = ano0_ppe
    conteudo["ano0"] = ano0
    conteudo["ppe"] = ppe
    salvar_json(caminho, conteudo)


def projetar_ppe(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Executa o schedule PP&E e persiste a D&A recalculada na DRE."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    parametros = carregar_parametros_ppe(raiz)
    taxas_capex_receita = carregar_premissas_ppe(ticker_normalizado, raiz)
    premissas_completas = carregar_premissas_completas(ticker_normalizado, raiz)
    metadados = carregar_metadados(ticker_normalizado, raiz)
    caminho_projecao, conteudo, dre = carregar_projecao_existente(
        ticker_normalizado,
        raiz,
    )
    ano0_ppe = carregar_ano0_ppe(ticker_normalizado, raiz)
    modo_dre = str(conteudo.get("modo_dre", "legado"))
    ppe = projetar_linhas_ppe(
        dre=dre,
        taxas_capex_receita=taxas_capex_receita,
        imobilizado_ano0=float(ano0_ppe["imobilizado"]),
        taxa_depreciacao=parametros["taxa_depreciacao_ppe"],
    )
    atualizar_dre_com_depreciacao(
        dre=dre,
        ppe=ppe,
        usa_ret=empresa_usa_ret(premissas_completas, metadados),
        modo_dre=modo_dre,
    )
    atualizar_projecao_ppe(caminho_projecao, conteudo, ano0_ppe, ppe)
    return {
        "ticker": ticker_normalizado,
        "parametros_ppe": parametros,
        "ano0_ppe": ano0_ppe,
        "ppe": ppe,
        "dre": dre,
        "caminho_saida": caminho_projecao,
    }


def serie_depreciacao_igual_dre(resultado: dict[str, Any]) -> bool:
    """Confirma que a serie D&A da DRE e identica a serie do schedule PP&E."""
    ppe = resultado["ppe"]
    dre = resultado["dre"]
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        depreciacao_ppe = float(ppe[chave_ano]["depreciacao_amortizacao"])
        depreciacao_dre = float(dre[chave_ano]["depreciacao_amortizacao"])
        if abs(depreciacao_ppe - depreciacao_dre) > 1e-9:
            return False
    return True


def imprimir_tabela_ppe(resultado: dict[str, Any]) -> None:
    """Imprime tabela de CAPEX, D&A e PP&E para validacao visual."""
    ticker = resultado["ticker"]
    ano0_ppe = resultado["ano0_ppe"]
    ppe = resultado["ppe"]
    dre = resultado["dre"]
    parametros = resultado["parametros_ppe"]
    print("\n" + "=" * 120)
    print(f"Schedule PP&E - {ticker}")
    print(
        "Ano 0: "
        f"PP&E={formatar_numero(float(ano0_ppe['imobilizado']))} | "
        f"data={ano0_ppe.get('data_exercicio')} | "
        f"fonte={ano0_ppe.get('fonte')}"
    )
    print(
        "Vida util PP&E: "
        f"{formatar_numero(float(parametros['vida_util_ppe_anos']))} anos | "
        f"taxa D&A={formatar_percentual(parametros['taxa_depreciacao_ppe'])}"
    )
    print(
        "Campos de CAPEX/Receita lidos individualmente: "
        + ", ".join(f"capex_receita_ano{ano}" for ano in range(1, 9))
    )

    cabecalho = (
        f"{'Ano':<6} {'Receita':>18} {'CAPEX/Receita':>15} "
        f"{'CAPEX':>18} {'D&A':>18} {'PP&E':>18} {'DRE D&A':>18}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for chave_ano, linha in ppe.items():
        receita_liquida = float(dre[chave_ano]["receita_liquida"])
        print(
            f"{chave_ano:<6} "
            f"{formatar_numero(receita_liquida):>18} "
            f"{formatar_percentual(float(linha['capex_receita'])):>15} "
            f"{formatar_numero(float(linha['capex'])):>18} "
            f"{formatar_numero(float(linha['depreciacao_amortizacao'])):>18} "
            f"{formatar_numero(float(linha['imobilizado'])):>18} "
            f"{formatar_numero(float(dre[chave_ano]['depreciacao_amortizacao'])):>18}"
        )

    status = "OK" if serie_depreciacao_igual_dre(resultado) else "DIVERGENTE"
    print(f"D&A da DRE == D&A do schedule PP&E: {status}")


def executar_validacao_padrao() -> None:
    """Executa o schedule PP&E para DIRR3 e MGLU3 ao rodar o arquivo direto."""
    houve_falha = False
    for ticker in ("DIRR3", "MGLU3"):
        try:
            resultado = projetar_ppe(ticker)
            imprimir_tabela_ppe(resultado)
        except Exception as erro:
            houve_falha = True
            print(f"\nFalha ao projetar PP&E de {ticker}: {erro}")

    if houve_falha:
        raise SystemExit(1)


if __name__ == "__main__":
    executar_validacao_padrao()
