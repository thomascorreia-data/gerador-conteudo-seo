import re
import time
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

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "identificador-rodoviaria/1.0 (uso interno)"}

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


# ---------------------------------------------------------------------------
# ETAPA 1: identificar cidade/UF a partir do nome da rodoviária
# (mesma técnica usada em ponto_turistico_config.py)
# ---------------------------------------------------------------------------

def identificar_cidade_rodoviaria(nome_rodoviaria: str) -> dict:
    resultado = {"cidade": None, "uf": None, "erro": None}

    params = {
        "q": nome_rodoviaria,
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
        resultado["erro"] = f"Nenhum resultado encontrado para '{nome_rodoviaria}'."
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
# CONFIGURAÇÃO DECLARATIVA DAS FONTES
#
#   "url"           -> template com {rodoviaria_slug} e/ou {ponto}
#   "container"     -> seletor CSS do bloco com o conteúdo
#   "titulo"        -> seletor CSS do título (ou None)
#   "paragrafos"    -> seletor CSS dos itens de texto
#   "modo"          -> hoje só existe "introducao_completa" (página
#                       própria da rodoviária) — se algum dia surgir um
#                       site tipo "lista de rodoviárias por cidade",
#                       reaproveita-se o "buscar_item_especifico" que já
#                       existe em ponto_turistico_config.py
#   "encoding_especial" (opcional) -> True quando o site declara um
#        charset incomum (ex: ISO-8859-1) que precisa de correção manual
#   "ignorar_paragrafos_com_classe" (opcional) -> descarta itens com
#        atributo class (lixo de interface, comum na Wikipédia)
#   "checar_desambiguacao" (opcional) -> detecta página de desambiguação
#
# Pra adicionar uma nova fonte: só criar uma entrada nova aqui.
# ---------------------------------------------------------------------------

rodoviarias = {
    "QueroPassagem": {
        "url": "https://queropassagem.com.br/rodoviaria-de-{rodoviaria_slug}",
        "container": '.texto:has(h2:-soup-contains("Sobre"))',
        "titulo": "h2",
        "paragrafos": "p",
        "modo": "introducao_completa",
        "encoding_especial": True,
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
# GERAÇÃO DE SLUG (com tentativa automática — nem sempre acerta de
# primeira, já que o QueroPassagem não segue um padrão 100% fixo)
# ---------------------------------------------------------------------------

def _gerar_slug_queropassagem(nome_rodoviaria: str, uf: str = None) -> str:
    """Tentativa automática de gerar o slug. Remove palavras genéricas
    tipo 'Rodoviária de/do', normaliza acento e espaço."""
    nome_limpo = re.sub(
        r"^(rodovi[aá]ria|terminal rodovi[aá]rio)\s+(?:(?:de|do|da)\s+)?",
        "",
        nome_rodoviaria.strip(),
        flags=re.IGNORECASE,
    )
    slug = unidecode(nome_limpo).lower().replace(" ", "-")
    if uf:
        slug = f"{slug}-{uf.lower()}"
    return slug


def _limpar_texto(elemento) -> str:
    for sup in elemento.find_all("sup"):
        sup.decompose()
    texto = " ".join(elemento.get_text(separator=" ", strip=True).split())
    texto = re.sub(r"\s+([.,!?;:])", r"\1", texto)
    return texto


# ---------------------------------------------------------------------------
# COLETA DE UMA FONTE
# ---------------------------------------------------------------------------

def _coletar_fonte(
    nome_fonte: str, config: dict, nome_rodoviaria: str, rodoviaria_slug: str, uf: str = None
) -> dict:
    resultado = {"url": None, "conteudo": None, "erro": None}

    # Quatro formatos de nome disponíveis pros templates de URL:
    #   {ponto}           -> "Rodoviária_do_Tietê" (acento e maiúscula preservados, tipo Wikipédia)
    #   {rodoviaria_slug}  -> "tiete-sp" (sem prefixo, sem acento, minúsculo, com UF — tipo QueroPassagem)
    #   {ponto_slug}      -> "rodoviaria-do-tiete" (sem acento, minúsculo, com hífen, SEM UF)
    #   {ponto_slug_uf}   -> "rodoviaria-do-tiete-sp" (igual ao ponto_slug, mas COM UF no final)
    ponto_slug_maiuscula = nome_rodoviaria.strip().replace(" ", "_")
    ponto_slug_minusculo = unidecode(nome_rodoviaria).strip().lower().replace(" ", "-")

    # Só monta ponto_slug_uf de verdade se a UF estiver disponível — caso
    # contrário, sites que dependem desse formato vão dar erro explícito
    # em vez de gerar uma URL quebrada silenciosamente.
    if "{ponto_slug_uf}" in config["url"] and not uf:
        resultado["erro"] = (
            f"UF não identificada — necessária para montar a URL de {nome_fonte}."
        )
        return resultado

    ponto_slug_com_uf = f"{ponto_slug_minusculo}-{uf.lower()}" if uf else ponto_slug_minusculo

    try:
        url = config["url"].format(
            ponto=ponto_slug_maiuscula,
            rodoviaria_slug=rodoviaria_slug,
            ponto_slug=ponto_slug_minusculo,
            ponto_slug_uf=ponto_slug_com_uf,
        )
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

    if config.get("encoding_especial"):
        resp.encoding = resp.apparent_encoding

    soup = BeautifulSoup(resp.text, "lxml")

    if config.get("checar_desambiguacao"):
        if soup.select_one("#disambigbox") or "pode referir-se a" in soup.get_text()[:2000]:
            resultado["erro"] = f"'{nome_rodoviaria}' é uma página de desambiguação em {nome_fonte}."
            return resultado

    bloco = soup.select_one(config["container"])
    if bloco is None:
        resultado["erro"] = (
            f"Container não encontrado em {nome_fonte} "
            f"(a URL pode estar errada, ou o slug não corresponde a essa rodoviária)."
        )
        return resultado

    paragrafos_tags = bloco.select(config["paragrafos"])
    paragrafos_limpos = []
    for item in paragrafos_tags:
        if config.get("ignorar_paragrafos_com_classe") and item.get("class"):
            continue
        texto = _limpar_texto(item)
        if texto:
            paragrafos_limpos.append(texto)

    if not paragrafos_limpos:
        resultado["erro"] = f"Nenhum parágrafo encontrado em {nome_fonte}."
        return resultado

    resultado["conteudo"] = " ".join(paragrafos_limpos)
    return resultado


# ---------------------------------------------------------------------------
# FLUXO COMPLETO
# ---------------------------------------------------------------------------

def coletar_rodoviaria(nome_rodoviaria: str, slug_queropassagem: str = None) -> dict:
    """
    Coleta a descrição de uma rodoviária a partir de todas as fontes
    configuradas em `rodoviarias`. Você só precisa passar o nome — a
    cidade/UF são descobertas automaticamente (geocodificação).

    Parâmetros:
        nome_rodoviaria: nome da rodoviária/terminal (ex: "Rodoviária do Tietê")
        slug_queropassagem: se você já souber o slug exato (ex: "tiete-sp"),
            passe aqui pra pular a tentativa automática — recomendado quando
            a cidade tem mais de um terminal, já que o padrão varia.

    Retorna:
        {
            "rodoviaria": str,
            "cidade": str,
            "uf": str,
            "fontes": {
                "QueroPassagem": {"url":..., "conteudo":..., "erro":...},
                "Wikipedia": {"url":..., "conteudo":..., "erro":...},
            },
        }
    """
    resultado = {
        "rodoviaria": nome_rodoviaria,
        "cidade": None,
        "uf": None,
        "fontes": {},
    }

    uf = None
    if slug_queropassagem is None:
        # Só precisa geocodificar se não veio um slug manual — economiza
        # uma chamada de rede quando você já sabe o slug certo.
        localizacao = identificar_cidade_rodoviaria(nome_rodoviaria)
        resultado["cidade"] = localizacao["cidade"]
        resultado["uf"] = localizacao["uf"]
        uf = localizacao["uf"]
        if localizacao["erro"]:
            resultado["aviso_localizacao"] = (
                f"Não foi possível identificar a cidade automaticamente: "
                f"{localizacao['erro']}. A tentativa de slug pode falhar."
            )
        time.sleep(1)  # respeita o limite de 1 req/s do Nominatim

    rodoviaria_slug = slug_queropassagem or _gerar_slug_queropassagem(nome_rodoviaria, uf)

    for nome_fonte, config in rodoviarias.items():
        resultado["fontes"][nome_fonte] = _coletar_fonte(
            nome_fonte, config, nome_rodoviaria, rodoviaria_slug, uf
        )

    return resultado


if __name__ == "__main__":
    nome = "Rodoviária do Tietê"

    r = coletar_rodoviaria(nome)
    print(r) 