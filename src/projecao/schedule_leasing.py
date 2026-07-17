"""Schedule de arrendamento (IFRS-16) — Prompt 8.2.

Modela o arrendamento como cidadao de primeira classe:

- **Passivo de arrendamento**: rollforward BoP - amortizacao + novos contratos
  = EoP, com split CP/LP e **juros de arrendamento** (taxa x saldo de ABERTURA,
  convencao D-015) SEPARADOS dos juros de divida.
- **Ativo de direito de uso**: BoP - depreciacao do direito de uso + adicoes.
- **D&A do direito de uso**: como o direito de uso vem AGREGADO no imobilizado
  da CVM (1.02.03.02 dentro de 1.02.03), a D&A do direito de uso e obtida por
  RECLASSIFICACAO proporcional da D&A do imobilizado (fallback documentado do
  Prompt 8.2.1) — a D&A TOTAL nao muda, apenas se abre em imobilizado x direito
  de uso; logo o EBIT/EBITDA e o FCFF nao mudam com a reclassificacao (so os
  juros de arrendamento, abaixo do EBIT, afetam LL/FCFE/caixa).

Empresa com passivo de arrendamento abaixo do limiar (% do ativo) => o bloco
inteiro zera, sem erro (Principio 7).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        normalizar_texto,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
        somar_ultimo_exercicio,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        normalizar_texto,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
        somar_ultimo_exercicio,
    )

logger = logging.getLogger(__name__)

LIMIAR_LEASING_PADRAO = 0.01
SPREAD_ARRENDAMENTO_PADRAO = 0.02
CLAMP_MIN_PP_PADRAO = -0.02
CLAMP_MAX_PP_PADRAO = 0.08
PRAZO_MIN_PADRAO = 2.0
PRAZO_MAX_PADRAO = 15.0
PRAZO_PADRAO = 6.0
CDI_FALLBACK = 0.10


def obter_float_obrigatorio(dados: dict[str, Any], campo: str, contexto: str) -> float:
    """Le campo numerico obrigatorio de um dicionario de projecao."""
    valor = dados.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"Campo numerico obrigatorio invalido: {contexto}.{campo}")
    return float(valor)


def carregar_parametros_leasing(raiz_projeto: Path) -> dict[str, float]:
    """Le o bloco ``leasing`` de config/parametros.json com defaults."""
    parametros = carregar_json(raiz_projeto / "config" / "parametros.json")
    bloco = parametros.get("leasing", {})
    return {
        "limiar": float(
            bloco.get("limiar_leasing_relevante_pct_ativo", LIMIAR_LEASING_PADRAO)
        ),
        "spread": float(
            bloco.get("spread_arrendamento_sobre_cdi", SPREAD_ARRENDAMENTO_PADRAO)
        ),
        "clamp_min_pp": float(
            bloco.get("clamp_taxa_min_sobre_cdi_pp", CLAMP_MIN_PP_PADRAO)
        ),
        "clamp_max_pp": float(
            bloco.get("clamp_taxa_max_sobre_cdi_pp", CLAMP_MAX_PP_PADRAO)
        ),
        "prazo_min": float(bloco.get("prazo_medio_leasing_min_anos", PRAZO_MIN_PADRAO)),
        "prazo_max": float(bloco.get("prazo_medio_leasing_max_anos", PRAZO_MAX_PADRAO)),
        "prazo_padrao": float(
            bloco.get("prazo_medio_leasing_padrao_anos", PRAZO_PADRAO)
        ),
    }


def carregar_projecao_existente(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[Path, dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Carrega a projecao com DRE e PP&E ja calculados."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    dre = conteudo.get("dre")
    ppe = conteudo.get("ppe")
    if not isinstance(dre, dict):
        raise RuntimeError(f"DRE projetada ausente em {caminho}")
    if not isinstance(ppe, dict):
        raise RuntimeError(f"Schedule PP&E ausente em {caminho}")
    return caminho, conteudo, dre, ppe


def _somar_direito_uso_ano0(dados: pd.DataFrame) -> float:
    """Soma o ATIVO de direito de uso (DS_CONTA 'direito de uso') no Ano 0."""
    if dados.empty or "DS_CONTA" not in dados.columns:
        return 0.0
    ds = dados["DS_CONTA"].map(normalizar_texto)
    filtrado = dados[ds.str.contains("direito de uso", na=False)].copy()
    if filtrado.empty:
        return 0.0
    filtrado["nome_padronizado"] = "direito_uso_tmp"
    return abs(somar_ultimo_exercicio(filtrado, "direito_uso_tmp"))


def carregar_ano0_leasing(
    ticker: str,
    raiz_projeto: Path,
    imobilizado_ano0: float,
) -> dict[str, Any]:
    """Ano 0 do arrendamento: passivo (somado), direito de uso e ativo total."""
    caminho = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_bp.json"
    dados = pd.DataFrame(carregar_json(caminho))
    passivo = abs(somar_ultimo_exercicio(dados, "passivo_arrendamento"))
    ativo_total = abs(somar_ultimo_exercicio(dados, "ativo_total"))
    direito_uso = _somar_direito_uso_ano0(dados)
    origem_direito_uso = "bp_direito_de_uso"
    if direito_uso <= 0:
        # Fallback documentado (8.2.1): sem ativo de direito de uso no BP,
        # estima direito de uso = passivo de arrendamento.
        direito_uso = passivo
        origem_direito_uso = "fallback_passivo_arrendamento"
    return {
        "passivo_arrendamento": passivo,
        "direito_uso_ativo": direito_uso,
        "ativo_total": ativo_total,
        "imobilizado": imobilizado_ano0,
        "origem_direito_uso": origem_direito_uso,
    }


def carregar_cdi(raiz_projeto: Path) -> float:
    """CDI aproximado pela Selic coletada; fallback de config."""
    caminho = raiz_projeto / "data" / "raw" / "macro" / "macro_brasil.json"
    if not caminho.exists():
        return CDI_FALLBACK
    macro = carregar_json(caminho)
    selic = macro.get("selic_atual")
    if isinstance(selic, (int, float)) and not isinstance(selic, bool) and selic > 0:
        return float(selic) / 100.0 if selic > 1 else float(selic)
    return CDI_FALLBACK


def resolver_taxa_arrendamento(
    premissas: dict[str, Any],
    cdi: float,
    parametros: dict[str, float],
) -> tuple[float, str]:
    """Taxa de arrendamento: premissa > CDI + spread, com clamp sobre o CDI."""
    premissa = premissas.get("taxa_arrendamento")
    if (
        isinstance(premissa, (int, float))
        and not isinstance(premissa, bool)
        and premissa >= 0
    ):
        taxa = float(premissa)
        origem = "premissa"
    else:
        taxa = cdi + parametros["spread"]
        origem = "cdi_mais_spread"
    minimo = cdi + parametros["clamp_min_pp"]
    maximo = cdi + parametros["clamp_max_pp"]
    return max(minimo, min(maximo, taxa)), origem


def resolver_prazo_medio(
    premissas: dict[str, Any],
    direito_uso_ano0: float,
    da_direito_uso_ano0: float,
    parametros: dict[str, float],
) -> tuple[float, str]:
    """Prazo medio: premissa > derivado (direito uso / D&A direito uso) > default."""
    premissa = premissas.get("prazo_medio_leasing_anos")
    if (
        isinstance(premissa, (int, float))
        and not isinstance(premissa, bool)
        and premissa > 0
    ):
        prazo, origem = float(premissa), "premissa"
    elif da_direito_uso_ano0 > 0 and direito_uso_ano0 > 0:
        prazo = direito_uso_ano0 / da_direito_uso_ano0
        origem = "derivado_direito_uso/d&a"
    else:
        prazo, origem = parametros["prazo_padrao"], "config_padrao"
    return max(parametros["prazo_min"], min(parametros["prazo_max"], prazo)), origem


def carregar_adicoes_pcts(premissas: dict[str, Any]) -> dict[int, float] | None:
    """Vetor opcional de adicoes de leasing (% receita). None => renovacao."""
    pcts: dict[int, float] = {}
    algum = False
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        valor = premissas.get(f"adicoes_leasing_pct_receita_ano{ano}")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            pcts[ano] = float(valor)
            algum = True
        else:
            pcts[ano] = 0.0
    return pcts if algum else None


def projetar_linhas_leasing(
    dre: dict[str, dict[str, Any]],
    ppe: dict[str, dict[str, Any]],
    ano0: dict[str, Any],
    taxa: float,
    prazo: float,
    proporcao_direito_uso: float,
    adicoes_pcts: dict[int, float] | None,
) -> dict[str, dict[str, float | str]]:
    """Rollforward do ativo/passivo de arrendamento e juros de ano1 a ano8."""
    linhas: dict[str, dict[str, float | str]] = {}
    ativo_anterior = float(ano0["direito_uso_ativo"])
    passivo_anterior = float(ano0["passivo_arrendamento"])

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        receita = obter_float_obrigatorio(dre[chave_ano], "receita_liquida", chave_ano)
        da_imobilizado_full = obter_float_obrigatorio(
            ppe[chave_ano], "da_imobilizado", chave_ano
        )
        # D&A do direito de uso = reclassificacao proporcional da D&A do imob.
        da_direito_uso = proporcao_direito_uso * da_imobilizado_full

        if adicoes_pcts is not None:
            adicoes = adicoes_pcts[ano] * receita
        else:
            # Renovacao (steady-state): adiciona o que depreciou.
            adicoes = da_direito_uso

        # Ativo de direito de uso: BoP - D&A + adicoes.
        ativo = max(ativo_anterior - da_direito_uso + adicoes, 0.0)

        # Passivo de arrendamento: juros sobre saldo de ABERTURA (D-015).
        juros = taxa * passivo_anterior
        amortizacao = (
            min(passivo_anterior / prazo, passivo_anterior) if prazo > 0 else 0.0
        )
        novos = adicoes
        passivo = max(passivo_anterior - amortizacao + novos, 0.0)
        passivo_cp = min(passivo / prazo, passivo) if prazo > 0 else 0.0
        passivo_lp = max(passivo - passivo_cp, 0.0)

        linhas[chave_ano] = {
            "ano_projecao": chave_ano,
            "direito_uso_ativo": ativo,
            "da_direito_uso": da_direito_uso,
            "adicoes_arrendamento": adicoes,
            "passivo_arrendamento": passivo,
            "passivo_arrendamento_cp": passivo_cp,
            "passivo_arrendamento_lp": passivo_lp,
            "amortizacao_arrendamento": amortizacao,
            "juros_arrendamento": juros,
            "taxa_arrendamento": taxa,
        }
        ativo_anterior = ativo
        passivo_anterior = passivo

    return linhas


def _linhas_leasing_zeradas() -> dict[str, dict[str, float | str]]:
    """Bloco de leasing zerado (empresa sem arrendamento relevante)."""
    linhas: dict[str, dict[str, float | str]] = {}
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linhas[chave_ano] = {
            "ano_projecao": chave_ano,
            "direito_uso_ativo": 0.0,
            "da_direito_uso": 0.0,
            "adicoes_arrendamento": 0.0,
            "passivo_arrendamento": 0.0,
            "passivo_arrendamento_cp": 0.0,
            "passivo_arrendamento_lp": 0.0,
            "amortizacao_arrendamento": 0.0,
            "juros_arrendamento": 0.0,
            "taxa_arrendamento": 0.0,
        }
    return linhas


def atualizar_dre_com_leasing(
    dre: dict[str, dict[str, Any]],
    ppe: dict[str, dict[str, Any]],
    leasing: dict[str, dict[str, Any]],
    modo_dre: str,
) -> None:
    """Reclassifica a D&A (imob x direito de uso) e injeta juros de arrendamento.

    A D&A TOTAL nao muda (reclassificacao), entao EBIT/EBITDA ficam intactos;
    apenas os componentes ``da_imobilizado``/``da_direito_uso`` e a linha
    ``juros_arrendamento`` (consumida pelo schedule de divida no resultado
    financeiro) sao gravados.
    """
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_dre = dre[chave_ano]
        da_imobilizado_full = obter_float_obrigatorio(
            ppe[chave_ano], "da_imobilizado", chave_ano
        )
        da_direito_uso = float(leasing[chave_ano]["da_direito_uso"])
        da_intangivel = float(linha_dre.get("da_intangivel") or 0.0)
        da_imobilizado = max(da_imobilizado_full - da_direito_uso, 0.0)

        linha_dre["da_imobilizado"] = da_imobilizado
        linha_dre["da_direito_uso"] = da_direito_uso
        linha_dre["da_intangivel"] = da_intangivel
        # D&A total preservada (soma dos tres componentes).
        linha_dre["depreciacao_amortizacao"] = (
            da_imobilizado + da_direito_uso + da_intangivel
        )
        linha_dre["juros_arrendamento"] = float(
            leasing[chave_ano]["juros_arrendamento"]
        )
        # EBIT/EBITDA nao mudam: a D&A total e a mesma, so foi reclassificada.


def atualizar_projecao_leasing(
    caminho: Path,
    conteudo: dict[str, Any],
    ano0: dict[str, Any],
    leasing: dict[str, dict[str, float | str]],
    politicas: dict[str, Any],
) -> None:
    """Grava o bloco leasing e o Ano 0 dentro da projecao integrada."""
    ano0_projecao = conteudo.get("ano0")
    if not isinstance(ano0_projecao, dict):
        ano0_projecao = {}
    ano0_projecao["leasing"] = ano0
    conteudo["ano0"] = ano0_projecao
    conteudo["leasing"] = leasing
    politicas_projecao = conteudo.get("politicas_projecao")
    if not isinstance(politicas_projecao, dict):
        politicas_projecao = {}
    politicas_projecao["leasing"] = politicas
    conteudo["politicas_projecao"] = politicas_projecao
    salvar_json(caminho, conteudo)


def projetar_leasing(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Executa o schedule de arrendamento IFRS-16 e refina a DRE."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    parametros = carregar_parametros_leasing(raiz)
    caminho, conteudo, dre, ppe = carregar_projecao_existente(ticker_normalizado, raiz)
    modo_dre = str(conteudo.get("modo_dre", "legado"))

    imobilizado_ano0 = float(
        conteudo.get("ano0", {}).get("ppe", {}).get("imobilizado", 0.0)
    )
    da_historica_ano0 = float(
        conteudo.get("ano0", {}).get("ppe", {}).get("da_historica", 0.0)
    )
    ano0 = carregar_ano0_leasing(ticker_normalizado, raiz, imobilizado_ano0)

    ativo_total = ano0["ativo_total"]
    relevante = ano0["passivo_arrendamento"] > parametros["limiar"] * max(
        ativo_total, 1.0
    )

    if not relevante:
        logger.info(
            "%s sem arrendamento relevante (passivo=%.0f); bloco leasing zerado.",
            ticker_normalizado,
            ano0["passivo_arrendamento"],
        )
        leasing = _linhas_leasing_zeradas()
        politicas = {
            "relevante": False,
            "motivo": "passivo_arrendamento_abaixo_do_limiar",
            "limiar_pct_ativo": parametros["limiar"],
        }
        atualizar_dre_com_leasing(dre, ppe, leasing, modo_dre)
        atualizar_projecao_leasing(caminho, conteudo, ano0, leasing, politicas)
        return {
            "ticker": ticker_normalizado,
            "relevante": False,
            "ano0": ano0,
            "leasing": leasing,
            "dre": dre,
            "caminho_saida": caminho,
        }

    premissas = carregar_json(
        raiz / "data" / "premissas" / f"{ticker_normalizado}_premissas.json"
    )
    proporcao = 0.0
    if imobilizado_ano0 > 0:
        proporcao = min(max(ano0["direito_uso_ativo"] / imobilizado_ano0, 0.0), 1.0)
    da_direito_uso_ano0 = proporcao * da_historica_ano0

    cdi = carregar_cdi(raiz)
    taxa, origem_taxa = resolver_taxa_arrendamento(premissas, cdi, parametros)
    prazo, origem_prazo = resolver_prazo_medio(
        premissas, ano0["direito_uso_ativo"], da_direito_uso_ano0, parametros
    )
    adicoes_pcts = carregar_adicoes_pcts(premissas)

    leasing = projetar_linhas_leasing(
        dre=dre,
        ppe=ppe,
        ano0=ano0,
        taxa=taxa,
        prazo=prazo,
        proporcao_direito_uso=proporcao,
        adicoes_pcts=adicoes_pcts,
    )
    atualizar_dre_com_leasing(dre, ppe, leasing, modo_dre)
    politicas = {
        "relevante": True,
        "cdi_base": cdi,
        "taxa_arrendamento": taxa,
        "origem_taxa": origem_taxa,
        "prazo_medio_leasing_anos": prazo,
        "origem_prazo": origem_prazo,
        "proporcao_direito_uso_no_imobilizado": proporcao,
        "origem_direito_uso": ano0["origem_direito_uso"],
        "adicoes_via_premissa": adicoes_pcts is not None,
    }
    atualizar_projecao_leasing(caminho, conteudo, ano0, leasing, politicas)
    return {
        "ticker": ticker_normalizado,
        "relevante": True,
        "taxa_arrendamento": taxa,
        "prazo_medio_leasing_anos": prazo,
        "proporcao_direito_uso": proporcao,
        "ano0": ano0,
        "leasing": leasing,
        "dre": dre,
        "caminho_saida": caminho,
    }


def executar_validacao_padrao() -> None:
    """Roda o schedule de leasing para DIRR3 e MGLU3 ao rodar o arquivo direto."""
    for ticker in ("DIRR3", "MGLU3"):
        resultado = projetar_leasing(ticker)
        print(
            f"{ticker}: relevante={resultado['relevante']} | "
            f"passivo_ano0={resultado['ano0']['passivo_arrendamento']:.0f}"
        )


if __name__ == "__main__":
    executar_validacao_padrao()
