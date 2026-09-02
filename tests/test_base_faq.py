"""
Testes de base_faq.py — sem rede de verdade, monkeypatch em requests.get
pra simular as respostas HTML.
"""

from base_faq import coletar_faq


class _RespostaFalsa:
    def __init__(self, texto, status=200):
        self.text = texto
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


HTML_COM_CONTEUDO = """
<html><body>
<nav>Menu | Entrar | Cadastrar</nav>
<header>Cabeçalho do site</header>
<main>
<p>Como funciona o cancelamento? Você pode cancelar até 3 horas antes.</p>
<p>Qual o prazo de reembolso? O valor volta em até 5 dias úteis.</p>
</main>
<footer>Rodapé com links legais</footer>
</body></html>
"""

HTML_SEM_MAIN_NEM_ARTICLE = """
<html><body>
<nav>Menu</nav>
<p>Pergunta e resposta direto no corpo da página, sem main/article.</p>
</body></html>
"""

HTML_SO_LIXO_DE_LAYOUT = """
<html><body>
<nav><p>Menu</p></nav>
<footer><p>Direitos reservados</p></footer>
</body></html>
"""


def test_link_vazio_nao_faz_requisicao_nenhuma(monkeypatch):
    chamadas = []
    monkeypatch.setattr("base_faq.requests.get", lambda *a, **k: chamadas.append(1))

    resultado = coletar_faq("")

    assert chamadas == []
    fonte = resultado["fontes"]["Pagina"]
    assert fonte["conteudo"] is None
    assert "Nenhum link" in fonte["erro"]


def test_coleta_com_sucesso_ignora_nav_header_footer(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_COM_CONTEUDO)

    monkeypatch.setattr("base_faq.requests.get", _fake_get)

    resultado = coletar_faq("https://exemplo.com.br/faq")

    fonte = resultado["fontes"]["Pagina"]
    assert fonte["erro"] is None
    assert "cancelamento" in fonte["conteudo"]
    assert "reembolso" in fonte["conteudo"]
    assert "Menu" not in fonte["conteudo"]
    assert "Cabeçalho" not in fonte["conteudo"]
    assert "Rodapé" not in fonte["conteudo"]


def test_sem_main_ou_article_cai_para_o_body(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_SEM_MAIN_NEM_ARTICLE)

    monkeypatch.setattr("base_faq.requests.get", _fake_get)

    resultado = coletar_faq("https://exemplo.com.br/faq")

    fonte = resultado["fontes"]["Pagina"]
    assert fonte["erro"] is None
    assert "Pergunta e resposta" in fonte["conteudo"]


def test_pagina_so_com_lixo_de_layout_nao_traz_conteudo(monkeypatch):
    # nav/footer são removidos antes de procurar parágrafo — sobrando nada,
    # tem que dar erro em vez de "conteudo" vazio silencioso.
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_SO_LIXO_DE_LAYOUT)

    monkeypatch.setattr("base_faq.requests.get", _fake_get)

    resultado = coletar_faq("https://exemplo.com.br/faq")

    fonte = resultado["fontes"]["Pagina"]
    assert fonte["conteudo"] is None
    assert "Nenhum parágrafo encontrado" in fonte["erro"]


def test_pagina_nao_encontrada_nao_levanta_excecao(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa("<html><body></body></html>", status=404)

    monkeypatch.setattr("base_faq.requests.get", _fake_get)

    resultado = coletar_faq("https://exemplo.com.br/pagina-que-nao-existe")

    fonte = resultado["fontes"]["Pagina"]
    assert fonte["conteudo"] is None
    assert "404" in fonte["erro"]


def test_erro_de_rede_nao_levanta_excecao(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        raise Exception("falha de conexão")

    monkeypatch.setattr("base_faq.requests.get", _fake_get)

    resultado = coletar_faq("https://dominio-que-nao-existe.com.br")

    fonte = resultado["fontes"]["Pagina"]
    assert fonte["conteudo"] is None
    assert "falha de conexão" in fonte["erro"]


def test_paragrafo_curto_e_ignorado_como_ruido():
    from base_faq import _extrair_paragrafos
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<body><main><p>Oi</p><p>Este parágrafo tem tamanho suficiente pra contar.</p></main></body>", "html.parser")
    paragrafos = _extrair_paragrafos(soup)

    assert paragrafos == ["Este parágrafo tem tamanho suficiente pra contar."]
