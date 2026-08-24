# Estratégia — Cidade

Categoria mais simples do projeto: texto livre (sem estrutura de parágrafos fixa) e sem exemplos few-shot. Template em [`prompts_descricao.json`](../prompts_descricao.json), coleta em [`base_cidade.py`](../base_cidade.py).

## De onde vêm os dados

[`base_cidade.py`](../base_cidade.py) raspa diretamente uma lista configurada de sites com informação de cidades (sem API paga) mais a Wikipédia, usando seletores CSS específicos por site.

## Os 3 tons

Nenhum dos três tem estrutura de parágrafo fixa nem exemplo — a diferença entre eles é só a instrução de tom:

- **`informativo`** — dados factuais, pontos de interesse, contexto histórico/geográfico, motivos comuns de viagem. Regra específica no fechamento: não force uma menção a ônibus/transporte só por forçar — se mencionar, varie a forma e conecte com algo específico já dito sobre a cidade (distância, região, perfil de quem visita), em vez de repetir sempre a mesma fórmula genérica
- **`vendas`** — foco em converter o leitor em viajante, com gatilho de urgência/oportunidade quando fizer sentido e chamada pra ação. Cita a Buser explicitamente, mas com termos neutros ("viajar", "sua viagem") em vez de assumir compra de passagem avulsa — nem toda cidade é atendida por linha regular, algumas só por fretamento/turismo
- **`promocional`** — destaca atrativos turísticos de forma envolvente, sem chamada direta pra compra. Cita a Buser como opção pra chegar até a cidade

## Por que não tem few-shot aqui

Ao contrário de `empresa`, essa categoria nunca teve um problema recorrente (tipo o passagem/viagem) que justificasse exemplo fixo — a variação natural entre cidades diferentes (histórico, geografia, motivo de visita) já é grande o suficiente pra não colar tudo no mesmo molde. Se aparecer um padrão de erro repetido aqui, vale considerar o mesmo caminho que `empresa` já percorreu: regra em texto primeiro, exemplo few-shot se a regra sozinha não bastar, checagem determinística no revisor se nem o exemplo resolver.
