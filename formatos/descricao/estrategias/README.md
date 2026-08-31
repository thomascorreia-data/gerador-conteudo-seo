# Estratégias de geração por categoria

Cada categoria de tema (`empresa`, `cidade`, `ponto_turistico`, ...) tem seu próprio jeito de coletar dados e seu próprio prompt por tom, guardado em [`../prompts_descricao.json`](../prompts_descricao.json). Esta pasta documenta, categoria por categoria, **por que o prompt é feito do jeito que é** — não só o que ele pede, mas o problema real que cada regra resolveu.

## Categorias com geração pronta

- [**Empresa**](empresa.md) — a mais desenvolvida: classificação automática de tipo (linha regular/híbrida/fretamento), 3 tons com few-shot, revisor com checagens específicas (passagem/viagem, sede)
- [**Cidade**](cidade.md) — texto livre, sem few-shot, 3 tons
- [**Ponto turístico**](ponto_turistico.md) — estrutura parecida com cidade, com uma nota sobre um risco já conhecido
- [**Terminal rodoviário**](terminal_rodoviaria.md) — mesmo padrão de cidade/ponto turístico, sem classificação de tipo
- [**Lugar genérico**](lugar_generico.md) — prompt pronto, mas sem coletor de verdade ainda: todo texto sai do conhecimento geral do modelo, sinalizado com aviso

## Categorias não implementadas

- [**Estado, país, evento**](nao_implementadas.md) — nada implementado ainda (nem coleta, nem prompt)

## Como esse conteúdo é usado

O ponto de entrada da geração é o grafo em [`../grafo_descricao.py`](../grafo_descricao.py) — desenho completo (com o motivo de cada decisão de arquitetura) em [`../explicacao_descricao_grafo/grafo_descricao.md`](../explicacao_descricao_grafo/grafo_descricao.md). Estes documentos aqui são sobre o **conteúdo dos prompts**; aquele outro é sobre o **fluxo que os executa** (geração → humanização → revisão → retry).
