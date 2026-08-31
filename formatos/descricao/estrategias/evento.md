# Estratégia — Evento

Categoria pra festivais, shows, feiras, festas populares e afins. Mesmo estilo de [lugar_generico](lugar_generico.md): estrutura livre, sem few-shot.

## De onde vêm os dados: só Wikipédia, sem geocodificação

Mesma receita de `lugar_generico` ([`base_eventos.py`](../base_eventos.py)): sem Nominatim, sem múltiplas fontes — o nome do evento já é a chave de busca direta na Wikipédia (`https://pt.wikipedia.org/wiki/{evento}`).

Uma diferença importante em relação a `lugar_generico`: vários eventos brasileiros são a edição local de um evento internacional homônimo bem mais famoso — o caso encontrado em teste foi "Oktoberfest de Blumenau": o classificador de tema devolveu `entidade: "Oktoberfest"` e `cidade: "Blumenau"` separados (mesmo o tema original já vindo com a cidade junto), e buscar só "Oktoberfest" na Wikipédia cai na festa original de Munique, não na de Blumenau — dado errado, mas sem erro nenhum pra sinalizar o problema (a página existe, só que é a errada). Pra cobrir esse caso, `coletar_evento` recebe também a `cidade` identificada e, quando ela ainda não está contida no nome do evento, tenta primeiro `"{evento} de {cidade}"` (padrão comum de título na Wikipédia pra esses casos — também funciona pra "Carnaval de Salvador", "Festa Junina de Campina Grande" etc.) antes de cair pro nome sozinho. Eventos cujo nome já é específico o bastante (ex: "Rock in Rio") não são afetados: a tentativa com cidade falha (não existe essa página) e a busca cai pro nome original normalmente.

Se nenhuma tentativa trouxer conteúdo (página ausente, desambiguação, ou nenhum parágrafo), a coleta não levanta exceção — devolve `"conteudo": None` e um `"erro"` explicando o motivo, o que aciona o mesmo fallback "sem fontes" das outras categorias (ver [`explicacao_descricao_grafo/grafo_descricao.md`](../explicacao_descricao_grafo/grafo_descricao.md)).

## Os 3 tons

Mesmo padrão de `lugar_generico`, adaptado pro contexto de evento:
- **`informativo`** — factual: o que é o evento, onde acontece, o que celebra/apresenta, por que é relevante
- **`vendas`** — cita a Buser e exatamente 3 dos 7 diferenciais (mesma lista das outras categorias), com chamada pra ação
- **`promocional`** — envolvente, cita a Buser, sem CTA direto

Todos os 3 tons incluem uma instrução explícita pra não inventar datas/edições/atrações que não estejam nas fontes — evento muda de ano pra ano, e uma data errada é pior do que nenhuma data.
