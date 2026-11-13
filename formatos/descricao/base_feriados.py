"""
Coleta, só na Wikipédia, uma descrição de um feriado (Ano Novo, Natal,
Carnaval, Tiradentes, Nossa Senhora dos Navegantes, etc.) a partir do nome.

Mesma receita simples de base_lugares_genericos.py e base_eventos.py: o
nome do feriado já é a chave de busca direto na URL da Wikipédia. Feriados
MUNICIPAIS (ex: padroeira de uma cidade específica) também reaproveitam a
lógica de "{nome} de {cidade}" de base_eventos.py, pro mesmo motivo: o
nome sozinho às vezes cai numa página genérica (sobre o santo/devoção),
sem a data e o lugar de verdade em que é feriado.
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

WIKIPEDIA_URL = "https://pt.wikipedia.org/wiki/{feriado}"

# Mesmo container/seletor usado em base_cidade.py, base_empresas.py e
# base_eventos.py pra Wikipédia — a introdução do artigo (antes do
# primeiro subtítulo).
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

    # Mesma checagem de desambiguação das outras coletas — nome de feriado
    # genérico demais pode cair numa página que só lista vários artigos
    # com esse nome, sem conteúdo de verdade sobre nenhum.
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


def coletar_feriado(nome_feriado: str, cidade: str = None) -> dict:
    """
    Recebe o nome de um feriado (Ano Novo, Natal, Carnaval, Tiradentes,
    etc.) e busca a introdução do artigo correspondente na Wikipédia — só
    essa fonte.

    Muitos feriados são MUNICIPAIS/regionais (ex: "Nossa Senhora dos
    Navegantes", padroeira de Porto Alegre) — o nome sozinho às vezes cai
    numa página genérica sobre a devoção/santo, sem nenhuma informação
    sobre QUANDO e ONDE é feriado de verdade (ver erro real: o modelo
    chutou "meados de agosto" só porque não tinha fonte nenhuma — a data
    certa, 2 de fevereiro, só aparece no artigo específico do feriado em
    Porto Alegre). Mesma receita de base_eventos.py: se `cidade` for
    passada, tenta primeiro "{nome_feriado} de {cidade}" (padrão comum nos
    títulos da Wikipédia pra feriado municipal) e só cai pro nome sozinho
    se essa tentativa não trouxer conteúdo.

    Retorna:
        {
            "feriado": str,
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
    nomes_a_tentar = [nome_feriado]
    if cidade and cidade.strip().lower() not in nome_feriado.strip().lower():
        nomes_a_tentar.insert(0, f"{nome_feriado} de {cidade}")

    for nome in nomes_a_tentar:
        slug = nome.strip().replace(" ", "_")
        url = WIKIPEDIA_URL.format(feriado=slug)
        paragrafos, erro = _coletar_paragrafos_wikipedia(url)
        if paragrafos:
            break

    return {
        "feriado": nome_feriado,
        "fontes": {
            "Wikipedia": {
                "url": url,
                "conteudo": " ".join(paragrafos) if paragrafos else None,
                "erro": erro,
            },
        },
    }


if __name__ == "__main__":
    print(coletar_feriado("Ano Novo"))
    print(coletar_feriado("Nossa Senhora dos Navegantes", cidade="Porto Alegre"))
