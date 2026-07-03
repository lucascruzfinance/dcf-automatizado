"""Schedule de capital de giro para empresas nao financeiras."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        formatar_numero,
        normalizar_texto,
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
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        formatar_numero,
        normalizar_texto,
        normalizar_ticker,
        normalizar_valor_json,
        resolver_raiz,
        salvar_json,
        selecionar_ultimo_exercicio,
        valor_numerico_obrigatorio,
    )

DIAS_ANO = 365
CAMPOS_SALDO_WK = ("contas_receber", "estoques", "fornecedores")
MODO_DIAS = "dias"
MODO_PERCENTUAL_RECEITA = "percentual_receita"
TETO_DELTA_NWC_RECEITA_PADRAO = 0.50
EPSILON = 1e-12
CAMPOS_WK_PROJETADOS = (
    "ano_projecao",
    "contas_receber",
    "estoques",
    "fornecedores",
    "nwc",
    "delta_nwc",
    "modo_capital_giro",
)

logger = logging.getLogger(__name__)


def validar_nomes_mapeados_wk(raiz_projeto: Path) -> None:
    """Garante que os campos do schedule existem no mapeamento oficial."""
    caminho = raiz_projeto / "config" / "mapeamento_cvm.json"
    mapeamento = carregar_json(caminho)
    campos_mapeados = set(mapeamento.get("campos", {}))
    faltantes = sorted(set(CAMPOS_WK_PROJETADOS) - campos_mapeados)
    if faltantes:
        raise RuntimeError(
            "Campos de schedule WK ausentes em config/mapeamento_cvm.json: "
            + ", ".join(faltantes)
        )


def valor_dias_obrigatorio(premissas: dict[str, Any], campo: str) -> float:
    """Le uma premissa obrigatoria de prazo medio em dias."""
    valor = valor_numerico_obrigatorio(premissas, campo)
    if valor < 0:
        raise ValueError(f"Premissa de prazo nao pode ser negativa: {campo}")
    return valor


def extrair_premissas_dias(premissas: dict[str, Any]) -> dict[str, float]:
    """Extrai DSO, DIO e DPO para empresas de ciclo curto."""
    return {
        "dso": valor_dias_obrigatorio(premissas, "dso"),
        "dio": valor_dias_obrigatorio(premissas, "dio"),
        "dpo": valor_dias_obrigatorio(premissas, "dpo"),
    }


def carregar_premissas_wk(ticker: str, raiz_projeto: Path) -> dict[str, float]:
    """Carrega DSO, DIO e DPO do arquivo de premissas do ticker."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    premissas = carregar_json(caminho)
    return extrair_premissas_dias(premissas)


def premissas_tem_prazos(premissas: dict[str, Any]) -> bool:
    """Indica se o analista informou DSO, DIO e DPO."""
    return all(
        campo in premissas and premissas[campo] is not None
        for campo in ("dso", "dio", "dpo")
    )


def carregar_premissas_completas(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega o arquivo integral de premissas para premissas opcionais."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    return carregar_json(caminho)


def obter_teto_delta_nwc_receita(premissas: dict[str, Any]) -> float:
    """Le o teto de Delta NWC do ano 1 sobre receita, com default conservador."""
    valor = premissas.get(
        "teto_delta_nwc_receita",
        TETO_DELTA_NWC_RECEITA_PADRAO,
    )
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError("Premissa teto_delta_nwc_receita precisa ser numerica.")
    teto = float(valor)
    if teto <= 0:
        raise ValueError("Premissa teto_delta_nwc_receita precisa ser positiva.")
    return teto


def obter_modo_capital_giro(
    premissas: dict[str, Any],
    metadados: dict[str, Any],
) -> str:
    """Define o modo de projecao do capital de giro."""
    usa_modo_ancorado = empresa_usa_ret(premissas, metadados)
    modo_informado = normalizar_texto(premissas.get("modo_capital_giro"))
    modo_informado = modo_informado.replace("-", "_").replace(" ", "_")

    if modo_informado == MODO_PERCENTUAL_RECEITA:
        usa_modo_ancorado = True
    elif modo_informado and modo_informado != MODO_DIAS:
        raise ValueError(
            "Premissa modo_capital_giro invalida. Use 'dias' ou "
            "'percentual_receita'."
        )

    if usa_modo_ancorado:
        return MODO_PERCENTUAL_RECEITA
    if premissas_tem_prazos(premissas):
        return MODO_DIAS
    raise ValueError(
        "Premissas DSO/DIO/DPO ausentes para modo de capital de giro por dias."
    )


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
        obter_float_obrigatorio(dre[chave_ano], "receita_liquida", chave_ano)

    return caminho, conteudo, dre


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


def normalizar_fornecedores(valor: float) -> float:
    """Mantem fornecedores como passivo negativo na convencao do BP."""
    return -abs(valor)


def calcular_nwc(
    contas_receber: float,
    estoques: float,
    fornecedores: float,
) -> float:
    """Calcula NWC respeitando fornecedores como passivo negativo."""
    # Formula economica: NWC = contas_receber + estoques - fornecedores_abs.
    # Como fornecedores e salvo negativo no BP, a forma equivalente no projeto e:
    # NWC = contas_receber + estoques + fornecedores.
    return contas_receber + estoques + fornecedores


def carregar_ano0_wk(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega saldos historicos de WK do ultimo exercicio disponivel."""
    caminho = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_bp.json"
    dados = carregar_quadro_cvm(caminho)
    linhas = {campo: extrair_linha_ano0(dados, campo) for campo in CAMPOS_SALDO_WK}
    contas_receber = float(linhas["contas_receber"]["valor_padronizado"])
    estoques = float(linhas["estoques"]["valor_padronizado"])
    fornecedores = normalizar_fornecedores(
        float(linhas["fornecedores"]["valor_padronizado"])
    )
    nwc = calcular_nwc(contas_receber, estoques, fornecedores)

    linha_referencia = linhas["contas_receber"]
    return {
        "fonte": str(caminho.relative_to(raiz_projeto)),
        "ano_arquivo": normalizar_valor_json(linha_referencia.get("ano_arquivo")),
        "data_exercicio": normalizar_valor_json(linha_referencia.get("DT_FIM_EXERC")),
        "ordem_exercicio": normalizar_valor_json(linha_referencia.get("ORDEM_EXERC")),
        "contas_receber": contas_receber,
        "estoques": estoques,
        "fornecedores": fornecedores,
        "nwc": nwc,
    }


def margem_bruta_opcional(premissas: dict[str, Any], ano: int) -> float | None:
    """Busca margem bruta opcional anual ou unica, se o analista a informou."""
    for campo in (f"margem_bruta_ano{ano}", "margem_bruta"):
        if campo not in premissas or premissas[campo] is None:
            continue
        valor = premissas[campo]
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError(f"Premissa de margem bruta precisa ser numerica: {campo}")
        margem = float(valor)
        if margem < 0 or margem > 1:
            raise ValueError(f"Premissa de margem bruta fora de 0-1: {campo}")
        return margem
    return None


def carregar_indice_cpv_historico(
    ticker: str,
    raiz_projeto: Path,
) -> dict[str, Any] | None:
    """Calcula CPV/receita historico para projetar base de estoques e DPO."""
    caminho = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_dre.json"
    try:
        dados = carregar_quadro_cvm(caminho)
        linha_receita = extrair_linha_ano0(dados, "receita_liquida")
        linha_cpv = extrair_linha_ano0(dados, "cpv_cmv")
    except RuntimeError:
        return None

    receita = float(linha_receita["valor_padronizado"])
    cpv = abs(float(linha_cpv["valor_padronizado"]))
    if receita <= 0 or cpv <= 0:
        return None

    return {
        "fonte": str(caminho.relative_to(raiz_projeto)),
        "indice_cpv_receita": cpv / receita,
        "receita_base": receita,
        "cpv_base": cpv,
        "data_exercicio": normalizar_valor_json(linha_cpv.get("DT_FIM_EXERC")),
    }


def calcular_base_cpv(
    linha_dre: dict[str, Any],
    premissas: dict[str, Any],
    indice_cpv_historico: dict[str, Any] | None,
    ano: int,
) -> tuple[float, str]:
    """Define a base de CPV positiva para estoques e fornecedores."""
    receita_liquida = obter_float_obrigatorio(linha_dre, "receita_liquida", f"ano{ano}")

    if linha_dre.get("cpv_cmv") is not None:
        cpv_projetado = obter_float_obrigatorio(linha_dre, "cpv_cmv", f"ano{ano}")
        return abs(cpv_projetado), "dre.cpv_cmv"

    margem_bruta = margem_bruta_opcional(premissas, ano)
    if margem_bruta is not None:
        # Formula: CPV_t = Receita_t x (1 - margem_bruta_t).
        return receita_liquida * (1 - margem_bruta), "premissa.margem_bruta"

    if indice_cpv_historico is not None:
        # Formula: CPV_t = Receita_t x CPV_ano0 / Receita_ano0.
        indice = float(indice_cpv_historico["indice_cpv_receita"])
        return receita_liquida * indice, "historico.cpv_receita"

    # Fallback conservador: sem CPV ou margem bruta, usa receita como base de
    # giro para nao derrubar o pipeline. Isso tende a superestimar estoques e
    # fornecedores em negocios com margem bruta positiva.
    return receita_liquida, "proxy.receita_liquida"


def obter_receita_ano0(conteudo: dict[str, Any]) -> float:
    """Le a receita do Ano 0 ja persistida pela DRE."""
    ano0 = conteudo.get("ano0")
    if not isinstance(ano0, dict):
        raise RuntimeError("Bloco ano0 ausente na projecao.")
    receita = obter_float_obrigatorio(ano0, "receita_liquida", "ano0")
    if receita <= 0:
        raise ValueError("Receita liquida do ano0 precisa ser positiva.")
    return receita


def projetar_linha_por_dias(
    linha_dre: dict[str, Any],
    premissas_wk: dict[str, float],
    premissas_completas: dict[str, Any],
    indice_cpv_historico: dict[str, Any] | None,
    ano: int,
) -> tuple[float, float, float, float, str]:
    """Projeta uma linha de WK por DSO/DIO/DPO."""
    receita_liquida = obter_float_obrigatorio(linha_dre, "receita_liquida", f"ano{ano}")
    base_cpv, fonte_base_cpv = calcular_base_cpv(
        linha_dre,
        premissas_completas,
        indice_cpv_historico,
        ano,
    )

    # Formula: contas_receber_t = (DSO / 365) x receita_t.
    contas_receber = (premissas_wk["dso"] / DIAS_ANO) * receita_liquida

    # Formula: estoques_t = (DIO / 365) x base_cpv_t.
    estoques = (premissas_wk["dio"] / DIAS_ANO) * base_cpv

    # Formula economica: fornecedores_abs_t = (DPO / 365) x base_cpv_t.
    # O saldo e salvo negativo porque fornecedores e passivo no BP.
    fornecedores = -((premissas_wk["dpo"] / DIAS_ANO) * base_cpv)
    nwc = calcular_nwc(contas_receber, estoques, fornecedores)
    return contas_receber, estoques, fornecedores, nwc, fonte_base_cpv


def projetar_linha_por_percentual_receita(
    ano0_wk: dict[str, Any],
    receita_ano0: float,
    receita_liquida: float,
) -> tuple[float, float, float, float]:
    """Projeta WK preservando o percentual historico sobre receita."""
    fator_receita = receita_liquida / receita_ano0

    # Modo ancorado: escala a composicao historica do WK por receita.
    # Assim NWC_t = (NWC_ano0 / Receita_ano0) x Receita_t e construtoras
    # com estoque/recebiveis longos nao liberam capital de giro ficticio no ano 1.
    contas_receber = float(ano0_wk["contas_receber"]) * fator_receita
    estoques = float(ano0_wk["estoques"]) * fator_receita
    fornecedores = float(ano0_wk["fornecedores"]) * fator_receita
    nwc = calcular_nwc(contas_receber, estoques, fornecedores)
    return contas_receber, estoques, fornecedores, nwc


def ajustar_componentes_para_nwc(
    contas_receber: float,
    estoques: float,
    fornecedores: float,
    nwc_original: float,
    nwc_ajustado: float,
) -> tuple[float, float, float]:
    """Ajusta os componentes para manter a identidade de NWC."""
    if abs(nwc_original) > EPSILON and (nwc_original * nwc_ajustado) >= 0:
        fator = nwc_ajustado / nwc_original
        return contas_receber * fator, estoques * fator, fornecedores * fator

    fornecedores_ajustado = nwc_ajustado - contas_receber - estoques
    return contas_receber, estoques, fornecedores_ajustado


def aplicar_salvaguarda_delta_ano1(
    *,
    ticker: str,
    chave_ano: str,
    receita_liquida: float,
    nwc_anterior: float,
    contas_receber: float,
    estoques: float,
    fornecedores: float,
    nwc: float,
    teto_delta_nwc_receita: float,
) -> tuple[float, float, float, float, float]:
    """Trunca Delta NWC do ano 1 quando o salto e economicamente irreal."""
    delta_nwc = nwc - nwc_anterior
    if chave_ano != "ano1":
        return contas_receber, estoques, fornecedores, nwc, delta_nwc

    limite = teto_delta_nwc_receita * abs(receita_liquida)
    if abs(delta_nwc) <= limite:
        return contas_receber, estoques, fornecedores, nwc, delta_nwc

    delta_truncado = limite if delta_nwc > 0 else -limite
    nwc_ajustado = nwc_anterior + delta_truncado
    logger.warning(
        "%s: Delta NWC ano1 truncado de %.1f para %.1f " "(teto %.2fx receita ano1).",
        ticker,
        delta_nwc,
        delta_truncado,
        teto_delta_nwc_receita,
    )

    # O teto evita que o ano 1 carregue uma liberacao/consumo de caixa
    # artificial. Reescalamos os componentes para preservar a identidade:
    # NWC = contas_receber + estoques + fornecedores.
    contas_ajustada, estoques_ajustado, fornecedores_ajustado = (
        ajustar_componentes_para_nwc(
            contas_receber,
            estoques,
            fornecedores,
            nwc,
            nwc_ajustado,
        )
    )
    return (
        contas_ajustada,
        estoques_ajustado,
        fornecedores_ajustado,
        nwc_ajustado,
        delta_truncado,
    )


def projetar_linhas_wk(
    ticker: str,
    dre: dict[str, dict[str, Any]],
    premissas_wk: dict[str, float] | None,
    premissas_completas: dict[str, Any],
    indice_cpv_historico: dict[str, Any] | None,
    ano0_wk: dict[str, Any],
    receita_ano0: float,
    modo_capital_giro: str,
    teto_delta_nwc_receita: float,
) -> tuple[dict[str, dict[str, float | str]], dict[str, str]]:
    """Projeta contas de working capital de ano1 a ano8."""
    linhas = {}
    fontes_base_cpv = {}
    nwc_anterior = float(ano0_wk["nwc"])

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_dre = dre[chave_ano]
        receita_liquida = obter_float_obrigatorio(
            linha_dre,
            "receita_liquida",
            chave_ano,
        )

        if modo_capital_giro == MODO_DIAS:
            if premissas_wk is None:
                raise ValueError("Premissas DSO/DIO/DPO ausentes para modo por dias.")
            (
                contas_receber,
                estoques,
                fornecedores,
                nwc,
                fonte_base_cpv,
            ) = projetar_linha_por_dias(
                linha_dre,
                premissas_wk,
                premissas_completas,
                indice_cpv_historico,
                ano,
            )
        else:
            contas_receber, estoques, fornecedores, nwc = (
                projetar_linha_por_percentual_receita(
                    ano0_wk,
                    receita_ano0,
                    receita_liquida,
                )
            )
            fonte_base_cpv = "nao_aplicavel.percentual_receita"

        (
            contas_receber,
            estoques,
            fornecedores,
            nwc,
            delta_nwc,
        ) = aplicar_salvaguarda_delta_ano1(
            ticker=ticker,
            chave_ano=chave_ano,
            receita_liquida=receita_liquida,
            nwc_anterior=nwc_anterior,
            contas_receber=contas_receber,
            estoques=estoques,
            fornecedores=fornecedores,
            nwc=nwc,
            teto_delta_nwc_receita=teto_delta_nwc_receita,
        )

        linhas[chave_ano] = {
            "ano_projecao": chave_ano,
            "contas_receber": contas_receber,
            "estoques": estoques,
            "fornecedores": fornecedores,
            "nwc": nwc,
            "delta_nwc": delta_nwc,
            "modo_capital_giro": modo_capital_giro,
        }
        fontes_base_cpv[chave_ano] = fonte_base_cpv
        nwc_anterior = nwc

    return linhas, fontes_base_cpv


def atualizar_projecao_wk(
    caminho: Path,
    conteudo: dict[str, Any],
    ano0_wk: dict[str, Any],
    wk: dict[str, dict[str, float | str]],
) -> None:
    """Grava o schedule WK dentro da estrutura unica de projecao."""
    ano0 = conteudo.get("ano0")
    if not isinstance(ano0, dict):
        ano0 = {}
    ano0["wk"] = ano0_wk
    conteudo["ano0"] = ano0
    conteudo["wk"] = wk
    salvar_json(caminho, conteudo)


def projetar_wk(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Executa o schedule WK e persiste saldos projetados de capital de giro."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    validar_nomes_mapeados_wk(raiz)
    premissas_completas = carregar_premissas_completas(ticker_normalizado, raiz)
    metadados = carregar_metadados(ticker_normalizado, raiz)
    modo_capital_giro = obter_modo_capital_giro(premissas_completas, metadados)
    premissas_wk = (
        extrair_premissas_dias(premissas_completas)
        if modo_capital_giro == MODO_DIAS
        else None
    )
    teto_delta_nwc_receita = obter_teto_delta_nwc_receita(premissas_completas)
    caminho_projecao, conteudo, dre = carregar_projecao_existente(
        ticker_normalizado,
        raiz,
    )
    ano0_wk = carregar_ano0_wk(ticker_normalizado, raiz)
    receita_ano0 = obter_receita_ano0(conteudo)
    indice_cpv_historico = carregar_indice_cpv_historico(ticker_normalizado, raiz)
    wk, fontes_base_cpv = projetar_linhas_wk(
        ticker=ticker_normalizado,
        dre=dre,
        premissas_wk=premissas_wk,
        premissas_completas=premissas_completas,
        indice_cpv_historico=indice_cpv_historico,
        ano0_wk=ano0_wk,
        receita_ano0=receita_ano0,
        modo_capital_giro=modo_capital_giro,
        teto_delta_nwc_receita=teto_delta_nwc_receita,
    )
    atualizar_projecao_wk(caminho_projecao, conteudo, ano0_wk, wk)
    return {
        "ticker": ticker_normalizado,
        "premissas_wk": premissas_wk,
        "modo_capital_giro": modo_capital_giro,
        "teto_delta_nwc_receita": teto_delta_nwc_receita,
        "ano0_wk": ano0_wk,
        "wk": wk,
        "base_cpv_historica": indice_cpv_historico,
        "fontes_base_cpv": fontes_base_cpv,
        "caminho_saida": caminho_projecao,
    }


def imprimir_tabela_wk(resultado: dict[str, Any]) -> None:
    """Imprime tabela de NWC e Delta NWC para validacao visual."""
    ticker = resultado["ticker"]
    ano0_wk = resultado["ano0_wk"]
    wk = resultado["wk"]
    print("\n" + "=" * 120)
    print(f"Schedule WK - {ticker}")
    print(
        "Ano 0: "
        f"NWC={formatar_numero(float(ano0_wk['nwc']))} | "
        f"data={ano0_wk.get('data_exercicio')} | "
        f"fonte={ano0_wk.get('fonte')}"
    )
    print(f"Modo capital de giro: {resultado['modo_capital_giro']}")
    print("Delta NWC positivo = consumo de caixa; impacto no FCF = -Delta NWC.")

    cabecalho = (
        f"{'Ano':<6} {'Contas receber':>18} {'Estoques':>18} "
        f"{'Fornecedores':>18} {'NWC':>18} {'Delta NWC':>18} "
        f"{'Impacto caixa':>18}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for chave_ano, linha in wk.items():
        delta_nwc = float(linha["delta_nwc"])
        impacto_caixa = -delta_nwc
        print(
            f"{chave_ano:<6} "
            f"{formatar_numero(float(linha['contas_receber'])):>18} "
            f"{formatar_numero(float(linha['estoques'])):>18} "
            f"{formatar_numero(float(linha['fornecedores'])):>18} "
            f"{formatar_numero(float(linha['nwc'])):>18} "
            f"{formatar_numero(delta_nwc):>18} "
            f"{formatar_numero(impacto_caixa):>18}"
        )


def executar_validacao_padrao() -> None:
    """Executa o schedule WK para DIRR3 e MGLU3 ao rodar o arquivo direto."""
    houve_falha = False
    for ticker in ("DIRR3", "MGLU3"):
        try:
            resultado = projetar_wk(ticker)
            imprimir_tabela_wk(resultado)
        except Exception as erro:
            houve_falha = True
            print(f"\nFalha ao projetar WK de {ticker}: {erro}")

    if houve_falha:
        raise SystemExit(1)


if __name__ == "__main__":
    executar_validacao_padrao()
