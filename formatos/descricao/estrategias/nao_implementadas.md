# Categorias ainda não implementadas

`estado`, `pais`, `lugar_generico` e `evento` não têm nem coleta de dados nem prompt de geração — em [`prompts_descricao.json`](../prompts_descricao.json) os 3 tons de cada uma são objetos vazios (`{}`), e não existe nenhum `base_estado.py`/`base_pais.py`/etc. em [`formatos/descricao/`](../).

O classificador de tema (`classificar_tema`, em [`interpretador_descricao.py`](../interpretador_descricao.py)) já reconhece essas 4 categorias — só a coleta e a geração é que faltam. No grafo ([`grafo_descricao.py`](../grafo_descricao.py)), um tema classificado como qualquer uma delas cai no nó `categoria_nao_implementada`, que levanta `NotImplementedError` de propósito, em vez de travar o restante do lote — a interface mostra isso como erro só naquele item.

Pra implementar qualquer uma: seguir o mesmo caminho de [terminal_rodoviaria](terminal_rodoviaria.md) (que já tem meio caminho andado) — primeiro um `base_<categoria>.py` com uma função de coleta, depois um nó novo no grafo, e só depois os templates de prompt em `prompts_descricao.json`.
