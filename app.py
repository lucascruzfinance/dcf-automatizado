"""Front-end institucional do DCF Automatizado (Streamlit).

Sidebar com 6 secoes: Overview, Historico, Premissas, Valuation, Analise e
Excel Preview. O app e um CONSUMIDOR do motor Python: le os resultados
persistidos em ``data/processed/`` e, quando o analista salva premissas novas,
reexecuta o pipeline oficial (DRE -> WK -> PP&E -> Divida -> FCFF -> WACC ->
VT -> EV -> Checklist). Nenhum calculo de valuation e reimplementado aqui.
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
from src.projecao.projetor_dre import (  # noqa: E402
    HORIZONTE_PROJECAO,
    carregar_json,
    projetar_dre,
    salvar_json,
)
from src.projecao.schedule_divida import projetar_divida  # noqa: E402
from src.projecao.schedule_ppe import projetar_ppe  # noqa: E402
from src.projecao.schedule_wk import projetar_wk  # noqa: E402
from src.valuation.calculador_ev import calcular_ev  # noqa: E402
from src.valuation.calculador_fcff import calcular_fcff  # noqa: E402
from src.valuation.calculador_vt import calcular_valor_terminal  # noqa: E402
from src.valuation.calculador_wacc import calcular_wacc  # noqa: E402
from src.valuation.checklist import executar_checklist  # noqa: E402
from src.visualizacao.apoio_cenarios import (  # noqa: E402
    carregar_mercado,
    carregar_metricas,
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
from src.visualizacao.waterfall_ev import gerar_waterfall_ev  # noqa: E402
from src.visualizacao.tema_institucional import (  # noqa: E402
    COR_TEXTO_SECUNDARIO,
    COR_VERDE_UPSIDE,
    COR_VERMELHO_DOWNSIDE,
    formatar_moeda_brl,
    formatar_percentual_br,
)

TICKERS_V1 = ("DIRR3", "MGLU3")
SECOES = (
    "Overview",
    "Historico",
    "Premissas",
    "Valuation",
    "Analise",
    "Excel Preview",
)
LIMITE_ALERTA_MARGEM_PP = 0.05

CAMPOS_VETORES = (
    ("crescimento_receita", "Crescimento da receita", -0.5, 1.0),
    ("margem_ebitda", "Margem EBITDA", -0.5, 0.8),
    ("capex_receita", "CAPEX / Receita (negativo = saida)", -0.5, 0.0),
)


def caminho_premissas(ticker: str) -> Path:
    """Caminho do JSON de premissas do ticker."""
    return RAIZ_PROJETO / "data" / "premissas" / f"{ticker}_premissas.json"


def caminho_projecao(ticker: str) -> Path:
    """Caminho da projecao persistida pelo motor."""
    return RAIZ_PROJETO / "data" / "processed" / f"{ticker}_projecao.json"


def carregar_projecao_app(ticker: str) -> dict[str, Any] | None:
    """Carrega a projecao persistida; None quando o pipeline nao rodou."""
    caminho = caminho_projecao(ticker)
    if not caminho.exists():
        return None
    conteudo = carregar_json(caminho)
    if not isinstance(conteudo.get("ev_equity"), dict):
        return None
    return conteudo


def obter_metricas(ticker: str) -> dict[str, Any]:
    """Metricas historicas persistidas; calcula na primeira execucao."""
    metricas = carregar_metricas(ticker, RAIZ_PROJETO)
    if not metricas.get("metricas_por_ano") or "roiic_media_3a" not in metricas.get(
        "agregados", {}
    ):
        metricas = calcular_metricas_historicas(ticker, RAIZ_PROJETO)
    return metricas


def rodar_pipeline(ticker: str) -> None:
    """Reexecuta o pipeline oficial do motor na ordem obrigatoria.

    Injeta Rf e preco atual a partir dos dados de mercado ja coletados para
    nao depender de rede dentro do app.
    """
    mercado = carregar_mercado(ticker, RAIZ_PROJETO)
    rf_usd = mercado.get("rf_usd_tbond10y")
    preco_atual = mercado.get("preco_atual")

    projetar_dre(ticker, RAIZ_PROJETO)
    projetar_wk(ticker, RAIZ_PROJETO)
    projetar_ppe(ticker, RAIZ_PROJETO)
    projetar_divida(ticker, RAIZ_PROJETO)
    calcular_fcff(ticker, RAIZ_PROJETO)
    calcular_wacc(ticker, RAIZ_PROJETO, rf_usd=rf_usd)
    calcular_valor_terminal(ticker, RAIZ_PROJETO)
    calcular_ev(ticker, RAIZ_PROJETO, preco_atual=preco_atual)
    executar_checklist(ticker, RAIZ_PROJETO)


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
        </style>
        """,
        unsafe_allow_html=True,
    )


def painel_decisao(conteudo: dict[str, Any]) -> None:
    """Faixa de decisao: Target, Upside e Recomendacao em destaque."""
    ev_equity = conteudo["ev_equity"]
    target = float(ev_equity["target_price"])
    preco = float(ev_equity["preco_atual"])
    upside = float(ev_equity["upside"])
    recomendacao = str(ev_equity.get("recomendacao", "n/d"))
    wacc = float(conteudo["wacc"]["wacc"])
    g = float(conteudo["valor_terminal"]["g"])

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
    colunas[3].metric("WACC", formatar_percentual_br(wacc, 2))
    colunas[4].metric("g (perpetuidade)", formatar_percentual_br(g, 2))


def secao_overview(ticker: str, conteudo: dict[str, Any]) -> None:
    """Overview executivo com o dashboard final embutido."""
    painel_decisao(conteudo)
    checklist = conteudo.get("checklist", {})
    aprovado = checklist.get("aprovado") is True
    vt = conteudo.get("valor_terminal", {})
    pct = vt.get("pct_ev_perpetuidade")
    st.caption(
        f"Checklist: {'APROVADO' if aprovado else 'REPROVADO'} | "
        f"perpetuidade = "
        f"{formatar_percentual_br(float(pct)) if pct is not None else 'n/d'} do EV"
    )
    resultado = gerar_dashboard_final(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado["figura"], width="stretch")


def secao_historico(ticker: str) -> None:
    """Metricas historicas anuais e grade historico vs projetado."""
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
    formato: dict[str, Any] = {coluna: "{:.1%}" for coluna in colunas_pct}
    for coluna in ("dso", "dio", "dpo", "ccc"):
        formato[coluna] = "{:,.0f}"
    formato["divida_liquida_ebitda"] = "{:,.2f}x"
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


def _entrada_vetor_anual(
    premissas: dict[str, Any],
    campo_base: str,
    rotulo: str,
    minimo: float,
    maximo: float,
) -> dict[str, float]:
    """Renderiza os 8 campos individuais de um vetor anual de premissas."""
    valores: dict[str, float] = {}
    colunas = st.columns(4)
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        campo = f"{campo_base}_ano{ano}"
        padrao = float(premissas.get(campo, 0.0))
        with colunas[(ano - 1) % 4]:
            valores[campo] = st.number_input(
                f"Ano {ano}",
                min_value=minimo,
                max_value=maximo,
                value=padrao,
                step=0.005,
                format="%.3f",
                key=f"{campo_base}_{ano}",
                help=f"{rotulo} do ano {ano} (decimal: 0,10 = 10%)",
            )
    return valores


def _historico_do_vetor(campo_base: str, agregados: dict[str, Any]) -> str:
    """Texto de historico exibido ao lado de cada vetor de premissas."""
    if campo_base == "crescimento_receita":
        cagr3 = agregados.get("cagr_receita_3a")
        cagr5 = agregados.get("cagr_receita_5a")
        partes = []
        if cagr3 is not None:
            partes.append(f"CAGR 3a {formatar_percentual_br(float(cagr3))}")
        if cagr5 is not None:
            partes.append(f"CAGR 5a {formatar_percentual_br(float(cagr5))}")
        return " | ".join(partes) if partes else "sem historico"
    if campo_base == "margem_ebitda":
        media = agregados.get("margem_ebitda_media_3a")
        maxima = agregados.get("margem_ebitda_maxima")
        partes = []
        if media is not None:
            partes.append(f"media 3a {formatar_percentual_br(float(media))}")
        if maxima is not None:
            partes.append(f"maxima {formatar_percentual_br(float(maxima))}")
        return " | ".join(partes) if partes else "sem historico"
    media_capex = agregados.get("capex_receita_media_3a")
    if media_capex is not None:
        return f"media 3a {formatar_percentual_br(float(media_capex))} da receita"
    return "sem historico"


def secao_premissas(ticker: str, conteudo: dict[str, Any] | None) -> None:
    """Editor de premissas com historico ao lado e validacao em tempo real."""
    caminho = caminho_premissas(ticker)
    premissas = carregar_json(caminho)
    metricas = obter_metricas(ticker)
    agregados = metricas.get("agregados", {})

    st.caption(
        "Os 8 valores anuais sao individuais por regra do projeto — nunca "
        "uma taxa unica replicada. Historico da CVM exibido ao lado de "
        "cada bloco como ancora."
    )

    novas: dict[str, Any] = dict(premissas)
    for campo_base, rotulo, minimo, maximo in CAMPOS_VETORES:
        with st.expander(f"{rotulo} — 8 anos individuais", expanded=False):
            st.caption(f"Historico: {_historico_do_vetor(campo_base, agregados)}")
            novas.update(
                _entrada_vetor_anual(premissas, campo_base, rotulo, minimo, maximo)
            )

    st.subheader("Capital de giro e custo de capital")
    coluna_esquerda, coluna_direita = st.columns(2)
    with coluna_esquerda:
        dso_hist = agregados.get("dso_media_3a")
        dio_hist = agregados.get("dio_media_3a")
        dpo_hist = agregados.get("dpo_media_3a")
        novas["dso"] = st.slider(
            (
                f"DSO em dias (hist. 3a: {dso_hist:,.0f})"
                if dso_hist is not None
                else "DSO em dias"
            ),
            0,
            400,
            int(premissas.get("dso", 30)),
        )
        novas["dio"] = st.slider(
            (
                f"DIO em dias (hist. 3a: {dio_hist:,.0f})"
                if dio_hist is not None
                else "DIO em dias"
            ),
            0,
            500,
            int(premissas.get("dio", 30)),
        )
        novas["dpo"] = st.slider(
            (
                f"DPO em dias (hist. 3a: {dpo_hist:,.0f})"
                if dpo_hist is not None
                else "DPO em dias"
            ),
            0,
            400,
            int(premissas.get("dpo", 30)),
        )
    with coluna_direita:
        beta_hist = agregados.get("beta_desalavancado")
        novas["beta"] = st.slider(
            (
                f"Beta desalavancado (hist.: {beta_hist:.2f})"
                if beta_hist is not None
                else "Beta desalavancado"
            ),
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
        salvar_json(caminho, novas)
        with st.spinner("Rodando o pipeline do motor..."):
            rodar_pipeline(ticker)
        st.success("Premissas salvas e valuation recalculado.")
        st.rerun()


def secao_valuation(ticker: str, conteudo: dict[str, Any]) -> None:
    """Decomposicao do WACC, valor terminal, bridge e checklist."""
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
    st.dataframe(
        pd.DataFrame(tabela_wacc),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Valor terminal e ponte para o equity")
    vt = conteudo["valor_terminal"]
    colunas = st.columns(4)
    colunas[0].metric(
        "Base do VT",
        str(vt.get("base_vt", "n/d")),
    )
    colunas[1].metric(
        "VP(VT)",
        formatar_moeda_brl(float(vt.get("vp_vt", 0.0)), 0),
    )
    colunas[2].metric(
        "% EV na perpetuidade",
        formatar_percentual_br(float(vt.get("pct_ev_perpetuidade", 0.0))),
    )
    multiplo = vt.get("multiplo_saida_implicito")
    colunas[3].metric(
        "Multiplo de saida implicito",
        f"{float(multiplo):.2f}x" if multiplo is not None else "n/d",
    )

    resultado_waterfall = gerar_waterfall_ev(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_waterfall["figura"], width="stretch")

    resultado_football = gerar_football_field(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_football["figura"], width="stretch")

    st.subheader("Checklist de consistencia")
    checklist = conteudo.get("checklist", {})
    itens = checklist.get("itens", [])
    if itens:
        quadro = pd.DataFrame(itens)[["id", "descricao", "status", "valor", "limite"]]
        st.dataframe(quadro, hide_index=True, width="stretch")
        aprovado = checklist.get("aprovado") is True
        if aprovado:
            st.success("Checklist APROVADO (nenhum item em ERRO).")
        else:
            st.error("Checklist REPROVADO — verifique os itens em ERRO.")
    else:
        st.info("Checklist ainda nao executado para este ticker.")


def secao_analise(ticker: str) -> None:
    """Sensibilidades WACC x g, crescimento x margem e setorial."""
    resultado_roic = gerar_roic_roiic(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_roic["figura"], width="stretch")

    resultado_wacc_g = gerar_sensibilidade_wacc_g(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_wacc_g["figura"], width="stretch")

    resultado_receita = gerar_sensibilidade_receita_margem(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_receita["figura"], width="stretch")

    resultado_setor = gerar_sensibilidade_setor(ticker, RAIZ_PROJETO)
    st.plotly_chart(resultado_setor["figura"], width="stretch")


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


def secao_excel_preview(ticker: str) -> None:
    """Renderiza as 7 abas do Excel dentro do app + download do .xlsx.

    O preview consome ``montar_preview_por_aba`` do exportador — o MESMO
    ``montar_contexto`` que alimenta o .xlsx —, entao as tabelas exibidas
    aqui nunca divergem do arquivo baixado. O preview mostra VALORES ja
    formatados; as formulas nativas, os graficos embutidos e a convencao
    de cores vivem no .xlsx real.
    """
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


def main() -> None:
    """Monta o app institucional com sidebar de 6 secoes."""
    st.set_page_config(
        page_title="DCF Automatizado",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
    )
    aplicar_estilo_institucional()

    with st.sidebar:
        st.title("DCF Automatizado")
        st.caption("Valuation por DCF para acoes da B3 — v1.0")
        ticker = st.selectbox("Empresa", TICKERS_V1)
        secao = st.radio("Secao", SECOES)
        st.divider()
        if st.button("Rodar pipeline completo"):
            with st.spinner("Executando o motor de calculo..."):
                rodar_pipeline(ticker)
            st.success("Pipeline concluido.")
            st.rerun()
        st.caption(
            "O motor Python e a fonte unica de verdade; este app apenas "
            "apresenta os resultados persistidos."
        )

    conteudo = carregar_projecao_app(ticker)

    st.header(f"{ticker} — {secao}")
    if conteudo is None and secao not in ("Premissas", "Historico"):
        st.warning(
            "Pipeline ainda nao executado para este ticker. Use o botao "
            "'Rodar pipeline completo' na sidebar."
        )
        return

    if secao == "Overview":
        secao_overview(ticker, conteudo)
    elif secao == "Historico":
        secao_historico(ticker)
    elif secao == "Premissas":
        secao_premissas(ticker, conteudo)
    elif secao == "Valuation":
        secao_valuation(ticker, conteudo)
    elif secao == "Analise":
        secao_analise(ticker)
    else:
        secao_excel_preview(ticker)


if __name__ == "__main__":
    main()
