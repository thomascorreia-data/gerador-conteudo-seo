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


def test_sortear_respeita_excluir_topicos():
    todos_topicos = {item["topico"] for item in PERGUNTAS_PRONTAS}
    excluir = set(list(todos_topicos)[:3])
    escolhidas = sortear_da_lista("Eucatur", len(PERGUNTAS_PRONTAS), excluir_topicos=excluir)
    topicos_escolhidos = {item["topico"] for item in escolhidas}
    assert topicos_escolhidos.isdisjoint(excluir)


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


# --- deduplicação por ASSUNTO (não só texto literal) ------------------------
# Caso real que motivou isso: o banco sorteou uma pergunta sobre segurança da
# Buser, e a geração dinâmica devolveu OUTRA pergunta sobre segurança da
# empresa — texto diferente, mesmo assunto. Não pode ter as duas juntas.

def test_gerada_com_mesmo_assunto_do_banco_e_descartada_e_substituida(monkeypatch):
    # random.sample determinístico -> pega sempre os N primeiros da lista,
    # na ordem em que aparecem em PERGUNTAS_PRONTAS (o primeiro é "como_comprar").
    monkeypatch.setattr("base_empresas_faq.random.sample", lambda seq, k: list(seq)[:k])

    def _gerar_stub(entidade, fontes, quantidade_gerada, itens_ja_usados, palavras_chave=None):
        return [
            {"pergunta": "Pergunta colidindo", "resposta": "R", "topico": "como_comprar"},
            {"pergunta": "Pergunta nova", "resposta": "R", "topico": "assunto_totalmente_novo"},
        ]

    monkeypatch.setattr("base_empresas_faq._gerar_dinamicas", _gerar_stub)

    resultado = montar_faq_empresa("Eucatur", fontes={}, quantidade_perguntas=7)
    perguntas_texto = [p["pergunta"] for p in resultado["perguntas"]]

    assert "Pergunta colidindo" not in perguntas_texto
    assert "Pergunta nova" in perguntas_texto
    assert len(resultado["perguntas"]) == 7  # total continua batendo (repôs do banco)
    assert resultado["quantidade_gerada"] == 1  # só 1 das 2 geradas foi aceita


def test_duas_geradas_com_mesmo_assunto_entre_si_so_aceita_a_primeira(monkeypatch):
    monkeypatch.setattr("base_empresas_faq.random.sample", lambda seq, k: list(seq)[:k])

    def _gerar_stub(entidade, fontes, quantidade_gerada, itens_ja_usados, palavras_chave=None):
        return [
            {"pergunta": "Primeira sobre rotas", "resposta": "R", "topico": "rotas"},
            {"pergunta": "Segunda também sobre rotas", "resposta": "R", "topico": "rotas"},
        ]

    monkeypatch.setattr("base_empresas_faq._gerar_dinamicas", _gerar_stub)

    resultado = montar_faq_empresa("Eucatur", fontes={}, quantidade_perguntas=7)
    perguntas_texto = [p["pergunta"] for p in resultado["perguntas"]]

    assert "Primeira sobre rotas" in perguntas_texto
    assert "Segunda também sobre rotas" not in perguntas_texto
    assert len(resultado["perguntas"]) == 7


def test_quando_banco_esgota_e_gerada_colide_aceita_repetido_em_vez_de_devolver_menos(monkeypatch):
    # Pede o banco inteiro (10) + 2 geradas -> se a gerada colidir de
    # assunto e não sobrar tópico novo no banco pra repor, tem que aceitar
    # a colidida mesmo assim: nunca devolver menos perguntas que o pedido.
    monkeypatch.setattr("base_empresas_faq.random.sample", lambda seq, k: list(seq)[:k])

    topico_do_banco_inteiro = PERGUNTAS_PRONTAS[0]["topico"]

    def _gerar_stub(entidade, fontes, quantidade_gerada, itens_ja_usados, palavras_chave=None):
        return [
            {"pergunta": "Pergunta colidindo", "resposta": "R", "topico": topico_do_banco_inteiro},
            {"pergunta": "Pergunta nova", "resposta": "R", "topico": "assunto_totalmente_novo"},
        ]

    monkeypatch.setattr("base_empresas_faq._gerar_dinamicas", _gerar_stub)

    resultado = montar_faq_empresa("Eucatur", fontes={}, quantidade_perguntas=12)
    perguntas_texto = [p["pergunta"] for p in resultado["perguntas"]]

    assert len(resultado["perguntas"]) == 12  # nunca devolve menos que o pedido
    assert "Pergunta colidindo" in perguntas_texto  # aceita repetida como último recurso
    assert "Pergunta nova" in perguntas_texto


def test_gerada_sem_topico_nunca_e_descartada_por_assunto(monkeypatch):
    # Se o modelo não incluir "topico" (não seguiu a instrução), o item é
    # aceito do mesmo jeito — mais seguro que descartar um item bom só por
    # um campo faltando.
    def _gerar_stub(entidade, fontes, quantidade_gerada, itens_ja_usados, palavras_chave=None):
        return [{"pergunta": f"gerada {i}", "resposta": "r"} for i in range(quantidade_gerada)]

    monkeypatch.setattr("base_empresas_faq._gerar_dinamicas", _gerar_stub)

    resultado = montar_faq_empresa("Eucatur", fontes={}, quantidade_perguntas=7)
    assert resultado["quantidade_gerada"] == 2
