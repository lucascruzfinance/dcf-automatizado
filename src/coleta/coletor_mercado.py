"""Coleta de dados de mercado via yfinance."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
MESES_BETA = 60


def resolver_raiz(raiz_projeto: Path | None = None) -> Path:
    """Devolve a raiz do projeto, permitindo override em testes."""
    if raiz_projeto is None:
        return RAIZ_PROJETO
    return Path(raiz_projeto)


def configurar_logger(raiz_projeto: Path) -> logging.Logger:
    """Configura log de coleta sem duplicar handlers."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    caminho_log = raiz_projeto / "logs" / "coletor_mercado.log"
    caminho_log.parent.mkdir(parents=True, exist_ok=True)
    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == caminho_log
        for handler in logger.handlers
    ):
        handler = logging.FileHandler(caminho_log, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def configurar_cache_yfinance(raiz_projeto: Path) -> None:
    """Direciona caches do yfinance para pasta gravavel no workspace."""
    caminho_cache = raiz_projeto / ".cache" / "yfinance"
    caminho_cache.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(caminho_cache))


def normalizar_ticker(ticker: str) -> str:
    """Normaliza ticker B3 removendo sufixo de bolsa e padronizando caixa."""
    return ticker.upper().replace(".SA", "").strip()


def ticker_yfinance_b3(ticker: str) -> str:
    """Converte ticker B3 para o simbolo usado pelo yfinance."""
    ticker_normalizado = normalizar_ticker(ticker)
    return f"{ticker_normalizado}.SA"


def salvar_json(caminho: Path, conteudo: dict[str, Any]) -> None:
    """Salva JSON com indentacao estavel."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False, indent=2)


def historico_fechamento(
    simbolo: str,
    periodo: str,
    intervalo: str,
    logger: logging.Logger,
) -> pd.Series:
    """Coleta serie de fechamento ajustado quando disponivel."""
    try:
        historico = yf.Ticker(simbolo).history(
            period=periodo,
            interval=intervalo,
            auto_adjust=True,
        )
    except Exception as erro:  # pragma: no cover - depende de rede/API externa.
        logger.exception("Falha ao coletar historico de %s: %s", simbolo, erro)
        return pd.Series(dtype="float64")

    if historico.empty or "Close" not in historico.columns:
        logger.warning("Historico vazio ou sem Close para %s", simbolo)
        return pd.Series(dtype="float64")

    return pd.to_numeric(historico["Close"], errors="coerce").dropna()


def obter_preco_atual(simbolo: str, logger: logging.Logger) -> float | None:
    """Obtem o ultimo fechamento disponivel."""
    serie = historico_fechamento(simbolo, "10d", "1d", logger)
    if serie.empty:
        logger.warning("Preco atual indisponivel para %s", simbolo)
        return None
    return float(serie.iloc[-1])


def obter_faixa_52_semanas(
    simbolo: str,
    logger: logging.Logger,
) -> tuple[float | None, float | None]:
    """Obtem minima e maxima de fechamento das ultimas 52 semanas."""
    serie = historico_fechamento(simbolo, "1y", "1d", logger)
    if serie.empty:
        logger.warning("Faixa de 52 semanas indisponivel para %s", simbolo)
        return None, None
    return float(serie.min()), float(serie.max())


def obter_info_yfinance(simbolo: str, logger: logging.Logger) -> dict[str, Any]:
    """Coleta o dicionario info sem interromper o pipeline em falhas."""
    try:
        ticker = yf.Ticker(simbolo)
        if hasattr(ticker, "get_info"):
            return dict(ticker.get_info())
        return dict(ticker.info)
    except Exception as erro:  # pragma: no cover - depende de rede/API externa.
        logger.exception("Falha ao coletar info de %s: %s", simbolo, erro)
        return {}


def calcular_beta_rolling(
    simbolo_ativo: str,
    logger: logging.Logger,
) -> float | None:
    """Calcula beta mensal do ativo contra o Ibovespa usando ate 60 meses."""
    ativo = historico_fechamento(simbolo_ativo, "7y", "1mo", logger)
    ibovespa = historico_fechamento("^BVSP", "7y", "1mo", logger)
    if ativo.empty or ibovespa.empty:
        logger.warning("Beta incalculavel por historico vazio: %s", simbolo_ativo)
        return None

    dados = pd.concat({"ativo": ativo, "mercado": ibovespa}, axis=1).dropna()
    retornos = dados.pct_change().dropna().tail(MESES_BETA)
    if len(retornos) < 2:
        logger.warning(
            "Beta incalculavel por retornos insuficientes: %s", simbolo_ativo
        )
        return None
    if len(retornos) < MESES_BETA:
        logger.warning(
            "Beta de %s calculado com %s meses, abaixo dos 60 pedidos.",
            simbolo_ativo,
            len(retornos),
        )

    variancia_mercado = retornos["mercado"].var()
    if variancia_mercado == 0 or pd.isna(variancia_mercado):
        logger.warning("Beta incalculavel por variancia nula do mercado.")
        return None

    return float(retornos["ativo"].cov(retornos["mercado"]) / variancia_mercado)


def converter_tnx_para_decimal(fechamento_tnx: float | None) -> float | None:
    """Converte a cotacao do ^TNX para taxa decimal anual."""
    if fechamento_tnx is None:
        return None
    if fechamento_tnx > 20:
        return fechamento_tnx / 1000
    if fechamento_tnx > 1:
        return fechamento_tnx / 100
    return fechamento_tnx


def coletar_mercado(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Coleta preco, beta, acoes, market cap e T-Bond 10Y via yfinance."""
    raiz = resolver_raiz(raiz_projeto)
    logger = configurar_logger(raiz)
    configurar_cache_yfinance(raiz)
    ticker_normalizado = normalizar_ticker(ticker)
    simbolo = ticker_yfinance_b3(ticker_normalizado)

    preco_atual = obter_preco_atual(simbolo, logger)
    preco_minimo_52s, preco_maximo_52s = obter_faixa_52_semanas(simbolo, logger)
    beta = calcular_beta_rolling(simbolo, logger)
    info = obter_info_yfinance(simbolo, logger)
    acoes = info.get("sharesOutstanding")
    if isinstance(acoes, bool) or not isinstance(acoes, (int, float)):
        logger.warning("Acoes em circulacao indisponiveis para %s", simbolo)
        acoes = None

    market_cap = info.get("marketCap")
    if isinstance(market_cap, bool) or not isinstance(market_cap, (int, float)):
        market_cap = preco_atual * acoes if preco_atual is not None and acoes else None
        if market_cap is None:
            logger.warning("Market cap indisponivel para %s", simbolo)

    fechamento_tnx = obter_preco_atual("^TNX", logger)
    rf_usd = converter_tnx_para_decimal(fechamento_tnx)

    resultado = {
        "ticker": ticker_normalizado,
        "ticker_yfinance": simbolo,
        "preco_atual": preco_atual,
        "preco_minimo_52s": preco_minimo_52s,
        "preco_maximo_52s": preco_maximo_52s,
        "beta_calculado": beta,
        "acoes_em_circulacao": None if acoes is None else float(acoes),
        "market_cap": None if market_cap is None else float(market_cap),
        "rf_usd_tbond10y": rf_usd,
        "data_coleta": datetime.now(timezone.utc).isoformat(),
    }
    caminho = raiz / "data" / "raw" / "mercado" / f"{ticker_normalizado}_mercado.json"
    salvar_json(caminho, resultado)
    return resultado


def imprimir_resumo(resultado: dict[str, Any]) -> None:
    """Imprime resumo compacto da coleta de mercado."""
    print(
        f"{resultado['ticker']}: "
        f"preco={resultado['preco_atual']} | "
        f"beta={resultado['beta_calculado']} | "
        f"acoes={resultado['acoes_em_circulacao']} | "
        f"market_cap={resultado['market_cap']} | "
        f"rf_usd={resultado['rf_usd_tbond10y']}"
    )


def main() -> None:
    """Executa a coleta padrao para os tickers da v1.0."""
    for ticker in ("DIRR3", "MGLU3"):
        imprimir_resumo(coletar_mercado(ticker))


if __name__ == "__main__":
    main()
