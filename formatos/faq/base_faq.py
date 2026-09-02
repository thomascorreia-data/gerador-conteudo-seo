"""
Coleta o conteúdo de uma página pra servir de base ao FAQ gerado sobre ela.

Diferente dos coletores do formato Descrição (formatos/descricao/base_*.py),
que descobrem a URL sozinhos — Wikipédia, Nominatim, SerpApi — aqui a URL já
vem pronta: quem pede o FAQ passa o link da página que quer transformar em
perguntas e respostas (ver "link_conteudo" em transformacaoJson.py). Não tem
busca nem geocodificação, só uma raspagem direta do texto dessa página.

Como a página pode ser de QUALQUER site (não é uma estrutura conhecida como
a da Wikipédia, onde dá pra usar um seletor CSS feito sob medida), a
extração é genérica: pega o texto de dentro de <main>/<article> se existir,
senão cai pro <body> inteiro, sempre removendo antes o que normalmente é
ruído (menu, cabeçalho, rodapé, script, estilo).
"""

import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

TIMEOUT_SEGUNDOS = 10

# Textos com menos que isso quase sempre são lixo de navegação (ex: "Menu",
# "Entrar", um item de lista solto) — não interessa como fonte de conteúdo
# pra gerar pergunta/resposta.
TAMANHO_MINIMO_PARAGRAFO = 20


def _extrair_paragrafos(soup: BeautifulSoup) -> list:
    """Extrai o texto "de conteúdo" da página, tentando ignorar o que
    normalmente é ruído de layout (menu, cabeçalho, rodapé etc.)."""
    for lixo in soup.select("script, style, nav, header, footer, aside, noscript"):
        lixo.decompose()

    container = soup.select_one("main, article") or soup.body
    if container is None:
        return []

    paragrafos_limpos = []
    for elemento in container.find_all(["p", "li"]):
        # Remove marcações de referência (ex: [7]) antes de extrair o
        # texto, senão elas ficam coladas na frase — mesmo cuidado dos
        # outros coletores que raspam Wikipédia.
        for sup in elemento.find_all("sup"):
            sup.decompose()

        texto = " ".join(elemento.get_text(separator=" ", strip=True).split())
        texto = re.sub(r"\s+([.,!?;:])", r"\1", texto)
        if texto and len(texto) >= TAMANHO_MINIMO_PARAGRAFO:
            paragrafos_limpos.append(texto)

    return paragrafos_limpos


def coletar_faq(link: str) -> dict:
    """
    Recebe a URL de uma página (passada pelo usuário — não tem busca nem
    geocodificação aqui) e coleta o texto dela, pra servir de fonte ao FAQ
    que vai ser gerado a partir desse conteúdo.

    Retorna:
        {
            "link": str,
            "fontes": {
                "Pagina": {"url": str, "conteudo": str | None, "erro": str | None},
            },
        }

    Nunca levanta exceção — se não vier link, a página não responder, ou
    não trouxer parágrafo nenhum, "conteudo" fica None e "erro" explica o
    motivo. Isso é o bastante pra acionar o fallback "sem fontes" do grafo
    (texto sai do conhecimento geral do modelo, sinalizado com aviso) em
    vez de travar a geração inteira — mesmo contrato dos outros base_*.py.
    """
    resultado = {
        "link": link,
        "fontes": {"Pagina": {"url": link, "conteudo": None, "erro": None}},
    }
    fonte = resultado["fontes"]["Pagina"]

    if not link or not link.strip():
        fonte["erro"] = "Nenhum link foi informado."
        return resultado

    try:
        resp = requests.get(link, headers=HEADERS, timeout=TIMEOUT_SEGUNDOS)
        resp.raise_for_status()
    except Exception as e:
        fonte["erro"] = str(e)
        return resultado

    soup = BeautifulSoup(resp.text, "html.parser")
    paragrafos = _extrair_paragrafos(soup)

    if not paragrafos:
        fonte["erro"] = f"Nenhum parágrafo encontrado em {link}."
        return resultado

    fonte["conteudo"] = " ".join(paragrafos)
    return resultado


if __name__ == "__main__":
    resultado = coletar_faq("https://buser.com.br/faq")
    print(resultado)
