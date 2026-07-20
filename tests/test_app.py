"""Testes do front-end Streamlit via AppTest (sem navegador) — fluxo 9.0.4.

Valida a jornada guiada de 4 etapas: escolher empresa, editar premissas (com
validacao em tempo real), ver resultados (sub-abas Overview/.../Modelo/
Retornos) e exportar. Usa os dados reais persistidos em data/processed
(pipeline da Semana 3 ja executado).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
CAMINHO_APP = RAIZ_PROJETO / "app.py"

PROJECAO_DISPONIVEL = (
    RAIZ_PROJETO / "data" / "processed" / "DIRR3_projecao.json"
).exists()

pytestmark = pytest.mark.skipif(
    not PROJECAO_DISPONIVEL,
    reason="Pipeline da Semana 3 nao executado (data/processed ausente).",
)


def _abrir_etapa(etapa: str, ticker: str = "DIRR3") -> AppTest:
    """Roda o app e navega ate uma etapa do fluxo guiado."""
    app = AppTest.from_file(str(CAMINHO_APP), default_timeout=120)
    app.run()
    app.session_state["ticker"] = ticker
    app.session_state["etapa"] = etapa
    app.run()
    return app


def test_etapa_empresa_landing_sem_excecao() -> None:
    """Etapa ① Empresa carrega o landing de busca sem excecao."""
    app = _abrir_etapa("① Empresa")
    assert not app.exception
    subtitulos = [str(sub.value) for sub in app.main.subheader]
    assert any("Escolha a empresa" in sub for sub in subtitulos)


def test_etapa_resultados_overview_mostra_target() -> None:
    """Etapa ③ Resultados: sub-aba Overview exibe o Target Price."""
    app = _abrir_etapa("③ Resultados")
    assert not app.exception
    rotulos = [metrica.label for metrica in app.main.metric]
    assert "Target Price" in rotulos


def test_etapa_resultados_tem_sub_abas_modelo_e_retornos() -> None:
    """As 5 sub-abas de resultados incluem Modelo e Retornos (novas)."""
    app = _abrir_etapa("③ Resultados")
    assert not app.exception
    rotulos_abas = [str(aba.label) for aba in app.main.tabs]
    assert "Modelo" in rotulos_abas
    assert "Retornos" in rotulos_abas
    assert rotulos_abas == ["Overview", "Historico", "Valuation", "Modelo", "Retornos"]


def test_premissas_bloqueia_g_maior_que_wacc() -> None:
    """g de 20% (acima do WACC) mostra erro e desabilita o salvar."""
    app = _abrir_etapa("② Premissas")
    assert not app.exception

    slider_g = next(
        widget for widget in app.main.slider if "perpetuidade" in str(widget.label)
    )
    slider_g.set_value(0.20).run()

    assert not app.exception
    erros = [str(erro.value) for erro in app.main.error]
    assert any("BLOQUEADO" in erro for erro in erros)
    botao_salvar = next(
        botao for botao in app.main.button if "Salvar premissas" in str(botao.label)
    )
    assert botao_salvar.disabled is True


def test_premissas_com_g_valido_nao_bloqueia() -> None:
    """g baixo nao gera erro e mantem o botao habilitado."""
    app = _abrir_etapa("② Premissas")

    slider_g = next(
        widget for widget in app.main.slider if "perpetuidade" in str(widget.label)
    )
    slider_g.set_value(0.02).run()

    assert not app.exception
    erros_bloqueio = [
        str(erro.value) for erro in app.main.error if "BLOQUEADO" in str(erro.value)
    ]
    assert not erros_bloqueio
    botao_salvar = next(
        botao for botao in app.main.button if "Salvar premissas" in str(botao.label)
    )
    assert botao_salvar.disabled is False


def test_premissas_expoe_margem_bruta_pre_dea() -> None:
    """O editor das 6 premissas trata margem bruta como pre-D&A e deriva EBITDA."""
    app = _abrir_etapa("② Premissas")
    assert not app.exception
    textos = [str(c.value) for c in app.main.caption]
    # A margem bruta e o conceito central (pre-D&A); a EBITDA vira derivada.
    assert any("margem bruta" in t.lower() for t in textos)
    assert any("DERIVADA" in t for t in textos)


def test_premissas_wacc_manual_opcional() -> None:
    """O grupo WACC expoe o checkbox de input manual (Prompt 9.0.4)."""
    app = _abrir_etapa("② Premissas")
    assert not app.exception
    rotulos_checkbox = [str(cb.label) for cb in app.main.checkbox]
    assert any("WACC manualmente" in rotulo for rotulo in rotulos_checkbox)


def test_etapa_exportar_renderiza_7_abas() -> None:
    """Etapa ④ Exportar mostra as 7 abas do .xlsx com tabelas."""
    app = _abrir_etapa("④ Exportar")
    assert not app.exception
    rotulos_abas = [str(aba.label) for aba in app.main.tabs]
    assert rotulos_abas == [
        "Capa",
        "Premissas",
        "Modelo Integrado",
        "Schedules",
        "Valuation",
        "Sensibilidades",
        "Output",
    ]
    assert len(app.main.dataframe) >= 7


def test_etapa_resultados_valuation_renderiza_checklist() -> None:
    """Sub-aba Valuation exibe a decomposicao do WACC e o checklist."""
    app = _abrir_etapa("③ Resultados")
    assert not app.exception
    subtitulos = [str(sub.value) for sub in app.main.subheader]
    assert any("WACC" in sub for sub in subtitulos)
    assert any("Checklist" in sub for sub in subtitulos)


def test_excel_download_serve_xlsx_valido() -> None:
    """O arquivo servido pelo botao de download e um .xlsx real (zip PK)."""
    import zipfile

    app = _abrir_etapa("④ Exportar")
    assert not app.exception

    caminho = RAIZ_PROJETO / "outputs" / "excel" / "DIRR3_dcf.xlsx"
    assert caminho.exists(), "Excel nao gerado — rode o pipeline (main.py)"
    assert zipfile.is_zipfile(caminho)
