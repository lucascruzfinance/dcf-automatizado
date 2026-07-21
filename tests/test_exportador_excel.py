"""Testes do exportador Excel 'Modelo' (Prompt 9.0.5).

Usa os dados reais persistidos de DIRR3 (pipeline ja executado). Valida o
contrato: 8 abas na ordem com nomes exatos (Modelo/FCFF/FCFE separadas),
legenda de cores na Capa, colunas historicas = CVM, linha Check booleana
avaliada como "Ok" nos 8 anos, recalculo integral (mini-avaliador reproduz
todos os valores do motor), MODELO VIVO (premissa editada propaga ate os
Targets FCFF e FCFE) e a convencao de cores de Lucas (historico azul /
premissa verde / formula preto).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.exportacao.exportador_excel import (
    COR_FORMULA,
    COR_HISTORICO,
    COR_PREMISSA,
    NOMES_ABAS,
    _construir_workbook,
    exportar_excel,
    montar_preview_por_aba,
)
from src.metricas.metricas_historicas import montar_series_anuais
from tests.apoio_avaliador_excel import Avaliador

RAIZ_PROJETO = Path(__file__).resolve().parents[1]

PROJECAO_DISPONIVEL = (
    RAIZ_PROJETO / "data" / "processed" / "DIRR3_projecao.json"
).exists()

pytestmark = pytest.mark.skipif(
    not PROJECAO_DISPONIVEL,
    reason="Pipeline nao executado (data/processed ausente).",
)


@pytest.fixture(scope="module")
def workbook_dirr3():
    """Workbook + abas construidas (uma vez por modulo) para DIRR3."""
    return _construir_workbook("DIRR3", RAIZ_PROJETO)


def test_oito_abas_na_ordem_com_nomes_exatos(workbook_dirr3) -> None:
    """8 abas na ordem fixa; Modelo, FCFF e FCFE sao abas SEPARADAS."""
    wb, _ = workbook_dirr3
    assert wb.sheetnames == list(NOMES_ABAS)
    assert "Modelo" in wb.sheetnames
    assert "FCFF" in wb.sheetnames
    assert "FCFE" in wb.sheetnames


def test_capa_tem_legenda_de_cores(workbook_dirr3) -> None:
    """A Capa traz a legenda: historico AZUL, premissa VERDE, formula PRETO."""
    wb, abas = workbook_dirr3
    capa = abas["Capa"]
    ws = wb["Capa"]
    azul = ws.cell(row=capa.L("legenda_historico"), column=2)
    verde = ws.cell(row=capa.L("legenda_premissa"), column=2)
    preto = ws.cell(row=capa.L("legenda_formula"), column=2)
    assert azul.value == "AZUL" and azul.font.color.rgb == COR_HISTORICO
    assert verde.value == "VERDE" and verde.font.color.rgb == COR_PREMISSA
    assert preto.value == "PRETO" and preto.font.color.rgb == COR_FORMULA


def test_cores_por_tipo_de_celula(workbook_dirr3) -> None:
    """Historico azul; premissa verde; formula preta (convencao de Lucas)."""
    wb, abas = workbook_dirr3
    modelo = abas["Modelo"]
    ws = wb["Modelo"]
    nh = len(montar_series_anuais("DIRR3", RAIZ_PROJETO).get("receita_liquida", {}))
    receita = modelo.L("receita_liquida")
    # Historico (coluna B) azul; projecao (primeira coluna projetada) preta.
    assert ws.cell(row=receita, column=2).font.color.rgb == COR_HISTORICO
    assert ws.cell(row=receita, column=2 + nh).font.color.rgb == COR_FORMULA
    # Premissa na aba Premissas em verde.
    premissas = abas["Premissas"]
    celula = wb["Premissas"].cell(row=premissas.L("margem_bruta"), column=2)
    assert celula.font.color.rgb == COR_PREMISSA


def test_colunas_historicas_do_modelo_batem_com_a_cvm(workbook_dirr3) -> None:
    """Toda coluna historica da receita liquida = serie padronizada da CVM."""
    wb, abas = workbook_dirr3
    modelo = abas["Modelo"]
    ws = wb["Modelo"]
    series = montar_series_anuais("DIRR3", RAIZ_PROJETO)
    anos = sorted(series["receita_liquida"])
    linha = modelo.L("receita_liquida")
    for indice, ano in enumerate(anos):
        celula = ws.cell(row=linha, column=2 + indice)
        assert float(celula.value) == pytest.approx(series["receita_liquida"][ano])


def test_linha_check_booleana_ok_nos_8_anos(workbook_dirr3) -> None:
    """Check = IF(ROUND(ativo)=ROUND(passivo+PL),"Ok",dif) avalia Ok x8."""
    wb, abas = workbook_dirr3
    modelo = abas["Modelo"]
    ws = wb["Modelo"]
    nh = len(montar_series_anuais("DIRR3", RAIZ_PROJETO).get("receita_liquida", {}))
    linha = modelo.L("bp_check")
    avaliador = Avaliador(wb)
    for t in range(1, 9):
        celula = ws.cell(row=linha, column=2 + nh + t - 1)
        assert str(celula.value).startswith("=IF(ROUND(")
        assert avaliador.valor_celula("Modelo", celula.coordinate) == "Ok"


def test_recalculo_integral_reproduz_o_motor(workbook_dirr3) -> None:
    """Recalcular TODAS as formulas nao muda nenhum valor exibido."""
    wb, abas = workbook_dirr3
    avaliador = Avaliador(wb)
    formulas, divergentes = 0, []
    for nome, aba in abas.items():
        ws = wb[nome]
        for (linha, coluna), esperado in aba.valores.items():
            celula = ws.cell(row=linha, column=coluna)
            if not (isinstance(celula.value, str) and celula.value.startswith("=")):
                continue
            formulas += 1
            obtido = avaliador.valor_celula(nome, celula.coordinate)
            if isinstance(esperado, (int, float)) and isinstance(obtido, (int, float)):
                escala = max(abs(esperado), 1.0)
                if abs(obtido - esperado) > max(1e-6 * escala, 1e-4):
                    divergentes.append(f"{nome}!{celula.coordinate}")
            elif isinstance(esperado, str) and str(obtido) != esperado:
                divergentes.append(f"{nome}!{celula.coordinate}")
    assert formulas > 400
    assert not divergentes, divergentes[:10]


def test_modelo_vivo_premissa_propaga_ate_os_dois_targets(workbook_dirr3) -> None:
    """Margem bruta ano 3 +2pp muda o Target da aba FCFF E o da aba FCFE."""
    wb, abas = workbook_dirr3
    fcff, fcfe = abas["FCFF"], abas["FCFE"]
    premissas = abas["Premissas"]
    coord_fcff = f"B{fcff.L('target')}"
    coord_fcfe = f"B{fcfe.L('target')}"

    base = Avaliador(wb)
    target_fcff = base.valor_celula("FCFF", coord_fcff)
    target_fcfe = base.valor_celula("FCFE", coord_fcfe)

    coord_mb = f"D{premissas.L('margem_bruta')}"  # coluna D = ano 3
    original = float(wb["Premissas"][coord_mb].value)
    vivo = Avaliador(wb, overrides={("Premissas", coord_mb): original + 0.02})
    novo_fcff = vivo.valor_celula("FCFF", coord_fcff)
    novo_fcfe = vivo.valor_celula("FCFE", coord_fcfe)

    assert abs(novo_fcff - target_fcff) > 1e-6
    assert abs(novo_fcfe - target_fcfe) > 1e-6


def test_targets_batem_com_o_motor(workbook_dirr3) -> None:
    """Target FCFF = ev_equity.target_price; Target FCFE = fcfe_valuation."""
    import json

    wb, abas = workbook_dirr3
    projecao = json.loads(
        (RAIZ_PROJETO / "data" / "processed" / "DIRR3_projecao.json").read_text(
            encoding="utf-8"
        )
    )
    avaliador = Avaliador(wb)
    target_fcff = avaliador.valor_celula("FCFF", f"B{abas['FCFF'].L('target')}")
    assert target_fcff == pytest.approx(projecao["ev_equity"]["target_price"], rel=1e-6)
    target_fcfe = avaliador.valor_celula("FCFE", f"B{abas['FCFE'].L('target')}")
    esperado = projecao.get("fcfe_valuation", {}).get("target_price_fcfe")
    if esperado is not None:
        assert target_fcfe == pytest.approx(esperado, rel=1e-6)


def test_bloco_leasing_condicional(workbook_dirr3) -> None:
    """DIRR3 (leasing imaterial) NAO tem o bloco Arrendamento no Modelo."""
    _, abas = workbook_dirr3
    assert "sec_leasing" not in abas["Modelo"].linhas
    # MGLU3 (leasing relevante) TEM o bloco.
    if (RAIZ_PROJETO / "data" / "processed" / "MGLU3_projecao.json").exists():
        _, abas_mglu = _construir_workbook("MGLU3", RAIZ_PROJETO)
        assert "sec_leasing" in abas_mglu["Modelo"].linhas


def test_sem_erros_de_formula_literais(workbook_dirr3) -> None:
    """Nenhuma celula com #REF!/#DIV/0!/#VALUE!/#NAME?."""
    wb, _ = workbook_dirr3
    for nome in wb.sheetnames:
        for row in wb[nome].iter_rows():
            for celula in row:
                if isinstance(celula.value, str):
                    assert not any(
                        erro in celula.value
                        for erro in ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?")
                    ), f"{nome}!{celula.coordinate}"


def test_exportar_excel_salva_xlsx_valido() -> None:
    """exportar_excel grava um .xlsx real (zip PK) no caminho padrao."""
    import zipfile

    caminho = exportar_excel("DIRR3", RAIZ_PROJETO)
    assert caminho.exists()
    assert zipfile.is_zipfile(caminho)


def test_preview_cobre_as_8_abas() -> None:
    """montar_preview_por_aba devolve as 8 abas novas para o app."""
    preview = montar_preview_por_aba("DIRR3", RAIZ_PROJETO)
    assert list(preview.keys()) == list(NOMES_ABAS)
    for secoes in preview.values():
        assert secoes and secoes[0][1] is not None


def test_financeira_recebe_erro_claro() -> None:
    """Bancos: erro claro (Excel cobre so nao-financeiras)."""
    if not (RAIZ_PROJETO / "data" / "raw" / "cvm" / "ITUB4_meta.json").exists():
        pytest.skip("ITUB4 nao coletado")
    with pytest.raises(RuntimeError, match="financeira"):
        exportar_excel("ITUB4", RAIZ_PROJETO)
