"""
Testes de formatos/faq/base_empresas.py — só a lógica de proporção/sorteio,
sem chamar a OpenAI de verdade (a geração dinâmica é stubada com monkeypatch).
"""

from base_empresas_faq import calcular_divisao, sortear_da_lista, montar_faq_empresa, PERGUNTAS_PRONTAS


# --- proporção (1 gerada a cada 6 pedidas) ----------------------------------

def test_proporcao_bate_com_os_exemplos_combinados():
    # Exatamente os exemplos dados: 5 -> 1; 6 -> 1 (continua); 7 -> 2 (sobe).
    assert calcular_divisao(5) == (1, 4)
    assert calcular_divisao(6) == (1, 5)
    assert calcular_divisao(7) == (2, 5)


def test_proporcao_sobe_a_cada_6():
    assert calcular_divisao(12) == (2, 10)
    assert calcular_divisao(13) == (3, 10)
    assert calcular_divisao(18) == (3, 15)
    assert calcular_divisao(19) == (4, 15)


def test_proporcao_com_1_pergunta():
    assert calcular_divisao(1) == (1, 0)


def test_proporcao_com_zero_ou_negativo_nao_quebra():
    assert calcular_divisao(0) == (0, 0)
    assert calcular_divisao(-3) == (0, 0)


def test_soma_das_duas_partes_sempre_bate_com_o_pedido():
    for n in range(1, 30):
        gerada, lista = calcular_divisao(n)
        assert gerada + lista == n


# --- sorteio do banco --------------------------------------------------------

def test_sortear_substitui_entidade_no_texto():
    escolhidas = sortear_da_lista("Eucatur", 3)
    assert len(escolhidas) == 3
    for item in escolhidas:
        assert "{entidade}" not in item["pergunta"]
        assert "{entidade}" not in item["resposta"]


def test_sortear_nao_repete_pergunta_no_mesmo_sorteio():
    escolhidas = sortear_da_lista("Eucatur", len(PERGUNTAS_PRONTAS))
    perguntas = [item["pergunta"] for item in escolhidas]
    assert len(perguntas) == len(set(perguntas))


def test_sortear_zero_devolve_lista_vazia():
    assert sortear_da_lista("Eucatur", 0) == []


def test_sortear_mais_que_o_banco_devolve_so_o_banco_inteiro():
    escolhidas = sortear_da_lista("Eucatur", len(PERGUNTAS_PRONTAS) + 50)
    assert len(escolhidas) == len(PERGUNTAS_PRONTAS)


# --- montar_faq_empresa (geração stubada, sem chamar a API) -----------------

def test_total_final_bate_com_o_pedido_mesmo_pedindo_mais_que_o_banco(monkeypatch):
    # 25 perguntas > 10 do banco -> o excedente tem que virar geração extra,
    # nunca devolver menos que o pedido.
    def _gerar_stub(entidade, fontes, quantidade_gerada, perguntas_ja_usadas, palavras_chave=None):
        return [{"pergunta": f"gerada {i}", "resposta": "resposta"} for i in range(quantidade_gerada)]

    monkeypatch.setattr("base_empresas_faq._gerar_dinamicas", _gerar_stub)

    resultado = montar_faq_empresa("Eucatur", fontes={}, quantidade_perguntas=25)

    assert len(resultado["perguntas"]) == 25
    assert resultado["quantidade_do_banco"] == len(PERGUNTAS_PRONTAS)
    assert resultado["quantidade_gerada"] == 25 - len(PERGUNTAS_PRONTAS)


def test_total_final_bate_com_pedido_dentro_do_banco(monkeypatch):
    def _gerar_stub(entidade, fontes, quantidade_gerada, perguntas_ja_usadas, palavras_chave=None):
        return [{"pergunta": f"gerada {i}", "resposta": "resposta"} for i in range(quantidade_gerada)]

    monkeypatch.setattr("base_empresas_faq._gerar_dinamicas", _gerar_stub)

    resultado = montar_faq_empresa("Eucatur", fontes={}, quantidade_perguntas=7)

    assert len(resultado["perguntas"]) == 7
    assert resultado["quantidade_gerada"] == 2
    assert resultado["quantidade_do_banco"] == 5
