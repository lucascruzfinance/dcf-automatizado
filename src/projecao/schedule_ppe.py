"""Schedule de PP&E e devolucao de D&A para a DRE projetada.

Modelo SIMPLES por instrucao de Lucas (17/07/2026, D-047): CAPEX = % da
receita (premissa anual) e D&A = taxa unica (1/vida_util_ppe_anos da config)
sobre o PP&E de ABERTURA. A D&A por safra de CAPEX com vida derivada do
historico (Prompt 8.2.3 original) foi descopada; o intangivel NAO amortiza
(saldo constante do Ano 0, linha propria do balanco). Permanecem do 8.2: o
split informativo capex expansao x manutencao e a D&A historica do Ano 0
persistida em ``ano0.ppe`` (insumo do prazo medio do schedule de leasing).
"""

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
        montar_contexto_ir_completo,
        normalizar_ticker,
        normalizar_valor_json,
        recalcular_cauda_dre_completa,
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
        montar_contexto_ir_completo,
        normalizar_ticker,
        normalizar_valor_json,
        recalcular_cauda_dre_completa,
        resolver_raiz,
        salvar_json,
        selecionar_ultimo_exercicio,
        valor_numerico_obrigatorio,
    )

CAMPO_VIDA_UTIL_PPE = "vida_util_ppe_anos"
CAMPO_CAPEX_EXPANSAO_PCT = "capex_expansao_pct"
CAPEX_EXPANSAO_PCT_PADRAO = 0.80


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
    """Carrega parametros globais usados pelo schedule PP&E."""
    caminho = raiz_projeto / "config" / "parametros.json"
    parametros = carregar_json(caminho)
    valor = parametros.get(CAMPO_VIDA_UTIL_PPE)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"Parametro obrigatorio invalido: {CAMPO_VIDA_UTIL_PPE}")

    vida_util_anos = float(valor)
    if vida_util_anos <= 0:
        raise ValueError(f"Parametro precisa ser positivo: {CAMPO_VIDA_UTIL_PPE}")

    capex_split = parametros.get("capex_split", {})
    return {
        "vida_util_ppe_anos": vida_util_anos,
        # Formula: taxa D&A = 1 / vida util (modelo simples, D-047).
        "taxa_depreciacao_ppe": 1 / vida_util_anos,
        "capex_expansao_pct_padrao": float(
            capex_split.get("capex_expansao_pct_padrao", CAPEX_EXPANSAO_PCT_PADRAO)
        ),
    }


def resolver_vida_util_ppe(
    premissas: dict[str, Any],
    metadados: dict[str, Any],
    raiz_projeto: Path,
    vida_util_config: float,
) -> tuple[float, str]:
    """Vida util do PP&E: premissa da empresa > subtipo > config global.

    Decisao D-047 preservada: a vida NUNCA e derivada do historico — a taxa
    usada vem sempre de premissa/config (a D&A% historica fica so como
    informacao exibivel, Direcional ``Modelo`` L202).
    """
    valor = premissas.get(CAMPO_VIDA_UTIL_PPE)
    if (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and float(valor) > 0
    ):
        return float(valor), "premissa_da_empresa"

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
            valor_subtipo = defaults.get(CAMPO_VIDA_UTIL_PPE)
            if (
                isinstance(valor_subtipo, (int, float))
                and not isinstance(valor_subtipo, bool)
                and float(valor_subtipo) > 0
            ):
                return float(valor_subtipo), f"default_do_subtipo_{subtipo}"

    return vida_util_config, "parametro_global"


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
    """|D&A| historica do Ano 0 via DFC (insumo do prazo medio do leasing)."""
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
        # INFORMATIVO (Direcional ``Modelo`` L202): D&A% historica implicita.
        # A taxa USADA e sempre a da premissa/config (D-047 — nunca derivada).
        "da_pct_ppe_historica": (
            da_historica / imobilizado if imobilizado > 0 else None
        ),
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


def resolver_capex_expansao_padrao(
    metadados: dict[str, Any],
    raiz_projeto: Path,
    padrao_global: float,
) -> tuple[float, str]:
    """Default do split expansao: subtipo (setores.json) > parametro global."""
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
            valor = defaults.get(CAMPO_CAPEX_EXPANSAO_PCT)
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                if 0 <= valor <= 1:
                    return float(valor), f"default_do_subtipo_{subtipo}"
    return padrao_global, "parametro_global"


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
    taxa_depreciacao: float,
) -> dict[str, dict[str, float | str]]:
    """Projeta CAPEX, D&A e PP&E de ano1 a ano8 (modelo simples, D-047).

    CAPEX = % da receita (premissa anual); D&A do imobilizado = taxa unica
    (1/vida da config) sobre o PP&E de ABERTURA. O intangivel NAO amortiza
    (``da_intangivel = 0``; saldo do Ano 0 constante, linha propria do
    balanco). Capex split expansao x manutencao e informativo (nao muda o
    capex total). A D&A do direito de uso e RECLASSIFICADA depois pelo
    schedule de leasing, dentro do mesmo total (D-042).
    """
    linhas = {}
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

        # Formula: D&A_t = taxa x PP&E_(t-1), limitada a base disponivel.
        da_imobilizado = calcular_depreciacao_amortizacao(
            imobilizado_anterior=imobilizado_anterior,
            capex=capex,
            taxa_depreciacao=taxa_depreciacao,
        )

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
            "da_imobilizado": da_imobilizado,
            "da_intangivel": 0.0,
            "depreciacao_amortizacao": da_imobilizado,
            "imobilizado": imobilizado,
            "intangivel": intangivel_ano0,
        }
        imobilizado_anterior = imobilizado

    return linhas


def atualizar_dre_com_depreciacao(
    dre: dict[str, dict[str, Any]],
    ppe: dict[str, dict[str, float | str]],
    usa_ret: bool,
    modo_dre: str = "legado",
    contexto_ir_completo: dict[str, Any] | None = None,
) -> None:
    """Fecha a D&A da DRE com o schedule PP&E (imobilizado + intangivel).

    A D&A do direito de uso (``da_direito_uso``) e preservada como esta no
    momento (0 quando o leasing ainda nao rodou; o schedule de leasing a
    preenche e RE-TOTALIZA depois). D&A total = imobilizado + intangivel +
    direito de uso. Modo LEGADO: EBIT = EBITDA - D&A total e recalcula
    EBT/IR/LL. Modo COMPLETO (PRE-D&A, Prompt 9.0.2): EBIT = EBIT
    ex-Depreciacao - D&A total (a D&A e linha PROPRIA, nao esta nas
    margens); EBITDA = EBIT ex-Depreciacao (invariante); recalcula
    EBT -> IR (aliquota anual/RET) -> minoritarios -> LL -> LPA.
    """
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_dre = dre[chave_ano]
        linha_ppe = ppe[chave_ano]
        da_imobilizado = obter_float_obrigatorio(
            linha_ppe,
            "da_imobilizado",
            chave_ano,
        )
        da_intangivel = obter_float_obrigatorio(linha_ppe, "da_intangivel", chave_ano)
        da_direito_uso = float(linha_dre.get("da_direito_uso") or 0.0)
        da_total = da_imobilizado + da_intangivel + da_direito_uso

        linha_dre["da_imobilizado"] = da_imobilizado
        linha_dre["da_intangivel"] = da_intangivel
        linha_dre["depreciacao_amortizacao"] = da_total

        if modo_dre == "completo":
            ebit_ex_depreciacao = obter_float_obrigatorio(
                linha_dre,
                "ebit_ex_depreciacao",
                chave_ano,
            )
            # Formula: EBIT = EBIT ex-Depreciacao - D&A total (linha propria).
            linha_dre["ebit"] = ebit_ex_depreciacao - da_total
            # Memo: EBITDA = EBIT ex-Depreciacao (nao muda com a D&A).
            linha_dre["ebitda"] = ebit_ex_depreciacao
            resultado_financeiro = float(linha_dre.get("resultado_financeiro") or 0.0)
            linha_dre["ebt"] = float(linha_dre["ebit"]) + resultado_financeiro
            recalcular_cauda_dre_completa(
                linha_dre,
                chave_ano,
                usa_ret,
                contexto_ir_completo or {},
            )
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

        # Formula: EBIT = EBITDA - D&A total; recalcula EBT/IR/LL (a D&A reduz
        # o lucro no modo legado). O leasing e a divida refinam depois.
        linha_dre["ebit"] = ebitda - da_total
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
    # Vida util com override (9.0.2): premissa > subtipo > config global.
    vida_util, origem_vida_util = resolver_vida_util_ppe(
        premissas=premissas_completas,
        metadados=metadados,
        raiz_projeto=raiz,
        vida_util_config=parametros["vida_util_ppe_anos"],
    )
    parametros["vida_util_ppe_anos"] = vida_util
    parametros["taxa_depreciacao_ppe"] = 1 / vida_util
    parametros["origem_vida_util"] = origem_vida_util
    capex_expansao_padrao, origem_capex_expansao = resolver_capex_expansao_padrao(
        metadados=metadados,
        raiz_projeto=raiz,
        padrao_global=parametros["capex_expansao_pct_padrao"],
    )
    capex_expansao_pcts = carregar_capex_expansao_pcts(
        premissas_completas,
        capex_expansao_padrao,
    )
    ppe = projetar_linhas_ppe(
        dre=dre,
        taxas_capex_receita=taxas_capex_receita,
        capex_expansao_pcts=capex_expansao_pcts,
        imobilizado_ano0=float(ano0_ppe["imobilizado"]),
        intangivel_ano0=float(ano0_ppe.get("intangivel", 0.0)),
        taxa_depreciacao=parametros["taxa_depreciacao_ppe"],
    )
    atualizar_dre_com_depreciacao(
        dre=dre,
        ppe=ppe,
        usa_ret=empresa_usa_ret(premissas_completas, metadados),
        modo_dre=modo_dre,
        contexto_ir_completo=montar_contexto_ir_completo(conteudo),
    )
    atualizar_projecao_ppe(caminho_projecao, conteudo, ano0_ppe, ppe)
    return {
        "ticker": ticker_normalizado,
        "parametros_ppe": parametros,
        "origem_capex_expansao_padrao": origem_capex_expansao,
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
