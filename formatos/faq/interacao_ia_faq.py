"""
Gera as perguntas e respostas do FAQ a partir do conteúdo coletado por
base_faq.py. Mesmo padrão de formatos/descricao/interacao_ia_descricao.py
(prompt por tom, carregado de um .json, fallback quando não há fonte), só
que a saída aqui é uma LISTA de perguntas e respostas em JSON, não um texto
corrido — combinado com o usuário: código valida a contagem/formato, a IA
não precisa (nem deve) se autopoliciar nisso enquanto escreve.
"""

import json
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from base_faq import coletar_faq

load_dotenv()

if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError(
        "OPENAI_API_KEY não encontrada. Confira se o arquivo .env existe "
        "na raiz do projeto e tem a linha OPENAI_API_KEY=sk-..."
    )

modelo = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

CAMINHO_PROMPTS = os.path.join(os.path.dirname(__file__), "prompts_faq.json")

with open(CAMINHO_PROMPTS, encoding="utf-8") as arquivo:
    PROMPTS_FAQ = json.load(arquivo)

QUANTIDADE_PERGUNTAS_PADRAO = 5


def montar_fontes_texto(fontes: dict) -> str:
    """Mesma lógica de interacao_ia_descricao.py: junta o conteúdo de cada
    fonte (ignorando erro/vazio) num só bloco de texto pro prompt. Duplicada
    aqui de propósito — cada formato (descrição, FAQ, ...) tem seu próprio
    módulo de interação com a IA, sem acoplar um no outro.

    NÃO inclui o "faq" real que base_faq.py pode ter coletado (schema.org) —
    esse vira seu próprio bloco (ver _formatar_faq_existente), usado só no
    prompt "com_faq". Aqui entram só descrição/conteúdo genérico, que servem
    de contexto pros dois prompts (com e sem FAQ existente)."""
    blocos = []
    for nome_fonte, dados in fontes.items():
        if dados.get("erro"):
            continue
        partes = []
        if dados.get("descricao"):
            partes.append(dados["descricao"])
        if dados.get("paragrafos"):
            partes.append(" ".join(dados["paragrafos"]))
        elif dados.get("conteudo"):
            partes.append(dados["conteudo"])
        if not partes:
            continue
        blocos.append(f"[{nome_fonte}]\n" + "\n\n".join(partes))
    return "\n\n".join(blocos)


def _coletar_faq_existente(fontes: dict) -> list:
    """Junta o "faq" real (schema.org, coletado por base_faq.py) de todas as
    fontes que tiverem — hoje só existe "Pagina", mas escrito de forma
    genérica igual montar_fontes_texto, caso outra fonte apareça no futuro."""
    faq = []
    for dados in fontes.values():
        if dados.get("erro"):
            continue
        faq.extend(dados.get("faq") or [])
    return faq


def _formatar_faq_existente(faq: list) -> str:
    """Formata a lista de pergunta/resposta real como texto legível pro
    prompt "com_faq" — mesmo padrão P:/R: usado no __main__ deste módulo."""
    return "\n\n".join(f"P: {item['pergunta']}\nR: {item['resposta']}" for item in faq)


def gerar_faq_bruto(
    entidade: str,
    fontes: dict,
    tom: str = "geral",
    quantidade_perguntas: int = None,
    palavras_chave: list = None,
    instrucao_extra: str = None,
) -> str:
    """
    Monta o prompt certo (foco x variante) a partir de prompts_faq.json e
    chama o modelo. Devolve a resposta bruta (texto que DEVERIA ser um JSON
    de lista de perguntas/respostas, mas ainda não parseado) — quem chama
    decide o que fazer se vier mal formado, igual ao revisor_ia do grafo de
    descrição já faz hoje.

    O parâmetro "tom" aqui não controla VOZ (informativo/vendas/promocional,
    como em Descrição) — controla FOCO DE ASSUNTO: "geral" (sem filtro),
    "compra" (só compra/reserva/pagamento/cancelamento) ou "regras" (só
    bagagem/documentos/pets/descontos/embarque). Decisão tomada em conjunto
    com o usuário: boa parte das perguntas de FAQ é inerentemente factual
    (ex: "posso levar pet?" não muda de resposta com tom de venda), então
    filtrar por ASSUNTO rende um controle mais útil que filtrar por VOZ —
    ver a discussão registrada no histórico do projeto. Mantido o nome do
    parâmetro ("tom") por ser o mesmo campo genérico que todo formato recebe
    de transformacaoJson.py, só a interpretação muda aqui dentro do módulo
    de FAQ.

    Duas variantes de prompt por foco, escolhidas automaticamente:
    - "com_faq": a página já tinha um FAQ real coletado (schema.org, ver
      base_faq.py) — o modelo REESCREVE esses pares (filtrando pelo foco
      pedido), em vez de inventar perguntas do zero. Grounding mais forte
      (dado real, pronto), risco menor de o FAQ gerado divergir do que já
      está publicado.
    - "sem_faq": não tinha FAQ nenhum coletado — gera do zero a partir da
      descrição/conteúdo genérico, já filtrando pelo foco pedido.
    """
    tom_normalizado = (tom or "geral").strip().lower()
    dados_tom = PROMPTS_FAQ.get(tom_normalizado)
    if not dados_tom:
        raise NotImplementedError(
            f"Prompt de FAQ para o foco '{tom}' ainda não foi cadastrado em prompts_faq.json"
        )

    faq_existente = _coletar_faq_existente(fontes)
    variante = "com_faq" if faq_existente else "sem_faq"
    dados_variante = dados_tom.get(variante)
    if not dados_variante or not dados_variante.get("template"):
        raise NotImplementedError(
            f"Prompt de FAQ ({variante}) para o foco '{tom}' ainda não foi cadastrado em prompts_faq.json"
        )

    fontes_texto = montar_fontes_texto(fontes)
    # "sem fontes" de verdade só quando não tem NEM conteúdo genérico NEM
    # FAQ real — com faq_existente já é grounding suficiente, mesmo que
    # descrição/conteúdo tenham vindo vazios.
    sem_fontes = not fontes_texto and not faq_existente
    if not fontes_texto:
        # Mesmo fallback já usado em todas as categorias de Descrição: em
        # vez de travar a geração porque a página não respondeu ou não
        # trouxe conteúdo, deixa o modelo escrever com o que ele já sabe
        # (ou só com o faq_existente, se houver) — sinalizado de volta pra
        # quem chamar (ver gerar_faq() mais abaixo) quando for realmente
        # "sem_fontes" (nem isso).
        fontes_texto = (
            f"(nenhum conteúdo genérico adicional foi coletado sobre {entidade})"
            if faq_existente else
            f"(nenhuma fonte real foi coletada sobre {entidade} — a página "
            f"não respondeu ou não trouxe conteúdo aproveitável)"
        )

    kwargs_formato = dict(
        entidade=entidade,
        fontes_texto=fontes_texto,
        quantidade_perguntas=quantidade_perguntas or QUANTIDADE_PERGUNTAS_PADRAO,
    )
    if variante == "com_faq":
        kwargs_formato["faq_existente_texto"] = _formatar_faq_existente(faq_existente)

    prompt = dados_variante["template"].format(**kwargs_formato)

    if palavras_chave:
        prompt += (
            "\n\nInclua de forma natural, sem forçar, as seguintes palavras-chave: "
            + ", ".join(palavras_chave)
            + "."
        )

    if sem_fontes:
        prompt += (
            f"\n\nATENÇÃO: não foi possível coletar nenhum conteúdo real sobre "
            f"{entidade}. As instruções acima que pedem pra basear tudo no "
            f"conteúdo coletado NÃO se aplicam aqui, porque não há conteúdo "
            f"nenhum. Em vez disso, gere perguntas e respostas genéricas com "
            f"base no que você já sabe sobre esse assunto — evite datas, "
            f"números e detalhes muito específicos que você não tenha certeza "
            f"absoluta de estarem corretos, e não mencione em nenhum momento "
            f"que faltam fontes ou que a informação é incerta."
        )

    if instrucao_extra:
        # Fica por último de propósito, mesmo motivo do módulo de Descrição:
        # é a última coisa que o modelo lê antes de escrever.
        prompt += f"\n\n{instrucao_extra}"

    resposta = modelo.invoke(prompt)
    return resposta.content.strip()


def _parsear_perguntas_respostas(texto_resposta: str) -> list:
    """Tenta interpretar a resposta do modelo como a lista de
    pergunta/resposta pedida no prompt. Nunca levanta exceção — se vier mal
    formado (JSON quebrado, não é lista, item sem os dois campos), devolve
    lista vazia em vez de propagar o erro pra quem chamou."""
    texto_limpo = texto_resposta.strip().replace("```json", "").replace("```", "").strip()

    try:
        dados = json.loads(texto_limpo)
    except json.JSONDecodeError:
        return []

    if not isinstance(dados, list):
        return []

    return [
        {"pergunta": item["pergunta"].strip(), "resposta": item["resposta"].strip()}
        for item in dados
        if isinstance(item, dict) and item.get("pergunta") and item.get("resposta")
    ]


def gerar_faq(
    link: str,
    entidade: str,
    tom: str = "geral",
    quantidade_perguntas: int = QUANTIDADE_PERGUNTAS_PADRAO,
    palavras_chave: list = None,
) -> dict:
    """
    Ponto de entrada simples pra testar coleta + geração juntas de ponta a
    ponta. Ainda NÃO é o pipeline final (isso viria de um grafo próprio,
    nos moldes de formatos/descricao/grafo_descricao.py, com humanização e
    revisor) — só valida se o que foi coletado gera um FAQ que faz sentido.
    """
    resultado_coleta = coletar_faq(link)
    fontes = resultado_coleta["fontes"]

    texto_bruto = gerar_faq_bruto(
        entidade=entidade,
        fontes=fontes,
        tom=tom,
        quantidade_perguntas=quantidade_perguntas,
        palavras_chave=palavras_chave,
    )

    faq_existente = _coletar_faq_existente(fontes)
    return {
        "link": link,
        "entidade": entidade,
        "variante_usada": "com_faq" if faq_existente else "sem_faq",
        "sem_fontes": not montar_fontes_texto(fontes) and not faq_existente,
        "perguntas": _parsear_perguntas_respostas(texto_bruto),
        "texto_bruto": texto_bruto,
    }


if __name__ == "__main__":
    import sys

    resultado = gerar_faq(
        link=sys.argv[1] if len(sys.argv) > 1 else "https://expressojk.buser.com.br/",
        entidade=sys.argv[2] if len(sys.argv) > 2 else "Expresso JK",
        tom=sys.argv[3] if len(sys.argv) > 3 else "geral",
        quantidade_perguntas=5,
    )
    print(f"variante_usada: {resultado['variante_usada']}")
    print(f"sem_fontes: {resultado['sem_fontes']}")
    for par in resultado["perguntas"]:
        print(f"\nP: {par['pergunta']}\nR: {par['resposta']}")
