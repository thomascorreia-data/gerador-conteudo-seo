# Para temas enquadrados como [pais; estado; cidade e bairro/região]:
"""
    PAÍS: Quando o tema for um país, devemos descrever o país de forma geral, buscando trazer elementos
    que o caracterizam, como cultura, economia, gastronomia e turismo. Você deve evitar falar de cidades específicas, mas pode mencionar regiões ou estados do país.
    O objetivo é fornecer uma visão geral do país e suas características únicas.
        Exemplo:
        "
        O Brasil é o maior país da América do Sul e um dos mais diversos do mundo em paisagem e cultura.
        No litoral do Nordeste predominam praias tropicais e clima quente o ano todo, enquanto a Amazônia guarda a maior floresta tropical do planeta.
        No Sul, o clima é mais frio e a paisagem lembra o campo europeu, com serras e vinícolas.
        Já o Pantanal, no Centro-Oeste, é uma das maiores concentrações de vida selvagem da América Latina.

        A cultura brasileira nasce da mistura entre povos indígenas, africanos e europeus.
        Essa mistura aparece na música, no carnaval, nas religiões e principalmente na comida.
        A culinária muda bastante de região para região: no Nordeste o dendê e o peixe dão o tom, no Sul prevalecem carnes e churrasco, e na Amazônia aparecem frutas e peixes que não existem em outros lugares do país.
        Economicamente, o Brasil é uma das maiores economias em desenvolvimento do mundo, com força grande no agronegócio e também em serviços e indústria.

        Para quem gosta de viajar, o país oferece praticamente todo tipo de experiência: praia, ecoturismo, trilhas, vida noturna e turismo cultural.
        Com um território tão grande, ir de ônibus costuma valer mais a pena que outros meios de transporte, tanto no preço quanto pela quantidade de rotas disponíveis.



    ESTADO: Quando o tema for um estado, devemos descrever suas características gerais, trazendo elementos
    que o diferenciam dentro do país, como geografia, cultura regional, economia e principais atrativos turísticos. Você deve evitar entrar em detalhes de cidades específicas, mas pode citá-las brevemente como exemplos dentro do estado.
    O objetivo é fornecer uma visão panorâmica do estado, destacando o que o torna único frente aos demais.
        Exemplo:
        "
        A Bahia é o maior estado do Nordeste brasileiro e um dos destinos mais procurados do país, conhecido por suas praias, sua história e sua cultura vibrante.
        O litoral se estende por centenas de quilômetros, alternando entre praias urbanas movimentadas e trechos mais preservados, enquanto o interior guarda paisagens de serra e vegetação de caatinga.

        A cultura baiana tem forte influência africana, presente na música, na religião, nas festas populares e na culinária.
        Pratos como acarajé, moqueca e vatapá são exemplos dessa herança, que também aparece no ritmo do axé e nas manifestações religiosas de matriz africana.
        A economia do estado combina turismo, agronegócio e um polo industrial relevante, sendo um dos principais motores econômicos da região Nordeste.

        Para quem viaja, a Bahia oferece desde praias paradisíacas até cidades históricas e festas populares ao longo do ano.
        A extensão do estado favorece roteiros de ônibus entre diferentes regiões, conectando praia, cidade histórica e interior em uma mesma viagem.
        "


    CIDADE: Quando o tema for uma cidade, devemos descrever suas características específicas, trazendo elementos
    que a tornam reconhecível, como pontos turísticos, cultura local, gastronomia e vida urbana. Você deve focar na cidade em si, evitando generalizar para o estado ou país inteiro, mas pode mencionar bairros ou regiões da cidade como exemplos.
    O objetivo é fornecer uma visão prática e atrativa da cidade para quem está considerando visitá-la.
        Exemplo:
        "
        Salvador, capital da Bahia, é uma das cidades mais antigas do Brasil e reúne história, cultura e praia em um só lugar.
        O Pelourinho, seu centro histórico, é conhecido pelas casas coloridas, ladeiras de pedra e pela forte presença de manifestações culturais como capoeira e música ao vivo.
        Já bairros como Barra e Rio Vermelho concentram boa parte da vida noturna e das praias urbanas mais frequentadas pelos moradores.

        A culinária local é um dos grandes atrativos da cidade, com destaque para o acarajé vendido nas ruas e os restaurantes especializados em comida baiana.
        Salvador também é palco de um dos carnavais mais tradicionais do país, movimentando a cidade inteira durante os dias de festa.

        Para chegar até lá ou seguir viagem para outras cidades da região, o ônibus costuma ser uma opção prática e econômica, com boa frequência de rotas.
        "


    BAIRRO/REGIÃO: Quando o tema for um bairro ou região específica dentro de uma cidade, devemos descrever suas características particulares, trazendo elementos
    que o distinguem de outras áreas da cidade, como perfil dos moradores, comércio local, pontos de interesse e ambiente predominante. Você deve manter o foco na área específica, evitando generalizar para a cidade inteira.
    O objetivo é fornecer uma visão detalhada do bairro ou região, útil para quem quer entender o que esperar daquele local especificamente.
        Exemplo:
        "
        O Rio Vermelho, em Salvador, é um dos bairros mais conhecidos da cidade, famoso por reunir vida noturna, gastronomia e tradição religiosa em um mesmo espaço.
        Suas ruas concentram bares, restaurantes e casas de música que funcionam até tarde, atraindo tanto moradores quanto turistas em busca de badalação.

        O bairro também é palco da Festa de Iemanjá, uma das celebrações religiosas mais importantes da cidade, que reúne milhares de pessoas todos os anos.
        Além da vida noturna, o Rio Vermelho tem um lado mais tranquilo durante o dia, com cafés, feiras de artesanato e orla à beira-mar ideal para caminhadas.

        Por ficar relativamente perto do centro e de outros pontos turísticos, o bairro costuma ser um bom ponto de partida para quem está de passagem por Salvador e quer explorar a cidade a pé ou usando transporte local.
        Para quem chega de outras cidades, vale considerar rotas de ônibus que desembarcam próximo à região, evitando deslocamentos longos dentro da própria capital.
        "
"""

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
