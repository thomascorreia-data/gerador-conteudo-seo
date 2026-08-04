"""
Recebe o JSON já normalizado por transformacaoJson.normalizar_lote (lista de
itens com "tema", "tom", "media_palavras", "palavras_chave", "formato", etc.,
no mesmo formato de formatos/descricao/descricao_entrada.json) e gera o
conteúdo de cada item.

Hoje só o formato "Descrição" tem gerador implementado (delega para
formatos/descricao/interacao_ia.py, que já cuida de classificar o tema e
coletar as fontes via interpretador_descricao). Itens de outros formatos
(Post, Artigo, ...) não travam o lote — voltam com um "erro" no próprio item.
"""

import json
import os
import sys

_DIR_FORMATOS = os.path.dirname(__file__)
_DIR_DESCRICAO = os.path.join(_DIR_FORMATOS, "descricao")
# "descricao" precisa estar em sys.path pro import qualificado abaixo (usado
# quando este módulo é importado, ex: pela API); "formatos/descricao"
# também precisa estar, pois interacao_ia.py faz imports simples (não
# qualificados) de interpretador_descricao/base_cidade etc.
for _dir in (_DIR_FORMATOS, _DIR_DESCRICAO):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

from descricao.interpretador_descricao import interpretador  # noqa: E402
from descricao.interacao_ia import (  # noqa: E402
    gerar_descricao,
    TOM_PADRAO,
    MEDIA_PALAVRAS_PADRAO,
    PALAVRAS_CHAVE_PADRAO,
)

FORMATOS_DESCRICAO = {"descrição", "descricao"}


def gerar_conteudo(itens: list) -> list:
    """
    Recebe a lista de itens normalizada (saída de normalizar_lote) e devolve
    a mesma lista, com "categoria_identificada" e "conteudo_gerado" (ou
    "erro") preenchidos em cada item. A categoria vem do interpretador, que
    é chamado aqui (em vez de usar gerar_descricao_por_tema) justamente para
    conseguir expor essa classificação como metadado no resultado.
    """
    resultados = []

    for item in itens:
        formato = (item.get("formato") or "").strip().lower()
        item_resultado = dict(item)

        if formato not in FORMATOS_DESCRICAO:
            item_resultado["erro"] = (
                f"Formato '{item.get('formato')}' ainda não tem gerador implementado."
            )
            resultados.append(item_resultado)
            continue

        try:
            classificacao = interpretador(item["tema"])
            item_resultado["categoria_identificada"] = classificacao["categoria"]
            item_resultado["conteudo_gerado"] = gerar_descricao(
                categoria=classificacao["categoria"],
                entidade=classificacao["entidade"],
                fontes=classificacao["fontes"],
                tom=item.get("tom") or TOM_PADRAO,
                media_palavras=item.get("media_palavras") or MEDIA_PALAVRAS_PADRAO,
                palavras_chave=item.get("palavras_chave") or PALAVRAS_CHAVE_PADRAO,
            )
        except Exception as erro:
            item_resultado["erro"] = str(erro)

        resultados.append(item_resultado)

    return resultados


if __name__ == "__main__":
    caminho_entrada = os.path.join(_DIR_DESCRICAO, "descricao_entrada.json")
    with open(caminho_entrada, encoding="utf-8") as arquivo:
        itens = json.load(arquivo)

    resultados = gerar_conteudo(itens)
    print(json.dumps(resultados, ensure_ascii=False, indent=2))
