"""
Testes de formatos/gerando.py — especificamente o item de FAQ ganhando
"company_slug" e "faqs" no formato que a API de produção espera (ver
enviando/enviando--buser.py), pronto pra exportar da interface sem
transformação a mais. Nada aqui chama a OpenAI de verdade (gerar_faq_via_grafo
é sempre stubado).
"""

from gerando import gerar_conteudo, _entidade_do_link, _slug_do_link, _faqs_para_producao


# --- rótulo de domínio: nome de exibição x slug -----------------------------

def test_entidade_do_link_prettifica_pro_nome_de_exibicao():
    assert _entidade_do_link("https://eucatur.buser.com.br/") == "Eucatur"
    assert _entidade_do_link("https://www.expresso-jk.buser.com.br") == "Expresso Jk"


def test_slug_do_link_mantem_minusculo_e_hifen():
    assert _slug_do_link("https://eucatur.buser.com.br/") == "eucatur"
    assert _slug_do_link("https://www.expresso-jk.buser.com.br") == "expresso-jk"


def test_slug_do_link_sem_link_devolve_vazio():
    assert _slug_do_link("") == ""
    assert _slug_do_link(None) == ""


# --- conversão pergunta/resposta -> question/answer -------------------------

def test_faqs_para_producao_troca_chaves_pt_por_en():
    perguntas = [
        {"pergunta": "Posso levar bagagem extra?", "resposta": "Sim, até 2 volumes por passageiro."},
        {"pergunta": "Tem Wi-Fi no ônibus?", "resposta": "Sim, em todas as rotas."},
    ]
    assert _faqs_para_producao(perguntas) == [
        {"question": "Posso levar bagagem extra?", "answer": "Sim, até 2 volumes por passageiro."},
        {"question": "Tem Wi-Fi no ônibus?", "answer": "Sim, em todas as rotas."},
    ]


def test_faqs_para_producao_lista_vazia():
    assert _faqs_para_producao([]) == []


# --- gerar_conteudo: item de FAQ ganha company_slug + faqs -------------------

def _item_faq(**extra):
    base = {
        "id": "thomas-0",
        "formato": "FAQ",
        "tema": "https://expressojk.buser.com.br",
        "tom": "geral",
        "quantidade_perguntas": 2,
        "palavras_chave": None,
    }
    base.update(extra)
    return base


def test_item_faq_ganha_company_slug_e_faqs_no_formato_producao(monkeypatch):
    def _grafo_stub(link, entidade, foco, quantidade_perguntas, palavras_chave):
        return {
            "perguntas_humanizadas": [
                {"pergunta": "Posso remarcar?", "resposta": "Sim, até 3h antes."},
                {"pergunta": "Tem Wi-Fi?", "resposta": "Sim, em todas as rotas."},
            ],
            "erro": None,
            "sem_fontes": False,
        }

    monkeypatch.setattr("gerando.gerar_faq_via_grafo", _grafo_stub)

    resultados = gerar_conteudo([_item_faq()])
    item = resultados[0]

    assert item["company_slug"] == "expressojk"
    assert item["faqs"] == [
        {"question": "Posso remarcar?", "answer": "Sim, até 3h antes."},
        {"question": "Tem Wi-Fi?", "answer": "Sim, em todas as rotas."},
    ]
    # conteudo_gerado continua existindo, pra tela/CSV — faqs não substitui,
    # só complementa com o formato estruturado.
    assert "conteudo_gerado" in item
    assert "erro" not in item


def test_item_faq_sem_perguntas_nao_ganha_company_slug_nem_faqs(monkeypatch):
    def _grafo_stub(link, entidade, foco, quantidade_perguntas, palavras_chave):
        return {"perguntas_humanizadas": [], "erro": None, "sem_fontes": False}

    monkeypatch.setattr("gerando.gerar_faq_via_grafo", _grafo_stub)

    resultados = gerar_conteudo([_item_faq()])
    item = resultados[0]

    assert "company_slug" not in item
    assert "faqs" not in item
    assert item["erro"]


def test_item_descricao_nao_ganha_company_slug_nem_faqs(monkeypatch):
    def _grafo_stub(tema, tom, media_palavras, palavras_chave):
        return {"categoria": "empresa", "texto_humanizado": "texto qualquer", "erro": None, "sem_fontes": False}

    monkeypatch.setattr("gerando.gerar_descricao_via_grafo", _grafo_stub)

    resultados = gerar_conteudo([{
        "id": "thomas-0",
        "formato": "Descrição",
        "tema": "Expresso JK",
        "tom": "informativo",
        "media_palavras": 100,
        "palavras_chave": None,
    }])
    item = resultados[0]

    assert "company_slug" not in item
    assert "faqs" not in item
