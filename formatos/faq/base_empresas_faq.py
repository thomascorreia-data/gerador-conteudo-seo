"""
Regra específica de FAQ para EMPRESA: parte das perguntas vem de um banco
pronto (universal, sobre a Buser — mesma resposta pra qualquer empresa),
parte é gerada com o conteúdo real coletado daquela empresa (base_faq.py).

Por quê: testado ao vivo, pergunta tipo "quando a empresa foi fundada?" não
ajuda ninguém a decidir/comprar — é biografia, não FAQ (isso já é coberto
pelo formato Descrição). E pergunta sobre política específica (pet, bagagem,
documento) não pode ser inventada pra empresa sem essa informação coletada
— informação errada aí pode complicar a viagem de alguém de verdade. Então:
- O que é universal (sempre verdade, qualquer empresa) vira banco pronto,
  sem custo de IA nenhum.
- O que depende de fato específico da empresa é gerado, só com o que foi
  coletado de verdade (base_faq.coletar_faq) — nunca inventado; e só entra
  política específica se a empresa tiver um FAQ real coletado (schema.org).

Proporção: 1 pergunta gerada a cada 6 pedidas (arredondando pra cima), o
resto vem do banco pronto. Ex: 5 -> 1 gerada + 4 do banco; 6 -> 1 gerada +
5 do banco; 7 -> 2 geradas + 5 do banco; 12 -> 2 geradas + 10 do banco;
13 -> 3 geradas + 10 do banco.

Funções de fontes ("montar_fontes_texto" etc.) duplicadas de propósito de
interacao_ia_faq.py — mesmo padrão já usado no projeto: cada módulo de
interação com a IA fica autocontido, sem acoplar um no outro.
"""

import json
import os
import random

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError(
        "OPENAI_API_KEY não encontrada. Confira se o arquivo .env existe "
        "na raiz do projeto e tem a linha OPENAI_API_KEY=sk-..."
    )

modelo = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

CAMINHO_PROMPTS = os.path.join(os.path.dirname(__file__), "prompts_faq_empresas.json")

with open(CAMINHO_PROMPTS, encoding="utf-8") as arquivo:
    DADOS_EMPRESA = json.load(arquivo)

PERGUNTAS_PRONTAS = DADOS_EMPRESA["perguntas_prontas"]

QUANTIDADE_POR_GERADA = 6  # 1 pergunta gerada a cada N pedidas


def calcular_divisao(quantidade_perguntas: int) -> tuple:
    """Devolve (quantidade_gerada, quantidade_lista). 1 gerada a cada 6
    perguntas pedidas (arredondando pra cima): 5 e 6 -> 1; 7 a 12 -> 2;
    13 a 18 -> 3; e assim por diante. Nunca pede mais geradas do que o
    total (guarda pro caso de quantidade_perguntas vir 0 ou negativa)."""
    if quantidade_perguntas < 1:
        return 0, 0
    quantidade_gerada = (quantidade_perguntas - 1) // QUANTIDADE_POR_GERADA + 1
    quantidade_gerada = min(quantidade_gerada, quantidade_perguntas)
    return quantidade_gerada, quantidade_perguntas - quantidade_gerada


def sortear_da_lista(entidade: str, quantidade: int) -> list:
    """Sorteia `quantidade` perguntas do banco pronto (sem repetir dentro do
    mesmo sorteio), já substituindo {entidade} no texto. Se pedir mais do
    que o banco tem, devolve o banco inteiro (não repete pergunta)."""
    if quantidade <= 0:
        return []
    quantidade = min(quantidade, len(PERGUNTAS_PRONTAS))
    escolhidas = random.sample(PERGUNTAS_PRONTAS, quantidade)
    return [
        {
            "pergunta": item["pergunta"].format(entidade=entidade),
            "resposta": item["resposta"].format(entidade=entidade),
        }
        for item in escolhidas
    ]


def _montar_fontes_texto(fontes: dict) -> str:
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
    faq = []
    for dados in fontes.values():
        if dados.get("erro"):
            continue
        faq.extend(dados.get("faq") or [])
    return faq


def _formatar_faq_existente(faq: list) -> str:
    return "\n\n".join(f"P: {item['pergunta']}\nR: {item['resposta']}" for item in faq)


def _parsear_perguntas_respostas(texto_resposta: str) -> list:
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


def _gerar_dinamicas(
    entidade: str,
    fontes: dict,
    quantidade_gerada: int,
    perguntas_ja_usadas: list,
    palavras_chave: list = None,
) -> list:
    """Gera as perguntas complementares (a parte que NÃO vem do banco
    pronto), grounded no que foi coletado de verdade sobre a empresa."""
    if quantidade_gerada <= 0:
        return []

    faq_existente = _coletar_faq_existente(fontes)
    variante = "com_faq" if faq_existente else "sem_faq"
    dados_variante = DADOS_EMPRESA["geracao"][variante]

    fontes_texto = _montar_fontes_texto(fontes)
    if not fontes_texto:
        fontes_texto = (
            f"(nenhum conteúdo genérico adicional foi coletado sobre {entidade})"
        )

    perguntas_evitar_texto = "\n".join(f"- {p}" for p in perguntas_ja_usadas) or "(nenhuma)"

    kwargs_formato = dict(
        entidade=entidade,
        fontes_texto=fontes_texto,
        quantidade_perguntas=quantidade_gerada,
        perguntas_evitar=perguntas_evitar_texto,
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

    resposta = modelo.invoke(prompt)
    return _parsear_perguntas_respostas(resposta.content.strip())


def montar_faq_empresa(
    entidade: str,
    fontes: dict,
    quantidade_perguntas: int,
    palavras_chave: list = None,
) -> dict:
    """
    Ponto de entrada: monta a lista final de perguntas/respostas pra uma
    empresa, misturando banco pronto + geração dinâmica na proporção certa
    (ver calcular_divisao) e embaralhando a ordem final, pra não ficar
    sempre "as do banco primeiro, a gerada por último".
    """
    quantidade_gerada, quantidade_lista = calcular_divisao(quantidade_perguntas)

    # O banco tem um tamanho fixo (hoje 10) — se pedir mais do que ele tem
    # disponível, o que faltar vira geração extra em vez de devolver menos
    # perguntas do que foi pedido.
    if quantidade_lista > len(PERGUNTAS_PRONTAS):
        excedente = quantidade_lista - len(PERGUNTAS_PRONTAS)
        quantidade_lista = len(PERGUNTAS_PRONTAS)
        quantidade_gerada += excedente

    do_banco = sortear_da_lista(entidade, quantidade_lista)
    perguntas_ja_usadas = [item["pergunta"] for item in do_banco]

    geradas = _gerar_dinamicas(entidade, fontes, quantidade_gerada, perguntas_ja_usadas, palavras_chave)

    todas = do_banco + geradas
    random.shuffle(todas)

    return {
        "perguntas": todas,
        "quantidade_pedida": quantidade_perguntas,
        "quantidade_gerada": quantidade_gerada,
        "quantidade_do_banco": len(do_banco),
    }


if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.dirname(__file__))
    from base_faq import coletar_faq

    link = sys.argv[1] if len(sys.argv) > 1 else "https://expressojk.buser.com.br/"
    entidade = sys.argv[2] if len(sys.argv) > 2 else "Expresso JK"
    quantidade = int(sys.argv[3]) if len(sys.argv) > 3 else 7

    resultado_coleta = coletar_faq(link)
    resultado = montar_faq_empresa(entidade, resultado_coleta["fontes"], quantidade)

    print(f"pedidas: {resultado['quantidade_pedida']} | geradas: {resultado['quantidade_gerada']} | do banco: {resultado['quantidade_do_banco']}")
    for par in resultado["perguntas"]:
        print(f"\nP: {par['pergunta']}\nR: {par['resposta']}")
