"""Pipeline universal por ticker (v2.0, Onda 4): coleta -> motor -> comps.

Orquestrador reutilizavel pelo app Streamlit e por scripts: dado QUALQUER
ticker da B3, executa coleta CVM (com cache), limpeza Parquet, relatorio de
qualidade, dados de mercado, metricas historicas, premissas automaticas de
partida (quando o analista ainda nao tem premissas), o motor de valuation
CORRETO por tipo (FCFF/WACC ou FCFE/Ke), comparaveis reais e cenarios.

O app nao reimplementa nada disso: chama ``rodar_pipeline_universal`` e
apresenta os JSONs persistidos (fonte unica de verdade no motor).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

from src.coleta.coletor_cvm import coletar_empresa
from src.coleta.coletor_mercado import coletar_mercado
from src.coleta.relatorio_qualidade import gerar_relatorio_qualidade
from src.metricas.metricas_historicas import calcular_metricas_historicas
from src.metricas.qualidade_lucro import calcular_qualidade_lucro
from src.processamento.limpeza import limpar_empresa
from src.projecao.gerador_premissas import gerar_premissas_automaticas
from src.projecao.projetor_dre import (
    carregar_json,
    normalizar_ticker,
    projetar_dre,
    resolver_raiz,
)
from src.projecao.projetor_financeiro import projetar_financeiro
from src.projecao.schedule_divida import projetar_divida
from src.projecao.schedule_leasing import projetar_leasing
from src.projecao.schedule_ppe import projetar_ppe
from src.projecao.schedule_wk import projetar_wk
from src.valuation.calculador_ev import calcular_ev
from src.valuation.calculador_fcfe import calcular_fcfe_financeira
from src.valuation.calculador_fcff import calcular_fcff
from src.valuation.calculador_vt import calcular_valor_terminal
from src.valuation.calculador_wacc import calcular_ke, calcular_wacc
from src.exportacao.exportador_bi import exportar_fato_comparaveis
from src.valuation.checklist import executar_checklist
from src.valuation.comparaveis import gerar_comparaveis
from src.valuation.motor_cenarios import executar_cenarios

logger = logging.getLogger(__name__)

CallbackStatus = Callable[[str], None]


def _avisar(callback: CallbackStatus | None, mensagem: str) -> None:
    """Propaga o status da etapa para o chamador (ex.: st.status do app)."""
    logger.info(mensagem)
    if callback is not None:
        callback(mensagem)


def _dados_cvm_existem(ticker: str, raiz: Path) -> bool:
    """True quando os JSONs brutos obrigatorios do ticker ja existem."""
    pasta = raiz / "data" / "raw" / "cvm"
    return (
        all(
            (pasta / f"{ticker}_{demonstracao}.json").exists()
            for demonstracao in ("dre", "bp", "dfc")
        )
        and (pasta / f"{ticker}_meta.json").exists()
    )


def _mercado_existe(ticker: str, raiz: Path) -> bool:
    """True quando o JSON de mercado do ticker ja foi coletado."""
    return (raiz / "data" / "raw" / "mercado" / f"{ticker}_mercado.json").exists()


def rodar_motor_valuation(
    ticker: str,
    raiz: Path,
    callback: CallbackStatus | None = None,
) -> dict[str, Any]:
    """Roda apenas o MOTOR (sem recoletar), pelo metodo correto do tipo.

    Usado pelo app ao salvar premissas: injeta Rf e preco dos JSONs de
    mercado persistidos para nao depender de rede nem de preco vivo.
    """
    meta = carregar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json")
    financeira = str(meta.get("tipo")) == "financeira"
    caminho_mercado = raiz / "data" / "raw" / "mercado" / f"{ticker}_mercado.json"
    mercado = carregar_json(caminho_mercado) if caminho_mercado.exists() else {}
    rf = mercado.get("rf_usd_tbond10y")
    preco = mercado.get("preco_atual")

    if financeira:
        _avisar(callback, "Projetando DRE bancaria e capital regulatorio...")
        projetar_financeiro(ticker, raiz)
        _avisar(callback, "Calculando Ke (CAPM Brasil)...")
        calcular_ke(ticker, raiz, rf_usd=rf)
        _avisar(callback, "Valuation FCFE e valor terminal...")
        calcular_fcfe_financeira(ticker, raiz, preco_atual=preco)
    else:
        _avisar(callback, "Projetando DRE, WK, PP&E, leasing e divida...")
        projetar_dre(ticker, raiz)
        projetar_wk(ticker, raiz)
        projetar_ppe(ticker, raiz)
        projetar_leasing(ticker, raiz)
        projetar_divida(ticker, raiz)
        _avisar(callback, "FCFF, WACC, valor terminal e bridge...")
        calcular_fcff(ticker, raiz)
        calcular_wacc(ticker, raiz, rf_usd=rf)
        calcular_valor_terminal(ticker, raiz)
        calcular_ev(ticker, raiz, preco_atual=preco)

    _avisar(callback, "Checklist de consistencia...")
    return executar_checklist(ticker, raiz)


def rodar_pipeline_universal(
    ticker: str,
    raiz_projeto: Path | None = None,
    forcar_recoleta: bool = False,
    com_cenarios: bool = True,
    com_comparaveis: bool = True,
    callback_status: CallbackStatus | None = None,
) -> dict[str, Any]:
    """Executa o pipeline completo para QUALQUER ticker da B3.

    Reusa dados coletados quando existem (``forcar_recoleta=False``);
    comparaveis e cenarios sao opcionais e suas falhas NAO derrubam o
    pipeline (viram avisos no resumo). Devolve um resumo com as etapas.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    inicio = time.time()
    etapas: list[dict[str, Any]] = []
    avisos: list[str] = []

    def etapa(nome: str, funcao: Callable[[], Any], opcional: bool = False) -> Any:
        """Executa uma etapa cronometrada; opcionais nao derrubam o fluxo."""
        _avisar(callback_status, f"{nome}...")
        marco = time.time()
        try:
            resultado = funcao()
        except Exception as erro:  # noqa: BLE001 - decisao por etapa
            etapas.append({"etapa": nome, "status": "FALHA", "erro": str(erro)})
            if opcional:
                avisos.append(f"{nome} falhou: {erro}")
                logger.warning("Etapa opcional falhou (%s): %s", nome, erro)
                return None
            raise
        etapas.append(
            {
                "etapa": nome,
                "status": "OK",
                "duracao_s": round(time.time() - marco, 1),
            }
        )
        return resultado

    if forcar_recoleta or not _dados_cvm_existem(ticker_normalizado, raiz):
        etapa(
            "Coleta CVM (DFP/ITR/DVA)",
            lambda: coletar_empresa(ticker_normalizado, raiz),
        )
    else:
        etapas.append({"etapa": "Coleta CVM", "status": "REUSO_CACHE"})

    etapa("Limpeza Parquet", lambda: limpar_empresa(ticker_normalizado, raiz))
    etapa(
        "Relatorio de qualidade",
        lambda: gerar_relatorio_qualidade(ticker_normalizado, raiz),
    )

    if forcar_recoleta or not _mercado_existe(ticker_normalizado, raiz):
        etapa(
            "Dados de mercado (yfinance)",
            lambda: coletar_mercado(ticker_normalizado, raiz),
        )
    else:
        etapas.append({"etapa": "Dados de mercado", "status": "REUSO_CACHE"})

    etapa(
        "Metricas historicas",
        lambda: calcular_metricas_historicas(ticker_normalizado, raiz),
    )
    etapa(
        "Premissas de partida",
        lambda: gerar_premissas_automaticas(ticker_normalizado, raiz),
    )
    etapa(
        "Motor de valuation",
        lambda: rodar_motor_valuation(
            ticker_normalizado, raiz, callback=callback_status
        ),
    )
    etapa(
        "Qualidade do lucro",
        lambda: calcular_qualidade_lucro(ticker_normalizado, raiz),
        opcional=True,
    )
    # Ordem deliberada: cenarios ANTES dos comparaveis, para a triangulacao
    # ler o ev_equity final (o motor_cenarios re-grava o caso base ao fim).
    if com_cenarios:
        etapa(
            "Cenarios Bear/Base/Bull",
            lambda: executar_cenarios(ticker_normalizado, raiz),
            opcional=True,
        )
    if com_comparaveis:
        etapa(
            "Comparaveis (peers reais)",
            lambda: gerar_comparaveis(ticker_normalizado, raiz),
            opcional=True,
        )
        # Export BI nasce junto com os comparaveis (fonte -> uso completo).
        etapa(
            "Export BI (fato_comparaveis)",
            lambda: exportar_fato_comparaveis(ticker_normalizado, raiz),
            opcional=True,
        )

    meta = carregar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker_normalizado}_meta.json"
    )
    caminho_projecao = (
        raiz / "data" / "processed" / f"{ticker_normalizado}_projecao.json"
    )
    projecao = carregar_json(caminho_projecao) if caminho_projecao.exists() else {}
    ev_equity = projecao.get("ev_equity", {})
    caminho_premissas = (
        raiz / "data" / "premissas" / f"{ticker_normalizado}_premissas.json"
    )
    premissas = carregar_json(caminho_premissas) if caminho_premissas.exists() else {}

    return {
        "ticker": ticker_normalizado,
        "tipo": meta.get("tipo"),
        "subtipo": meta.get("subtipo"),
        "score_confiabilidade": meta.get("score_confiabilidade"),
        "target_price": ev_equity.get("target_price"),
        "upside": ev_equity.get("upside"),
        "recomendacao": ev_equity.get("recomendacao"),
        "premissas_automaticas": bool(premissas.get("premissas_automaticas")),
        "duracao_total_s": round(time.time() - inicio, 1),
        "etapas": etapas,
        "avisos": avisos,
    }


def main() -> None:
    """Roda o pipeline universal via linha de comando."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline universal: qualquer ticker da B3, metodo correto."
    )
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--forcar-recoleta", action="store_true")
    argumentos = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    for ticker in argumentos.tickers:
        resumo = rodar_pipeline_universal(
            ticker,
            forcar_recoleta=argumentos.forcar_recoleta,
        )
        target = resumo.get("target_price")
        print(
            f"{resumo['ticker']} ({resumo['tipo']}/{resumo['subtipo']}): "
            f"Target {'n/d' if target is None else f'R$ {target:.2f}'} | "
            f"{resumo.get('recomendacao')} | score {resumo['score_confiabilidade']}"
            f" | {resumo['duracao_total_s']}s"
        )
        for aviso in resumo["avisos"]:
            print(f"  AVISO: {aviso}")


if __name__ == "__main__":
    main()
