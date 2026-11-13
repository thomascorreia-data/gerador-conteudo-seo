"""
Smoke test de formatos/descricao/prompts_descricao.json: garante que todo
template (categoria x tom) é .format()-ável com o conjunto padrão de
kwargs que gerar_texto_bruto() sempre passa — sem isso, um placeholder
digitado errado (ex: "{cidade}" em vez de "{cidade_texto}") só aparece na
hora de gerar de verdade, com custo de API, em vez de aparecer aqui.
"""

from interacao_ia_descricao import PROMPTS_POR_CATEGORIA

# Mesmos kwargs sempre passados por gerar_texto_bruto() na chamada real
# (ver interacao_ia_descricao.py) — um template só pode referenciar um
# desses nomes, nenhum outro.
KWARGS_PADRAO = dict(
    entidade="Entidade de Teste",
    fontes_texto="Texto de fontes de teste.",
    instrucao_tipo_empresa="",
    data_calculada_texto="DATA EXATA CALCULADA: não disponível.",
    cidade_texto="CIDADE RELACIONADA: não aplicável.",
)


def test_todos_os_templates_de_categoria_formatam_sem_erro():
    for categoria, dados_categoria in PROMPTS_POR_CATEGORIA.items():
        if categoria == "humanizador":
            continue  # assinatura própria (texto_gerado, instrucao_tipo_empresa)
        for tom, dados_tom in dados_categoria.items():
            template = dados_tom.get("template")
            if not template:
                continue
            try:
                template.format(**KWARGS_PADRAO)
            except KeyError as erro:
                raise AssertionError(
                    f"prompts_descricao.json['{categoria}']['{tom}'] usa o "
                    f"placeholder {erro} que gerar_texto_bruto() nunca passa "
                    f"— provavelmente um nome errado (ex: {{cidade}} em vez "
                    f"de {{cidade_texto}})."
                )


def test_humanizador_formata_sem_erro():
    template = PROMPTS_POR_CATEGORIA["humanizador"]["template"]
    template.format(texto_gerado="texto de teste", instrucao_tipo_empresa="")
