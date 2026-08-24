# Estratégia — Terminal Rodoviário

**Parcialmente implementada.** A coleta de dados já funciona; a geração de texto ainda não — os 3 tons estão vazios em [`prompts_descricao.json`](../prompts_descricao.json) (`"informativo": {}, "vendas": {}, "promocional": {}`). Pedir uma descrição desse tipo hoje resulta em erro (`NotImplementedError`) depois da coleta.

## O que já existe

[`base_rodoviarias.py`](../base_rodoviarias.py) recebe só o nome do terminal (ex: "Rodoviária do Tietê"), descobre cidade/UF automaticamente por geocodificação (Nominatim) e coleta descrição em duas fontes: **QueroPassagem** e **Wikipédia**. Isso já está encaixado no grafo ([`grafo_descricao.py`](../grafo_descricao.py), nó `coletar_terminal_rodoviaria`) — o roteamento por categoria já reconhece `terminal_rodoviaria` e chama esse coletor certo.

## O que falta

Escrever os templates de prompt (um por tom) em `prompts_descricao.json`, seguindo o mesmo processo já usado nas outras categorias:
1. Definir a estrutura desejada em conversa (ver como foi feito pra [empresa](empresa.md) — primeiro um exemplo concreto do resultado esperado, depois traduzir isso em instrução de prompt)
2. Escrever um primeiro rascunho de template e testar contra dados reais já coletados
3. Se aparecer um padrão de erro recorrente, considerar exemplo few-shot e/ou checagem determinística no revisor — nessa ordem, não ao contrário
