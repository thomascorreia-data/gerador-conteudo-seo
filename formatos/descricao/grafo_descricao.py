"""
Grafo LangGraph que substitui o par interpretador_descricao + interacao_ia_
descricao como ponto de entrada de geração: classifica o tema, roteia pra
coleta certa por categoria, gera, humaniza e revisa o resultado — voltando
pra geração se o revisor reprovar, até um teto de tentativas.

Só a coleta (e, pra empresa, a classificação de tipo) é ramificada por
categoria. Gerar, humanizar e revisar são nós únicos, compartilhados por
qualquer categoria — o humanizador já funciona assim hoje (roda pra
qualquer descrição, não só empresa), então não faz sentido duplicar esse
trecho por categoria só porque o revisor é novo.

Desenho completo (com o motivo de cada decisão) em:
https://claude.ai/code/artifact/29df91fe-b5f2-4d65-81b8-33f7bb445103
"""

from typing import TypedDict

from langgraph.graph import StateGraph, END

from interpretador_descricao import classificar_tema
from base_empresas import coletar_empresa
from base_pontos_turisticos import coletar_ponto_turistico
from base_cidade import coletando_conteudo
from base_rodoviarias import coletar_rodoviaria
from interacao_ia_descricao import gerar_texto_bruto, humanizar_texto

MAX_TENTATIVAS = 3

# Cobre os casos concretos já vistos nos testes desta conversa. Se aparecer
# um caso novo de palavra banida escapando, é só adicionar aqui — não exige
# mexer no grafo.
PALAVRAS_BANIDAS = [
    "garante", "garantindo", "garantia", "garanta", "garantir",
    "memórias inesquecíveis", "aventura", "experiência única",
    "não perca",
]


class DescricaoState(TypedDict, total=False):
    # entrada
    tema: str
    tom: str
    media_palavras: int
    palavras_chave: list

    # depois de classificar_tema
    categoria: str
    entidade: str
    cidade: str
    estado: str

    # depois da coleta
    fontes: dict
    classificacao_tipo: dict  # só populado pra categoria "empresa"

    # geração / humanização
    texto_gerado: str
    texto_humanizado: str

    # revisor
    revisao: dict  # {"aprovado": bool, "motivos": [str, ...]}
    tentativas: int

    # saída
    erro: str


# ---------------------------------------------------------------------------
# Nós
# ---------------------------------------------------------------------------

def no_classificar_tema(state: DescricaoState) -> dict:
    classificacao = classificar_tema(state["tema"])
    return {
        "categoria": classificacao["categoria"],
        "entidade": classificacao.get("entidade"),
        "cidade": classificacao.get("cidade"),
        "estado": classificacao.get("estado"),
    }


def _rotear_por_categoria(state: DescricaoState) -> str:
    return {
        "empresa": "coletar_empresa",
        "ponto_turistico": "coletar_ponto_turistico",
        "cidade": "coletar_cidade",
        "terminal_rodoviaria": "coletar_terminal_rodoviaria",
    }.get(state["categoria"], "categoria_nao_implementada")


def no_coletar_empresa(state: DescricaoState) -> dict:
    # coletar_empresa já calcula a classificação de tipo (passagem/viagem)
    # junto da coleta — não existe um nó separado pra isso porque seria só
    # reler um campo que já veio pronto, sem nenhum comportamento novo.
    resultado = coletar_empresa(state["entidade"])
    return {
        "fontes": resultado["fontes"],
        "classificacao_tipo": resultado.get("classificacao_tipo"),
    }


def no_coletar_ponto_turistico(state: DescricaoState) -> dict:
    resultado = coletar_ponto_turistico(state["entidade"])
    if resultado.get("erro"):
        raise ValueError(resultado["erro"])
    return {"fontes": resultado["fontes"]}


def no_coletar_cidade(state: DescricaoState) -> dict:
    cidade = state.get("cidade") or state["entidade"]
    fontes = coletando_conteudo(cidade, state.get("estado"))
    return {"fontes": fontes, "entidade": cidade}


def no_coletar_terminal_rodoviaria(state: DescricaoState) -> dict:
    resultado = coletar_rodoviaria(state["entidade"])
    return {"fontes": resultado["fontes"]}


def no_categoria_nao_implementada(state: DescricaoState) -> dict:
    raise NotImplementedError(f"Coleta para '{state['categoria']}' ainda não implementada")


def no_gerar(state: DescricaoState) -> dict:
    texto = gerar_texto_bruto(
        categoria=state["categoria"],
        entidade=state["entidade"],
        fontes=state["fontes"],
        tom=state.get("tom") or "informativo",
        media_palavras=state.get("media_palavras"),
        palavras_chave=state.get("palavras_chave"),
        classificacao_tipo=state.get("classificacao_tipo"),
    )
    return {"texto_gerado": texto}


def no_humanizar(state: DescricaoState) -> dict:
    instrucao_tipo_empresa = (state.get("classificacao_tipo") or {}).get("instrucao", "")
    texto = humanizar_texto(state["texto_gerado"], instrucao_tipo_empresa)
    return {"texto_humanizado": texto}


def _checar_regras(state: DescricaoState) -> list:
    """Checagens determinísticas (sem LLM) sobre o texto já humanizado.
    Universais: rodam pra qualquer categoria/tom. Condicionais: só rodam
    quando o campo relevante existe no state — é assim que o mesmo nó
    revisor cobre empresa e as outras categorias sem duplicar lógica."""
    texto = state["texto_humanizado"]
    texto_lower = texto.lower()
    motivos = []

    for palavra in PALAVRAS_BANIDAS:
        if palavra in texto_lower:
            motivos.append(f"contém palavra banida: '{palavra}'")

    media_palavras = state.get("media_palavras")
    if media_palavras:
        total_palavras = len(texto.split())
        limite = media_palavras * 1.2
        if total_palavras > limite:
            motivos.append(f"{total_palavras} palavras, acima do limite de {limite:.0f}")

    classificacao_tipo = state.get("classificacao_tipo")
    if classificacao_tipo and classificacao_tipo["palavra"] == "passagem":
        # Só checa esse sentido (linha regular/híbrida -> "passagem" tem que
        # aparecer). O inverso não dá pra checar assim: "viagem" aparece
        # quase sempre em qualquer texto, mesmo correto, porque "Viagem
        # segura" é um dos 7 diferenciais da Buser permitidos no prompt —
        # checar "viagem presente e passagem ausente" reprovava até texto
        # certo de empresa fretamento puro.
        if "passagem" not in texto_lower:
            motivos.append(
                'empresa linha regular/híbrida deveria mencionar "passagem" '
                'pelo menos uma vez, só apareceu "viagem"'
            )

    if state.get("tom") == "vendas":
        paragrafos = [p for p in texto.split("\n\n") if p.strip()]
        if not (3 <= len(paragrafos) <= 4):
            motivos.append(f"{len(paragrafos)} parágrafos, esperado 3 a 4")

    return motivos


def no_revisor(state: DescricaoState) -> dict:
    motivos = _checar_regras(state)
    return {"revisao": {"aprovado": not motivos, "motivos": motivos}}


def _apos_revisor(state: DescricaoState) -> str:
    if state["revisao"]["aprovado"]:
        return "aprovado"
    if state.get("tentativas", 0) + 1 >= MAX_TENTATIVAS:
        return "esgotado"
    return "tentar_de_novo"


def no_incrementar_tentativa(state: DescricaoState) -> dict:
    return {"tentativas": state.get("tentativas", 0) + 1}


def no_marcar_erro(state: DescricaoState) -> dict:
    motivos = "; ".join(state["revisao"]["motivos"])
    return {
        "erro": (
            f"Revisor reprovou {MAX_TENTATIVAS}x seguidas e não foi possível "
            f"corrigir: {motivos}"
        )
    }


# ---------------------------------------------------------------------------
# Montagem do grafo
# ---------------------------------------------------------------------------

def construir_grafo():
    grafo = StateGraph(DescricaoState)

    grafo.add_node("classificar_tema", no_classificar_tema)
    grafo.add_node("coletar_empresa", no_coletar_empresa)
    grafo.add_node("coletar_ponto_turistico", no_coletar_ponto_turistico)
    grafo.add_node("coletar_cidade", no_coletar_cidade)
    grafo.add_node("coletar_terminal_rodoviaria", no_coletar_terminal_rodoviaria)
    grafo.add_node("categoria_nao_implementada", no_categoria_nao_implementada)
    grafo.add_node("gerar", no_gerar)
    grafo.add_node("humanizar", no_humanizar)
    grafo.add_node("revisor", no_revisor)
    grafo.add_node("incrementar_tentativa", no_incrementar_tentativa)
    grafo.add_node("marcar_erro", no_marcar_erro)

    grafo.set_entry_point("classificar_tema")

    grafo.add_conditional_edges("classificar_tema", _rotear_por_categoria, {
        "coletar_empresa": "coletar_empresa",
        "coletar_ponto_turistico": "coletar_ponto_turistico",
        "coletar_cidade": "coletar_cidade",
        "coletar_terminal_rodoviaria": "coletar_terminal_rodoviaria",
        "categoria_nao_implementada": "categoria_nao_implementada",
    })

    # Toda coleta converge pro mesmo "gerar" — é aqui que os branches por
    # categoria terminam.
    grafo.add_edge("coletar_empresa", "gerar")
    grafo.add_edge("coletar_ponto_turistico", "gerar")
    grafo.add_edge("coletar_cidade", "gerar")
    grafo.add_edge("coletar_terminal_rodoviaria", "gerar")
    # Na prática a exceção sobe antes de chegar no END; a aresta só existe
    # pra o grafo ficar bem-formado (todo nó precisa levar a algum lugar).
    grafo.add_edge("categoria_nao_implementada", END)

    grafo.add_edge("gerar", "humanizar")
    grafo.add_edge("humanizar", "revisor")

    grafo.add_conditional_edges("revisor", _apos_revisor, {
        "aprovado": END,
        "tentar_de_novo": "incrementar_tentativa",
        "esgotado": "marcar_erro",
    })
    grafo.add_edge("incrementar_tentativa", "gerar")
    grafo.add_edge("marcar_erro", END)

    return grafo.compile()


_GRAFO = construir_grafo()


def gerar_descricao_via_grafo(
    tema: str,
    tom: str = "informativo",
    media_palavras: int = 100,
    palavras_chave: list = None,
) -> dict:
    """
    Ponto de entrada único: recebe o tema (e os parâmetros de tom/tamanho/
    palavras-chave) e roda o grafo inteiro. Devolve o state final — o texto
    fica em resultado["texto_humanizado"], ou resultado["erro"] se o
    revisor nunca aprovou dentro do teto de tentativas (ou se a categoria/
    coleta falhar, a exceção original sobe normalmente, sem passar por
    "erro" no state).
    """
    estado_inicial = {
        "tema": tema,
        "tom": tom,
        "media_palavras": media_palavras,
        "palavras_chave": palavras_chave or [],
        "tentativas": 0,
    }
    return _GRAFO.invoke(estado_inicial)


if __name__ == "__main__":
    resultado = gerar_descricao_via_grafo("Expresso JK", tom="vendas", media_palavras=100)
    print(f"categoria: {resultado.get('categoria')}")
    print(f"tentativas: {resultado.get('tentativas')}")
    print(f"revisao: {resultado.get('revisao')}")
    print()
    print(resultado.get("erro") or resultado.get("texto_humanizado"))
