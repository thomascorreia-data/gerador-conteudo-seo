"""
Testes de base_lugares_genericos.py — sem rede de verdade, monkeypatch em
requests.get pra simular as respostas HTML.
"""

from base_lugares_genericos import coletar_lugar_generico


class _RespostaFalsa:
    def __init__(self, texto, status=200):
        self.text = texto
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


HTML_COM_CONTEUDO = """
<html><body>
<div id="mw-content-text"><div class="mw-parser-output">
<section data-mw-section-id="0">
<p>Shopping Exemplo é um centro comercial fictício <sup>[1]</sup> usado em teste.</p>
<p>Segundo parágrafo da introdução.</p>
</section>
<section data-mw-section-id="1"><h2>História</h2><p>Não deveria entrar.</p></section>
</div></div>
</body></html>
"""

HTML_DESAMBIGUACAO = """
<html><body>
<div id="disambigbox">Esta página pode referir-se a vários lugares.</div>
</body></html>
"""


def test_coleta_com_sucesso_extrai_paragrafos_da_introducao(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_COM_CONTEUDO)

    monkeypatch.setattr("base_lugares_genericos.requests.get", _fake_get)

    resultado = coletar_lugar_generico("Shopping Exemplo")

    fonte = resultado["fontes"]["Wikipedia"]
    assert fonte["erro"] is None
    assert "Shopping Exemplo é um centro comercial fictício" in fonte["conteudo"]
    assert "Segundo parágrafo" in fonte["conteudo"]
    # não deve puxar parágrafo de seção seguinte (fora da introdução)
    assert "Não deveria entrar" not in fonte["conteudo"]
    # marcação de referência ([1]) deve ser removida
    assert "[1]" not in fonte["conteudo"]


def test_pagina_de_desambiguacao_nao_traz_conteudo(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_DESAMBIGUACAO)

    monkeypatch.setattr("base_lugares_genericos.requests.get", _fake_get)

    resultado = coletar_lugar_generico("Nome Ambíguo")

    fonte = resultado["fontes"]["Wikipedia"]
    assert fonte["conteudo"] is None
    assert "desambiguação" in fonte["erro"]


def test_erro_de_rede_nao_levanta_excecao(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        raise Exception("falha de conexão")

    monkeypatch.setattr("base_lugares_genericos.requests.get", _fake_get)

    resultado = coletar_lugar_generico("Qualquer Lugar")

    fonte = resultado["fontes"]["Wikipedia"]
    assert fonte["conteudo"] is None
    assert "falha de conexão" in fonte["erro"]


def test_url_usa_nome_do_lugar_com_underscore(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        raise Exception("sem rede")

    monkeypatch.setattr("base_lugares_genericos.requests.get", _fake_get)

    resultado = coletar_lugar_generico("Shopping Morumbi")

    assert resultado["fontes"]["Wikipedia"]["url"] == "https://pt.wikipedia.org/wiki/Shopping_Morumbi"
