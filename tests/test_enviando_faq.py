"""
Testes de enviando/enviando_faq_empresas/enviando-faq.py — só carregar_itens()
(lógica pura, sem chamar a API de produção). Carregado via importlib (nome
de arquivo com hífen não é um identificador Python válido).
"""

import importlib.util
import json
import os

_CAMINHO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "enviando", "enviando_faq_empresas", "enviando-faq.py",
)
_spec = importlib.util.spec_from_file_location("enviando_faq", _CAMINHO)
enviando_faq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enviando_faq)

carregar_itens = enviando_faq.carregar_itens
arquivar = enviando_faq.arquivar


def _escrever_json(tmp_path, dados):
    caminho = tmp_path / "descricoes-geradas.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return str(caminho)


def test_carrega_item_com_company_slug_e_faqs(tmp_path):
    caminho = _escrever_json(tmp_path, [
        {
            "tema": "https://3-estrelas.buser.com.br/",
            "company_slug": "3-estrelas",
            "faqs": [{"question": "Posso levar bagagem extra?", "answer": "Sim, até 2 volumes."}],
        },
    ])

    itens = carregar_itens(caminho)

    assert len(itens) == 1
    assert itens[0]["company_slug"] == "3-estrelas"
    assert itens[0]["faqs"] == [{"question": "Posso levar bagagem extra?", "answer": "Sim, até 2 volumes."}]
    assert itens[0]["nome"] == "https://3-estrelas.buser.com.br/"


def test_carrega_varias_empresas_do_mesmo_arquivo(tmp_path):
    caminho = _escrever_json(tmp_path, [
        {"tema": "a", "company_slug": "empresa-a", "faqs": [{"question": "P1", "answer": "R1"}]},
        {"tema": "b", "company_slug": "empresa-b", "faqs": [{"question": "P2", "answer": "R2"}]},
    ])

    itens = carregar_itens(caminho)

    assert [i["company_slug"] for i in itens] == ["empresa-a", "empresa-b"]


def test_pula_item_sem_company_slug_ou_sem_faqs(tmp_path):
    caminho = _escrever_json(tmp_path, [
        {"tema": "Descrição qualquer", "formato": "Descrição", "conteudo_gerado": "texto"},
        {"tema": "FAQ que deu erro", "formato": "FAQ", "erro": "não gerou nada"},
        {"tema": "ok", "company_slug": "empresa-ok", "faqs": [{"question": "P", "answer": "R"}]},
    ])

    itens = carregar_itens(caminho)

    assert len(itens) == 1
    assert itens[0]["company_slug"] == "empresa-ok"


def test_arquivo_sem_itens_validos_devolve_lista_vazia(tmp_path):
    caminho = _escrever_json(tmp_path, [
        {"tema": "Descrição qualquer", "conteudo_gerado": "texto"},
    ])

    assert carregar_itens(caminho) == []


def test_arquivar_move_arquivo_pra_pasta_jsons_enviados(tmp_path, monkeypatch):
    # Redireciona a pasta de destino pra não mexer na real do projeto.
    pasta_destino = tmp_path / "jsons_enviados"
    monkeypatch.setattr(enviando_faq, "PASTA_JSONS_ENVIADOS", str(pasta_destino))

    origem = tmp_path / "descricoes-geradas.json"
    origem.write_text("[]", encoding="utf-8")

    arquivar(str(origem))

    assert not origem.exists()
    assert (pasta_destino / "descricoes-geradas.json").exists()
