"""
Grafo LangGraph que dá acabamento à geração de FAQ (mesmo espírito de
formatos/descricao/grafo_descricao.py): coleta a página, gera as perguntas
e respostas, humaniza e revisa — voltando pra geração se algum revisor
reprovar, até um teto de tentativas.

Existem dois revisores em sequência, barato primeiro:
  1. `revisor` — determinístico (sem LLM): confere se veio a QUANTIDADE de
     perguntas pedida, e (só quando o foco é "compra" ou "regras") se
     nenhum par fugiu do assunto pedido, por palavra-chave.
  2. `revisor_ia` — só roda se o (1) já tiver aprovado, e só de verdade
     quando o foco NÃO é "geral" (foco "geral" não tem assunto pra
     restringir, então nem gasta uma chamada de API julgando isso). Usa
     outro invoke pra julgar semanticamente se as perguntas realmente
     pertencem ao foco pedido — pega paráfrases que o check de palavra-
     chave do revisor determinístico deixa passar.

Diferente de Descrição, aqui não tem categoria/coleta ramificada — o FAQ
sempre recebe o link direto (ver transformacaoJson.py: no FAQ, "tema" É o
link) e coleta do mesmo jeito, então não tem nó de classificação nem
roteamento condicional na entrada.
"""

import json
from typing import TypedDict

from langgraph.graph import StateGraph, END

from base_faq import coletar_faq
from interacao_ia_faq import (
    gerar_faq_bruto,
    humanizar_faq,
    modelo,
    montar_fontes_texto,
    _coletar_faq_existente,
    _parsear_perguntas_respostas,
    QUANTIDADE_PERGUNTAS_PADRAO,
)

MAX_TENTATIVAS = 3

# Palavras que só fazem sentido no foco "regras" (bagagem/documentos/pets/
# descontos/embarque) — se aparecerem numa pergunta ou resposta gerada com
# foco "compra", é sinal de que o par fugiu do assunto pedido (mesma lista
# de exclusão descrita nos templates de prompts_faq.json).
#
# NÃO inclui a palavra solta "embarque": testado ao vivo, ela aparece o
# tempo todo em respostas de COMPRA só pra marcar prazo ("cancele até 3
# horas antes do embarque") — reprovava um FAQ correto 3x seguidas por
# causa disso. "regras de embarque" (a frase completa) é bem mais
# específica do assunto de verdade, sem esse falso positivo.
PALAVRAS_TEMA_REGRAS = [
    "bagagem", "mala", "documento", "pet", "animal de estimação",
    "desconto", "gratuidade", "pcd", "idoso", "id jovem", "regras de embarque",
]

# Palavras que só fazem sentido no foco "compra" (comprar/reservar/pagar/
# cancelar/remarcar) — se aparecerem num par gerado com foco "regras", é
# sinal de que fugiu do assunto pedido.
PALAVRAS_TEMA_COMPRA = [
    "comprar", "compra", "reservar", "reserva", "pagamento", "pagar",
    "remarca", "cancelamento", "cancelar", "confiável", "confiavel",
    "segura", "segurança", "pix", "cartão", "boleto",
]

# Perguntas "meta" (sobre onde tirar dúvida, como entrar em contato, quais
# os canais de atendimento) não são FAQ de verdade — são só encaminhamento
# pra outro lugar, sem responder nada. Testado ao vivo: o modelo cria uma
# dessas quando pede mais perguntas do que sobra assunto real pra cobrir.
# Só olha a PERGUNTA (não a resposta) — mesmo motivo das listas de foco:
# checar a resposta pegaria menção legítima tipo "se tiver dúvida sobre a
# bagagem, é só perguntar ao motorista" dentro de uma resposta que já é uma
# pergunta de verdade sobre outro assunto.
FRASES_PERGUNTA_META = [
    "tirar dúvidas", "tirar duvidas", "tirar dúvida", "tirar duvida",
    "entrar em contato", "entro em contato", "como entrar em contato",
    "canais de atendimento", "canal de atendimento", "fale conosco",
    "onde posso obter mais informações", "onde encontro mais informações",
]


def _perguntas_meta(perguntas: list) -> list:
    return [
        item["pergunta"] for item in perguntas
        if any(frase in item["pergunta"].lower() for frase in FRASES_PERGUNTA_META)
    ]


FOCO_DESCRICAO_CURTA = {
    "geral": "sem restrição de assunto — qualquer pergunta relacionada à empresa/Buser vale",
    "compra": (
        "só compra, reserva, pagamento, remarcação, cancelamento e "
        "confiabilidade da compra pela Buser — NADA de bagagem, "
        "documentos, pets ou descontos/gratuidade"
    ),
    "regras": (
        "só bagagem, documentos exigidos, transporte de pets, descontos/"
        "gratuidade (PCD, idoso, ID Jovem) e regras de embarque — NADA de "
        "comprar, pagar, cancelar ou remarcar"
    ),
}

# O revisor determinístico já pega as frases "meta" mais óbvias por
# palavra-chave (ver FRASES_PERGUNTA_META), mas testado ao vivo: o modelo
# encontra paráfrase que não bate com nenhuma palavra da lista (ex: "o que
# devo fazer se minha dúvida não estiver nesta lista?" — mesmo problema,
# texto diferente). Por isso o revisor_ia SEMPRE roda, mesmo no foco
# "geral" (que não tem assunto pra restringir) — e sempre checa as duas
# coisas: foco (quando houver) e pergunta "meta" (sempre, não importa o
# foco).
PROMPT_REVISOR_IA = """Você é um revisor de FAQs gerados por IA para um site de transporte rodoviário (Buser).

Leia as perguntas e respostas abaixo e avalie DUAS coisas:

1. FOCO: elas realmente pertencem ao foco pedido: "{foco}"? O que esse foco cobre: {foco_descricao}
2. PERGUNTA "META": alguma pergunta é sobre onde tirar dúvida, como entrar em contato, ou só encaminha o leitor pra outro canal/site em vez de responder de verdade (ex: "o que fazer se minha dúvida não estiver aqui?", "onde posso saber mais?", "quais os canais de atendimento?")? Isso NUNCA é uma pergunta de FAQ válida, não importa o foco — reprove se achar qualquer uma assim.

SEJA TOLERANTE no item 1: reprove só se alguma pergunta claramente fugir do foco — não é achismo de assunto correlato, tem que ser algo que qualquer pessoa lendo reconheceria na hora como fora do que foi pedido. Na dúvida quanto ao FOCO, aprove — mas no item 2 (pergunta "meta"), qualquer pergunta desse tipo reprova, sem exceção. Não julgue mais nada além desses dois pontos (nem quantidade, nem qualidade de escrita) — isso já é conferido em outra etapa.

PERGUNTAS E RESPOSTAS:
{texto_faq}

Responda APENAS com um JSON, sem markdown, sem texto adicional, no formato:
{{"foco_ok": true ou false, "motivos": ["motivo 1"]}}
"""


class FaqState(TypedDict, total=False):
    # entrada
    link: str
    entidade: str
    foco: str
    quantidade_perguntas: int
    palavras_chave: list

    # coleta
    fontes: dict

    # geração / humanização
    perguntas_geradas: list
    perguntas_humanizadas: list
    sem_fontes: bool

    # revisor determinístico
    revisao: dict  # {"aprovado": bool, "motivos": [str, ...]}
    # revisor de IA (só roda se o determinístico já tiver aprovado)
    revisao_ia: dict  # {"foco_ok": bool, "motivos": [str, ...]}
    tentativas: int
    motivos_reprovacao: list

    # saída
    erro: str


# ---------------------------------------------------------------------------
# Nós
# ---------------------------------------------------------------------------

def no_coletar(state: FaqState) -> dict:
    resultado = coletar_faq(state["link"])
    return {"fontes": resultado["fontes"]}


def no_gerar(state: FaqState) -> dict:
    instrucao_extra = None
    motivos_reprovacao = state.get("motivos_reprovacao")
    if motivos_reprovacao:
        motivos_str = "; ".join(motivos_reprovacao)
        instrucao_extra = (
            f"ATENÇÃO: a tentativa anterior de gerar este FAQ foi reprovada "
            f"pelos seguintes motivos: {motivos_str}. Corrija isso "
            f"especificamente nesta nova tentativa, sem repetir o mesmo erro."
        )

    texto_bruto = gerar_faq_bruto(
        entidade=state["entidade"],
        fontes=state["fontes"],
        tom=state.get("foco") or "geral",
        quantidade_perguntas=state.get("quantidade_perguntas"),
        palavras_chave=state.get("palavras_chave"),
        instrucao_extra=instrucao_extra,
    )
    perguntas = _parsear_perguntas_respostas(texto_bruto)

    fontes = state.get("fontes") or {}
    sem_fontes = not montar_fontes_texto(fontes) and not _coletar_faq_existente(fontes)

    return {"perguntas_geradas": perguntas, "sem_fontes": sem_fontes}


def no_humanizar(state: FaqState) -> dict:
    perguntas = humanizar_faq(state["perguntas_geradas"], foco=state.get("foco") or "geral")
    return {"perguntas_humanizadas": perguntas}


def _checar_regras(state: FaqState) -> list:
    """Checagens determinísticas (sem LLM): quantidade de perguntas certa,
    e (só pra foco "compra"/"regras") nenhum par falando do assunto do
    OUTRO foco. Foco "geral" não tem restrição de assunto nenhuma."""
    perguntas = state.get("perguntas_humanizadas") or []
    motivos = []

    quantidade_pedida = state.get("quantidade_perguntas")
    if quantidade_pedida and len(perguntas) != quantidade_pedida:
        motivos.append(
            f"{len(perguntas)} pergunta(s) geradas, esperado exatamente {quantidade_pedida}"
        )

    foco = (state.get("foco") or "geral").strip().lower()
    palavras_proibidas = {
        "compra": PALAVRAS_TEMA_REGRAS,
        "regras": PALAVRAS_TEMA_COMPRA,
    }.get(foco)

    if palavras_proibidas:
        # Só olha o texto da PERGUNTA, não a resposta — testado ao vivo: a
        # palavra proibida quase sempre aparece na resposta por menção
        # incidental (ex: "pagamento da bagagem extra" numa pergunta de
        # regras, "cartão do Passe Livre" numa resposta sobre gratuidade),
        # nunca indicando que o PAR fugiu do assunto de verdade — só a
        # pergunta em si é um sinal confiável do tema pedido.
        for item in perguntas:
            texto = item["pergunta"].lower()
            achadas = [palavra for palavra in palavras_proibidas if palavra in texto]
            if achadas:
                motivos.append(
                    f'pergunta "{item["pergunta"]}" foge do foco \'{foco}\' '
                    f'(fala de {", ".join(achadas)})'
                )

    # Roda pra qualquer foco (geral/compra/regras) — pergunta "meta" nunca
    # é FAQ de verdade, não importa o assunto.
    for pergunta_meta in _perguntas_meta(perguntas):
        motivos.append(
            f'pergunta "{pergunta_meta}" é uma pergunta "meta" (só encaminha '
            f'pra outro canal, não responde nada) — não é FAQ de verdade'
        )

    return motivos


def no_revisor(state: FaqState) -> dict:
    motivos = _checar_regras(state)
    # Limpa uma avaliação de IA de uma tentativa anterior — mesmo cuidado
    # de grafo_descricao.py: sem isso, uma reprovação aqui poderia misturar
    # motivos de uma rodada velha do revisor_ia.
    return {"revisao": {"aprovado": not motivos, "motivos": motivos}, "revisao_ia": None}


def no_revisor_ia(state: FaqState) -> dict:
    """Só roda depois do revisor determinístico aprovar. SEMPRE chama a
    API, mesmo no foco "geral" (que não tem assunto pra restringir) —
    ainda tem uma coisa importante pra julgar em qualquer foco: pergunta
    "meta" que virou paráfrase e passou batido pelo revisor determinístico
    (ver comentário de PROMPT_REVISOR_IA)."""
    foco = (state.get("foco") or "geral").strip().lower()
    perguntas = state.get("perguntas_humanizadas") or []
    texto_faq = "\n\n".join(f"P: {p['pergunta']}\nR: {p['resposta']}" for p in perguntas)

    prompt = PROMPT_REVISOR_IA.format(
        foco=foco,
        foco_descricao=FOCO_DESCRICAO_CURTA.get(foco, "sem restrição de assunto conhecida"),
        texto_faq=texto_faq,
    )
    resposta = modelo.invoke(prompt)
    texto_resposta = resposta.content.strip().replace("```json", "").replace("```", "").strip()

    try:
        avaliacao = json.loads(texto_resposta)
    except json.JSONDecodeError:
        # Mesmo fallback de grafo_descricao.py: resposta não-JSON da IA não
        # deveria travar o pipeline num retry por um erro que é dela mesma
        # — trata como aprovado (o determinístico já rodou e aprovou antes).
        avaliacao = {
            "foco_ok": True,
            "motivos": [f"revisor_ia devolveu resposta não-JSON: {texto_resposta[:200]}"],
        }

    return {"revisao_ia": avaliacao}


def _decidir_retry_ou_esgotado(state: FaqState) -> str:
    if state.get("tentativas", 0) + 1 >= MAX_TENTATIVAS:
        return "esgotado"
    return "tentar_de_novo"


def _apos_revisor(state: FaqState) -> str:
    if state["revisao"]["aprovado"]:
        return "aprovado"
    return _decidir_retry_ou_esgotado(state)


def _apos_revisor_ia(state: FaqState) -> str:
    if state["revisao_ia"]["foco_ok"]:
        return "aprovado"
    return _decidir_retry_ou_esgotado(state)


def _motivos_da_reprovacao(state: FaqState) -> list:
    motivos = list((state.get("revisao") or {}).get("motivos") or [])
    revisao_ia = state.get("revisao_ia")
    if revisao_ia and not revisao_ia.get("foco_ok"):
        motivos.extend(revisao_ia.get("motivos") or [])
    return motivos


def no_incrementar_tentativa(state: FaqState) -> dict:
    return {
        "tentativas": state.get("tentativas", 0) + 1,
        "motivos_reprovacao": _motivos_da_reprovacao(state),
    }


def no_marcar_erro(state: FaqState) -> dict:
    motivos = _motivos_da_reprovacao(state)
    motivos_str = "; ".join(motivos) if motivos else "motivo não registrado"
    return {
        "erro": (
            f"Revisor reprovou {MAX_TENTATIVAS}x seguidas e não foi possível "
            f"corrigir: {motivos_str} (FAQ abaixo é a última versão gerada, "
            f"não passou por todas as checagens)"
        )
    }


# ---------------------------------------------------------------------------
# Montagem do grafo
# ---------------------------------------------------------------------------

def construir_grafo():
    grafo = StateGraph(FaqState)

    grafo.add_node("coletar", no_coletar)
    grafo.add_node("gerar", no_gerar)
    grafo.add_node("humanizar", no_humanizar)
    grafo.add_node("revisor", no_revisor)
    grafo.add_node("revisor_ia", no_revisor_ia)
    grafo.add_node("incrementar_tentativa", no_incrementar_tentativa)
    grafo.add_node("marcar_erro", no_marcar_erro)

    grafo.set_entry_point("coletar")

    grafo.add_edge("coletar", "gerar")
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


def gerar_faq_via_grafo(
    link: str,
    entidade: str,
    foco: str = "geral",
    quantidade_perguntas: int = None,
    palavras_chave: list = None,
) -> dict:
    """
    Ponto de entrada único: recebe o link, o nome de exibição da empresa, o
    foco e roda o grafo inteiro. Devolve o state final — a lista final de
    perguntas/respostas fica em resultado["perguntas_humanizadas"] mesmo se
    o revisor nunca aprovou dentro do teto de tentativas (nesse caso
    resultado["erro"] também vem preenchido, como aviso de que essa última
    versão não passou por todas as checagens — mas ela ainda é devolvida,
    em vez de nada).
    """
    estado_inicial = {
        "link": link,
        "entidade": entidade,
        "foco": (foco or "geral").strip().lower(),
        "quantidade_perguntas": quantidade_perguntas or QUANTIDADE_PERGUNTAS_PADRAO,
        "palavras_chave": palavras_chave or [],
        "tentativas": 0,
    }
    return _GRAFO.invoke(estado_inicial)


if __name__ == "__main__":
    import sys

    resultado = gerar_faq_via_grafo(
        link=sys.argv[1] if len(sys.argv) > 1 else "https://expressojk.buser.com.br/",
        entidade=sys.argv[2] if len(sys.argv) > 2 else "Expresso JK",
        foco=sys.argv[3] if len(sys.argv) > 3 else "geral",
        quantidade_perguntas=6,
    )
    print(f"tentativas: {resultado.get('tentativas')}")
    print(f"revisao (determinístico): {resultado.get('revisao')}")
    print(f"revisao_ia: {resultado.get('revisao_ia')}")
    print(f"erro: {resultado.get('erro')}")
    print()
    for par in resultado.get("perguntas_humanizadas") or []:
        print(f"P: {par['pergunta']}\nR: {par['resposta']}\n")
