from datetime import date
from pathlib import Path

from limpeza.leitura import ler_csv, ler_json
from limpeza.normalizacao import formatar_processo
from limpeza.pagamentos import limpar_pagamentos
from limpeza.precatorios import (
    ARQ_HUB,
    ARQ_TRIBUNAL,
    ler_apresentacoes,
    ler_cadastro,
    montar_precatorios,
    somar_pagamentos,
)
from limpeza.relatorio import CORRIGIDO, DESCARTADO, DUVIDA, Relatorio
from limpeza.saida import salvar_pagamentos, salvar_precatorios

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "exemplo" / "dados"
PASTA_SAIDA = RAIZ / "saida"


def main():
    hoje = date.today()
    relatorio = Relatorio()

    hub = ler_cadastro(ler_csv(PASTA_DADOS / ARQ_HUB, relatorio), ARQ_HUB, "processo", "ente", relatorio)
    tribunal = ler_cadastro(
        ler_csv(PASTA_DADOS / ARQ_TRIBUNAL, relatorio), ARQ_TRIBUNAL, "numero_processo", "ente_devedor", relatorio
    )
    apresentacoes = ler_apresentacoes(ler_json(PASTA_DADOS / "apresentacoes.json"), relatorio)
    precatorios = montar_precatorios(hub, tribunal, apresentacoes, relatorio)

    eventos = ler_json(PASTA_DADOS / "pagamentos.json")
    pagamentos = limpar_pagamentos(eventos, set(precatorios), relatorio)
    somar_pagamentos(precatorios, pagamentos, relatorio)

    pagamentos.sort(key=lambda p: (p.processo, p.data_pagamento, p.evento_id))
    PASTA_SAIDA.mkdir(exist_ok=True)
    salvar_precatorios(list(precatorios.values()), PASTA_SAIDA / "precatorios.csv", hoje)
    salvar_pagamentos(pagamentos, PASTA_SAIDA / "pagamentos.csv")
    relatorio.salvar_csv(PASTA_SAIDA / "ocorrencias.csv")
    relatorio.salvar_markdown(PASTA_SAIDA / "relatorio.md", _resumo(precatorios, pagamentos, eventos, relatorio, hoje))

    print(f"Pronto. {len(relatorio.do_tipo(DUVIDA))} dúvidas; veja {PASTA_SAIDA / 'relatorio.md'}")


def _resumo(precatorios, pagamentos, eventos, relatorio, hoje) -> list[str]:
    vencidos = [p for p in precatorios.values() if p.vencido_em(hoje)]
    total_pago = sum(p.total_pago for p in precatorios.values())
    return [
        f"Data de referência: {hoje:%d/%m/%Y}",
        f"Precatórios na base: {len(precatorios)}",
        f"Eventos de pagamento lidos: {len(eventos)}; na base: {len(pagamentos)}",
        f"Total pago (pagamentos menos estornos): R$ {total_pago}",
        f"Ocorrências: {len(relatorio.do_tipo(CORRIGIDO))} corrigidas, "
        f"{len(relatorio.do_tipo(DESCARTADO))} descartadas, {len(relatorio.do_tipo(DUVIDA))} dúvidas",
        *[
            f"**Vencido:** {formatar_processo(p.processo)}, prazo {p.prazo_pagamento:%d/%m/%Y}, saldo R$ {p.saldo} ({p.fontes})"
            for p in vencidos
        ],
    ]


if __name__ == "__main__":
    main()
