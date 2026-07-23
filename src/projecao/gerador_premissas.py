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
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.projecao.projetor_dre import (
    HORIZONTE_PROJECAO,
    carregar_json,
    carregar_metadados,
    carregar_razao_receita_bruta,
    empresa_usa_ret,
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
# Beta e INPUT do analista (Bloomberg); o clamp abaixo e apenas de sanidade
# AMPLA (evita valor patologico de acao em colapso), NAO um driver que molda o
# Ke — 10.0.0 removeu a re-alavancagem de Hamada e o clamp estreito [0,5; 1,8].
LIMITES_BETA_SANIDADE = (0.3, 2.0)
SPREAD_DIVIDA_SOBRE_CDI_PADRAO = 0.02
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


def _cdi_ano1(raiz: Path) -> float | None:
    """CDI esperado do ano 1 (bloco macro_anual persistido); None se ausente.

    Base do default do Kd (CDI + spread), padrao Direcional/aula: o custo da
    divida sai das ultimas emissoes ~ CDI + spread, nunca de despesa/divida
    media (que estoura em nomes pouco alavancados).
    """
    caminho = raiz / "data" / "raw" / "macro" / "macro_brasil.json"
    if not caminho.exists():
        return None
    try:
        macro = carregar_json(caminho)
    except RuntimeError:
        return None
    macro_anual = macro.get("macro_anual") if isinstance(macro, dict) else None
    if not isinstance(macro_anual, dict):
        return None
    linha = macro_anual.get("ano1")
    if not isinstance(linha, dict):
        return None
    cdi = linha.get("cdi")
    if isinstance(cdi, bool) or not isinstance(cdi, (int, float)) or cdi < 0:
        return None
    return float(cdi)


def _carregar_bruto(ticker: str, raiz: Path, demonstrativo: str) -> pd.DataFrame:
    """Carrega um JSON bruto da CVM em DataFrame; vazio quando ausente."""
    caminho = raiz / "data" / "raw" / "cvm" / f"{ticker}_{demonstrativo}.json"
    if not caminho.exists():
        return pd.DataFrame()
    return pd.DataFrame(carregar_json(caminho))


def _serie_anual(dados: pd.DataFrame, nome: str, n: int = 5) -> dict[int, float]:
    """Ultimos n valores anuais (31/12, ULTIMO) de uma conta, por ano.

    Base do "achatamento pela media de 5 anos" (10.0.0): devolve {ano: valor}
    filtrando ruido de ITR trimestral e escolhendo a conta consolidada (menor
    CD_CONTA) e o arquivo mais recente por exercicio.
    """
    if dados.empty or "nome_padronizado" not in dados.columns:
        return {}
    if "valor_padronizado" not in dados.columns:
        return {}
    sel = dados[dados["nome_padronizado"] == nome].copy()
    sel = sel[sel["valor_padronizado"].notna()]
    if sel.empty:
        return {}
    if "ORDEM_EXERC" in sel.columns:
        ordem = sel["ORDEM_EXERC"].map(
            lambda v: unicodedata.normalize("NFKD", str(v))
            .encode("ascii", "ignore")
            .decode("ascii")
            .strip()
            .lower()
        )
        sel = sel[ordem == "ultimo"]
    sel["_data"] = pd.to_datetime(sel.get("DT_FIM_EXERC"), errors="coerce")
    sel = sel[sel["_data"].notna()]
    sel = sel[(sel["_data"].dt.month == 12) & (sel["_data"].dt.day == 31)]
    if sel.empty:
        return {}
    if "CD_CONTA" in sel.columns:
        sel["_prio"] = sel["CD_CONTA"].astype(str).str.len()
    else:
        sel["_prio"] = 0
    if "ano_arquivo" in sel.columns:
        sel["_arq"] = pd.to_numeric(sel["ano_arquivo"], errors="coerce")
    else:
        sel["_arq"] = 0
    por_ano: dict[int, float] = {}
    for data, grupo in sel.groupby("_data"):
        if grupo["_arq"].notna().any():
            grupo = grupo[grupo["_arq"] == grupo["_arq"].max()]
        grupo = grupo.sort_values("_prio")
        por_ano[int(data.year)] = float(grupo.iloc[0]["valor_padronizado"])
    anos = sorted(por_ano)[-n:]
    return {ano: por_ano[ano] for ano in anos}


def _num_opt(valor: Any) -> float | None:
    """Float defensivo sem aceitar booleanos; invalido vira None."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def _central_robusta(valores: list[float]) -> float | None:
    """Valor central ACHATADO robusto a outlier (10.0.0).

    Regra: usa a MEDIA, salvo quando ha um ANO EXTREMO — algum ponto que se
    afasta da mediana em mais de 1,5x o |mediana| (ex.: dividendo especial que
    triplica o payout de um unico ano). Nesse caso a MEDIANA e mais fiel ao
    regime tipico da empresa. Lista vazia devolve None; mediana ~0 cai na
    media (razoes centradas em zero, como equivalencia, nao tem outlier util).
    """
    if not valores:
        return None
    ordenados = sorted(valores)
    n = len(ordenados)
    media = sum(ordenados) / n
    meio = n // 2
    if n % 2 == 1:
        mediana = ordenados[meio]
    else:
        mediana = (ordenados[meio - 1] + ordenados[meio]) / 2
    if abs(mediana) < 1e-9:
        return media
    if any(abs(v - mediana) > 1.5 * abs(mediana) for v in ordenados):
        return mediana
    return media


def _central_pct_hist(
    numerador: dict[int, float],
    denominador: dict[int, float],
    n: int = 5,
    usar_abs: bool = True,
) -> float | None:
    """Central robusta (media-5a achatada) das razoes num/den (den != 0)."""
    anos = sorted(set(numerador) & set(denominador))[-n:]
    razoes: list[float] = []
    for ano in anos:
        den = denominador[ano]
        if den == 0:
            continue
        num = abs(numerador[ano]) if usar_abs else numerador[ano]
        razoes.append(num / den)
    return _central_robusta(razoes)


def _ancora_flat_5a(
    agregados: dict[str, Any],
    campo: str,
    fallback: float | None,
) -> float | None:
    """Ancora ACHATADA da media de 5 anos com salvaguarda de outlier (10.0.0).

    Preferencia: media-5a; se a media-5a e a mediana-5a divergem forte (ano
    extremo), usa a mediana-5a; sem 5a cai para a media-3a e depois para o
    ``fallback``. E a base do default achatado dos vetores de premissa.
    """
    media5 = _num_opt(agregados.get(f"{campo}_media_5a"))
    mediana5 = _num_opt(agregados.get(f"{campo}_mediana_5a"))
    if media5 is not None:
        if (
            mediana5 is not None
            and abs(mediana5) > 1e-9
            and abs(media5 - mediana5) > 0.5 * abs(mediana5)
        ):
            return mediana5
        return media5
    media3 = _num_opt(agregados.get(f"{campo}_media_3a"))
    if media3 is not None:
        return media3
    return fallback


def _vetor_flat(valor: float) -> dict[int, float]:
    """Vetor de 8 valores ACHATADO (10.0.0): mesmo valor em todos os anos.

    O default das premissas passa a ser a media historica de 5 anos fletada
    nos 8 anos (padrao Madero/WEGE3). O analista sobrescreve ano a ano no app
    para escrever a narrativa — o editor 8x continua existindo.
    """
    return {ano: valor for ano in range(1, HORIZONTE_PROJECAO + 1)}


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


def _da_pct_receita_ano0(ticker: str, raiz: Path) -> float:
    """|D&A historica do Ano 0| / Receita Liquida do Ano 0 (via DFC + DRE).

    Insumo da calibracao PRE-D&A (9.0.2): somar a D&A%RL a margem bruta
    historica (pos-D&A) faz o EBIT ex-Depreciacao do ano 1 ancorar EXATAMENTE
    no EBITDA historico (EBIT_hist + D&A_hist). Sem DFC/RL devolve 0.0.
    """
    caminho_dfc = raiz / "data" / "raw" / "cvm" / f"{ticker}_dfc.json"
    caminho_dre = raiz / "data" / "raw" / "cvm" / f"{ticker}_dre.json"
    if not caminho_dfc.exists() or not caminho_dre.exists():
        return 0.0
    dfc = pd.DataFrame(carregar_json(caminho_dfc))
    dre = pd.DataFrame(carregar_json(caminho_dre))
    if dfc.empty or dre.empty:
        return 0.0
    da = abs(_valor_ano0_dre(dfc, "depreciacao_amortizacao"))
    receita = _valor_ano0_dre(dre, "receita_liquida")
    if receita <= 0 or da <= 0:
        return 0.0
    return da / receita


def _ancoras_dre_completa(
    ticker: str,
    raiz: Path,
    agregados: dict[str, Any],
    defaults_setor: dict[str, float],
) -> dict[str, Any]:
    """Ancoras da DRE completa PRE-D&A: margem bruta, SG&A, deducoes, etc.

    MUDANCA 9.0.2 (margens de nivel EBITDA): a margem bruta historica da CVM
    e POS-D&A (o CPV divulgado embute depreciacao); a ancora pre-D&A soma a
    D&A%RL historica inteira a margem bruta (aproximacao: D&A
    majoritariamente no CPV, padrao industrial). Com isso EBIT ex-Depreciacao
    do ano 1 = EBITDA historico por identidade. SG&A, outras, equivalencia e
    deducoes vem do Ano 0 real (CVM/DVA); defaults setoriais no fallback.
    Sao PONTOS DE PARTIDA — o analista revisa.
    """
    da_pct_rl = _da_pct_receita_ano0(ticker, raiz)
    # Margem bruta ancorada na MEDIA-5a ACHATADA robusta (10.0.0) + D&A%RL.
    margem_bruta = (
        _ancora_flat_5a(
            agregados,
            "margem_bruta",
            _numero(defaults_setor.get("margem_bruta"), 0.30),
        )
        + da_pct_rl
    )

    # SG&A, outras e equivalencia pela MEDIA DE 5 ANOS (10.0.0), calculada das
    # razoes historicas ano a ano (nao mais so o Ano 0).
    dre = _carregar_bruto(ticker, raiz, "dre")
    receita_por_ano = _serie_anual(dre, "receita_liquida")
    dv = _serie_anual(dre, "despesas_vendas")
    dga = _serie_anual(dre, "despesas_gerais_administrativas")
    sgna_por_ano = {
        ano: _numero(dv.get(ano), 0.0) + _numero(dga.get(ano), 0.0)
        for ano in set(dv) | set(dga)
    }
    # SG&A = comerciais + G&A (despesas negativas -> razao positiva por abs).
    sgna_pct = _numero(
        _central_pct_hist(sgna_por_ano, receita_por_ano, usar_abs=True),
        _numero(defaults_setor.get("sgna_pct_receita"), 0.15),
    )
    # Outras (com sinal) = impairment + outras receitas/despesas operacionais.
    perdas = _serie_anual(dre, "perdas_nao_recuperabilidade")
    outras_rec = _serie_anual(dre, "outras_receitas_operacionais")
    outras_desp = _serie_anual(dre, "outras_despesas_operacionais")
    outras_por_ano = {
        ano: _numero(perdas.get(ano), 0.0)
        + _numero(outras_rec.get(ano), 0.0)
        + _numero(outras_desp.get(ano), 0.0)
        for ano in set(perdas) | set(outras_rec) | set(outras_desp)
    }
    outras_pct = _numero(
        _central_pct_hist(outras_por_ano, receita_por_ano, usar_abs=False), 0.0
    )
    equiv = _serie_anual(dre, "resultado_equivalencia_patrimonial")
    equivalencia_pct = _numero(
        _central_pct_hist(equiv, receita_por_ano, usar_abs=False), 0.0
    )

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
        "da_pct_rl": da_pct_rl,
        "sgna_pct_receita": sgna_pct,
        "deducoes_pct": deducoes_pct,
        "outras_despesas_pct_receita": round(outras_pct, 5),
        "equivalencia_pct_receita": round(equivalencia_pct, 5),
        "aliquota_efetiva": _ancora_flat_5a(agregados, "aliquota_efetiva", None),
        "fonte_deducoes": fonte_deducoes,
    }


def _payout_hist_5a(ticker: str, raiz: Path) -> float | None:
    """Payout historico ACHATADO: media-5a robusta de |dividendos|/LL.

    Fonte: dividendos pagos no DFC (financiamento) sobre o Lucro Liquido do
    ano (DRE). 10.0.0: o payout deixa de ser input do analista e vira FATO
    HISTORICO achatado. Sem as linhas (ou LL ~0 em todo o periodo) devolve
    None — o gerador cai no default do subtipo. Clampado em [0, 1].
    """
    dfc = _carregar_bruto(ticker, raiz, "dfc")
    dre = _carregar_bruto(ticker, raiz, "dre")
    dividendos = _serie_anual(dfc, "dividendos_pagos_dfc")
    lucro = _serie_anual(dre, "lucro_liquido")
    valor = _central_pct_hist(dividendos, lucro, usar_abs=True)
    if valor is None:
        return None
    return min(max(valor, 0.0), 1.0)


def _minoritarios_hist_5a(ticker: str, raiz: Path) -> float:
    """Minoritarios ACHATADO: media-5a robusta de |nao_controladores|/|LL|.

    10.0.0: minoritarios deixa de ser input e vira FATO HISTORICO (media dos
    ultimos 5 anos, suavizada por outlier). Sem as linhas (ou LL ~0) devolve
    0.0 (default do 9.0.2.6). Clampado em [0, 0.5].
    """
    dre = _carregar_bruto(ticker, raiz, "dre")
    nao_controladores = _serie_anual(dre, "lucro_atribuido_nao_controladores")
    lucro = _serie_anual(dre, "lucro_liquido")
    valor = _central_pct_hist(nao_controladores, lucro, usar_abs=True)
    if valor is None:
        return 0.0
    return min(max(valor, 0.0), 0.5)


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

    # 10.0.0: o default de cada vetor passa a ser a MEDIA-5a ACHATADA nos 8
    # anos (nao mais CAGR/fade). O analista sobrescreve ano a ano no app (o
    # editor 8x segue vivo) para escrever a narrativa; ate la o vetor sai
    # achatado no fato historico, com salvaguarda de outlier (media/mediana).
    crescimento_flat = _clamp(
        _numero(
            _ancora_flat_5a(
                agregados,
                "crescimento_receita_yoy",
                _numero(
                    agregados.get("cagr_receita_3a"),
                    _numero(defaults.get("crescimento_receita"), 0.05),
                ),
            ),
            _numero(defaults.get("crescimento_receita"), 0.05),
        ),
        LIMITES_CRESCIMENTO,
    )
    margem_ebitda_flat = _clamp(
        _ancora_flat_5a(
            agregados,
            "margem_ebitda",
            _numero(defaults.get("margem_ebitda"), 0.15),
        ),
        LIMITES_MARGEM,
    )
    # CAPEX e saida de caixa: forca sinal negativo mesmo com historico ruidoso.
    capex_flat = _clamp(
        -abs(
            _ancora_flat_5a(
                agregados,
                "capex_receita",
                _numero(defaults.get("capex_receita"), -0.04),
            )
        ),
        LIMITES_CAPEX_RECEITA,
    )

    premissas: dict[str, Any] = {
        "ticker": ticker,
        "setor": metadados.get("subtipo") or metadados.get("setor"),
        "tipo": "nao_financeira",
    }
    vetores = {
        "crescimento_receita": _vetor_flat(crescimento_flat),
        "margem_ebitda": _vetor_flat(margem_ebitda_flat),
        "capex_receita": _vetor_flat(capex_flat),
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
    # 10.0.0: vetores da DRE ACHATADOS na ancora historica de 5 anos (sem fade).
    vetores_dre = {
        "margem_bruta": _vetor_flat(
            _clamp(ancoras["margem_bruta"], LIMITES_MARGEM_BRUTA)
        ),
        "sgna_pct_receita": _vetor_flat(
            _clamp(ancoras["sgna_pct_receita"], LIMITES_SGNA)
        ),
        "deducoes_pct_receita_bruta": _vetor_flat(
            _clamp(ancoras["deducoes_pct"], LIMITES_DEDUCOES)
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

    # --- Padrao Direcional (9.0.2): margens PRE-D&A + aliquota ANUAL +
    # minoritarios + WK multi-driver ---
    usa_ret = empresa_usa_ret({"setor": premissas.get("setor")}, metadados)
    if not usa_ret:
        # Vetor anual de aliquota: interpolacao da efetiva historica com
        # clamp [15%, 45%]; sem historico, marginal 34%. Construtora RET nao
        # gera o vetor (o RET incide sobre a Receita Bruta projetada).
        aliquota_base = _numero(ancoras.get("aliquota_efetiva"), 0.34)
        aliquota_base = min(max(aliquota_base, 0.15), 0.45)
        # 10.0.0: aliquota ACHATADA na efetiva historica de 5 anos (sem fade).
        for ano, valor in _vetor_flat(aliquota_base).items():
            premissas[f"aliquota_ir_ano{ano}"] = round(valor, 5)
        # WK multi-driver (dias por conta derivados do Ano 0 no schedule).
        premissas["modo_capital_giro"] = "dias_multi_driver"
    # Minoritarios = FATO HISTORICO ACHATADO (media-5a robusta), nao mais input.
    premissas["minoritarios_pct_ll"] = round(_minoritarios_hist_5a(ticker, raiz), 5)
    premissas["origem_dre_completa"] = (
        "PRE-D&A (9.0.2) + vetores ACHATADOS na media-5a (10.0.0): margem_bruta "
        f"= historica + D&A%RL ({ancoras['da_pct_rl']:.4f}); SG&A/deducoes de "
        "ancoras historicas; payout/minoritarios = media-5a do historico; "
        f"deducoes: {ancoras['fonte_deducoes']}; REVISAR"
    )

    premissas["dso"] = round(_numero(agregados.get("dso_media_3a"), 45.0))
    premissas["dio"] = round(_numero(agregados.get("dio_media_3a"), 45.0))
    premissas["dpo"] = round(_numero(agregados.get("dpo_media_3a"), 45.0))
    # Kd = INPUT do analista; default = CDI do ano 1 + spread (padrao
    # Direcional/aula: ultimas emissoes ~ CDI + spread). Sem macro, KD_PADRAO.
    cdi_ano1 = _cdi_ano1(raiz)
    if cdi_ano1 is not None:
        premissas["custo_divida_kd"] = round(
            cdi_ano1 + SPREAD_DIVIDA_SOBRE_CDI_PADRAO, 5
        )
        # Faz o Kd POR ANO acompanhar o CDI projetado (schedule_divida).
        premissas["spread_divida_sobre_cdi"] = SPREAD_DIVIDA_SOBRE_CDI_PADRAO
    else:
        premissas["custo_divida_kd"] = KD_PADRAO
    premissas["crescimento_perpetuidade_g"] = G_PERPETUIDADE_PADRAO
    # Beta = INPUT do analista (Bloomberg). Default = beta de MERCADO bruto
    # (yfinance ~5a, ja alavancado), com clamp so de sanidade ampla; sem
    # desalavancar/re-alavancar por Hamada (10.0.0) — entra direto no CAPM.
    premissas["beta"] = round(
        _clamp(
            _numero(agregados.get("beta_mercado"), BETA_PADRAO),
            LIMITES_BETA_SANIDADE,
        ),
        4,
    )
    premissas["erp"] = ERP_PADRAO
    premissas["crp"] = CRP_PADRAO
    # Payout = FATO HISTORICO ACHATADO (10.0.0): media-5a de |dividendos|/LL.
    # Sem historico de dividendos, cai no default do subtipo.
    payout_hist = _payout_hist_5a(ticker, raiz)
    if payout_hist is not None:
        premissas["payout_dividendos"] = round(payout_hist, 5)
    else:
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
