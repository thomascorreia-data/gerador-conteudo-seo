# Estratégia — Empresa

Categoria mais desenvolvida do projeto: os 3 tons (`informativo`, `vendas`, `promocional`) têm prompt pronto, e é a única categoria que passa por uma classificação extra antes da geração (ver abaixo). Templates em [`prompts_descricao.json`](../prompts_descricao.json), coleta em [`base_empresas.py`](../base_empresas.py), classificação em [`grafo_descricao.py`](../grafo_descricao.py).

## De onde vêm os dados

[`base_empresas.py`](../base_empresas.py) usa a **SerpApi** (paga, com cache em [`cache_empresas.json`](../cache_empresas.json)) pra buscar, numa única consulta:
- o **AI Overview** do Google pra "o que é a empresa {nome}"
- o **top 15 de resultados orgânicos** (título/link/snippet, sem visitar os sites)
- se algum desses resultados for a Wikipédia, os parágrafos de introdução do artigo

## A classificação de tipo (passagem x viagem)

Antes de gerar qualquer texto, [`base_empresas.py`](../base_empresas.py) analisa o texto coletado por palavra-chave (sem LLM) e decide um de 4 tipos:

| Tipo | Sinal na fonte | Palavra a usar |
|---|---|---|
| `linha_regular` | menciona "linha regular/fixa/convencional", não menciona fretamento | `passagem` |
| `hibrida` | menciona os dois — linha regular E fretamento/turismo | `passagem` |
| `fretamento` | só menciona fretamento/turismo/excursão, nunca linha regular | `viagem` |
| `ambiguo` | fonte não deixa claro nenhum dos dois | `viagem` (mais seguro) |

Essa decisão vira uma frase pronta (`instrucao_tipo_empresa`) injetada no prompt — o modelo não precisa (e não deve) tentar classificar sozinho. Isso existe porque, na prática, pedir pro modelo classificar E escrever ao mesmo tempo é muito menos confiável do que decidir em código e só mandar escrever.

Duas regras extras vêm dessa classificação, só pra `fretamento` puro (não pra `ambiguo`):
- **nunca usar "compra"/"comprar"/"compre"** — passagem se compra, viagem de fretamento se reserva/adquire
- se pedirem "passagem" como palavra-chave de SEO, o código troca automaticamente por "viagem" antes de montar o prompt (evita o prompt se contradizer)

## Tom `informativo`

Sempre **4 parágrafos fixos**, com 3 exemplos few-shot (Guerino Seiscento, Eucatur, Expresso JK Transportes):

1. **Fundação e reconhecimento** — ano/local de fundação, tradição no setor, órgão regulador. A ANTT pode ser citada sempre que a empresa evidentemente rodar rotas interestaduais (é um fato do setor, não precisa estar na fonte); uma agência **estadual** (ARTESP, AGEMS, etc.) só pode ser citada se a fonte confirmar o estado
2. **Sede, operação e rotas** — cidade sede é **opcional**: só cita se a fonte disser explicitamente, nunca inventa pra preencher o parágrafo, e se a fonte tiver cidades conflitantes pra sede (comum quando o Google mistura empresas de nome parecido), não escolhe nenhuma às cegas
3. **Frota** — categorias de veículo e comodidades, quando a fonte trouxer
4. **Como viajar** — menção neutra à Buser, com foco em "processo 100% digital" — **não** numa lista de benefícios genéricos (isso soa promocional demais pro tom informativo)

## Tom `vendas`

Formato curto de conversão, **3 a 4 parágrafos**, com 3 exemplos few-shot (um por tipo: Eucatur linha regular, Brasil Bus híbrida, AAVA fretamento puro):

1. **Subtítulo** — sozinho, nunca colado com o parágrafo seguinte (erro grave explícito no prompt). Varia o verbo de abertura (reserve/encontre/adquira/compre) pra não repetir sempre o mesmo
2. **Apresentação breve** — o essencial, sem contar história/fundação
3. **Benefícios da Buser** — cita exatamente 3 de uma lista de 7 diferenciais (atendimento 24h, viagem segura, preço baixo, cancelamento grátis, fácil remarcação, poltrona confortável, prático de comprar/reservar online), variando quais

Proibições específicas: não usar "garante"/"garantindo"/"garantia", não usar frases de urgência, não atribuir qualidade/preço à empresa (só à Buser, a menos que esteja explícito na fonte), não fechar com frase de efeito genérica.

## Tom `promocional`

Sem few-shot. Foco exclusivo em transporte rodoviário — ignora completamente qualquer menção a outros modais (aéreo, hospedagem) que apareça na fonte. Cita a Buser logo no início, reforça pelo menos 2 dos 3 benefícios fixos (atendimento 24h, cancelamento grátis, preço que cabe no bolso). Mais estrito que os outros dois tons quanto a atribuição de qualidade: toda frase sobre a empresa tem que ser rastreável a um fato explícito na fonte.

## Revisão (grafo)

Depois de gerado e humanizado, o texto passa pelo revisor determinístico do grafo ([`grafo_descricao.py`](../grafo_descricao.py)) — ele confere, entre outras coisas, se a palavra passagem/viagem bate com a classificação e se a cidade-sede alegada realmente aparece perto de um termo de sede nas fontes. Desenho completo do grafo em [`explicacao_descricao_grafo/`](../explicacao_descricao_grafo/grafo_descricao.md).
