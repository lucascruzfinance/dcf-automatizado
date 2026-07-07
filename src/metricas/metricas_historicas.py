"""Metricas historicas da trilha nao-financeira.

Consome os JSONs brutos da CVM (``data/raw/cvm/``) e produz series anuais e
agregados que ancoram as premissas do analista: crescimento YoY e CAGR,
margens, aliquota efetiva, prazos de giro (DSO/DIO/DPO/CCC), alavancagem,
cobertura de juros, ROIC e CAPEX aproximado. O resultado e persistido em
``data/processed/<TICKER>_metricas.json`` e alimenta a aba Premissas do app.

A trilha financeira (bancos) fica como esqueleto nao validado ate a v1.5.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

try:
    from src.projecao.projetor_dre import (
        carregar_json,
        carregar_metadados,
        normalizar_texto,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.projecao.projetor_dre import (
        carregar_json,
        carregar_metadados,
        normalizar_texto,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )

ALIQUOTA_IR_GERAL = 0.34
DIAS_ANO = 365.0
JANELAS_CAGR = (3, 5, 7)

logger = logging.getLogger(__name__)


def _quadro_bruto(ticker: str, raiz: Path, demonstrativo: str) -> pd.DataFrame:
    """Carrega um JSON bruto da CVM em DataFrame; vazio se nao existir."""
    caminho = raiz / "data" / "raw" / "cvm" / f"{ticker}_{demonstrativo}.json"
    if not caminho.exists():
        logger.warning("Base historica ausente: %s", caminho)
        return pd.DataFrame()
    return pd.DataFrame(carregar_json(caminho))


def serie_anual_por_ano(
    dados: pd.DataFrame,
    nome_padronizado: str,
) -> dict[int, float]:
    """Extrai a serie anual (31/12, ORDEM ULTIMO) de uma conta padronizada.

    Devolve ``{ano_exercicio: valor_padronizado}``. Conta ausente devolve
    dicionario vazio em vez de quebrar (robustez de dados externos).
    """
    if dados.empty or "nome_padronizado" not in dados.columns:
        return {}

    selecao = dados[dados["nome_padronizado"] == nome_padronizado].copy()
    selecao = selecao[selecao["valor_padronizado"].notna()]
    if selecao.empty:
        return {}

    if "ORDEM_EXERC" in selecao.columns:
        ordem = selecao["ORDEM_EXERC"].map(normalizar_texto)
        selecao = selecao[ordem == "ultimo"]

    selecao["_data"] = pd.to_datetime(selecao.get("DT_FIM_EXERC"), errors="coerce")
    selecao = selecao[selecao["_data"].notna()]
    selecao = selecao[
        (selecao["_data"].dt.month == 12) & (selecao["_data"].dt.day == 31)
    ]
    if selecao.empty:
        return {}

    selecao["_ano_arquivo"] = pd.to_numeric(selecao.get("ano_arquivo"), errors="coerce")
    if "CD_CONTA" in selecao.columns:
        # Conta consolidada tem o codigo mais curto (ex.: 3.01 vs 3.01.01).
        selecao["_prioridade"] = selecao["CD_CONTA"].astype(str).str.len()
    else:
        selecao["_prioridade"] = 0

    serie: dict[int, float] = {}
    for data_exercicio, grupo in selecao.groupby("_data"):
        if grupo["_ano_arquivo"].notna().any():
            grupo = grupo[grupo["_ano_arquivo"] == grupo["_ano_arquivo"].max()]
        grupo = grupo.sort_values("_prioridade")
        serie[int(data_exercicio.year)] = float(grupo.iloc[0]["valor_padronizado"])
    return serie


def _razao(numerador: float | None, denominador: float | None) -> float | None:
    """Divide com protecao contra None e denominador zero."""
    if numerador is None or denominador is None or denominador == 0:
        return None
    return numerador / denominador


def calcular_cagr(
    receitas: dict[int, float],
    janela: int,
) -> float | None:
    """CAGR da receita na janela: (V_final / V_inicial)^(1/n) - 1."""
    anos = sorted(receitas)
    if len(anos) < janela + 1:
        return None
    ano_final = anos[-1]
    ano_inicial = anos[-1 - janela]
    inicial = receitas[ano_inicial]
    final = receitas[ano_final]
    if inicial <= 0 or final <= 0:
        # CAGR indefinido com base nao positiva (prejuizo/receita zerada).
        return None
    return (final / inicial) ** (1.0 / janela) - 1.0


def _aliquota_efetiva(ir_csll: float | None, ebt: float | None) -> float | None:
    """Aliquota efetiva = |IR/CSLL| / EBT, apenas quando EBT positivo."""
    if ir_csll is None or ebt is None or ebt <= 0:
        return None
    return abs(ir_csll) / ebt


def montar_series_anuais(
    ticker: str,
    raiz: Path,
) -> dict[str, dict[int, float]]:
    """Carrega todas as series anuais usadas pelas metricas."""
    dre = _quadro_bruto(ticker, raiz, "dre")
    bp = _quadro_bruto(ticker, raiz, "bp")
    dfc = _quadro_bruto(ticker, raiz, "dfc")

    return {
        "receita_liquida": serie_anual_por_ano(dre, "receita_liquida"),
        "lucro_bruto": serie_anual_por_ano(dre, "lucro_bruto"),
        "cpv_cmv": serie_anual_por_ano(dre, "cpv_cmv"),
        "ebit": serie_anual_por_ano(dre, "ebit"),
        "ebt": serie_anual_por_ano(dre, "ebt"),
        "ir_csll": serie_anual_por_ano(dre, "ir_csll"),
        "lucro_liquido": serie_anual_por_ano(dre, "lucro_liquido"),
        "despesas_financeiras": serie_anual_por_ano(dre, "despesas_financeiras"),
        "depreciacao_amortizacao": serie_anual_por_ano(dfc, "depreciacao_amortizacao"),
        "contas_receber": serie_anual_por_ano(bp, "contas_receber"),
        "estoques": serie_anual_por_ano(bp, "estoques"),
        "fornecedores": serie_anual_por_ano(bp, "fornecedores"),
        "imobilizado": serie_anual_por_ano(bp, "imobilizado"),
        "divida_curto_prazo": serie_anual_por_ano(bp, "divida_curto_prazo"),
        "divida_longo_prazo": serie_anual_por_ano(bp, "divida_longo_prazo"),
        "caixa_equivalentes": serie_anual_por_ano(bp, "caixa_equivalentes"),
        "aplicacoes_financeiras": serie_anual_por_ano(bp, "aplicacoes_financeiras"),
        "patrimonio_liquido": serie_anual_por_ano(bp, "patrimonio_liquido"),
    }


def calcular_metricas_por_ano(
    series: dict[str, dict[int, float]],
) -> dict[str, dict[str, float | None]]:
    """Calcula as metricas anuais da trilha nao-financeira.

    Cada metrica devolve None quando os insumos do ano nao existem, em vez
    de quebrar (anos de prejuizo e contas ausentes sao validos).
    """
    receitas = series["receita_liquida"]
    anos = sorted(receitas)
    metricas: dict[str, dict[str, float | None]] = {}

    for indice, ano in enumerate(anos):
        receita = receitas.get(ano)
        receita_anterior = receitas.get(anos[indice - 1]) if indice > 0 else None
        lucro_bruto = series["lucro_bruto"].get(ano)
        cpv = series["cpv_cmv"].get(ano)
        ebit = series["ebit"].get(ano)
        ebt = series["ebt"].get(ano)
        ir_csll = series["ir_csll"].get(ano)
        lucro_liquido = series["lucro_liquido"].get(ano)
        despesas_financeiras = series["despesas_financeiras"].get(ano)
        depreciacao = series["depreciacao_amortizacao"].get(ano)
        contas_receber = series["contas_receber"].get(ano)
        estoques = series["estoques"].get(ano)
        fornecedores = series["fornecedores"].get(ano)
        imobilizado = series["imobilizado"].get(ano)
        imobilizado_anterior = (
            series["imobilizado"].get(anos[indice - 1]) if indice > 0 else None
        )
        divida_cp = series["divida_curto_prazo"].get(ano)
        divida_lp = series["divida_longo_prazo"].get(ano)
        caixa = series["caixa_equivalentes"].get(ano)
        aplicacoes = series["aplicacoes_financeiras"].get(ano)

        # Formula: EBITDA = EBIT + D&A (D&A vem do DFC como magnitude).
        ebitda = None
        if ebit is not None and depreciacao is not None:
            ebitda = ebit + abs(depreciacao)

        # Formula: crescimento YoY = Receita_t / Receita_(t-1) - 1.
        crescimento = None
        if receita is not None and receita_anterior not in (None, 0):
            crescimento = receita / receita_anterior - 1.0

        divida_bruta = None
        if divida_cp is not None and divida_lp is not None:
            divida_bruta = abs(divida_cp) + abs(divida_lp)

        divida_liquida = None
        if divida_bruta is not None and caixa is not None:
            divida_liquida = divida_bruta - caixa - (aplicacoes or 0.0)

        # Formula: NWC = Contas a Receber + Estoques - |Fornecedores|.
        nwc = None
        if (
            contas_receber is not None
            and estoques is not None
            and fornecedores is not None
        ):
            nwc = contas_receber + estoques - abs(fornecedores)

        # Formula: CAPEX aproximado = Imobilizado_t - Imobilizado_(t-1) + D&A_t.
        # Aproximacao necessaria porque a linha de CAPEX do DFC nao esta mapeada.
        capex_aproximado = None
        if (
            imobilizado is not None
            and imobilizado_anterior is not None
            and depreciacao is not None
        ):
            capex_aproximado = imobilizado - imobilizado_anterior + abs(depreciacao)

        aliquota_efetiva = _aliquota_efetiva(ir_csll, ebt)

        # Formula: NOPAT = EBIT x (1 - aliquota efetiva do ano; 34% fallback).
        nopat = None
        if ebit is not None:
            aliquota_nopat = (
                aliquota_efetiva if aliquota_efetiva is not None else ALIQUOTA_IR_GERAL
            )
            nopat = ebit * (1 - aliquota_nopat)

        # Formula: ROIC = NOPAT / Capital Investido (NWC + Imobilizado).
        roic = None
        if nopat is not None and nwc is not None and imobilizado is not None:
            capital_investido = nwc + imobilizado
            roic = _razao(nopat, capital_investido)

        cpv_magnitude = abs(cpv) if cpv is not None else None
        dso = _razao(contas_receber, receita)
        dso = dso * DIAS_ANO if dso is not None else None
        dio = _razao(estoques, cpv_magnitude)
        dio = dio * DIAS_ANO if dio is not None else None
        dpo = _razao(
            abs(fornecedores) if fornecedores is not None else None, cpv_magnitude
        )
        dpo = dpo * DIAS_ANO if dpo is not None else None
        ccc = None
        if dso is not None and dio is not None and dpo is not None:
            # Formula: CCC = DSO + DIO - DPO.
            ccc = dso + dio - dpo

        metricas[str(ano)] = {
            "receita_liquida": receita,
            "crescimento_receita_yoy": crescimento,
            "margem_bruta": _razao(lucro_bruto, receita),
            "margem_ebitda": _razao(ebitda, receita),
            "margem_ebit": _razao(ebit, receita),
            "margem_liquida": _razao(lucro_liquido, receita),
            "ebitda": ebitda,
            "lucro_liquido": lucro_liquido,
            "aliquota_efetiva": aliquota_efetiva,
            "dso": dso,
            "dio": dio,
            "dpo": dpo,
            "ccc": ccc,
            "nwc": nwc,
            "nwc_receita": _razao(nwc, receita),
            "capex_aproximado": capex_aproximado,
            "capex_receita": _razao(capex_aproximado, receita),
            "divida_bruta": divida_bruta,
            "divida_liquida": divida_liquida,
            "divida_liquida_ebitda": _razao(divida_liquida, ebitda),
            "cobertura_juros": _razao(
                ebit,
                abs(despesas_financeiras) if despesas_financeiras is not None else None,
            ),
            "roic": roic,
        }

    return metricas


def _media_metrica(
    metricas: dict[str, dict[str, float | None]],
    campo: str,
    janela: int,
) -> float | None:
    """Media simples dos ultimos ``janela`` anos com valor definido."""
    anos = sorted(metricas)[-janela:]
    valores = [
        metricas[ano][campo] for ano in anos if metricas[ano].get(campo) is not None
    ]
    if not valores:
        return None
    return sum(valores) / len(valores)


def calcular_beta_desalavancado(
    ticker: str,
    raiz: Path,
    series: dict[str, dict[int, float]],
) -> dict[str, float | None]:
    """Beta desalavancado (Hamada) a partir do beta de mercado coletado.

    Formula: beta_U = beta_L / [1 + (1 - t) x (D/E)], com D/E contabil do
    ultimo exercicio anual. Sem beta de mercado, devolve None sem quebrar.
    """
    caminho = raiz / "data" / "raw" / "mercado" / f"{ticker}_mercado.json"
    beta_mercado: float | None = None
    if caminho.exists():
        dados = carregar_json(caminho)
        bruto = dados.get("beta_calculado")
        if isinstance(bruto, (int, float)) and not isinstance(bruto, bool):
            beta_mercado = float(bruto)

    divida_cp = series["divida_curto_prazo"]
    divida_lp = series["divida_longo_prazo"]
    pl = series["patrimonio_liquido"]
    anos_comuns = sorted(set(divida_cp) & set(divida_lp) & set(pl))

    beta_desalavancado = None
    divida_sobre_equity = None
    if beta_mercado is not None and anos_comuns:
        ano = anos_comuns[-1]
        pl_ano = pl[ano]
        if pl_ano > 0:
            divida_sobre_equity = (abs(divida_cp[ano]) + abs(divida_lp[ano])) / pl_ano
            beta_desalavancado = beta_mercado / (
                1 + (1 - ALIQUOTA_IR_GERAL) * divida_sobre_equity
            )

    return {
        "beta_mercado": beta_mercado,
        "divida_sobre_equity": divida_sobre_equity,
        "beta_desalavancado": beta_desalavancado,
    }


def calcular_metricas_historicas(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Calcula e persiste as metricas historicas do ticker.

    Trilha nao-financeira validada; para financeiras devolve apenas o
    esqueleto com aviso (validacao completa na v1.5).
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    metadados = carregar_metadados(ticker_normalizado, raiz)
    tipo = normalizar_texto(metadados.get("tipo")).replace("-", "_")

    resultado: dict[str, Any] = {
        "ticker": ticker_normalizado,
        "tipo": metadados.get("tipo"),
        "setor": metadados.get("setor"),
    }

    if tipo not in {"nao_financeira", "naofinanceira"}:
        # Esqueleto da trilha financeira (ROE/NIM/Basileia) fica para a v1.5.
        resultado["trilha"] = "financeira_nao_validada"
        resultado["metricas_por_ano"] = {}
        resultado["agregados"] = {}
    else:
        series = montar_series_anuais(ticker_normalizado, raiz)
        metricas = calcular_metricas_por_ano(series)
        agregados: dict[str, float | None] = {}
        for janela in JANELAS_CAGR:
            agregados[f"cagr_receita_{janela}a"] = calcular_cagr(
                series["receita_liquida"],
                janela,
            )
        for campo in (
            "crescimento_receita_yoy",
            "margem_bruta",
            "margem_ebitda",
            "margem_liquida",
            "capex_receita",
            "dso",
            "dio",
            "dpo",
            "ccc",
            "nwc_receita",
            "aliquota_efetiva",
            "roic",
        ):
            agregados[f"{campo}_media_3a"] = _media_metrica(metricas, campo, 3)
        agregados["margem_ebitda_maxima"] = max(
            (
                linha["margem_ebitda"]
                for linha in metricas.values()
                if linha.get("margem_ebitda") is not None
            ),
            default=None,
        )
        agregados.update(calcular_beta_desalavancado(ticker_normalizado, raiz, series))

        resultado["trilha"] = "nao_financeira"
        resultado["metricas_por_ano"] = metricas
        resultado["agregados"] = agregados

    caminho = raiz / "data" / "processed" / f"{ticker_normalizado}_metricas.json"
    salvar_json(caminho, resultado)
    resultado["caminho_saida"] = caminho
    return resultado


def imprimir_resumo(resultado: dict[str, Any]) -> None:
    """Imprime um resumo tabular das metricas para validacao visual."""
    print("\n" + "=" * 100)
    print(
        f"Metricas historicas - {resultado['ticker']} " f"({resultado.get('trilha')})"
    )
    metricas = resultado.get("metricas_por_ano", {})
    if not metricas:
        print("Sem metricas calculadas (trilha financeira fica para a v1.5).")
        return

    cabecalho = (
        f"{'Ano':<6} {'Receita':>16} {'Cresc.':>9} {'M.EBITDA':>10} "
        f"{'M.Liq':>9} {'DSO':>7} {'DIO':>7} {'DPO':>7} {'DL/EBITDA':>10}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))

    def _fmt_pct(valor: float | None) -> str:
        return f"{valor:.1%}" if valor is not None else "n/d"

    def _fmt_num(valor: float | None) -> str:
        return f"{valor:,.0f}" if valor is not None else "n/d"

    for ano in sorted(metricas):
        linha = metricas[ano]
        dl_ebitda = linha.get("divida_liquida_ebitda")
        print(
            f"{ano:<6} {_fmt_num(linha.get('receita_liquida')):>16} "
            f"{_fmt_pct(linha.get('crescimento_receita_yoy')):>9} "
            f"{_fmt_pct(linha.get('margem_ebitda')):>10} "
            f"{_fmt_pct(linha.get('margem_liquida')):>9} "
            f"{_fmt_num(linha.get('dso')):>7} "
            f"{_fmt_num(linha.get('dio')):>7} "
            f"{_fmt_num(linha.get('dpo')):>7} "
            f"{dl_ebitda if dl_ebitda is None else f'{dl_ebitda:.2f}x':>10}"
        )

    agregados = resultado.get("agregados", {})
    print("\nAgregados:")
    for chave in sorted(agregados):
        valor = agregados[chave]
        if valor is None:
            texto = "n/d"
        elif (
            "cagr" in chave
            or "margem" in chave
            or chave.startswith(("crescimento", "capex", "nwc", "aliquota", "roic"))
        ):
            texto = f"{valor:.2%}"
        else:
            texto = f"{valor:,.2f}"
        print(f"  {chave:<32} {texto}")


def main() -> None:
    """Executa as metricas para DIRR3 e MGLU3 ao rodar o arquivo direto."""
    houve_falha = False
    for ticker in ("DIRR3", "MGLU3"):
        try:
            imprimir_resumo(calcular_metricas_historicas(ticker))
        except Exception as erro:  # noqa: BLE001 - validacao operacional.
            houve_falha = True
            print(f"\nFalha ao calcular metricas de {ticker}: {erro}")
    if houve_falha:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
