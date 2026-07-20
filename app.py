"""Front-end institucional do DCF Automatizado (Streamlit) — fluxo guiado.

Prompt 9.0.4: o app vira um FLUXO GUIADO de 4 etapas, sem perder capacidade:

    (1) Escolher empresa  (2) Premissas  (3) Resultados & ajustes  (4) Exportar

Etapa (2) expoe as 6 premissas de Lucas para nao-financeiras (crescimento,
margem bruta pre-D&A, SG&A, aliquota anual, WACC manual opcional e o grupo
Outros), com validacao em tempo real. Etapa (3) tem sub-abas — inclui a nova
aba **Modelo** (DRE/BP/DFC projetados + FCFF/FCFE com a linha de verificacao
do balanco) e **Retornos** (multiplos, TIR/MOIC do 9.0.3). Etapa (4) faz o
preview e o download do Excel.

Regra dura (Principio 3): o app NUNCA recalcula valuation — edita premissas e
dispara o motor Python (fonte unica de verdade).
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

from src.apresentacao.formatacao import (  # noqa: E402
    COR_TEXTO_SECUNDARIO,
    COR_VERDE_UPSIDE,
    COR_VERMELHO_DOWNSIDE,
    formatar_moeda_brl,
    formatar_percentual_br,
)
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
    carregar_metadados,
    empresa_usa_ret,
    salvar_json,
)

TICKERS_REFERENCIA = ("DIRR3", "MGLU3", "SMFT3")

# Etapas do fluxo guiado (Prompt 9.0.4). A navegacao vive na sidebar como
# radio unico — os testes AppTest tambem navegam por ele.
ETAPAS = (
    "① Empresa",
    "② Premissas",
    "③ Resultados",
    "④ Exportar",
)
# Sub-abas da etapa (3) Resultados (a aba Modelo e a Retornos sao novas).
SUBABAS_RESULTADOS = (
    "Overview",
    "Historico",
    "Valuation",
    "Modelo",
    "Retornos",
)
LIMITE_ALERTA_MARGEM_PP = 0.05
ANOS = [f"Ano {ano}" for ano in range(1, HORIZONTE_PROJECAO + 1)]

# Vetores anuais editaveis da trilha nao-financeira (as premissas 1-4 + capex).
VETORES_OPERACIONAIS = (
    ("crescimento_receita", "Crescimento da receita liquida", 0.05),
    ("margem_bruta", "Margem bruta (nivel EBITDA, pre-D&A)", 0.30),
    ("sgna_pct_receita", "SG&A % da receita liquida", 0.15),
    ("capex_receita", "CAPEX / Receita (negativo = saida)", -0.04),
)
VETORES_FINANCEIRA = (
    ("crescimento_receita", "Crescimento das receitas de intermediacao", 0.05),
    ("margem_resultado_bruto", "Margem do resultado bruto", 0.30),
    ("despesas_operacionais_receita", "Despesas operacionais / receitas", 0.40),
)


# ---------------------------------------------------------------------------
# Caminhos e carregamento (consumidor puro dos JSONs do motor)
# ---------------------------------------------------------------------------


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


def empresa_ret(ticker: str) -> bool:
    """Detecta construtora no RET (aliquota travada em 4% sobre a bruta)."""
    caminho = caminho_premissas(ticker)
    if not caminho.exists():
        return False
    try:
        premissas = carregar_json(caminho)
        metadados = carregar_metadados(ticker, RAIZ_PROJETO)
    except (RuntimeError, FileNotFoundError):
        return False
    return empresa_usa_ret(premissas, metadados)


def _carregar_metricas(ticker: str) -> dict[str, Any]:
    """Le as metricas historicas persistidas; vazio se nao existirem."""
    caminho = RAIZ_PROJETO / "data" / "processed" / f"{ticker}_metricas.json"
    if not caminho.exists():
        return {}
    return carregar_json(caminho)


def obter_metricas(ticker: str) -> dict[str, Any]:
    """Metricas historicas persistidas; calcula na primeira execucao."""
    metricas = _carregar_metricas(ticker)
    if not metricas.get("metricas_por_ano"):
        try:
            metricas = calcular_metricas_historicas(ticker, RAIZ_PROJETO)
        except RuntimeError:
            return metricas or {}
    return metricas


# ---------------------------------------------------------------------------
# Helpers de renderizacao (tabelas de anos, decisao)
# ---------------------------------------------------------------------------


def _quadro_anos(
    bloco: dict[str, Any],
    linhas: tuple[tuple[str, str], ...],
) -> pd.DataFrame:
    """DataFrame (rotulo x Ano1..Ano8) de valores float de um bloco anual.

    Blocos do motor sao {ano1: {...}, ...}; aqui viram tabela navegavel com
    os anos nas colunas. Valores nao numericos viram NaN (float) para o Arrow
    serializar sem erro de tipo misto.
    """
    dados: dict[str, list[float]] = {}
    for campo, rotulo in linhas:
        serie = []
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            valor = bloco.get(f"ano{ano}", {}).get(campo)
            serie.append(
                float(valor)
                if isinstance(valor, (int, float)) and not isinstance(valor, bool)
                else float("nan")
            )
        dados[rotulo] = serie
    return pd.DataFrame(dados, index=ANOS).T


def _exibir_quadro(quadro: pd.DataFrame, formato: str = "{:,.0f}") -> None:
    """Exibe um DataFrame numerico formatado (Arrow-safe: tudo float)."""
    st.dataframe(quadro.style.format(formato, na_rep="n/d"), width="stretch")


def painel_decisao(conteudo: dict[str, Any]) -> None:
    """Faixa de decisao: Target, Upside, Recomendacao, taxa e g do caso base."""
    ev_equity = conteudo["ev_equity"]
    financeira = str(conteudo.get("tipo")) == "financeira"
    target = float(ev_equity["target_price"])
    upside = float(ev_equity.get("upside") or 0.0)
    recomendacao = str(ev_equity.get("recomendacao", "n/d"))
    preco = float(ev_equity.get("preco_atual") or 0.0)

    if financeira:
        taxa = float(conteudo.get("ke", {}).get("ke_brl") or 0.0)
        rotulo_taxa = "Ke"
    else:
        taxa = float(conteudo.get("wacc", {}).get("wacc") or 0.0)
        rotulo_taxa = "WACC"
    g = float(conteudo.get("valor_terminal", {}).get("g") or 0.0)

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
            "defaults do subtipo). A tese e do analista: revise na etapa "
            "② Premissas e salve para assumir a autoria."
        )


def _resumo_valuation(conteudo: dict[str, Any]) -> None:
    """Tabela compacta com a espinha do valuation (EV, VT, perpetuidade)."""
    ev_equity = conteudo.get("ev_equity", {})
    linhas = [
        ("Soma VP(FCFF)", ev_equity.get("soma_vp_fcff")),
        ("VP(VT)", ev_equity.get("vp_vt")),
        ("Enterprise Value", ev_equity.get("ev")),
        ("Equity Value", ev_equity.get("equity_value")),
    ]
    tabela = []
    for rotulo, valor in linhas:
        texto = formatar_moeda_brl(float(valor), 0) if valor is not None else "n/d"
        tabela.append({"Componente": rotulo, "Valor": texto})
    st.subheader("Espinha do valuation (motor)")
    st.dataframe(pd.DataFrame(tabela), hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Etapa (1) — Escolher empresa
# ---------------------------------------------------------------------------


def executar_pipeline_com_status(ticker: str, forcar: bool) -> None:
    """Roda o pipeline universal exibindo o progresso por etapa."""
    with st.status(
        f"Analisando {ticker} — pipeline do nucleo...", expanded=True
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
    st.session_state["etapa"] = "③ Resultados"
    _carregar_projecao_cacheada.clear()
    st.rerun()


def etapa_empresa(ticker: str) -> None:
    """Landing: busca por ticker, referencias e status da empresa atual."""
    st.subheader("① Escolha a empresa")
    st.caption(
        "Busque qualquer acao da B3 pelo ticker. A coleta (CVM + mercado + "
        "macro) e o motor de valuation rodam automaticamente; depois edite as "
        "premissas na etapa ②."
    )

    coluna_busca, coluna_botao = st.columns([3, 1])
    with coluna_busca:
        novo = st.text_input(
            "Analisar novo ticker",
            placeholder="Ex.: WEGE3, RADL3, PETR4, ABEV3, TOTS3, ITUB4",
            label_visibility="collapsed",
        )
    with coluna_botao:
        if st.button("Analisar", type="primary", width="stretch"):
            candidato = novo.strip().upper().replace(".SA", "")
            if candidato:
                executar_pipeline_com_status(candidato, forcar=False)
            else:
                st.warning("Informe um ticker para analisar.")

    st.caption("Empresas de referencia (clique para carregar):")
    colunas_ref = st.columns(len(TICKERS_REFERENCIA))
    for coluna, referencia in zip(colunas_ref, TICKERS_REFERENCIA):
        if coluna.button(referencia, width="stretch"):
            st.session_state["ticker"] = referencia
            st.rerun()

    analisadas = listar_empresas_analisadas()
    if analisadas:
        st.divider()
        st.caption("Empresas ja analisadas:")
        indice = analisadas.index(ticker) if ticker in analisadas else 0
        escolhida = st.selectbox("Empresa analisada", analisadas, index=indice)
        if escolhida != ticker:
            st.session_state["ticker"] = escolhida
            st.rerun()

    conteudo = carregar_projecao_app(ticker)
    if conteudo is not None:
        st.divider()
        st.success(
            f"{ticker} pronto. Va para a etapa ② para editar premissas ou ③ "
            "para ver os resultados."
        )
        painel_decisao(conteudo)


# ---------------------------------------------------------------------------
# Etapa (2) — Premissas (as 6 de Lucas)
# ---------------------------------------------------------------------------


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


def _editor_vetores(
    premissas: dict[str, Any],
    vetores: tuple[tuple[str, str, float], ...],
    chave: str,
) -> dict[str, float]:
    """Tabela EDITAVEL dos vetores anuais (8 valores individuais por linha).

    st.data_editor nativo (D-005): testavel via AppTest. Editar uma celula
    NAO recalcula — o botao Salvar dispara o motor.
    """
    linhas = {}
    for campo_base, rotulo, padrao in vetores:
        linhas[rotulo] = [
            float(premissas.get(f"{campo_base}_ano{ano}", padrao) or padrao)
            for ano in range(1, HORIZONTE_PROJECAO + 1)
        ]
    quadro = pd.DataFrame(linhas, index=ANOS).T
    editado = st.data_editor(
        quadro,
        width="stretch",
        key=chave,
        column_config={
            coluna: st.column_config.NumberColumn(format="%.4f")
            for coluna in quadro.columns
        },
    )

    novos: dict[str, float] = {}
    for campo_base, rotulo, _ in vetores:
        for indice, ano in enumerate(range(1, HORIZONTE_PROJECAO + 1)):
            novos[f"{campo_base}_ano{ano}"] = float(editado.loc[rotulo].iloc[indice])
    return novos


def _premissas_nao_financeira(
    ticker: str,
    premissas: dict[str, Any],
    conteudo: dict[str, Any] | None,
) -> None:
    """Editor das 6 premissas de Lucas (trilha FCFF/WACC)."""
    metricas = obter_metricas(ticker)
    agregados = metricas.get("agregados", {})
    usa_ret = empresa_ret(ticker)
    novas: dict[str, Any] = dict(premissas)

    st.caption(
        "As 6 premissas de Lucas em grupos colapsaveis. Fonte VERDE = 'voce "
        "escolhe' (coerente com o Excel). Ancoras historicas: CAGR 3a "
        f"{formatar_percentual_br(float(agregados.get('cagr_receita_3a') or 0))}"
        " | margem bruta 3a "
        + formatar_percentual_br(float(agregados.get("margem_bruta_media_3a") or 0))
        + " | CAPEX/receita 3a "
        + formatar_percentual_br(float(agregados.get("capex_receita_media_3a") or 0))
    )

    # Grupo 1-3: crescimento, margem bruta, SG&A + capex (vetores ×8).
    with st.expander(
        "① Crescimento, ② Margem bruta e ③ SG&A (vetores anuais)", expanded=True
    ):
        st.caption(
            "A margem bruta e de NIVEL EBITDA (pre-D&A); a D&A e subtraida "
            "depois pelo schedule PP&E. A margem EBITDA vira DERIVADA (leitura)."
        )
        novas.update(_editor_vetores(premissas, VETORES_OPERACIONAIS, "vet_op"))
        # Margem EBITDA derivada = margem bruta - SG&A (nivel EBITDA), read-only.
        margem_ebitda_derivada = {
            rotulo: [
                novas[f"margem_bruta_ano{ano}"] - novas[f"sgna_pct_receita_ano{ano}"]
                for ano in range(1, HORIZONTE_PROJECAO + 1)
            ]
            for rotulo in ("Margem EBITDA derivada (bruta - SG&A)",)
        }
        st.caption("Margem EBITDA DERIVADA (so leitura — nao e mais input):")
        _exibir_quadro(pd.DataFrame(margem_ebitda_derivada, index=ANOS).T, "{:.1%}")

    # Grupo 4: aliquota de impostos (vetor ×8) ou RET travado.
    with st.expander("④ Aliquota de impostos (anual)", expanded=False):
        if usa_ret:
            st.info(
                "Construtora no RET: aliquota TRAVADA em 4% sobre a Receita "
                "BRUTA projetada (nao sobre o EBT). O motor aplica o RET "
                "automaticamente — o vetor de aliquota nao se aplica."
            )
        else:
            novas.update(
                _editor_vetores(
                    premissas,
                    (("aliquota_ir", "Aliquota IR/CSLL", 0.34),),
                    "vet_aliq",
                )
            )
            aliquotas = [
                novas[f"aliquota_ir_ano{ano}"]
                for ano in range(1, HORIZONTE_PROJECAO + 1)
            ]
            if any(not 0 <= a <= 0.45 for a in aliquotas):
                st.error(
                    "Aliquota fora de 0-45%: ajuste antes de salvar (limite "
                    "de sanidade do motor)."
                )

    # Grupo 5: WACC manual opcional.
    wacc_projetado = None
    if conteudo is not None and isinstance(conteudo.get("wacc"), dict):
        wacc_projetado = conteudo["wacc"].get("wacc")
    with st.expander("⑤ WACC (input direto opcional)", expanded=False):
        usar_manual = st.checkbox(
            "Informar o WACC manualmente (sobrepoe o build-up CAPM)",
            value=isinstance(premissas.get("wacc_manual"), (int, float)),
        )
        if usar_manual:
            novas["wacc_manual"] = st.number_input(
                "WACC manual (decimal, ex.: 0.135 = 13,5%)",
                min_value=0.01,
                max_value=1.0,
                value=float(premissas.get("wacc_manual") or wacc_projetado or 0.13),
                step=0.005,
                format="%.4f",
            )
            st.caption(
                "O motor usara este WACC no VT/EV; a decomposicao CAPM continua "
                "visivel na etapa ③ Valuation."
            )
        else:
            novas.pop("wacc_manual", None)
            if wacc_projetado is not None:
                st.caption(
                    "Usando o build-up CAPM. WACC resultante atual: "
                    f"{formatar_percentual_br(float(wacc_projetado), 2)}."
                )

    # Grupo 6: Outros (escalares).
    with st.expander("⑥ Outros (capital de giro, custo de capital, g)"):
        coluna_esquerda, coluna_direita = st.columns(2)
        with coluna_esquerda:
            novas["dso"] = st.slider(
                "DSO em dias", 0, 400, int(premissas.get("dso", 30))
            )
            novas["dio"] = st.slider(
                "DIO em dias", 0, 500, int(premissas.get("dio", 30))
            )
            novas["dpo"] = st.slider(
                "DPO em dias", 0, 400, int(premissas.get("dpo", 30))
            )
            novas["payout_dividendos"] = st.slider(
                "Payout de dividendos",
                0.0,
                1.0,
                float(premissas.get("payout_dividendos", 0.0) or 0.0),
                step=0.05,
            )
            novas["minoritarios_pct_ll"] = st.slider(
                "Participacao de minoritarios (% do LL)",
                0.0,
                0.5,
                float(premissas.get("minoritarios_pct_ll", 0.0) or 0.0),
                step=0.01,
            )
        with coluna_direita:
            novas["beta"] = st.slider(
                "Beta desalavancado (build-up CAPM)",
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
            novas["caixa_minimo_pct_receita"] = st.slider(
                "Caixa minimo (% da receita)",
                0.0,
                0.20,
                float(premissas.get("caixa_minimo_pct_receita", 0.02) or 0.02),
                step=0.005,
                format="%.3f",
            )
            novas["crescimento_perpetuidade_g"] = st.slider(
                "g — crescimento na perpetuidade (decimal)",
                0.0,
                0.25,
                float(premissas.get("crescimento_perpetuidade_g", 0.02)),
                step=0.0025,
                format="%.4f",
            )

    bloqueado = _validar_premissas_nf(novas, conteudo, agregados)

    coluna_salvar, coluna_restaurar = st.columns([2, 1])
    with coluna_salvar:
        if st.button(
            "Salvar premissas e recalcular valuation",
            type="primary",
            disabled=bloqueado,
            width="stretch",
        ):
            _salvar_e_recalcular(ticker, novas)
    with coluna_restaurar:
        if st.button("Restaurar automaticas", width="stretch"):
            st.session_state["confirmar_restauracao"] = True
    if st.session_state.get("confirmar_restauracao"):
        st.warning(
            "Isto DESCARTA suas premissas e regenera as automaticas de "
            "partida. Confirme para prosseguir."
        )
        if st.button("Confirmar restauracao das automaticas", type="secondary"):
            st.session_state["confirmar_restauracao"] = False
            executar_pipeline_com_status(ticker, forcar=False)


def _validar_premissas_nf(
    novas: dict[str, Any],
    conteudo: dict[str, Any] | None,
    agregados: dict[str, Any],
) -> bool:
    """Validacao em tempo real; devolve True quando o salvamento esta bloqueado.

    A regra g >= WACC usa o WACC MANUAL quando informado (senao o projetado),
    coerente com o que o motor de fato usara ao recalcular.
    """
    bloqueado = False
    g_novo = float(novas["crescimento_perpetuidade_g"])
    wacc_ref = novas.get("wacc_manual")
    if not isinstance(wacc_ref, (int, float)):
        wacc_ref = None
        if conteudo is not None and isinstance(conteudo.get("wacc"), dict):
            wacc_ref = conteudo["wacc"].get("wacc")

    if wacc_ref is not None and g_novo >= float(wacc_ref):
        st.error(
            f"BLOQUEADO: g ({formatar_percentual_br(g_novo, 2)}) >= WACC "
            f"({formatar_percentual_br(float(wacc_ref), 2)}). A perpetuidade "
            "de Gordon explode — reduza o g antes de salvar."
        )
        bloqueado = True
    if g_novo > 0.05:
        st.warning(
            f"g de {formatar_percentual_br(g_novo, 2)} acima de 5% nominal "
            "BRL: justifique com o crescimento de longo prazo da economia."
        )

    # Margem bruta coerente (0-100%).
    margens_brutas = [
        float(novas.get(f"margem_bruta_ano{ano}", 0.0))
        for ano in range(1, HORIZONTE_PROJECAO + 1)
    ]
    if any(not 0 <= m <= 1 for m in margens_brutas):
        st.error("BLOQUEADO: margem bruta fora de 0-100%. Ajuste antes de salvar.")
        bloqueado = True

    # Alerta: margem EBITDA derivada acima da maxima historica + 5pp.
    maxima_historica = agregados.get("margem_ebitda_maxima")
    if maxima_historica is not None:
        derivadas = [
            float(novas.get(f"margem_bruta_ano{ano}", 0.0))
            - float(novas.get(f"sgna_pct_receita_ano{ano}", 0.0))
            for ano in range(1, HORIZONTE_PROJECAO + 1)
        ]
        excesso = max(derivadas) - float(maxima_historica)
        if excesso > LIMITE_ALERTA_MARGEM_PP:
            st.warning(
                f"Margem EBITDA derivada excede a maxima historica "
                f"({formatar_percentual_br(float(maxima_historica))}) em "
                f"{excesso * 100:.1f}pp. Justifique."
            )
    return bloqueado


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
    novas.update(_editor_vetores(premissas, VETORES_FINANCEIRA, "vet_fin"))

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


def etapa_premissas(
    ticker: str,
    conteudo: dict[str, Any] | None,
    financeira: bool,
) -> None:
    """Editor de premissas por trilha, com validacao em tempo real."""
    st.subheader("② Premissas")
    caminho = caminho_premissas(ticker)
    if not caminho.exists():
        st.warning(
            "Sem premissas para este ticker — analise a empresa na etapa ① "
            "(as premissas de partida sao geradas automaticamente)."
        )
        return
    premissas = carregar_json(caminho)
    _aviso_premissas_automaticas(ticker)
    if financeira:
        _premissas_financeira(ticker, premissas, conteudo)
    else:
        _premissas_nao_financeira(ticker, premissas, conteudo)


# ---------------------------------------------------------------------------
# Etapa (3) — Resultados (sub-abas, inclui Modelo e Retornos)
# ---------------------------------------------------------------------------


def sub_overview(ticker: str, conteudo: dict[str, Any]) -> None:
    """Capa: KPIs de decisao, qualidade dos dados e espinha do valuation."""
    painel_decisao(conteudo)
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
            st.subheader("FCFE projetado (LL - ΔCapital regulatorio)")
            _exibir_quadro(
                _quadro_anos(
                    fcfe,
                    (
                        ("lucro_liquido", "Lucro liquido"),
                        ("delta_capital_regulatorio", "ΔCapital regulatorio"),
                        ("fcfe", "FCFE"),
                    ),
                )
            )
        return

    _resumo_valuation(conteudo)


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


def sub_historico(ticker: str, financeira: bool) -> None:
    """Metricas historicas por tipo de empresa (tabelas, sem graficos)."""
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


def _tabela_checklist(conteudo: dict[str, Any]) -> None:
    """Tabela do checklist persistido com status final (Arrow-safe)."""
    st.subheader("Checklist de consistencia")
    checklist = conteudo.get("checklist", {})
    itens = checklist.get("itens", [])
    if not itens:
        st.info("Checklist ainda nao executado para este ticker.")
        return
    quadro = pd.DataFrame(itens)[["id", "descricao", "status", "valor", "limite"]]
    # valor/limite misturam numeros e texto -> coage a str para o Arrow nao
    # falhar (bug de serializacao que sumia a tabela no navegador).
    quadro["valor"] = quadro["valor"].map(
        lambda v: f"{v:,.4g}" if isinstance(v, (int, float)) else str(v)
    )
    quadro["limite"] = quadro["limite"].astype(str)
    st.dataframe(quadro, hide_index=True, width="stretch")
    if checklist.get("aprovado") is True:
        st.success("Checklist APROVADO (nenhum item em ERRO).")
    else:
        st.error("Checklist REPROVADO — verifique os itens em ERRO.")


def _valuation_financeira(ticker: str, conteudo: dict[str, Any]) -> None:
    """Decomposicao do Ke, VT e checklist da trilha financeira."""
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
    _tabela_checklist(conteudo)


def sub_valuation(ticker: str, conteudo: dict[str, Any], financeira: bool) -> None:
    """Decomposicao do custo de capital, VT e checklist (tabelas)."""
    if financeira:
        _valuation_financeira(ticker, conteudo)
        return

    painel_decisao(conteudo)
    st.subheader("Decomposicao do WACC")
    wacc = conteudo["wacc"]
    origem = wacc.get("wacc_origem", "build_up_capm")
    if origem == "manual_do_analista":
        st.info(
            f"WACC MANUAL do analista: {formatar_percentual_br(float(wacc['wacc']), 2)}"
            " (o build-up CAPM abaixo fica como referencia; o motor usou o "
            "manual no VT/EV)."
        )
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
        ("WACC build-up CAPM", "wacc_capm_buildup", "%"),
        ("WACC usado", "wacc", "%"),
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

    _resumo_valuation(conteudo)
    _tabela_checklist(conteudo)


def sub_modelo(ticker: str, conteudo: dict[str, Any], financeira: bool) -> None:
    """DRE/BP/DFC projetados + FCFF/FCFE em tabelas navegaveis (9.0.4)."""
    if financeira:
        st.info(
            "A aba Modelo cobre a trilha nao-financeira (DRE/BP/DFC + "
            "FCFF/FCFE). Para bancos, use Overview/Valuation (FCFE/Ke)."
        )
        return

    st.subheader("DRE projetada (pre-D&A, padrao Direcional)")
    _exibir_quadro(
        _quadro_anos(
            conteudo.get("dre", {}),
            (
                ("receita_bruta", "Receita bruta"),
                ("deducoes", "(-) Deducoes"),
                ("receita_liquida", "Receita liquida"),
                ("cpv_cmv", "(-) CPV/CMV"),
                ("lucro_bruto", "Lucro bruto"),
                ("sgna", "(-) SG&A"),
                ("ebit_ex_depreciacao", "EBIT ex-D&A (EBITDA)"),
                ("depreciacao_amortizacao", "(-) D&A"),
                ("ebit", "EBIT"),
                ("resultado_financeiro", "Resultado financeiro"),
                ("ebt", "EBT"),
                ("ir_csll", "(-) IR/CSLL"),
                ("participacao_minoritarios", "(-) Minoritarios"),
                ("lucro_liquido", "Lucro liquido"),
            ),
        )
    )

    st.subheader("Balanco projetado (com linha de verificacao)")
    balanco = conteudo.get("balanco", {})
    _exibir_quadro(
        _quadro_anos(
            balanco,
            (
                ("ativo_total", "Ativo total"),
                ("passivo_patrimonio_liquido", "Passivo + PL"),
                ("patrimonio_liquido", "Patrimonio liquido"),
                ("divida_curto_prazo", "Divida CP"),
                ("divida_longo_prazo", "Divida LP"),
                ("verificacao_balanco", "CHECK |Ativo-(Pass+PL)|"),
            ),
        )
    )
    checks = [
        float(balanco.get(f"ano{ano}", {}).get("verificacao_balanco") or 0.0)
        for ano in range(1, HORIZONTE_PROJECAO + 1)
    ]
    if max(checks) < 1.0:
        st.success(
            f"Balanco FECHA nos 8 anos (maior residual {max(checks):.2e} < 1,0)."
        )
    else:
        st.error(f"Balanco NAO fecha: residual maximo {max(checks):,.2f}.")

    st.subheader("DFC indireto projetado")
    _exibir_quadro(
        _quadro_anos(
            conteudo.get("dfc", {}),
            (
                ("lucro_liquido", "Lucro liquido"),
                ("depreciacao_amortizacao", "(+) D&A"),
                ("delta_nwc", "(-) ΔNWC"),
                ("fco", "= FCO"),
                ("capex", "(-) CAPEX"),
                ("fci", "= FCI"),
                ("fcfin", "= FCFin"),
                ("variacao_caixa", "Variacao de caixa"),
                ("caixa_final", "Caixa final (= BP)"),
            ),
        )
    )

    coluna_fcff, coluna_fcfe = st.columns(2)
    with coluna_fcff:
        st.subheader("FCFF (NOPAT + D&A - ΔWK - CAPEX)")
        _exibir_quadro(
            _quadro_anos(
                conteudo.get("fcff", {}),
                (
                    ("nopat", "NOPAT"),
                    ("depreciacao_amortizacao", "(+) D&A"),
                    ("delta_nwc", "(-) ΔNWC"),
                    ("capex_saida_caixa", "(-) CAPEX"),
                    ("fcff", "= FCFF"),
                ),
            )
        )
    with coluna_fcfe:
        st.subheader("FCFE (checagem ao Ke)")
        _exibir_quadro(
            _quadro_anos(
                conteudo.get("fcfe", {}),
                (
                    ("fcff", "FCFF"),
                    ("juros_apos_ir", "(-) Juros apos IR"),
                    ("delta_divida", "(+) ΔDivida"),
                    ("fcfe", "= FCFE"),
                ),
            )
        )
    fcfe_val = conteudo.get("fcfe_valuation", {})
    if fcfe_val:
        equity_fcfe = fcfe_val.get("equity_value_fcfe")
        divergencia = fcfe_val.get("divergencia_vs_bridge")
        colunas = st.columns(3)
        colunas[0].metric(
            "Equity FCFE/Ke",
            (
                formatar_moeda_brl(float(equity_fcfe), 0)
                if equity_fcfe is not None
                else "n/d"
            ),
        )
        colunas[1].metric(
            "Equity bridge FCFF",
            formatar_moeda_brl(float(fcfe_val.get("equity_value_bridge", 0.0)), 0),
        )
        colunas[2].metric(
            "Divergencia FCFE vs bridge",
            (
                formatar_percentual_br(float(divergencia))
                if divergencia is not None
                else "n/d"
            ),
        )
        if fcfe_val.get("divergencia_acima_limiar"):
            st.caption(
                "AVISO: divergencia acima do limiar — estruturas de desconto "
                "diferentes (Ke unico vs WACC). O bridge FCFF e o metodo "
                "primario do target; o FCFE e checagem."
            )


def sub_retornos(ticker: str, conteudo: dict[str, Any]) -> None:
    """Painel de Retornos (9.0.3): multiplos implicitos, TIR/MOIC."""
    retornos = conteudo.get("retornos")
    if not isinstance(retornos, dict):
        st.info(
            "Painel de retornos ainda nao computado para este ticker. "
            "Recalcule o motor na etapa ②."
        )
        return

    tipo = str(retornos.get("tipo", "nao_financeira"))
    st.subheader("TIR e MOIC do acionista (grade de saida)")
    tir_moic = retornos.get("tir_moic", {})
    st.caption(
        f"Fluxo: -preco de entrada; +dividendos/acao; +preco de saida no ano "
        f"{tir_moic.get('horizonte_tir_anos', 5)} (target do bridge, truncado "
        "em zero). Grade bear/base/bull varia o preco de saida em +/- 20%."
    )
    cenarios = tir_moic.get("cenarios", {})
    tabela = []
    for nome in ("bear", "base", "bull"):
        cenario = cenarios.get(nome, {})
        tir = cenario.get("tir_acionista")
        moic = cenario.get("moic")
        tabela.append(
            {
                "Cenario": nome.capitalize(),
                "Preco de saida": formatar_moeda_brl(
                    float(cenario.get("preco_saida", 0.0))
                ),
                "TIR do acionista": (
                    formatar_percentual_br(float(tir)) if tir is not None else "n/d"
                ),
                "MOIC": f"{float(moic):.2f}x" if moic is not None else "n/d",
            }
        )
    st.dataframe(pd.DataFrame(tabela), hide_index=True, width="stretch")

    st.subheader("Multiplos implicitos por ano")
    multiplos = retornos.get("multiplos", {})
    if tipo == "financeira":
        linhas = (
            ("p_l_preco_atual", "P/L (preco atual)"),
            ("p_l_target", "P/L (target)"),
            ("p_vp_preco_atual", "P/VP (preco atual)"),
            ("p_vp_target", "P/VP (target)"),
        )
    else:
        linhas = (
            ("ev_ebitda_preco_atual", "EV/EBITDA (preco atual)"),
            ("ev_ebitda_target", "EV/EBITDA (target)"),
            ("ev_receita_preco_atual", "EV/Receita (preco atual)"),
            ("ev_receita_target", "EV/Receita (target)"),
            ("p_l_preco_atual", "P/L (preco atual)"),
            ("p_l_target", "P/L (target)"),
        )
    _exibir_quadro(_quadro_anos(multiplos, linhas), "{:,.2f}x")


def etapa_resultados(
    ticker: str,
    conteudo: dict[str, Any],
    financeira: bool,
) -> None:
    """Sub-abas de resultados (Overview, Historico, Valuation, Modelo, Retornos)."""
    st.subheader("③ Resultados e ajustes")
    st.caption(
        "Mudou uma premissa na etapa ②? Salve la e volte aqui — as tabelas "
        "re-renderizam com os numeros novos do motor."
    )
    abas = st.tabs(list(SUBABAS_RESULTADOS))
    with abas[0]:
        sub_overview(ticker, conteudo)
    with abas[1]:
        sub_historico(ticker, financeira)
    with abas[2]:
        sub_valuation(ticker, conteudo, financeira)
    with abas[3]:
        sub_modelo(ticker, conteudo, financeira)
    with abas[4]:
        sub_retornos(ticker, conteudo)


# ---------------------------------------------------------------------------
# Etapa (4) — Exportar
# ---------------------------------------------------------------------------


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


def etapa_exportar(ticker: str, financeira: bool) -> None:
    """Preview das 7 abas do Excel + download do .xlsx (Prompt 9.0.4 etapa ④)."""
    st.subheader("④ Exportar")
    if financeira:
        st.info(
            "O exportador Excel de 7 abas cobre a trilha nao-financeira; o "
            "modelo bancario (FCFE/Ke) chega depois (backlog v2.2). Use as "
            "abas Overview/Valuation da etapa ③ para os resultados do banco."
        )
        return

    caminho_xlsx = caminho_excel(ticker, RAIZ_PROJETO)
    st.caption(
        "Preview fiel das 7 abas geradas pelo exportador. O download entrega "
        "o .xlsx real, com formulas nativas, formatacao condicional e a "
        "convencao de cores de banco."
    )

    coluna_gerar, coluna_baixar, coluna_info = st.columns([1, 1, 2])
    with coluna_gerar:
        if st.button("Regerar Excel", width="stretch"):
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
                "'Regerar Excel' ao lado."
            )

    preview = preview_excel_cacheado(ticker, _versao_dados(ticker))
    abas = st.tabs(list(NOMES_ABAS))
    for aba, nome in zip(abas, NOMES_ABAS):
        with aba:
            for subtitulo, quadro in preview[nome]:
                st.subheader(subtitulo)
                st.dataframe(quadro, hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Layout e navegacao
# ---------------------------------------------------------------------------


def aplicar_estilo_institucional() -> None:
    """Injeta tipografia monoespacada nos numeros (padrao institucional)."""
    st.markdown(
        """
        <style>
        [data-testid="stMetricValue"], [data-testid="stMetricDelta"] {
            font-family: 'IBM Plex Mono', Consolas, monospace;
        }
        [data-testid="stSidebar"] { border-right: 1px solid #1E3350; }
        div[data-testid="stDataFrame"] * {
            font-variant-numeric: tabular-nums;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def montar_sidebar() -> tuple[str, str]:
    """Sidebar: empresa atual, navegacao pelas 4 etapas e acoes do motor."""
    with st.sidebar:
        st.title("DCF Automatizado")
        st.caption("Fluxo guiado: escolher → premissas → resultados → exportar")

        analisadas = listar_empresas_analisadas()
        padrao = st.session_state.get(
            "ticker",
            "DIRR3" if "DIRR3" in analisadas else (analisadas[0] if analisadas else ""),
        )
        if analisadas:
            indice = analisadas.index(padrao) if padrao in analisadas else 0
            ticker = st.selectbox("Empresa", analisadas, index=indice)
        else:
            ticker = padrao
        st.session_state["ticker"] = ticker

        indice_etapa = (
            ETAPAS.index(st.session_state.get("etapa", "① Empresa"))
            if st.session_state.get("etapa") in ETAPAS
            else 0
        )
        etapa = st.radio("Etapa", ETAPAS, index=indice_etapa)
        st.session_state["etapa"] = etapa

        st.divider()
        if st.button("Recalcular motor (premissas atuais)", width="stretch"):
            with st.spinner("Executando o motor de calculo..."):
                rodar_motor_valuation(ticker, RAIZ_PROJETO)
            _carregar_projecao_cacheada.clear()
            st.success("Motor recalculado.")
            st.rerun()
        if st.button("Recoletar tudo e reanalisar", width="stretch"):
            executar_pipeline_com_status(ticker, forcar=True)
        st.caption(
            "O motor Python e a fonte unica de verdade; este app apenas "
            "apresenta os resultados persistidos (nunca recalcula em JS)."
        )
    return ticker, etapa


def main() -> None:
    """Monta o fluxo guiado de 4 etapas (Prompt 9.0.4)."""
    st.set_page_config(
        page_title="DCF Automatizado",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
    )
    aplicar_estilo_institucional()
    ticker, etapa = montar_sidebar()

    st.header(f"{ticker or 'DCF Automatizado'} — {etapa}")

    if etapa == "① Empresa":
        if not ticker:
            st.info("Nenhuma empresa analisada. Informe um ticker abaixo.")
        etapa_empresa(ticker)
        return

    if not ticker:
        st.info("Escolha ou analise uma empresa na etapa ① Empresa.")
        return

    conteudo = carregar_projecao_app(ticker)
    financeira = empresa_financeira(ticker, conteudo)

    if etapa == "② Premissas":
        etapa_premissas(ticker, conteudo, financeira)
        return

    # Etapas ③ e ④ exigem valuation persistido.
    if conteudo is None:
        meta = carregar_meta(ticker)
        score = meta.get("score_confiabilidade")
        st.warning(
            f"Sem valuation persistido para {ticker} "
            f"(score de dados: {score if score is not None else 'n/d'}/100). "
            "Rode 'Recoletar tudo e reanalisar' na sidebar ou volte a etapa "
            "① Empresa."
        )
        return

    if etapa == "③ Resultados":
        etapa_resultados(ticker, conteudo, financeira)
    else:
        etapa_exportar(ticker, financeira)


if __name__ == "__main__":
    main()
