"""
Coleta, só na Wikipédia, uma descrição de um evento (festival, show, feira,
festa popular, etc.) a partir do nome.

Mesma receita simples de base_lugares_genericos.py: o nome do evento já é a
chave de busca direto na URL da Wikipédia, sem precisar de geocodificação
nem de identificar cidade antes.
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

WIKIPEDIA_URL = "https://pt.wikipedia.org/wiki/{evento}"

# Mesmo container/seletor usado em base_cidade.py, base_empresas.py e
# base_lugares_genericos.py pra Wikipédia — a introdução do artigo (antes
# do primeiro subtítulo).
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

    # Mesma checagem de desambiguação das outras coletas — nome de evento
    # genérico (ex: "Carnaval") pode cair numa página que só lista vários
    # eventos com esse nome, sem conteúdo de verdade sobre nenhum.
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


def coletar_evento(nome_evento: str, cidade: str = None) -> dict:
    """
    Recebe o nome de um evento (festival, show, feira, festa popular, etc.)
    e busca a introdução do artigo correspondente na Wikipédia — só essa
    fonte, sem geocodificação.

    Muitos eventos brasileiros têm edição local de um evento internacional
    homônimo mais famoso (ex: "Oktoberfest" -> a de Munique, não a de
    Blumenau) — o classificador de tema às vezes devolve só o nome genérico
    em "entidade" e separa a cidade num campo à parte, mesmo quando o tema
    original já vinha com a cidade junto. Se `cidade` for passada e ainda
    não estiver contida no nome, tenta primeiro "{nome_evento} de {cidade}"
    (padrão comum nos títulos da Wikipédia pra esses casos: "Carnaval de
    Salvador", "Oktoberfest de Blumenau") e só cai pro nome sozinho se essa
    tentativa não trouxer conteúdo.

    Retorna:
        {
            "evento": str,
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
    nomes_a_tentar = [nome_evento]
    if cidade and cidade.strip().lower() not in nome_evento.strip().lower():
        nomes_a_tentar.insert(0, f"{nome_evento} de {cidade}")

    for nome in nomes_a_tentar:
        slug = nome.strip().replace(" ", "_")
        url = WIKIPEDIA_URL.format(evento=slug)
        paragrafos, erro = _coletar_paragrafos_wikipedia(url)
        if paragrafos:
            break

    return {
        "evento": nome_evento,
        "fontes": {
            "Wikipedia": {
                "url": url,
                "conteudo": " ".join(paragrafos) if paragrafos else None,
                "erro": erro,
            },
        },
    }


if __name__ == "__main__":
    resultado = coletar_evento("Oktoberfest", cidade="Blumenau")
    print(resultado)
