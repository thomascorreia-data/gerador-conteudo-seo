# Estratégia — Terminal Rodoviário

Estrutura livre (sem parágrafos fixos, sem few-shot) — igual [cidade](cidade.md) e [ponto turístico](ponto_turistico.md), não igual [empresa](empresa.md). Faz sentido: um terminal não tem "tipo de empresa" pra classificar (não existe ambiguidade passagem/viagem — quem embarca ali sempre compra passagem de linha regular).

## De onde vêm os dados

[`base_rodoviarias.py`](../base_rodoviarias.py) recebe só o nome do terminal (ex: "Rodoviária do Tietê"), descobre cidade/UF automaticamente por geocodificação (Nominatim) e coleta descrição em duas fontes: **QueroPassagem** e **Wikipédia**.

**Limitação conhecida, herdada da geocodificação**: pra nomes ambíguos ou pouco comuns, o Nominatim pode casar com o lugar errado — testado com "Terminal Rodoviário de Brasília", ele achou um bairro chamado "Brasília" dentro de Formiga (MG), não o Distrito Federal, e as duas fontes 404aram por causa disso. Usar o nome oficial mais específico (ex: "Rodoviária do Plano Piloto") contorna isso. É o mesmo tipo de falha que motivou o fallback de [ponto_turistico](ponto_turistico.md) pra cidade não encontrada — aqui ainda não tem esse fallback, é um candidato a melhoria futura se aparecer com frequência.

## Os 3 tons

- **`informativo`** — dados factuais: localização (cidade/bairro), principais destinos e empresas que operam ali, estrutura do terminal (plataformas, serviços), quando a fonte trouxer. Sem menção à Buser
- **`vendas`** — mesmo padrão de `empresa`/`cidade`/`ponto_turistico`: cita a Buser explicitamente e exatamente 3 dos 7 diferenciais (ver lista em qualquer um desses), variando quais
- **`promocional`** — destaca praticidade e destinos disponíveis de forma envolvente, cita a Buser sem chamada direta pra compra

Testado com dois terminais reais (Rodoviária do Tietê, Rodoviária do Plano Piloto) nos 3 tons — todos aprovaram de primeira, sem retry.
