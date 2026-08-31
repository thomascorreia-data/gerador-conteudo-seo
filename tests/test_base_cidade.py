"""
Testes de base_cidade.py — sem rede de verdade, monkeypatch em
requests.get pra simular as respostas HTML.

Foco principal: uf=None não pode levantar exceção. ClickBus/QueroPassagem/
DeOnibus precisam da UF pra montar a URL (formato ".../{cidade}-{uf}") —
sem ela, essas 3 fontes devem ser puladas com erro, e só Wikipédia (que só
precisa do nome da cidade) deve seguir tentando. Sem essa checagem,
gerar_formatos_cidade fazia `uf.lower()` incondicionalmente e quebrava com
AttributeError sempre que o classificador não identificava o estado —
impedindo até o fallback "sem_fontes" de entrar em ação.
"""

from base_cidade import coletando_conteudo, gerar_formatos_cidade


class _RespostaFalsa:
    def __init__(self, texto, status=200):
        self.text = texto
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


HTML_WIKIPEDIA = """
<html><body>
<div id="mw-content-text"><div class="mw-parser-output">
<section data-mw-section-id="0">
<p>Salvador é uma cidade brasileira.</p>
</section>
</div></div>
</body></html>
"""


def test_gerar_formatos_cidade_sem_uf_nao_levanta_excecao():
    cidade_uf, Cidade = gerar_formatos_cidade("Salvador", None)
    assert cidade_uf is None
    assert Cidade == "Salvador"


def test_gerar_formatos_cidade_com_uf_monta_slug_normal():
    cidade_uf, Cidade = gerar_formatos_cidade("São Paulo", "SP")
    assert cidade_uf == "sao-paulo-sp"
    assert Cidade == "São_Paulo"


def test_coletando_conteudo_sem_uf_pula_fontes_que_precisam_de_uf_mas_nao_quebra(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_WIKIPEDIA)

    monkeypatch.setattr("base_cidade.requests.get", _fake_get)

    resultado = coletando_conteudo("Salvador", None)

    for fonte in ("ClickBus", "QueroPassagem", "DeOnibus"):
        assert resultado[fonte]["erro"] is not None
        assert resultado[fonte]["paragrafos"] == []

    assert resultado["Wikipedia"]["erro"] is None
    assert resultado["Wikipedia"]["paragrafos"]


def test_coletando_conteudo_com_uf_tenta_todas_as_fontes(monkeypatch):
    urls_tentadas = []

    def _fake_get(url, headers=None, timeout=None):
        urls_tentadas.append(url)
        return _RespostaFalsa(HTML_WIKIPEDIA)

    monkeypatch.setattr("base_cidade.requests.get", _fake_get)

    coletando_conteudo("Salvador", "BA")

    assert len(urls_tentadas) == 4
    assert any("salvador-ba" in u for u in urls_tentadas)
