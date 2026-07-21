# DESCONGELADO na Semana 10 (revisao de 20/07/2026): re-alinhado ao motor
# 9.0.x e coberto por teste. A re-integracao ao app (sub-abas de graficos) e a
# entrega do Prompt 10.0.4. Ver Humano_revisar.md (D-078, reverte D-053).
"""Comparaveis / CCA: multiplos de peers reais e triangulacao (v2.0, Onda 3).

Para o subtipo da empresa (lido do ``_meta.json``), le a lista de ``peers``
em ``config/setores.json`` e coleta via yfinance os multiplos de mercado:
EV/EBITDA, P/L, P/VP, EV/Sales e EV/EBIT (este ultimo best-effort, so quando
o EBIT do peer esta disponivel). Calcula mediana e quartis (Q1/Q3) do peer
group e deriva o PRECO IMPLICITO por multiplo aplicando as estatisticas aos
denominadores da empresa-alvo — que vem da CVM (Ano 0 oficial do pipeline),
nunca do yfinance.

Robustez (regra da onda): peer sem dado vai para ``logs/comparaveis_peers.log``
e e excluido da mediana; multiplo <= 0 (ex.: P/L de empresa com prejuizo) e
descartado com aviso; nada disso derruba o pipeline. A empresa-alvo e
EXCLUIDA da mediana do proprio peer group (evita vies circular), mas os
multiplos dela aparecem na tabela para comparacao.

Persistencia: ``data/processed/<TICKER>_comparaveis.json`` — consumido pelo
Football Field, pela tabela de comparaveis, pelo front-end e pelo export BI.
Bancos/seguradoras usam apenas P/L e P/VP (multiplos de EV nao se aplicam a
financeiras).
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.projecao.projetor_dre import (
    carregar_json,
    normalizar_ticker,
    resolver_raiz,
    salvar_json,
    selecionar_ultimo_exercicio,
)
from src.valuation.calculador_ev import obter_fator_escala_moeda

NOME_LOG_PEERS = "comparaveis_peers.log"

# Multiplos aplicaveis por tipo de empresa: EV nao faz sentido para bancos
# (a divida e insumo operacional, nao estrutura de capital).
MULTIPLOS_POR_TIPO: dict[str, tuple[str, ...]] = {
    "nao_financeira": ("ev_ebitda", "ev_ebit", "ev_sales", "p_l", "p_vp"),
    "financeira": ("p_l", "p_vp"),
}
MULTIPLOS_PRINCIPAIS_POR_TIPO: dict[str, tuple[str, ...]] = {
    "nao_financeira": ("ev_ebitda", "p_l"),
    "financeira": ("p_vp", "p_l"),
}
ROTULOS_MULTIPLOS = {
    "ev_ebitda": "EV/EBITDA",
    "ev_ebit": "EV/EBIT",
    "ev_sales": "EV/Sales",
    "p_l": "P/L",
    "p_vp": "P/VP",
}
MINIMO_PEERS_VALIDOS = 2
MINIMO_PEERS_CONFORTAVEL = 3

logger = logging.getLogger(__name__)


def caminho_comparaveis(ticker: str, raiz_projeto: Path) -> Path:
    """Caminho do JSON de comparaveis persistido."""
    return (
        Path(raiz_projeto)
        / "data"
        / "processed"
        / f"{normalizar_ticker(ticker)}_comparaveis.json"
    )


def carregar_comparaveis(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Carrega os comparaveis persistidos; vazio se ainda nao gerados."""
    raiz = resolver_raiz(raiz_projeto)
    caminho = caminho_comparaveis(ticker, raiz)
    if not caminho.exists():
        return {}
    return carregar_json(caminho)


def _registrar_peer_excluido(
    raiz_projeto: Path,
    ticker_alvo: str,
    peer: str,
    motivo: str,
) -> None:
    """Audita peer excluido em logs/comparaveis_peers.log sem quebrar."""
    pasta = raiz_projeto / "logs"
    pasta.mkdir(parents=True, exist_ok=True)
    linha = (
        f"{datetime.now().isoformat(timespec='seconds')} | alvo={ticker_alvo} | "
        f"peer={peer} | motivo={motivo}\n"
    )
    with (pasta / NOME_LOG_PEERS).open("a", encoding="utf-8") as arquivo:
        arquivo.write(linha)


def obter_peers_do_subtipo(
    meta: dict[str, Any],
    raiz_projeto: Path,
) -> list[str]:
    """Le a lista de peers do subtipo em config/setores.json (nunca hard-code)."""
    setores = carregar_json(raiz_projeto / "config" / "setores.json")
    subtipo = str(meta.get("subtipo") or "outros")
    config_subtipo = setores.get("subtipos", {}).get(subtipo, {})
    peers = [normalizar_ticker(peer) for peer in config_subtipo.get("peers", [])]
    return peers


def coletar_multiplos_yfinance(ticker: str) -> dict[str, Any]:
    """Coleta multiplos de mercado de UM ticker via yfinance (com rede).

    Devolve ``{"multiplos": {...}, "market_cap", "preco"}``; campos ausentes
    ficam None. Falha total (rede/ticker) levanta RuntimeError para o
    chamador registrar e excluir o peer.
    """
    import yfinance as yf

    simbolo = f"{normalizar_ticker(ticker)}.SA"
    try:
        ativo = yf.Ticker(simbolo)
        info = dict(ativo.get_info() if hasattr(ativo, "get_info") else ativo.info)
    except Exception as erro:
        raise RuntimeError(f"yfinance falhou para {simbolo}: {erro}") from erro
    if not info:
        raise RuntimeError(f"yfinance sem dados para {simbolo}")

    def _numero(chave: str) -> float | None:
        valor = info.get(chave)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return None
        return float(valor)

    multiplos: dict[str, float | None] = {
        "ev_ebitda": _numero("enterpriseToEbitda"),
        "ev_sales": _numero("enterpriseToRevenue"),
        "p_l": _numero("trailingPE"),
        "p_vp": _numero("priceToBook"),
        "ev_ebit": None,
    }

    # EV/EBIT best-effort: so quando o income statement do yfinance expoe o
    # EBIT do peer; qualquer falha vira None (o multiplo e opcional).
    enterprise_value = _numero("enterpriseValue")
    if enterprise_value is not None and enterprise_value > 0:
        try:
            demonstracao = ativo.income_stmt
            if demonstracao is not None and "EBIT" in demonstracao.index:
                ebit = float(demonstracao.loc["EBIT"].dropna().iloc[0])
                if ebit > 0:
                    multiplos["ev_ebit"] = enterprise_value / ebit
        except Exception:  # noqa: BLE001 - EV/EBIT e opcional por peer
            multiplos["ev_ebit"] = None

    return {
        "multiplos": multiplos,
        "market_cap": _numero("marketCap"),
        "preco": _numero("currentPrice") or _numero("regularMarketPrice"),
        "acoes": _numero("sharesOutstanding"),
    }


def calcular_estatisticas(
    multiplos_por_peer: dict[str, dict[str, float | None]],
    multiplos_aplicaveis: tuple[str, ...],
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Mediana e quartis por multiplo, descartando valores nao positivos.

    Funcao PURA (testavel sem rede). Devolve ``(estatisticas, avisos)``;
    multiplo sem ao menos MINIMO_PEERS_VALIDOS valores validos fica fora.
    """
    estatisticas: dict[str, dict[str, float]] = {}
    avisos: list[str] = []
    for multiplo in multiplos_aplicaveis:
        valores = []
        for peer, multiplos in multiplos_por_peer.items():
            valor = multiplos.get(multiplo)
            if valor is None:
                continue
            if valor <= 0:
                avisos.append(
                    f"{ROTULOS_MULTIPLOS.get(multiplo, multiplo)} de {peer} "
                    f"descartado (valor nao positivo: {valor:.2f})."
                )
                continue
            valores.append(float(valor))
        if len(valores) < MINIMO_PEERS_VALIDOS:
            avisos.append(
                f"{ROTULOS_MULTIPLOS.get(multiplo, multiplo)} sem peers "
                f"suficientes ({len(valores)} valido(s)); estatistica omitida."
            )
            continue
        serie = pd.Series(valores, dtype="float64")
        estatisticas[multiplo] = {
            "q1": float(serie.quantile(0.25)),
            "mediana": float(serie.quantile(0.50)),
            "q3": float(serie.quantile(0.75)),
            "n": len(valores),
        }
        if len(valores) < MINIMO_PEERS_CONFORTAVEL:
            avisos.append(
                f"{ROTULOS_MULTIPLOS.get(multiplo, multiplo)} com amostra "
                f"pequena ({len(valores)} peers) — use com cautela."
            )
    return estatisticas, avisos


def _valor_cvm(dados: pd.DataFrame, nome: str) -> float | None:
    """Valor do ultimo exercicio anual para uma conta padronizada (ou None)."""
    try:
        linha = selecionar_ultimo_exercicio(dados, nome)
    except RuntimeError:
        return None
    return float(linha["valor_padronizado"])


def carregar_denominadores_alvo(
    ticker: str,
    tipo: str,
    raiz_projeto: Path,
) -> tuple[dict[str, float | None], list[str]]:
    """Denominadores da empresa-alvo a partir da CVM (Ano 0 oficial).

    Receita, LL, EBIT, PL, divida CP/LP, caixa e aplicacoes; EBITDA derivado
    como EBIT + |D&A do DFC|. Tudo em moeda da CVM (MIL) — a conversao para
    R$ absolutos acontece na derivacao do preco implicito.
    """
    pasta = raiz_projeto / "data" / "raw" / "cvm"
    avisos: list[str] = []

    def _quadro(demonstracao: str) -> pd.DataFrame:
        caminho = pasta / f"{ticker}_{demonstracao}.json"
        if not caminho.exists():
            return pd.DataFrame()
        return pd.DataFrame(carregar_json(caminho))

    dre = _quadro("dre")
    bp = _quadro("bp")
    dfc = _quadro("dfc")

    nome_lucro = "lucro_liquido"
    denominadores: dict[str, float | None] = {
        "receita_liquida": _valor_cvm(dre, "receita_liquida"),
        "lucro_liquido": _valor_cvm(dre, nome_lucro),
        "ebit": _valor_cvm(dre, "ebit"),
        "patrimonio_liquido": _valor_cvm(bp, "patrimonio_liquido"),
        "divida_curto_prazo": _valor_cvm(bp, "divida_curto_prazo"),
        "divida_longo_prazo": _valor_cvm(bp, "divida_longo_prazo"),
        "caixa_equivalentes": _valor_cvm(bp, "caixa_equivalentes"),
        "aplicacoes_financeiras": _valor_cvm(bp, "aplicacoes_financeiras"),
        "depreciacao_amortizacao": _valor_cvm(dfc, "depreciacao_amortizacao"),
        "ebitda": None,
    }

    if tipo != "financeira":
        ebit = denominadores["ebit"]
        d_e_a = denominadores["depreciacao_amortizacao"]
        if ebit is not None and d_e_a is not None:
            # Formula: EBITDA = EBIT + |D&A| (D&A vem negativa do DFC).
            denominadores["ebitda"] = ebit + abs(d_e_a)
        else:
            avisos.append(
                "EBITDA do alvo indisponivel (EBIT ou D&A ausentes na CVM); "
                "preco implicito por EV/EBITDA omitido."
            )
    return denominadores, avisos


def calcular_divida_liquida(denominadores: dict[str, float | None]) -> float:
    """Divida liquida = |divida CP| + |divida LP| - caixa - aplicacoes."""
    divida = abs(denominadores.get("divida_curto_prazo") or 0.0)
    divida += abs(denominadores.get("divida_longo_prazo") or 0.0)
    caixa = denominadores.get("caixa_equivalentes") or 0.0
    aplicacoes = denominadores.get("aplicacoes_financeiras") or 0.0
    return divida - caixa - aplicacoes


def derivar_precos_implicitos(
    estatisticas: dict[str, dict[str, float]],
    denominadores: dict[str, float | None],
    acoes: float,
    fator_escala: float,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Preco implicito por acao para cada multiplo com estatistica valida.

    Funcao PURA. Para multiplos de EV: preco = (mult x denominador -
    divida liquida) x fator_escala / acoes. Para P/L e P/VP: preco = mult x
    (denominador x fator_escala / acoes). Denominador nao positivo gera
    aviso e omite o multiplo (P/L de alvo com prejuizo nao produz preco).
    """
    avisos: list[str] = []
    precos: dict[str, dict[str, float]] = {}
    divida_liquida = calcular_divida_liquida(denominadores)
    base_por_multiplo = {
        "ev_ebitda": ("ebitda", True),
        "ev_ebit": ("ebit", True),
        "ev_sales": ("receita_liquida", True),
        "p_l": ("lucro_liquido", False),
        "p_vp": ("patrimonio_liquido", False),
    }
    for multiplo, faixa in estatisticas.items():
        nome_base, eh_ev = base_por_multiplo[multiplo]
        denominador = denominadores.get(nome_base)
        if denominador is None or denominador <= 0:
            avisos.append(
                f"Preco implicito por {ROTULOS_MULTIPLOS.get(multiplo, multiplo)} "
                f"omitido: {nome_base} do alvo ausente ou nao positivo."
            )
            continue
        precos_faixa: dict[str, float] = {}
        for ponto in ("q1", "mediana", "q3"):
            mult = faixa[ponto]
            if eh_ev:
                # Formula: Equity = EV - Divida Liquida; EV = mult x base.
                equity = mult * denominador - divida_liquida
                precos_faixa[ponto] = equity * fator_escala / acoes
            else:
                # Formula: preco = mult x (base por acao em R$ absolutos).
                precos_faixa[ponto] = mult * denominador * fator_escala / acoes
        precos[multiplo] = precos_faixa
    return precos, avisos


def montar_triangulacao(
    target_dcf: float | None,
    precos_implicitos: dict[str, dict[str, float]],
    principais: tuple[str, ...],
    preco_atual: float | None,
) -> dict[str, Any]:
    """Resume DCF vs faixa por multiplos vs preco atual com veredito textual.

    Funcao PURA. A faixa considerada e o Q1..Q3 dos multiplos PRINCIPAIS do
    tipo da empresa.
    """
    pontas: list[float] = []
    for multiplo in principais:
        faixa = precos_implicitos.get(multiplo)
        if faixa:
            pontas.extend((faixa["q1"], faixa["q3"]))
    faixa_multiplos = (min(pontas), max(pontas)) if pontas else None

    veredito = "Sem dados suficientes para triangular DCF e multiplos."
    if faixa_multiplos and target_dcf is not None:
        minimo, maximo = faixa_multiplos
        if target_dcf > maximo:
            veredito = (
                "O DCF esta ACIMA da faixa dos multiplos: a tese embute mais "
                "crescimento/margem do que o mercado precifica nos peers."
            )
        elif target_dcf < minimo:
            veredito = (
                "O DCF esta ABAIXO da faixa dos multiplos: a tese e mais "
                "conservadora do que o mercado precifica nos peers."
            )
        else:
            veredito = (
                "O DCF esta DENTRO da faixa dos multiplos: DCF e mercado "
                "contam historias compativeis."
            )
    elif faixa_multiplos:
        veredito = (
            "Sem Target Price de DCF para este ticker (trilha de valuation "
            "pendente); a faixa dos multiplos ancora a leitura de preco."
        )

    return {
        "target_dcf": target_dcf,
        "faixa_multiplos": (
            None
            if faixa_multiplos is None
            else {"minimo": faixa_multiplos[0], "maximo": faixa_multiplos[1]}
        ),
        "multiplos_principais": list(principais),
        "preco_atual": preco_atual,
        "veredito": veredito,
    }


def _target_dcf_persistido(ticker: str, raiz_projeto: Path) -> float | None:
    """Target Price do DCF persistido pelo motor, quando existir."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    if not caminho.exists():
        return None
    conteudo = carregar_json(caminho)
    ev_equity = conteudo.get("ev_equity")
    if not isinstance(ev_equity, dict):
        return None
    target = ev_equity.get("target_price")
    return float(target) if isinstance(target, (int, float)) else None


def _acoes_e_preco_do_alvo(
    ticker: str,
    raiz_projeto: Path,
    dados_alvo_yf: dict[str, Any] | None,
) -> tuple[float | None, float | None]:
    """Acoes e preco atual do alvo: mercado coletado > yfinance."""
    caminho = raiz_projeto / "data" / "raw" / "mercado" / f"{ticker}_mercado.json"
    acoes = None
    preco = None
    if caminho.exists():
        mercado = carregar_json(caminho)
        acoes = mercado.get("acoes_em_circulacao")
        preco = mercado.get("preco_atual")
    if dados_alvo_yf:
        if acoes is None:
            acoes = dados_alvo_yf.get("acoes")
        preco = dados_alvo_yf.get("preco") or preco
    acoes_float = float(acoes) if isinstance(acoes, (int, float)) else None
    preco_float = float(preco) if isinstance(preco, (int, float)) else None
    return acoes_float, preco_float


def gerar_comparaveis(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera e persiste os comparaveis reais do ticker (com rede).

    Coleta multiplos dos peers e do proprio alvo via yfinance, calcula
    estatisticas, deriva precos implicitos com denominadores da CVM e monta
    a triangulacao. Peer indisponivel NUNCA derruba a execucao.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    meta = carregar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker_normalizado}_meta.json"
    )
    tipo = str(meta.get("tipo", "nao_financeira"))
    subtipo = str(meta.get("subtipo") or "outros")
    multiplos_aplicaveis = MULTIPLOS_POR_TIPO.get(
        tipo, MULTIPLOS_POR_TIPO["nao_financeira"]
    )
    principais = MULTIPLOS_PRINCIPAIS_POR_TIPO.get(
        tipo, MULTIPLOS_PRINCIPAIS_POR_TIPO["nao_financeira"]
    )

    peers_config = obter_peers_do_subtipo(meta, raiz)
    # A empresa-alvo sai da mediana do proprio peer group (vies circular).
    peers = [peer for peer in peers_config if peer != ticker_normalizado]

    multiplos_por_peer: dict[str, dict[str, float | None]] = {}
    dados_por_peer: dict[str, dict[str, Any]] = {}
    excluidos: list[dict[str, str]] = []
    for peer in peers:
        try:
            dados = coletar_multiplos_yfinance(peer)
        except RuntimeError as erro:
            excluidos.append({"peer": peer, "motivo": str(erro)})
            _registrar_peer_excluido(raiz, ticker_normalizado, peer, str(erro))
            logger.warning("Peer %s excluido: %s", peer, erro)
            continue
        multiplos_por_peer[peer] = dados["multiplos"]
        dados_por_peer[peer] = dados

    estatisticas, avisos = calcular_estatisticas(
        multiplos_por_peer,
        multiplos_aplicaveis,
    )

    # Multiplos do proprio alvo (para a tabela; fora das estatisticas).
    dados_alvo: dict[str, Any] | None
    try:
        dados_alvo = coletar_multiplos_yfinance(ticker_normalizado)
    except RuntimeError as erro:
        dados_alvo = None
        avisos.append(f"Multiplos do alvo indisponiveis no yfinance: {erro}")

    denominadores, avisos_denominadores = carregar_denominadores_alvo(
        ticker_normalizado,
        tipo,
        raiz,
    )
    avisos.extend(avisos_denominadores)

    acoes, preco_atual = _acoes_e_preco_do_alvo(
        ticker_normalizado,
        raiz,
        dados_alvo,
    )
    fator_escala = obter_fator_escala_moeda(ticker_normalizado, raiz)

    precos_implicitos: dict[str, dict[str, float]] = {}
    if acoes is None or acoes <= 0:
        avisos.append("Acoes em circulacao indisponiveis: precos implicitos omitidos.")
    else:
        precos_implicitos, avisos_precos = derivar_precos_implicitos(
            estatisticas,
            denominadores,
            acoes,
            fator_escala,
        )
        avisos.extend(avisos_precos)

    triangulacao = montar_triangulacao(
        _target_dcf_persistido(ticker_normalizado, raiz),
        precos_implicitos,
        principais,
        preco_atual,
    )

    resultado = {
        "ticker": ticker_normalizado,
        "tipo": tipo,
        "subtipo": subtipo,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "fonte_multiplos": "yfinance",
        "peers_config": peers_config,
        "peers_validos": sorted(multiplos_por_peer),
        "peers_excluidos": excluidos,
        "multiplos_aplicaveis": list(multiplos_aplicaveis),
        "multiplos_principais": list(principais),
        "multiplos_por_peer": {
            peer: {
                **multiplos,
                "market_cap": dados_por_peer[peer].get("market_cap"),
                "preco": dados_por_peer[peer].get("preco"),
            }
            for peer, multiplos in multiplos_por_peer.items()
        },
        "multiplos_alvo": (
            None
            if dados_alvo is None
            else {
                **dados_alvo["multiplos"],
                "market_cap": dados_alvo.get("market_cap"),
                "preco": dados_alvo.get("preco"),
            }
        ),
        "estatisticas": estatisticas,
        "alvo": {
            "denominadores_cvm": denominadores,
            "divida_liquida": calcular_divida_liquida(denominadores),
            "acoes": acoes,
            "fator_escala_moeda": fator_escala,
            "preco_atual": preco_atual,
        },
        "precos_implicitos": precos_implicitos,
        "triangulacao": triangulacao,
        "avisos": avisos,
    }
    salvar_json(caminho_comparaveis(ticker_normalizado, raiz), resultado)
    logger.info(
        "Comparaveis de %s: %s peers validos, %s excluidos, %s multiplos.",
        ticker_normalizado,
        len(multiplos_por_peer),
        len(excluidos),
        len(estatisticas),
    )
    return resultado


def imprimir_resumo(resultado: dict[str, Any]) -> None:
    """Resumo legivel dos comparaveis para validacao manual."""
    print("\n" + "=" * 72)
    print(
        f"{resultado['ticker']} ({resultado['subtipo']}) — "
        f"{len(resultado['peers_validos'])} peers validos de "
        f"{len(resultado['peers_config'])} configurados"
    )
    for multiplo, faixa in resultado["estatisticas"].items():
        rotulo = ROTULOS_MULTIPLOS.get(multiplo, multiplo)
        preco = resultado["precos_implicitos"].get(multiplo)
        texto_preco = (
            f" -> preco implicito R$ {preco['q1']:.2f} / "
            f"{preco['mediana']:.2f} / {preco['q3']:.2f}"
            if preco
            else ""
        )
        print(
            f"  {rotulo}: Q1 {faixa['q1']:.2f} | mediana {faixa['mediana']:.2f} "
            f"| Q3 {faixa['q3']:.2f} (n={faixa['n']}){texto_preco}"
        )
    print(f"  Triangulacao: {resultado['triangulacao']['veredito']}")
    for aviso in resultado["avisos"]:
        print(f"  AVISO: {aviso}")


def main() -> None:
    """Gera comparaveis via linha de comando."""
    parser = argparse.ArgumentParser(
        description="Comparaveis/CCA com peers reais por subtipo setorial."
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        default=["DIRR3", "MGLU3"],
        help="Tickers ja coletados pela Onda 1 (default: DIRR3 MGLU3).",
    )
    argumentos = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    for ticker in argumentos.tickers:
        try:
            imprimir_resumo(gerar_comparaveis(ticker))
        except RuntimeError as erro:
            print(f"Falha nos comparaveis de {ticker}: {erro}")


if __name__ == "__main__":
    main()
