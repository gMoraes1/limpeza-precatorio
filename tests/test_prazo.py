from datetime import date

import pytest

from limpeza.normalizacao import normalizar_data
from limpeza.prazo import calcular_prazo


@pytest.mark.parametrize("apresentado_em, prazo_esperado", [
    (date(2025, 1, 1), date(2026, 12, 31)),
    (date(2025, 4, 2), date(2026, 12, 31)),
    (date(2025, 4, 3), date(2027, 12, 31)),
    (date(2025, 12, 31), date(2027, 12, 31)),
    (date(2024, 2, 29), date(2025, 12, 31)),
])
def test_regra_de_2_de_abril(apresentado_em, prazo_esperado):
    assert calcular_prazo(apresentado_em) == prazo_esperado


def test_madrugada_utc_de_3_de_abril_ainda_e_2_de_abril_em_brasilia():
    apresentado_em = normalizar_data("2025-04-03T01:00:00Z")
    assert apresentado_em == date(2025, 4, 2)
    assert calcular_prazo(apresentado_em) == date(2026, 12, 31)


def test_noite_de_2_de_abril_com_fuso_de_brasilia():
    apresentado_em = normalizar_data("2025-04-02T23:30:00-03:00")
    assert calcular_prazo(apresentado_em) == date(2026, 12, 31)


def test_3_de_abril_de_manha_em_brasilia_ja_passou_do_limite():
    apresentado_em = normalizar_data("2025-04-03T12:00:00Z")
    assert calcular_prazo(apresentado_em) == date(2027, 12, 31)
