"""Testes do classificador universal de tipo/subtipo (sem rede)."""

from __future__ import annotations

from pathlib import Path

from src.coleta.classificador_empresa import (
    NOME_LOG_SETORES,
    carregar_setores,
    classificar_empresa,
    detectar_tipo_empresa,
)

SETORES = carregar_setores()


def classificar(setor: str, **kwargs) -> dict:
    """Atalho com a config real do repositorio."""
    return classificar_empresa(setor, setores=SETORES, **kwargs)


def test_banco_classifica_como_financeira_fcfe_ke() -> None:
    """Bancos usam a trilha financeira: FCFE descontado a Ke."""
    resultado = classificar("Bancos")
    assert resultado["tipo"] == "financeira"
    assert resultado["subtipo"] == "banco"
    assert resultado["metodo_valuation"] == "FCFE"
    assert resultado["taxa_desconto"] == "Ke"


def test_construcao_civil_mantem_ret() -> None:
    """Construtoras seguem FCFF/WACC com tributacao RET na config."""
    resultado = classificar("Construção Civil, Mat. Constr. e Decoração")
    assert resultado["tipo"] == "nao_financeira"
    assert resultado["subtipo"] == "construcao_civil"
    assert resultado["metodo_valuation"] == "FCFF"
    assert resultado["config_subtipo"]["tributacao"]["usa_ret"] is True


def test_setores_cvm_conhecidos() -> None:
    """Setores CVM tipicos caem nos subtipos esperados."""
    esperados = {
        "Comércio (Atacado e Varejo)": "varejo",
        "Extração Mineral": "mineracao",
        "Petróleo e Gás": "oleo_gas",
        "Energia Elétrica": "utility_energia",
        "Saneamento, Serv. Água e Gás": "saneamento",
        "Telecomunicações": "telecom",
        "Papel e Celulose": "papel_celulose",
        "Seguradoras e Corretoras": "seguradora",
        "Serviços Transporte e Logística": "transporte_logistica",
    }
    for setor, subtipo in esperados.items():
        assert classificar(setor)["subtipo"] == subtipo, setor


def test_emp_adm_part_classifica_pelo_segmento() -> None:
    """'Emp. Adm. Part. - X' e operadora consolidada: vale o segmento X."""
    resultado = classificar("Emp. Adm. Part. - Máqs., Equip., Veíc. e Peças")
    assert resultado["subtipo"] == "industria"
    assert classificar("Emp. Adm. Part. - Extração Mineral")["subtipo"] == ("mineracao")


def test_emp_adm_part_sem_segmento_cai_em_holding() -> None:
    """Sem segmento reconhecivel, 'Emp. Adm. Part.' e holding de verdade."""
    resultado = classificar("Emp. Adm. Part. - Sem Setor Principal")
    assert resultado["subtipo"] == "holding"
    assert resultado["tipo"] == "nao_financeira"


def test_setor_desconhecido_cai_em_outros_e_loga(tmp_path: Path) -> None:
    """Setor sem regra usa o default seguro (outros, FCFF/WACC) e audita."""
    resultado = classificar(
        "Fabricação de Discos Voadores",
        ticker="OVNI3",
        raiz_projeto=tmp_path,
    )
    assert resultado["tipo"] == "nao_financeira"
    assert resultado["subtipo"] == "outros"
    assert resultado["metodo_valuation"] == "FCFF"
    assert resultado["taxa_desconto"] == "WACC"

    caminho_log = tmp_path / "logs" / NOME_LOG_SETORES
    assert caminho_log.exists()
    assert "OVNI3" in caminho_log.read_text(encoding="utf-8")


def test_compatibilidade_detectar_tipo_empresa() -> None:
    """A assinatura v1 continua devolvendo apenas o tipo."""
    assert detectar_tipo_empresa("Bancos") == "financeira"
    assert detectar_tipo_empresa("Comércio (Atacado e Varejo)") == "nao_financeira"
