# Estratégia — Ponto Turístico

Estrutura quase idêntica à de [cidade](cidade.md): texto livre, sem parágrafos fixos, sem few-shot. Template em [`prompts_descricao.json`](../prompts_descricao.json), coleta em [`base_pontos_turisticos.py`](../base_pontos_turisticos.py).

## De onde vêm os dados

[`base_pontos_turisticos.py`](../base_pontos_turisticos.py) usa o **Nominatim** (geocodificação do OpenStreetMap) pra identificar/confirmar o local, combinado com raspagem de sites e Wikipédia — mesmo estilo de `base_cidade.py`, sem API paga.

## Os 3 tons

- **`informativo`** — dados factuais, contexto histórico/geográfico, o que torna o local relevante e motivos comuns pra visitá-lo. Não tem a regra especial de "variar o fechamento" que `cidade` tem
- **`vendas`** — foco em converter o leitor em comprador da passagem, com gatilho de urgência/oportunidade e chamada pra ação (ex: "garanta sua passagem"). Cita a Buser como a empresa que leva até o ponto turístico
- **`promocional`** — destaca atrativos e experiências de forma envolvente, sem pedir compra direta. Cita a Buser como opção pra chegar até lá

## Diferença notável em relação a `cidade`

O tom `vendas` aqui ainda usa "garanta sua passagem" como exemplo de chamada pra ação — a mesma palavra que, na categoria `empresa`, foi banida (`garante`/`garantindo`/`garantia` viram problema recorrente lá). Como `ponto_turistico` nunca teve esse sintoma reportado, a regra não foi replicada aqui. Se aparecer o mesmo padrão de vazamento de "garante" nessa categoria, vale revisar esse exemplo específico primeiro — ele pode estar reforçando o próprio uso que se quer evitar, do jeito que aconteceu com um exemplo few-shot de `empresa` que continha a palavra banida.
