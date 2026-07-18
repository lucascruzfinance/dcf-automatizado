"""Schedule de divida real, DFC e verificacao do balanco projetado (v2.0).

Substitui as simplificacoes da v1 (divida constante, payout zero, caixa
como plug) pelo motor completo da Onda 2:

- **Amortizacao por perfil:** a divida de curto prazo do Ano 0 amortiza no
  ano 1; a de longo prazo amortiza linearmente em
  ``prazo_amortizacao_lp_anos`` (config). Captacoes novas viram tranches
  que amortizam no mesmo prazo a partir do ano seguinte. O CP de cada ano
  projetado e a amortizacao programada do ano seguinte (reclassificacao).
- **Captacao para deficit:** se o caixa projetado ficar abaixo do caixa
  minimo (``caixa_minimo_pct_receita`` x receita), capta a diferenca no fim
  do ano (sem juros no proprio ano).
- **Receita financeira sobre caixa:** ``taxa_aplicacao_caixa`` (premissa >
  Selic coletada > fallback de config) x (caixa inicial + aplicacoes).
- **Convencao de saldo inicial:** juros e receita financeira incidem sobre
  os saldos de ABERTURA do ano — remove a circularidade juros/captacao sem
  iteracao (convencao documentada; captacao do ano so paga juros em t+1).
- **Payout real:** ``payout_dividendos`` da premissa > default do subtipo
  (config/setores.json) > parametro global. PL_t = PL_(t-1) + LL_t - div_t.
- **Caixa via DFC:** caixa_t = caixa_(t-1) + FCO + FCI + FCF. O fechamento
  ``Ativo = Passivo + PL`` vira VERIFICACAO: ``outros_ativos``/
  ``outros_passivos`` sao os residuais do BP REAL do Ano 0 (constantes na
  projecao), o que fecha o balanco por construcao; desvio numerico vira
  alerta (checklist NF1), nunca plug.
"""

from __future__ import annotations

import logging
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
        montar_contexto_ir_completo,
        normalizar_ticker,
        normalizar_valor_json,
        projetar_dre,
        recalcular_cauda_dre_completa,
        resolver_raiz,
        salvar_json,
        selecionar_ultimo_exercicio,
        somar_ultimo_exercicio,
        valor_numerico_obrigatorio,
    )
    from src.projecao.schedule_leasing import projetar_leasing
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
        montar_contexto_ir_completo,
        normalizar_ticker,
        normalizar_valor_json,
        projetar_dre,
        recalcular_cauda_dre_completa,
        resolver_raiz,
        salvar_json,
        selecionar_ultimo_exercicio,
        somar_ultimo_exercicio,
        valor_numerico_obrigatorio,
    )
    from schedule_leasing import projetar_leasing
    from schedule_ppe import projetar_ppe
    from schedule_wk import projetar_wk

CAMPO_PAYOUT_DIVIDENDOS = "payout_dividendos"
POLITICA_DIVIDA = "amortizacao_perfil_cp_lp_com_captacao_para_caixa_minimo"
POLITICA_CAIXA = "caixa_resultado_do_dfc_com_verificacao"
TOLERANCIA_FECHAMENTO_RELATIVA = 1e-6
PRAZO_AMORTIZACAO_LP_PADRAO = 5
CAIXA_MINIMO_PCT_RECEITA_PADRAO = 0.02
TAXA_APLICACAO_FALLBACK_PADRAO = 0.10

logger = logging.getLogger(__name__)


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


def _numero_ou_none(valor: Any) -> float | None:
    """Converte para float sem aceitar booleanos; invalido vira None."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def carregar_parametros_divida(raiz_projeto: Path) -> dict[str, float]:
    """Parametros globais do schedule: payout fallback e politica de divida."""
    caminho = raiz_projeto / "config" / "parametros.json"
    parametros = carregar_json(caminho)
    valor = parametros.get(CAMPO_PAYOUT_DIVIDENDOS)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"Parametro obrigatorio invalido: {CAMPO_PAYOUT_DIVIDENDOS}")
    payout = float(valor)
    if payout < 0 or payout > 1:
        raise ValueError(f"Parametro fora de 0-1: {CAMPO_PAYOUT_DIVIDENDOS}")

    politica = parametros.get("politica_divida", {})
    prazo = politica.get("prazo_amortizacao_lp_anos", PRAZO_AMORTIZACAO_LP_PADRAO)
    caixa_minimo = politica.get(
        "caixa_minimo_pct_receita",
        CAIXA_MINIMO_PCT_RECEITA_PADRAO,
    )
    taxa_fallback = politica.get(
        "taxa_aplicacao_caixa_fallback",
        TAXA_APLICACAO_FALLBACK_PADRAO,
    )
    return {
        "payout_dividendos_global": payout,
        "prazo_amortizacao_lp_anos": max(int(prazo), 1),
        "caixa_minimo_pct_receita": float(caixa_minimo),
        "taxa_aplicacao_caixa_fallback": float(taxa_fallback),
    }


def carregar_premissas_divida(ticker: str, raiz_projeto: Path) -> dict[str, float]:
    """Carrega o custo da divida informado pelo analista."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    premissas = carregar_json(caminho)
    custo_divida = valor_numerico_obrigatorio(premissas, "custo_divida_kd")
    if custo_divida < 0:
        raise ValueError("Premissa custo_divida_kd nao pode ser negativa.")
    return {"custo_divida_kd": custo_divida}


def resolver_payout(
    premissas: dict[str, Any],
    metadados: dict[str, Any],
    parametros: dict[str, float],
    raiz_projeto: Path,
) -> tuple[float, str]:
    """Payout: premissa da empresa > default do subtipo > parametro global."""
    payout_premissa = _numero_ou_none(premissas.get(CAMPO_PAYOUT_DIVIDENDOS))
    if payout_premissa is not None and 0 <= payout_premissa <= 1:
        return payout_premissa, "premissa_da_empresa"

    subtipo = metadados.get("subtipo")
    if subtipo:
        caminho_setores = raiz_projeto / "config" / "setores.json"
        if caminho_setores.exists():
            setores = carregar_json(caminho_setores)
            defaults = (
                setores.get("subtipos", {})
                .get(str(subtipo), {})
                .get("premissas_default", {})
            )
            payout_subtipo = _numero_ou_none(defaults.get(CAMPO_PAYOUT_DIVIDENDOS))
            if payout_subtipo is not None and 0 <= payout_subtipo <= 1:
                return payout_subtipo, f"default_do_subtipo_{subtipo}"

    return parametros["payout_dividendos_global"], "parametro_global"


def resolver_taxa_aplicacao(
    premissas: dict[str, Any],
    parametros: dict[str, float],
    raiz_projeto: Path,
) -> tuple[float, str]:
    """Taxa de aplicacao do caixa: premissa > Selic coletada > fallback."""
    taxa_premissa = _numero_ou_none(premissas.get("taxa_aplicacao_caixa"))
    if taxa_premissa is not None and taxa_premissa >= 0:
        return taxa_premissa, "premissa_da_empresa"

    caminho_macro = raiz_projeto / "data" / "raw" / "macro" / "macro_brasil.json"
    if caminho_macro.exists():
        macro = carregar_json(caminho_macro)
        selic = _numero_ou_none(macro.get("selic_atual"))
        if selic is not None and selic > 0:
            # Selic > 1 indica valor em % a.a. (ex.: 10.5) — converte.
            taxa = selic / 100.0 if selic > 1 else selic
            return taxa, "selic_atual_coletada"

    return parametros["taxa_aplicacao_caixa_fallback"], "fallback_config"


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


def _valor_opcional_ano0(dados: pd.DataFrame, nome: str) -> float:
    """Valor do Ano 0 para conta opcional; ausente vira 0.0 sem quebrar."""
    try:
        linha = selecionar_ultimo_exercicio(dados, nome)
    except RuntimeError:
        return 0.0
    return float(linha["valor_padronizado"])


def carregar_ano0_divida_balanco(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega o BP real do Ano 0: divida, caixa, PL e itens do bridge.

    Alem dos campos da v1, expoe ``ativo_total``, minoritarios, coligadas e
    arrendamento (IFRS16) — insumos do bridge completo EV -> Equity e dos
    residuais ``outros_ativos``/``outros_passivos`` que ancoram o balanco
    projetado no balanco REAL.
    """
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
        "ativo_total": _valor_opcional_ano0(dados, "ativo_total"),
        "participacao_nao_controladores": abs(
            _valor_opcional_ano0(dados, "participacao_nao_controladores")
        ),
        "investimentos_coligadas": _valor_opcional_ano0(
            dados,
            "investimentos_coligadas",
        ),
        # Passivo de arrendamento SOMADO das sub-contas (CP + LP), fonte unica
        # do bridge e do schedule de leasing (Prompt 8.2) — o valor de uma
        # unica sub-conta subestimava o saldo total (algumas sao zero).
        "passivo_arrendamento": abs(
            somar_ultimo_exercicio(dados, "passivo_arrendamento")
        ),
    }


def _wk_tem_multi_driver(wk: dict[str, dict[str, Any]]) -> bool:
    """True quando o schedule WK projetou as contas expandidas (9.0.2)."""
    linha = wk.get("ano1", {})
    return "tributos_a_recuperar" in linha


def _residuais_balanco_ano0(
    ano0: dict[str, Any],
    conteudo: dict[str, Any],
    wk_multi_driver: bool,
) -> tuple[float, float]:
    """Residuais do BP real do Ano 0 (constantes e EXPLICITOS na projecao).

    outros_ativos_0 = Ativo Total real - linhas de ativo MODELADAS (caixa,
    aplicacoes, CR, estoques, imobilizado, intangivel e, no WK expandido,
    tributos a recuperar). outros_passivos_0 = passivo exigivel real -
    fornecedores - divida bruta - passivo de arrendamento (linha propria
    constante, 9.0.2) - contas do WK expandido quando projetadas. Com os
    residuais constantes e caixa via DFC, o balanco fecha por construcao
    (verificado, nao plugado).
    """
    ano0_wk = conteudo.get("ano0", {}).get("wk", {})
    ano0_ppe = conteudo.get("ano0", {}).get("ppe", {})
    ativo_total = float(ano0.get("ativo_total") or 0.0)
    if ativo_total <= 0:
        # Sem ativo total mapeado nao ha residuo confiavel; degrada para
        # zero com aviso (o fechamento vira o proprio residuo do modelo).
        logger.warning("ativo_total do Ano 0 indisponivel; outros_ativos/passivos = 0.")
        return 0.0, 0.0

    contas_receber = float(ano0_wk.get("contas_receber") or 0.0)
    estoques = float(ano0_wk.get("estoques") or 0.0)
    fornecedores = abs(float(ano0_wk.get("fornecedores") or 0.0))
    imobilizado = float(ano0_ppe.get("imobilizado") or 0.0)
    # Intangivel e linha PROPRIA do balanco (D-043); fora do residual.
    intangivel = float(ano0_ppe.get("intangivel") or 0.0)

    ativos_modelados = (
        float(ano0["caixa_equivalentes"])
        + float(ano0["aplicacoes_financeiras"])
        + contas_receber
        + estoques
        + imobilizado
        + intangivel
    )
    passivos_modelados = fornecedores + float(ano0["divida_bruta"])
    # Passivo de arrendamento vira linha PROPRIA constante do BP aberto
    # (9.0.2); sai do residual sem alterar o total.
    passivos_modelados += abs(float(ano0.get("passivo_arrendamento") or 0.0))
    if wk_multi_driver:
        ativos_modelados += abs(float(ano0_wk.get("tributos_a_recuperar") or 0.0))
        passivos_modelados += abs(
            float(ano0_wk.get("obrigacoes_sociais_trabalhistas") or 0.0)
        ) + abs(float(ano0_wk.get("adiantamento_clientes") or 0.0))

    outros_ativos = ativo_total - ativos_modelados
    passivo_exigivel = ativo_total - float(ano0["patrimonio_liquido"])
    outros_passivos = passivo_exigivel - passivos_modelados
    return outros_ativos, outros_passivos


def carregar_instrumentos_divida(
    premissas: dict[str, Any],
) -> list[dict[str, Any]] | None:
    """Tabela OPCIONAL ``instrumentos_divida`` das premissas (Prompt 9.0.2.4).

    Cada item: ``{"nome", "saldo"`` (BRL, ja convertido), ``"taxa"`` (a.a.
    decimal; ausente usa o Kd), ``"indexador"`` (texto informativo),
    ``"ano_vencimento"`` (1..8, bullet) OU ``"curva_amortizacao"``
    ({"ano1": pct, ...}, soma <= 100%; o resto permanece devedor)``}``.
    Sem a tabela devolve None e o perfil CP/LP agregado v2 continua.
    """
    instrumentos = premissas.get("instrumentos_divida")
    if not isinstance(instrumentos, list) or not instrumentos:
        return None
    validados: list[dict[str, Any]] = []
    for indice, item in enumerate(instrumentos):
        if not isinstance(item, dict):
            raise ValueError(f"instrumentos_divida[{indice}] precisa ser objeto.")
        saldo = item.get("saldo")
        if isinstance(saldo, bool) or not isinstance(saldo, (int, float)) or saldo < 0:
            raise ValueError(
                f"instrumentos_divida[{indice}].saldo invalido (BRL >= 0)."
            )
        validados.append(item)
    return validados


def _cronograma_do_instrumento(
    instrumento: dict[str, Any],
    prazo_lp: int,
) -> dict[int, float]:
    """Cronograma absoluto de amortizacao (ano -> R$) de um instrumento.

    ``curva_amortizacao`` (percentuais do saldo) > ``ano_vencimento`` (bullet)
    > linear em ``prazo_lp`` anos (fallback do perfil agregado).
    """
    saldo = float(instrumento["saldo"])
    curva = instrumento.get("curva_amortizacao")
    if isinstance(curva, dict) and curva:
        cronograma: dict[int, float] = {}
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            pct = curva.get(f"ano{ano}", 0.0)
            if isinstance(pct, bool) or not isinstance(pct, (int, float)):
                pct = 0.0
            cronograma[ano] = saldo * max(float(pct), 0.0)
        return cronograma
    vencimento = instrumento.get("ano_vencimento")
    if (
        isinstance(vencimento, (int, float))
        and not isinstance(vencimento, bool)
        and 1 <= int(vencimento) <= HORIZONTE_PROJECAO
    ):
        return {int(vencimento): saldo}
    return {ano: saldo / prazo_lp for ano in range(1, prazo_lp + 1)}


def _montar_tranches_iniciais(
    ano0: dict[str, Any],
    prazo_lp: int,
    custo_divida_kd: float,
    instrumentos: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Tranches de amortizacao do estoque de divida do Ano 0.

    SEM instrumentos (perfil agregado v2): CP do Ano 0 vence no ano 1; LP
    amortiza linearmente em ``prazo_lp`` anos; juros por Kd unico. COM a
    tabela ``instrumentos_divida``: uma tranche por instrumento, com taxa e
    cronograma proprios (o saldo total substitui o CP/LP agregado).
    """
    if instrumentos:
        tranches: list[dict[str, Any]] = []
        for instrumento in instrumentos:
            saldo = float(instrumento["saldo"])
            if saldo <= 0:
                continue
            taxa = instrumento.get("taxa")
            if isinstance(taxa, bool) or not isinstance(taxa, (int, float)):
                taxa = custo_divida_kd
            tranches.append(
                {
                    "nome": str(instrumento.get("nome", "instrumento")),
                    "saldo": saldo,
                    "parcela": 0.0,
                    "carencia": 0,
                    "taxa": float(taxa),
                    "cronograma": _cronograma_do_instrumento(instrumento, prazo_lp),
                    "ano_corrente": 1,
                }
            )
        return tranches

    tranches = []
    divida_cp = float(ano0["divida_curto_prazo"])
    if divida_cp > 0:
        tranches.append(
            {
                "saldo": divida_cp,
                "parcela": divida_cp,
                "carencia": 0,
                "taxa": custo_divida_kd,
            }
        )
    divida_lp = float(ano0["divida_longo_prazo"])
    if divida_lp > 0:
        tranches.append(
            {
                "saldo": divida_lp,
                "parcela": divida_lp / prazo_lp,
                "carencia": 0,
                "taxa": custo_divida_kd,
            }
        )
    return tranches


def _parcela_da_tranche(tranche: dict[str, Any]) -> float:
    """Parcela devida no ano corrente (cronograma proprio ou parcela fixa)."""
    cronograma = tranche.get("cronograma")
    if isinstance(cronograma, dict):
        return float(cronograma.get(int(tranche.get("ano_corrente", 1)), 0.0))
    return float(tranche["parcela"])


def _amortizacao_do_ano(tranches: list[dict[str, Any]]) -> float:
    """Amortizacao devida no ano corrente (tranches fora de carencia)."""
    total = 0.0
    for tranche in tranches:
        if tranche["carencia"] > 0:
            continue
        total += min(_parcela_da_tranche(tranche), float(tranche["saldo"]))
    return total


def _juros_do_ano(
    tranches: list[dict[str, Any]],
    custo_divida_kd: float,
    usa_instrumentos: bool,
    divida_abertura: float,
) -> float:
    """Juros do ano sobre os saldos de ABERTURA (convencao D-015).

    Perfil agregado: formula v2 intacta (Kd x divida de abertura). Com
    instrumentos: soma taxa_i x saldo_abertura_i de cada tranche.
    """
    if not usa_instrumentos:
        # Formula: juros_t = Kd x divida de ABERTURA (byte-igual a v2).
        return custo_divida_kd * divida_abertura
    return sum(
        float(t.get("taxa", custo_divida_kd)) * float(t["saldo"]) for t in tranches
    )


def _aplicar_amortizacao(tranches: list[dict[str, Any]]) -> None:
    """Baixa as parcelas do ano e reduz a carencia das tranches novas."""
    for tranche in tranches:
        if tranche["carencia"] > 0:
            tranche["carencia"] = int(tranche["carencia"]) - 1
            if "ano_corrente" in tranche:
                tranche["ano_corrente"] = int(tranche["ano_corrente"]) + 1
            continue
        pago = min(_parcela_da_tranche(tranche), float(tranche["saldo"]))
        tranche["saldo"] = float(tranche["saldo"]) - pago
        if "ano_corrente" in tranche:
            tranche["ano_corrente"] = int(tranche["ano_corrente"]) + 1
    # Remove tranches quitadas para manter o schedule enxuto.
    tranches[:] = [t for t in tranches if float(t["saldo"]) > 1e-9]


def _saldo_total(tranches: list[dict[str, Any]]) -> float:
    """Saldo devedor total das tranches vivas."""
    return sum(float(t["saldo"]) for t in tranches)


def _cp_reclassificado(tranches: list[dict[str, Any]]) -> float:
    """CP no fechamento = amortizacao programada para o ANO SEGUINTE."""
    total = 0.0
    for tranche in tranches:
        if tranche["carencia"] > 1:
            continue
        cronograma = tranche.get("cronograma")
        if isinstance(cronograma, dict):
            proxima = float(cronograma.get(int(tranche.get("ano_corrente", 1)), 0.0))
        else:
            proxima = float(tranche["parcela"])
        total += min(proxima, float(tranche["saldo"]))
    return total


def calcular_dividendos(lucro_liquido: float, payout: float) -> float:
    """Calcula dividendos sem distribuir resultado negativo."""
    # Formula: dividendos_t = max(LL_t, 0) x payout.
    return max(lucro_liquido, 0.0) * payout


def projetar_divida_balanco_dfc(
    ano0: dict[str, Any],
    conteudo: dict[str, Any],
    dre: dict[str, dict[str, Any]],
    wk: dict[str, dict[str, Any]],
    ppe: dict[str, dict[str, Any]],
    custo_divida_kd: float,
    taxa_aplicacao: float,
    payout: float,
    usa_ret: bool,
    razao_receita_bruta: float | None,
    parametros: dict[str, float],
    modo_dre: str = "legado",
    contexto_ir_completo: dict[str, Any] | None = None,
    instrumentos: list[dict[str, Any]] | None = None,
) -> tuple[
    dict[str, dict[str, float | str]],
    dict[str, dict[str, float | str]],
    dict[str, dict[str, float | str]],
]:
    """Projeta divida, balanco e DFC integrados ano a ano (v2.0 + 9.0.2).

    Ordem dentro de cada ano (convencao de saldo inicial): juros e receita
    financeira sobre os saldos de abertura -> DRE (EBT, IR, LL, minoritarios)
    -> dividendos -> FCO/FCI -> teste do caixa minimo -> captacao (fim do
    ano) -> FCF -> caixa de fechamento via DFC -> balanco ABERTO verificado
    (contas do WK expandido + passivo de arrendamento como linha propria).
    """
    prazo_lp = int(parametros["prazo_amortizacao_lp_anos"])
    pct_caixa_minimo = float(parametros["caixa_minimo_pct_receita"])
    usa_instrumentos = bool(instrumentos)
    tranches = _montar_tranches_iniciais(
        ano0,
        prazo_lp,
        custo_divida_kd,
        instrumentos,
    )
    if usa_instrumentos:
        # Com a tabela de instrumentos, o estoque inicial e o dos proprios
        # instrumentos (ja em BRL). A troca acontece ANTES dos residuais:
        # qualquer diferenca para a divida do BP real fica EXPLICITA em
        # outros_passivos (o balanco segue fechando por construcao).
        ano0 = dict(ano0)
        saldo_instrumentos = _saldo_total(tranches)
        divida_bp = float(ano0["divida_bruta"])
        if divida_bp > 0 and abs(saldo_instrumentos - divida_bp) > 0.01 * divida_bp:
            logger.warning(
                "instrumentos_divida somam %.0f vs divida bruta do BP %.0f "
                "(diferenca vai para outros_passivos).",
                saldo_instrumentos,
                divida_bp,
            )
        ano0["divida_bruta"] = saldo_instrumentos
    wk_multi_driver = _wk_tem_multi_driver(wk)
    outros_ativos, outros_passivos = _residuais_balanco_ano0(
        ano0,
        conteudo,
        wk_multi_driver,
    )
    passivo_arrendamento_0 = abs(float(ano0.get("passivo_arrendamento") or 0.0))

    divida: dict[str, dict[str, float | str]] = {}
    balanco: dict[str, dict[str, float | str]] = {}
    dfc: dict[str, dict[str, float | str]] = {}

    divida_abertura = float(ano0["divida_bruta"])
    caixa_anterior = float(ano0["caixa_equivalentes"])
    aplicacoes = float(ano0["aplicacoes_financeiras"])
    patrimonio_liquido_anterior = float(ano0["patrimonio_liquido"])

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_dre = dre[chave_ano]
        linha_wk = wk[chave_ano]
        linha_ppe = ppe[chave_ano]

        receita_liquida = obter_float_obrigatorio(
            linha_dre,
            "receita_liquida",
            chave_ano,
        )
        ebit = obter_float_obrigatorio(linha_dre, "ebit", chave_ano)

        # Formula: juros_t = Kd x divida de ABERTURA (captacao do ano nao
        # paga juros no proprio ano — convencao sem circularidade). Com a
        # tabela de instrumentos, juros = soma(taxa_i x saldo_abertura_i).
        juros = _juros_do_ano(
            tranches,
            custo_divida_kd,
            usa_instrumentos,
            divida_abertura,
        )
        # Juros de arrendamento (IFRS-16) vem do schedule de leasing, SEPARADOS
        # dos juros de divida; 0 quando nao ha leasing relevante.
        juros_arrendamento = float(linha_dre.get("juros_arrendamento") or 0.0)
        # Formula: receita financeira_t = taxa x (caixa inicial + aplicacoes).
        receita_financeira = taxa_aplicacao * max(
            caixa_anterior + aplicacoes,
            0.0,
        )
        resultado_financeiro = receita_financeira - juros - juros_arrendamento

        # DRE recalculada com o resultado financeiro completo.
        linha_dre["resultado_financeiro"] = resultado_financeiro
        linha_dre["ebt"] = ebit + resultado_financeiro
        if modo_dre == "completo":
            # Cauda PRE-D&A (9.0.2): RET sobre a Receita BRUTA projetada >
            # vetor de aliquota ANUAL > efetiva > marginal; depois
            # minoritarios e LPA — mesma regra do projetor (fonte unica).
            recalcular_cauda_dre_completa(
                linha_dre,
                chave_ano,
                usa_ret,
                contexto_ir_completo or {},
            )
        else:
            linha_dre["ir_csll"] = calcular_ir_csll(
                ebt=float(linha_dre["ebt"]),
                receita_liquida=receita_liquida,
                usa_ret=usa_ret,
                razao_receita_bruta=razao_receita_bruta,
            )
            linha_dre["lucro_liquido"] = linha_dre["ebt"] + linha_dre["ir_csll"]
        lucro_liquido = float(linha_dre["lucro_liquido"])

        depreciacao = obter_float_obrigatorio(
            linha_ppe,
            "depreciacao_amortizacao",
            chave_ano,
        )
        delta_nwc = obter_float_obrigatorio(linha_wk, "delta_nwc", chave_ano)
        capex_assinado = obter_float_obrigatorio(linha_ppe, "capex", chave_ano)
        capex_saida_caixa = abs(capex_assinado)

        amortizacao = _amortizacao_do_ano(tranches)
        dividendos = calcular_dividendos(lucro_liquido, payout)

        # Formula DFC: FCO = LL + D&A - Delta NWC (juros/receita financeira
        # ja estao no LL); FCI = CAPEX (aplicacoes constantes).
        fco = lucro_liquido + depreciacao - delta_nwc
        fci = -capex_saida_caixa

        caixa_minimo = pct_caixa_minimo * receita_liquida
        caixa_pre_captacao = caixa_anterior + fco + fci - amortizacao - dividendos
        # Captacao no fim do ano cobre o deficit ate o caixa minimo.
        captacao = max(caixa_minimo - caixa_pre_captacao, 0.0)

        # Formula DFC: FCF = captacao - amortizacao - dividendos.
        fcf = captacao - amortizacao - dividendos
        variacao_caixa = fco + fci + fcf
        caixa = caixa_anterior + variacao_caixa

        _aplicar_amortizacao(tranches)
        if captacao > 0:
            # Captacao automatica v2: tranche linear com carencia de 1 ano,
            # sempre ao Kd (mesmo com tabela de instrumentos).
            tranches.append(
                {
                    "saldo": captacao,
                    "parcela": captacao / prazo_lp,
                    "carencia": 1,
                    "taxa": custo_divida_kd,
                }
            )

        divida_fechamento = _saldo_total(tranches)
        divida_curto = _cp_reclassificado(tranches)
        divida_longo = divida_fechamento - divida_curto
        delta_divida = divida_fechamento - divida_abertura
        saldo_medio = (divida_abertura + divida_fechamento) / 2

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
        # Intangivel projetado (linha propria, D-043; constante pos-D-047).
        intangivel = float(linha_ppe.get("intangivel") or 0.0)
        # Contas do WK EXPANDIDO (9.0.2): projetadas no modo multi-driver;
        # zero nos demais modos (os saldos do Ano 0 ficam nos residuais).
        tributos_a_recuperar = abs(float(linha_wk.get("tributos_a_recuperar") or 0.0))
        obrigacoes_trabalhistas = abs(
            float(linha_wk.get("obrigacoes_sociais_trabalhistas") or 0.0)
        )
        adiantamento_clientes = abs(float(linha_wk.get("adiantamento_clientes") or 0.0))

        ativo_total = (
            caixa
            + aplicacoes
            + contas_receber
            + estoques
            + tributos_a_recuperar
            + imobilizado
            + intangivel
            + outros_ativos
        )
        # Passivo de arrendamento: linha PROPRIA constante do Ano 0 (9.0.2;
        # rollforward informativo vive no bloco ``leasing`` — a integracao
        # dos fluxos de caixa do leasing e backlog).
        passivo_total = (
            fornecedores
            + obrigacoes_trabalhistas
            + adiantamento_clientes
            + divida_curto
            + divida_longo
            + passivo_arrendamento_0
            + outros_passivos
        )
        passivo_patrimonio_liquido = passivo_total + patrimonio_liquido
        # Verificacao (nao plug): com residuais do Ano 0 constantes e caixa
        # via DFC, a diferenca deve ser ~0 por construcao.
        diferenca = ativo_total - passivo_patrimonio_liquido

        divida[chave_ano] = {
            "ano_projecao": chave_ano,
            "politica_divida": POLITICA_DIVIDA,
            "custo_divida_kd": custo_divida_kd,
            "divida_abertura": divida_abertura,
            "amortizacao": amortizacao,
            "captacao": captacao,
            "divida_curto_prazo": divida_curto,
            "divida_longo_prazo": divida_longo,
            "divida_bruta": divida_fechamento,
            "saldo_medio_divida": saldo_medio,
            "base_juros": "saldo_inicial_do_ano",
            "juros": juros,
            "juros_arrendamento": juros_arrendamento,
            "receita_financeira_caixa": receita_financeira,
            "taxa_aplicacao_caixa": taxa_aplicacao,
            "resultado_financeiro": resultado_financeiro,
            "delta_divida": delta_divida,
        }
        balanco[chave_ano] = {
            "ano_projecao": chave_ano,
            "caixa_equivalentes": caixa,
            "aplicacoes_financeiras": aplicacoes,
            "contas_receber": contas_receber,
            "estoques": estoques,
            "tributos_a_recuperar": tributos_a_recuperar,
            "imobilizado": imobilizado,
            "intangivel": intangivel,
            "outros_ativos": outros_ativos,
            "ativo_total": ativo_total,
            "fornecedores": fornecedores,
            "obrigacoes_sociais_trabalhistas": obrigacoes_trabalhistas,
            "adiantamento_clientes": adiantamento_clientes,
            "divida_curto_prazo": divida_curto,
            "divida_longo_prazo": divida_longo,
            "passivo_arrendamento": passivo_arrendamento_0,
            "outros_passivos": outros_passivos,
            "passivo_total": passivo_total,
            "patrimonio_liquido": patrimonio_liquido,
            "passivo_patrimonio_liquido": passivo_patrimonio_liquido,
            "diferenca_balanco": diferenca,
            # Check visivel (Direcional ``Modelo`` L122): |Ativo - Passivo-PL|.
            "verificacao_balanco": abs(diferenca),
            "politica_caixa": POLITICA_CAIXA,
        }
        dfc[chave_ano] = {
            "ano_projecao": chave_ano,
            "lucro_liquido": lucro_liquido,
            "depreciacao_amortizacao": depreciacao,
            "delta_nwc": delta_nwc,
            "fco": fco,
            "capex": capex_assinado,
            "capex_saida_caixa": capex_saida_caixa,
            "fci": fci,
            "captacao": captacao,
            "amortizacao": amortizacao,
            "dividendos": dividendos,
            "fcf": fcf,
            "delta_divida": delta_divida,
            "variacao_caixa": variacao_caixa,
            "caixa_final": caixa,
            "caixa_minimo": caixa_minimo,
            # Compatibilidade v1 (Excel/graficos leem estes nomes).
            "fluxo_caixa_livre": fco + fci + delta_divida,
            "variacao_caixa_plug": variacao_caixa,
        }

        divida_abertura = divida_fechamento
        caixa_anterior = caixa
        patrimonio_liquido_anterior = patrimonio_liquido

    return divida, balanco, dfc


def validar_fechamento_balanco(
    balanco: dict[str, dict[str, float | str]],
    tolerancia_relativa: float = TOLERANCIA_FECHAMENTO_RELATIVA,
) -> bool:
    """VERIFICA o fechamento Ativo = Passivo + PL nos anos projetados.

    Na v2 o fechamento e verificacao, nao plug: desvio acima da tolerancia
    gera ALERTA (log + flag) e o checklist NF1 sinaliza — nunca derruba o
    pipeline silenciosamente.
    """
    fechado = True
    for chave_ano, linha in balanco.items():
        ativo_total = float(linha["ativo_total"])
        passivo_pl = float(linha["passivo_patrimonio_liquido"])
        diferenca = float(linha["diferenca_balanco"])
        escala = max(abs(ativo_total), abs(passivo_pl), 1.0)
        if abs(diferenca) > escala * tolerancia_relativa:
            fechado = False
            logger.warning(
                "ALERTA: balanco nao fecha em %s (diferenca=%s); "
                "verifique premissas e residuais do Ano 0.",
                chave_ano,
                diferenca,
            )
    return fechado


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
        "ativo_total": ano0_divida_balanco["ativo_total"],
        "participacao_nao_controladores": (
            ano0_divida_balanco["participacao_nao_controladores"]
        ),
        "investimentos_coligadas": ano0_divida_balanco["investimentos_coligadas"],
        "passivo_arrendamento": ano0_divida_balanco["passivo_arrendamento"],
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
    """Executa o schedule de divida v2 e verifica o balanco projetado."""
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
    premissas_completas = carregar_json(
        raiz / "data" / "premissas" / f"{ticker_normalizado}_premissas.json"
    )
    usa_ret = empresa_usa_ret(premissas_completas, metadados)
    razao_receita_bruta = (
        conteudo.get("politicas_projecao", {}).get("ret", {}).get("razao_receita_bruta")
    )
    razao_receita_bruta = _numero_ou_none(razao_receita_bruta)

    modo_dre = str(conteudo.get("modo_dre", "legado"))
    # Contexto tributario/minoritarios da DRE completa (fonte unica, 9.0.2).
    contexto_ir_completo = montar_contexto_ir_completo(conteudo)
    instrumentos = carregar_instrumentos_divida(premissas_completas)

    payout, origem_payout = resolver_payout(
        premissas_completas,
        metadados,
        parametros,
        raiz,
    )
    taxa_aplicacao, origem_taxa = resolver_taxa_aplicacao(
        premissas_completas,
        parametros,
        raiz,
    )

    divida, balanco, dfc = projetar_divida_balanco_dfc(
        ano0=ano0_divida_balanco,
        conteudo=conteudo,
        dre=dre,
        wk=wk,
        ppe=ppe,
        custo_divida_kd=premissas_divida["custo_divida_kd"],
        taxa_aplicacao=taxa_aplicacao,
        payout=payout,
        usa_ret=usa_ret,
        razao_receita_bruta=razao_receita_bruta,
        parametros=parametros,
        modo_dre=modo_dre,
        contexto_ir_completo=contexto_ir_completo,
        instrumentos=instrumentos,
    )
    fechamento_ok = validar_fechamento_balanco(balanco)
    politicas = {
        "politica_divida": POLITICA_DIVIDA,
        "politica_caixa": POLITICA_CAIXA,
        "instrumentos_divida": (
            f"{len(instrumentos)} instrumentos da premissa (taxa/cronograma "
            "proprios; captacao automatica ao Kd)"
            if instrumentos
            else "perfil_cp_lp_agregado"
        ),
        "payout_dividendos": payout,
        "origem_payout": origem_payout,
        "taxa_aplicacao_caixa": taxa_aplicacao,
        "origem_taxa_aplicacao": origem_taxa,
        "prazo_amortizacao_lp_anos": parametros["prazo_amortizacao_lp_anos"],
        "caixa_minimo_pct_receita": parametros["caixa_minimo_pct_receita"],
        "receita_financeira_sobre_caixa": True,
        "base_juros": "saldo_inicial_do_ano",
        "aplicacoes_financeiras": "constantes_no_saldo_do_ano0",
        "outros_ativos": "residual_do_bp_real_ano0_constante",
        "outros_passivos": "residual_do_bp_real_ano0_constante",
        "fechamento_ok": fechamento_ok,
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
        f"payout={politicas['payout_dividendos']:.2%} "
        f"({politicas['origem_payout']}) | "
        f"taxa aplicacao={politicas['taxa_aplicacao_caixa']:.2%}"
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
            projetar_leasing(ticker)
            resultado = projetar_divida(ticker)
            imprimir_fechamento_balanco(resultado)
        except Exception as erro:
            houve_falha = True
            print(f"\nFalha ao projetar divida de {ticker}: {erro}")

    if houve_falha:
        raise SystemExit(1)


if __name__ == "__main__":
    executar_validacao_padrao()
