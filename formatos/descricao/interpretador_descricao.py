import json
from base_cidade import coletando_conteudo
from base_pontos_turisticos import coletar_ponto_turistico
from base_rodoviarias import coletar_rodoviaria
from base_empresas import coletar_empresa
# from base_estados import coletar_estado
# from base_paises import coletar_pais
from base_lugares_genericos import coletar_lugar_generico
from base_eventos import coletar_evento

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

CATEGORIAS = [
    "cidade",
    "estado",
    "pais",
    "ponto_turistico",
    "lugar_generico",
    "evento",
    "feriado",
    "empresa",
    "terminal_rodoviaria",
]

PROMPT_CLASSIFICACAO = """Você é um classificador de temas para um site de transporte rodoviário.

Dado o tema abaixo, identifique a categoria mais adequada entre:
- cidade
- estado
- pais
- ponto_turistico (praia, parque, museu, monumento, avenidas famosas,etc.)
- lugar_generico (shopping, comércio, restaurante, hotel, aeroporto, etc.)
- evento (festival, show, feira, etc. — algo pontual, de uma edição/ano específico, não uma data fixa do calendário)
- feriado (Ano Novo, Natal, Carnaval, Tiradentes, Páscoa, Dia do Trabalho, Independência, etc. — uma data comemorativa fixa do calendário civil/religioso brasileiro, nacional ou regional, que se repete todo ano)
- empresa (nome de operadora/empresa de transporte)
- terminal_rodoviaria (terminal ou rodoviária)

ATENÇÃO — evento x feriado: a diferença não é o quão "festivo" é, é se existe uma DATA FIXA recorrente no calendário. "Carnaval" e "Natal" são feriado (data certa todo ano, mesmo que o Carnaval seja móvel pela Páscoa). Já "Festival de Parintins" ou "Rock in Rio" são evento (edição específica, sem data fixa no calendário civil). Na dúvida entre os dois, pergunte-se: "isso está marcado no calendário nacional de feriados?" — se sim, é "feriado".

ATENÇÃO — feriado MUNICIPAL/regional precisa da cidade: nem todo feriado é nacional — muitos são de uma cidade só (ex: "Nossa Senhora dos Navegantes" é a padroeira de Porto Alegre, não feriado no resto do país). Se o tema trouxer o nome do feriado JUNTO com uma cidade (ex: "Nossa Senhora dos Navegantes de Porto Alegre", "Aniversário de São Paulo feriado"), classifique como "feriado" normalmente, mas preencha o campo "cidade" com essa cidade — isso é essencial pra coleta de conteúdo, que precisa da cidade pra achar a página certa (sem isso, cai numa página genérica sobre o santo/devoção, sem data nem lugar nenhum). Se o tema NÃO trouxer cidade nenhuma (ex: só "Nossa Senhora dos Navegantes"), deixe "cidade" como null mesmo — não invente uma cidade que não foi mencionada.

ATENÇÃO — armadilha comum: muitas empresas de ônibus/fretamento levam o nome
de uma cidade real (às vezes até uma cidade turística conhecida) seguido de
uma palavra que indica que é uma EMPRESA, não o lugar em si. Palavras como
"Turismo", "Tur", "Viação", "Expresso", "Transportes", "Viagens" ou
"Fretamento" no final do tema são um sinal FORTE de categoria "empresa" —
isso vale mesmo que a primeira palavra pareça (ou seja de fato) o nome de
uma cidade, ponto turístico ou região real. Nesse caso, classifique como
"empresa", não como "cidade" nem "ponto_turistico".
Exemplo: "Penedo Turismo" é uma empresa de fretamento (mesmo "Penedo" sendo
uma cidade turística real em Alagoas) — categoria certa: "empresa".

Tema: "{tema}"

Responda APENAS com um JSON no seguinte formato, sem nenhum texto adicional, sem markdown, sem crases:
{{
  "categoria": "uma das categorias listadas",
  "entidade": "nome principal identificado",
  "cidade": "cidade relacionada, se identificável, senão null",
  "estado": "sigla do estado relacionado, se identificável, senão null",
  "confianca": "alta, media ou baixa"
}}
"""

load_dotenv()

if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError(
        "OPENAI_API_KEY não encontrada. Confira se o arquivo .env existe "
        "na raiz do projeto e tem a linha OPENAI_API_KEY=sk-..."
    )

modelo = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


def classificar_tema(tema: str) -> dict:
    """Usa o modelo para classificar o tema em uma das categorias definidas."""
    resposta = modelo.invoke(PROMPT_CLASSIFICACAO.format(tema=tema))
    texto = resposta.content.strip()

    # remove possíveis blocos de markdown (```json ... ```), por segurança
    texto = texto.replace("```json", "").replace("```", "").strip()

    try:
        resultado = json.loads(texto)
    except json.JSONDecodeError:
        raise ValueError(f"Não foi possível interpretar a resposta do modelo: {texto}")

    if resultado.get("categoria") not in CATEGORIAS:
        raise ValueError(f"Categoria retornada inválida: {resultado.get('categoria')}")

    return resultado


ABRANGENCIAS_FERIADO = ["nacional", "estadual", "municipal"]

PROMPT_ABRANGENCIA_FERIADO = """Você é um especialista em feriados e datas comemorativas do Brasil.

Dado o feriado abaixo, use seu conhecimento sobre feriados brasileiros reais pra identificar a ABRANGÊNCIA dele:
- "nacional": válido em todo o Brasil (ex: Natal, Tiradentes, Carnaval, Ano Novo, Dia do Trabalho)
- "estadual": só um estado específico tem esse feriado (ex: Revolução Constitucionalista, feriado só em SP)
- "municipal": só uma cidade específica tem esse feriado (ex: aniversário de uma cidade, padroeiro/padroeira de uma cidade)

Feriado: "{entidade}"
Cidade já identificada no tema original (se houver): {cidade_conhecida}
Estado já identificado no tema original (se houver): {estado_conhecido}

Se já tiver cidade/estado identificado acima, use isso como pista forte (mas corrija se seu conhecimento disser outra coisa — às vezes o tema original vem incompleto ou errado). Se você NÃO tiver certeza real de qual cidade/estado específico é (feriado municipal/estadual pouco conhecido, ou nome genérico demais), deixe "cidade"/"estado" como null e marque confianca "baixa" — NUNCA invente uma cidade/estado que você não tem certeza de verdade, é melhor devolver null do que chutar errado.

Responda APENAS com um JSON, sem markdown, sem texto adicional, no seguinte formato:
{{
  "abrangencia": "nacional" ou "estadual" ou "municipal",
  "cidade": "cidade específica, só se abrangencia for municipal e você tiver certeza, senão null",
  "estado": "sigla do estado, se abrangencia for estadual ou municipal e você tiver certeza, senão null",
  "confianca": "alta, media ou baixa"
}}
"""


def classificar_abrangencia_feriado(entidade: str, cidade: str = None, estado: str = None) -> dict:
    """Identifica se um feriado é nacional, estadual ou municipal, usando o
    CONHECIMENTO GERAL do modelo sobre feriados brasileiros reais — não só
    o que está escrito no tema (diferente de classificar_tema, que só
    extrai cidade/estado quando aparecem literalmente no texto digitado).

    Usado só pra categoria "feriado", como um nó à parte depois da
    classificação principal (ver no_classificar_abrangencia_feriado em
    grafo_descricao.py) — pode preencher cidade/estado que
    classificar_tema não pegou (ex: tema só "Nossa Senhora dos
    Navegantes", sem cidade nenhuma escrita), mas só quando o modelo tiver
    confiança real; nunca inventa só pra preencher o campo."""
    resposta = modelo.invoke(PROMPT_ABRANGENCIA_FERIADO.format(
        entidade=entidade,
        cidade_conhecida=cidade or "nenhuma",
        estado_conhecido=estado or "nenhum",
    ))
    texto = resposta.content.strip().replace("```json", "").replace("```", "").strip()

    try:
        resultado = json.loads(texto)
    except json.JSONDecodeError:
        raise ValueError(f"Não foi possível interpretar a resposta do modelo: {texto}")

    if resultado.get("abrangencia") not in ABRANGENCIAS_FERIADO:
        raise ValueError(f"Abrangência retornada inválida: {resultado.get('abrangencia')}")

    return resultado


PROMPT_MES_DIA_FIXO_FERIADO = """Você é um especialista em feriados, datas comemorativas e calendário litúrgico do Brasil.

Dado o feriado abaixo, diga se ele tem uma data FIXA no calendário (mesmo dia e mês todo ano — como a maioria dos dias de santo/padroeiro, ex: Santos Reis é sempre 6 de janeiro) ou se é uma data MÓVEL (calculada a partir da Páscoa, varia de ano pra ano, ex: Carnaval, Corpus Christi).

Feriado: "{entidade}"
Cidade (se houver): {cidade_conhecida}
Estado (se houver): {estado_conhecido}

Se for uma data FIXA e você tiver certeza real do dia e mês, devolva eles. Se for uma data MÓVEL, ou se você NÃO tiver certeza de verdade do dia/mês exatos (nome genérico, feriado pouco conhecido, risco de confundir com outro feriado parecido), devolva "tem_data_fixa": false e mes/dia como null — NUNCA invente um dia/mês que você não tem certeza de verdade, é melhor devolver null do que chutar errado.

Responda APENAS com um JSON, sem markdown, sem texto adicional, no seguinte formato:
{{
  "tem_data_fixa": true ou false,
  "mes": numero de 1 a 12, só se tem_data_fixa for true e você tiver certeza, senão null,
  "dia": numero do dia, só se tem_data_fixa for true e você tiver certeza, senão null,
  "confianca": "alta, media ou baixa"
}}
"""


def obter_mes_dia_fixo_feriado(entidade: str, cidade: str = None, estado: str = None) -> dict:
    """Pra feriados de data FIXA que não estão na tabela verificada de
    feriados_datas.py (ex: "Santos Reis", "Nossa Senhora da Apresentação")
    — pergunta ao modelo só o mês/dia (fato de calendário, não aritmética),
    pra depois o código calcular o ANO/dia-da-semana certos em cima disso
    (feriados_datas.calcular_proxima_ocorrencia). Evita o mesmo erro que
    calcular_data_feriado foi criado pra evitar: deixar o modelo "inventar"
    o ano, que é onde ele historicamente erra (citou 2023/2024 — anos já
    passados — em vez do próximo ano em que a data realmente cai)."""
    resposta = modelo.invoke(PROMPT_MES_DIA_FIXO_FERIADO.format(
        entidade=entidade,
        cidade_conhecida=cidade or "nenhuma",
        estado_conhecido=estado or "nenhum",
    ))
    texto = resposta.content.strip().replace("```json", "").replace("```", "").strip()

    try:
        resultado = json.loads(texto)
    except json.JSONDecodeError:
        raise ValueError(f"Não foi possível interpretar a resposta do modelo: {texto}")

    return resultado


def interpretador(tema: str) -> dict:
    """
    Recebe o tema, classifica sua categoria, roteia para a função de coleta
    correspondente e devolve tudo já normalizado para a geração do texto:

        {
            "categoria": "cidade" | "ponto_turistico" | "terminal_rodoviaria" | ...,
            "entidade": nome a usar no prompt (ex: "Salvador", "Hopi Hari"),
            "fontes": {nome_da_fonte: {"paragrafos"/"conteudo": ..., "erro": ...}, ...},
            "classificacao_tipo": só presente pra categoria "empresa" (ver
                base_empresas.coletar_empresa) — None nas demais categorias,
        }
    """
    classificacao = classificar_tema(tema)
    categoria = classificacao["categoria"]

    #print(f"[interpretador] Tema: '{tema}' -> Categoria: '{categoria}' "
    #     f"(confiança: {classificacao.get('confianca')})")

    if categoria == "cidade":
        cidade = classificacao.get("cidade") or classificacao["entidade"]
        estado = classificacao.get("estado")
        fontes = coletando_conteudo(cidade, estado)
        return {"categoria": categoria, "entidade": cidade, "fontes": fontes}

    elif categoria == "ponto_turistico":
        entidade = classificacao["entidade"]
        resultado = coletar_ponto_turistico(entidade)
        if resultado.get("erro"):
            raise ValueError(resultado["erro"])
        return {"categoria": categoria, "entidade": entidade, "fontes": resultado["fontes"]}

    elif categoria == "terminal_rodoviaria":
        entidade = classificacao["entidade"]
        resultado = coletar_rodoviaria(entidade)
        return {"categoria": categoria, "entidade": entidade, "fontes": resultado["fontes"]}

    elif categoria == "estado":
        raise NotImplementedError("Coleta para 'estado' ainda não implementada")

    elif categoria == "pais":
        raise NotImplementedError("Coleta para 'pais' ainda não implementada")

    elif categoria == "lugar_generico":
        entidade = classificacao["entidade"]
        resultado = coletar_lugar_generico(entidade)
        return {"categoria": categoria, "entidade": entidade, "fontes": resultado["fontes"]}

    elif categoria == "evento":
        entidade = classificacao["entidade"]
        resultado = coletar_evento(entidade, cidade=classificacao.get("cidade"))
        return {"categoria": categoria, "entidade": entidade, "fontes": resultado["fontes"]}

    elif categoria == "empresa":
        entidade = classificacao["entidade"]
        resultado = coletar_empresa(entidade)
        return {
            "categoria": categoria,
            "entidade": entidade,
            "fontes": resultado["fontes"],
            "classificacao_tipo": resultado.get("classificacao_tipo"),
        }

    else:
        raise ValueError(f"Categoria não tratada: {categoria}")


if __name__ == "__main__":
    resultado = interpretador("Avenida Paulista")
    print(resultado)