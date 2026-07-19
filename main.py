"""Pipeline ponta a ponta do DCF Automatizado (Etapa 5 do ROTEIRO).

Executa, de um unico comando, a cadeia completa do valuation:

    coleta -> limpeza -> metricas -> premissas -> projecao -> valuation
    -> graficos -> Excel

Uso:
    python main.py --ticker DIRR3 --setor construcao --usar-premissas-existentes
    python main.py --ticker MGLU3 --setor varejo --usar-premissas-existentes

Cada etapa e cronometrada com timestamp; ao final o resumo imprime Target
Price, Upside, Recomendacao e o checklist de consistencia. A coleta trata
falta de rede sem quebrar: se os dados persistidos em ``data/raw/`` ja
existirem, o pipeline avisa e segue com eles (robustez de dados externos).

O tipo da empresa (financeira x nao-financeira) e detectado via
``data/raw/cvm/<TICKER>_meta.json``; a trilha financeira e bloqueada na
v1.0 (arquitetura pronta, validacao na v1.5).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

RAIZ_PROJETO = Path(__file__).resolve().parent
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.coleta.coletor_cvm import coletar_empresa  # noqa: E402
from src.coleta.coletor_macro import coletar_macro  # noqa: E402
from src.coleta.coletor_mercado import coletar_mercado  # noqa: E402
from src.exportacao.exportador_excel import exportar_excel  # noqa: E402
from src.metricas.metricas_historicas import (  # noqa: E402
    calcular_metricas_historicas,
)
from src.projecao.projetor_dre import (  # noqa: E402
    HORIZONTE_PROJECAO,
    carregar_json,
    carregar_metadados,
    normalizar_ticker,
    projetar_dre,
    salvar_json,
)
from src.projecao.dfc_indireto import projetar_dfc_indireto  # noqa: E402
from src.projecao.schedule_divida import projetar_divida  # noqa: E402
from src.projecao.schedule_leasing import projetar_leasing  # noqa: E402
from src.projecao.schedule_ppe import projetar_ppe  # noqa: E402
from src.projecao.schedule_wk import projetar_wk  # noqa: E402
from src.valuation.calculador_ev import calcular_ev  # noqa: E402
from src.valuation.calculador_fcfe import (  # noqa: E402
    calcular_fcfe_naofinanceira,
)
from src.valuation.calculador_fcff import calcular_fcff  # noqa: E402
from src.valuation.calculador_retornos import calcular_retornos  # noqa: E402
from src.valuation.calculador_vt import calcular_valor_terminal  # noqa: E402
from src.valuation.calculador_wacc import calcular_wacc  # noqa: E402
from src.valuation.checklist import (  # noqa: E402
    executar_checklist,
    imprimir_checklist,
)

# NOTA (Prompt 9.0.0 — Enxugamento): os 8 geradores de grafico de
# ``src/visualizacao/`` foram CONGELADOS (fora do nucleo). O caminho critico do
# pipeline agora e coleta -> motor -> Excel; os graficos so entram com a flag
# opcional ``--com-graficos`` (import tardio em ``etapa_graficos``).

SETORES_V1 = ("construcao", "varejo")
TICKERS_V1 = ("DIRR3", "MGLU3")

# Vetores de premissas que exigem 8 valores INDIVIDUAIS por ano (regra 5 do
# ROTEIRO): ausencia de qualquer um dos 24 campos e erro, nunca repeticao.
VETORES_PREMISSAS = ("crescimento_receita", "margem_ebitda", "capex_receita")
ESCALARES_PREMISSAS = (
    "dso",
    "dio",
    "dpo",
    "custo_divida_kd",
    "crescimento_perpetuidade_g",
    "beta",
)


class ErroPipeline(RuntimeError):
    """Erro de pipeline com mensagem orientada ao analista."""


def _timestamp() -> str:
    """Timestamp curto para o log de etapas."""
    return datetime.now().strftime("%H:%M:%S")


def executar_etapa(
    numero: int,
    total: int,
    nome: str,
    funcao: Callable[[], Any],
) -> Any:
    """Executa uma etapa cronometrada, imprimindo inicio e duracao."""
    print(f"[{_timestamp()}] ETAPA {numero}/{total} — {nome}...")
    inicio = time.perf_counter()
    resultado = funcao()
    duracao = time.perf_counter() - inicio
    print(
        f"[{_timestamp()}] ETAPA {numero}/{total} — {nome} concluida em {duracao:.1f}s"
    )
    return resultado


# ---------------------------------------------------------------------------
# Etapa 1 — Coleta (CVM + mercado + macro) com fallback offline
# ---------------------------------------------------------------------------


def _dados_cvm_existem(ticker: str) -> bool:
    """True quando os 4 JSONs da coleta CVM ja estao persistidos."""
    pasta = RAIZ_PROJETO / "data" / "raw" / "cvm"
    sufixos = ("meta", "dre", "bp", "dfc")
    return all((pasta / f"{ticker}_{sufixo}.json").exists() for sufixo in sufixos)


def etapa_coleta(ticker: str) -> None:
    """Roda os 3 coletores; sem rede, segue com os dados ja persistidos."""
    coletas: tuple[tuple[str, Callable[[], Any], Callable[[], bool]], ...] = (
        (
            "CVM (DFP/ITR)",
            lambda: coletar_empresa(ticker),
            lambda: _dados_cvm_existem(ticker),
        ),
        (
            "mercado (yfinance)",
            lambda: coletar_mercado(ticker, RAIZ_PROJETO),
            lambda: (
                RAIZ_PROJETO / "data" / "raw" / "mercado" / f"{ticker}_mercado.json"
            ).exists(),
        ),
        (
            "macro (BACEN/Focus)",
            lambda: coletar_macro(RAIZ_PROJETO),
            lambda: (
                RAIZ_PROJETO / "data" / "raw" / "macro" / "macro_brasil.json"
            ).exists(),
        ),
    )
    for nome, coletar, persistido_existe in coletas:
        try:
            coletar()
            print(f"    coleta {nome}: OK")
        except Exception as erro:  # noqa: BLE001 - fallback documentado
            if persistido_existe():
                print(
                    f"    coleta {nome}: FALHOU ({type(erro).__name__}); "
                    "usando dados ja persistidos em data/raw/"
                )
            else:
                raise ErroPipeline(
                    f"Coleta {nome} falhou e nao ha dados persistidos para "
                    f"{ticker}. Verifique a conexao e rode novamente. "
                    f"Erro original: {erro}"
                ) from erro


# ---------------------------------------------------------------------------
# Etapa 2 — Limpeza/validacao dos dados brutos
# ---------------------------------------------------------------------------


def etapa_limpeza(ticker: str) -> None:
    """Valida o contrato dos dados brutos antes do resto do pipeline.

    Decisao v1 documentada no CONTEXT: a projecao le os JSONs brutos
    mapeados diretamente (fallback oficial quando nao ha Parquet), entao a
    etapa de limpeza garante o CONTRATO — arquivos presentes, linhas com
    ``nome_padronizado``/``valor_padronizado`` e contas-chave mapeadas.
    """
    pasta = RAIZ_PROJETO / "data" / "raw" / "cvm"
    obrigatorios = {
        "dre": ("receita_liquida", "lucro_liquido"),
        "bp": ("patrimonio_liquido",),
        "dfc": ("depreciacao_amortizacao",),
    }
    for demonstrativo, contas in obrigatorios.items():
        caminho = pasta / f"{ticker}_{demonstrativo}.json"
        if not caminho.exists():
            raise ErroPipeline(f"Arquivo bruto ausente: {caminho}")
        linhas = carregar_json(caminho)
        if not isinstance(linhas, list) or not linhas:
            raise ErroPipeline(f"Arquivo bruto vazio ou invalido: {caminho}")
        nomes = {
            str(linha.get("nome_padronizado"))
            for linha in linhas
            if linha.get("valor_padronizado") is not None
        }
        faltantes = [conta for conta in contas if conta not in nomes]
        if faltantes:
            raise ErroPipeline(
                f"Contas-chave nao mapeadas em {caminho.name}: {faltantes}. "
                "Confira config/mapeamento_cvm.json e o log de contas nao "
                "mapeadas em logs/."
            )
        print(
            f"    {demonstrativo.upper()}: {len(linhas)} linhas brutas, "
            f"{len(nomes)} contas padronizadas"
        )


# ---------------------------------------------------------------------------
# Etapa 3 — Metricas historicas
# ---------------------------------------------------------------------------


def etapa_metricas(ticker: str) -> None:
    """Calcula e persiste as metricas historicas (ancoras das premissas)."""
    resultado = calcular_metricas_historicas(ticker, RAIZ_PROJETO)
    agregados = resultado.get("agregados", {})
    cagr = agregados.get("cagr_receita_3a")
    margem = agregados.get("margem_ebitda_media_3a")
    cagr_texto = f"{cagr * 100:.1f}%" if cagr is not None else "n/d"
    margem_texto = f"{margem * 100:.1f}%" if margem is not None else "n/d"
    print(f"    CAGR receita 3a: {cagr_texto} | margem EBITDA media 3a: {margem_texto}")


# ---------------------------------------------------------------------------
# Etapa 4 — Premissas (unico input humano)
# ---------------------------------------------------------------------------


def _validar_premissas(premissas: dict[str, Any], caminho: Path) -> None:
    """Confere os 8 campos individuais por vetor e os escalares minimos."""
    faltantes: list[str] = []
    for vetor in VETORES_PREMISSAS:
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            campo = f"{vetor}_ano{ano}"
            if not isinstance(premissas.get(campo), (int, float)):
                faltantes.append(campo)
    for campo in ESCALARES_PREMISSAS:
        if not isinstance(premissas.get(campo), (int, float)):
            faltantes.append(campo)
    if faltantes:
        raise ErroPipeline(
            f"Premissas incompletas em {caminho}: faltam {faltantes}. "
            "Cada vetor exige 8 valores INDIVIDUAIS por ano (nunca uma taxa "
            "unica replicada). Edite pelo app (aba Premissas) ou no JSON."
        )


def etapa_premissas(ticker: str, setor: str, usar_existentes: bool) -> None:
    """Garante premissas validas; sem a flag, protege o trabalho do analista."""
    caminho = RAIZ_PROJETO / "data" / "premissas" / f"{ticker}_premissas.json"

    if not caminho.exists():
        template = RAIZ_PROJETO / "data" / "premissas" / "template_naofinanceiras.json"
        conteudo = carregar_json(template)
        conteudo["ticker"] = ticker
        conteudo["setor"] = setor
        salvar_json(caminho, conteudo)
        raise ErroPipeline(
            f"Nao havia premissas para {ticker}. Um arquivo novo foi criado a "
            f"partir do template em {caminho}. As premissas sao o trabalho "
            "intelectual do analista: preencha os 8 valores por vetor (pelo "
            "app ou no JSON) e rode novamente com --usar-premissas-existentes."
        )

    premissas = carregar_json(caminho)
    _validar_premissas(premissas, caminho)

    if not usar_existentes:
        raise ErroPipeline(
            f"Ja existem premissas em {caminho}. Para usa-las sem revisao "
            "adicione a flag --usar-premissas-existentes; para revisa-las use "
            "a aba Premissas do app (streamlit run app.py)."
        )

    setor_premissas = str(premissas.get("setor", "")).strip().lower()
    if setor_premissas and setor_premissas != setor:
        print(
            f"    AVISO: --setor {setor} difere do setor das premissas "
            f"({setor_premissas}); o pipeline segue com as premissas."
        )
    print(f"    premissas validadas: {caminho.name} (24 campos anuais + escalares)")


# ---------------------------------------------------------------------------
# Etapas 5 e 6 — Projecao e Valuation (ordem obrigatoria do Modulo 4)
# ---------------------------------------------------------------------------


def etapa_projecao(ticker: str) -> None:
    """DRE -> WK -> PP&E -> leasing -> Divida -> DFC indireto (9.0.2)."""
    projetar_dre(ticker, RAIZ_PROJETO)
    projetar_wk(ticker, RAIZ_PROJETO)
    projetar_ppe(ticker, RAIZ_PROJETO)
    projetar_leasing(ticker, RAIZ_PROJETO)
    projetar_divida(ticker, RAIZ_PROJETO)
    projetar_dfc_indireto(ticker, RAIZ_PROJETO)
    caminho_projecao = RAIZ_PROJETO / "data" / "processed" / f"{ticker}_projecao.json"
    projecao = carregar_json(caminho_projecao)
    politica = projecao.get("politicas_projecao", {}).get("divida_balanco", "n/d")
    print(f"    DRE, WK, PP&E e Divida projetados (politica: {politica})")


def _carregar_mercado(ticker: str) -> dict[str, Any]:
    """Le o JSON de mercado coletado (Rf/preco); vazio se nao existir.

    Inline no nucleo (Prompt 9.0.0): antes vinha de
    ``src.visualizacao.apoio_cenarios``, agora fora do caminho critico.
    """
    caminho = RAIZ_PROJETO / "data" / "raw" / "mercado" / f"{ticker}_mercado.json"
    if not caminho.exists():
        return {}
    return carregar_json(caminho)


def etapa_valuation(ticker: str) -> dict[str, Any]:
    """FCFF -> WACC -> VT -> EV -> checklist, consumindo mercado persistido."""
    mercado = _carregar_mercado(ticker)
    rf_usd = mercado.get("rf_usd_tbond10y")
    preco_atual = mercado.get("preco_atual")

    calcular_fcff(ticker, RAIZ_PROJETO)
    calcular_wacc(ticker, RAIZ_PROJETO, rf_usd=rf_usd)
    calcular_valor_terminal(ticker, RAIZ_PROJETO)
    calcular_ev(ticker, RAIZ_PROJETO, preco_atual=preco_atual)
    # 9.0.3: FCFE nao-financeira (checagem do bridge) + painel de retornos.
    calcular_fcfe_naofinanceira(ticker, RAIZ_PROJETO)
    calcular_retornos(ticker, RAIZ_PROJETO)
    return executar_checklist(ticker, RAIZ_PROJETO)


# ---------------------------------------------------------------------------
# Etapas 7 e 8 — Graficos e Excel
# ---------------------------------------------------------------------------


def etapa_graficos(ticker: str) -> None:
    """Gera os 8 graficos institucionais (HTML + PNG) do ticker.

    Etapa PERIFERICA (congelada no 9.0.0): so roda com ``--com-graficos``. Os
    geradores sao importados sob demanda porque vivem em ``src/visualizacao/``,
    fora do nucleo — o import tardio mantem o caminho critico limpo.
    """
    from src.visualizacao.dashboard_final import gerar_dashboard_final
    from src.visualizacao.football_field import gerar_football_field
    from src.visualizacao.historico_vs_projetado import gerar_historico_vs_projetado
    from src.visualizacao.roic_roiic import gerar_roic_roiic
    from src.visualizacao.sensibilidade_receita_margem import (
        gerar_sensibilidade_receita_margem,
    )
    from src.visualizacao.sensibilidade_setor import gerar_sensibilidade_setor
    from src.visualizacao.sensibilidade_wacc_g import gerar_sensibilidade_wacc_g
    from src.visualizacao.waterfall_ev import gerar_waterfall_ev

    geradores: tuple[tuple[str, Callable[..., dict[str, Any]]], ...] = (
        ("football_field", gerar_football_field),
        ("waterfall_ev", gerar_waterfall_ev),
        ("sensibilidade_wacc_g", gerar_sensibilidade_wacc_g),
        ("sensibilidade_receita_margem", gerar_sensibilidade_receita_margem),
        ("sensibilidade_setor", gerar_sensibilidade_setor),
        ("historico_vs_projetado", gerar_historico_vs_projetado),
        ("roic_roiic", gerar_roic_roiic),
        ("dashboard_final", gerar_dashboard_final),
    )
    for nome, gerador in geradores:
        caminhos = gerador(ticker, RAIZ_PROJETO)
        png = "com PNG" if caminhos.get("png") else "SEM PNG (kaleido/Chrome)"
        print(f"    {nome}: HTML ok, {png}")


def etapa_excel(ticker: str) -> Path:
    """Exporta o Excel institucional de 7 abas."""
    caminho = exportar_excel(ticker, RAIZ_PROJETO)
    print(f"    Excel de 7 abas: {caminho}")
    return caminho


# ---------------------------------------------------------------------------
# Resumo final
# ---------------------------------------------------------------------------


def imprimir_resumo_final(
    ticker: str,
    caminho_excel: Path,
    checklist: dict[str, Any],
    duracao_total: float,
) -> None:
    """Resumo de decisao: Target Price, Upside, Recomendacao e checklist."""
    caminho_projecao = RAIZ_PROJETO / "data" / "processed" / f"{ticker}_projecao.json"
    projecao = carregar_json(caminho_projecao)
    ev_equity = projecao.get("ev_equity", {})
    wacc = projecao.get("wacc", {})
    valor_terminal = projecao.get("valor_terminal", {})

    target = ev_equity.get("target_price")
    preco = ev_equity.get("preco_atual")
    upside = ev_equity.get("upside")

    largura = 58
    print()
    print("=" * largura)
    print(f"RESUMO FINAL — {ticker}")
    print("=" * largura)
    linhas = (
        ("Target Price", f"R$ {target:,.2f}" if target is not None else "n/d"),
        ("Preco atual", f"R$ {preco:,.2f}" if preco is not None else "n/d"),
        ("Upside", f"{upside * 100:,.1f}%" if upside is not None else "n/d"),
        ("Recomendacao", str(ev_equity.get("recomendacao", "n/d"))),
        (
            "WACC",
            (
                f"{wacc.get('wacc') * 100:,.2f}%"
                if wacc.get("wacc") is not None
                else "n/d"
            ),
        ),
        (
            "% EV perpetuidade",
            (
                f"{valor_terminal.get('pct_ev_perpetuidade') * 100:,.1f}%"
                if valor_terminal.get("pct_ev_perpetuidade") is not None
                else "n/d"
            ),
        ),
        ("Excel", str(caminho_excel)),
        ("Graficos", str(RAIZ_PROJETO / "outputs" / "graficos")),
        ("Duracao total", f"{duracao_total:.1f}s"),
    )
    for rotulo, valor in linhas:
        print(f"{rotulo:<22}{valor}")
    print()
    imprimir_checklist(checklist)


# ---------------------------------------------------------------------------
# Orquestracao
# ---------------------------------------------------------------------------


def montar_parser() -> argparse.ArgumentParser:
    """CLI do pipeline ponta a ponta."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "Pipeline do nucleo do DCF Automatizado: coleta -> limpeza -> "
            "metricas -> premissas -> projecao -> valuation -> Excel. Os "
            "graficos (congelados no 9.0.0) entram so com --com-graficos."
        ),
    )
    parser.add_argument(
        "--ticker",
        required=True,
        help=f"Ticker da B3 (escopo v1.0: {', '.join(TICKERS_V1)})",
    )
    parser.add_argument(
        "--setor",
        required=True,
        choices=SETORES_V1,
        help="Setor da tese (v1.0: construcao ou varejo)",
    )
    parser.add_argument(
        "--usar-premissas-existentes",
        action="store_true",
        help=(
            "Usa data/premissas/<TICKER>_premissas.json sem pedir revisao. "
            "Sem a flag, o pipeline para na etapa de premissas para proteger "
            "o julgamento do analista."
        ),
    )
    parser.add_argument(
        "--com-graficos",
        action="store_true",
        help=(
            "Gera os 8 graficos institucionais (etapa PERIFERICA congelada no "
            "9.0.0, fora do nucleo). Sem a flag, o pipeline entrega o Excel "
            "direto, sem os PNGs."
        ),
    )
    return parser


def executar_pipeline(
    ticker: str,
    setor: str,
    usar_existentes: bool,
    com_graficos: bool = False,
) -> int:
    """Executa as etapas do nucleo na ordem, com timestamps e resumo final.

    Caminho critico (default): coleta -> limpeza -> metricas -> premissas ->
    projecao -> valuation -> Excel (7 etapas). Com ``com_graficos``, insere a
    etapa PERIFERICA de graficos (congelada no 9.0.0) antes do Excel.
    """
    inicio_total = time.perf_counter()
    total = 8 if com_graficos else 7
    print(f"[{_timestamp()}] DCF Automatizado — pipeline do nucleo para {ticker}")

    executar_etapa(
        1, total, "coleta (CVM + mercado + macro)", lambda: etapa_coleta(ticker)
    )

    # Deteccao de tipo via _meta.json ANTES de qualquer calculo: a trilha
    # financeira (FCFE/Ke) existe como arquitetura mas nao e validada na v1.0.
    metadados = carregar_metadados(ticker, RAIZ_PROJETO)
    tipo = str(metadados.get("tipo", "n/d"))
    print(f"    tipo detectado via _meta.json: {tipo}")
    if tipo != "nao_financeira":
        raise ErroPipeline(
            f"{ticker} foi detectada como '{tipo}'. A trilha financeira so "
            "sera validada na v1.5; o escopo da v1.0 e DIRR3 e MGLU3 "
            "(nao-financeiras)."
        )

    executar_etapa(
        2, total, "limpeza/validacao dos dados brutos", lambda: etapa_limpeza(ticker)
    )
    executar_etapa(3, total, "metricas historicas", lambda: etapa_metricas(ticker))
    executar_etapa(
        4,
        total,
        "premissas do analista",
        lambda: etapa_premissas(ticker, setor, usar_existentes),
    )
    executar_etapa(
        5, total, "projecao (DRE, WK, PP&E, Divida)", lambda: etapa_projecao(ticker)
    )
    checklist = executar_etapa(
        6,
        total,
        "valuation (FCFF, WACC, VT, EV, FCFE, retornos, checklist)",
        lambda: etapa_valuation(ticker),
    )
    if com_graficos:
        executar_etapa(
            7,
            total,
            "graficos institucionais (HTML + PNG, congelado)",
            lambda: etapa_graficos(ticker),
        )
    caminho = executar_etapa(
        total, total, "Excel de 7 abas", lambda: etapa_excel(ticker)
    )

    duracao_total = time.perf_counter() - inicio_total
    imprimir_resumo_final(ticker, caminho, checklist, duracao_total)
    return 0


def main(argumentos: list[str] | None = None) -> int:
    """Entrada da CLI; devolve o codigo de saida do processo."""
    parser = montar_parser()
    opcoes = parser.parse_args(argumentos)
    ticker = normalizar_ticker(opcoes.ticker)

    if ticker not in TICKERS_V1:
        print(
            f"AVISO: {ticker} esta fora do escopo v1.0 ({', '.join(TICKERS_V1)}). "
            "O pipeline tentara rodar, mas casos de borda da CVM nao foram "
            "validados para este ticker."
        )

    try:
        return executar_pipeline(
            ticker,
            opcoes.setor,
            opcoes.usar_premissas_existentes,
            com_graficos=opcoes.com_graficos,
        )
    except ErroPipeline as erro:
        print(f"\nERRO DE PIPELINE: {erro}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
