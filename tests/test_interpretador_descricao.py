"""
Testes de interpretador_descricao.py — foco em
classificar_abrangencia_feriado(), que usa o conhecimento geral do modelo
pra identificar se um feriado é nacional/estadual/municipal.
"""

import pytest

from interpretador_descricao import classificar_abrangencia_feriado, obter_mes_dia_fixo_feriado


class _FakeModelo:
    """Substitui o ChatOpenAI inteiro (não dá pra sobrescrever só o método
    ".invoke" de uma instância pydantic — ChatOpenAI bloqueia atribuir
    atributo que não é um field declarado)."""

    def __init__(self, resposta):
        self._resposta = resposta
        self.chamadas = []

    def invoke(self, prompt, **kwargs):
        self.chamadas.append(prompt)
        return type("_Resposta", (), {"content": self._resposta})()


def test_feriado_nacional_sem_cidade_nem_estado(monkeypatch):
    fake = _FakeModelo('{"abrangencia": "nacional", "cidade": null, "estado": null, "confianca": "alta"}')
    monkeypatch.setattr("interpretador_descricao.modelo", fake)

    resultado = classificar_abrangencia_feriado("Tiradentes")

    assert resultado["abrangencia"] == "nacional"
    assert resultado["cidade"] is None
    assert resultado["estado"] is None


def test_feriado_municipal_preenche_cidade_pelo_conhecimento_do_modelo(monkeypatch):
    # Caso real que motivou isso: tema só "Nossa Senhora dos Navegantes",
    # sem cidade nenhuma escrita — o modelo deve saber (conhecimento
    # próprio) que é de Porto Alegre.
    fake = _FakeModelo('{"abrangencia": "municipal", "cidade": "Porto Alegre", "estado": "RS", "confianca": "alta"}')
    monkeypatch.setattr("interpretador_descricao.modelo", fake)

    resultado = classificar_abrangencia_feriado("Nossa Senhora dos Navegantes")

    assert resultado["abrangencia"] == "municipal"
    assert resultado["cidade"] == "Porto Alegre"
    assert resultado["estado"] == "RS"


def test_feriado_pouco_conhecido_devolve_null_em_vez_de_chutar(monkeypatch):
    fake = _FakeModelo('{"abrangencia": "municipal", "cidade": null, "estado": null, "confianca": "baixa"}')
    monkeypatch.setattr("interpretador_descricao.modelo", fake)

    resultado = classificar_abrangencia_feriado("Feriado Municipal Qualquer")

    assert resultado["abrangencia"] == "municipal"
    assert resultado["cidade"] is None
    assert resultado["confianca"] == "baixa"


def test_repassa_cidade_e_estado_conhecidos_para_o_prompt(monkeypatch):
    fake = _FakeModelo('{"abrangencia": "municipal", "cidade": "Recife", "estado": "PE", "confianca": "alta"}')
    monkeypatch.setattr("interpretador_descricao.modelo", fake)

    classificar_abrangencia_feriado("Corpus Christi", cidade="Recife", estado="PE")

    assert "Recife" in fake.chamadas[0]
    assert "PE" in fake.chamadas[0]


def test_resposta_com_bloco_markdown_e_interpretada(monkeypatch):
    fake = _FakeModelo('```json\n{"abrangencia": "estadual", "cidade": null, "estado": "SP", "confianca": "alta"}\n```')
    monkeypatch.setattr("interpretador_descricao.modelo", fake)

    resultado = classificar_abrangencia_feriado("Revolução Constitucionalista")

    assert resultado["abrangencia"] == "estadual"
    assert resultado["estado"] == "SP"


def test_abrangencia_invalida_levanta_erro(monkeypatch):
    fake = _FakeModelo('{"abrangencia": "planetario", "cidade": null, "estado": null, "confianca": "alta"}')
    monkeypatch.setattr("interpretador_descricao.modelo", fake)

    with pytest.raises(ValueError):
        classificar_abrangencia_feriado("Algum Feriado")


def test_resposta_nao_json_levanta_erro(monkeypatch):
    fake = _FakeModelo("isso não é json")
    monkeypatch.setattr("interpretador_descricao.modelo", fake)

    with pytest.raises(ValueError):
        classificar_abrangencia_feriado("Algum Feriado")


# --- obter_mes_dia_fixo_feriado ----------------------------------------------

def test_feriado_de_data_fixa_devolve_mes_e_dia(monkeypatch):
    fake = _FakeModelo('{"tem_data_fixa": true, "mes": 1, "dia": 6, "confianca": "alta"}')
    monkeypatch.setattr("interpretador_descricao.modelo", fake)

    resultado = obter_mes_dia_fixo_feriado("Santos Reis")

    assert resultado == {"tem_data_fixa": True, "mes": 1, "dia": 6, "confianca": "alta"}


def test_feriado_movel_devolve_sem_data_fixa(monkeypatch):
    fake = _FakeModelo('{"tem_data_fixa": false, "mes": null, "dia": null, "confianca": "alta"}')
    monkeypatch.setattr("interpretador_descricao.modelo", fake)

    resultado = obter_mes_dia_fixo_feriado("Corpus Christi")

    assert resultado["tem_data_fixa"] is False
    assert resultado["mes"] is None
    assert resultado["dia"] is None


def test_feriado_incerto_devolve_null_em_vez_de_chutar(monkeypatch):
    fake = _FakeModelo('{"tem_data_fixa": false, "mes": null, "dia": null, "confianca": "baixa"}')
    monkeypatch.setattr("interpretador_descricao.modelo", fake)

    resultado = obter_mes_dia_fixo_feriado("Nossa Senhora dos Navegantes")

    assert resultado["mes"] is None
    assert resultado["confianca"] == "baixa"
