"""
Coleta, só na Wikipédia, uma descrição de um lugar genérico (shopping,
comércio, restaurante, hotel, aeroporto, etc.) a partir do nome.

Categoria mais simples do projeto pra coletar: diferente de
base_pontos_turisticos.py e base_rodoviarias.py, não precisa de
geocodificação (Nominatim) nem de identificar cidade — o próprio nome do
lugar já é a chave de busca direto na URL da Wikipédia.
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

WIKIPEDIA_URL = "https://pt.wikipedia.org/wiki/{lugar}"

# Mesmo container/seletor usado em base_cidade.py e base_empresas.py pra
# Wikipédia — a introdução do artigo (antes do primeiro subtítulo).
WIKIPEDIA_CONTAINER = "#mw-content-text .mw-parser-output section[data-mw-section-id='0']"
WIKIPEDIA_PARAGRAFOS = "p"


def _coletar_paragrafos_wikipedia(url: str) -> tuple:
    """Busca a página da Wikipédia e extrai os primeiros parágrafos (a
    introdução do artigo, antes do primeiro subtítulo). Devolve
    (paragrafos, erro)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return [], str(e)

    soup = BeautifulSoup(resp.text, "html.parser")

    # Mesma checagem de desambiguação de base_pontos_turisticos.py — nome
    # genérico (ex: "Shopping Central") pode cair numa página que só lista
    # vários lugares com esse nome, sem conteúdo de verdade sobre nenhum.
    if soup.select_one("#disambigbox") or "pode referir-se a" in soup.get_text()[:2000]:
        return [], f"'{url}' é uma página de desambiguação."

    bloco = soup.select_one(WIKIPEDIA_CONTAINER)
    if bloco is None:
        return [], f"Container '{WIKIPEDIA_CONTAINER}' não encontrado em {url}."

    paragrafos_limpos = []
    for p in bloco.select(WIKIPEDIA_PARAGRAFOS):
        # Remove marcações de referência (ex: [7]) antes de extrair o
        # texto, senão elas ficam coladas na frase.
        for sup in p.find_all("sup"):
            sup.decompose()

        texto = " ".join(p.get_text(separator=" ", strip=True).split())
        texto = re.sub(r"\s+([.,!?;:])", r"\1", texto)
        if texto:
            paragrafos_limpos.append(texto)

    if not paragrafos_limpos:
        return [], f"Nenhum parágrafo encontrado em {url}."

    return paragrafos_limpos, None


def coletar_lugar_generico(nome_lugar: str) -> dict:
    """
    Recebe o nome de um lugar genérico (shopping, comércio, restaurante,
    hotel, aeroporto, etc.) e busca a introdução do artigo correspondente
    na Wikipédia — só essa fonte, sem geocodificação nem identificação de
    cidade.

    Retorna:
        {
            "lugar": str,
            "fontes": {
                "Wikipedia": {"url": str, "conteudo": str | None, "erro": str | None},
            },
        }

    Se a página não existir, for desambiguação, ou não tiver parágrafo
    nenhum, "conteudo" fica None e "erro" explica o motivo — mas a função
    nunca levanta exceção: quem chama (grafo_descricao.py) sabe lidar com
    fontes vazias, gerando o texto do conhecimento geral do modelo nesse
    caso (ver "sem_fontes" no grafo).
    """
    slug = nome_lugar.strip().replace(" ", "_")
    url = WIKIPEDIA_URL.format(lugar=slug)

    paragrafos, erro = _coletar_paragrafos_wikipedia(url)

    return {
        "lugar": nome_lugar,
        "fontes": {
            "Wikipedia": {
                "url": url,
                "conteudo": " ".join(paragrafos) if paragrafos else None,
                "erro": erro,
            },
        },
    }


if __name__ == "__main__":
    nome = "Shopping Eldorado"
    resultado = coletar_lugar_generico(nome)
    print(resultado)
