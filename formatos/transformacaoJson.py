"""
Normaliza um "lote" de solicitação de conteúdo (envelope + Temas) em uma
lista plana de itens completos — um JSON por conteúdo — pronta para
alimentar o modelo gerador.

Aceita os dois formatos de entrada:

1) Temas como lista de OBJETOS (cada um pode sobrescrever o envelope):
   {
     "Requisitor": "Lucas",
     "Formato": "Post",
     "Autor": "Lucas",
     "Média de Palavras Por Conteúdo": 300,
     "Tom": "Informativo",
     "Temas": [
        {"Formato": "Artigo", "tema": "..."},
        {"tema": "..."}
     ]
   }

2) Temas como lista de STRINGS (tudo herda do envelope):
   {
     "Requisitor": "Lucas",
     "Formato": "Post",
     "Autor": "Lucas",
     "Média de Palavras Por Conteúdo": 300,
     "Tom": "Informativo",
     "Temas": ["...", "..."]
   }

Saída de normalizar_lote(): uma tupla (resultado, avisos)
  resultado = [
     {
       "id": "req-lucas-0",
       "requisitor": "Lucas",
       "autor": "Lucas",
       "formato": "Post",
       "tema": "...",
       "tom": "Informativo",
       "media_palavras": 300,
       "palavras_chave": ["...", "..."]
     },
     ...
  ]
  avisos = ["texto do aviso, se houver alguma inconsistência"]

Observação: no JSON de entrada, "Palavras-chave" é sempre uma única string
com os termos separados por ponto e vírgula (";"), ex: "buser; onibus barato".
Na saída, isso já vem convertido em lista.
"""

import json
import re
import unicodedata


# Campos do envelope que podem ser herdados/sobrescritos por item.
# chave final normalizada -> lista de nomes possíveis (com/sem acento, PT/EN)
CAMPOS_HERDAVEIS = {
    "requisitor": ["requisitor", "requester"],
    "autor": ["autor", "author"],
    "formato": ["formato", "tipo", "format", "type"],
    "tom": ["tom", "tone"],
    "media_palavras": [
        "media de palavras por conteudo",
        "media_palavras",
        "média de palavras por conteúdo",
        "word_count",
        "average_words",
    ],
    "palavras_chave": [
        "palavras-chave",
        "palavras chave",
        "palavras_chave",
        "palavra_chave",
        "keywords",
        "keyword",
    ],
}

CAMPO_TEMAS = ["temas", "lista de temas", "themes", "topics"]
CAMPO_TEMA_ITEM = ["tema", "assunto", "topico", "topic"]
CAMPO_QUANTIDADE = ["quantidade de conteudo", "quantidade_de_conteudo", "quantidade"]


def _slug(texto):
    """Remove acentos, baixa a caixa e troca espaços por underline."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto


def _chave_normalizada(chave):
    """Normaliza uma chave de dict para comparação (sem acento, sem espaço, minúsculo)."""
    chave = unicodedata.normalize("NFKD", str(chave))
    chave = "".join(c for c in chave if not unicodedata.combining(c))
    return chave.lower().strip()


def _buscar_campo(d, nomes_possiveis):
    """Procura em d por qualquer uma das chaves em nomes_possiveis, ignorando acento/caixa."""
    if not isinstance(d, dict):
        return None
    mapa = {_chave_normalizada(k): v for k, v in d.items()}
    for nome in nomes_possiveis:
        chave = _chave_normalizada(nome)
        if chave in mapa and mapa[chave] not in (None, ""):
            return mapa[chave]
    return None


def _dividir_palavras_chave(valor):
    """Recebe a string de palavras-chave (separadas por ';') e devolve uma lista limpa."""
    if valor is None:
        return None
    if isinstance(valor, list):
        partes = [str(v).strip() for v in valor]
    else:
        partes = str(valor).split(";")
    partes = [p.strip() for p in partes if p.strip()]
    return partes or None


def normalizar_lote(payload):
    """
    Recebe o dict do JSON de entrada (qualquer um dos dois formatos)
    e retorna uma tupla (resultado, avisos):
      - resultado: a lista plana de conteúdos, no padrão de saída.
      - avisos: lista de strings com inconsistências não-bloqueantes
        (ex: "Quantidade de Conteúdo" declarada não bate com a real).
    """
    if isinstance(payload, str):
        payload = json.loads(payload)

    temas_raw = _buscar_campo(payload, CAMPO_TEMAS)
    if temas_raw is None:
        raise ValueError('Não encontrei o campo "Temas" (ou "Lista de Temas") no JSON.')
    if not isinstance(temas_raw, list):
        raise ValueError('O campo de temas precisa ser uma lista.')
    if len(temas_raw) == 0:
        raise ValueError('A lista de temas está vazia.')

    requisitor_envelope = _buscar_campo(payload, CAMPOS_HERDAVEIS["requisitor"])
    slug_base = _slug(requisitor_envelope or "lote")

    resultado = []
    for i, item in enumerate(temas_raw):
        if isinstance(item, str):
            tema_texto = item
            item_dict = {}
        elif isinstance(item, dict):
            tema_texto = _buscar_campo(item, CAMPO_TEMA_ITEM)
            if not tema_texto:
                raise ValueError(f'Item {i} da lista de temas não tem campo "tema".')
            item_dict = item
        else:
            raise ValueError(f'Item {i} da lista de temas tem tipo inválido: {type(item)}')

        conteudo = {"id": f"{slug_base}-{i}"}

        # Para cada campo herdável: usa o valor do item se existir, senão cai pro envelope.
        for chave_final, nomes in CAMPOS_HERDAVEIS.items():
            valor = _buscar_campo(item_dict, nomes)
            if valor is None:
                valor = _buscar_campo(payload, nomes)
            conteudo[chave_final] = valor

        conteudo["tema"] = tema_texto
        conteudo["palavras_chave"] = _dividir_palavras_chave(conteudo.get("palavras_chave"))
        resultado.append(conteudo)

    # Checagem de sanidade (não trava, só avisa) contra "Quantidade de Conteúdo"
    quantidade_declarada = _buscar_campo(payload, CAMPO_QUANTIDADE)
    avisos = []
    if quantidade_declarada is not None and int(quantidade_declarada) != len(resultado):
        avisos.append(
            f'"Quantidade de Conteúdo" declarada ({quantidade_declarada}) '
            f'não bate com o número real de temas ({len(resultado)}).'
        )

    return resultado, avisos


if __name__ == "__main__":
    exemplo_com_objetos = """
    {
        "Requisitor": "Lucas",
        "Quantidade de Conteúdo": 3,
        "Autor": "Lucas",
        "Formato": "Post",
        "Média de Palavras Por Conteúdo": 300,
        "Tom": "Informativo",
        "Palavras-chave": "buser; onibus barato; viagem economica",
        "Temas": [
            {
                "Formato": "Post",
                "Autor": "Lucas",
                "Média de Palavras Por Conteúdo": 300,
                "Tom": "Informativo",
                "tema": "Pq a Buser é uma ótima opção para viajar de ônibus"
            },
            {
                "Formato": "Post",
                "Autor": "José",
                "Média de Palavras Por Conteúdo": 300,
                "Tom": "Informativo",
                "Palavras-chave": "buser revoluciona; transporte rodoviario",
                "tema": "Como a Buser está revolucionando o transporte rodoviário"
            },
            {
                "Formato": "Post",
                "Autor": "Buser",
                "Média de Palavras Por Conteúdo": 200,
                "Tom": "Dicas",
                "tema": "Vantagens de usar a Buser para suas viagens"
            }
        ]
    }
    """

    exemplo_com_strings = """
    {
        "Requisitor": "Lucas",
        "Quantidade de Conteúdo": 3,
        "Autor": "Lucas",
        "Formato": "Post",
        "Média de Palavras Por Conteúdo": 300,
        "Tom": "Informativo",
        "Palavras-chave": "buser; onibus barato; viagem economica",
        "Temas": [
            "Pq a Buser é uma ótima opção para viajar de ônibus",
            "Como a Buser está revolucionando o transporte rodoviário",
            "Vantagens de usar a Buser para suas viagens"
        ]
    }
    """

    print("=== Resultado a partir do formato com objetos ===")
    resultado_1, avisos_1 = normalizar_lote(json.loads(exemplo_com_objetos))
    print(json.dumps(resultado_1, ensure_ascii=False, indent=2))
    if avisos_1:
        print("Avisos:", avisos_1)

    print("\n=== Resultado a partir do formato com strings ===")
    resultado_2, avisos_2 = normalizar_lote(json.loads(exemplo_com_strings))
    print(json.dumps(resultado_2, ensure_ascii=False, indent=2))
    if avisos_2:
        print("Avisos:", avisos_2)