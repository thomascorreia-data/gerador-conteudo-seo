import re
import requests
from bs4 import BeautifulSoup
from unidecode import unidecode

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO POR SITE: URL + seletores, tudo junto
#
#   "url"          -> template da URL, com {cidade_uf} ou {Cidade}
#   "container"    -> seletor CSS do bloco que envolve o conteúdo(class da div principal)
#   "titulo"       -> seletor CSS do título, relativo ao container(tag título)
#   "paragrafos"   -> seletor CSS dos parágrafos, relativo ao container(tag paragrafo)
#
# Sites sem seletor preenchido (None) ainda podem gerar a URL normalmente,
# só não terão extração de conteúdo até você me passar o HTML de exemplo.
# ---------------------------------------------------------------------------

cidade = {
    "ClickBus": {
        "url": "https://www.clickbus.com.br/onibus/{cidade_uf}",
        "container": '[data-testid="lp-destinations-container-places"]',
        "titulo": "h2",
        "paragrafos": "p",
    },
    "QueroPassagem": {
        "url": "https://queropassagem.com.br/para-{cidade_uf}",
        "container": ".conteudo-de-texto",
        "titulo": "h3",
        "paragrafos": "p",
    },
    "DeOnibus": {
        "url": "https://deonibus.com/onibus-para/{cidade_uf}",
        "container": "#toggle-content",
        "titulo": "h2",
        "paragrafos": "p",
    },
    "Wikipedia": {
        "url": "https://pt.wikipedia.org/wiki/{Cidade}",
        "container": "#mw-content-text .mw-parser-output section[data-mw-section-id='0']",
        "titulo": None, 
        "paragrafos": "p",
    },
}

# ---------------------------------------------------------------------------
# GERAÇÃO DE SLUGS
# ---------------------------------------------------------------------------

def gerar_formatos_cidade(nome: str, uf: str) -> tuple[str, str]:
    """Retorna (cidade_uf, Cidade) a partir do nome bruto + UF.
    cidade_uf -> 'brasilia-df' (sem acento, minúsculo, hífen)
    Cidade     -> 'Brasília' (com acento, underscore se tiver espaço)"""
    nome_limpo = nome.strip()
    cidade_uf = unidecode(nome_limpo).lower().replace(" ", "-") + "-" + uf.lower()
    Cidade = nome_limpo.replace(" ", "_")
    return cidade_uf, Cidade

# ---------------------------------------------------------------------------
# FLUXO PRINCIPAL
# ---------------------------------------------------------------------------

def coletando_conteudo(nome: str, uf: str) -> dict[str, dict[str, str]]:
    """Gera as URLs e extrai o conteúdo de cada site, se possível."""
    cidade_uf, Cidade = gerar_formatos_cidade(nome, uf)
    resultados = {}

    for site, config in cidade.items():
        url = config["url"].format(cidade_uf=cidade_uf, Cidade=Cidade)
        container = config["container"]
        titulo_sel = config["titulo"]
        paragrafos_sel = config["paragrafos"]

        resultado_site = {
            "url": url,
            "titulo": None,
            "paragrafos": [],
            "erro": None,
        }

        if container is None:
            resultado_site["erro"] = "Seletor ainda não configurado para este site."
            resultados[site] = resultado_site
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            resultado_site["erro"] = str(e)
            resultados[site] = resultado_site
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        bloco = soup.select_one(container)

        if bloco is None:
            resultado_site["erro"] = (
                f"Container '{container}' não encontrado. "
                "O site pode ter mudado a estrutura."
            )
            resultados[site] = resultado_site
            continue

        titulo_tag = bloco.select_one(titulo_sel) if titulo_sel else None
        if titulo_tag:
            resultado_site["titulo"] = " ".join(titulo_tag.get_text(strip=True).split())

        paragrafos_tags = bloco.select(paragrafos_sel)
        paragrafos_limpos = []
        for p in paragrafos_tags:
            # Remove marcações de referência (ex: [7], [nota 1]) antes de
            # extrair o texto, senão elas ficam coladas na frase.
            for sup in p.find_all("sup"):
                sup.decompose()

            texto = " ".join(p.get_text(separator=" ", strip=True).split())
            # Remove espaço que sobra antes de pontuação (ex: "Paulo ?" -> "Paulo?")
            texto = re.sub(r"\s+([.,!?;:])", r"\1", texto)
            if texto:  # ignora parágrafos vazios (comuns na Wikipedia)
                paragrafos_limpos.append(texto)
        resultado_site["paragrafos"] = paragrafos_limpos

        resultados[site] = resultado_site

    return resultados


if __name__ == "__main__":
    resultados = coletando_conteudo("São Paulo", "SP")

    print(resultados)