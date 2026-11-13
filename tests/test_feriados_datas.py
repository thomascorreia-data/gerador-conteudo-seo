"""
Testes de formatos/descricao/feriados_datas.py — cálculo de data de
feriados (fixos e móveis), sem chamar nada de IA.
"""

import datetime

from feriados_datas import (
    calcular_data_feriado,
    formatar_data_extenso,
    formatar_dia_semana,
    _pascoa,
)


# --- Páscoa (algoritmo computus) ---------------------------------------

def test_pascoa_bate_com_datas_reais_conhecidas():
    # Datas de Páscoa publicamente conhecidas/conferidas, usadas como
    # referência pra validar o algoritmo.
    assert _pascoa(2024) == datetime.date(2024, 3, 31)
    assert _pascoa(2025) == datetime.date(2025, 4, 20)
    assert _pascoa(2026) == datetime.date(2026, 4, 5)
    assert _pascoa(2027) == datetime.date(2027, 3, 28)


# --- feriados fixos -------------------------------------------------------

def test_feriado_fixo_ainda_nao_passou_usa_o_ano_atual():
    hoje = datetime.date(2026, 1, 1)  # bem no começo do ano
    data = calcular_data_feriado("Natal", hoje=hoje)
    assert data == datetime.date(2026, 12, 25)


def test_feriado_fixo_ja_passou_usa_o_ano_que_vem():
    hoje = datetime.date(2026, 12, 26)  # um dia depois do Natal
    data = calcular_data_feriado("Natal", hoje=hoje)
    assert data == datetime.date(2027, 12, 25)


def test_feriado_fixo_no_proprio_dia_conta_como_nao_passou():
    hoje = datetime.date(2026, 4, 21)  # dia exato de Tiradentes
    data = calcular_data_feriado("Tiradentes", hoje=hoje)
    assert data == datetime.date(2026, 4, 21)


# --- feriados móveis (a partir da Páscoa) ----------------------------------

def test_carnaval_e_47_dias_antes_da_pascoa():
    hoje = datetime.date(2026, 1, 1)
    data = calcular_data_feriado("Carnaval", hoje=hoje)
    assert data == _pascoa(2026) - datetime.timedelta(days=47)


def test_corpus_christi_e_60_dias_depois_da_pascoa():
    hoje = datetime.date(2026, 1, 1)
    data = calcular_data_feriado("Corpus Christi", hoje=hoje)
    assert data == _pascoa(2026) + datetime.timedelta(days=60)


def test_feriado_movel_ja_passado_no_ano_usa_proximo_ano():
    # Carnaval 2026 é antes de abril — em dezembro de 2026 já passou.
    hoje = datetime.date(2026, 12, 1)
    data = calcular_data_feriado("Carnaval", hoje=hoje)
    assert data == _pascoa(2027) - datetime.timedelta(days=47)


# --- normalização / não reconhecido ----------------------------------------

def test_nome_com_acento_ou_caixa_diferente_ainda_reconhece():
    hoje = datetime.date(2026, 1, 1)
    assert calcular_data_feriado("CARNAVAL", hoje=hoje) == calcular_data_feriado("Carnaval", hoje=hoje)
    assert calcular_data_feriado("páscoa", hoje=hoje) is not None


def test_feriado_nao_reconhecido_devolve_none():
    assert calcular_data_feriado("Dia do Padroeiro de Lugar Nenhum") is None


# --- formatação -------------------------------------------------------------

def test_formatar_data_extenso():
    assert formatar_data_extenso(datetime.date(2027, 2, 9)) == "9 de fevereiro de 2027"


def test_formatar_dia_semana():
    # 9 de fevereiro de 2027 é uma terça-feira.
    assert formatar_dia_semana(datetime.date(2027, 2, 9)) == "terça-feira"
