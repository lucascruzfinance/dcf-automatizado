"""Calculador de WACC em BRL nominal com decomposicao completa.

Fluxo:
    Rf_USD (^TNX) -> Ke_USD (CAPM com beta re-alavancado por Hamada e CRP) ->
    Ke_BRL (diferencial de inflacao) -> Kd historico -> pesos E/V e D/V ->
    WACC = (E/V) x Ke_BRL + (D/V) x Kd x (1 - t).
"""

from __future__ import annotations

import logging
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

try:
    from src.coleta.coletor_mercado import converter_tnx_para_decimal
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        formatar_percentual,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.coleta.coletor_mercado import converter_tnx_para_decimal
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        formatar_percentual,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio

ALIQUOTA_IR_GERAL = 0.34
RF_USD_FALLBACK = 0.044
IPCA_LONGO_PRAZO_PADRAO = 0.035
CPI_EUA_LONGO_PRAZO_PADRAO = 0.020
ANOS_KD_HISTORICO = 3

logger = logging.getLogger(__name__)


def normalizar_texto(valor: Any) -> str:
    """Normaliza texto sem acentos para comparacoes defensivas."""
    texto = "" if valor is None else str(valor)
    texto = unicodedata.normalize("NFKD", texto)
    return texto.encode("ascii", "ignore").decode("ascii").strip().lower()


def ler_premissa_numerica(
    premissas: dict[str, Any],
    aliases: tuple[str, ...],
    *,
    padrao: float | None = None,
) -> float:
    """Le uma premissa numerica aceitando nomes alternativos (aliases).

    Mantem compatibilidade com premissas que usam nomes curtos (``beta``,
    ``erp``, ``crp``) e com o padrao canonico da Semana 3.
    """
    for alias in aliases:
        if alias in premissas and premissas[alias] is not None:
            valor = premissas[alias]
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ValueError(
                    f"Premissa precisa ser numerica: {alias}"
                )
            return float(valor)
    if padrao is not None:
        logger.warning(
            "Premissa ausente (%s); usando padrao %.4f",
            "/".join(aliases),
            padrao,
        )
        return padrao
    raise ValueError(
        "Premissa obrigatoria ausente. Aceito qualquer um de: "
        + ", ".join(aliases)
    )


def carregar_premissas_wacc(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega o arquivo de premissas do ticker."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    return carregar_json(caminho)


def carregar_blocos_projecao(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega a projecao integrada e valida os blocos usados pelo WACC."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    for bloco in ("divida", "balanco"):
        if not isinstance(conteudo.get(bloco), dict):
            raise RuntimeError(f"Bloco obrigatorio ausente em {caminho}: {bloco}")
    return conteudo


def obter_aliquota_ir(
    premissas: dict[str, Any],
    metadados: dict[str, Any],
) -> float:
    """Define a aliquota efetiva usada no escudo fiscal do WACC."""
    if empresa_usa_ret(premissas, metadados):
        return 0.0
    return ALIQUOTA_IR_GERAL


def calcular_medias_estrutura_capital(
    conteudo: dict[str, Any],
) -> tuple[float, float]:
    """Calcula divida bruta media e patrimonio liquido medio (anos 1-8)."""
    divida = conteudo["divida"]
    balanco = conteudo["balanco"]
    somas_divida = 0.0
    somas_pl = 0.0
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        somas_divida += abs(
            obter_float_obrigatorio(divida[chave_ano], "divida_bruta", chave_ano)
        )
        somas_pl += obter_float_obrigatorio(
            balanco[chave_ano], "patrimonio_liquido", chave_ano
        )
    divida_media = somas_divida / HORIZONTE_PROJECAO
    pl_medio = somas_pl / HORIZONTE_PROJECAO
    if pl_medio <= 0:
        raise ValueError(
            "Patrimonio liquido medio nao positivo: estrutura de capital "
            "invalida para calcular pesos e re-alavancagem."
        )
    return divida_media, pl_medio


def obter_rf_usd(rf_usd: float | None) -> float:
    """Obtem Rf em USD via ^TNX; usa fallback quando a coleta falhar.

    Se ``rf_usd`` for informado (injecao em testes), ele e usado diretamente.
    """
    if rf_usd is not None:
        return float(rf_usd)
    try:
        import yfinance as yf

        historico = yf.Ticker("^TNX").history(
            period="10d",
            interval="1d",
            auto_adjust=True,
        )
        serie = pd.to_numeric(historico["Close"], errors="coerce").dropna()
        if serie.empty:
            raise RuntimeError("historico ^TNX vazio")
        convertido = converter_tnx_para_decimal(float(serie.iloc[-1]))
        if convertido is None or convertido <= 0:
            raise RuntimeError("^TNX convertido invalido")
        return convertido
    except Exception as erro:  # pragma: no cover - depende de rede/API externa.
        logger.warning(
            "Falha ao coletar Rf via ^TNX (%s); usando fallback %.4f",
            erro,
            RF_USD_FALLBACK,
        )
        return RF_USD_FALLBACK


def _quadro_bruto_cvm(
    ticker: str,
    raiz_projeto: Path,
    demonstrativo: str,
) -> pd.DataFrame:
    """Carrega um JSON bruto da CVM em DataFrame."""
    caminho = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_{demonstrativo}.json"
    dados = pd.DataFrame(carregar_json(caminho))
    if dados.empty:
        raise RuntimeError(f"Base historica vazia: {caminho}")
    return dados


def serie_anual_historica(
    dados: pd.DataFrame,
    nome_padronizado: str,
    quantidade: int = ANOS_KD_HISTORICO,
) -> list[float]:
    """Extrai os ultimos exercicios anuais (31/12, ULTIMO) de uma conta.

    Filtra ruido de ITRs trimestrais e escolhe, por data de exercicio, o
    arquivo mais recente e a conta consolidada (menor CD_CONTA).
    """
    if "nome_padronizado" not in dados.columns:
        raise RuntimeError("Base historica sem coluna nome_padronizado.")

    selecao = dados[dados["nome_padronizado"] == nome_padronizado].copy()
    selecao = selecao[selecao["valor_padronizado"].notna()]
    if "ORDEM_EXERC" in selecao.columns:
        ordem = selecao["ORDEM_EXERC"].map(normalizar_texto)
        selecao = selecao[ordem == "ultimo"]

    selecao["_data"] = pd.to_datetime(selecao.get("DT_FIM_EXERC"), errors="coerce")
    selecao = selecao[selecao["_data"].notna()]
    selecao = selecao[
        (selecao["_data"].dt.month == 12) & (selecao["_data"].dt.day == 31)
    ]
    if selecao.empty:
        raise RuntimeError(
            f"Nenhum exercicio anual encontrado para {nome_padronizado}."
        )

    selecao["_ano_arquivo"] = pd.to_numeric(
        selecao.get("ano_arquivo"), errors="coerce"
    )
    if "CD_CONTA" in selecao.columns:
        selecao["_prioridade"] = selecao["CD_CONTA"].astype(str).str.len()
    else:
        selecao["_prioridade"] = 0

    valores_por_data: list[tuple[pd.Timestamp, float]] = []
    for data_exercicio, grupo in selecao.groupby("_data"):
        if grupo["_ano_arquivo"].notna().any():
            grupo = grupo[grupo["_ano_arquivo"] == grupo["_ano_arquivo"].max()]
        grupo = grupo.sort_values("_prioridade")
        valores_por_data.append(
            (data_exercicio, float(grupo.iloc[0]["valor_padronizado"]))
        )

    valores_por_data.sort(key=lambda item: item[0])
    return [valor for _, valor in valores_por_data[-quantidade:]]


def calcular_kd_historico(ticker: str, raiz_projeto: Path) -> float:
    """Kd historico = media(despesas financeiras) / media(divida bruta).

    Usa os ultimos exercicios anuais disponiveis (ate 3). Trabalha com
    magnitudes (abs) porque despesas e dividas sao armazenadas negativas.
    """
    dre = _quadro_bruto_cvm(ticker, raiz_projeto, "dre")
    bp = _quadro_bruto_cvm(ticker, raiz_projeto, "bp")

    despesas = serie_anual_historica(dre, "despesas_financeiras")
    divida_curto = serie_anual_historica(bp, "divida_curto_prazo")
    divida_longo = serie_anual_historica(bp, "divida_longo_prazo")

    if not despesas or not divida_curto or not divida_longo:
        raise RuntimeError("Historico insuficiente para calcular Kd historico.")

    media_despesas = sum(abs(valor) for valor in despesas) / len(despesas)
    quantidade_divida = min(len(divida_curto), len(divida_longo))
    divida_bruta = [
        abs(divida_curto[-quantidade_divida + indice])
        + abs(divida_longo[-quantidade_divida + indice])
        for indice in range(quantidade_divida)
    ]
    media_divida = sum(divida_bruta) / len(divida_bruta)
    if media_divida <= 0:
        raise ValueError("Divida bruta media historica nao positiva para Kd.")
    return media_despesas / media_divida


def calcular_wacc(
    ticker: str,
    raiz_projeto: Path | None = None,
    rf_usd: float | None = None,
    kd_historico: float | None = None,
) -> dict[str, Any]:
    """Calcula o WACC em BRL nominal e persiste a decomposicao completa.

    Parametros ``rf_usd`` e ``kd_historico`` permitem injetar valores em
    testes offline; quando ``None``, sao obtidos de ^TNX e dos dados brutos.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    premissas = carregar_premissas_wacc(ticker_normalizado, raiz)
    metadados = carregar_metadados(ticker_normalizado, raiz)
    conteudo = carregar_blocos_projecao(ticker_normalizado, raiz)

    rf = obter_rf_usd(rf_usd)
    if rf <= 0:
        raise ValueError(f"Rf em USD precisa ser positivo, recebido {rf}.")

    beta_desalavancado = ler_premissa_numerica(
        premissas, ("beta_desalavancado", "beta")
    )
    erp_eua = ler_premissa_numerica(premissas, ("erp_eua", "erp"))
    crp_brasil = ler_premissa_numerica(premissas, ("crp_brasil", "crp"))
    ipca = ler_premissa_numerica(
        premissas,
        ("ipca_longo_prazo", "ipca"),
        padrao=IPCA_LONGO_PRAZO_PADRAO,
    )
    cpi_eua = ler_premissa_numerica(
        premissas,
        ("cpi_eua_longo_prazo", "cpi_eua"),
        padrao=CPI_EUA_LONGO_PRAZO_PADRAO,
    )

    aliquota_ir = obter_aliquota_ir(premissas, metadados)
    divida_media, pl_medio = calcular_medias_estrutura_capital(conteudo)
    divida_sobre_equity = divida_media / pl_medio

    # Formula de Hamada: beta_L = beta_U x [1 + (D/E) x (1 - t)].
    beta_realavancado = beta_desalavancado * (
        1 + divida_sobre_equity * (1 - aliquota_ir)
    )

    # CAPM em USD com premio de risco Brasil (CRP).
    ke_usd = rf + beta_realavancado * (erp_eua + crp_brasil)

    # Diferencial de inflacao: converte o custo de equity de USD para BRL.
    ke_brl = ((1 + ke_usd) * (1 + ipca)) / (1 + cpi_eua) - 1

    if kd_historico is None:
        kd_historico = calcular_kd_historico(ticker_normalizado, raiz)
    kd_liquido = kd_historico * (1 - aliquota_ir)

    valor_total = pl_medio + divida_media
    peso_equity = pl_medio / valor_total
    peso_divida = 1 - peso_equity

    wacc = peso_equity * ke_brl + peso_divida * kd_liquido
    if wacc <= 0:
        raise ValueError(
            f"WACC nao positivo ({wacc:.4%}): reveja premissas de Ke, Kd e "
            "estrutura de capital."
        )

    resultado = {
        "ticker": ticker_normalizado,
        "rf_usd": rf,
        "beta_desalavancado": beta_desalavancado,
        "divida_media": divida_media,
        "patrimonio_liquido_medio": pl_medio,
        "divida_sobre_equity": divida_sobre_equity,
        "beta_realavancado": beta_realavancado,
        "erp_eua": erp_eua,
        "crp_brasil": crp_brasil,
        "ke_usd": ke_usd,
        "ipca": ipca,
        "cpi_eua": cpi_eua,
        "ke_brl": ke_brl,
        "kd_historico": kd_historico,
        "aliquota_ir": aliquota_ir,
        "kd_liquido": kd_liquido,
        "peso_equity": peso_equity,
        "peso_divida": peso_divida,
        "wacc": wacc,
    }

    conteudo["wacc"] = resultado
    caminho = raiz / "data" / "processed" / f"{ticker_normalizado}_projecao.json"
    salvar_json(caminho, conteudo)
    resultado["caminho_saida"] = caminho
    return resultado


def imprimir_decomposicao_wacc(resultado: dict[str, Any]) -> None:
    """Imprime a decomposicao completa do WACC para validacao visual."""
    print("\n" + "=" * 72)
    print(f"WACC (BRL nominal) - {resultado['ticker']}")
    print("-" * 72)
    linhas = [
        ("Rf USD (^TNX)", resultado["rf_usd"], "%"),
        ("Beta desalavancado", resultado["beta_desalavancado"], "x"),
        ("D/E (medio 1-8)", resultado["divida_sobre_equity"], "x"),
        ("Beta re-alavancado", resultado["beta_realavancado"], "x"),
        ("ERP EUA", resultado["erp_eua"], "%"),
        ("CRP Brasil", resultado["crp_brasil"], "%"),
        ("Ke USD", resultado["ke_usd"], "%"),
        ("IPCA LP", resultado["ipca"], "%"),
        ("CPI EUA LP", resultado["cpi_eua"], "%"),
        ("Ke BRL", resultado["ke_brl"], "%"),
        ("Kd historico", resultado["kd_historico"], "%"),
        ("Aliquota IR", resultado["aliquota_ir"], "%"),
        ("Kd liquido", resultado["kd_liquido"], "%"),
        ("Peso Equity (E/V)", resultado["peso_equity"], "%"),
        ("Peso Divida (D/V)", resultado["peso_divida"], "%"),
        ("WACC", resultado["wacc"], "%"),
    ]
    for rotulo, valor, unidade in linhas:
        if unidade == "%":
            texto = formatar_percentual(float(valor))
        else:
            texto = f"{float(valor):.4f}x"
        print(f"{rotulo:<24} {texto:>16}")


def main() -> None:
    """Executa o calculo padrao para DIRR3."""
    imprimir_decomposicao_wacc(calcular_wacc("DIRR3"))


if __name__ == "__main__":
    main()
