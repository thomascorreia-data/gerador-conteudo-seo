"""
Calcula a data exata (já no futuro) de feriados nacionais brasileiros
conhecidos — pra NÃO depender do modelo fazer essa conta sozinho, que é
exatamente onde ele errava (ex: afirmou "Carnaval é 60 dias antes da
Páscoa", quando o certo é 47 dias — uma vez acertou, outra vez errou,
prova que não é confiável pra aritmética de calendário).

Usado por grafo_descricao.py: calcula a data real e injeta ela PRONTA no
prompt, pro modelo só repetir o valor já calculado em vez de inventar.
"""

import datetime

from unidecode import unidecode


def _pascoa(ano: int) -> datetime.date:
    """Data do Domingo de Páscoa pro ano dado, calendário gregoriano —
    algoritmo computus de Gauss/Meeus (o mesmo usado por softwares de
    calendário litúrgico, não é aproximação)."""
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(ano, mes, dia)


# Feriados nacionais com data FIXA (mês, dia) no calendário civil.
FERIADOS_FIXOS = {
    "ano novo": (1, 1),
    "confraternizacao universal": (1, 1),
    "tiradentes": (4, 21),
    "dia do trabalho": (5, 1),
    "dia do trabalhador": (5, 1),
    "independencia do brasil": (9, 7),
    "independencia": (9, 7),
    "nossa senhora aparecida": (10, 12),
    "nossa senhora de aparecida": (10, 12),
    "finados": (11, 2),
    "proclamacao da republica": (11, 15),
    "natal": (12, 25),
}

# Feriados MÓVEIS, calculados a partir da Páscoa (offset em dias — negativo
# é antes da Páscoa, positivo é depois). Valores conferidos contra o
# calendário litúrgico oficial, não adivinhados.
FERIADOS_MOVEIS_OFFSET_PASCOA = {
    "carnaval": -47,  # terça-feira de carnaval
    "sexta-feira santa": -2,
    "sexta feira santa": -2,
    "paixao de cristo": -2,
    "pascoa": 0,
    "domingo de pascoa": 0,
    "corpus christi": 60,
}


def _normalizar(nome: str) -> str:
    """Sem acento, minúsculo — mesma receita de slugify já usada no
    projeto (ver base_cidade.py), só que sem trocar espaço por hífen."""
    return unidecode(nome or "").strip().lower()


def _data_do_feriado_no_ano(chave_normalizada: str, ano: int):
    if chave_normalizada in FERIADOS_FIXOS:
        mes, dia = FERIADOS_FIXOS[chave_normalizada]
        return datetime.date(ano, mes, dia)
    if chave_normalizada in FERIADOS_MOVEIS_OFFSET_PASCOA:
        offset = FERIADOS_MOVEIS_OFFSET_PASCOA[chave_normalizada]
        return _pascoa(ano) + datetime.timedelta(days=offset)
    return None


def calcular_data_feriado(nome_feriado: str, hoje: datetime.date = None) -> datetime.date:
    """Devolve a próxima ocorrência (a partir de `hoje`) do feriado dado,
    calculada com fórmula verificada — ou None se o nome não for
    reconhecido (feriado regional/municipal, ou nome fora do padrão).

    Se a data desse feriado já passou neste ano, devolve a data do ano que
    vem, em vez da que já ficou pra trás — é sempre uma data futura."""
    hoje = hoje or datetime.date.today()
    chave = _normalizar(nome_feriado)

    data_este_ano = _data_do_feriado_no_ano(chave, hoje.year)
    if data_este_ano is None:
        return None
    if data_este_ano >= hoje:
        return data_este_ano
    return _data_do_feriado_no_ano(chave, hoje.year + 1)


_MESES_PT = [
    None, "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
_DIAS_SEMANA_PT = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]


def formatar_data_extenso(data: datetime.date) -> str:
    """'22 de fevereiro de 2027' — sem zero à esquerda no dia, mês por
    extenso em português, igual o padrão de redação do projeto."""
    return f"{data.day} de {_MESES_PT[data.month]} de {data.year}"


def formatar_dia_semana(data: datetime.date) -> str:
    return _DIAS_SEMANA_PT[data.weekday()]


if __name__ == "__main__":
    for nome in ("Carnaval", "Corpus Christi", "Natal", "Tiradentes", "Ano Novo"):
        d = calcular_data_feriado(nome)
        if d:
            print(f"{nome}: {formatar_data_extenso(d)} ({formatar_dia_semana(d)})")
        else:
            print(f"{nome}: não reconhecido")
