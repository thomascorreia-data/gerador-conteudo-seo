import re
import time
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz, process

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "identificador-ponto-turistico/1.0 (uso interno)"}

ESTADOS_UF = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM",
    "Bahia": "BA", "Ceará": "CE", "Distrito Federal": "DF",
    "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA",
    "Mato Grosso": "MT", "Mato Grosso do Sul": "MS", "Minas Gerais": "MG",
    "Pará": "PA", "Paraíba": "PB", "Paraná": "PR", "Pernambuco": "PE",
    "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN",
    "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR",
    "Santa Catarina": "SC", "São Paulo": "SP", "Sergipe": "SE",
    "Tocantins": "TO",
}

LIMIAR_CONFIANCA_ATRACAO = 60


# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DECLARATIVA DAS FONTES
#
# Cada fonte tem:
#   "url"         -> template com {Cidade} e/ou {ponto} conforme necessário
#   "container"   -> seletor CSS do bloco com o conteúdo
#   "titulo"      -> seletor CSS do título (ou None)
#   "paragrafos"  -> seletor CSS dos itens de texto (p, li, etc.)
#   "modo"        -> "introducao_completa": pega todos os itens do container
#                     "buscar_item_especifico": entre vários itens, acha o
#                        que corresponde ao ponto turístico buscado
#   "ignorar_paragrafos_com_classe" (opcional) -> descarta <p>/<li> com
#        atributo class (lixo de interface, comum na Wikipédia: coordenadas,
#        legendas de imagem, navbar)
#   "checar_desambiguacao" (opcional) -> detecta página de desambiguação
#        (nome ambíguo sem artigo específico) e retorna erro nesse caso
#
# Pra adicionar uma nova fonte no futuro: basta acrescentar uma entrada
# aqui com esses campos preenchidos — nenhuma outra parte do código
# precisa mudar.
# ---------------------------------------------------------------------------

pontos_turisticos = {
    "Wikivoyage": {
        "url": "https://pt.wikivoyage.org/wiki/{Cidade}",
        "container": "section:has(h2#Veja)",
        "titulo": None,
        "paragrafos": "li",
        "modo": "buscar_item_especifico",
    },
    "Wikipedia": {
        "url": "https://pt.wikipedia.org/wiki/{ponto}",
        "container": "#mw-content-text .mw-parser-output section[data-mw-section-id='0']",
        "titulo": None,
        "paragrafos": "p",
        "modo": "introducao_completa",
        "ignorar_paragrafos_com_classe": True,
        "checar_desambiguacao": True,
    },
}


# ---------------------------------------------------------------------------
# ETAPA 1: identificar cidade a partir do nome do ponto turístico
# ---------------------------------------------------------------------------

def identificar_cidade_ponto_turistico(nome_ponto: str) -> dict:
    resultado = {"cidade": None, "uf": None, "erro": None}

    params = {
        "q": nome_ponto,
        "format": "json",
        "addressdetails": 1,
        "countrycodes": "br",
        "limit": 1,
        "accept-language": "pt-BR",
    }

    try:
        resp = requests.get(
            NOMINATIM_URL, params=params, headers=NOMINATIM_HEADERS, timeout=10
        )
        resp.raise_for_status()
        dados = resp.json()
    except Exception as e:
        resultado["erro"] = str(e)
        return resultado

    if not dados:
        resultado["erro"] = f"Nenhum resultado encontrado para '{nome_ponto}'."
        return resultado

    endereco = dados[0].get("address", {})
    resultado["cidade"] = (
        endereco.get("city") or endereco.get("town") or endereco.get("municipality")
    )
    resultado["uf"] = ESTADOS_UF.get(endereco.get("state"))

    if resultado["cidade"] is None:
        resultado["erro"] = "Resultado encontrado, mas sem cidade identificável."

    return resultado


# ---------------------------------------------------------------------------
# LIMPEZA DE TEXTO (comum a todas as fontes)
# ---------------------------------------------------------------------------

def _limpar_texto(elemento) -> str:
    for sup in elemento.find_all("sup"):
        sup.decompose()
    texto = " ".join(elemento.get_text(separator=" ", strip=True).split())
    texto = re.sub(r"\s+([.,!?;:])", r"\1", texto)
    return texto


def _extrair_nome_candidato(texto: str) -> str:
    """Extrai o 'nome' de um item de lista tipo 'Nome - descrição...'."""
    match = re.match(r"^(.+?)(?:\s*[-–.(]|$)", texto)
    return match.group(1).strip() if match else texto[:40]


# ---------------------------------------------------------------------------
# EXTRAÇÃO POR MODO
# ---------------------------------------------------------------------------

def _extrair_introducao_completa(bloco, config: dict) -> list[str]:
    """Pega todos os itens do container (ex: introdução da Wikipédia)."""
    itens = bloco.select(config["paragrafos"])
    resultado = []
    for item in itens:
        if config.get("ignorar_paragrafos_com_classe") and item.get("class"):
            continue
        texto = _limpar_texto(item)
        if texto:
            resultado.append(texto)
    return resultado


def _extrair_item_especifico(bloco, config: dict, nome_ponto: str) -> tuple[str, float]:
    """Entre vários itens do container, acha o que corresponde ao ponto
    turístico buscado (ex: achar 'MASP' na lista de atrações da Wikivoyage)."""
    itens = bloco.select(config["paragrafos"])
    textos = [_limpar_texto(item) for item in itens]
    textos = [t for t in textos if t]

    if not textos:
        return None, 0

    nomes_candidatos = [_extrair_nome_candidato(t) for t in textos]
    melhor_match = process.extractOne(nome_ponto, nomes_candidatos, scorer=fuzz.WRatio)

    if melhor_match is None or melhor_match[1] < LIMIAR_CONFIANCA_ATRACAO:
        return None, melhor_match[1] if melhor_match else 0

    indice = nomes_candidatos.index(melhor_match[0])
    return textos[indice], melhor_match[1]


# ---------------------------------------------------------------------------
# COLETA DE UMA FONTE
# ---------------------------------------------------------------------------

def _coletar_fonte(nome_fonte: str, config: dict, nome_ponto: str, cidade: str) -> dict:
    resultado = {"url": None, "conteudo": None, "erro": None}

    ponto_slug = nome_ponto.strip().replace(" ", "_")
    cidade_slug = cidade.strip().replace(" ", "_") if cidade else None

    try:
        url = config["url"].format(ponto=ponto_slug, Cidade=cidade_slug)
    except KeyError as e:
        resultado["erro"] = f"Template de URL inválido, falta a chave {e}."
        return resultado

    resultado["url"] = url

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        resultado["erro"] = str(e)
        return resultado

    soup = BeautifulSoup(resp.text, "lxml")

    if config.get("checar_desambiguacao"):
        if soup.select_one("#disambigbox") or "pode referir-se a" in soup.get_text()[:2000]:
            resultado["erro"] = f"'{nome_ponto}' é uma página de desambiguação em {nome_fonte}."
            return resultado

    bloco = soup.select_one(config["container"])
    if bloco is None:
        resultado["erro"] = f"Container não encontrado em {nome_fonte}."
        return resultado

    if config["modo"] == "introducao_completa":
        paragrafos = _extrair_introducao_completa(bloco, config)
        if not paragrafos:
            resultado["erro"] = f"Nenhum parágrafo encontrado em {nome_fonte}."
            return resultado
        resultado["conteudo"] = " ".join(paragrafos)

    elif config["modo"] == "buscar_item_especifico":
        texto, confianca = _extrair_item_especifico(bloco, config, nome_ponto)
        if texto is None:
            resultado["erro"] = f"'{nome_ponto}' não encontrado na lista de {nome_fonte}."
            return resultado
        resultado["conteudo"] = texto
        resultado["confianca"] = round(confianca, 1)

    else:
        resultado["erro"] = f"Modo de extração desconhecido: '{config['modo']}'."

    return resultado


# ---------------------------------------------------------------------------
# FLUXO COMPLETO
# ---------------------------------------------------------------------------

def coletar_ponto_turistico(nome_ponto: str) -> dict:
    """
    Recebe o nome de um ponto turístico, identifica a cidade e coleta o
    conteúdo de cada fonte configurada em `pontos_turisticos`.

    Retorna:
        {
            "ponto_turistico": str,
            "cidade": str,
            "uf": str,
            "fontes": {
                "Wikivoyage": {"url":..., "conteudo":..., "erro":...},
                "Wikipedia": {"url":..., "conteudo":..., "erro":...},
            },
        }
    """
    localizacao = identificar_cidade_ponto_turistico(nome_ponto)

    resultado = {
        "ponto_turistico": nome_ponto,
        "cidade": localizacao["cidade"],
        "uf": localizacao["uf"],
        "fontes": {},
    }

    if localizacao["erro"]:
        resultado["erro"] = f"Falha ao identificar cidade: {localizacao['erro']}"
        return resultado

    time.sleep(1)  # respeita o limite de 1 req/s do Nominatim

    for nome_fonte, config in pontos_turisticos.items():
        resultado["fontes"][nome_fonte] = _coletar_fonte(
            nome_fonte, config, nome_ponto, localizacao["cidade"]
        )

    return resultado


if __name__ == "__main__":
    nome ="Hopi Hari"

    r = coletar_ponto_turistico(nome)
    print(r)
        