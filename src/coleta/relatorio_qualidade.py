"""Relatorio de qualidade de dados por empresa coletada (v2.0, Onda 1).

Para cada empresa coletada gera ``data/raw/cvm/<TICKER>_qualidade.json`` com:

- numero de anos historicos coletados (exercicios anuais 31/12 na DRE);
- contas-chave presentes por tipo de empresa (receita, EBIT, LL, ativo,
  PL, divida, caixa — EBIT/divida nao se aplicam a financeiras);
- contas nao mapeadas (pares codigo+descricao unicos, com exemplos);
- avisos (consolidado ausente, DFP defasada ou apenas ITR, sinais suspeitos);
- ``score_confiabilidade`` 0-100 decomposto em componentes auditaveis.

O score tambem e persistido no ``<TICKER>_meta.json``, fechando o contrato
da Onda 1 que as ondas seguintes leem (tipo, subtipo, metodo, score).

Formula do score (soma dos componentes, limitada a 0-100):
    contas_chave      40 x (contas-chave presentes / aplicaveis)
    anos_historicos   30 x min(anos coletados / alvo de anos, 1)
    consolidado       15 se so consolidado; 5 se individual usado; 0 se n/d
    linhas_mapeadas   15 x (linhas com nome_padronizado / linhas totais)
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.coleta.coletor_cvm import salvar_json
from src.coleta.mapeador_contas import carregar_json, normalizar_texto
from src.coleta.resolvedor_ticker import normalizar_ticker

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
DEMONSTRACOES_RELATORIO = ("dre", "bp", "dfc", "dva")
LIMITE_EXEMPLOS_NAO_MAPEADAS = 30

# Contas-chave por tipo: (demonstracao, nome_padronizado). Divida e tratada
# a parte como "uma de" CP/LP, e so se aplica a nao-financeiras (bancos
# captam via depositos, nao via emprestimos classicos).
CONTAS_CHAVE_POR_TIPO: dict[str, tuple[tuple[str, str], ...]] = {
    "nao_financeira": (
        ("dre", "receita_liquida"),
        ("dre", "ebit"),
        ("dre", "lucro_liquido"),
        ("bp", "ativo_total"),
        ("bp", "patrimonio_liquido"),
        ("bp", "caixa_equivalentes"),
    ),
    "financeira": (
        ("dre", "receitas_intermediacao_financeira"),
        ("dre", "lucro_liquido"),
        ("bp", "ativo_total"),
        ("bp", "patrimonio_liquido"),
        ("bp", "caixa_equivalentes"),
    ),
}
CONTAS_DIVIDA = ("divida_curto_prazo", "divida_longo_prazo")

PESOS_SCORE = {
    "contas_chave": 40,
    "anos_historicos": 30,
    "consolidado": 15,
    "linhas_mapeadas": 15,
}

logger = logging.getLogger(__name__)


def resolver_raiz(raiz_projeto: Path | None) -> Path:
    """Devolve a raiz do projeto, permitindo override em testes."""
    return RAIZ_PROJETO if raiz_projeto is None else Path(raiz_projeto)


def alvo_anos_historicos(raiz_projeto: Path) -> int:
    """Le o alvo de anos historicos de config/parametros.json."""
    parametros = carregar_json(raiz_projeto / "config" / "parametros.json")
    return int(parametros.get("anos_historicos_coleta", 7))


def carregar_demonstracoes(
    ticker: str,
    raiz_projeto: Path,
) -> dict[str, pd.DataFrame]:
    """Carrega os JSONs brutos coletados; demonstracao ausente vira vazia."""
    pasta = raiz_projeto / "data" / "raw" / "cvm"
    quadros: dict[str, pd.DataFrame] = {}
    for demonstracao in DEMONSTRACOES_RELATORIO:
        caminho = pasta / f"{ticker}_{demonstracao}.json"
        if not caminho.exists():
            quadros[demonstracao] = pd.DataFrame()
            continue
        registros = carregar_json(caminho)
        quadros[demonstracao] = pd.DataFrame(registros)
    return quadros


def _linhas_anuais_dfp(dados: pd.DataFrame) -> pd.DataFrame:
    """Filtra linhas DFP de fechamento anual (31/12) de uma demonstracao."""
    if dados.empty or "DT_FIM_EXERC" not in dados.columns:
        return pd.DataFrame()
    filtro = pd.Series(True, index=dados.index)
    if "tipo_documento" in dados.columns:
        filtro &= dados["tipo_documento"] == "DFP"
    datas = pd.to_datetime(dados["DT_FIM_EXERC"], errors="coerce")
    filtro &= (datas.dt.month == 12) & (datas.dt.day == 31)
    return dados[filtro]


def contar_anos_coletados(dre: pd.DataFrame) -> list[int]:
    """Anos de exercicios anuais distintos disponiveis na DRE (via DFP)."""
    anuais = _linhas_anuais_dfp(dre)
    if anuais.empty:
        return []
    anos = pd.to_datetime(anuais["DT_FIM_EXERC"], errors="coerce").dt.year
    return sorted(int(ano) for ano in anos.dropna().unique())


def _conta_presente(dados: pd.DataFrame, nome_padronizado: str) -> bool:
    """True quando existe linha mapeada com valor nao nulo para a conta."""
    if dados.empty or "nome_padronizado" not in dados.columns:
        return False
    filtro = (dados["nome_padronizado"] == nome_padronizado) & (
        dados["valor_padronizado"].notna()
    )
    return bool(filtro.any())


def _valor_ultimo_exercicio_anual(
    dados: pd.DataFrame,
    nome_padronizado: str,
) -> float | None:
    """Valor da conta no ultimo exercicio anual (menor CD_CONTA vence).

    Selecao local e defensiva (DFP, 31/12, ORDEM ULTIMO, maior data, conta
    mais curta) para os avisos de sinal suspeito — o Ano 0 oficial do
    pipeline continua sendo o do ``projetor_dre.selecionar_ultimo_exercicio``.
    """
    anuais = _linhas_anuais_dfp(dados)
    if anuais.empty or "nome_padronizado" not in anuais.columns:
        return None
    selecionado = anuais[
        (anuais["nome_padronizado"] == nome_padronizado)
        & (anuais["valor_padronizado"].notna())
    ].copy()
    if "ORDEM_EXERC" in selecionado.columns:
        ordem = selecionado["ORDEM_EXERC"].map(normalizar_texto)
        ultimos = selecionado[ordem == "ultimo"]
        if not ultimos.empty:
            selecionado = ultimos.copy()
    if selecionado.empty:
        return None
    selecionado["_data"] = pd.to_datetime(selecionado["DT_FIM_EXERC"], errors="coerce")
    selecionado = selecionado[selecionado["_data"] == selecionado["_data"].max()]
    if "CD_CONTA" in selecionado.columns:
        tamanhos = selecionado["CD_CONTA"].astype(str).str.len()
        selecionado = selecionado.loc[tamanhos.sort_values().index]
    return float(selecionado.iloc[0]["valor_padronizado"])


def avaliar_contas_chave(
    tipo: str,
    quadros: dict[str, pd.DataFrame],
) -> dict[str, bool]:
    """Presenca das contas-chave do tipo, incluindo divida CP-ou-LP."""
    contas = CONTAS_CHAVE_POR_TIPO.get(tipo, CONTAS_CHAVE_POR_TIPO["nao_financeira"])
    presencas: dict[str, bool] = {}
    for demonstracao, nome in contas:
        presencas[nome] = _conta_presente(
            quadros.get(demonstracao, pd.DataFrame()),
            nome,
        )
    if tipo != "financeira":
        bp = quadros.get("bp", pd.DataFrame())
        presencas["divida_cp_ou_lp"] = any(
            _conta_presente(bp, nome) for nome in CONTAS_DIVIDA
        )
    return presencas


def levantar_contas_nao_mapeadas(
    quadros: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    """Pares (demonstracao, codigo, descricao) unicos sem nome padronizado."""
    pares: list[dict[str, str]] = []
    vistos: set[tuple[str, str, str]] = set()
    for demonstracao, dados in quadros.items():
        if dados.empty or "nome_padronizado" not in dados.columns:
            continue
        sem_nome = dados[dados["nome_padronizado"].isna()]
        for codigo, descricao in zip(
            sem_nome.get("CD_CONTA", pd.Series(dtype=object)),
            sem_nome.get("DS_CONTA", pd.Series(dtype=object)),
        ):
            chave = (demonstracao, str(codigo), str(descricao))
            if chave in vistos:
                continue
            vistos.add(chave)
            pares.append(
                {
                    "demonstracao": demonstracao,
                    "codigo": str(codigo),
                    "descricao": str(descricao),
                }
            )
    pares.sort(key=lambda par: (par["demonstracao"], par["codigo"]))
    return {
        "quantidade_pares": len(pares),
        "exemplos": pares[:LIMITE_EXEMPLOS_NAO_MAPEADAS],
    }


def contar_linhas_mapeadas(quadros: dict[str, pd.DataFrame]) -> tuple[int, int]:
    """Devolve (linhas totais, linhas com nome_padronizado) das demonstracoes."""
    totais = 0
    mapeadas = 0
    for dados in quadros.values():
        if dados.empty:
            continue
        totais += len(dados)
        if "nome_padronizado" in dados.columns:
            mapeadas += int(dados["nome_padronizado"].notna().sum())
    return totais, mapeadas


def montar_avisos(
    meta: dict[str, Any],
    quadros: dict[str, pd.DataFrame],
    anos_coletados: list[int],
) -> list[str]:
    """Avisos de qualidade: consolidacao, defasagem de DFP e sinais suspeitos."""
    avisos: list[str] = []
    if meta.get("consolidado") is False:
        avisos.append(
            "Demonstracoes consolidadas ausentes em parte dos exercicios; "
            "demonstracoes individuais usadas como fallback."
        )

    dre = quadros.get("dre", pd.DataFrame())
    tem_itr = (
        not dre.empty
        and "tipo_documento" in dre.columns
        and bool((dre["tipo_documento"] == "ITR").any())
    )
    if not anos_coletados:
        if tem_itr:
            avisos.append(
                "Nenhum exercicio anual (DFP) coletado; apenas ITR disponivel "
                "— o Ano 0 do pipeline exige fechamento anual."
            )
        else:
            avisos.append("Nenhuma DRE coletada; empresa sem dados utilizaveis.")
    elif max(anos_coletados) < date.today().year - 1:
        avisos.append(
            f"DFP mais recente e do exercicio {max(anos_coletados)}; "
            "dados anuais defasados."
        )

    tipo = str(meta.get("tipo", "nao_financeira"))
    nome_receita = (
        "receitas_intermediacao_financeira"
        if tipo == "financeira"
        else "receita_liquida"
    )
    receita = _valor_ultimo_exercicio_anual(dre, nome_receita)
    if receita is not None and receita <= 0:
        avisos.append(f"Sinal suspeito: {nome_receita} <= 0 no ultimo exercicio anual.")

    bp = quadros.get("bp", pd.DataFrame())
    ativo_total = _valor_ultimo_exercicio_anual(bp, "ativo_total")
    if ativo_total is not None and ativo_total <= 0:
        avisos.append("Sinal suspeito: ativo_total <= 0 no ultimo exercicio anual.")
    patrimonio = _valor_ultimo_exercicio_anual(bp, "patrimonio_liquido")
    if patrimonio is not None and patrimonio < 0:
        avisos.append(
            "Patrimonio liquido negativo no ultimo exercicio anual "
            "(valido, mas exige atencao no valuation)."
        )
    return avisos


def calcular_score(
    contas_chave: dict[str, bool],
    anos_coletados: list[int],
    alvo_anos: int,
    consolidado: bool | None,
    linhas_totais: int,
    linhas_mapeadas: int,
) -> tuple[int, dict[str, float]]:
    """Aplica a formula documentada do score e devolve os componentes."""
    total_contas = max(len(contas_chave), 1)
    presentes = sum(1 for presente in contas_chave.values() if presente)
    componente_contas = PESOS_SCORE["contas_chave"] * presentes / total_contas

    alvo = max(alvo_anos, 1)
    componente_anos = PESOS_SCORE["anos_historicos"] * min(
        len(anos_coletados) / alvo, 1.0
    )

    if consolidado is True:
        componente_consolidado = float(PESOS_SCORE["consolidado"])
    elif consolidado is False:
        componente_consolidado = 5.0
    else:
        componente_consolidado = 0.0

    proporcao_mapeadas = linhas_mapeadas / linhas_totais if linhas_totais else 0.0
    componente_mapeamento = PESOS_SCORE["linhas_mapeadas"] * proporcao_mapeadas

    componentes = {
        "contas_chave": round(componente_contas, 2),
        "anos_historicos": round(componente_anos, 2),
        "consolidado": round(componente_consolidado, 2),
        "linhas_mapeadas": round(componente_mapeamento, 2),
    }
    score = round(sum(componentes.values()))
    return max(0, min(100, score)), componentes


def avaliar_qualidade(
    meta: dict[str, Any],
    quadros: dict[str, pd.DataFrame],
    alvo_anos: int,
) -> dict[str, Any]:
    """Monta o relatorio de qualidade (funcao pura para testes)."""
    tipo = str(meta.get("tipo", "nao_financeira"))
    anos_coletados = contar_anos_coletados(quadros.get("dre", pd.DataFrame()))
    contas_chave = avaliar_contas_chave(tipo, quadros)
    linhas_totais, linhas_mapeadas = contar_linhas_mapeadas(quadros)
    nao_mapeadas = levantar_contas_nao_mapeadas(quadros)
    avisos = montar_avisos(meta, quadros, anos_coletados)
    score, componentes = calcular_score(
        contas_chave=contas_chave,
        anos_coletados=anos_coletados,
        alvo_anos=alvo_anos,
        consolidado=meta.get("consolidado"),
        linhas_totais=linhas_totais,
        linhas_mapeadas=linhas_mapeadas,
    )
    return {
        "ticker": meta.get("ticker"),
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "tipo": tipo,
        "subtipo": meta.get("subtipo"),
        "consolidado": meta.get("consolidado"),
        "anos_coletados": anos_coletados,
        "quantidade_anos": len(anos_coletados),
        "alvo_anos": alvo_anos,
        "contas_chave": contas_chave,
        "contas_chave_ausentes": sorted(
            nome for nome, presente in contas_chave.items() if not presente
        ),
        "linhas_totais": linhas_totais,
        "linhas_mapeadas": linhas_mapeadas,
        "contas_nao_mapeadas": nao_mapeadas,
        "avisos": avisos,
        "componentes_score": componentes,
        "score_confiabilidade": score,
    }


def _atualizar_score_no_meta(
    caminho_meta: Path,
    score: int,
) -> None:
    """Grava o score no _meta.json preservando os demais campos do contrato."""
    meta = carregar_json(caminho_meta)
    meta["score_confiabilidade"] = int(score)
    salvar_json(caminho_meta, meta)


def gerar_relatorio_qualidade(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Gera e persiste o relatorio de qualidade de um ticker coletado.

    Persiste ``data/raw/cvm/<TICKER>_qualidade.json`` e atualiza o
    ``score_confiabilidade`` no ``<TICKER>_meta.json``. Exige coleta previa
    (o _meta.json precisa existir); demonstracoes ausentes nao quebram —
    apenas rebaixam o score e entram nos avisos.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    pasta = raiz / "data" / "raw" / "cvm"
    caminho_meta = pasta / f"{ticker_normalizado}_meta.json"
    meta = carregar_json(caminho_meta)

    quadros = carregar_demonstracoes(ticker_normalizado, raiz)
    relatorio = avaliar_qualidade(meta, quadros, alvo_anos_historicos(raiz))
    relatorio["ticker"] = ticker_normalizado

    salvar_json(pasta / f"{ticker_normalizado}_qualidade.json", relatorio)
    _atualizar_score_no_meta(caminho_meta, relatorio["score_confiabilidade"])
    logger.info(
        "Relatorio de qualidade de %s: score %s (%s avisos).",
        ticker_normalizado,
        relatorio["score_confiabilidade"],
        len(relatorio["avisos"]),
    )
    return relatorio


def imprimir_relatorio(relatorio: dict[str, Any]) -> None:
    """Imprime um resumo legivel do relatorio para validacao manual."""
    print("\n" + "=" * 72)
    print(
        f"{relatorio['ticker']} | tipo {relatorio['tipo']} / "
        f"{relatorio.get('subtipo', 'n/d')} | score "
        f"{relatorio['score_confiabilidade']}/100"
    )
    print(
        f"Anos coletados ({relatorio['quantidade_anos']}/"
        f"{relatorio['alvo_anos']}): {relatorio['anos_coletados']}"
    )
    ausentes = relatorio["contas_chave_ausentes"]
    print(f"Contas-chave ausentes: {ausentes if ausentes else 'nenhuma'}")
    print(
        "Linhas mapeadas: "
        f"{relatorio['linhas_mapeadas']}/{relatorio['linhas_totais']} | "
        "contas nao mapeadas (pares unicos): "
        f"{relatorio['contas_nao_mapeadas']['quantidade_pares']}"
    )
    for aviso in relatorio["avisos"]:
        print(f"  AVISO: {aviso}")


def main() -> None:
    """Gera relatorios de qualidade via linha de comando."""
    parser = argparse.ArgumentParser(
        description="Relatorio de qualidade de dados CVM por ticker coletado."
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        default=["DIRR3", "MGLU3"],
        help="Tickers ja coletados (default: DIRR3 MGLU3).",
    )
    argumentos = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    for ticker in argumentos.tickers:
        try:
            relatorio = gerar_relatorio_qualidade(ticker)
        except RuntimeError as erro:
            print(f"Falha no relatorio de {ticker}: {erro}")
            continue
        imprimir_relatorio(relatorio)


if __name__ == "__main__":
    main()
