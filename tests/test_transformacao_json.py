import pytest
from transformacaoJson import normalizar_lote


def test_formato_com_objetos_herda_do_envelope():
    payload = {
        "Requisitor": "Lucas",
        "Autor": "Lucas",
        "Formato": "Post",
        "Média de Palavras Por Conteúdo": 300,
        "Tom": "Informativo",
        "Palavras-chave": "buser; onibus barato",
        "Temas": [
            {"tema": "Tema um"},
            {"tema": "Tema dois", "Tom": "Vendas"},
        ],
    }

    resultado, avisos = normalizar_lote(payload)

    assert avisos == []
    assert len(resultado) == 2
    assert resultado[0]["tema"] == "Tema um"
    assert resultado[0]["tom"] == "Informativo"
    assert resultado[0]["media_palavras"] == 300
    assert resultado[0]["palavras_chave"] == ["buser", "onibus barato"]
    # item 1 sobrescreve o tom do envelope
    assert resultado[1]["tom"] == "Vendas"


def test_formato_com_strings_usa_tudo_do_envelope():
    payload = {
        "Requisitor": "Lucas",
        "Formato": "Post",
        "Tom": "Informativo",
        "Temas": ["Primeiro tema", "Segundo tema"],
    }

    resultado, avisos = normalizar_lote(payload)

    assert avisos == []
    assert [item["tema"] for item in resultado] == ["Primeiro tema", "Segundo tema"]
    assert all(item["formato"] == "Post" for item in resultado)


def test_ids_sao_unicos_e_usam_slug_do_requisitor():
    payload = {"Requisitor": "João da Silva", "Formato": "Post", "Temas": ["A", "B"]}
    resultado, _ = normalizar_lote(payload)
    assert resultado[0]["id"] == "joao-da-silva-0"
    assert resultado[1]["id"] == "joao-da-silva-1"


def test_sem_requisitor_usa_slug_lote():
    payload = {"Formato": "Post", "Temas": ["A"]}
    resultado, _ = normalizar_lote(payload)
    assert resultado[0]["id"] == "lote-0"


def test_aviso_quando_quantidade_declarada_diverge():
    payload = {
        "Requisitor": "Lucas",
        "Formato": "Post",
        "Quantidade de Conteúdo": 5,
        "Temas": ["A", "B"],
    }
    resultado, avisos = normalizar_lote(payload)
    assert len(resultado) == 2
    assert len(avisos) == 1
    assert "5" in avisos[0] and "2" in avisos[0]


def test_sem_campo_temas_levanta_erro():
    with pytest.raises(ValueError):
        normalizar_lote({"Requisitor": "Lucas", "Formato": "Post"})


def test_lista_de_temas_vazia_levanta_erro():
    with pytest.raises(ValueError):
        normalizar_lote({"Formato": "Post", "Temas": []})


def test_item_objeto_sem_campo_tema_levanta_erro():
    with pytest.raises(ValueError):
        normalizar_lote({"Formato": "Post", "Temas": [{"Formato": "Artigo"}]})


def test_aceita_payload_como_string_json():
    payload_str = '{"Formato": "Post", "Temas": ["Um tema qualquer"]}'
    resultado, _ = normalizar_lote(payload_str)
    assert resultado[0]["tema"] == "Um tema qualquer"


def test_palavras_chave_sem_valor_fica_none():
    payload = {"Formato": "Post", "Temas": ["A"]}
    resultado, _ = normalizar_lote(payload)
    assert resultado[0]["palavras_chave"] is None
