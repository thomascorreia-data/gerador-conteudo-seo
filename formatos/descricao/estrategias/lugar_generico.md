# Estratégia — Lugar Genérico

Categoria pra lugares que não são cidade, ponto turístico "clássico" nem terminal — shopping, comércio, restaurante, hotel, aeroporto, etc. Estrutura livre, sem few-shot, mesmo estilo de [cidade](cidade.md) e [ponto turístico](ponto_turistico.md).

## De onde vêm os dados: de lugar nenhum, por enquanto

Diferente de todas as outras categorias prontas, **não existe coletor nenhum pra `lugar_generico`** — nenhum `base_lugares_genericos.py`, nenhuma raspagem, nenhuma API. O nó `coletar_lugar_generico` (em [`grafo_descricao.py`](../grafo_descricao.py)) devolve fontes vazias de propósito:

```python
def no_coletar_lugar_generico(state: DescricaoState) -> dict:
    return {"fontes": {}}
```

Isso aciona o fallback "sem fontes" que existe no grafo pra qualquer categoria (ver [`explicacao_descricao_grafo/grafo_descricao.md`](../explicacao_descricao_grafo/grafo_descricao.md)): o texto é gerado do conhecimento geral do modelo, e o resultado final sai marcado com `"sem_fontes": true` (e um `"aviso"` explicando isso, em `gerando.py`/na interface). Ou seja: **toda descrição de `lugar_generico` hoje é gerada sem verificação nenhuma contra fonte real** — vale conferir manualmente antes de publicar, sempre.

## Por que fazer assim em vez de esperar por um coletor de verdade

O pedido original era só "gera o prompt" — construir um coletor de verdade (identificar o lugar, escolher fontes confiáveis tipo Google/Wikipédia, tratar os mesmos problemas de ambiguidade que já apareceram em [ponto_turistico](ponto_turistico.md) e [terminal_rodoviaria](terminal_rodoviaria.md)) é um trabalho bem maior. Como o fallback "sem fontes" já existia (construído pra cobrir falha de coleta nas outras categorias), aproveitá-lo aqui deixa a categoria utilizável imediatamente, com o risco de alucinação sinalizado de forma explícita — em vez de ficar travada em `NotImplementedError` esperando um coletor nunca escrito.

## Os 3 tons

Mesmo padrão de `cidade`/`ponto_turistico`:
- **`informativo`** — factual: o que é o lugar, onde fica, o que oferece, por que é relevante
- **`vendas`** — cita a Buser e exatamente 3 dos 7 diferenciais (mesma lista das outras categorias), com chamada pra ação
- **`promocional`** — envolvente, cita a Buser, sem CTA direto

## Quando vale construir um coletor de verdade

Se essa categoria passar a ser usada com frequência (ou se as alucinações viradas de "conhecimento geral" começarem a ser um problema recorrente), vale construir um `base_lugares_genericos.py` de verdade — mesma receita das outras: identificar o lugar (Nominatim, como `ponto_turistico`/`terminal_rodoviaria` já fazem), coletar de Wikipédia/site oficial, e então o nó do grafo passa a devolver fontes reais em vez de `{}`, desligando o fallback automaticamente (ele só entra em ação quando as fontes vêm vazias).
