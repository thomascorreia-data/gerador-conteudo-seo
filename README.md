# Central de Geração de Conteúdo SEO

Ferramenta interna pra gerar conteúdo de SEO (hoje, o formato **Descrição**). Você lista os temas (cidades, pontos
turísticos, etc.), e o sistema coleta informações reais sobre cada um e usa
IA pra escrever um texto original a partir delas.

## Como funciona (visão simples)

O fluxo é uma esteira com 3 passos, do momento em que você digita um tema
até o texto pronto na tela:

```
1. INTERFACE            2. NORMALIZAÇÃO         3. GRAFO DE GERAÇÃO
   (navegador)              (transformacaoJson)     (grafo_descricao)

Você preenche:          Transforma o que você    Pra cada tema: identifica a categoria,
- Tema(s)                preencheu (que pode      coleta dados reais, gera o texto,
- Tom (informativo/       variar por tema ou       humaniza e revisa — voltando a gerar
  vendas/promocional)     ser igual pra todos)     de novo se a revisão reprovar, até
- Média de palavras       numa lista simples,      um teto de tentativas.
- Palavras-chave          um item por tema.
```

Cada passo alimenta o próximo:

1. **Interface** ([interface/gerador-json.html](interface/gerador-json.html)) — você monta o pedido: um ou
   vários temas, tom de voz, tamanho aproximado do texto e palavras-chave de SEO.
2. **Normalização** ([formatos/transformacaoJson.py](formatos/transformacaoJson.py)) — a API recebe esse
   pedido e transforma numa lista simples e padronizada, um item por tema.
3. **Grafo de geração** ([formatos/descricao/grafo_descricao.py](formatos/descricao/grafo_descricao.py),
   implementado com [LangGraph](https://github.com/langchain-ai/langgraph)) — pra cada tema:
   1. identifica a categoria (cidade, ponto turístico, empresa, ...);
   2. coleta informações reais sobre esse tema, num coletor específico por categoria
      (`formatos/descricao/base_*.py` — raspagem de Wikipédia/sites, ou SerpApi no caso de empresa);
   3. monta o prompt certo (categoria × tom, a partir de
      [prompts_descricao.json](formatos/descricao/prompts_descricao.json)) e gera o texto;
   4. humaniza o texto gerado;
   5. revisa o resultado — primeiro um revisor determinístico (regras de string, sem custo de IA),
      depois um revisor de IA (só tom) — e volta pro passo 3 se algum reprovar, até um teto de tentativas.
      Mesmo esgotando as tentativas, a última versão gerada é devolvida (com um aviso), nunca nada.

   Desenho completo do grafo (com o motivo de cada decisão) em
   [`formatos/descricao/explicacao_descricao_grafo/`](formatos/descricao/explicacao_descricao_grafo/grafo_descricao.md).
   A estratégia de prompt de cada categoria — o que cada uma pede e por quê — está documentada em
   [`formatos/descricao/estrategias/`](formatos/descricao/estrategias/README.md).

O resultado aparece na própria interface, com a categoria e o tom usados em
cada item, e pode ser copiado, baixado em `.json` ou exportado em `.csv`.

> **Cobertura atual:** as categorias **empresa**, **cidade** e **ponto turístico**
> têm coleta de dados e prompts de geração prontos (nos 3 tons: informativo,
> vendas e promocional). **Terminal rodoviário** tem só a coleta pronta — a
> geração de texto ainda não tem prompt. As demais (estado, país, lugar
> genérico, evento) ainda não têm nada implementado — aparecem como erro no
> resultado. Detalhes por categoria em
> [`formatos/descricao/estrategias/`](formatos/descricao/estrategias/README.md).

## Como executar localmente

### 1. Pré-requisitos

- Python 3.13+ instalado
- Uma chave de API da OpenAI
- Uma chave da [SerpApi](https://serpapi.com/) — só necessária pra gerar
  descrições da categoria **empresa** (as demais categorias raspam sites
  diretamente, sem API paga)

### 2. Configurar o ambiente

Na raiz do projeto, ative o ambiente virtual (`venv`) já existente e instale
as dependências:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz do projeto (mesmo nível deste README) com a
sua chave da OpenAI:

```
OPENAI_API_KEY=sk-...
SERPAPI_API_KEY=...
```

### 3. Rodar

Com o ambiente virtual ativado, na raiz do projeto:

```powershell
python start.py
```

Isso sobe a API em `http://127.0.0.1:8000` e já abre a interface no
navegador. Pra encerrar, aperte `Ctrl+C` na janela do terminal.

Se preferir não ativar o venv, dá pra rodar direto com:

```powershell
.\venv\Scripts\python.exe start.py
```

### 4. Usar

1. Preencha requisitor, formato (**Descrição**), tom e tamanho padrão.
2. Liste os temas (um por linha, ou um cartão por tema se quiser valores
   diferentes por item).
3. Clique em **"Gerar JSON de entrada"** — a lista normalizada aparece na
   tela.
4. Clique em **"Gerar conteúdo com IA"** — o sistema identifica a categoria
   de cada tema, coleta as informações e escreve o texto.
5. Copie o resultado, baixe o `.json` ou exporte o `.csv` (com tema,
   categoria identificada, tom e o texto gerado).
