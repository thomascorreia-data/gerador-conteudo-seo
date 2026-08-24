import pytest
from fastapi.testclient import TestClient

from api.app import app

cliente = TestClient(app)


def test_health():
    resposta = cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_raiz_redireciona_para_interface():
    resposta = cliente.get("/", follow_redirects=False)
    assert resposta.status_code in (302, 307)
    assert resposta.headers["location"] == "/interface/gerador-json.html"


def test_normalizar_com_payload_valido():
    payload = {
        "Requisitor": "Teste",
        "Formato": "Descrição",
        "Temas": ["Salvador", "Recife"],
    }
    resposta = cliente.post("/normalizar", json={"payload": payload})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total_itens"] == 2
    assert corpo["resultado"][0]["tema"] == "Salvador"


def test_normalizar_sem_temas_retorna_400():
    payload = {"Requisitor": "Teste", "Formato": "Descrição"}
    resposta = cliente.post("/normalizar", json={"payload": payload})
    assert resposta.status_code == 400


def test_interface_e_servida_como_arquivo_estatico():
    resposta = cliente.get("/interface/gerador-json.html")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
    assert resposta.headers["cache-control"] == "no-store, must-revalidate"
