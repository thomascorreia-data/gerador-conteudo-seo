"""
Testes de base_feriados.py — sem rede de verdade, monkeypatch em
requests.get pra simular as respostas HTML.
"""

from base_feriados import coletar_feriado


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
<div id="disambigbox">Esta página pode referir-se a vários feriados.</div>
</body></html>
"""


def test_coleta_com_sucesso_extrai_paragrafos_da_introducao(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(_html_com_paragrafo("Tiradentes é um feriado nacional brasileiro."))

    monkeypatch.setattr("base_feriados.requests.get", _fake_get)

    resultado = coletar_feriado("Tiradentes")

    fonte = resultado["fontes"]["Wikipedia"]
    assert fonte["erro"] is None
    assert "Tiradentes é um feriado nacional" in fonte["conteudo"]


def test_pagina_de_desambiguacao_nao_traz_conteudo(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_DESAMBIGUACAO)

    monkeypatch.setattr("base_feriados.requests.get", _fake_get)

    resultado = coletar_feriado("Nome Ambíguo")

    fonte = resultado["fontes"]["Wikipedia"]
    assert fonte["conteudo"] is None
    assert "desambiguação" in fonte["erro"]


def test_erro_de_rede_nao_levanta_excecao(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        raise Exception("falha de conexão")

    monkeypatch.setattr("base_feriados.requests.get", _fake_get)

    resultado = coletar_feriado("Qualquer Feriado")

    fonte = resultado["fontes"]["Wikipedia"]
    assert fonte["conteudo"] is None
    assert "falha de conexão" in fonte["erro"]


def test_sem_cidade_usa_so_o_nome_do_feriado(monkeypatch):
    urls_tentadas = []

    def _fake_get(url, headers=None, timeout=None):
        urls_tentadas.append(url)
        return _RespostaFalsa(_html_com_paragrafo("Conteúdo do feriado."))

    monkeypatch.setattr("base_feriados.requests.get", _fake_get)

    resultado = coletar_feriado("Natal")

    assert urls_tentadas == ["https://pt.wikipedia.org/wiki/Natal"]
    assert resultado["fontes"]["Wikipedia"]["url"] == "https://pt.wikipedia.org/wiki/Natal"


def test_feriado_municipal_com_cidade_tenta_combinar_primeiro(monkeypatch):
    # Caso real que motivou isso: "Nossa Senhora dos Navegantes" sozinho
    # cai numa página genérica sobre a devoção mariana, sem data nem
    # lugar. Com a cidade "Porto Alegre", a primeira tentativa deve ser
    # "Nossa Senhora dos Navegantes de Porto Alegre" — e como ela
    # "funciona" aqui, não deve nem tentar a segunda.
    urls_tentadas = []

    def _fake_get(url, headers=None, timeout=None):
        urls_tentadas.append(url)
        return _RespostaFalsa(_html_com_paragrafo("Feriado municipal de Porto Alegre, celebrado em 2 de fevereiro."))

    monkeypatch.setattr("base_feriados.requests.get", _fake_get)

    resultado = coletar_feriado("Nossa Senhora dos Navegantes", cidade="Porto Alegre")

    assert urls_tentadas == ["https://pt.wikipedia.org/wiki/Nossa_Senhora_dos_Navegantes_de_Porto_Alegre"]
    assert "Porto Alegre" in resultado["fontes"]["Wikipedia"]["conteudo"]


def test_tentativa_com_cidade_falha_cai_para_nome_sozinho(monkeypatch):
    respostas_por_url = {
        "https://pt.wikipedia.org/wiki/Corpus_Christi_de_Recife": _RespostaFalsa("<html><body></body></html>"),
        "https://pt.wikipedia.org/wiki/Corpus_Christi": _RespostaFalsa(_html_com_paragrafo("Festa católica da Eucaristia.")),
    }
    urls_tentadas = []

    def _fake_get(url, headers=None, timeout=None):
        urls_tentadas.append(url)
        return respostas_por_url[url]

    monkeypatch.setattr("base_feriados.requests.get", _fake_get)

    resultado = coletar_feriado("Corpus Christi", cidade="Recife")

    assert urls_tentadas == [
        "https://pt.wikipedia.org/wiki/Corpus_Christi_de_Recife",
        "https://pt.wikipedia.org/wiki/Corpus_Christi",
    ]
    assert resultado["fontes"]["Wikipedia"]["url"] == "https://pt.wikipedia.org/wiki/Corpus_Christi"


def test_cidade_ja_contida_no_nome_nao_tenta_combinar(monkeypatch):
    urls_tentadas = []

    def _fake_get(url, headers=None, timeout=None):
        urls_tentadas.append(url)
        return _RespostaFalsa(_html_com_paragrafo("Nossa Senhora dos Navegantes de Porto Alegre é um feriado municipal."))

    monkeypatch.setattr("base_feriados.requests.get", _fake_get)

    coletar_feriado("Nossa Senhora dos Navegantes de Porto Alegre", cidade="Porto Alegre")

    assert urls_tentadas == ["https://pt.wikipedia.org/wiki/Nossa_Senhora_dos_Navegantes_de_Porto_Alegre"]
