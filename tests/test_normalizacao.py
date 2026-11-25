from datetime import date
from decimal import Decimal

import pytest

from limpeza.normalizacao import (
    formatar_processo,
    normalizar_data,
    normalizar_nome,
    normalizar_processo,
    normalizar_valor,
)


@pytest.mark.parametrize("bruto, esperado", [
    ("2.500,50", Decimal("2500.50")),
    ("45.000,00", Decimal("45000.00")),
    ("45000.00", Decimal("45000.00")),
    (15000.0, Decimal("15000.00")),
    (8000, Decimal("8000.00")),
    (-200, Decimal("-200.00")),
])
def test_valor_em_formatos_aceitos(bruto, esperado):
    assert normalizar_valor(bruto) == esperado


@pytest.mark.parametrize("bruto", [None, "", "   ", "abc", True])
def test_valor_invalido_ou_ausente_levanta_erro(bruto):
    with pytest.raises(ValueError):
        normalizar_valor(bruto)


def test_valor_ambiguo_nao_e_adivinhado():
    with pytest.raises(ValueError, match="ambíguo"):
        normalizar_valor("1.500")


def test_processo_com_e_sem_pontuacao_geram_a_mesma_chave():
    com_pontuacao = normalizar_processo("0023456-21.2020.8.26.0053")
    sem_pontuacao = normalizar_processo("00234562120208260053")
    assert com_pontuacao == sem_pontuacao == "00234562120208260053"
    assert formatar_processo(com_pontuacao) == "0023456-21.2020.8.26.0053"


@pytest.mark.parametrize("bruto", ["", None, "123", 234562120208260053])
def test_processo_incompleto_levanta_erro(bruto):
    with pytest.raises(ValueError):
        normalizar_processo(bruto)


@pytest.mark.parametrize("bruto", ["2025-04-10", "10/04/2025", "2025-04-10T09:00:00-03:00"])
def test_data_em_formatos_aceitos(bruto):
    assert normalizar_data(bruto) == date(2025, 4, 10)


@pytest.mark.parametrize("bruto", ["31/02/2025", "2025-13-01", "ontem", ""])
def test_data_invalida_levanta_erro(bruto):
    with pytest.raises(ValueError):
        normalizar_data(bruto)


def test_nome_do_ente_ignora_acento_e_caixa():
    assert normalizar_nome("MUNICIPIO DE SAO PAULO") == normalizar_nome("Município de  São Paulo")
    assert normalizar_nome("Município de Santos") != normalizar_nome("União")
