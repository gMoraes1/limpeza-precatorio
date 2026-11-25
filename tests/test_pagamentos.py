from decimal import Decimal

from limpeza.pagamentos import limpar_pagamentos, total_por_processo
from limpeza.relatorio import DESCARTADO, DUVIDA, Relatorio

PROCESSO = "0012345-10.2019.8.26.0053"
CHAVE = "00123451020198260053"


def evento(**campos) -> dict:
    padrao = {
        "evento_id": "ev-1",
        "processo": PROCESSO,
        "valor": 1000,
        "data_pagamento": "2025-03-10",
        "tipo": "pagamento",
        "atualizado_em": "2025-03-10T10:00:00-03:00",
    }
    return padrao | campos


def limpar(eventos):
    relatorio = Relatorio()
    pagamentos = limpar_pagamentos(eventos, {CHAVE}, relatorio)
    return pagamentos, relatorio


def test_copia_identica_conta_uma_vez():
    pagamentos, relatorio = limpar([evento(), evento()])
    assert total_por_processo(pagamentos) == {CHAVE: Decimal("1000.00")}
    assert len(relatorio.do_tipo(DESCARTADO)) == 1


def test_reimportar_o_mesmo_arquivo_nao_muda_o_total():
    arquivo = [evento(evento_id="ev-1"), evento(evento_id="ev-2", valor=500)]
    uma_vez, _ = limpar(arquivo)
    duas_vezes, _ = limpar(arquivo + arquivo)
    assert total_por_processo(uma_vez) == total_por_processo(duas_vezes) == {CHAVE: Decimal("1500.00")}


def test_versao_mais_recente_vence_mesmo_vindo_antes_no_arquivo():
    nova = evento(valor=15500, atualizado_em="2025-03-11T09:00:00-03:00")
    antiga = evento(valor=15000, atualizado_em="2025-03-10T10:00:00-03:00")
    pagamentos, _ = limpar([nova, antiga])
    assert [p.valor for p in pagamentos] == [Decimal("15500.00")]


def test_mesmo_atualizado_em_com_conteudo_diferente_vira_duvida():
    _, relatorio = limpar([evento(valor=100), evento(valor=200)])
    assert len(relatorio.do_tipo(DUVIDA)) == 1


def test_estorno_anula_o_pagamento():
    pagamentos, _ = limpar([
        evento(evento_id="ev-6", valor=5000),
        evento(evento_id="ev-7", valor=5000, tipo="estorno"),
    ])
    assert total_por_processo(pagamentos) == {CHAVE: Decimal("0.00")}


def test_pagamento_negativo_nao_entra_na_soma():
    pagamentos, relatorio = limpar([evento(valor=-200)])
    assert pagamentos == []
    assert "negativo" in relatorio.do_tipo(DUVIDA)[0].motivo


def test_evento_invalido_nunca_some_em_silencio():
    pagamentos, relatorio = limpar([
        evento(evento_id="ev-4", valor=None),
        evento(evento_id="ev-10", processo=""),
        evento(evento_id="ev-x", tipo="ajuste"),
    ])
    assert pagamentos == []
    assert len(relatorio.do_tipo(DUVIDA)) == 3


def test_processo_desconhecido_fica_fora_e_vira_duvida():
    pagamentos, relatorio = limpar([evento(processo="0067890-65.2016.8.26.0053")])
    assert pagamentos == []
    assert "não existe" in relatorio.do_tipo(DUVIDA)[0].motivo
