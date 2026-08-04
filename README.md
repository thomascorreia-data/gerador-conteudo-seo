# Central de Geração de Conteúdo SEO

Ferramenta interna pra gerar conteúdo de SEO (hoje, o formato **Descrição**). Você lista os temas (cidades, pontos
turísticos, etc.), e o sistema coleta informações reais sobre cada um e usa
IA pra escrever um texto original a partir delas.

## Como funciona (visão simples)

O fluxo é uma esteira com 4 passos, do momento em que você digita um tema
até o texto pronto na tela:

```
1. INTERFACE            2. NORMALIZAÇÃO         3. INTERPRETAÇÃO + COLETA        4. GERAÇÃO COM IA
   (navegador)              (transformacaoJson)     (interpretador_descricao)        (interacao_ia)

Você preenche:          Transforma o que você    Pra cada tema, identifica a      Pega o que foi coletado,
- Tema(s)                preencheu (que pode      categoria (cidade, ponto        monta um prompt (de
- Tom (informativo/       variar por tema ou       turístico, terminal            acordo com a categoria +
  vendas/promocional)     ser igual pra todos)     rodoviário, etc.) e busca       o tom) e chama o modelo
- Média de palavras       numa lista simples,      informações reais sobre         de IA pra escrever o
- Palavras-chave          um item por tema.        aquele tema (raspagem de        texto final.
                                                    Wikipédia, sites de
                                                    passagem, etc.)
```

Cada passo alimenta o próximo:

1. **Interface** ([interface/gerador-json.html](interface/gerador-json.html)) — você monta o pedido: um ou
   vários temas, tom de voz, tamanho aproximado do texto e palavras-chave de SEO.
2. **Normalização** ([formatos/transformacaoJson.py](formatos/transformacaoJson.py)) — a API recebe esse
   pedido e transforma numa lista simples e padronizada, um item por tema.
3. **Interpretação + coleta** ([formatos/descricao/interpretador_descricao.py](formatos/descricao/interpretador_descricao.py)) —
   pra cada tema, a IA identifica a categoria (cidade, ponto turístico, terminal
   rodoviário, ...) e o sistema busca informações reais sobre esse tema em
   fontes como Wikipédia e sites de passagem (`formatos/descricao/base_*.py`).
4. **Geração com IA** ([formatos/descricao/interacao_ia.py](formatos/descricao/interacao_ia.py)) — com o
   material coletado em mãos, monta um prompt (escolhido de acordo com a
   categoria e o tom, a partir de [prompts_descricao.json](formatos/descricao/prompts_descricao.json))
   e pede pro modelo escrever o texto final, respeitando o tamanho e citando
   as palavras-chave pedidas.

O resultado aparece na própria interface, com a categoria e o tom usados em
cada item, e pode ser copiado, baixado em `.json` ou exportado em `.csv`.

> **Cobertura atual:** só as categorias **cidade** e **ponto turístico** têm
> coleta de dados e prompts de geração prontos. As demais (estado, país,
> bairro, evento, empresa, terminal rodoviário) ainda não geram texto —
> aparecem como erro no resultado até serem implementadas.

## Como executar localmente

### 1. Pré-requisitos

- Python 3.13+ instalado
- Uma chave de API da OpenAI

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
