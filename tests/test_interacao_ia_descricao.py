"""
Testes de interacao_ia_descricao.py — só a lógica de escolha de prompt
(_resolver_humanizador), sem chamar a OpenAI de verdade.
"""

import pytest
from interacao_ia_descricao import PROMPTS_POR_CATEGORIA, _resolver_humanizador


@pytest.fixture(autouse=True)
def _restaura_prompts_apos_teste():
    """Alguns testes aqui sujam PROMPTS_POR_CATEGORIA (é o dict carregado
    uma vez só, no import do módulo) pra simular categoria com humanizador
    próprio — restaura o estado original depois de cada teste, senão um
    teste vaza pro outro."""
    original = {
        categoria: dict(dados) if isinstance(dados, dict) else dados
        for categoria, dados in PROMPTS_POR_CATEGORIA.items()
    }
    yield
    for categoria, dados in original.items():
        PROMPTS_POR_CATEGORIA[categoria] = dados


def test_categoria_sem_humanizador_proprio_usa_o_geral():
    # "cidade" (e as demais, exceto "empresa") continuam sem humanizador
    # próprio preenchido — "empresa" tem o dela real agora, testada à parte
    # em test_empresa_tem_humanizador_proprio_com_regra_de_negrito.
    geral = PROMPTS_POR_CATEGORIA["humanizador"]
    assert _resolver_humanizador("cidade") is geral
    assert _resolver_humanizador("ponto_turistico") is geral
    assert _resolver_humanizador("terminal_rodoviaria") is geral


def test_empresa_tem_humanizador_proprio_com_regra_de_negrito():
    geral = PROMPTS_POR_CATEGORIA["humanizador"]
    resultado = _resolver_humanizador("empresa")
    assert resultado is not geral
    assert "negrito" in resultado["template"].lower()
    assert "**expressão**" in resultado["template"]


def test_categoria_com_humanizador_proprio_usa_o_dela():
    PROMPTS_POR_CATEGORIA["empresa"]["humanizador"] = {
        "descricao": "teste",
        "template": "TEMPLATE ESPECIFICO DE EMPRESA",
    }
    resultado = _resolver_humanizador("empresa")
    assert resultado["template"] == "TEMPLATE ESPECIFICO DE EMPRESA"


def test_humanizador_proprio_de_uma_categoria_nao_afeta_as_outras():
    PROMPTS_POR_CATEGORIA["empresa"]["humanizador"] = {
        "descricao": "teste",
        "template": "TEMPLATE ESPECIFICO DE EMPRESA",
    }
    geral = PROMPTS_POR_CATEGORIA["humanizador"]
    assert _resolver_humanizador("cidade") is geral


def test_categoria_none_ou_desconhecida_usa_o_geral():
    geral = PROMPTS_POR_CATEGORIA["humanizador"]
    assert _resolver_humanizador(None) is geral
    assert _resolver_humanizador("categoria-que-nao-existe") is geral


def test_humanizador_proprio_vazio_nao_conta_como_preenchido():
    # "humanizador": {} (o padrão hoje em cada categoria) não tem "template"
    # — não pode ser confundido com um humanizador de verdade.
    PROMPTS_POR_CATEGORIA["empresa"]["humanizador"] = {}
    geral = PROMPTS_POR_CATEGORIA["humanizador"]
    assert _resolver_humanizador("empresa") is geral
