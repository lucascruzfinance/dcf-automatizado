"""Schedule de divida, DFC simplificado e fechamento do balanco projetado."""

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
        normalizar_ticker,
        normalizar_valor_json,
        projetar_dre,
        resolver_raiz,
        salvar_json,
        selecionar_ultimo_exercicio,
        valor_numerico_obrigatorio,
    )
    from src.projecao.schedule_ppe import projetar_ppe
    from src.projecao.schedule_wk import projetar_wk
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
        normalizar_ticker,
        normalizar_valor_json,
        projetar_dre,
        resolver_raiz,
        salvar_json,
        selecionar_ultimo_exercicio,
        valor_numerico_obrigatorio,
    )
    from schedule_ppe import projetar_ppe
    from schedule_wk import projetar_wk

CAMPO_PAYOUT_DIVIDENDOS = "payout_dividendos"
POLITICA_DIVIDA = "divida_bruta_constante_sem_amortizacao"
POLITICA_CAIXA = "caixa_como_plug_de_fechamento"
TOLERANCIA_FECHAMENTO_RELATIVA = 1e-6


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


def carregar_parametros_divida(raiz_projeto: Path) -> dict[str, float]:
    """Carrega parametros globais usados pelo schedule de divida."""
    caminho = raiz_projeto / "config" / "parametros.json"
    parametros = carregar_json(caminho)
    valor = parametros.get(CAMPO_PAYOUT_DIVIDENDOS)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"Parametro obrigatorio invalido: {CAMPO_PAYOUT_DIVIDENDOS}")

    payout = float(valor)
    if payout < 0 or payout > 1:
        raise ValueError(f"Parametro fora de 0-1: {CAMPO_PAYOUT_DIVIDENDOS}")

    return {"payout_dividendos": payout}


def carregar_premissas_divida(ticker: str, raiz_projeto: Path) -> dict[str, float]:
    """Carrega o custo da divida informado pelo analista."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    premissas = carregar_json(caminho)
    custo_divida = valor_numerico_obrigatorio(premissas, "custo_divida_kd")
    if custo_divida < 0:
        raise ValueError("Premissa custo_divida_kd nao pode ser negativa.")
    return {"custo_divida_kd": custo_divida}


def carregar_projecao_existente(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[
    Path,
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    """Carrega DRE, WK e PP&E ja projetados para o ticker."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    dre = conteudo.get("dre")
    wk = conteudo.get("wk")
    ppe = conteudo.get("ppe")
    if not isinstance(dre, dict):
        raise RuntimeError(f"DRE projetada ausente ou invalida em {caminho}")
    if not isinstance(wk, dict):
        raise RuntimeError(f"Schedule WK ausente ou invalido em {caminho}")
    if not isinstance(ppe, dict):
        raise RuntimeError(f"Schedule PP&E ausente ou invalido em {caminho}")

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        if chave_ano not in dre or not isinstance(dre[chave_ano], dict):
            raise RuntimeError(f"DRE projetada sem {chave_ano} em {caminho}")
        if chave_ano not in wk or not isinstance(wk[chave_ano], dict):
            raise RuntimeError(f"Schedule WK sem {chave_ano} em {caminho}")
        if chave_ano not in ppe or not isinstance(ppe[chave_ano], dict):
            raise RuntimeError(f"Schedule PP&E sem {chave_ano} em {caminho}")

        obter_float_obrigatorio(dre[chave_ano], "receita_liquida", chave_ano)
        obter_float_obrigatorio(dre[chave_ano], "ebit", chave_ano)
        obter_float_obrigatorio(wk[chave_ano], "contas_receber", chave_ano)
        obter_float_obrigatorio(wk[chave_ano], "estoques", chave_ano)
        obter_float_obrigatorio(wk[chave_ano], "fornecedores", chave_ano)
        obter_float_obrigatorio(wk[chave_ano], "delta_nwc", chave_ano)
        obter_float_obrigatorio(ppe[chave_ano], "capex", chave_ano)
        obter_float_obrigatorio(
            ppe[chave_ano],
            "depreciacao_amortizacao",
            chave_ano,
        )
        obter_float_obrigatorio(ppe[chave_ano], "imobilizado", chave_ano)

    return caminho, conteudo, dre, wk, ppe


def carregar_quadro_cvm(caminho: Path) -> pd.DataFrame:
    """Carrega JSON bruto da CVM em DataFrame validando estrutura minima."""
    registros = carregar_json(caminho)
    dados = pd.DataFrame(registros)
    if dados.empty:
        raise RuntimeError(f"Base historica vazia: {caminho}")
    return dados


def extrair_linha_ano0(
    dados: pd.DataFrame,
    nome_padronizado: str,
) -> pd.Series:
    """Seleciona a linha historica mais recente para uma conta padronizada."""
    return selecionar_ultimo_exercicio(dados, nome_padronizado)


def valor_linha(linhas: dict[str, pd.Series], campo: str) -> float:
    """Extrai valor padronizado de uma linha historica ja selecionada."""
    return float(linhas[campo]["valor_padronizado"])


def carregar_ano0_divida_balanco(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega divida, caixa, aplicacoes e PL do ultimo BP historico."""
    caminho = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_bp.json"
    dados = carregar_quadro_cvm(caminho)
    campos = (
        "caixa_equivalentes",
        "aplicacoes_financeiras",
        "divida_curto_prazo",
        "divida_longo_prazo",
        "patrimonio_liquido",
    )
    linhas = {campo: extrair_linha_ano0(dados, campo) for campo in campos}
    divida_curto = abs(valor_linha(linhas, "divida_curto_prazo"))
    divida_longo = abs(valor_linha(linhas, "divida_longo_prazo"))
    divida_bruta = divida_curto + divida_longo
    linha_referencia = linhas["caixa_equivalentes"]

    return {
        "fonte": str(caminho.relative_to(raiz_projeto)),
        "ano_arquivo": normalizar_valor_json(linha_referencia.get("ano_arquivo")),
        "data_exercicio": normalizar_valor_json(linha_referencia.get("DT_FIM_EXERC")),
        "ordem_exercicio": normalizar_valor_json(linha_referencia.get("ORDEM_EXERC")),
        "caixa_equivalentes": valor_linha(linhas, "caixa_equivalentes"),
        "aplicacoes_financeiras": valor_linha(linhas, "aplicacoes_financeiras"),
        "divida_curto_prazo": divida_curto,
        "divida_longo_prazo": divida_longo,
        "divida_bruta": divida_bruta,
        "patrimonio_liquido": valor_linha(linhas, "patrimonio_liquido"),
    }


def projetar_linhas_divida(
    ano0_divida_balanco: dict[str, Any],
    custo_divida_kd: float,
) -> dict[str, dict[str, float | str]]:
    """Projeta a divida usando saldo bruto constante e sem amortizacao."""
    divida_inicial = float(ano0_divida_balanco["divida_bruta"])
    if divida_inicial > 0:
        percentual_curto = (
            float(ano0_divida_balanco["divida_curto_prazo"]) / divida_inicial
        )
    else:
        percentual_curto = 0.0

    linhas = {}
    divida_anterior = divida_inicial
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"

        # Politica v1: manter divida bruta constante. Nao ha captacao liquida
        # nem amortizacao programada nesta versao; o caixa fecha o balanco.
        divida_bruta = divida_inicial
        divida_curto = divida_bruta * percentual_curto
        divida_longo = divida_bruta - divida_curto

        # Formula: juros_t = Kd x (divida_(t-1) + divida_t) / 2.
        saldo_medio = (divida_anterior + divida_bruta) / 2
        juros = custo_divida_kd * saldo_medio
        delta_divida = divida_bruta - divida_anterior

        linhas[chave_ano] = {
            "ano_projecao": chave_ano,
            "politica_divida": POLITICA_DIVIDA,
            "custo_divida_kd": custo_divida_kd,
            "divida_curto_prazo": divida_curto,
            "divida_longo_prazo": divida_longo,
            "divida_bruta": divida_bruta,
            "saldo_medio_divida": saldo_medio,
            "juros": juros,
            "resultado_financeiro": -juros,
            "amortizacao": 0.0,
            "captacao": 0.0,
            "delta_divida": delta_divida,
        }
        divida_anterior = divida_bruta

    return linhas


def atualizar_dre_com_resultado_financeiro(
    dre: dict[str, dict[str, Any]],
    divida: dict[str, dict[str, float | str]],
    usa_ret: bool,
) -> None:
    """Sobrescreve resultado financeiro e recalcula EBT, IR/CSLL e LL."""
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_dre = dre[chave_ano]
        receita_liquida = obter_float_obrigatorio(
            linha_dre,
            "receita_liquida",
            chave_ano,
        )
        ebit = obter_float_obrigatorio(linha_dre, "ebit", chave_ano)
        resultado_financeiro = obter_float_obrigatorio(
            divida[chave_ano],
            "resultado_financeiro",
            chave_ano,
        )

        # Formula: resultado_financeiro_t = -juros_t. Receita financeira sobre
        # caixa nao e modelada nesta versao para manter o loop simples.
        linha_dre["resultado_financeiro"] = resultado_financeiro
        linha_dre["ebt"] = ebit + resultado_financeiro
        linha_dre["ir_csll"] = calcular_ir_csll(
            ebt=float(linha_dre["ebt"]),
            receita_liquida=receita_liquida,
            usa_ret=usa_ret,
        )
        linha_dre["lucro_liquido"] = linha_dre["ebt"] + linha_dre["ir_csll"]


def calcular_dividendos(lucro_liquido: float, payout: float) -> float:
    """Calcula dividendos sem distribuir resultado negativo."""
    # Formula: dividendos_t = max(LL_t, 0) x payout.
    return max(lucro_liquido, 0.0) * payout


def montar_balanco_e_dfc(
    ano0_divida_balanco: dict[str, Any],
    dre: dict[str, dict[str, Any]],
    wk: dict[str, dict[str, Any]],
    ppe: dict[str, dict[str, Any]],
    divida: dict[str, dict[str, float | str]],
    payout: float,
) -> tuple[dict[str, dict[str, float | str]], dict[str, dict[str, float | str]]]:
    """Monta balanco com caixa plug e DFC simplificado para ano1..ano8."""
    balanco = {}
    dfc = {}
    patrimonio_liquido_anterior = float(ano0_divida_balanco["patrimonio_liquido"])
    caixa_anterior = float(ano0_divida_balanco["caixa_equivalentes"])
    aplicacoes = float(ano0_divida_balanco["aplicacoes_financeiras"])

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_dre = dre[chave_ano]
        linha_wk = wk[chave_ano]
        linha_ppe = ppe[chave_ano]
        linha_divida = divida[chave_ano]

        lucro_liquido = obter_float_obrigatorio(
            linha_dre,
            "lucro_liquido",
            chave_ano,
        )
        depreciacao = obter_float_obrigatorio(
            linha_ppe,
            "depreciacao_amortizacao",
            chave_ano,
        )
        delta_nwc = obter_float_obrigatorio(linha_wk, "delta_nwc", chave_ano)
        capex_assinado = obter_float_obrigatorio(linha_ppe, "capex", chave_ano)
        delta_divida = obter_float_obrigatorio(
            linha_divida,
            "delta_divida",
            chave_ano,
        )
        capex_saida_caixa = abs(capex_assinado)

        # Formula DFC simplificado:
        # FCF_t = LL_t + D&A_t - Delta NWC_t - CAPEX_t + Delta Divida_t.
        # Como o CAPEX e salvo assinado no PP&E, o DFC subtrai sua magnitude.
        fluxo_caixa_livre = (
            lucro_liquido + depreciacao - delta_nwc - capex_saida_caixa + delta_divida
        )

        dividendos = calcular_dividendos(lucro_liquido, payout)

        # Formula: PL_t = PL_(t-1) + LL_t - dividendos_t.
        patrimonio_liquido = patrimonio_liquido_anterior + lucro_liquido - dividendos

        contas_receber = obter_float_obrigatorio(
            linha_wk,
            "contas_receber",
            chave_ano,
        )
        estoques = obter_float_obrigatorio(linha_wk, "estoques", chave_ano)
        fornecedores = abs(obter_float_obrigatorio(linha_wk, "fornecedores", chave_ano))
        imobilizado = obter_float_obrigatorio(linha_ppe, "imobilizado", chave_ano)
        divida_curto = obter_float_obrigatorio(
            linha_divida,
            "divida_curto_prazo",
            chave_ano,
        )
        divida_longo = obter_float_obrigatorio(
            linha_divida,
            "divida_longo_prazo",
            chave_ano,
        )
        outros_ativos = 0.0
        outros_passivos = 0.0

        passivo_total = fornecedores + divida_curto + divida_longo + outros_passivos
        ativo_sem_caixa = (
            aplicacoes + contas_receber + estoques + imobilizado + outros_ativos
        )

        # Caixa e plug: Caixa_t = Passivo_t + PL_t - ativos sem caixa_t.
        caixa = passivo_total + patrimonio_liquido - ativo_sem_caixa
        ativo_total = caixa + ativo_sem_caixa
        passivo_patrimonio_liquido = passivo_total + patrimonio_liquido
        diferenca = ativo_total - passivo_patrimonio_liquido
        variacao_caixa_plug = caixa - caixa_anterior

        balanco[chave_ano] = {
            "ano_projecao": chave_ano,
            "caixa_equivalentes": caixa,
            "aplicacoes_financeiras": aplicacoes,
            "contas_receber": contas_receber,
            "estoques": estoques,
            "imobilizado": imobilizado,
            "outros_ativos": outros_ativos,
            "ativo_total": ativo_total,
            "fornecedores": fornecedores,
            "divida_curto_prazo": divida_curto,
            "divida_longo_prazo": divida_longo,
            "outros_passivos": outros_passivos,
            "passivo_total": passivo_total,
            "patrimonio_liquido": patrimonio_liquido,
            "passivo_patrimonio_liquido": passivo_patrimonio_liquido,
            "diferenca_balanco": diferenca,
            "politica_caixa": POLITICA_CAIXA,
        }
        dfc[chave_ano] = {
            "ano_projecao": chave_ano,
            "lucro_liquido": lucro_liquido,
            "depreciacao_amortizacao": depreciacao,
            "delta_nwc": delta_nwc,
            "capex": capex_assinado,
            "capex_saida_caixa": capex_saida_caixa,
            "delta_divida": delta_divida,
            "fluxo_caixa_livre": fluxo_caixa_livre,
            "dividendos": dividendos,
            "variacao_caixa_plug": variacao_caixa_plug,
        }

        patrimonio_liquido_anterior = patrimonio_liquido
        caixa_anterior = caixa

    return balanco, dfc


def validar_fechamento_balanco(
    balanco: dict[str, dict[str, float | str]],
    tolerancia_relativa: float = TOLERANCIA_FECHAMENTO_RELATIVA,
) -> None:
    """Garante que Ativo = Passivo + PL em todos os anos projetados."""
    for chave_ano, linha in balanco.items():
        ativo_total = float(linha["ativo_total"])
        passivo_pl = float(linha["passivo_patrimonio_liquido"])
        diferenca = float(linha["diferenca_balanco"])
        escala = max(abs(ativo_total), abs(passivo_pl), 1.0)
        if abs(diferenca) > escala * tolerancia_relativa:
            raise RuntimeError(
                f"Balanco nao fecha em {chave_ano}: diferenca={diferenca}"
            )


def atualizar_projecao_divida(
    caminho: Path,
    conteudo: dict[str, Any],
    ano0_divida_balanco: dict[str, Any],
    divida: dict[str, dict[str, float | str]],
    balanco: dict[str, dict[str, float | str]],
    dfc: dict[str, dict[str, float | str]],
    politicas: dict[str, Any],
) -> None:
    """Grava divida, balanco, DFC e politicas dentro da projecao."""
    ano0 = conteudo.get("ano0")
    if not isinstance(ano0, dict):
        ano0 = {}
    ano0["divida"] = {
        "fonte": ano0_divida_balanco["fonte"],
        "ano_arquivo": ano0_divida_balanco["ano_arquivo"],
        "data_exercicio": ano0_divida_balanco["data_exercicio"],
        "ordem_exercicio": ano0_divida_balanco["ordem_exercicio"],
        "divida_curto_prazo": ano0_divida_balanco["divida_curto_prazo"],
        "divida_longo_prazo": ano0_divida_balanco["divida_longo_prazo"],
        "divida_bruta": ano0_divida_balanco["divida_bruta"],
    }
    ano0["balanco"] = {
        "fonte": ano0_divida_balanco["fonte"],
        "ano_arquivo": ano0_divida_balanco["ano_arquivo"],
        "data_exercicio": ano0_divida_balanco["data_exercicio"],
        "ordem_exercicio": ano0_divida_balanco["ordem_exercicio"],
        "caixa_equivalentes": ano0_divida_balanco["caixa_equivalentes"],
        "aplicacoes_financeiras": ano0_divida_balanco["aplicacoes_financeiras"],
        "patrimonio_liquido": ano0_divida_balanco["patrimonio_liquido"],
    }
    conteudo["ano0"] = ano0
    conteudo["divida"] = divida
    conteudo["balanco"] = balanco
    conteudo["dfc"] = dfc
    politicas_projecao = conteudo.get("politicas_projecao")
    if not isinstance(politicas_projecao, dict):
        politicas_projecao = {}
    politicas_projecao["divida_balanco"] = politicas
    conteudo["politicas_projecao"] = politicas_projecao
    salvar_json(caminho, conteudo)


def projetar_divida(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Executa o schedule de divida e fecha o balanco projetado."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    parametros = carregar_parametros_divida(raiz)
    premissas_divida = carregar_premissas_divida(ticker_normalizado, raiz)
    metadados = carregar_metadados(ticker_normalizado, raiz)
    caminho_projecao, conteudo, dre, wk, ppe = carregar_projecao_existente(
        ticker_normalizado,
        raiz,
    )
    ano0_divida_balanco = carregar_ano0_divida_balanco(ticker_normalizado, raiz)
    divida = projetar_linhas_divida(
        ano0_divida_balanco=ano0_divida_balanco,
        custo_divida_kd=premissas_divida["custo_divida_kd"],
    )
    premissas_completas = carregar_json(
        raiz / "data" / "premissas" / f"{ticker_normalizado}_premissas.json"
    )
    atualizar_dre_com_resultado_financeiro(
        dre=dre,
        divida=divida,
        usa_ret=empresa_usa_ret(premissas_completas, metadados),
    )
    balanco, dfc = montar_balanco_e_dfc(
        ano0_divida_balanco=ano0_divida_balanco,
        dre=dre,
        wk=wk,
        ppe=ppe,
        divida=divida,
        payout=parametros["payout_dividendos"],
    )
    validar_fechamento_balanco(balanco)
    politicas = {
        "politica_divida": POLITICA_DIVIDA,
        "politica_caixa": POLITICA_CAIXA,
        "payout_dividendos": parametros["payout_dividendos"],
        "receita_financeira_sobre_caixa": False,
        "aplicacoes_financeiras": "constantes_no_saldo_do_ano0",
        "outros_ativos": "zerado_nesta_versao",
        "outros_passivos": "zerado_nesta_versao",
    }
    atualizar_projecao_divida(
        caminho=caminho_projecao,
        conteudo=conteudo,
        ano0_divida_balanco=ano0_divida_balanco,
        divida=divida,
        balanco=balanco,
        dfc=dfc,
        politicas=politicas,
    )
    return {
        "ticker": ticker_normalizado,
        "premissas_divida": premissas_divida,
        "parametros_divida": parametros,
        "ano0_divida_balanco": ano0_divida_balanco,
        "divida": divida,
        "dre": dre,
        "balanco": balanco,
        "dfc": dfc,
        "politicas": politicas,
        "caminho_saida": caminho_projecao,
    }


def imprimir_fechamento_balanco(resultado: dict[str, Any]) -> None:
    """Imprime as verificacoes de fechamento para os oito anos."""
    ticker = resultado["ticker"]
    balanco = resultado["balanco"]
    politicas = resultado["politicas"]
    print("\n" + "=" * 120)
    print(f"Schedule de divida e fechamento do balanco - {ticker}")
    print(
        "Politica: "
        f"{politicas['politica_divida']} | "
        f"{politicas['politica_caixa']} | "
        f"payout={politicas['payout_dividendos']:.2%}"
    )
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha = balanco[chave_ano]
        print(
            f"Ano {ano}: "
            f"Ativo = {formatar_numero(float(linha['ativo_total']))} | "
            "Passivo+PL = "
            f"{formatar_numero(float(linha['passivo_patrimonio_liquido']))} | "
            f"diferenca = {formatar_numero(float(linha['diferenca_balanco']))}"
        )


def executar_validacao_padrao() -> None:
    """Executa a cadeia de projecao ate divida para DIRR3 e MGLU3."""
    houve_falha = False
    for ticker in ("DIRR3", "MGLU3"):
        try:
            projetar_dre(ticker)
            projetar_wk(ticker)
            projetar_ppe(ticker)
            resultado = projetar_divida(ticker)
            imprimir_fechamento_balanco(resultado)
        except Exception as erro:
            houve_falha = True
            print(f"\nFalha ao projetar divida de {ticker}: {erro}")

    if houve_falha:
        raise SystemExit(1)


if __name__ == "__main__":
    executar_validacao_padrao()
