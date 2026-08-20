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


def gerar_texto_bruto(
    categoria: str,
    entidade: str,
    fontes: dict,
    tom: str = "informativo",
    media_palavras: int = None,
    palavras_chave: list = None,
    classificacao_tipo: dict = None,
    instrucao_extra: str = None,
) -> str:
    """
    Monta o prompt certo (categoria x tom) a partir de prompts_descricao.json
    e chama o modelo — só a geração bruta, SEM passar pelo humanizador.
    Separada de gerar_descricao() pra poder ser chamada isoladamente pelo
    grafo (formatos/descricao/grafo_descricao.py), que roda humanizar e
    revisor como nós próprios e pode voltar a chamar só esta função de novo
    se o revisor reprovar.

    instrucao_extra: usado pelo grafo numa nova tentativa depois de uma
    reprovação — carrega o motivo específico da reprovação anterior, pra
    não repetir o mesmo erro às cegas numa reamostragem sem nenhuma pista
    do que falhou da vez passada.
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

    # Só a categoria "empresa" tem {instrucao_tipo_empresa} no template — nas
    # demais, o .format() simplesmente ignora esse kwarg (não é KeyError
    # passar um nome a mais que não aparece na string).
    instrucao_tipo_empresa = (classificacao_tipo or {}).get("instrucao", "")

    prompt = dados_tom["template"].format(
        entidade=entidade,
        fontes_texto=fontes_texto,
        instrucao_tipo_empresa=instrucao_tipo_empresa,
    )

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

    if instrucao_extra:
        # Fica por último de propósito: é a última coisa que o modelo lê
        # antes de escrever, então tem mais peso que uma correção enterrada
        # no meio do prompt.
        prompt += f"\n\n{instrucao_extra}"

    resposta = modelo.invoke(prompt, **kwargs_modelo)
    return resposta.content.strip()


def gerar_descricao(
    categoria: str,
    entidade: str,
    fontes: dict,
    tom: str = "informativo",
    media_palavras: int = None,
    palavras_chave: list = None,
    classificacao_tipo: dict = None,
) -> str:
    """
    Ponto de entrada de geração completo (gera + humaniza), mantido pra quem
    ainda chama direto (CLI, testes manuais). O grafo não usa esta função —
    ele chama gerar_texto_bruto() e humanizar_texto() como nós separados,
    com o revisor entre eles decidindo se repete a geração.
    """
    texto_gerado = gerar_texto_bruto(
        categoria=categoria,
        entidade=entidade,
        fontes=fontes,
        tom=tom,
        media_palavras=media_palavras,
        palavras_chave=palavras_chave,
        classificacao_tipo=classificacao_tipo,
    )

    # Repassa a mesma instrução de tipo de empresa pro humanizador: sem
    # isso, ele tinha sua própria regra de auto-classificação (menos
    # informada) e podia desfazer a escolha de "passagem"/"viagem" que a
    # geração acima já acertou.
    instrucao_tipo_empresa = (classificacao_tipo or {}).get("instrucao", "")
    return humanizar_texto(texto_gerado, instrucao_tipo_empresa)


def humanizar_texto(texto_gerado: str, instrucao_tipo_empresa: str = "") -> str:
    """
    Etapa final de revisão: reescreve o texto gerado pra soar mais natural
    e menos "de IA", preservando fatos e diferenciais da Buser já citados.
    Roda pra qualquer categoria/tom, sempre — o prompt vem do bloco
    "humanizador" (fora das categorias) em prompts_descricao.json.
    """
    dados_humanizador = PROMPTS_POR_CATEGORIA.get("humanizador")
    if not dados_humanizador or not dados_humanizador.get("template"):
        return texto_gerado

    prompt = dados_humanizador["template"].format(
        texto_gerado=texto_gerado,
        instrucao_tipo_empresa=instrucao_tipo_empresa,
    )

    # Mesmo problema que a geração original tinha antes de ganhar max_tokens:
    # "mantenha o tamanho aproximado" no prompt é só uma sugestão, o modelo
    # pode ignorá-la e devolver um texto bem maior que o original — mesmo
    # que a geração já tivesse respeitado media_palavras. O teto aqui usa o
    # tamanho do PRÓPRIO texto de entrada (não media_palavras), porque o
    # contrato do humanizador é preservar o tamanho, não mirar um alvo novo.
    palavras_originais = len(texto_gerado.split())
    max_tokens = int(palavras_originais * 1.8) + 40

    try:
        resposta = modelo.invoke(prompt, max_tokens=max_tokens)
        return resposta.content.strip()
    except Exception:
        # Se a humanização falhar por qualquer motivo (rate limit, etc.),
        # não trava a geração inteira — devolve o texto original, que já
        # é válido, em vez de propagar o erro.
        return texto_gerado


TOM_PADRAO = "informativo"
MEDIA_PALAVRAS_PADRAO = 100
# "buser" não entra aqui: isso é usado como fallback sempre que o usuário
# deixa o campo de palavras-chave em branco, e forçar a marca como
# "palavra-chave" faz o modelo citá-la mesmo no tom informativo (que pede
# EXPLICITAMENTE pra evitar linguagem promocional). Citar a Buser é papel
# das instruções de tom (vendas/promocional já pedem isso no template),
# não do mecanismo de palavras-chave de SEO.
PALAVRAS_CHAVE_PADRAO = ["passagem", "onibus"]


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
        classificacao_tipo=resultado.get("classificacao_tipo"),
    )


if __name__ == "__main__":
    texto = gerar_descricao_por_tema("Expresso JK", tom="vendas", media_palavras=100)
    print(texto)
