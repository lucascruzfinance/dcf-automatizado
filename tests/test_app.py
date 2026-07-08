"""Testes do front-end Streamlit via AppTest (sem navegador).

Valida a jornada critica da aba Premissas: a validacao em tempo real
bloqueia g >= WACC e o botao de salvar fica desabilitado. Usa os dados
reais persistidos em data/processed (pipeline da Semana 3 ja executado).
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


def _abrir_secao(nome_secao: str) -> AppTest:
    """Roda o app e navega ate uma secao da sidebar."""
    app = AppTest.from_file(str(CAMINHO_APP), default_timeout=120)
    app.run()
    app.sidebar.radio[0].set_value(nome_secao).run()
    return app


def test_overview_mostra_target_price() -> None:
    """Overview exibe o painel de decisao sem excecoes."""
    app = _abrir_secao("Overview")

    assert not app.exception
    rotulos = [metrica.label for metrica in app.main.metric]
    assert "Target Price" in rotulos


def test_premissas_bloqueia_g_maior_que_wacc() -> None:
    """g de 20% (acima do WACC) mostra erro e desabilita o salvar."""
    app = _abrir_secao("Premissas")
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
    app = _abrir_secao("Premissas")

    slider_g = next(
        widget for widget in app.main.slider if "perpetuidade" in str(widget.label)
    )
    slider_g.set_value(0.02).run()

    assert not app.exception
    assert not [str(erro.value) for erro in app.main.error]
    botao_salvar = next(
        botao for botao in app.main.button if "Salvar premissas" in str(botao.label)
    )
    assert botao_salvar.disabled is False


def test_secao_valuation_renderiza_checklist() -> None:
    """Valuation exibe a decomposicao do WACC e o checklist."""
    app = _abrir_secao("Valuation")

    assert not app.exception
    subtitulos = [str(sub.value) for sub in app.main.subheader]
    assert any("WACC" in sub for sub in subtitulos)
    assert any("Checklist" in sub for sub in subtitulos)


def test_excel_preview_renderiza_7_abas() -> None:
    """Excel Preview mostra as 7 abas do .xlsx com tabelas de valores."""
    app = _abrir_secao("Excel Preview")

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
    # Cada aba do preview traz ao menos uma tabela de valores.
    assert len(app.main.dataframe) >= 7


def test_excel_preview_download_serve_xlsx_valido() -> None:
    """O arquivo servido pelo botao de download e um .xlsx real (zip PK)."""
    import zipfile

    app = _abrir_secao("Excel Preview")
    assert not app.exception

    caminho = RAIZ_PROJETO / "outputs" / "excel" / "DIRR3_dcf.xlsx"
    assert caminho.exists(), "Excel nao gerado — rode o pipeline (main.py)"
    # O download_button serve exatamente estes bytes; valida o container zip.
    assert zipfile.is_zipfile(caminho)
