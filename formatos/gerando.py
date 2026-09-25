"""
Recebe o JSON já normalizado por transformacaoJson.normalizar_lote (lista de
itens com "tema", "tom", "media_palavras", "palavras_chave", "formato", etc.,
no mesmo formato de formatos/descricao/descricao_entrada.json) e gera o
conteúdo de cada item.

Dois formatos têm gerador implementado:
- "Descrição": delega para o grafo em formatos/descricao/grafo_descricao.py,
  que classifica o tema, coleta as fontes, gera, humaniza e revisa
  (refazendo a geração se o revisor reprovar).
- "FAQ": delega para o grafo em formatos/faq/grafo_faq.py, que coleta a
  página, gera, humaniza e revisa (refazendo a geração se o revisor
  reprovar) — mesmo espírito do grafo de Descrição. No FAQ, "tema" é o
  link da página (ver transformacaoJson.py) e "tom" carrega o FOCO (geral/
  compra/regras, não voz) — mesma reinterpretação de campo já feita lá
  dentro.

Itens de outros formatos (Post, Artigo, ...) não travam o lote — voltam com
um "erro" no próprio item.
"""

import json
import os
import sys
from urllib.parse import urlparse

_DIR_FORMATOS = os.path.dirname(__file__)
_DIR_DESCRICAO = os.path.join(_DIR_FORMATOS, "descricao")
_DIR_FAQ = os.path.join(_DIR_FORMATOS, "faq")
# "descricao"/"faq" precisam estar em sys.path pros imports qualificados
# abaixo (usado quando este módulo é importado, ex: pela API); as pastas
# "formatos/descricao" e "formatos/faq" também precisam estar, pois os
# módulos de interação com a IA fazem imports simples (não qualificados)
# entre si (ex: interacao_ia_faq.py importa "from base_faq import ...").
for _dir in (_DIR_FORMATOS, _DIR_DESCRICAO, _DIR_FAQ):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

from descricao.grafo_descricao import gerar_descricao_via_grafo  # noqa: E402
from formatos.descricao.interacao_ia_descricao import (  # noqa: E402
    TOM_PADRAO,
    MEDIA_PALAVRAS_PADRAO,
    PALAVRAS_CHAVE_PADRAO,
)
from faq.grafo_faq import gerar_faq_via_grafo  # noqa: E402
from faq.interacao_ia_faq import QUANTIDADE_PERGUNTAS_PADRAO  # noqa: E402

FORMATOS_DESCRICAO = {"descrição", "descricao"}
FORMATOS_FAQ = {"faq"}


def _entidade_do_link(link: str) -> str:
    """Deriva um nome de exibição pra empresa a partir do link — no FAQ não
    existe campo de nome separado, o "tema" É o link (ver
    transformacaoJson.py), então não tem de onde tirar o nome real da
    empresa sem essa heurística. Usa o primeiro rótulo do domínio (ex:
    "eucatur.buser.com.br" -> "Eucatur"). Fica imperfeito em nomes
    compostos sem separador (ex: "expressojk" -> "Expressojk" em vez de
    "Expresso JK") — mesmo trade-off já aceito em slugify()/limpar_slug()
    no resto do projeto: corrige-se direto no texto gerado quando acontecer."""
    dominio = urlparse(link or "").netloc.lower()
    if dominio.startswith("www."):
        dominio = dominio[4:]
    rotulo = dominio.split(".")[0] if dominio else ""
    rotulo = rotulo.replace("-", " ").replace("_", " ").strip()
    return rotulo.title() if rotulo else "essa empresa"


def _formatar_faq_texto(perguntas: list) -> str:
    """Achata a lista de pergunta/resposta num texto só (mesmo padrão
    P:/R: usado no __main__ de interacao_ia_faq.py), pra caber no campo
    único "conteudo_gerado" que a interface já sabe exibir/copiar/baixar."""
    return "\n\n".join(f"P: {item['pergunta']}\nR: {item['resposta']}" for item in perguntas)


def gerar_conteudo(itens: list) -> list:
    """
    Recebe a lista de itens normalizada (saída de normalizar_lote) e devolve
    a mesma lista, com "categoria_identificada" e "conteudo_gerado" (ou
    "erro") preenchidos em cada item. Categoria, coleta, geração, humanização
    e revisão rodam todas dentro do grafo — aqui só extraímos o resultado.
    """
    resultados = []

    for item in itens:
        formato = (item.get("formato") or "").strip().lower()
        item_resultado = dict(item)

        if formato in FORMATOS_DESCRICAO:
            try:
                resultado = gerar_descricao_via_grafo(
                    tema=item["tema"],
                    tom=item.get("tom") or TOM_PADRAO,
                    media_palavras=item.get("media_palavras") or MEDIA_PALAVRAS_PADRAO,
                    palavras_chave=item.get("palavras_chave") or PALAVRAS_CHAVE_PADRAO,
                )
                item_resultado["categoria_identificada"] = resultado.get("categoria")
                # Mesmo se o revisor nunca aprovou dentro do teto de tentativas,
                # a última versão gerada continua em texto_humanizado — devolve
                # ela junto do erro (como aviso), em vez de não devolver nada.
                if resultado.get("texto_humanizado"):
                    item_resultado["conteudo_gerado"] = resultado["texto_humanizado"]
                if resultado.get("erro"):
                    item_resultado["erro"] = resultado["erro"]
                if resultado.get("sem_fontes"):
                    item_resultado["aviso"] = (
                        "Nenhuma fonte real foi coletada — texto gerado do "
                        "conhecimento geral do modelo, sem verificação contra "
                        "dado nenhum. Vale conferir manualmente antes de publicar."
                    )
            except Exception as erro:
                item_resultado["erro"] = str(erro)

        elif formato in FORMATOS_FAQ:
            try:
                link = item["tema"]
                resultado = gerar_faq_via_grafo(
                    link=link,
                    entidade=_entidade_do_link(link),
                    foco=item.get("tom") or "geral",
                    quantidade_perguntas=item.get("quantidade_perguntas") or QUANTIDADE_PERGUNTAS_PADRAO,
                    palavras_chave=item.get("palavras_chave"),
                )
                # Mesmo se o revisor nunca aprovou dentro do teto de
                # tentativas, a última versão gerada continua em
                # perguntas_humanizadas — devolve ela junto do erro (como
                # aviso), em vez de não devolver nada.
                perguntas_finais = resultado.get("perguntas_humanizadas") or []
                if perguntas_finais:
                    item_resultado["conteudo_gerado"] = _formatar_faq_texto(perguntas_finais)
                else:
                    item_resultado["erro"] = (
                        "O modelo não devolveu nenhuma pergunta/resposta em formato válido."
                    )
                if resultado.get("erro"):
                    item_resultado["erro"] = resultado["erro"]
                if resultado.get("sem_fontes"):
                    item_resultado["aviso"] = (
                        "Nenhuma fonte real foi coletada — texto gerado do "
                        "conhecimento geral do modelo, sem verificação contra "
                        "dado nenhum. Vale conferir manualmente antes de publicar."
                    )
            except Exception as erro:
                item_resultado["erro"] = str(erro)

        else:
            item_resultado["erro"] = (
                f"Formato '{item.get('formato')}' ainda não tem gerador implementado."
            )

        resultados.append(item_resultado)

    return resultados


if __name__ == "__main__":
    caminho_entrada = os.path.join(_DIR_DESCRICAO, "descricao_entrada.json")
    with open(caminho_entrada, encoding="utf-8") as arquivo:
        itens = json.load(arquivo)

    resultados = gerar_conteudo(itens)
    print(json.dumps(resultados, ensure_ascii=False, indent=2))
