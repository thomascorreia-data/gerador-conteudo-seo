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

HTML_COM_JSON_LD = """
<html><head>
<meta name="description" content="Descrição da meta tag, usada só se não houver Organization.">
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Organization", "name": "Empresa X", "description": "Descrição oficial da Empresa X, vinda do schema.org."}
</script>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
  {"@type": "Question", "name": "Aceita pet?", "acceptedAnswer": {"@type": "Answer", "text": "Sim, em caixa de transporte."}},
  {"@type": "Question", "name": "Tem banheiro a bordo?", "acceptedAnswer": {"@type": "Answer", "text": "Sim, em todos os veículos."}}
]}
</script>
</head><body>
<main><p>Parágrafo comum que não veio do schema.org, ainda deve ir pro campo conteudo.</p></main>
</body></html>
"""

HTML_SO_JSON_LD_SEM_MAIN = """
<html><head>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
  {"@type": "Question", "name": "Pergunta única?", "acceptedAnswer": {"@type": "Answer", "text": "Resposta única."}}
]}
</script>
</head><body>
<nav><p>Menu</p></nav>
</body></html>
"""

HTML_SEM_ORGANIZATION_USA_META = """
<html><head>
<meta name="description" content="Descrição só da meta tag, sem Organization no schema.">
</head><body>
<main><p>Parágrafo qualquer que preenche o conteudo genérico normalmente.</p></main>
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
    assert "Nenhum conteúdo encontrado" in fonte["erro"]


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


def test_json_ld_preenche_descricao_e_faq_junto_com_conteudo_generico(monkeypatch):
    # Organization.description e FAQPage.mainEntity vêm junto do "conteudo"
    # genérico de sempre — um não substitui o outro, são campos separados.
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_COM_JSON_LD)

    monkeypatch.setattr("base_faq.requests.get", _fake_get)

    resultado = coletar_faq("https://exemplo.com.br/empresa")
    fonte = resultado["fontes"]["Pagina"]

    assert fonte["erro"] is None
    assert fonte["descricao"] == "Descrição oficial da Empresa X, vinda do schema.org."
    assert fonte["faq"] == [
        {"pergunta": "Aceita pet?", "resposta": "Sim, em caixa de transporte."},
        {"pergunta": "Tem banheiro a bordo?", "resposta": "Sim, em todos os veículos."},
    ]
    assert "Parágrafo comum" in fonte["conteudo"]


def test_json_ld_sozinho_sem_main_nao_da_erro(monkeypatch):
    # Sem <main>/<article> com parágrafo nenhum, "conteudo" fica None — mas
    # como o FAQPage estruturado existe, não é "nada aproveitável", então
    # não deve gerar erro.
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_SO_JSON_LD_SEM_MAIN)

    monkeypatch.setattr("base_faq.requests.get", _fake_get)

    resultado = coletar_faq("https://exemplo.com.br/so-schema")
    fonte = resultado["fontes"]["Pagina"]

    assert fonte["erro"] is None
    assert fonte["conteudo"] is None
    assert fonte["faq"] == [{"pergunta": "Pergunta única?", "resposta": "Resposta única."}]


def test_sem_organization_usa_meta_description_como_fallback(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_SEM_ORGANIZATION_USA_META)

    monkeypatch.setattr("base_faq.requests.get", _fake_get)

    resultado = coletar_faq("https://exemplo.com.br/sem-organization")
    fonte = resultado["fontes"]["Pagina"]

    assert fonte["descricao"] == "Descrição só da meta tag, sem Organization no schema."
    assert fonte["faq"] is None


def test_pagina_sem_schema_nenhum_deixa_descricao_e_faq_none(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        return _RespostaFalsa(HTML_COM_CONTEUDO)

    monkeypatch.setattr("base_faq.requests.get", _fake_get)

    resultado = coletar_faq("https://exemplo.com.br/sem-schema")
    fonte = resultado["fontes"]["Pagina"]

    assert fonte["descricao"] is None
    assert fonte["faq"] is None
    assert fonte["conteudo"] is not None
