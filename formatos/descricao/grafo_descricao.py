"""
Grafo LangGraph que substitui o par interpretador_descricao + interacao_ia_
descricao como ponto de entrada de geração: classifica o tema, roteia pra
coleta certa por categoria, gera, humaniza e revisa o resultado — voltando
pra geração se algum revisor reprovar, até um teto de tentativas.

Só a coleta (e, pra empresa, a classificação de tipo) é ramificada por
categoria. Gerar, humanizar e os dois revisores são nós únicos,
compartilhados por qualquer categoria — o humanizador já funciona assim
hoje (roda pra qualquer descrição, não só empresa), então não faz sentido
duplicar esse trecho por categoria só porque os revisores são novos.

Existem dois revisores em sequência, barato primeiro:
  1. `revisor` — determinístico (sem LLM): palavra banida, contagem de
     palavras, passagem/viagem (só empresa), estrutura de parágrafos (só
     tom vendas). Roda sempre, é de graça.
  2. `revisor_ia` — só roda se o (1) já tiver aprovado. Usa outro invoke
     pra julgar só o TOM do texto (soa como vendas/informativo/promocional
     mesmo?) — não recebe as instruções/template de geração, então não
     tem como reprovar por regra nenhuma que já não seja checável no
     próprio texto lido isoladamente.

Desenho completo (com o motivo de cada decisão) em:
https://claude.ai/code/artifact/29df91fe-b5f2-4d65-81b8-33f7bb445103
"""

import json
from typing import TypedDict

from langgraph.graph import StateGraph, END

from interpretador_descricao import classificar_tema
from base_empresas import coletar_empresa
from base_pontos_turisticos import coletar_ponto_turistico
from base_cidade import coletando_conteudo
from base_rodoviarias import coletar_rodoviaria
from interacao_ia_descricao import gerar_texto_bruto, humanizar_texto, modelo

MAX_TENTATIVAS = 3

# Revisor de IA: só julga o TOM do texto final, lido isoladamente — não
# recebe o template/instruções de geração. As regras de conteúdo (palavra
# banida, passagem/viagem, estrutura de parágrafos) já são checadas pelo
# revisor determinístico; dar o template inteiro pro revisor_ia também fazia
# ele reprovar por interpretação de regras estruturais que não é o papel
# dele julgar (e às vezes de forma equivocada, tipo achar que dois
# parágrafos já separados por linha em branco estavam "misturados").
PROMPT_REVISOR_IA = """Você é um revisor de tom de textos gerados por IA para um site de conteúdo sobre transporte rodoviário (Buser).

Leia o TEXTO FINAL abaixo e diga se o tom dele realmente soa como o tom pedido: "{tom}".

Guia rápido do que cada tom deve soar:
- "vendas": foco em conversão — incentiva a compra/reserva, cita benefícios diretos
- "informativo": neutro e objetivo, sem apelo comercial
- "promocional": envolvente, destaca diferenciais, mas sem apelo de urgência direto

SEJA TOLERANTE: reprove só se o tom estiver claramente errado pra categoria pedida — não é "poderia ser um pouco mais persuasivo" ou achismo de estilo, tem que ser algo que qualquer pessoa lendo reconheceria na hora como o tom errado. Na dúvida, aprove. Não julgue nada além do tom (nem estrutura, nem palavras específicas, nem regras de conteúdo) — isso já é conferido em outra etapa.

TEXTO FINAL:
{texto}

Responda APENAS com um JSON, sem markdown, sem texto adicional, no formato:
{{"tom_ok": true ou false, "motivos": ["motivo 1"]}}
"""

# Lista manual, de propósito (não regex de raiz) — cobre as formas mais
# comuns que já apareceram nos testes; outras conjugações mais raras podem
# passar sem ser pegas, e por ora tá tudo bem.
PALAVRAS_BANIDAS = [
    "memórias inesquecíveis", "não perca"
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

    # revisor determinístico
    revisao: dict  # {"aprovado": bool, "motivos": [str, ...]}
    # revisor de IA (só roda se o determinístico já tiver aprovado) — só
    # julga tom, não recebe as instruções de geração
    revisao_ia: dict  # {"tom_ok": bool, "motivos": [str, ...]}
    tentativas: int
    # motivos da última reprovação (de qualquer um dos dois revisores) —
    # injetado como instrução extra na próxima chamada de "gerar", pra não
    # reamostrar às cegas repetindo o mesmo erro
    motivos_reprovacao: list

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
    instrucao_extra = None
    motivos_reprovacao = state.get("motivos_reprovacao")
    if motivos_reprovacao:
        motivos_str = "; ".join(motivos_reprovacao)
        instrucao_extra = (
            f"ATENÇÃO: a tentativa anterior de gerar este texto foi reprovada "
            f"pelos seguintes motivos: {motivos_str}. Corrija isso especificamente "
            f"nesta nova tentativa, sem repetir o mesmo erro."
        )

    texto = gerar_texto_bruto(
        categoria=state["categoria"],
        entidade=state["entidade"],
        fontes=state["fontes"],
        tom=state.get("tom") or "informativo",
        media_palavras=state.get("media_palavras"),
        palavras_chave=state.get("palavras_chave"),
        classificacao_tipo=state.get("classificacao_tipo"),
        instrucao_extra=instrucao_extra,
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
        limite = media_palavras * 1.5
        if total_palavras > limite:
            motivos.append(f"{total_palavras} palavras, acima do limite de {limite:.0f}")

    paragrafos = [p for p in texto.split("\n\n") if p.strip()]

    classificacao_tipo = state.get("classificacao_tipo")
    if classificacao_tipo and classificacao_tipo["palavra"] == "passagem":
        # Checagem 1 (ampla): "passagem" tem que aparecer em algum lugar do
        # texto. O inverso não dá pra checar assim — "viagem" aparece quase
        # sempre em qualquer texto, mesmo correto, porque "Viagem segura" é
        # um dos 7 diferenciais da Buser permitidos no prompt.
        # "passagens" (plural) não contém "passagem" como substring — o
        # plural em português troca o "m" final por "ns" (passagem ->
        # passagens), não é só adicionar "s". Checar os dois evita reprovar
        # texto que já está certo, só porque usou o plural.
        if "passagem" not in texto_lower and "passagens" not in texto_lower:
            motivos.append(
                'empresa linha regular/híbrida deveria mencionar "passagem" '
                'pelo menos uma vez, só apareceu "viagem"'
            )
        # Checagem 2 (pontual): no tom vendas, o SUBTÍTULO (parágrafo 1) é
        # a frase de compra ("Reserve sua passagem/viagem...") e é onde a
        # regra mais importa — a checagem 1 sozinha deixa passar um texto
        # que erra exatamente aí (usa "viagem" no subtítulo) desde que
        # "passagem" apareça em qualquer outro parágrafo, como aconteceu
        # num teste real desta conversa.
        if state.get("categoria") == "empresa" and state.get("tom") == "vendas" and paragrafos:
            subtitulo = paragrafos[0].lower()
            if "viagem" in subtitulo and "passagem" not in subtitulo and "passagens" not in subtitulo:
                motivos.append(
                    'o subtítulo usa "viagem" em vez de "passagem" — empresa '
                    'linha regular/híbrida deveria usar "passagem" na frase de compra'
                )
    elif classificacao_tipo and classificacao_tipo["tipo"] == "fretamento":
        # Sentido inverso, só pra fretamento PURO (confirmado) — não
        # "ambíguo": empresa ambígua pode legitimamente usar "passagem" se
        # isso vier como palavra-chave pedida (ver gerar_texto_bruto), então
        # reprovar "passagem apareceu" pra ela seria bloquear um caso válido.
        if "passagem" in texto_lower or "passagens" in texto_lower:
            motivos.append(
                'empresa de fretamento puro deveria usar "viagem", mas apareceu "passagem"'
            )
        # Passagem se compra, viagem (fretamento) se reserva — "compra"/
        # "comprar"/"compre" não deveriam aparecer nesse caso, mesmo
        # combinados com "viagem" (ex: "compra de viagens").
        for termo in ("compra", "comprar", "compre"):
            if termo in texto_lower:
                motivos.append(
                    f'empresa de fretamento puro não deveria usar "{termo}" — '
                    f'viagem se reserva/adquire, não se compra'
                )
                break

    # Contagem de parágrafos é específica de cada template de empresa —
    # outras categorias podem ter estruturas de parágrafo completamente
    # diferentes, então essa checagem não pode valer em geral, só pra
    # empresa, e com o número certo pra cada tom.
    if state.get("categoria") == "empresa":
        if state.get("tom") == "vendas" and not (3 <= len(paragrafos) <= 4):
            motivos.append(f"{len(paragrafos)} parágrafos, esperado 3 a 4")
        elif state.get("tom") == "informativo" and len(paragrafos) != 4:
            motivos.append(f"{len(paragrafos)} parágrafos, esperado sempre 4")

    return motivos


def no_revisor(state: DescricaoState) -> dict:
    motivos = _checar_regras(state)
    # Limpa uma avaliação de IA de uma tentativa anterior — sem isso, se
    # esta rodada for reprovada aqui (antes de chegar no revisor_ia de
    # novo), marcar_erro poderia misturar motivos de uma tentativa velha.
    return {"revisao": {"aprovado": not motivos, "motivos": motivos}, "revisao_ia": None}


def no_revisor_ia(state: DescricaoState) -> dict:
    """Só roda depois do revisor determinístico aprovar — barato descarta
    primeiro, a IA só julga o que já passou nas regras de string/contagem.
    Recebe só o texto e o nome do tom, não o template/instruções — isso é
    de propósito: mantém o julgamento restrito a "isso soa como o tom
    pedido?", sem abrir espaço pra reprovar por regra estrutural/de
    conteúdo que já é responsabilidade do revisor determinístico."""
    tom = (state.get("tom") or "informativo").strip().lower()

    prompt = PROMPT_REVISOR_IA.format(tom=tom, texto=state["texto_humanizado"])
    resposta = modelo.invoke(prompt)
    texto_resposta = resposta.content.strip().replace("```json", "").replace("```", "").strip()

    try:
        avaliacao = json.loads(texto_resposta)
    except json.JSONDecodeError:
        # Se a IA não devolver JSON válido, não trava o pipeline num retry
        # infinito por causa de um erro de formatação dela mesma — trata
        # como aprovado (o determinístico já rodou e aprovou antes disso).
        avaliacao = {
            "tom_ok": True,
            "motivos": [f"revisor_ia devolveu resposta não-JSON: {texto_resposta[:200]}"],
        }

    return {"revisao_ia": avaliacao}


def _decidir_retry_ou_esgotado(state: DescricaoState) -> str:
    if state.get("tentativas", 0) + 1 >= MAX_TENTATIVAS:
        return "esgotado"
    return "tentar_de_novo"


def _apos_revisor(state: DescricaoState) -> str:
    if state["revisao"]["aprovado"]:
        return "aprovado"
    return _decidir_retry_ou_esgotado(state)


def _apos_revisor_ia(state: DescricaoState) -> str:
    avaliacao = state["revisao_ia"]
    if avaliacao["tom_ok"]:
        return "aprovado"
    return _decidir_retry_ou_esgotado(state)


def _motivos_da_reprovacao(state: DescricaoState) -> list:
    """Junta os motivos de quem reprovou desta vez — revisor determinístico
    ou revisor_ia, o outro fica vazio/aprovado nesse ponto, então dá pra
    somar os dois sem checar qual foi."""
    motivos = list((state.get("revisao") or {}).get("motivos") or [])
    revisao_ia = state.get("revisao_ia")
    if revisao_ia and not revisao_ia.get("tom_ok"):
        motivos.extend(revisao_ia.get("motivos") or [])
    return motivos


def no_incrementar_tentativa(state: DescricaoState) -> dict:
    return {
        "tentativas": state.get("tentativas", 0) + 1,
        "motivos_reprovacao": _motivos_da_reprovacao(state),
    }


def no_marcar_erro(state: DescricaoState) -> dict:
    motivos = _motivos_da_reprovacao(state)
    motivos_str = "; ".join(motivos) if motivos else "motivo não registrado"
    return {
        "erro": (
            f"Revisor reprovou {MAX_TENTATIVAS}x seguidas e não foi possível "
            f"corrigir: {motivos_str} (texto abaixo é a última versão gerada, "
            f"não passou por todas as checagens)"
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
    grafo.add_node("revisor_ia", no_revisor_ia)
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
        "aprovado": "revisor_ia",
        "tentar_de_novo": "incrementar_tentativa",
        "esgotado": "marcar_erro",
    })
    grafo.add_conditional_edges("revisor_ia", _apos_revisor_ia, {
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
    fica em resultado["texto_humanizado"] mesmo se o revisor nunca aprovou
    dentro do teto de tentativas (nesse caso resultado["erro"] também vem
    preenchido, como aviso de que essa última versão não passou por todas
    as checagens — mas ela ainda é devolvida, em vez de nada). Se a
    categoria/coleta falhar, a exceção original sobe normalmente, sem
    passar por "erro" no state.
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
    print(f"revisao (determinístico): {resultado.get('revisao')}")
    print(f"revisao_ia: {resultado.get('revisao_ia')}")
    print()
    print(resultado.get("erro") or resultado.get("texto_humanizado"))
