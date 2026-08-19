"""
Coleta, via SerpApi (https://serpapi.com/), duas fontes sobre uma empresa a
partir da MESMA busca no Google (economiza cota da API):
  - o AI Overview (endpoint oficial e assíncrono da SerpApi, sem scraping
    direto do google.com);
  - o top 10 de resultados orgânicos da SERP (título, link e snippet/
    description — sem visitar os sites, só o que a própria busca já traz).

Em cima desse top 10, o módulo tenta identificar (por domínio/nome, sem
nenhuma requisição extra):
  - qual resultado parece ser o site oficial da empresa;
  - qual resultado é a página da Wikipédia, se houver — e, se achar, essa é
    a ÚNICA fonte do top 10 pra qual fazemos uma requisição de verdade,
    pra buscar os primeiros parágrafos (mesmo padrão do base_cidade.py).

Requer SERPAPI_API_KEY no arquivo .env na raiz do projeto.

Pra não gastar cota da SerpApi repetindo a mesma empresa em teste, o
resultado de cada busca bem-sucedida é salvo em cache_empresas.json (nesta
mesma pasta). Da próxima vez que essa empresa for pedida, o resultado
salvo é reaproveitado e nenhuma requisição nova é feita.
"""

import json
import os
import re
import time
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from unidecode import unidecode

load_dotenv()

SERPAPI_URL = "https://serpapi.com/search"
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")

CAMINHO_CACHE = os.path.join(os.path.dirname(__file__), "cache_empresas.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Mesmo container/seletor usado em base_cidade.py pra Wikipédia — a
# introdução do artigo (antes do primeiro subtítulo).
WIKIPEDIA_CONTAINER = "#mw-content-text .mw-parser-output section[data-mw-section-id='0']"
WIKIPEDIA_PARAGRAFOS = "p"

# Domínios de plataformas de terceiros conhecidas — mesmo quando o nome da
# empresa aparece no link (ex: instagram.com/buser), não contam como "site
# oficial" da empresa.
DOMINIOS_NAO_OFICIAIS = {
    "wikipedia.org", "instagram.com", "facebook.com", "linkedin.com",
    "youtube.com", "twitter.com", "x.com", "tiktok.com",
    "reclameaqui.com.br", "glassdoor.com", "glassdoor.com.br",
    "indeed.com", "google.com", "play.google.com", "apps.apple.com",
}


def _extrair_dominio(url: str) -> str:
    """Devolve o domínio de uma URL, sem 'www.' (ex: 'buser.com.br')."""
    try:
        dominio = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return dominio[4:] if dominio.startswith("www.") else dominio


def _slug(texto: str) -> str:
    """Remove acentos/pontuação e baixa a caixa, só letras e números."""
    return re.sub(r"[^a-z0-9]", "", unidecode(texto or "").lower())


def _carregar_cache() -> dict:
    if not os.path.exists(CAMINHO_CACHE):
        return {}
    try:
        with open(CAMINHO_CACHE, encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (json.JSONDecodeError, OSError):
        return {}


def _salvar_no_cache(chave: str, resultado: dict) -> None:
    cache = _carregar_cache()
    cache[chave] = resultado
    with open(CAMINHO_CACHE, "w", encoding="utf-8") as arquivo:
        json.dump(cache, arquivo, ensure_ascii=False, indent=2)


def _e_dominio_nao_oficial(dominio: str) -> bool:
    return any(dominio == d or dominio.endswith("." + d) for d in DOMINIOS_NAO_OFICIAIS)


# Termos que indicam operação de linha regular vs. só fretamento/turismo,
# verificados manualmente contra o texto real já coletado (AI Overview +
# snippets do Google) de Allestur (fretamento puro) e Expresso JK (híbrida)
# em cache_empresas.json — os dois casos batem com a classificação correta.
TERMOS_LINHA_REGULAR = [
    "linha regular", "linhas regulares", "linha fixa", "linhas fixas",
    "linha convencional", "linhas convencionais",
]
TERMOS_FRETAMENTO = [
    "fretamento", "turismo", "excursao", "excursoes",
    "aluguel de onibus", "viagens em grupo",
]


def _normalizar_para_busca(texto: str) -> str:
    """Baixa a caixa e remove acentos, mas MANTÉM os espaços — diferente de
    _slug(), que existe pra gerar chave de cache e não serve aqui porque
    juntaria "linha regular" em "linharegular", quebrando a busca por frase."""
    return unidecode(texto or "").lower()


def _texto_para_classificacao(fontes: dict) -> str:
    """Junta o 'conteudo' de cada fonte já coletada (AI Overview, TopSites,
    Wikipedia) num texto só, normalizado, pra buscar os termos acima."""
    partes = [dados.get("conteudo") or "" for dados in fontes.values()]
    return _normalizar_para_busca(" ".join(partes))


def _instrucao_tipo_empresa(tipo: str, entidade: str) -> str:
    """Frase pronta pra injetar no prompt de geração — troca a auto-
    classificação que antes pedíamos ao modelo fazer (e que ele errava com
    frequência pra empresas híbridas) por uma decisão determinística feita
    aqui em código, a partir do texto já coletado."""
    textos = {
        "linha_regular": (
            f'{entidade} opera linha regular de ônibus (classificação automática, '
            f'baseada nas fontes coletadas). Use "passagem" em todas as menções.'
        ),
        "hibrida": (
            f'{entidade} opera linha regular de ônibus e também faz fretamento/turismo '
            f'(classificação automática, baseada nas fontes coletadas). Use "passagem" em '
            f'todas as menções, e pode citar as duas atividades no texto (ex: "opera linhas '
            f'regulares e também realiza fretamento para excursões").'
        ),
        "fretamento": (
            f'{entidade} faz SOMENTE fretamento/turismo/viagens, sem operar nenhuma linha '
            f'regular (classificação automática, baseada nas fontes coletadas). Use "viagem" '
            f'em vez de "passagem" em todas as menções, e não restrinja o texto exclusivamente '
            f'a "transporte rodoviário" — pode incluir roteiros, destinos e serviços de viagem '
            f'coerentes com o fretamento.'
        ),
        "ambiguo": (
            f'Não foi possível identificar com clareza, nas fontes coletadas, se {entidade} '
            f'opera linha regular ou só fretamento/turismo. Use "viagem" em vez de "passagem" '
            f'em todas as menções — é o termo mais seguro nesse caso, evita afirmar algo que '
            f'pode não ser verdade.'
        ),
    }
    return textos[tipo]


def _classificar_tipo_empresa(fontes: dict, entidade: str) -> dict:
    """
    Decide, por palavras-chave no texto já coletado (sem nenhuma chamada
    extra de API ou de LLM), se a empresa opera linha regular, fretamento/
    turismo, as duas coisas (híbrida) ou não deixa isso claro (ambíguo).
    """
    texto = _texto_para_classificacao(fontes)
    tem_regular = any(termo in texto for termo in TERMOS_LINHA_REGULAR)
    tem_fretamento = any(termo in texto for termo in TERMOS_FRETAMENTO)

    if tem_regular and tem_fretamento:
        tipo = "hibrida"
    elif tem_regular:
        tipo = "linha_regular"
    elif tem_fretamento:
        tipo = "fretamento"
    else:
        tipo = "ambiguo"

    palavra = "viagem" if tipo in ("fretamento", "ambiguo") else "passagem"

    return {
        "tipo": tipo,
        "palavra": palavra,
        "instrucao": _instrucao_tipo_empresa(tipo, entidade),
    }


def _identificar_site_oficial(sites: list, nome_empresa: str) -> dict:
    """
    Entre os resultados já coletados, tenta achar o que parece ser o site
    oficial: domínio contém o nome da empresa e não é uma plataforma de
    terceiros conhecida (rede social, Wikipédia, site de reclamação etc.).
    Não faz nenhuma requisição nova — só compara texto que já veio na busca.
    """
    nome_normalizado = _slug(nome_empresa)
    if not nome_normalizado:
        return None

    for site in sites:
        dominio = _extrair_dominio(site.get("link", ""))
        if not dominio or _e_dominio_nao_oficial(dominio):
            continue
        dominio_base = _slug(dominio.split(".")[0])
        if nome_normalizado in dominio_base or dominio_base in nome_normalizado:
            return site

    return None


def _identificar_wikipedia(sites: list) -> dict:
    """Acha, entre os resultados já coletados, o que aponta pra Wikipédia."""
    for site in sites:
        if "wikipedia.org" in _extrair_dominio(site.get("link", "")):
            return site
    return None


def _coletar_paragrafos_wikipedia(url: str) -> tuple:
    """
    Busca a página da Wikipédia encontrada no top 10 e extrai os primeiros
    parágrafos (a introdução do artigo), no mesmo padrão de base_cidade.py.
    Devolve (paragrafos, erro).
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return [], str(e)

    soup = BeautifulSoup(resp.text, "html.parser")
    bloco = soup.select_one(WIKIPEDIA_CONTAINER)

    if bloco is None:
        return [], (
            f"Container '{WIKIPEDIA_CONTAINER}' não encontrado em {url}. "
            "A Wikipédia pode ter mudado a estrutura."
        )

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

    return paragrafos_limpos, None


def _texto_dos_blocos(blocos: list) -> str:
    """Achata os text_blocks do AI Overview (parágrafos, listas, etc.) num único texto."""
    partes = []
    for bloco in blocos:
        tipo = bloco.get("type")
        if tipo == "paragraph":
            partes.append(bloco.get("snippet", ""))
        elif tipo in ("list", "expandable"):
            for item in bloco.get("list", []):
                titulo = item.get("title")
                snippet = item.get("snippet", "")
                partes.append(f"{titulo}: {snippet}" if titulo else snippet)
        elif bloco.get("snippet"):
            partes.append(bloco["snippet"])
    return " ".join(p for p in partes if p)


def _resolver_ai_overview_assincrono(page_token: str, tentativas: int = 5, espera_segundos: float = 2.0):
    """
    A busca inicial pode devolver só um "page_token" (o Overview ainda
    está sendo processado do lado do Google). Nesse caso, a própria SerpApi
    documenta consultar esse endpoint dedicado até o status sair de
    "Processing" — é o fluxo oficial da API, não uma tentativa de forçar
    o Google direto.
    """
    params = {
        "engine": "google_ai_overview",
        "page_token": page_token,
        "api_key": SERPAPI_API_KEY,
    }

    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(SERPAPI_URL, params=params, timeout=15)
            resp.raise_for_status()
            dados = resp.json()
        except Exception as e:
            return None, f"Erro ao consultar o AI Overview (tentativa {tentativa}): {e}"

        blocos = dados.get("ai_overview", {}).get("text_blocks")
        if blocos:
            return blocos, None

        status = dados.get("search_metadata", {}).get("status", "")
        if status != "Processing":
            return None, f"SerpApi não retornou o AI Overview (status: {status or 'desconhecido'})."

        time.sleep(espera_segundos)

    return None, f"AI Overview não ficou pronto a tempo ({tentativas} tentativas)."


def _buscar_serp(nome_empresa: str):
    """
    Faz a única chamada de busca à SerpApi. Devolve (dados, erro) — os dois
    extratores (_extrair_ai_overview e _extrair_top_sites) trabalham em
    cima do mesmo `dados`, sem gastar uma segunda busca.
    """
    if not SERPAPI_API_KEY:
        erro = (
            "SERPAPI_API_KEY não encontrada. Confira se o arquivo .env existe "
            "na raiz do projeto e tem a linha SERPAPI_API_KEY=..."
        )
        return None, erro

    # Buscar só o nome da empresa raramente ativa o AI Overview (é mais um
    # resultado de marca/site oficial). Frases no formato pergunta ativam
    # com muito mais consistência — testado com "Buser" isolado (sem
    # overview) vs. "o que é a empresa Buser" (com overview).
    query = f"o que é a empresa {nome_empresa}"

    params = {
        "engine": "google",
        "q": query,
        "hl": "pt-br",
        "gl": "br",
        "api_key": SERPAPI_API_KEY,
    }

    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json(), None
    except Exception as e:
        return None, f"Erro ao consultar a SerpApi: {e}"


def _extrair_ai_overview(dados: dict, nome_empresa: str) -> dict:
    resultado = {"conteudo": None, "referencias": [], "erro": None}

    ai_overview = dados.get("ai_overview")
    if not ai_overview:
        resultado["erro"] = f"Google não retornou AI Overview para '{nome_empresa}'."
        return resultado

    blocos = ai_overview.get("text_blocks")

    page_token = ai_overview.get("page_token")
    if not blocos and page_token:
        blocos, erro = _resolver_ai_overview_assincrono(page_token)
        if erro:
            resultado["erro"] = erro
            return resultado

    if not blocos:
        resultado["erro"] = f"AI Overview vazio para '{nome_empresa}'."
        return resultado

    resultado["conteudo"] = _texto_dos_blocos(blocos)
    resultado["referencias"] = [
        ref.get("link") for ref in ai_overview.get("references", []) if ref.get("link")
    ]
    return resultado


def _extrair_top_sites(dados: dict, nome_empresa: str, limite: int = 10) -> dict:
    resultado = {
        "conteudo": None,
        "sites": [],
        "site_oficial": None,
        "wikipedia": None,
        "erro": None,
    }

    organicos = dados.get("organic_results", [])[:limite]
    if not organicos:
        resultado["erro"] = f"Nenhum resultado orgânico encontrado para '{nome_empresa}'."
        return resultado

    blocos_texto = []
    for item in organicos:
        titulo = item.get("title", "")
        snippet = item.get("snippet", "")
        resultado["sites"].append({
            "titulo": titulo,
            "link": item.get("link"),
            "snippet": snippet,
        })
        # Só usamos a description que a própria SERP já trouxe — nenhuma
        # requisição extra é feita pros 10 sites.
        if snippet:
            blocos_texto.append(f"{titulo}: {snippet}" if titulo else snippet)

    resultado["conteudo"] = " ".join(blocos_texto)
    resultado["site_oficial"] = _identificar_site_oficial(resultado["sites"], nome_empresa)

    wikipedia = _identificar_wikipedia(resultado["sites"])
    if wikipedia:
        # Única fonte do top 10 pra qual fazemos uma requisição de verdade:
        # a introdução do artigo da Wikipédia, no padrão do base_cidade.py.
        paragrafos, erro_wikipedia = _coletar_paragrafos_wikipedia(wikipedia["link"])
        wikipedia["paragrafos"] = paragrafos
        wikipedia["erro"] = erro_wikipedia
    resultado["wikipedia"] = wikipedia

    return resultado


def coletar_empresa(nome_empresa: str, usar_cache: bool = True) -> dict:
    """
    Recebe o nome de uma empresa e coleta, numa única busca no Google:
      - o AI Overview sobre ela;
      - o top 10 de resultados orgânicos da SERP (só título/link/description,
        sem visitar nenhum dos sites), de onde também tenta identificar qual
        parece ser o site oficial da empresa e qual é a Wikipédia.

    Por padrão (usar_cache=True), antes de gastar cota da SerpApi, confere
    se essa empresa já tem resultado salvo em cache_empresas.json — se
    tiver, devolve ele direto, sem nenhuma requisição nova. Passe
    usar_cache=False pra forçar uma busca de verdade mesmo com cache salvo.

    Retorna:
        {
            "empresa": str,
            "fontes": {
                "Google_AIOverview": {"conteudo": ..., "referencias": [...], "erro": ...},
                "Google_TopSites": {
                    "conteudo": ...,
                    "sites": [{"titulo":..., "link":..., "snippet":...}, ...],
                    "site_oficial": {"titulo":..., "link":..., "snippet":...} | None,
                    "wikipedia": {"titulo":..., "link":..., "snippet":..., "paragrafos": [...], "erro": ...} | None,
                    "erro": ...,
                },
                # só aparece se achou a Wikipédia no top 10:
                "Wikipedia": {"conteudo": ..., "erro": ...},
            },
            "classificacao_tipo": {
                "tipo": "linha_regular" | "hibrida" | "fretamento" | "ambiguo",
                "palavra": "passagem" | "viagem",
                "instrucao": str,  # pronta pra injetar no prompt de geração
            },
        }
    """
    chave_cache = _slug(nome_empresa)

    if usar_cache:
        cache = _carregar_cache()
        if chave_cache in cache:
            resultado_cache = cache[chave_cache]
            # Cache salvo antes dessa classificação existir não tem o campo
            # ainda — calcula em cima do que já foi coletado (sem gastar
            # nenhuma chamada nova) e atualiza o cache pra não repetir isso
            # a cada chamada futura.
            if "classificacao_tipo" not in resultado_cache:
                resultado_cache["classificacao_tipo"] = _classificar_tipo_empresa(
                    resultado_cache["fontes"], nome_empresa
                )
                _salvar_no_cache(chave_cache, resultado_cache)
            return resultado_cache

    dados, erro_busca = _buscar_serp(nome_empresa)

    if erro_busca:
        resultado_ai_overview = {"conteudo": None, "referencias": [], "erro": erro_busca}
        resultado_top_sites = {
            "conteudo": None, "sites": [], "site_oficial": None, "wikipedia": None,
            "erro": erro_busca,
        }
    else:
        resultado_ai_overview = _extrair_ai_overview(dados, nome_empresa)
        resultado_top_sites = _extrair_top_sites(dados, nome_empresa)

    fontes = {
        "Google_AIOverview": resultado_ai_overview,
        "Google_TopSites": resultado_top_sites,
    }

    # Promove os parágrafos da Wikipédia (coletados dentro de
    # Google_TopSites) pra uma fonte própria no nível raiz — é onde
    # montar_fontes_texto (interacao_ia.py) sabe procurar "conteudo"/
    # "paragrafos" de cada fonte. Sem isso, esse texto ficaria coletado
    # mas nunca chegaria no prompt do modelo.
    wikipedia = resultado_top_sites.get("wikipedia")
    if wikipedia:
        fontes["Wikipedia"] = {
            "conteudo": " ".join(wikipedia.get("paragrafos") or []),
            "erro": wikipedia.get("erro"),
        }

    resultado = {
        "empresa": nome_empresa,
        "fontes": fontes,
        "classificacao_tipo": _classificar_tipo_empresa(fontes, nome_empresa),
    }

    # Só cacheia busca que de fato rodou (erro_busca é falha de infra —
    # chave ausente, timeout etc. — não queremos "travar" esse erro em
    # cache; erros por fonte, como "sem AI Overview", são normais e cacheáveis).
    if usar_cache and not erro_busca:
        _salvar_no_cache(chave_cache, resultado)

    return resultado


if __name__ == "__main__":
    nome = "Expresso JK"
    resultado = coletar_empresa(nome)
    print(resultado)
