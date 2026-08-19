# Grafo de geração de descrições

Visualização do grafo implementado em [`grafo_descricao.py`](grafo_descricao.py). A imagem abaixo (`grafo_descricao.png`) e o código-fonte do diagrama (`grafo_descricao.mmd`) foram gerados direto do grafo compilado (`_GRAFO.get_graph().draw_mermaid()` / `draw_mermaid_png()`) — não são um desenho à mão, então qualquer mudança nos nós/arestas do código é refletida aqui só rodando de novo o comando no final deste arquivo.

![Grafo de geração de descrições](grafo_descricao.png)

## Como ler

- **Só a coleta é ramificada por categoria** (`coletar_cidade`, `coletar_empresa`, `coletar_ponto_turistico`, `coletar_terminal_rodoviaria`) — cada uma chama seu `base_*.py` correspondente. Categorias sem coletor implementado (`estado`, `país`, `evento`, `lugar_genérico`) caem em `categoria_nao_implementada`, que só levanta `NotImplementedError` (a aresta pro `__end__` existe só porque todo nó do LangGraph precisa levar a algum lugar — na prática a exceção sobe antes disso).
- **`gerar` → `humanizar` → `revisor` são nós únicos**, compartilhados por qualquer categoria que chegue até eles — assim como o humanizador já funciona hoje (roda pra toda descrição, não só empresa).
- **O único ciclo do grafo** é `revisor -- tentar_de_novo --> incrementar_tentativa --> gerar`: se o revisor reprovar e ainda houver tentativas sobrando (teto de 3, em `MAX_TENTATIVAS`), o texto é gerado de novo do zero. Se reprovar 3x seguidas, cai em `marcar_erro` e sai com o campo `erro` preenchido em vez de um texto.
- **O revisor é determinístico** (sem LLM) — confere palavra banida, contagem de palavras, e duas checagens condicionais: passagem/viagem (só se a categoria for empresa) e estrutura de 3-4 parágrafos (só se o tom for vendas).

## Como regenerar

```bash
python -c "from grafo_descricao import _GRAFO; \
    open('grafo_descricao.mmd', 'w', encoding='utf-8').write(_GRAFO.get_graph().draw_mermaid()); \
    open('grafo_descricao.png', 'wb').write(_GRAFO.get_graph().draw_mermaid_png())"
```

(`draw_mermaid_png()` usa a API pública do mermaid.ink pra renderizar — precisa de internet; `draw_mermaid()` sozinho já dá o texto do diagrama, sem depender de rede.)
