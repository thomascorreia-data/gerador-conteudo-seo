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


def sortear_da_lista(entidade: str, quantidade: int, excluir_topicos: set = None) -> list:
    """Sorteia `quantidade` perguntas do banco pronto (sem repetir dentro do
    mesmo sorteio), já substituindo {entidade} no texto. Cada item devolvido
    mantém o "topico" (usado só internamente, pra detectar assunto repetido
    — não aparece pro leitor final).

    `excluir_topicos`: usado quando o banco precisa complementar uma vaga
    que a geração dinâmica não conseguiu preencher sem repetir assunto (ver
    montar_faq_empresa) — só sorteia entre os tópicos que ainda não foram
    usados nesta rodada.

    Se pedir mais do que os candidatos disponíveis, devolve todos que
    houver (nunca repete pergunta/tópico)."""
    if quantidade <= 0:
        return []
    candidatos = PERGUNTAS_PRONTAS
    if excluir_topicos:
        candidatos = [item for item in PERGUNTAS_PRONTAS if item["topico"] not in excluir_topicos]
    quantidade = min(quantidade, len(candidatos))
    escolhidas = random.sample(candidatos, quantidade)
    return [
        {
            "topico": item["topico"],
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
    """Cada item pode vir com "topico" (pedido no prompt de geração) — se o
    modelo não incluir por algum motivo, o item ainda é aceito (só não entra
    na checagem de assunto repetido em montar_faq_empresa, em vez de ser
    descartado por um campo faltando)."""
    texto_limpo = texto_resposta.strip().replace("```json", "").replace("```", "").strip()
    try:
        dados = json.loads(texto_limpo)
    except json.JSONDecodeError:
        return []
    if not isinstance(dados, list):
        return []

    resultado = []
    for item in dados:
        if not isinstance(item, dict) or not item.get("pergunta") or not item.get("resposta"):
            continue
        par = {"pergunta": item["pergunta"].strip(), "resposta": item["resposta"].strip()}
        if item.get("topico"):
            par["topico"] = str(item["topico"]).strip().lower()
        resultado.append(par)
    return resultado


def _montar_texto_evitar(itens_ja_usados: list) -> str:
    """Lista as perguntas já usadas (do banco) PRA MOSTRAR o assunto de cada
    uma junto — ajuda o modelo a evitar não só a mesma pergunta, mas o mesmo
    ASSUNTO reformulado com outras palavras (o caso real que motivou isso:
    "a Buser é segura?" no banco + "a {entidade} é segura?" gerada — mesmo
    assunto, "seguranca", só que com o nome trocado)."""
    if not itens_ja_usados:
        return "(nenhuma)"
    linhas = []
    for item in itens_ja_usados:
        rotulo = f" [assunto: {item['topico']}]" if item.get("topico") else ""
        linhas.append(f"- {item['pergunta']}{rotulo}")
    return "\n".join(linhas)


def _gerar_dinamicas(
    entidade: str,
    fontes: dict,
    quantidade_gerada: int,
    itens_ja_usados: list,
    palavras_chave: list = None,
) -> list:
    """Gera as perguntas complementares (a parte que NÃO vem do banco
    pronto), grounded no que foi coletado de verdade sobre a empresa.
    `itens_ja_usados` é a lista de perguntas do banco já sorteadas (cada uma
    com "topico") — usada só pra montar o texto de "não repita isso"."""
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

    perguntas_evitar_texto = _montar_texto_evitar(itens_ja_usados)

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

    Garantia de assunto único: cada pergunta (do banco ou gerada) carrega um
    "topico" — se a geração devolver algo com o MESMO assunto de uma pergunta
    do banco já sorteada (ou de outra gerada nesta mesma rodada), aquele item
    é descartado e a vaga é preenchida com outra pergunta PRONTA de assunto
    ainda não usado, em vez de arriscar gerar de novo e colidir de novo
    (testado ao vivo: "a Buser é segura?" do banco + "a {entidade} é segura?"
    gerada — mesmo assunto, reformulado).
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
    topicos_usados = {item["topico"] for item in do_banco}

    geradas_brutas = _gerar_dinamicas(entidade, fontes, quantidade_gerada, do_banco, palavras_chave)

    geradas_aceitas = []
    geradas_descartadas = []
    for item in geradas_brutas:
        topico = item.get("topico")
        # Sem "topico" (modelo não incluiu) -> aceita sem checar, mais seguro
        # que descartar um item bom só por um campo faltando.
        if topico and topico in topicos_usados:
            geradas_descartadas.append(item)
            continue
        geradas_aceitas.append(item)
        if topico:
            topicos_usados.add(topico)

    faltando = quantidade_gerada - len(geradas_aceitas)
    if faltando > 0:
        # A geração colidiu de assunto e ficou curta — completa com pronta(s)
        # de assunto ainda não usado, em vez de tentar gerar de novo (mesmo
        # risco de colidir outra vez).
        extras = sortear_da_lista(entidade, faltando, excluir_topicos=topicos_usados)
        do_banco = do_banco + extras
        faltando -= len(extras)

    if faltando > 0:
        # Banco também já esgotado (todo tópico disponível já foi usado) —
        # não tem mais de onde tirar assunto novo. Nesse caso extremo,
        # aceita a(s) gerada(s) descartada(s) mesmo repetindo assunto: é
        # melhor que devolver menos perguntas do que foi pedido.
        geradas_aceitas += geradas_descartadas[:faltando]

    todas = do_banco + geradas_aceitas
    random.shuffle(todas)

    # "topico" é só controle interno — não vai pro leitor final.
    perguntas_finais = [{"pergunta": p["pergunta"], "resposta": p["resposta"]} for p in todas]

    return {
        "perguntas": perguntas_finais,
        "quantidade_pedida": quantidade_perguntas,
        "quantidade_gerada": len(geradas_aceitas),
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
