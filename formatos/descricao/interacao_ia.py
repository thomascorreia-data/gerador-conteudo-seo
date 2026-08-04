import json
import os
import sys
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from interpretador_descricao import interpretador

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError(
        "OPENAI_API_KEY não encontrada. Confira se o arquivo .env existe "
        "na raiz do projeto e tem a linha OPENAI_API_KEY=sk-..."
    )

modelo = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# ---------------------------------------------------------------------------
# PROMPTS POR CATEGORIA x TOM, carregados de prompts_descricao.json
# (uma categoria sem template preenchido para o tom pedido lança
# NotImplementedError — hoje só "cidade" e "ponto_turistico" estão prontos)
# ---------------------------------------------------------------------------

CAMINHO_PROMPTS = os.path.join(os.path.dirname(__file__), "prompts_descricao.json")

with open(CAMINHO_PROMPTS, encoding="utf-8") as arquivo:
    PROMPTS_POR_CATEGORIA = json.load(arquivo)


def montar_fontes_texto(fontes: dict) -> str:
    """Junta o conteúdo coletado de cada fonte (ignorando as que deram erro
    ou vieram sem conteúdo) em um único bloco de texto para o prompt.
    Aceita tanto o formato {"paragrafos": [...]} (ex: base_cidade) quanto
    {"conteudo": "..."} (ex: base_pontos_turisticos)."""
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


def gerar_descricao(
    categoria: str,
    entidade: str,
    fontes: dict,
    tom: str = "informativo",
    media_palavras: int = None,
    palavras_chave: list = None,
) -> str:
    """
    Função genérica de geração: dado que o interpretador já identificou a
    categoria do tema (cidade, ponto_turistico, etc.) e já coletou as
    fontes correspondentes, monta o prompt certo (categoria x tom) a partir
    de prompts_descricao.json e chama o modelo.
    """
    dados_categoria = PROMPTS_POR_CATEGORIA.get(categoria)
    if not dados_categoria:
        raise NotImplementedError(
            f"Categoria '{categoria}' não existe em prompts_descricao.json"
        )

    tom_normalizado = tom.strip().lower()
    dados_tom = dados_categoria.get(tom_normalizado)
    if not dados_tom or not dados_tom.get("template"):
        raise NotImplementedError(
            f"Prompt para categoria '{categoria}' com tom '{tom}' ainda não foi "
            "cadastrado em prompts_descricao.json"
        )

    fontes_texto = montar_fontes_texto(fontes)
    if not fontes_texto:
        raise ValueError(f"Nenhuma fonte com conteúdo coletado para '{entidade}'.")

    prompt = dados_tom["template"].format(entidade=entidade, fontes_texto=fontes_texto)

    kwargs_modelo = {}
    if media_palavras:
        # "Aproximadamente" no fim do prompt era ignorado pelo modelo (ele
        # prioriza cobrir todos os aspectos pedidos acima em vez do tamanho).
        # Agora é um limite rígido, reforçado, e complementado por um teto
        # de max_tokens de verdade — sem isso o modelo não tinha nenhum freio
        # técnico e podia gerar um texto de qualquer tamanho.
        prompt += (
            f"\n\nRESTRIÇÃO DE TAMANHO (obrigatória): o texto final deve ter "
            f"NO MÁXIMO {media_palavras} palavras. Esse é um limite rígido, não "
            f"uma sugestão — prefira cortar detalhes secundários a ultrapassá-lo."
        )
        # ~1.8 tokens por palavra em português (acentos/palavras longas
        # tokenizam em mais partes que em inglês) + margem pro texto fechar
        # a última frase sem ser cortado no meio.
        kwargs_modelo["max_tokens"] = int(media_palavras * 1.8) + 40

    if palavras_chave:
        prompt += (
            "\n\nInclua de forma natural, sem forçar, as seguintes palavras-chave: "
            + ", ".join(palavras_chave)
            + "."
        )

    resposta = modelo.invoke(prompt, **kwargs_modelo)
    return resposta.content.strip()


TOM_PADRAO = "informativo"
MEDIA_PALAVRAS_PADRAO = 300
PALAVRAS_CHAVE_PADRAO = ["buser", "viagem barata", "passagem", "onibus"]


def gerar_descricao_por_tema(
    tema: str,
    tom: str = TOM_PADRAO,
    media_palavras: int = MEDIA_PALAVRAS_PADRAO,
    palavras_chave: list = None,
) -> str:
    """
    Único ponto de entrada necessário: recebe só o tema (ex: "Salvador",
    "Hopi Hari"). O interpretador classifica a categoria, coleta as fontes
    certas e devolve entidade/fontes já prontos para o prompt — aqui só
    aplicamos o tom e os valores padrão de media_palavras/palavras_chave.
    """
    if palavras_chave is None:
        palavras_chave = PALAVRAS_CHAVE_PADRAO

    resultado = interpretador(tema)
    return gerar_descricao(
        categoria=resultado["categoria"],
        entidade=resultado["entidade"],
        fontes=resultado["fontes"],
        tom=tom,
        media_palavras=media_palavras,
        palavras_chave=palavras_chave,
    )


if __name__ == "__main__":
    texto = gerar_descricao_por_tema("MASP")
    print(texto)
