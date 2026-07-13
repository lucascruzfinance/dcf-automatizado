"""Front-end institucional do DCF Automatizado (Streamlit) — v2.0 Onda 4.

Estacao de trabalho de analista MULTI-EMPRESA: qualquer ticker da B3 entra
pela sidebar (o app dispara o pipeline universal com feedback de progresso),
e as secoes apresentam os JSONs persistidos pelo motor — Overview com
cenarios, Historico por tipo (metricas bancarias para financeiras),
Premissas editaveis em tabela, Valuation por metodo (FCFF/WACC ou FCFE/Ke),
Comparaveis com triangulacao, Analise com tornado e sensibilidades vivas,
Comparar (2-5 empresas + watchlist) e Excel Preview.

Regra dura: o app NUNCA recalcula valuation — edita premissas e dispara o
motor Python (fonte unica de verdade).
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

RAIZ_PROJETO = Path(__file__).resolve().parent
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.exportacao.exportador_excel import (  # noqa: E402
    NOMES_ABAS,
    caminho_excel,
    exportar_excel,
    montar_preview_por_aba,
)
from src.metricas.metricas_historicas import (  # noqa: E402
    calcular_metricas_historicas,
)
from src.pipeline import (  # noqa: E402
    rodar_motor_valuation,
    rodar_pipeline_universal,
)
from src.projecao.projetor_dre import (  # noqa: E402
    HORIZONTE_PROJECAO,
    carregar_json,
    salvar_json,
)
from src.valuation.comparaveis import (  # noqa: E402
    ROTULOS_MULTIPLOS,
    carregar_comparaveis,
    gerar_comparaveis,
)
from src.visualizacao.apoio_cenarios import (  # noqa: E402
    carregar_metricas,
    recalcular_cenario,
)
from src.visualizacao.comparacao_empresas import (  # noqa: E402
    gerar_comparacao_empresas,
    montar_painel_comparacao,
)
from src.visualizacao.dashboard_final import gerar_dashboard_final  # noqa: E402
from src.visualizacao.football_field import gerar_football_field  # noqa: E402
from src.visualizacao.historico_vs_projetado import (  # noqa: E402
    gerar_historico_vs_projetado,
)
from src.visualizacao.roic_roiic import gerar_roic_roiic  # noqa: E402
from src.visualizacao.sensibilidade_receita_margem import (  # noqa: E402
    gerar_sensibilidade_receita_margem,
)
from src.visualizacao.sensibilidade_setor import (  # noqa: E402
    gerar_sensibilidade_setor,
)
from src.visualizacao.sensibilidade_wacc_g import (  # noqa: E402
    gerar_sensibilidade_wacc_g,
)
from src.visualizacao.tabela_comparaveis import (  # noqa: E402
    gerar_tabela_comparaveis,
)
from src.visualizacao.tornado import gerar_tornado  # noqa: E402
from src.visualizacao.waterfall_ev import gerar_waterfall_ev  # noqa: E402
from src.visualizacao.tema_institucional import (  # noqa: E402
    COR_TEXTO_SECUNDARIO,
    COR_VERDE_UPSIDE,
    COR_VERMELHO_DOWNSIDE,
    formatar_moeda_brl,
    formatar_percentual_br,
)

TICKERS_REFERENCIA = ("DIRR3", "MGLU3")
SECOES = (
    "Overview",
    "Historico",
    "Premissas",
    "Valuation",
    "Comparaveis",
    "Analise",
    "Comparar",
    "Excel Preview",
)
LIMITE_ALERTA_MARGEM_PP = 0.05
CAMINHO_WATCHLIST = RAIZ_PROJETO / "data" / "watchlist.json"

VETORES_NAO_FINANCEIRA = (
    ("crescimento_receita", "Crescimento da receita"),
    ("margem_ebitda", "Margem EBITDA"),
    ("capex_receita", "CAPEX / Receita (negativo = saida)"),
)
VETORES_FINANCEIRA = (
    ("crescimento_receita", "Crescimento das receitas de intermediacao"),
    ("margem_resultado_bruto", "Margem do resultado bruto"),
    ("despesas_operacionais_receita", "Despesas operacionais / receitas"),
)


def caminho_premissas(ticker: str) -> Path:
    """Caminho do JSON de premissas do ticker."""
    return RAIZ_PROJETO / "data" / "premissas" / f"{ticker}_premissas.json"


def caminho_projecao(ticker: str) -> Path:
    """Caminho da projecao persistida pelo motor."""
    return RAIZ_PROJETO / "data" / "processed" / f"{ticker}_projecao.json"


def listar_empresas_analisadas() -> list[str]:
    """Tickers com projecao persistida em data/processed/."""
    pasta = RAIZ_PROJETO / "data" / "processed"
    if not pasta.exists():
        return []
    return sorted(
        caminho.name.replace("_projecao.json", "")
        for caminho in pasta.glob("*_projecao.json")
    )


@st.cache_data(show_spinner=False)
def _carregar_projecao_cacheada(ticker: str, mtime: float) -> dict[str, Any]:
    """Le a projecao persistida com cache invalidado por mtime."""
    return carregar_json(caminho_projecao(ticker))


def carregar_projecao_app(ticker: str) -> dict[str, Any] | None:
    """Carrega a projecao persistida; None quando o pipeline nao rodou."""
    caminho = caminho_projecao(ticker)
    if not caminho.exists():
        return None
    conteudo = _carregar_projecao_cacheada(ticker, caminho.stat().st_mtime)
    if not isinstance(conteudo.get("ev_equity"), dict):
        return None
    return conteudo


def carregar_meta(ticker: str) -> dict[str, Any]:
    """Metadados da coleta (tipo, subtipo, score)."""
    caminho = RAIZ_PROJETO / "data" / "raw" / "cvm" / f"{ticker}_meta.json"
    if not caminho.exists():
        return {}
    return carregar_json(caminho)


def empresa_financeira(ticker: str, conteudo: dict[str, Any] | None) -> bool:
    """Detecta a trilha financeira pelo meta ou pela projecao."""
    meta = carregar_meta(ticker)
    if str(meta.get("tipo")) == "financeira":
        return True
    return bool(conteudo and str(conteudo.get("tipo")) == "financeira")


def obter_metricas(ticker: str) -> dict[str, Any]:
    """Metricas historicas persistidas; calcula na primeira execucao."""
    metricas = carregar_metricas(ticker, RAIZ_PROJETO)
    if not metricas.get("metricas_por_ano"):
        try:
            metricas = calcular_metricas_historicas(ticker, RAIZ_PROJETO)
        except RuntimeError:
            return metricas or {}
    return metricas


def carregar_watchlist() -> dict[str, Any]:
    """Watchlist persistida em data/watchlist.json."""
    if not CAMINHO_WATCHLIST.exists():
        return {"tickers": {}}
    return carregar_json(CAMINHO_WATCHLIST)


def atualizar_watchlist(ticker: str, remover: bool = False) -> None:
    """Adiciona/remove o ticker na watchlist com o ultimo resultado."""
    watchlist = carregar_watchlist()
    if remover:
        watchlist["tickers"].pop(ticker, None)
    else:
        conteudo = carregar_projecao_app(ticker) or {}
        ev_equity = conteudo.get("ev_equity", {})
        watchlist["tickers"][ticker] = {
            "target_price": ev_equity.get("target_price"),
            "recomendacao": ev_equity.get("recomendacao"),
            "upside": ev_equity.get("upside"),
            "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        }
    salvar_json(CAMINHO_WATCHLIST, watchlist)


def executar_pipeline_com_status(ticker: str, forcar: bool) -> None:
    """Roda o pipeline universal exibindo o progresso por etapa."""
    with st.status(
        f"Analisando {ticker} — pipeline universal...", expanded=True
    ) as status:
        try:
            resumo = rodar_pipeline_universal(
                ticker,
                RAIZ_PROJETO,
                forcar_recoleta=forcar,
                callback_status=lambda mensagem: st.write(mensagem),
            )
        except Exception as erro:  # noqa: BLE001 - erro vai para a UI
            status.update(label=f"Falha ao analisar {ticker}", state="error")
            st.error(
                f"O pipeline falhou para {ticker}: {erro}. Verifique o "
                "ticker (ex.: PETR4, WEGE3) e os logs em logs/."
            )
            return
        for aviso in resumo.get("avisos", []):
            st.warning(aviso)
        status.update(
            label=(
                f"{ticker} analisado em {resumo['duracao_total_s']}s "
                f"(score {resumo.get('score_confiabilidade', 'n/d')})"
            ),
            state="complete",
        )
    st.session_state["ticker"] = ticker
    _carregar_projecao_cacheada.clear()
    st.rerun()


URL_FONTES_INSTITUCIONAIS = (
    "https://fonts.googleapis.com/css2"
    "?family=IBM+Plex+Mono:wght@400;600"
    "&family=Inter:wght@400;600;700&display=swap"
)


def aplicar_estilo_institucional() -> None:
    """Injeta tipografia monoespacada nos numeros (padrao institucional)."""
    st.markdown(
        f"""
        <style>
        @import url('{URL_FONTES_INSTITUCIONAIS}');
        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
        [data-testid="stMetricValue"], [data-testid="stMetricDelta"] {{
            font-family: 'IBM Plex Mono', monospace;
        }}
        [data-testid="stSidebar"] {{ border-right: 1px solid #1E3350; }}
        div[data-testid="stDataFrame"] * {{
            font-variant-numeric: tabular-nums;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def painel_decisao(
    conteudo: dict[str, Any],
    cenario: dict[str, Any] | None = None,
) -> None:
    """Faixa de decisao: Target, Upside e Recomendacao (cenario opcional)."""
    ev_equity = conteudo["ev_equity"]
    financeira = str(conteudo.get("tipo")) == "financeira"
    fonte = cenario if cenario else ev_equity
    target = float(fonte["target_price"])
    upside = float(fonte.get("upside") or 0.0)
    recomendacao = str(fonte.get("recomendacao", "n/d"))
    preco = float(ev_equity.get("preco_atual") or 0.0)

    if financeira:
        taxa = float(conteudo.get("ke", {}).get("ke_brl") or 0.0)
        rotulo_taxa = "Ke"
    else:
        taxa = float(conteudo.get("wacc", {}).get("wacc") or 0.0)
        rotulo_taxa = "WACC"
    g = float(conteudo.get("valor_terminal", {}).get("g") or 0.0)
    if cenario:
        if cenario.get("taxa_desconto") is not None:
            taxa = float(cenario["taxa_desconto"])
        if cenario.get("g") is not None:
            g = float(cenario["g"])

    colunas = st.columns(5)
    colunas[0].metric("Target Price", formatar_moeda_brl(target))
    colunas[1].metric(
        "Preco atual",
        formatar_moeda_brl(preco),
        delta=formatar_percentual_br(upside),
        delta_color="normal",
    )
    cor = COR_VERDE_UPSIDE if upside >= 0 else COR_VERMELHO_DOWNSIDE
    colunas[2].markdown(
        f"<div style='font-size:14px;color:{COR_TEXTO_SECUNDARIO}'>"
        "Recomendacao</div>"
        f"<div style='font-family:IBM Plex Mono,monospace;font-size:30px;"
        f"font-weight:600;color:{cor}'>{recomendacao}</div>",
        unsafe_allow_html=True,
    )
    colunas[3].metric(rotulo_taxa, formatar_percentual_br(taxa, 2))
    colunas[4].metric("g (perpetuidade)", formatar_percentual_br(g, 2))


def _aviso_premissas_automaticas(ticker: str) -> None:
    """Alerta quando as premissas ainda sao o ponto de partida automatico."""
    caminho = caminho_premissas(ticker)
    if not caminho.exists():
        return
    premissas = carregar_json(caminho)
    if premissas.get("premissas_automaticas"):
        st.warning(
            "PREMISSAS AUTOMATICAS DE PARTIDA em uso (ancoras historicas + "
            "defaults do subtipo). A tese e do analista: revise na secao "
            "Premissas e salve para assumir a autoria."
        )


def secao_overview(ticker: str, conteudo: dict[str, Any]) -> None:
    """Capa viva: KPIs de decisao, cenarios e qualidade dos dados."""
    cenarios = conteudo.get("cenarios", {})
    cenario_ativo = None
    if cenarios:
        rotulos = {"Bear": "bear", "Base": "base", "Bull": "bull"}
        escolha = st.radio(
            "Cenario (motor de cenarios — pipeline completo por cenario)",
            list(rotulos),
            index=1,
            horizontal=True,
        )
        cenario_ativo = cenarios.get(rotulos[escolha])
        if escolha != "Base" and cenario_ativo:
            st.caption(f"Cenario {escolha}: ajustes {cenario_ativo.get('ajustes', {})}")
    painel_decisao(conteudo, cenario_ativo if cenario_ativo else None)

    meta = carregar_meta(ticker)
    checklist = conteudo.get("checklist", {})
    aprovado = checklist.get("aprovado") is True
    valor_terminal = conteudo.get("valor_terminal", {})
    pct = valor_terminal.get("pct_ev_perpetuidade")
    st.caption(
        f"{meta.get('razao_social', ticker)} | "
        f"{meta.get('tipo', 'n/d')}/{meta.get('subtipo', 'n/d')} | "
        f"metodo {meta.get('metodo_valuation', 'n/d')} | "
        f"score de dados {meta.get('score_confiabilidade', 'n/d')}/100 | "
        f"checklist {'APROVADO' if aprovado else 'REPROVADO'} | perpetuidade "
        f"{formatar_percentual_br(float(pct)) if pct is not None else 'n/d'}"
        " do EV"
    )
    _aviso_premissas_automaticas(ticker)

    if str(conteudo.get("tipo")) == "financeira":
        fcfe = conteudo.get("fcfe", {})
        if fcfe:
            quadro = pd.DataFrame(fcfe).T
            st.subheader("FCFE projetado (LL - ΔCapital regulatorio)")
            st.dataframe(
                quadro[
                    ["lucro_liquido", "delta_capital_regulatorio", "fcfe"]
                ].style.format("{:,.0f}"),
                width="stretch",
            )
        resultado_football = gerar_football_field(ticker, RAIZ_PROJETO)
        st.plotly_chart(resultado_football["figura"], width="stretch")
        return

    resultado = gerar_dashboard_final(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado["figura"], width="stretch")


def _historico_financeira(ticker: str) -> None:
    """Metricas bancarias historicas (ROE, ROA, NIM, eficiencia)."""
    metricas = obter_metricas(ticker)
    por_ano = metricas.get("metricas_por_ano", {})
    if not por_ano:
        st.warning("Sem metricas historicas bancarias para este ticker.")
        return
    quadro = pd.DataFrame(por_ano).T.sort_index()
    colunas_pct = [
        "crescimento_receitas_yoy",
        "roe",
        "roa",
        "margem_resultado_bruto",
        "despesas_operacionais_receita",
        "margem_liquida_receitas",
        "nim_aproximada",
        "indice_eficiencia",
        "aliquota_efetiva",
    ]
    formato = {coluna: "{:.1%}" for coluna in colunas_pct if coluna in quadro}
    for coluna in ("receitas_intermediacao_financeira", "lucro_liquido"):
        if coluna in quadro:
            formato[coluna] = "{:,.0f}"
    st.subheader("Metricas bancarias anuais (exercicios CVM)")
    st.dataframe(quadro.style.format(formato, na_rep="n/d"), width="stretch")

    agregados = metricas.get("agregados", {})
    colunas = st.columns(4)
    ancoras = (
        ("ROE medio 3a", agregados.get("roe_media_3a")),
        ("ROA medio 3a", agregados.get("roa_media_3a")),
        ("NIM aprox. 3a", agregados.get("nim_aproximada_media_3a")),
        ("Eficiencia 3a", agregados.get("indice_eficiencia_media_3a")),
    )
    for coluna, (rotulo, valor) in zip(colunas, ancoras):
        texto = formatar_percentual_br(float(valor)) if valor is not None else "n/d"
        coluna.metric(rotulo, texto)
    for aviso in metricas.get("avisos", []):
        st.caption(f"AVISO: {aviso}")


def secao_historico(ticker: str, financeira: bool) -> None:
    """Metricas historicas por tipo de empresa."""
    if financeira:
        _historico_financeira(ticker)
        return

    metricas = obter_metricas(ticker)
    por_ano = metricas.get("metricas_por_ano", {})
    if not por_ano:
        st.warning("Sem metricas historicas para este ticker.")
        return

    quadro = pd.DataFrame(por_ano).T.sort_index()
    colunas_pct = [
        "crescimento_receita_yoy",
        "margem_bruta",
        "margem_ebitda",
        "margem_ebit",
        "margem_liquida",
        "aliquota_efetiva",
        "nwc_receita",
        "capex_receita",
        "roic",
        "roiic",
    ]
    formato: dict[str, Any] = {c: "{:.1%}" for c in colunas_pct if c in quadro}
    for coluna in ("dso", "dio", "dpo", "ccc"):
        if coluna in quadro:
            formato[coluna] = "{:,.0f}"
    if "divida_liquida_ebitda" in quadro:
        formato["divida_liquida_ebitda"] = "{:,.2f}x"
    if "cobertura_juros" in quadro:
        formato["cobertura_juros"] = "{:,.2f}x"
    st.subheader("Metricas anuais (exercicios CVM)")
    st.dataframe(quadro.style.format(formato, na_rep="n/d"), width="stretch")

    agregados = metricas.get("agregados", {})
    st.subheader("Agregados (ancoras para premissas)")
    colunas = st.columns(4)
    ancoras = (
        ("CAGR receita 3a", agregados.get("cagr_receita_3a"), True),
        ("Margem EBITDA media 3a", agregados.get("margem_ebitda_media_3a"), True),
        ("CAPEX/Receita media 3a", agregados.get("capex_receita_media_3a"), True),
        ("Beta desalavancado", agregados.get("beta_desalavancado"), False),
    )
    for coluna, (rotulo, valor, eh_pct) in zip(colunas, ancoras):
        if valor is None:
            texto = "n/d"
        elif eh_pct:
            texto = formatar_percentual_br(float(valor))
        else:
            texto = f"{float(valor):.2f}"
        coluna.metric(rotulo, texto)

    resultado = gerar_historico_vs_projetado(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado["figura"], width="stretch")


def _editor_vetores(
    premissas: dict[str, Any],
    vetores: tuple[tuple[str, str], ...],
) -> dict[str, float]:
    """Tabela EDITAVEL dos vetores anuais (8 valores individuais por linha).

    st.data_editor nativo no lugar do streamlit-aggrid (decisao D-005 do
    Humano_revisar.md: testavel via AppTest e alinhado ao tema). Editar uma
    celula NAO recalcula em JS — o botao Salvar dispara o motor Python.
    """
    linhas = {}
    for campo_base, rotulo in vetores:
        linhas[rotulo] = [
            float(premissas.get(f"{campo_base}_ano{ano}", 0.0) or 0.0)
            for ano in range(1, HORIZONTE_PROJECAO + 1)
        ]
    quadro = pd.DataFrame(
        linhas,
        index=[f"Ano {ano}" for ano in range(1, HORIZONTE_PROJECAO + 1)],
    ).T
    editado = st.data_editor(
        quadro,
        width="stretch",
        column_config={
            coluna: st.column_config.NumberColumn(format="%.4f")
            for coluna in quadro.columns
        },
    )

    novos: dict[str, float] = {}
    for campo_base, rotulo in vetores:
        for indice, ano in enumerate(range(1, HORIZONTE_PROJECAO + 1)):
            novos[f"{campo_base}_ano{ano}"] = float(editado.loc[rotulo].iloc[indice])
    return novos


def _salvar_e_recalcular(ticker: str, novas: dict[str, Any]) -> None:
    """Persiste premissas revisadas e reexecuta o motor oficial."""
    novas = dict(novas)
    # Ao salvar, o analista assume a autoria da tese.
    novas["premissas_automaticas"] = False
    salvar_json(caminho_premissas(ticker), novas)
    with st.spinner("Rodando o motor de valuation..."):
        rodar_motor_valuation(ticker, RAIZ_PROJETO)
    _carregar_projecao_cacheada.clear()
    st.success("Premissas salvas e valuation recalculado pelo motor.")
    st.rerun()


def _premissas_nao_financeira(
    ticker: str,
    premissas: dict[str, Any],
    conteudo: dict[str, Any] | None,
) -> None:
    """Editor de premissas da trilha FCFF/WACC."""
    metricas = obter_metricas(ticker)
    agregados = metricas.get("agregados", {})
    st.caption(
        "Vetores anuais EDITAVEIS na tabela (8 valores individuais por "
        "regra do projeto). Ancoras historicas: CAGR 3a "
        f"{formatar_percentual_br(float(agregados.get('cagr_receita_3a') or 0))}"
        " | margem EBITDA 3a "
        + formatar_percentual_br(float(agregados.get("margem_ebitda_media_3a") or 0))
        + " | CAPEX/receita 3a "
        + formatar_percentual_br(float(agregados.get("capex_receita_media_3a") or 0))
    )
    novas: dict[str, Any] = dict(premissas)
    novas.update(_editor_vetores(premissas, VETORES_NAO_FINANCEIRA))

    st.subheader("Capital de giro e custo de capital")
    coluna_esquerda, coluna_direita = st.columns(2)
    with coluna_esquerda:
        novas["dso"] = st.slider("DSO em dias", 0, 400, int(premissas.get("dso", 30)))
        novas["dio"] = st.slider("DIO em dias", 0, 500, int(premissas.get("dio", 30)))
        novas["dpo"] = st.slider("DPO em dias", 0, 400, int(premissas.get("dpo", 30)))
        novas["payout_dividendos"] = st.slider(
            "Payout de dividendos",
            0.0,
            1.0,
            float(premissas.get("payout_dividendos", 0.0) or 0.0),
            step=0.05,
        )
    with coluna_direita:
        novas["beta"] = st.slider(
            "Beta desalavancado",
            0.2,
            3.0,
            float(premissas.get("beta", 1.0)),
            step=0.05,
        )
        novas["custo_divida_kd"] = st.slider(
            "Kd — custo da divida (decimal)",
            0.01,
            0.35,
            float(premissas.get("custo_divida_kd", 0.10)),
            step=0.005,
            format="%.3f",
        )
        # Teto de 25% permite testar deliberadamente o bloqueio g >= WACC.
        novas["crescimento_perpetuidade_g"] = st.slider(
            "g — crescimento na perpetuidade (decimal)",
            0.0,
            0.25,
            float(premissas.get("crescimento_perpetuidade_g", 0.02)),
            step=0.0025,
            format="%.4f",
        )

    # Validacao em tempo real (1): g >= WACC bloqueia o salvamento.
    wacc_atual = None
    if conteudo is not None and isinstance(conteudo.get("wacc"), dict):
        wacc_atual = conteudo["wacc"].get("wacc")
    g_novo = float(novas["crescimento_perpetuidade_g"])
    bloqueado = False
    if wacc_atual is not None and g_novo >= float(wacc_atual):
        st.error(
            f"BLOQUEADO: g ({formatar_percentual_br(g_novo, 2)}) >= WACC "
            f"({formatar_percentual_br(float(wacc_atual), 2)}). A perpetuidade "
            "de Gordon explode — reduza o g antes de salvar."
        )
        bloqueado = True
    if g_novo > 0.05:
        st.warning(
            f"g de {formatar_percentual_br(g_novo, 2)} acima de 5% nominal "
            "BRL: justifique com o crescimento de longo prazo da economia."
        )

    # Validacao em tempo real (2): margem acima da maxima historica + 5pp.
    maxima_historica = agregados.get("margem_ebitda_maxima")
    if maxima_historica is not None:
        margens_novas = [
            float(novas.get(f"margem_ebitda_ano{ano}", 0.0))
            for ano in range(1, HORIZONTE_PROJECAO + 1)
        ]
        excesso = max(margens_novas) - float(maxima_historica)
        if excesso > LIMITE_ALERTA_MARGEM_PP:
            st.warning(
                f"Margem EBITDA projetada excede a maxima historica "
                f"({formatar_percentual_br(float(maxima_historica))}) em "
                f"{excesso * 100:.1f}pp — acima do limite de 5pp. Justifique."
            )

    if st.button(
        "Salvar premissas e recalcular valuation",
        type="primary",
        disabled=bloqueado,
    ):
        _salvar_e_recalcular(ticker, novas)


def _premissas_financeira(
    ticker: str,
    premissas: dict[str, Any],
    conteudo: dict[str, Any] | None,
) -> None:
    """Editor de premissas da trilha FCFE/Ke (bancos)."""
    st.caption(
        "Trilha financeira: receitas de intermediacao, margem do resultado "
        "bruto e despesas operacionais projetam a DRE bancaria; o capital "
        "regulatorio retido define o FCFE."
    )
    novas: dict[str, Any] = dict(premissas)
    novas.update(_editor_vetores(premissas, VETORES_FINANCEIRA))

    coluna_esquerda, coluna_direita = st.columns(2)
    with coluna_esquerda:
        novas["indice_capital_alvo"] = st.slider(
            "Indice de capital alvo (Basileia)",
            0.08,
            0.20,
            float(premissas.get("indice_capital_alvo", 0.115)),
            step=0.005,
            format="%.3f",
        )
        novas["fator_rwa_ativos"] = st.slider(
            "Fator RWA / Ativos",
            0.3,
            1.0,
            float(premissas.get("fator_rwa_ativos", 0.75)),
            step=0.05,
        )
        novas["aliquota_ir_financeira"] = st.slider(
            "Aliquota IR/CSLL financeira",
            0.20,
            0.50,
            float(premissas.get("aliquota_ir_financeira", 0.45)),
            step=0.01,
        )
    with coluna_direita:
        novas["beta"] = st.slider(
            "Beta (alavancado, de mercado/peers)",
            0.2,
            3.0,
            float(premissas.get("beta", 1.0)),
            step=0.05,
        )
        novas["crescimento_perpetuidade_g"] = st.slider(
            "g — crescimento na perpetuidade (decimal)",
            0.0,
            0.25,
            float(premissas.get("crescimento_perpetuidade_g", 0.03)),
            step=0.0025,
            format="%.4f",
        )

    ke_atual = None
    if conteudo is not None and isinstance(conteudo.get("ke"), dict):
        ke_atual = conteudo["ke"].get("ke_brl")
    g_novo = float(novas["crescimento_perpetuidade_g"])
    bloqueado = False
    if ke_atual is not None and g_novo >= float(ke_atual):
        st.error(
            f"BLOQUEADO: g ({formatar_percentual_br(g_novo, 2)}) >= Ke "
            f"({formatar_percentual_br(float(ke_atual), 2)}). A perpetuidade "
            "explode — reduza o g antes de salvar."
        )
        bloqueado = True
    if novas["indice_capital_alvo"] < 0.105:
        st.warning("Indice de capital abaixo de Basileia (10,5%) — checklist F1.")

    if st.button(
        "Salvar premissas e recalcular valuation",
        type="primary",
        disabled=bloqueado,
    ):
        _salvar_e_recalcular(ticker, novas)


def secao_premissas(
    ticker: str,
    conteudo: dict[str, Any] | None,
    financeira: bool,
) -> None:
    """Editor de premissas por trilha, com validacao em tempo real."""
    caminho = caminho_premissas(ticker)
    if not caminho.exists():
        st.warning(
            "Sem premissas para este ticker — rode o pipeline pela sidebar "
            "(as premissas de partida sao geradas automaticamente)."
        )
        return
    premissas = carregar_json(caminho)
    _aviso_premissas_automaticas(ticker)
    if financeira:
        _premissas_financeira(ticker, premissas, conteudo)
    else:
        _premissas_nao_financeira(ticker, premissas, conteudo)


def _valuation_financeira(ticker: str, conteudo: dict[str, Any]) -> None:
    """Decomposicao do Ke, FCFE e checklist da trilha financeira."""
    painel_decisao(conteudo)
    st.subheader("Decomposicao do Ke (CAPM Brasil, beta alavancado)")
    ke = conteudo.get("ke", {})
    linhas_ke = (
        ("Rf USD (^TNX)", "rf_usd"),
        ("Beta alavancado (mercado/peers)", "beta_alavancado"),
        ("ERP EUA", "erp_eua"),
        ("CRP Brasil", "crp_brasil"),
        ("Ke USD", "ke_usd"),
        ("IPCA longo prazo", "ipca"),
        ("CPI EUA longo prazo", "cpi_eua"),
        ("Ke BRL", "ke_brl"),
    )
    tabela = []
    for rotulo, campo in linhas_ke:
        valor = ke.get(campo)
        texto = (
            formatar_percentual_br(float(valor), 2)
            if isinstance(valor, (int, float)) and campo != "beta_alavancado"
            else (f"{float(valor):.4f}x" if isinstance(valor, (int, float)) else "n/d")
        )
        tabela.append({"Componente": rotulo, "Valor": texto})
    st.dataframe(pd.DataFrame(tabela), hide_index=True, width="stretch")

    valor_terminal = conteudo.get("valor_terminal", {})
    colunas = st.columns(4)
    colunas[0].metric("Base do VT", str(valor_terminal.get("base_vt", "n/d")))
    colunas[1].metric(
        "VP(VT)",
        formatar_moeda_brl(float(valor_terminal.get("vp_vt", 0.0)), 0),
    )
    pct = valor_terminal.get("pct_ev_perpetuidade")
    colunas[2].metric(
        "% Equity na perpetuidade",
        formatar_percentual_br(float(pct)) if pct is not None else "n/d",
    )
    colunas[3].metric(
        "Capital regulatorio alvo",
        formatar_percentual_br(
            float(
                conteudo.get("capital_regulatorio", {})
                .get("ano1", {})
                .get("indice_capital_alvo", 0.0)
            ),
            1,
        ),
    )

    resultado_football = gerar_football_field(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_football["figura"], width="stretch")
    _tabela_checklist(conteudo)


def _tabela_checklist(conteudo: dict[str, Any]) -> None:
    """Tabela do checklist persistido com status final."""
    st.subheader("Checklist de consistencia")
    checklist = conteudo.get("checklist", {})
    itens = checklist.get("itens", [])
    if not itens:
        st.info("Checklist ainda nao executado para este ticker.")
        return
    quadro = pd.DataFrame(itens)[["id", "descricao", "status", "valor", "limite"]]
    st.dataframe(quadro, hide_index=True, width="stretch")
    if checklist.get("aprovado") is True:
        st.success("Checklist APROVADO (nenhum item em ERRO).")
    else:
        st.error("Checklist REPROVADO — verifique os itens em ERRO.")


def secao_valuation(
    ticker: str,
    conteudo: dict[str, Any],
    financeira: bool,
) -> None:
    """Decomposicao do custo de capital, VT, bridge e checklist."""
    if financeira:
        _valuation_financeira(ticker, conteudo)
        return

    painel_decisao(conteudo)
    st.subheader("Decomposicao do WACC")
    wacc = conteudo["wacc"]
    linhas_wacc = (
        ("Rf USD (^TNX)", "rf_usd", "%"),
        ("Beta desalavancado", "beta_desalavancado", "x"),
        ("D/E medio (anos 1-8)", "divida_sobre_equity", "x"),
        ("Beta re-alavancado (Hamada)", "beta_realavancado", "x"),
        ("ERP EUA", "erp_eua", "%"),
        ("CRP Brasil", "crp_brasil", "%"),
        ("Ke USD", "ke_usd", "%"),
        ("IPCA longo prazo", "ipca", "%"),
        ("CPI EUA longo prazo", "cpi_eua", "%"),
        ("Ke BRL", "ke_brl", "%"),
        ("Kd historico", "kd_historico", "%"),
        ("Aliquota IR", "aliquota_ir", "%"),
        ("Kd liquido", "kd_liquido", "%"),
        ("Peso Equity (E/V)", "peso_equity", "%"),
        ("Peso Divida (D/V)", "peso_divida", "%"),
        ("WACC", "wacc", "%"),
    )
    tabela_wacc = []
    for rotulo, campo, unidade in linhas_wacc:
        valor = wacc.get(campo)
        if valor is None:
            texto = "n/d"
        elif unidade == "%":
            texto = formatar_percentual_br(float(valor), 2)
        else:
            texto = f"{float(valor):.4f}x"
        tabela_wacc.append({"Componente": rotulo, "Valor": texto})
    st.dataframe(pd.DataFrame(tabela_wacc), hide_index=True, width="stretch")

    st.subheader("Valor terminal e ponte para o equity")
    valor_terminal = conteudo["valor_terminal"]
    colunas = st.columns(4)
    colunas[0].metric("Base do VT", str(valor_terminal.get("base_vt", "n/d")))
    colunas[1].metric(
        "VP(VT)",
        formatar_moeda_brl(float(valor_terminal.get("vp_vt", 0.0)), 0),
    )
    colunas[2].metric(
        "% EV na perpetuidade",
        formatar_percentual_br(float(valor_terminal.get("pct_ev_perpetuidade", 0.0))),
    )
    multiplo = valor_terminal.get("multiplo_saida_implicito")
    colunas[3].metric(
        "Multiplo de saida implicito",
        f"{float(multiplo):.2f}x" if multiplo is not None else "n/d",
    )

    resultado_waterfall = gerar_waterfall_ev(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_waterfall["figura"], width="stretch")

    resultado_football = gerar_football_field(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_football["figura"], width="stretch")
    _tabela_checklist(conteudo)


def secao_comparaveis(ticker: str, conteudo: dict[str, Any] | None) -> None:
    """Comparaveis reais (CCA) e triangulacao DCF vs multiplos."""
    comparaveis = carregar_comparaveis(ticker, RAIZ_PROJETO)
    if st.button("Atualizar comparaveis (coleta peers via yfinance)"):
        with st.spinner("Coletando multiplos dos peers..."):
            try:
                gerar_comparaveis(ticker, RAIZ_PROJETO)
                st.rerun()
            except RuntimeError as erro:
                st.error(f"Falha nos comparaveis: {erro}")
    if not comparaveis:
        st.info(
            "Comparaveis ainda nao gerados para este ticker — use o botao "
            "acima (exige rede)."
        )
        return

    triangulacao = comparaveis.get("triangulacao", {})
    faixa = triangulacao.get("faixa_multiplos")
    colunas = st.columns(3)
    target = triangulacao.get("target_dcf")
    colunas[0].metric(
        "DCF (base)",
        formatar_moeda_brl(float(target)) if target else "n/d",
    )
    colunas[1].metric(
        "Faixa por multiplos (Q1-Q3)",
        (
            # dois "$" na mesma string viram math inline no markdown do
            # st.metric — escapar para exibir "R$" literal nas duas pontas
            (
                f"{formatar_moeda_brl(float(faixa['minimo']))} - "
                f"{formatar_moeda_brl(float(faixa['maximo']))}"
            ).replace("$", "\\$")
            if faixa
            else "n/d"
        ),
    )
    preco = triangulacao.get("preco_atual")
    colunas[2].metric(
        "Preco atual",
        formatar_moeda_brl(float(preco)) if preco else "n/d",
    )
    veredito = str(triangulacao.get("veredito", ""))
    if "DENTRO" in veredito:
        st.success(f"Triangulacao: {veredito}")
    elif "ACIMA" in veredito or "ABAIXO" in veredito:
        st.warning(f"Triangulacao: {veredito}")
    else:
        st.info(f"Triangulacao: {veredito}")

    resultado_tabela = gerar_tabela_comparaveis(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_tabela["figura"], width="stretch")

    precos_implicitos = comparaveis.get("precos_implicitos", {})
    if precos_implicitos:
        quadro = pd.DataFrame(precos_implicitos).T
        quadro.index = [ROTULOS_MULTIPLOS.get(nome, nome) for nome in quadro.index]
        st.subheader("Preco implicito por multiplo (Q1 / mediana / Q3)")
        st.dataframe(quadro.style.format("R$ {:,.2f}"), width="stretch")

    avisos = comparaveis.get("avisos", [])
    if avisos or comparaveis.get("peers_excluidos"):
        with st.expander("Avisos e peers excluidos"):
            for aviso in avisos:
                st.write(f"- {aviso}")
            for excluido in comparaveis.get("peers_excluidos", []):
                st.write(f"- {excluido['peer']}: {excluido['motivo']}")


def _sensibilidade_viva(conteudo: dict[str, Any]) -> None:
    """Sliders vivos: recalculo instantaneo do Target sob choques."""
    st.subheader("Sensibilidade viva (derivada do caso base do motor)")
    colunas = st.columns(4)
    delta_wacc = colunas[0].slider("Δ WACC (pp)", -3.0, 3.0, 0.0, 0.25) / 100
    delta_g = colunas[1].slider("Δ g (pp)", -1.5, 1.5, 0.0, 0.25) / 100
    delta_crescimento = (
        colunas[2].slider("Δ crescimento (pp/ano)", -5.0, 5.0, 0.0, 0.5) / 100
    )
    delta_margem = colunas[3].slider("Δ margem (pp)", -5.0, 5.0, 0.0, 0.5) / 100

    cenario = recalcular_cenario(
        conteudo,
        delta_wacc=delta_wacc,
        delta_g=delta_g,
        delta_crescimento_pp=delta_crescimento,
        delta_margem_pp=delta_margem,
    )
    base = float(conteudo["ev_equity"]["target_price"])
    if cenario is None:
        st.error("Combinacao bloqueada: g >= WACC no cenario simulado.")
        return
    target = float(cenario["target_price"])
    colunas = st.columns(3)
    colunas[0].metric(
        "Target simulado",
        formatar_moeda_brl(target),
        delta=formatar_percentual_br(target / base - 1),
    )
    upside = cenario.get("upside")
    colunas[1].metric(
        "Upside simulado",
        formatar_percentual_br(float(upside)) if upside is not None else "n/d",
    )
    colunas[2].metric(
        "WACC | g simulados",
        f"{formatar_percentual_br(float(cenario['wacc']), 2)} | "
        f"{formatar_percentual_br(float(cenario['g']), 2)}",
    )


def secao_analise(
    ticker: str,
    conteudo: dict[str, Any],
    financeira: bool,
) -> None:
    """Tornado, sensibilidades vivas e heatmaps institucionais."""
    if financeira:
        cenarios = conteudo.get("cenarios", {})
        if cenarios:
            st.subheader("Cenarios do motor (pipeline completo por cenario)")
            quadro = pd.DataFrame(cenarios).T[
                ["target_price", "upside", "taxa_desconto", "g"]
            ]
            st.dataframe(
                quadro.style.format(
                    {
                        "target_price": "R$ {:,.2f}",
                        "upside": "{:.1%}",
                        "taxa_desconto": "{:.2%}",
                        "g": "{:.2%}",
                    }
                ),
                width="stretch",
            )
        st.info(
            "Sensibilidades FCFF (WACC x g, receita x margem) nao se aplicam "
            "a trilha financeira; as sensibilidades bancarias (Ke x g, "
            "capital x crescimento) chegam na Onda 5."
        )
        return

    resultado_tornado = gerar_tornado(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_tornado["figura"], width="stretch")

    _sensibilidade_viva(conteudo)

    resultado_roic = gerar_roic_roiic(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_roic["figura"], width="stretch")

    resultado_wacc_g = gerar_sensibilidade_wacc_g(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_wacc_g["figura"], width="stretch")

    resultado_receita = gerar_sensibilidade_receita_margem(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_receita["figura"], width="stretch")

    resultado_setor = gerar_sensibilidade_setor(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_setor["figura"], width="stretch")


def secao_comparar(ticker: str) -> None:
    """Comparacao lado a lado de 2-5 empresas + watchlist persistida."""
    analisadas = [
        analisada
        for analisada in listar_empresas_analisadas()
        if carregar_projecao_app(analisada) is not None
    ]
    if len(analisadas) < 2:
        st.info("Analise ao menos 2 empresas (sidebar) para compara-las aqui.")
        return

    padrao = [t for t in (ticker, *TICKERS_REFERENCIA, "VALE3") if t in analisadas]
    padrao = list(dict.fromkeys(padrao))[:4]
    escolhidas = st.multiselect(
        "Empresas (2 a 5)",
        options=analisadas,
        default=padrao if len(padrao) >= 2 else analisadas[:2],
        max_selections=5,
    )
    if len(escolhidas) < 2:
        st.warning("Escolha ao menos 2 empresas.")
        return

    linhas = montar_painel_comparacao(escolhidas, RAIZ_PROJETO)
    quadro = pd.DataFrame(linhas).set_index("ticker")
    formato = {
        "target_price": "R$ {:,.2f}",
        "preco_atual": "R$ {:,.2f}",
        "upside": "{:.1%}",
        "taxa_desconto": "{:.2%}",
        "g": "{:.2%}",
        "roic_ano1": "{:.1%}",
        "spread_roic_taxa": "{:.1%}",
        "ev_ebitda_mediana_peers": "{:,.1f}x",
        "p_l_mediana_peers": "{:,.1f}x",
        "p_vp_mediana_peers": "{:,.1f}x",
    }
    st.subheader("Painel comparativo (motor + comparaveis persistidos)")
    st.dataframe(
        quadro.style.format(formato, na_rep="n/d"),
        width="stretch",
    )

    resultado = gerar_comparacao_empresas(escolhidas, RAIZ_PROJETO)
    st.plotly_chart(resultado["figura"], width="stretch")

    st.subheader("Watchlist (data/watchlist.json)")
    watchlist = carregar_watchlist()
    colunas = st.columns(2)
    with colunas[0]:
        if st.button(f"Adicionar {ticker} a watchlist"):
            atualizar_watchlist(ticker)
            st.rerun()
    with colunas[1]:
        if ticker in watchlist.get("tickers", {}) and st.button(
            f"Remover {ticker} da watchlist"
        ):
            atualizar_watchlist(ticker, remover=True)
            st.rerun()
    if watchlist.get("tickers"):
        quadro_watch = pd.DataFrame(watchlist["tickers"]).T
        st.dataframe(
            quadro_watch.style.format(
                {"target_price": "R$ {:,.2f}", "upside": "{:.1%}"},
                na_rep="n/d",
            ),
            width="stretch",
        )
    else:
        st.caption("Watchlist vazia.")


@st.cache_data(show_spinner="Montando o preview das 7 abas...")
def preview_excel_cacheado(
    ticker: str,
    versao: tuple[float, float],
) -> dict[str, list[tuple[str, pd.DataFrame]]]:
    """Preview das 7 abas em cache; ``versao`` invalida apos novo pipeline."""
    return montar_preview_por_aba(ticker, RAIZ_PROJETO)


def _versao_dados(ticker: str) -> tuple[float, float]:
    """Mtimes de projecao e premissas — chave de invalidacao do preview."""
    arquivos = (caminho_projecao(ticker), caminho_premissas(ticker))
    return tuple(
        arquivo.stat().st_mtime if arquivo.exists() else 0.0 for arquivo in arquivos
    )


def secao_excel_preview(ticker: str, financeira: bool) -> None:
    """Renderiza as 7 abas do Excel dentro do app + download do .xlsx."""
    if financeira:
        st.info(
            "O exportador Excel de 7 abas cobre a trilha nao-financeira; o "
            "modelo bancario (FCFE/Ke) chega na Onda 5. Use as secoes "
            "Overview/Valuation para os resultados do banco."
        )
        return

    caminho_xlsx = caminho_excel(ticker, RAIZ_PROJETO)
    st.caption(
        "Preview fiel das 7 abas geradas pelo exportador. O download "
        "entrega o .xlsx real, com formulas nativas, graficos embutidos, "
        "formatacao condicional e a convencao de cores de banco "
        "(AZUL = input | PRETO = formula | VERDE = link entre abas)."
    )

    coluna_gerar, coluna_baixar, coluna_info = st.columns([1, 1, 2])
    with coluna_gerar:
        if st.button("Gerar/atualizar Excel", width="stretch"):
            with st.spinner("Exportando o Excel de 7 abas..."):
                exportar_excel(ticker, RAIZ_PROJETO)
            st.toast("Excel atualizado a partir do pipeline persistido.")
    if caminho_xlsx.exists():
        with coluna_baixar:
            st.download_button(
                label=f"Baixar {caminho_xlsx.name}",
                data=caminho_xlsx.read_bytes(),
                file_name=caminho_xlsx.name,
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".spreadsheetml.sheet"
                ),
                type="primary",
                width="stretch",
            )
        with coluna_info:
            gerado_em = datetime.fromtimestamp(caminho_xlsx.stat().st_mtime)
            tamanho_kb = caminho_xlsx.stat().st_size / 1024
            st.caption(f"Gerado em {gerado_em:%d/%m/%Y %H:%M} | {tamanho_kb:,.0f} KB")
    else:
        with coluna_info:
            st.info(
                "Excel ainda nao gerado para este ticker — use o botao "
                "'Gerar/atualizar Excel' ao lado."
            )

    preview = preview_excel_cacheado(ticker, _versao_dados(ticker))
    abas = st.tabs(list(NOMES_ABAS))
    for aba, nome in zip(abas, NOMES_ABAS):
        with aba:
            for subtitulo, quadro in preview[nome]:
                st.subheader(subtitulo)
                st.dataframe(quadro, hide_index=True, width="stretch")


def montar_sidebar() -> tuple[str, str]:
    """Sidebar: seletor universal de empresa, secoes e acoes do pipeline."""
    with st.sidebar:
        st.title("DCF Automatizado")
        st.caption("Valuation por DCF para QUALQUER acao da B3 — v2.0")

        analisadas = listar_empresas_analisadas()
        padrao = st.session_state.get(
            "ticker",
            "DIRR3" if "DIRR3" in analisadas else (analisadas[0] if analisadas else ""),
        )
        if analisadas:
            indice = analisadas.index(padrao) if padrao in analisadas else 0
            ticker = st.selectbox("Empresa analisada", analisadas, index=indice)
        else:
            ticker = padrao
        st.session_state["ticker"] = ticker

        st.caption("Empresas de referencia:")
        colunas_ref = st.columns(len(TICKERS_REFERENCIA))
        for coluna, referencia in zip(colunas_ref, TICKERS_REFERENCIA):
            if coluna.button(referencia, width="stretch"):
                st.session_state["ticker"] = referencia
                st.rerun()

        novo = st.text_input(
            "Analisar novo ticker (qualquer empresa da B3)",
            placeholder="Ex.: WEGE3, RADL3, PETR4, ITUB4",
        )
        if st.button("Analisar", type="primary", width="stretch"):
            candidato = novo.strip().upper().replace(".SA", "")
            if candidato:
                executar_pipeline_com_status(candidato, forcar=False)
            else:
                st.warning("Informe um ticker para analisar.")

        secao = st.radio("Secao", SECOES)
        st.divider()
        if st.button("Recalcular motor (premissas atuais)"):
            with st.spinner("Executando o motor de calculo..."):
                rodar_motor_valuation(ticker, RAIZ_PROJETO)
            _carregar_projecao_cacheada.clear()
            st.success("Motor recalculado.")
            st.rerun()
        if st.button("Recoletar tudo e reanalisar"):
            executar_pipeline_com_status(ticker, forcar=True)
        st.caption(
            "O motor Python e a fonte unica de verdade; este app apenas "
            "apresenta os resultados persistidos."
        )
    return ticker, secao


def main() -> None:
    """Monta a estacao de trabalho multi-empresa."""
    st.set_page_config(
        page_title="DCF Automatizado",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
    )
    aplicar_estilo_institucional()
    ticker, secao = montar_sidebar()

    if not ticker:
        st.info(
            "Nenhuma empresa analisada ainda. Informe um ticker na sidebar "
            "e clique em Analisar."
        )
        return

    conteudo = carregar_projecao_app(ticker)
    financeira = empresa_financeira(ticker, conteudo)

    st.header(f"{ticker} — {secao}")
    if conteudo is None and secao not in ("Premissas", "Historico", "Comparaveis"):
        meta = carregar_meta(ticker)
        score = meta.get("score_confiabilidade")
        st.warning(
            f"Sem valuation persistido para {ticker} "
            f"(score de dados: {score if score is not None else 'n/d'}/100). "
            "Use 'Recoletar tudo e reanalisar' na sidebar; se a empresa nao "
            "tiver dados suficientes na CVM, o relatorio de qualidade "
            "explica o motivo."
        )
        return

    if secao == "Overview":
        secao_overview(ticker, conteudo)
    elif secao == "Historico":
        secao_historico(ticker, financeira)
    elif secao == "Premissas":
        secao_premissas(ticker, conteudo, financeira)
    elif secao == "Valuation":
        secao_valuation(ticker, conteudo, financeira)
    elif secao == "Comparaveis":
        secao_comparaveis(ticker, conteudo)
    elif secao == "Analise":
        secao_analise(ticker, conteudo, financeira)
    elif secao == "Comparar":
        secao_comparar(ticker)
    else:
        secao_excel_preview(ticker, financeira)


if __name__ == "__main__":
    main()
