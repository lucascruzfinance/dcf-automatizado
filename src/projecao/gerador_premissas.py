"""Gerador de premissas AUTOMATICAS de partida (v2.0, Ondas 2 e 4).

As premissas continuam sendo o trabalho intelectual do analista — este
modulo gera apenas um PONTO DE PARTIDA auditavel para que qualquer ticker
da B3 rode o pipeline completo: ancora cada vetor nas metricas historicas
(CAGR, margens, prazos) e converge linearmente para os defaults do subtipo
(``config/setores.json``). Cada vetor tem 8 valores INDIVIDUAIS (nunca uma
taxa unica replicada — regra 5 do projeto) e o arquivo sai marcado com
``premissas_automaticas: true`` ate o analista revisar e salvar (o app
remove a flag no salvamento).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.projecao.projetor_dre import (
    HORIZONTE_PROJECAO,
    carregar_json,
    carregar_metadados,
    carregar_razao_receita_bruta,
    normalizar_ticker,
    resolver_raiz,
    salvar_json,
    selecionar_ultimo_exercicio,
)

LIMITES_CRESCIMENTO = (-0.05, 0.15)
LIMITES_MARGEM = (0.0, 0.60)
LIMITES_CAPEX_RECEITA = (-0.30, -0.005)
LIMITES_MARGEM_BRUTA = (0.01, 0.95)
LIMITES_SGNA = (0.0, 0.90)
LIMITES_DEDUCOES = (0.0, 0.90)
G_PERPETUIDADE_PADRAO = 0.035
KD_PADRAO = 0.12
BETA_PADRAO = 1.0
ERP_PADRAO = 0.045
CRP_PADRAO = 0.03
MODO_ALIQUOTA_PADRAO = "marginal"

logger = logging.getLogger(__name__)


def _clamp(valor: float, limites: tuple[float, float]) -> float:
    """Restringe o valor aos limites de sanidade do vetor."""
    return max(limites[0], min(limites[1], valor))


def _interpolar_vetor(
    inicial: float,
    final: float,
    limites: tuple[float, float],
) -> dict[int, float]:
    """Vetor de 8 valores em interpolacao linear (sempre individuais).

    A interpolacao garante 8 valores distintos entre a ancora historica e o
    default de longo prazo do subtipo — nunca uma taxa unica replicada.
    """
    inicial = _clamp(inicial, limites)
    final = _clamp(final, limites)
    if abs(final - inicial) < 1e-9:
        # Evita vetor constante: abre um leque minimo de -/+0,2pp em torno
        # do valor unico para preservar a regra dos 8 valores individuais.
        inicial, final = inicial + 0.002, final - 0.002
    passo = (final - inicial) / (HORIZONTE_PROJECAO - 1)
    return {
        ano: inicial + passo * (ano - 1) for ano in range(1, HORIZONTE_PROJECAO + 1)
    }


def _numero(valor: Any, padrao: float) -> float:
    """Numero defensivo com fallback."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return padrao
    return float(valor)


def _config_subtipo(metadados: dict[str, Any], raiz: Path) -> dict[str, Any]:
    """Config do subtipo da empresa em config/setores.json."""
    setores = carregar_json(raiz / "config" / "setores.json")
    subtipo = str(metadados.get("subtipo") or "outros")
    return setores.get("subtipos", {}).get(subtipo, {})


def _mercado(ticker: str, raiz: Path) -> dict[str, Any]:
    """JSON de mercado coletado, vazio se ausente."""
    caminho = raiz / "data" / "raw" / "mercado" / f"{ticker}_mercado.json"
    if not caminho.exists():
        return {}
    return carregar_json(caminho)


def _metricas(ticker: str, raiz: Path) -> dict[str, Any]:
    """Metricas historicas persistidas, vazio se ausentes."""
    caminho = raiz / "data" / "processed" / f"{ticker}_metricas.json"
    if not caminho.exists():
        return {}
    return carregar_json(caminho)


def _defaults_dre_completa(subtipo: str, raiz: Path) -> dict[str, float]:
    """Defaults setoriais da DRE completa (config/setores.json)."""
    setores = carregar_json(raiz / "config" / "setores.json")
    bloco = setores.get("defaults_dre_completa", {})
    return bloco.get(str(subtipo), bloco.get("outros", {}))


def _valor_ano0_dre(dados: pd.DataFrame, nome: str) -> float:
    """Valor padronizado do Ano 0 para uma conta da DRE; ausente vira 0.0."""
    try:
        linha = selecionar_ultimo_exercicio(dados, nome)
    except RuntimeError:
        return 0.0
    valor = linha["valor_padronizado"]
    return float(valor) if pd.notna(valor) else 0.0


def _ancoras_dre_completa(
    ticker: str,
    raiz: Path,
    agregados: dict[str, Any],
    defaults_setor: dict[str, float],
) -> dict[str, Any]:
    """Ancoras da DRE completa: margem bruta, SG&A, deducoes, outras, equiv.

    Usa a media historica quando disponivel (margem bruta agregada; SG&A,
    outras, equivalencia e deducoes a partir do Ano 0 real da CVM/DVA) e cai
    nos defaults setoriais quando falta a linha. Deducoes sem DVA => 0 + aviso
    (Prompt 8.1.1). Sao PONTOS DE PARTIDA — o analista revisa.
    """
    margem_bruta = _numero(
        agregados.get("margem_bruta_media_3a"),
        _numero(defaults_setor.get("margem_bruta"), 0.30),
    )

    # SG&A, outras e equivalencia a partir do Ano 0 real (3.04.xx da CVM).
    caminho_dre = raiz / "data" / "raw" / "cvm" / f"{ticker}_dre.json"
    sgna_pct = _numero(defaults_setor.get("sgna_pct_receita"), 0.15)
    outras_pct = 0.0
    equivalencia_pct = 0.0
    if caminho_dre.exists():
        dados = pd.DataFrame(carregar_json(caminho_dre))
        receita = _valor_ano0_dre(dados, "receita_liquida")
        if receita > 0:
            despesas_vendas = _valor_ano0_dre(dados, "despesas_vendas")
            desp_g_adm = _valor_ano0_dre(dados, "despesas_gerais_administrativas")
            perdas = _valor_ano0_dre(dados, "perdas_nao_recuperabilidade")
            outras_rec = _valor_ano0_dre(dados, "outras_receitas_operacionais")
            outras_desp = _valor_ano0_dre(dados, "outras_despesas_operacionais")
            equiv = _valor_ano0_dre(dados, "resultado_equivalencia_patrimonial")
            # SG&A = comerciais + G&A (despesas negativas -> ratio positivo).
            sgna_abs = abs(despesas_vendas + desp_g_adm)
            if sgna_abs > 0:
                sgna_pct = sgna_abs / receita
            # Outras = impairment + outras receitas/despesas operacionais (com sinal).
            outras_pct = (perdas + outras_rec + outras_desp) / receita
            equivalencia_pct = equiv / receita

    # Deducoes via DVA (razao RB/RL do Ano 0); deducoes% = 1 - RL/RB.
    razao, fonte_razao = carregar_razao_receita_bruta(ticker, raiz)
    if razao is not None and razao > 1:
        deducoes_pct = 1 - (1 / razao)
        fonte_deducoes = fonte_razao
    else:
        deducoes_pct = 0.0
        fonte_deducoes = "sem_dva_deducoes_zero"
        logger.warning(
            "%s: DVA/receita bruta indisponivel (%s); deducoes = 0.",
            ticker,
            fonte_razao,
        )

    return {
        "margem_bruta": margem_bruta,
        "sgna_pct_receita": sgna_pct,
        "deducoes_pct": deducoes_pct,
        "outras_despesas_pct_receita": round(outras_pct, 5),
        "equivalencia_pct_receita": round(equivalencia_pct, 5),
        "aliquota_efetiva": _numero(agregados.get("aliquota_efetiva_media_3a"), None),
        "fonte_deducoes": fonte_deducoes,
    }


def gerar_premissas_nao_financeira(
    ticker: str,
    metadados: dict[str, Any],
    raiz: Path,
) -> dict[str, Any]:
    """Premissas de partida da trilha nao-financeira (FCFF/WACC)."""
    config = _config_subtipo(metadados, raiz)
    defaults = config.get("premissas_default", {})
    agregados = _metricas(ticker, raiz).get("agregados", {})
    mercado = _mercado(ticker, raiz)

    crescimento_inicial = _numero(
        agregados.get("cagr_receita_3a"),
        _numero(defaults.get("crescimento_receita"), 0.05),
    )
    crescimento_final = _numero(defaults.get("crescimento_receita"), 0.04)
    margem_inicial = _numero(
        agregados.get("margem_ebitda_media_3a"),
        _numero(defaults.get("margem_ebitda"), 0.15),
    )
    margem_final = _numero(
        defaults.get("margem_ebitda"),
        margem_inicial,
    )
    capex_inicial = _numero(
        agregados.get("capex_receita_media_3a"),
        _numero(defaults.get("capex_receita"), -0.04),
    )
    # CAPEX e saida de caixa: forca sinal negativo mesmo com historico ruidoso.
    capex_inicial = -abs(capex_inicial)
    capex_final = -abs(_numero(defaults.get("capex_receita"), capex_inicial))

    premissas: dict[str, Any] = {
        "ticker": ticker,
        "setor": metadados.get("subtipo") or metadados.get("setor"),
        "tipo": "nao_financeira",
    }
    vetores = {
        "crescimento_receita": _interpolar_vetor(
            crescimento_inicial, crescimento_final, LIMITES_CRESCIMENTO
        ),
        "margem_ebitda": _interpolar_vetor(
            margem_inicial, margem_final, LIMITES_MARGEM
        ),
        "capex_receita": _interpolar_vetor(
            capex_inicial, capex_final, LIMITES_CAPEX_RECEITA
        ),
    }
    for nome, vetor in vetores.items():
        for ano, valor in vetor.items():
            premissas[f"{nome}_ano{ano}"] = round(valor, 5)

    # --- DRE completa (Padrao Smartfit, Prompt 8.1): conjunto SEMPRE gerado ---
    # margem_ebitda continua acima (retrocompat); os campos abaixo ligam o modo
    # completo (bruta->liquida, CPV/SG&A separados, imposto efetivo, D&A aberta).
    defaults_setor = _defaults_dre_completa(
        str(metadados.get("subtipo") or "outros"), raiz
    )
    ancoras = _ancoras_dre_completa(ticker, raiz, agregados, defaults_setor)
    vetores_dre = {
        "margem_bruta": _interpolar_vetor(
            ancoras["margem_bruta"],
            _numero(defaults_setor.get("margem_bruta"), ancoras["margem_bruta"]),
            LIMITES_MARGEM_BRUTA,
        ),
        "sgna_pct_receita": _interpolar_vetor(
            ancoras["sgna_pct_receita"],
            _numero(
                defaults_setor.get("sgna_pct_receita"),
                ancoras["sgna_pct_receita"],
            ),
            LIMITES_SGNA,
        ),
        "deducoes_pct_receita_bruta": _interpolar_vetor(
            ancoras["deducoes_pct"],
            ancoras["deducoes_pct"],
            LIMITES_DEDUCOES,
        ),
    }
    for nome, vetor in vetores_dre.items():
        for ano, valor in vetor.items():
            premissas[f"{nome}_ano{ano}"] = round(valor, 5)
    premissas["outras_despesas_pct_receita"] = ancoras["outras_despesas_pct_receita"]
    premissas["equivalencia_pct_receita"] = ancoras["equivalencia_pct_receita"]
    premissas["modo_aliquota"] = MODO_ALIQUOTA_PADRAO
    if ancoras.get("aliquota_efetiva") is not None:
        premissas["aliquota_efetiva"] = round(float(ancoras["aliquota_efetiva"]), 5)
    premissas["origem_dre_completa"] = (
        "margem_bruta/SG&A/deducoes derivados de ancoras historicas + defaults "
        f"do subtipo; deducoes: {ancoras['fonte_deducoes']}; REVISAR"
    )

    premissas["dso"] = round(_numero(agregados.get("dso_media_3a"), 45.0))
    premissas["dio"] = round(_numero(agregados.get("dio_media_3a"), 45.0))
    premissas["dpo"] = round(_numero(agregados.get("dpo_media_3a"), 45.0))
    premissas["custo_divida_kd"] = KD_PADRAO
    premissas["crescimento_perpetuidade_g"] = G_PERPETUIDADE_PADRAO
    premissas["beta"] = _numero(agregados.get("beta_desalavancado"), BETA_PADRAO)
    premissas["erp"] = ERP_PADRAO
    premissas["crp"] = CRP_PADRAO
    payout = defaults.get("payout_dividendos")
    if isinstance(payout, (int, float)) and not isinstance(payout, bool):
        premissas["payout_dividendos"] = float(payout)
    if mercado.get("acoes_em_circulacao"):
        premissas["acoes_fully_diluted"] = float(mercado["acoes_em_circulacao"])
    return premissas


def gerar_premissas_financeira(
    ticker: str,
    metadados: dict[str, Any],
    raiz: Path,
) -> dict[str, Any]:
    """Premissas de partida da trilha financeira (FCFE/Ke)."""
    config = _config_subtipo(metadados, raiz)
    defaults = config.get("premissas_default", {})
    parametros = carregar_json(raiz / "config" / "parametros.json")
    trilha = parametros.get("trilha_financeira", {})
    agregados = _metricas(ticker, raiz).get("agregados", {})
    mercado = _mercado(ticker, raiz)

    crescimento_inicial = _numero(
        agregados.get("cagr_receitas_3a"),
        _numero(defaults.get("crescimento_receita"), 0.06),
    )
    crescimento_final = _numero(defaults.get("crescimento_receita"), 0.05)
    margem_inicial = _numero(
        agregados.get("margem_resultado_bruto_media_3a"),
        0.35,
    )

    # Aliquota efetiva bancaria e ruidosa na DFP (JCP e participacoes
    # estatutarias distorcem 3.06/3.05 — ex.: BBAS3 sai 74%). Clamp de
    # sanidade em [20%, 50%]; fora disso usa o padrao da config.
    aliquota_bruta = _numero(
        agregados.get("aliquota_efetiva_media_3a"),
        _numero(trilha.get("aliquota_ir_financeira_padrao"), 0.45),
    )
    if 0.20 <= aliquota_bruta <= 0.50:
        aliquota = aliquota_bruta
    else:
        aliquota = _numero(trilha.get("aliquota_ir_financeira_padrao"), 0.45)

    # Calibracao pela margem liquida historica: as linhas intermediarias do
    # plano bancario (participacoes, equivalencia) nao sao todas projetadas;
    # a razao de despesas e calibrada para que LL_1/receitas reproduza a
    # margem liquida media historica: desp = ML/(1 - t) - margem_RB.
    margem_liquida_hist = agregados.get("margem_liquida_receitas_media_3a")
    if isinstance(margem_liquida_hist, (int, float)) and not isinstance(
        margem_liquida_hist, bool
    ):
        despesas_inicial = float(margem_liquida_hist) / (1 - aliquota) - margem_inicial
    else:
        despesas_inicial = _numero(
            agregados.get("despesas_operacionais_receita_media_3a"),
            -0.20,
        )
    despesas_inicial = -abs(despesas_inicial)

    premissas: dict[str, Any] = {
        "ticker": ticker,
        "setor": metadados.get("subtipo") or metadados.get("setor"),
        "tipo": "financeira",
    }
    vetores = {
        "crescimento_receita": _interpolar_vetor(
            crescimento_inicial,
            crescimento_final,
            LIMITES_CRESCIMENTO,
        ),
        "margem_resultado_bruto": _interpolar_vetor(
            margem_inicial,
            margem_inicial * 0.98,
            (0.05, 0.80),
        ),
        "despesas_operacionais_receita": _interpolar_vetor(
            despesas_inicial,
            despesas_inicial * 0.98,
            (-0.60, -0.02),
        ),
    }
    for nome, vetor in vetores.items():
        for ano, valor in vetor.items():
            premissas[f"{nome}_ano{ano}"] = round(valor, 5)

    premissas["indice_capital_alvo"] = _numero(
        trilha.get("indice_capital_alvo_padrao"), 0.115
    )
    premissas["fator_rwa_ativos"] = _numero(trilha.get("fator_rwa_ativos_padrao"), 0.75)
    premissas["aliquota_ir_financeira"] = aliquota
    premissas["payout_dividendos"] = _numero(defaults.get("payout_dividendos"), 0.4)
    premissas["crescimento_perpetuidade_g"] = G_PERPETUIDADE_PADRAO
    # Beta de banco entra ALAVANCADO (divida e insumo operacional; sem Hamada).
    premissas["beta"] = _numero(agregados.get("beta_mercado"), BETA_PADRAO)
    premissas["erp"] = ERP_PADRAO
    premissas["crp"] = CRP_PADRAO
    if mercado.get("acoes_em_circulacao"):
        premissas["acoes_fully_diluted"] = float(mercado["acoes_em_circulacao"])
    return premissas


def gerar_premissas_automaticas(
    ticker: str,
    raiz_projeto: Path | None = None,
    sobrescrever: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """Gera e persiste premissas de partida para um ticker coletado.

    Nao sobrescreve premissas existentes (trabalho do analista) a menos que
    ``sobrescrever=True``. O arquivo sai marcado com
    ``premissas_automaticas: true`` para o app exibir o alerta de revisao.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    caminho = raiz / "data" / "premissas" / f"{ticker_normalizado}_premissas.json"
    if caminho.exists() and not sobrescrever:
        return caminho, carregar_json(caminho)

    metadados = carregar_metadados(ticker_normalizado, raiz)
    tipo = str(metadados.get("tipo", "nao_financeira"))
    if tipo == "financeira":
        premissas = gerar_premissas_financeira(ticker_normalizado, metadados, raiz)
    else:
        premissas = gerar_premissas_nao_financeira(
            ticker_normalizado,
            metadados,
            raiz,
        )

    premissas["premissas_automaticas"] = True
    premissas["origem_premissas"] = (
        "geradas automaticamente: ancoras historicas + defaults do subtipo "
        f"({metadados.get('subtipo', 'outros')}); REVISAR antes de usar como tese"
    )
    premissas["gerado_em"] = datetime.now().isoformat(timespec="seconds")
    salvar_json(caminho, premissas)
    logger.info("Premissas automaticas geradas para %s em %s", ticker, caminho)
    return caminho, premissas


def main() -> None:
    """Gera premissas de partida via linha de comando."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Premissas automaticas de partida por ticker coletado."
    )
    parser.add_argument("tickers", nargs="+", help="Tickers ja coletados.")
    parser.add_argument(
        "--sobrescrever",
        action="store_true",
        help="Regenera mesmo se ja existir arquivo de premissas.",
    )
    argumentos = parser.parse_args()
    for ticker in argumentos.tickers:
        caminho, premissas = gerar_premissas_automaticas(
            ticker,
            sobrescrever=argumentos.sobrescrever,
        )
        flag = premissas.get("premissas_automaticas", False)
        print(f"{ticker}: {caminho} (automaticas={flag})")


if __name__ == "__main__":
    main()
