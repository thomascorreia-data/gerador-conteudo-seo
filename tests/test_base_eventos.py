"""
Testes de base_eventos.py — sem rede de verdade, monkeypatch em
requests.get pra simular as respostas HTML.
"""

from base_eventos import coletar_evento


class _RespostaFalsa:
    def __init__(self, texto, status=200):
        self.text = texto
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _html_com_paragrafo(texto_paragrafo):
    return f"""
    <html><body>
    <div id="mw-content-text"><div class="mw-parser-output">
    <section data-mw-section-id="0">
    <p>{texto_paragrafo}</p>
    </section>
    </div></div>
    </body></html>
    """


HTML_DESAMBIGUACAO = """
<html><body>
<div id="disambigbox">Esta página pode referir-se a vários eventos.</div>
</body></html>
"""


def test_coleta_com_sucesso_extrai_paragrafos_da_introducao(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(_html_com_paragrafo("Festival Exemplo é um evento fictício usado em teste."))

    monkeypatch.setattr("base_eventos.requests.get", _fake_get)

    resultado = coletar_evento("Festival Exemplo")

    fonte = resultado["fontes"]["Wikipedia"]
    assert fonte["erro"] is None
    assert "Festival Exemplo é um evento fictício" in fonte["conteudo"]


def test_pagina_de_desambiguacao_nao_traz_conteudo(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_DESAMBIGUACAO)

    monkeypatch.setattr("base_eventos.requests.get", _fake_get)

    resultado = coletar_evento("Nome Ambíguo")

    fonte = resultado["fontes"]["Wikipedia"]
    assert fonte["conteudo"] is None
    assert "desambiguação" in fonte["erro"]


def test_erro_de_rede_nao_levanta_excecao(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        raise Exception("falha de conexão")

    monkeypatch.setattr("base_eventos.requests.get", _fake_get)

    resultado = coletar_evento("Qualquer Evento")

    fonte = resultado["fontes"]["Wikipedia"]
    assert fonte["conteudo"] is None
    assert "falha de conexão" in fonte["erro"]


def test_sem_cidade_usa_so_o_nome_do_evento(monkeypatch):
    urls_tentadas = []

    def _fake_get(url, headers=None, timeout=None):
        urls_tentadas.append(url)
        return _RespostaFalsa(_html_com_paragrafo("Conteúdo do evento."))

    monkeypatch.setattr("base_eventos.requests.get", _fake_get)

    resultado = coletar_evento("Rock in Rio")

    assert urls_tentadas == ["https://pt.wikipedia.org/wiki/Rock_in_Rio"]
    assert resultado["fontes"]["Wikipedia"]["url"] == "https://pt.wikipedia.org/wiki/Rock_in_Rio"


def test_com_cidade_nao_contida_no_nome_tenta_combinar_primeiro(monkeypatch):
    # Caso real que motivou isso: "Oktoberfest" sozinho cai na festa de
    # Munique. Com a cidade "Blumenau" (que não está contida em
    # "Oktoberfest"), a primeira tentativa deve ser "Oktoberfest de
    # Blumenau" — e como ela "funciona" aqui (resposta com parágrafo), não
    # deve nem tentar a segunda.
    urls_tentadas = []

    def _fake_get(url, headers=None, timeout=None):
        urls_tentadas.append(url)
        return _RespostaFalsa(_html_com_paragrafo("Festival de tradições germânicas em Blumenau."))

    monkeypatch.setattr("base_eventos.requests.get", _fake_get)

    resultado = coletar_evento("Oktoberfest", cidade="Blumenau")

    assert urls_tentadas == ["https://pt.wikipedia.org/wiki/Oktoberfest_de_Blumenau"]
    assert "Blumenau" in resultado["fontes"]["Wikipedia"]["conteudo"]


def test_tentativa_com_cidade_falha_cai_para_nome_sozinho(monkeypatch):
    # Se "{evento} de {cidade}" não existir na Wikipédia (evento cujo nome
    # já é específico o bastante, ex: "Rock in Rio" + cidade "Rio de
    # Janeiro"), a segunda tentativa (só o nome) deve ser usada.
    respostas_por_url = {
        "https://pt.wikipedia.org/wiki/Rock_in_Rio_de_Rio_de_Janeiro": _RespostaFalsa("<html><body></body></html>"),
        "https://pt.wikipedia.org/wiki/Rock_in_Rio": _RespostaFalsa(_html_com_paragrafo("Festival de música no Rio.")),
    }
    urls_tentadas = []

    def _fake_get(url, headers=None, timeout=None):
        urls_tentadas.append(url)
        return respostas_por_url[url]

    monkeypatch.setattr("base_eventos.requests.get", _fake_get)

    resultado = coletar_evento("Rock in Rio", cidade="Rio de Janeiro")

    assert urls_tentadas == [
        "https://pt.wikipedia.org/wiki/Rock_in_Rio_de_Rio_de_Janeiro",
        "https://pt.wikipedia.org/wiki/Rock_in_Rio",
    ]
    assert resultado["fontes"]["Wikipedia"]["url"] == "https://pt.wikipedia.org/wiki/Rock_in_Rio"
    assert "Festival de música no Rio" in resultado["fontes"]["Wikipedia"]["conteudo"]


def test_cidade_ja_contida_no_nome_nao_tenta_combinar(monkeypatch):
    urls_tentadas = []

    def _fake_get(url, headers=None, timeout=None):
        urls_tentadas.append(url)
        return _RespostaFalsa(_html_com_paragrafo("Carnaval de Salvador é uma festa popular."))

    monkeypatch.setattr("base_eventos.requests.get", _fake_get)

    coletar_evento("Carnaval de Salvador", cidade="Salvador")

    assert urls_tentadas == ["https://pt.wikipedia.org/wiki/Carnaval_de_Salvador"]
