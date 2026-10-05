"""
Grafo LangGraph que dá acabamento à geração de FAQ (mesmo espírito de
formatos/descricao/grafo_descricao.py): coleta a página, gera as perguntas
e respostas, humaniza e revisa — voltando pra geração se algum revisor
reprovar, até um teto de tentativas.

Geração (nó "gerar") muda de estratégia por foco:
  - foco "geral": usa o sistema híbrido de base_empresas_faq.py — parte
    das perguntas vem de um banco pronto (as universais sobre a Buser,
    sem custo de IA), só a parte específica da empresa é gerada, na
    proporção de 1 gerada a cada 6 pedidas.
  - foco "compra"/"regras": 100% gerado por IA, filtrado pelo assunto
    pedido (o banco pronto não serve aqui — ele não cobre "regras").

Existem dois revisores em sequência, barato primeiro:
  1. `revisor` — determinístico (sem LLM): confere se veio a QUANTIDADE de
     perguntas pedida, se nenhuma é "meta" (encaminhamento sem responder
     nada), e (só quando o foco é "compra" ou "regras") se nenhum par
     fugiu do assunto pedido, por palavra-chave.
  2. `revisor_ia` — só roda se o (1) já tiver aprovado. Sempre chama a
     API (mesmo no foco "geral", pra pegar pergunta "meta" parafraseada),
     julgando foco (quando aplicável) e pergunta "meta".

Tem nó de classificação na entrada, igual Descrição — só que lá o "tema"
é um nome livre (classificado por IA, ver interpretador_descricao.py), e
aqui o "tema" É o link (ver transformacaoJson.py: no FAQ não tem campo de
link separado). Por isso a classificação aqui olha a ESTRUTURA da própria
URL (subdomínio próprio vs caminho em www.buser.com.br), não precisa de
IA pra isso — é um sinal bem mais confiável que adivinhar pelo nome.
Só "empresa" tem gerador de FAQ implementado; as outras categorias são
reconhecidas (pra dar um erro claro) mas ainda não geram nada.
"""

import json
import re
from typing import TypedDict
from urllib.parse import urlparse

from langgraph.graph import StateGraph, END

from base_empresas_faq import montar_faq_empresa
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

# Subdomínio próprio (ex: "expressojk.buser.com.br") — página de empresa
# fora de "www.buser.com.br". "www"/"buser" sozinho (o domínio raiz) NUNCA
# é empresa, por isso ficam de fora do grupo capturado abaixo.
PADRAO_SUBDOMINIO_EMPRESA = re.compile(r"^(?!www\.)([a-z0-9-]+)\.buser\.com\.br$")


def classificar_tema_faq(link: str) -> str:
    """Decide a categoria do link observando a URL — mesma ideia do
    classificador de Descrição (ver interpretador_descricao.py), adaptada
    pro fato de que aqui o "tema" é um link, não um nome livre: o sinal
    mais confiável é a ESTRUTURA da própria URL, não precisa de chamada de
    IA pra isso.

    Padrões conhecidos do site da Buser (confirmados ao vivo nesta sessão):
    - "<slug>.buser.com.br" (subdomínio próprio) ou
      "www.buser.com.br/empresas/<slug>" -> "empresa"
    - "www.buser.com.br/destinos/<cidade>-<uf>" -> "cidade"
    - "www.buser.com.br/onibus/..." (rota entre duas cidades) -> "rota"
    - "www.buser.com.br/pontos/..." (ponto de embarque) -> "ponto_embarque"
    - qualquer outra coisa -> "desconhecida"

    Só "empresa" tem gerador de FAQ implementado por enquanto (ver
    _rotear_por_categoria) — as outras ficam reconhecidas, pra dar um erro
    claro, mas ainda não implementado."""
    resultado = urlparse((link or "").strip())
    dominio = resultado.netloc.lower()
    caminho = resultado.path.strip("/")

    if dominio in ("buser.com.br", "www.buser.com.br"):
        primeiro_segmento = caminho.split("/")[0] if caminho else ""
        return {
            "empresas": "empresa",
            "destinos": "cidade",
            "onibus": "rota",
            "pontos": "ponto_embarque",
        }.get(primeiro_segmento, "desconhecida")

    if PADRAO_SUBDOMINIO_EMPRESA.match(dominio):
        return "empresa"

    return "desconhecida"

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

    # depois de classificar_tema_faq
    categoria: str

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

def no_classificar_tema(state: FaqState) -> dict:
    return {"categoria": classificar_tema_faq(state["link"])}


def _rotear_por_categoria(state: FaqState) -> str:
    return "coletar" if state.get("categoria") == "empresa" else "categoria_nao_implementada"


def no_categoria_nao_implementada(state: FaqState) -> dict:
    raise NotImplementedError(
        f"Geração de FAQ pra categoria '{state.get('categoria')}' ainda não "
        f"foi implementada — só empresa tem gerador por enquanto."
    )


def no_coletar(state: FaqState) -> dict:
    resultado = coletar_faq(state["link"])
    return {"fontes": resultado["fontes"]}


def no_gerar(state: FaqState) -> dict:
    foco = (state.get("foco") or "geral").strip().lower()
    fontes = state.get("fontes") or {}

    if foco == "geral":
        # Foco "geral" usa o sistema híbrido de base_empresas_faq.py: parte
        # das perguntas (as universais sobre a Buser — como comprar,
        # cancelar, atendimento etc.) vem de um banco pronto, sem custo de
        # IA; só a parte específica da empresa é gerada, na proporção de 1
        # gerada a cada 6 pedidas (calcular_divisao). Isso só se aplica ao
        # foco "geral": o banco é todo sobre assunto geral/compra, não tem
        # nada de "regras" (bagagem, documento, pet, desconto) — misturar
        # nos outros focos devolveria pergunta fora do assunto pedido.
        resultado = montar_faq_empresa(
            entidade=state["entidade"],
            fontes=fontes,
            quantidade_perguntas=state.get("quantidade_perguntas") or QUANTIDADE_PERGUNTAS_PADRAO,
            palavras_chave=state.get("palavras_chave"),
        )
        perguntas = resultado["perguntas"]
    else:
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
            fontes=fontes,
            tom=foco,
            quantidade_perguntas=state.get("quantidade_perguntas"),
            palavras_chave=state.get("palavras_chave"),
            instrucao_extra=instrucao_extra,
        )
        perguntas = _parsear_perguntas_respostas(texto_bruto)

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

    grafo.add_node("classificar_tema", no_classificar_tema)
    grafo.add_node("categoria_nao_implementada", no_categoria_nao_implementada)
    grafo.add_node("coletar", no_coletar)
    grafo.add_node("gerar", no_gerar)
    grafo.add_node("humanizar", no_humanizar)
    grafo.add_node("revisor", no_revisor)
    grafo.add_node("revisor_ia", no_revisor_ia)
    grafo.add_node("incrementar_tentativa", no_incrementar_tentativa)
    grafo.add_node("marcar_erro", no_marcar_erro)

    grafo.set_entry_point("classificar_tema")

    grafo.add_conditional_edges("classificar_tema", _rotear_por_categoria, {
        "coletar": "coletar",
        "categoria_nao_implementada": "categoria_nao_implementada",
    })
    # Na prática a exceção sobe antes de chegar no END; a aresta só existe
    # pra o grafo ficar bem-formado (todo nó precisa levar a algum lugar) —
    # mesmo padrão de categoria_nao_implementada em grafo_descricao.py.
    grafo.add_edge("categoria_nao_implementada", END)

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
    foco e roda o grafo inteiro. Primeiro classifica a categoria do link
    (ver classificar_tema_faq) — se não for "empresa", a exceção
    NotImplementedError sobe normalmente (mesmo contrato de
    gerar_descricao_via_grafo pra categoria sem coleta implementada),
    quem chama (formatos/gerando.py) já captura e vira "erro" no item.

    Pra categoria "empresa", devolve o state final — a lista final de
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
