"""Bridge de valuation: EV -> Equity -> Target Price -> Upside -> Recomendacao.

EV = soma VP(FCFF 1-8) + VP(VT). O equity value ajusta o EV pela divida
liquida e itens nao operacionais na data-base (ano0). O target price divide o
equity pelas acoes fully diluted e o upside compara com o preco atual.
"""

from __future__ import annotations

import logging
import sys
import unicodedata
from pathlib import Path
from typing import Any

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

try:
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
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
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

LIMITE_COMPRA = 0.20
LIMITE_VENDA = -0.05

# Fatores para converter valores das demonstracoes (em MIL/MILHAO) para R$
# absolutos, alinhando a escala do equity com acoes e preco por acao.
FATORES_ESCALA_MOEDA = {
    "unidade": 1.0,
    "mil": 1_000.0,
    "milhao": 1_000_000.0,
    "milhares": 1_000.0,
    "milhoes": 1_000_000.0,
}

logger = logging.getLogger(__name__)


def _normalizar_texto(valor: Any) -> str:
    """Normaliza texto sem acentos para comparar rotulos de escala."""
    texto = "" if valor is None else str(valor)
    texto = unicodedata.normalize("NFKD", texto)
    return texto.encode("ascii", "ignore").decode("ascii").strip().lower()


def carregar_premissas_ev(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega o arquivo de premissas do ticker."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    return carregar_json(caminho)


def carregar_projecao_ev(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[Path, dict[str, Any]]:
    """Carrega a projecao integrada e valida os blocos usados pelo bridge."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    for bloco in ("fcff", "wacc", "valor_terminal", "ano0"):
        if not isinstance(conteudo.get(bloco), dict):
            raise RuntimeError(f"Bloco obrigatorio ausente em {caminho}: {bloco}")
    return caminho, conteudo


def obter_valor_opcional(
    dados: dict[str, Any],
    aliases: tuple[str, ...],
    *,
    padrao: float | None = None,
) -> float:
    """Le um valor numerico aceitando nomes alternativos, com padrao opcional."""
    for alias in aliases:
        if alias in dados and dados[alias] is not None:
            valor = dados[alias]
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ValueError(f"Valor precisa ser numerico: {alias}")
            return float(valor)
    if padrao is not None:
        return padrao
    raise ValueError(
        "Campo obrigatorio ausente. Aceito qualquer um de: " + ", ".join(aliases)
    )


def calcular_soma_vp_fcff(conteudo: dict[str, Any], wacc: float) -> float:
    """Soma os FCFF dos anos 1-8 descontados ao WACC."""
    fcff = conteudo["fcff"]
    soma = 0.0
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        fluxo = obter_float_obrigatorio(fcff[chave_ano], "fcff", chave_ano)
        # Formula: VP(FCFF_t) = FCFF_t / (1 + WACC)^t.
        soma += fluxo / (1 + wacc) ** ano
    return soma


def montar_ajustes_bridge(
    conteudo: dict[str, Any],
    premissas: dict[str, Any],
) -> dict[str, float]:
    """Monta os ajustes EV -> Equity a partir do balanco na data-base (ano0)."""
    ano0 = conteudo["ano0"]
    divida_ano0 = ano0.get("divida")
    balanco_ano0 = ano0.get("balanco")
    if not isinstance(divida_ano0, dict) or not isinstance(balanco_ano0, dict):
        raise RuntimeError("Bloco ano0 sem sub-blocos divida/balanco para o bridge.")

    divida_curto = obter_valor_opcional(
        divida_ano0, ("divida_curto_prazo", "divida_cp")
    )
    divida_longo = obter_valor_opcional(
        divida_ano0, ("divida_longo_prazo", "divida_lp")
    )
    leasing_ifrs16 = obter_valor_opcional(premissas, ("leasing_ifrs16",), padrao=0.0)
    caixa = obter_valor_opcional(balanco_ano0, ("caixa_equivalentes", "caixa"))
    aplicacoes = obter_valor_opcional(
        balanco_ano0, ("aplicacoes_financeiras",), padrao=0.0
    )
    minoritarios = obter_valor_opcional(
        balanco_ano0,
        ("participacoes_minoritarias", "participacao_nao_controladores"),
        padrao=0.0,
    )
    coligadas = obter_valor_opcional(
        balanco_ano0, ("investimentos_coligadas",), padrao=0.0
    )
    ativos_nao_operacionais = obter_valor_opcional(
        premissas, ("ativos_nao_operacionais",), padrao=0.0
    )

    divida_bruta = abs(divida_curto) + abs(divida_longo) + abs(leasing_ifrs16)
    return {
        "divida_bruta": divida_bruta,
        "leasing_ifrs16": abs(leasing_ifrs16),
        "caixa_equivalentes": caixa,
        "aplicacoes_financeiras": aplicacoes,
        "participacoes_minoritarias": abs(minoritarios),
        "investimentos_coligadas": coligadas,
        "ativos_nao_operacionais": ativos_nao_operacionais,
    }


def obter_acoes_fully_diluted(
    premissas: dict[str, Any],
    ticker: str,
    raiz_projeto: Path,
    acoes: float | None,
) -> float:
    """Obtem as acoes fully diluted; premissa manda, mercado e fallback."""
    if acoes is not None:
        valor = float(acoes)
    elif "acoes_fully_diluted" in premissas and (
        premissas["acoes_fully_diluted"] is not None
    ):
        valor = float(premissas["acoes_fully_diluted"])
    else:
        valor = _acoes_de_mercado(ticker, raiz_projeto)

    if valor is None or valor <= 0:
        raise ValueError(
            "acoes_fully_diluted ausente ou <= 0: informe em premissas "
            "(campo acoes_fully_diluted) ou colete os dados de mercado."
        )
    return valor


def _acoes_de_mercado(ticker: str, raiz_projeto: Path) -> float | None:
    """Le acoes em circulacao do JSON de mercado coletado, se existir."""
    caminho = raiz_projeto / "data" / "raw" / "mercado" / f"{ticker}_mercado.json"
    if not caminho.exists():
        return None
    dados = carregar_json(caminho)
    valor = dados.get("acoes_em_circulacao")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def obter_preco_atual(
    premissas: dict[str, Any],
    ticker: str,
    raiz_projeto: Path,
    preco_atual: float | None,
) -> float:
    """Obtem o preco atual: injecao > yfinance > mercado coletado > fallback."""
    if preco_atual is not None:
        return float(preco_atual)

    preco = _preco_yfinance(ticker)
    if preco is None:
        preco = _preco_de_mercado(ticker, raiz_projeto)
    if preco is None:
        preco = premissas.get("preco_atual_fallback")

    if preco is None or isinstance(preco, bool) or not isinstance(preco, (int, float)):
        raise ValueError(
            "Preco atual indisponivel: yfinance falhou e nao ha "
            "preco_atual_fallback nas premissas nem mercado coletado."
        )
    if float(preco) <= 0:
        raise ValueError(f"Preco atual precisa ser positivo, recebido {preco}.")
    return float(preco)


def _preco_yfinance(ticker: str) -> float | None:
    """Tenta obter o ultimo Close via yfinance (ticker + .SA)."""
    try:
        import pandas as pd
        import yfinance as yf

        simbolo = f"{ticker}.SA"
        historico = yf.Ticker(simbolo).history(
            period="10d",
            interval="1d",
            auto_adjust=True,
        )
        serie = pd.to_numeric(historico["Close"], errors="coerce").dropna()
        if serie.empty:
            return None
        return float(serie.iloc[-1])
    except Exception as erro:  # pragma: no cover - depende de rede/API externa.
        logger.warning("Falha ao obter preco via yfinance (%s).", erro)
        return None


def _preco_de_mercado(ticker: str, raiz_projeto: Path) -> float | None:
    """Le o preco atual do JSON de mercado coletado, se existir."""
    caminho = raiz_projeto / "data" / "raw" / "mercado" / f"{ticker}_mercado.json"
    if not caminho.exists():
        return None
    dados = carregar_json(caminho)
    valor = dados.get("preco_atual")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def obter_fator_escala_moeda(ticker: str, raiz_projeto: Path) -> float:
    """Detecta a escala das demonstracoes (ESCALA_MOEDA) e devolve o fator.

    As demonstracoes da CVM vem em MIL (ou MILHAO); acoes e preco estao em
    unidades absolutas. O fator converte o equity para R$ absolutos antes de
    dividir pelas acoes. Se a escala for desconhecida, assume 1.0 com aviso.
    """
    caminho = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_bp.json"
    if not caminho.exists():
        return 1.0
    registros = carregar_json(caminho)
    escalas = {
        _normalizar_texto(linha.get("ESCALA_MOEDA"))
        for linha in registros
        if isinstance(linha, dict) and linha.get("ESCALA_MOEDA")
    }
    if not escalas:
        return 1.0
    if len(escalas) > 1:
        logger.warning("Escalas de moeda divergentes em %s: %s", caminho, escalas)
    escala = next(iter(escalas))
    fator = FATORES_ESCALA_MOEDA.get(escala)
    if fator is None:
        logger.warning(
            "Escala de moeda desconhecida (%s) em %s; assumindo fator 1.0.",
            escala,
            caminho,
        )
        return 1.0
    return fator


def classificar_recomendacao(upside: float) -> str:
    """Classifica a recomendacao pela faixa de upside."""
    if upside > LIMITE_COMPRA:
        return "COMPRA"
    if upside < LIMITE_VENDA:
        return "VENDA"
    return "NEUTRO"


def calcular_ev(
    ticker: str,
    raiz_projeto: Path | None = None,
    preco_atual: float | None = None,
    acoes_fully_diluted: float | None = None,
    fator_escala_moeda: float | None = None,
) -> dict[str, Any]:
    """Executa o bridge completo e persiste o bloco ev_equity na projecao.

    Parametros ``preco_atual``, ``acoes_fully_diluted`` e ``fator_escala_moeda``
    permitem injecao em testes offline; quando ``None``, sao obtidos de
    premissas/mercado/yfinance e da ESCALA_MOEDA dos dados brutos.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    premissas = carregar_premissas_ev(ticker_normalizado, raiz)
    caminho, conteudo = carregar_projecao_ev(ticker_normalizado, raiz)

    wacc = obter_float_obrigatorio(conteudo["wacc"], "wacc", "wacc")
    vp_vt = obter_float_obrigatorio(
        conteudo["valor_terminal"], "vp_vt", "valor_terminal"
    )
    soma_vp_fcff = calcular_soma_vp_fcff(conteudo, wacc)
    ev = soma_vp_fcff + vp_vt

    ajustes = montar_ajustes_bridge(conteudo, premissas)

    # Bridge: Equity = EV - Divida Bruta + Caixa + Aplicacoes - Minoritarios
    #                  + Coligadas + Ativos Nao Operacionais.
    equity_value = (
        ev
        - ajustes["divida_bruta"]
        + ajustes["caixa_equivalentes"]
        + ajustes["aplicacoes_financeiras"]
        - ajustes["participacoes_minoritarias"]
        + ajustes["investimentos_coligadas"]
        + ajustes["ativos_nao_operacionais"]
    )

    acoes = obter_acoes_fully_diluted(
        premissas, ticker_normalizado, raiz, acoes_fully_diluted
    )
    if fator_escala_moeda is None:
        fator_escala_moeda = obter_fator_escala_moeda(ticker_normalizado, raiz)

    # Equity vem em MIL/MILHAO (escala CVM); converte para R$ absolutos antes
    # de dividir pelas acoes (que estao em unidades) para obter R$/acao.
    equity_absoluto = equity_value * fator_escala_moeda
    target_price = equity_absoluto / acoes

    preco = obter_preco_atual(premissas, ticker_normalizado, raiz, preco_atual)
    upside = target_price / preco - 1
    recomendacao = classificar_recomendacao(upside)

    resultado = {
        "ticker": ticker_normalizado,
        "ev": ev,
        "soma_vp_fcff": soma_vp_fcff,
        "vp_vt": vp_vt,
        "ajustes_bridge": ajustes,
        "equity_value": equity_value,
        "fator_escala_moeda": fator_escala_moeda,
        "equity_value_absoluto": equity_absoluto,
        "acoes_fully_diluted": acoes,
        "target_price": target_price,
        "preco_atual": preco,
        "upside": upside,
        "recomendacao": recomendacao,
    }

    conteudo["ev_equity"] = resultado
    salvar_json(caminho, conteudo)
    resultado["caminho_saida"] = caminho
    return resultado


def _linha_bridge(rotulo: str, valor: float, sinal: str) -> str:
    """Formata uma linha do bridge com sinal explicito."""
    return f"  {sinal} {rotulo:<32} R$ {formatar_numero(valor):>18}"


def imprimir_bridge(resultado: dict[str, Any]) -> None:
    """Imprime o bridge EV -> Equity -> Target Price linha a linha."""
    ajustes = resultado["ajustes_bridge"]
    print("\n" + "=" * 72)
    print(f"Bridge de Valuation - {resultado['ticker']}")
    print("-" * 72)
    print(_linha_bridge("Soma VP(FCFF) 1-8", resultado["soma_vp_fcff"], " "))
    print(_linha_bridge("VP(Valor Terminal)", resultado["vp_vt"], "+"))
    print(_linha_bridge("= Enterprise Value", resultado["ev"], "="))
    print(_linha_bridge("Divida Bruta (CP+LP+Leasing)", ajustes["divida_bruta"], "-"))
    print(_linha_bridge("Caixa e Equivalentes", ajustes["caixa_equivalentes"], "+"))
    print(
        _linha_bridge(
            "Aplicacoes Financeiras",
            ajustes["aplicacoes_financeiras"],
            "+",
        )
    )
    print(
        _linha_bridge(
            "Participacoes Minoritarias",
            ajustes["participacoes_minoritarias"],
            "-",
        )
    )
    print(
        _linha_bridge(
            "Investimentos em Coligadas",
            ajustes["investimentos_coligadas"],
            "+",
        )
    )
    print(
        _linha_bridge(
            "Ativos Nao Operacionais",
            ajustes["ativos_nao_operacionais"],
            "+",
        )
    )
    print(_linha_bridge("= Equity Value", resultado["equity_value"], "="))
    print("-" * 72)
    fator = resultado.get("fator_escala_moeda", 1.0)
    if fator != 1.0:
        print(f"  (equity convertido para R$ absolutos; escala x{fator:,.0f})")
    acoes_formatado = formatar_numero(resultado["acoes_fully_diluted"])
    print(f"  Acoes fully diluted : {acoes_formatado}")
    print(f"  Target Price        : R$ {formatar_numero(resultado['target_price'])}")
    print(f"  Preco Atual         : R$ {formatar_numero(resultado['preco_atual'])}")
    print(f"  Upside              : {formatar_percentual(resultado['upside'])}")
    print(f"  Recomendacao        : {resultado['recomendacao']}")


def main() -> None:
    """Executa o bridge padrao para DIRR3."""
    imprimir_bridge(calcular_ev("DIRR3"))


if __name__ == "__main__":
    main()
