import json
from base_cidade import coletando_conteudo
from base_pontos_turisticos import coletar_ponto_turistico
from base_rodoviarias import coletar_rodoviaria
# from base_estados import coletar_estado
# from base_paises import coletar_pais
# from base_lugares_genericos import coletar_lugar_generico
# from base_eventos import coletar_evento
# from base_empresas import coletar_empresa

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
- evento (festival, show, feira, etc.)
- empresa (nome de operadora/empresa de transporte)
- terminal_rodoviaria (terminal ou rodoviária)

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


def interpretador(tema: str) -> dict:
    """
    Recebe o tema, classifica sua categoria, roteia para a função de coleta
    correspondente e devolve tudo já normalizado para a geração do texto:

        {
            "categoria": "cidade" | "ponto_turistico" | "terminal_rodoviaria" | ...,
            "entidade": nome a usar no prompt (ex: "Salvador", "Hopi Hari"),
            "fontes": {nome_da_fonte: {"paragrafos"/"conteudo": ..., "erro": ...}, ...},
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
        raise NotImplementedError("Coleta para 'lugar_generico' ainda não implementada")

    elif categoria == "evento":
        raise NotImplementedError("Coleta para 'evento' ainda não implementada")

    elif categoria == "empresa":
        raise NotImplementedError("Coleta para 'empresa' ainda não implementada")

    else:
        raise ValueError(f"Categoria não tratada: {categoria}")


if __name__ == "__main__":
    resultado = interpretador("Avenida Paulista")
    print(resultado)