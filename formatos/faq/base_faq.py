"""
Coleta o conteúdo de uma página pra servir de base ao FAQ gerado sobre ela.

Diferente dos coletores do formato Descrição (formatos/descricao/base_*.py),
que descobrem a URL sozinhos — Wikipédia, Nominatim, SerpApi — aqui a URL já
vem pronta: quem pede o FAQ passa o link da página que quer transformar em
perguntas e respostas como o próprio "tema" (ver transformacaoJson.py — no
FAQ, tema É o link, não tem um campo de link separado). Não tem busca nem
geocodificação, só uma raspagem direta do texto dessa página.

A coleta tem duas camadas:

1. Dados ESTRUTURADOS (schema.org, em <script type="application/ld+json">):
   muitos sites (a própria Buser incluída) já marcam "Organization.description"
   e "FAQPage.mainEntity" nesse formato pra aparecer melhor no Google — dá pra
   ler isso direto, sem heurística nenhuma, e cair em "descricao"/"faq" já
   separados do resto. Não é um hack específico de um site: é um padrão
   público, então funciona em qualquer link (de dentro ou de fora da Buser)
   que também o use — e não custa nada tentar nos que não usam (fica None).
2. Fallback GENÉRICO (sempre roda, complementa o que não veio estruturado):
   pega o texto de dentro de <main>/<article> se existir, senão cai pro
   <body> inteiro, sempre removendo antes o que normalmente é ruído (menu,
   cabeçalho, rodapé, script, estilo). Isso é o que sobra em "conteudo" — o
   "resto" que schema.org não rotulou (ou tudo, se o site não tiver schema
   nenhum).
"""

import json
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


def _limpar_texto(texto: str) -> str:
    """Colapsa qualquer sequência de espaço/quebra de linha (schema.org às
    vezes vem com \\r\\n\\r\\n soltos dentro do texto) num espaço só."""
    return " ".join(texto.split())


def _extrair_descricao_e_faq(soup: BeautifulSoup) -> tuple:
    """Lê os blocos <script type="application/ld+json"> da página (schema.org)
    à procura de "Organization" (descrição da empresa) e "FAQPage" (perguntas
    e respostas já prontas). PRECISA rodar antes de _extrair_paragrafos —
    aquela função decompõe (remove) todo <script> da página, JSON-LD incluso.

    Devolve (descricao, faq):
        descricao: str | None — de Organization.description, ou da meta tag
            <meta name="description"> se não achar Organization.
        faq: list[{"pergunta": str, "resposta": str}] | None — de
            FAQPage.mainEntity, ou None se a página não tiver esse schema.
    """
    descricao = None
    faq = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            dados = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            # JSON-LD malformado não é motivo pra travar a coleta inteira —
            # só ignora esse bloco e segue com o resto (script seguinte, ou
            # o fallback genérico de qualquer forma).
            continue

        for item in (dados if isinstance(dados, list) else [dados]):
            if not isinstance(item, dict):
                continue
            tipo = item.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]

            if descricao is None and "Organization" in tipos and item.get("description"):
                descricao = _limpar_texto(item["description"])

            if "FAQPage" in tipos:
                for entrada in item.get("mainEntity") or []:
                    pergunta = entrada.get("name")
                    resposta = (entrada.get("acceptedAnswer") or {}).get("text")
                    if pergunta and resposta:
                        faq.append({
                            "pergunta": _limpar_texto(pergunta),
                            "resposta": _limpar_texto(resposta),
                        })

    if descricao is None:
        # Fallback mais fraco que Organization.description, mas ainda uma
        # descrição "oficial" da página (a mesma que aparece no resultado
        # de busca do Google) — melhor que nada quando não há schema.org.
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            descricao = _limpar_texto(meta["content"])

    return descricao, (faq or None)


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
                "Pagina": {
                    "url": str,
                    "erro": str | None,
                    "descricao": str | None,           # Organization.description (schema.org) ou meta description
                    "faq": list[{"pergunta", "resposta"}] | None,  # FAQPage.mainEntity (schema.org), se existir
                    "conteudo": str | None,             # "resto": raspagem genérica de <main>/<article>/<body>
                },
            },
        }

    Nunca levanta exceção — se não vier link, a página não responder, ou não
    trouxer nada aproveitável (nem schema.org nem parágrafo genérico), os
    campos ficam None e "erro" explica o motivo. Isso é o bastante pra
    acionar o fallback "sem fontes" do grafo (texto sai do conhecimento
    geral do modelo, sinalizado com aviso) em vez de travar a geração
    inteira — mesmo contrato dos outros base_*.py.
    """
    resultado = {
        "link": link,
        "fontes": {"Pagina": {
            "url": link, "erro": None, "descricao": None, "faq": None, "conteudo": None,
        }},
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

    # PRECISA vir antes de _extrair_paragrafos: aquela função decompõe todo
    # <script> da página (JSON-LD incluso) como parte da limpeza de ruído.
    fonte["descricao"], fonte["faq"] = _extrair_descricao_e_faq(soup)

    paragrafos = _extrair_paragrafos(soup)
    if paragrafos:
        fonte["conteudo"] = " ".join(paragrafos)

    if not fonte["conteudo"] and not fonte["descricao"] and not fonte["faq"]:
        fonte["erro"] = f"Nenhum conteúdo encontrado em {link}."

    return resultado


if __name__ == "__main__":
    import sys

    resultado = coletar_faq(sys.argv[1] if len(sys.argv) > 1 else "https://expressojk.buser.com.br/")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
