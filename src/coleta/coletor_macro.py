"""Coleta de dados macroeconomicos do Brasil via python-bcb (Prompt 9.0.3).

Alem de Selic/IPCA (Focus), coleta CDI (SGS 4389, fallback Selic - 0,1pp),
IGP-M acumulado 12m (SGS 189) e cambio BRL/USD (SGS 1), e monta o bloco
``macro_anual`` (ano1..ano8) com IPCA/Selic/CDI/PIB esperados: mediana do
Focus onde ele cobre; alem do horizonte do Focus, convergencia LINEAR ate as
metas de longo prazo de ``config/parametros.json`` (bloco ``macro``) no ano 8.

O motor LE o CDI daqui (receita financeira e custo da divida = CDI + spread,
padrao Direcional ``Modelo`` L190). Sem rede, a coleta PRESERVA os valores ja
persistidos em ``data/raw/macro/macro_brasil.json`` (merge campo a campo) e o
``macro_anual`` e reconstruido a partir do que existir.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
CODIGO_SELIC_META = 432
CODIGO_CDI_ANUALIZADO = 4389
CODIGO_IGPM_MENSAL = 189
CODIGO_CAMBIO_VENDA = 1

# Indicadores anuais do Focus consumidos pelo bloco macro_anual e pelos
# campos informativos (IGP-M e Cambio ficam como INFO; o motor usa CDI).
INDICADORES_FOCUS = ("IPCA", "Selic", "IGP-M", "Câmbio", "PIB Total")
HORIZONTE_MACRO_ANUAL = 8

# Defaults quando config/parametros.json nao traz o bloco ``macro``:
# meta continua de inflacao do BC (3%), Selic nominal neutra aproximada
# (juro real neutro ~4,5% + meta ~3%, arredondado para cima pela media
# das medianas longas do Focus) e PIB potencial (~2%).
METAS_LONGO_PRAZO_PADRAO = {"ipca": 0.03, "selic": 0.09, "pib": 0.02}
SPREAD_CDI_SELIC_PADRAO = -0.001

# Campos escalares que o merge offline preserva quando a coleta falha.
CAMPOS_PRESERVADOS = (
    "selic_atual",
    "cdi_atual",
    "igpm_12m",
    "cambio_brl_usd",
    "ipca_focus_1a",
    "ipca_focus_2a",
    "selic_focus_1a",
    "selic_focus_2a",
    "focus_anuais",
)


def resolver_raiz(raiz_projeto: Path | None = None) -> Path:
    """Devolve a raiz do projeto, permitindo override em testes."""
    if raiz_projeto is None:
        return RAIZ_PROJETO
    return Path(raiz_projeto)


def configurar_logger(raiz_projeto: Path) -> logging.Logger:
    """Configura log de coleta macro sem duplicar handlers."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    caminho_log = raiz_projeto / "logs" / "coletor_macro.log"
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


def salvar_json(caminho: Path, conteudo: dict[str, Any]) -> None:
    """Salva JSON com indentacao estavel."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False, indent=2)


def percentual_para_decimal(valor: Any) -> float | None:
    """Converte percentuais do BCB/Focus para decimal (heuristica legada).

    Mantida para os campos legados (``*_focus_1a/2a`` e ``selic_atual``); os
    campos novos usam conversao EXPLICITA (``focus_para_decimal`` divide por
    100 sempre; cambio fica bruto) porque a heuristica erra para valores
    percentuais abaixo de 1 (ex.: PIB esperado de 0,5%).
    """
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if pd.isna(numero):
        return None
    if abs(numero) > 1:
        return numero / 100
    return numero


def focus_para_decimal(valor: Any) -> float | None:
    """Converte mediana do Focus (sempre em % a.a.) para decimal."""
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if pd.isna(numero):
        return None
    return numero / 100


def _numero_ou_none(valor: Any) -> float | None:
    """Converte para float sem aceitar booleanos; invalido vira None."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def carregar_parametros_macro(raiz_projeto: Path) -> dict[str, Any]:
    """Le o bloco ``macro`` de config/parametros.json com defaults seguros."""
    caminho = raiz_projeto / "config" / "parametros.json"
    bloco: dict[str, Any] = {}
    if caminho.exists():
        try:
            with caminho.open("r", encoding="utf-8") as arquivo:
                bloco = json.load(arquivo).get("macro", {}) or {}
        except (OSError, json.JSONDecodeError):
            bloco = {}
    metas = dict(METAS_LONGO_PRAZO_PADRAO)
    metas_config = bloco.get("metas_longo_prazo")
    if isinstance(metas_config, dict):
        for chave, valor in metas_config.items():
            numero = _numero_ou_none(valor)
            if numero is not None:
                metas[str(chave)] = numero
    spread = _numero_ou_none(bloco.get("cdi_spread_sobre_selic_pp"))
    if spread is None:
        spread = SPREAD_CDI_SELIC_PADRAO
    return {"metas_longo_prazo": metas, "cdi_spread_sobre_selic_pp": spread}


def coletar_serie_sgs(
    codigo: int,
    nome: str,
    logger: logging.Logger,
    ultimos: int = 1,
) -> pd.Series | None:
    """Coleta os ultimos valores de uma serie SGS; None quando falhar."""
    try:
        from bcb import sgs

        dados = sgs.get({nome: codigo}, last=ultimos)
    except Exception as erro:  # pragma: no cover - depende de rede/API externa.
        logger.exception("Falha ao coletar SGS %s (%s): %s", codigo, nome, erro)
        return None
    if dados.empty or nome not in dados.columns:
        logger.warning("SGS %s retornou sem coluna %s.", codigo, nome)
        return None
    serie = pd.to_numeric(dados[nome], errors="coerce").dropna()
    if serie.empty:
        logger.warning("SGS %s (%s) sem valores numericos.", codigo, nome)
        return None
    return serie


def coletar_selic_atual(logger: logging.Logger) -> float | None:
    """Coleta a Selic meta vigente pela serie SGS 432."""
    serie = coletar_serie_sgs(CODIGO_SELIC_META, "selic_atual", logger)
    if serie is None:
        return None
    return percentual_para_decimal(serie.iloc[-1])


def coletar_cdi_atual(
    logger: logging.Logger,
    selic_atual: float | None,
    spread_cdi_selic: float,
) -> tuple[float | None, str]:
    """CDI anualizado (SGS 4389, % a.a.); fallback Selic + spread (-0,1pp)."""
    serie = coletar_serie_sgs(CODIGO_CDI_ANUALIZADO, "cdi_atual", logger)
    if serie is not None:
        # Serie 4389 vem em % a.a. (ex.: 14.15); conversao explicita.
        return float(serie.iloc[-1]) / 100.0, "sgs_4389"
    if selic_atual is not None:
        logger.warning(
            "CDI SGS 4389 indisponivel; usando Selic %+.2fpp.", spread_cdi_selic * 100
        )
        return max(selic_atual + spread_cdi_selic, 0.0), "fallback_selic_menos_spread"
    return None, "indisponivel"


def acumular_12m(variacoes_mensais: list[float]) -> float:
    """Acumula variacoes mensais em % (ex.: 0,5 = 0,5% a.m.) em 12 meses.

    Formula: acumulado = prod(1 + v_m/100) - 1.
    """
    acumulado = 1.0
    for variacao in variacoes_mensais:
        acumulado *= 1.0 + float(variacao) / 100.0
    return acumulado - 1.0


def coletar_igpm_12m(logger: logging.Logger) -> float | None:
    """IGP-M acumulado 12 meses (SGS 189, variacao % a.m.)."""
    serie = coletar_serie_sgs(CODIGO_IGPM_MENSAL, "igpm_mensal", logger, ultimos=12)
    if serie is None:
        return None
    if len(serie) < 12:
        logger.warning(
            "IGP-M com apenas %d meses; acumulando o disponivel.", len(serie)
        )
    return acumular_12m([float(valor) for valor in serie])


def coletar_cambio_atual(logger: logging.Logger) -> float | None:
    """Cambio BRL/USD (SGS 1, dolar venda, valor BRUTO — nao e percentual)."""
    serie = coletar_serie_sgs(CODIGO_CAMBIO_VENDA, "cambio_brl_usd", logger)
    if serie is None:
        return None
    return float(serie.iloc[-1])


def coletar_expectativas_anuais(logger: logging.Logger) -> pd.DataFrame:
    """Coleta endpoint anual do Focus para os indicadores do macro_anual."""
    try:
        from bcb import Expectativas

        endpoint = Expectativas().get_endpoint("ExpectativasMercadoAnuais")
        filtro = endpoint.Indicador == INDICADORES_FOCUS[0]
        for indicador in INDICADORES_FOCUS[1:]:
            filtro = filtro | (endpoint.Indicador == indicador)
        return endpoint.get(filter=filtro, orderby=endpoint.Data.desc(), limit=2000)
    except Exception as erro:  # pragma: no cover - depende de rede/API externa.
        logger.exception("Falha ao coletar Expectativas Focus: %s", erro)
        return pd.DataFrame()


def selecionar_mediana_focus(
    dados: pd.DataFrame,
    indicador: str,
    ano_referencia: int,
    logger: logging.Logger,
) -> float | None:
    """Seleciona a mediana Focus mais recente para indicador e ano (bruta)."""
    if dados.empty:
        return None
    colunas_obrigatorias = {"Indicador", "DataReferencia", "Mediana"}
    if not colunas_obrigatorias.issubset(dados.columns):
        logger.warning("Focus sem colunas esperadas: %s", sorted(dados.columns))
        return None

    filtrado = dados[
        (dados["Indicador"] == indicador)
        & (dados["DataReferencia"].astype(str) == str(ano_referencia))
    ].copy()
    if filtrado.empty:
        logger.warning(
            "Focus sem %s para DataReferencia %s.", indicador, ano_referencia
        )
        return None
    if "Data" in filtrado.columns:
        filtrado = filtrado.sort_values("Data")

    valor = filtrado.iloc[-1]["Mediana"]
    if valor is None or pd.isna(valor):
        return None
    return float(valor)


def montar_focus_anuais(
    dados: pd.DataFrame,
    ano_base: int,
    logger: logging.Logger,
    quantidade_anos: int = HORIZONTE_MACRO_ANUAL,
) -> dict[str, dict[str, float]]:
    """Medianas anuais do Focus por indicador e ano-calendario (decimal).

    Cobre do ano corrente (ano_base = ano1 da projecao) ate ano_base +
    quantidade_anos - 1; anos sem mediana ficam FORA do dicionario (o
    montar_macro_anual completa por convergencia). Cambio fica BRUTO
    (BRL/USD); os demais indicadores convertem % -> decimal.
    """
    resultado: dict[str, dict[str, float]] = {}
    rotulos = {
        "IPCA": "ipca",
        "Selic": "selic",
        "IGP-M": "igpm",
        "Câmbio": "cambio",
        "PIB Total": "pib",
    }
    for indicador, rotulo in rotulos.items():
        por_ano: dict[str, float] = {}
        for deslocamento in range(quantidade_anos):
            ano_referencia = ano_base + deslocamento
            bruto = selecionar_mediana_focus(dados, indicador, ano_referencia, logger)
            if bruto is None:
                continue
            valor = float(bruto) if rotulo == "cambio" else focus_para_decimal(bruto)
            if valor is None:
                continue
            por_ano[str(ano_referencia)] = valor
        if por_ano:
            resultado[rotulo] = por_ano
    return resultado


def serie_convergente(
    conhecidos: dict[str, float] | dict[int, float],
    meta: float,
    ano_base: int,
    horizonte: int = HORIZONTE_MACRO_ANUAL,
) -> list[tuple[float, str]]:
    """Serie ano1..anoN: Focus onde cobre; depois convergencia LINEAR a meta.

    - Ano coberto pelo Focus -> valor do Focus (origem ``focus``).
    - Anos ANTES do primeiro coberto -> repetem o primeiro coberto
      (origem ``focus_mais_proximo``).
    - Anos entre coberturas -> repetem o ultimo coberto (Focus anual e
      contiguo na pratica; documentado).
    - Anos APOS o ultimo coberto -> interpolacao linear do ultimo valor ate a
      META no ano ``horizonte`` (origem ``convergencia_linear``).
    - Sem nenhum ano coberto -> meta em todos (origem ``meta``).
    """
    por_ano: dict[int, float] = {}
    for chave, valor in conhecidos.items():
        try:
            por_ano[int(chave)] = float(valor)
        except (TypeError, ValueError):
            continue

    anos_projecao = list(range(1, horizonte + 1))
    cobertos = sorted(ano for ano in anos_projecao if (ano_base + ano - 1) in por_ano)
    if not cobertos:
        return [(meta, "meta") for _ in anos_projecao]

    primeiro, ultimo = cobertos[0], cobertos[-1]
    valor_ultimo = por_ano[ano_base + ultimo - 1]
    resultado: list[tuple[float, str]] = []
    valor_anterior = por_ano[ano_base + primeiro - 1]
    for ano in anos_projecao:
        ano_calendario = ano_base + ano - 1
        if ano_calendario in por_ano:
            valor_anterior = por_ano[ano_calendario]
            resultado.append((valor_anterior, "focus"))
        elif ano < primeiro:
            resultado.append((por_ano[ano_base + primeiro - 1], "focus_mais_proximo"))
        elif ano < ultimo:
            resultado.append((valor_anterior, "focus_mais_proximo"))
        else:
            # Aqui ano > ultimo (ano == ultimo cai no primeiro if, pois e ano
            # coberto), logo ultimo < horizonte e o denominador nao zera.
            # Formula: v_t = v_u + (meta - v_u) x (t - t_u) / (N - t_u).
            fracao = (ano - ultimo) / (horizonte - ultimo)
            valor = valor_ultimo + (meta - valor_ultimo) * fracao
            resultado.append((valor, "convergencia_linear"))
    return resultado


def montar_macro_anual(
    focus_anuais: dict[str, dict[str, float]],
    selic_atual: float | None,
    parametros_macro: dict[str, Any],
    ano_base: int,
    horizonte: int = HORIZONTE_MACRO_ANUAL,
) -> dict[str, dict[str, Any]]:
    """Monta o bloco ``macro_anual`` (ano1..ano8) consumido pelo motor.

    ano1 = ano-calendario corrente (primeiro exercicio projetado apos o
    Ano 0). IPCA/Selic/PIB: Focus + convergencia (``serie_convergente``).
    CDI nao tem expectativa anual no Focus: deriva da Selic esperada,
    ``cdi_t = selic_t + spread`` (spread da config, default -0,1pp), piso 0.
    A Selic do Focus e de FIM de periodo — aproximacao documentada para a
    media do ano. Sem Focus de Selic, a Selic atual ancora o ano1.
    """
    metas = parametros_macro["metas_longo_prazo"]
    spread = float(parametros_macro["cdi_spread_sobre_selic_pp"])

    conhecidos_selic = dict(focus_anuais.get("selic", {}))
    if not conhecidos_selic and selic_atual is not None:
        # Ancora minima offline: Selic atual vale para o ano corrente.
        conhecidos_selic[str(ano_base)] = float(selic_atual)

    series = {
        "ipca": serie_convergente(
            focus_anuais.get("ipca", {}), metas["ipca"], ano_base, horizonte
        ),
        "selic": serie_convergente(
            conhecidos_selic, metas["selic"], ano_base, horizonte
        ),
        "pib": serie_convergente(
            focus_anuais.get("pib", {}), metas["pib"], ano_base, horizonte
        ),
    }

    macro_anual: dict[str, dict[str, Any]] = {}
    for ano in range(1, horizonte + 1):
        ipca, origem_ipca = series["ipca"][ano - 1]
        selic, origem_selic = series["selic"][ano - 1]
        pib, origem_pib = series["pib"][ano - 1]
        # Formula: CDI_t = Selic_t + spread (sem serie anual propria no Focus).
        cdi = max(selic + spread, 0.0)
        macro_anual[f"ano{ano}"] = {
            "ano_projecao": f"ano{ano}",
            "ano_calendario": ano_base + ano - 1,
            "ipca": ipca,
            "selic": selic,
            "cdi": cdi,
            "pib": pib,
            "origem_ipca": origem_ipca,
            "origem_selic": origem_selic,
            "origem_cdi": "selic_mais_spread",
            "origem_pib": origem_pib,
        }
    return macro_anual


def focus_de_campos_legados(
    dados: dict[str, Any], ano_base: int
) -> dict[str, dict[str, float]]:
    """Reconstroi um focus_anuais minimo dos campos legados persistidos.

    Usado no modo offline quando o arquivo persistido ainda nao tem o
    ``focus_anuais`` completo (formato pre-9.0.3): ``*_focus_1a/2a`` sao as
    medianas dos anos ano_base+1 e ano_base+2.
    """
    resultado: dict[str, dict[str, float]] = {}
    for rotulo, campo_1a, campo_2a in (
        ("ipca", "ipca_focus_1a", "ipca_focus_2a"),
        ("selic", "selic_focus_1a", "selic_focus_2a"),
    ):
        por_ano: dict[str, float] = {}
        valor_1a = _numero_ou_none(dados.get(campo_1a))
        valor_2a = _numero_ou_none(dados.get(campo_2a))
        if valor_1a is not None:
            por_ano[str(ano_base + 1)] = valor_1a
        if valor_2a is not None:
            por_ano[str(ano_base + 2)] = valor_2a
        if por_ano:
            resultado[rotulo] = por_ano
    return resultado


def mesclar_preservando(
    novo: dict[str, Any],
    persistido: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    """Merge campo a campo: coleta que falhou (None) preserva o persistido."""
    resultado = dict(novo)
    for campo in CAMPOS_PRESERVADOS:
        if resultado.get(campo) is None and persistido.get(campo) is not None:
            resultado[campo] = persistido[campo]
            logger.warning(
                "Campo macro %s indisponivel na coleta; preservando persistido.",
                campo,
            )
    return resultado


def coletar_macro(raiz_projeto: Path | None = None) -> dict[str, Any]:
    """Coleta macro completa (spot + Focus) e monta o bloco macro_anual.

    Sem rede, cada campo que falhar preserva o valor ja persistido em
    ``data/raw/macro/macro_brasil.json`` e o ``macro_anual`` e reconstruido
    do que existir (nunca quebra o pipeline por indisponibilidade).
    """
    raiz = resolver_raiz(raiz_projeto)
    logger = configurar_logger(raiz)
    parametros_macro = carregar_parametros_macro(raiz)
    ano_atual = date.today().year
    ano_1a = ano_atual + 1
    ano_2a = ano_atual + 2

    caminho_saida = raiz / "data" / "raw" / "macro" / "macro_brasil.json"
    persistido: dict[str, Any] = {}
    if caminho_saida.exists():
        try:
            with caminho_saida.open("r", encoding="utf-8") as arquivo:
                persistido = json.load(arquivo)
        except (OSError, json.JSONDecodeError):
            logger.warning("macro_brasil.json persistido ilegivel; ignorando.")
            persistido = {}

    dados_focus = coletar_expectativas_anuais(logger)
    selic_atual = coletar_selic_atual(logger)
    cdi_atual, origem_cdi_atual = coletar_cdi_atual(
        logger,
        selic_atual,
        float(parametros_macro["cdi_spread_sobre_selic_pp"]),
    )
    focus_anuais = montar_focus_anuais(dados_focus, ano_atual, logger)

    resultado: dict[str, Any] = {
        "selic_atual": selic_atual,
        "cdi_atual": cdi_atual,
        "origem_cdi_atual": origem_cdi_atual,
        "igpm_12m": coletar_igpm_12m(logger),
        "cambio_brl_usd": coletar_cambio_atual(logger),
        # Campos legados (consumidores v2 e fallback offline do macro_anual).
        "ipca_focus_1a": percentual_para_decimal(
            selecionar_mediana_focus(dados_focus, "IPCA", ano_1a, logger)
        ),
        "ipca_focus_2a": percentual_para_decimal(
            selecionar_mediana_focus(dados_focus, "IPCA", ano_2a, logger)
        ),
        "selic_focus_1a": percentual_para_decimal(
            selecionar_mediana_focus(dados_focus, "Selic", ano_1a, logger)
        ),
        "selic_focus_2a": percentual_para_decimal(
            selecionar_mediana_focus(dados_focus, "Selic", ano_2a, logger)
        ),
        "focus_anuais": focus_anuais or None,
        "data_coleta": datetime.now(timezone.utc).isoformat(),
    }
    resultado = mesclar_preservando(resultado, persistido, logger)

    focus_efetivo = resultado.get("focus_anuais") or focus_de_campos_legados(
        resultado, ano_atual
    )
    if resultado.get("cdi_atual") is None and resultado.get("selic_atual") is not None:
        resultado["cdi_atual"] = max(
            float(resultado["selic_atual"])
            + float(parametros_macro["cdi_spread_sobre_selic_pp"]),
            0.0,
        )
        resultado["origem_cdi_atual"] = "fallback_selic_menos_spread"
    resultado["macro_anual"] = montar_macro_anual(
        focus_efetivo,
        _numero_ou_none(resultado.get("selic_atual")),
        parametros_macro,
        ano_atual,
    )
    resultado["metas_longo_prazo"] = parametros_macro["metas_longo_prazo"]

    salvar_json(caminho_saida, resultado)
    return resultado


def main() -> None:
    """Executa a coleta macro e imprime os valores salvos."""
    resultado = coletar_macro()
    for campo, valor in resultado.items():
        if campo == "macro_anual":
            print("macro_anual:")
            for chave_ano, linha in valor.items():
                print(
                    f"  {chave_ano} ({linha['ano_calendario']}): "
                    f"IPCA={linha['ipca']:.2%} Selic={linha['selic']:.2%} "
                    f"CDI={linha['cdi']:.2%} PIB={linha['pib']:.2%}"
                )
            continue
        print(f"{campo}: {valor}")


if __name__ == "__main__":
    main()
