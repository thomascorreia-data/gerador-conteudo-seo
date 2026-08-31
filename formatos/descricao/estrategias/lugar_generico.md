# Estratégia — Lugar Genérico

Categoria pra lugares que não são cidade, ponto turístico "clássico" nem terminal — shopping, comércio, restaurante, hotel, aeroporto, etc. Estrutura livre, sem few-shot, mesmo estilo de [cidade](cidade.md) e [ponto turístico](ponto_turistico.md).

## De onde vêm os dados: só Wikipédia, sem geocodificação

Diferente de [ponto_turistico](ponto_turistico.md) e [terminal_rodoviaria](terminal_rodoviaria.md), a coleta pra `lugar_generico` ([`base_lugares_genericos.py`](../base_lugares_genericos.py)) não usa Nominatim nem precisa identificar cidade antes: o próprio nome do lugar já é a chave de busca direta na Wikipédia (`https://pt.wikipedia.org/wiki/{lugar}`). É a categoria mais simples de coletar do projeto — sem geocodificação, sem múltiplas fontes, só uma raspagem direta da introdução do artigo.

Se a página não existir, for uma página de desambiguação, ou não tiver parágrafo nenhum, a coleta não levanta exceção — devolve `"conteudo": None` e um `"erro"` explicando o motivo. Isso aciona o fallback "sem fontes" que existe no grafo pra qualquer categoria (ver [`explicacao_descricao_grafo/grafo_descricao.md`](../explicacao_descricao_grafo/grafo_descricao.md)): o texto é gerado do conhecimento geral do modelo, e o resultado final sai marcado com `"sem_fontes": true` (e um `"aviso"` explicando isso, em `gerando.py`/na interface). Nomes bem conhecidos (grandes shoppings, aeroportos, hotéis famosos) costumam ter artigo na Wikipédia e saem com dado real; nomes muito genéricos ou pouco conhecidos caem no fallback.

## Os 3 tons

Mesmo padrão de `cidade`/`ponto_turistico`:
- **`informativo`** — factual: o que é o lugar, onde fica, o que oferece, por que é relevante
- **`vendas`** — cita a Buser e exatamente 3 dos 7 diferenciais (mesma lista das outras categorias), com chamada pra ação
- **`promocional`** — envolvente, cita a Buser, sem CTA direto

## Quando vale evoluir a coleta

Se páginas ambíguas ou nomes muito genéricos virarem um problema recorrente (caindo no fallback com frequência), vale considerar outras fontes além da Wikipédia (site oficial do lugar, Google) — mesmo caminho que [evento](evento.md) já percorreu ao lidar com nomes de eventos que colidem com uma versão internacional mais famosa e homônima.
