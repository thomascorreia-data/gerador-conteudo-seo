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
    módulo de interação com a IA, sem acoplar um no outro."""
    blocos = []
    for nome_fonte, dados in fontes.items():
        if dados.get("erro"):
            continue
        if dados.get("paragrafos"):
            texto = " ".join(dados["paragrafos"])
        elif dados.get("conteudo"):
            texto = dados["conteudo"]
        else:
            continue
        blocos.append(f"[{nome_fonte}]\n{texto}")
    return "\n\n".join(blocos)


def gerar_faq_bruto(
    entidade: str,
    fontes: dict,
    tom: str = "informativo",
    quantidade_perguntas: int = None,
    palavras_chave: list = None,
    instrucao_extra: str = None,
) -> str:
    """
    Monta o prompt certo (tom) a partir de prompts_faq.json e chama o
    modelo. Devolve a resposta bruta (texto que DEVERIA ser um JSON de
    lista de perguntas/respostas, mas ainda não parseado) — quem chama
    decide o que fazer se vier mal formado, igual ao revisor_ia do grafo de
    descrição já faz hoje.
    """
    tom_normalizado = (tom or "informativo").strip().lower()
    dados_tom = PROMPTS_FAQ.get(tom_normalizado)
    if not dados_tom or not dados_tom.get("template"):
        raise NotImplementedError(
            f"Prompt de FAQ para o tom '{tom}' ainda não foi cadastrado em prompts_faq.json"
        )

    fontes_texto = montar_fontes_texto(fontes)
    sem_fontes = not fontes_texto
    if sem_fontes:
        # Mesmo fallback já usado em todas as categorias de Descrição: em
        # vez de travar a geração porque a página não respondeu ou não
        # trouxe conteúdo, deixa o modelo escrever com o que ele já sabe
        # sobre o assunto — sinalizado de volta pra quem chamar (ver
        # gerar_faq() mais abaixo) pra saber que isso não foi verificado
        # contra fonte real nenhuma.
        fontes_texto = (
            f"(nenhuma fonte real foi coletada sobre {entidade} — a página "
            f"não respondeu ou não trouxe conteúdo aproveitável)"
        )

    prompt = dados_tom["template"].format(
        entidade=entidade,
        fontes_texto=fontes_texto,
        quantidade_perguntas=quantidade_perguntas or QUANTIDADE_PERGUNTAS_PADRAO,
    )

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
    tom: str = "informativo",
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

    return {
        "link": link,
        "entidade": entidade,
        "sem_fontes": not montar_fontes_texto(fontes),
        "perguntas": _parsear_perguntas_respostas(texto_bruto),
        "texto_bruto": texto_bruto,
    }


if __name__ == "__main__":
    resultado = gerar_faq(
        link="https://expressojk.buser.com.br/",
        entidade="Expresso JK",
        tom="informativo",
        quantidade_perguntas=5,
    )
    print(f"sem_fontes: {resultado['sem_fontes']}")
    for par in resultado["perguntas"]:
        print(f"\nP: {par['pergunta']}\nR: {par['resposta']}")
