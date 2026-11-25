from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from limpeza.normalizacao import (
    formatar_processo,
    normalizar_data,
    normalizar_data_hora,
    normalizar_processo,
    normalizar_valor,
)
from limpeza.relatorio import Relatorio

ARQUIVO = "pagamentos.json"
TIPOS_VALIDOS = {"pagamento", "estorno"}


@dataclass
class Pagamento:
    evento_id: str
    processo: str
    tipo: str
    valor: Decimal
    data_pagamento: date
    atualizado_em: datetime
    origem: str = field(default="", compare=False)

    @property
    def valor_com_sinal(self) -> Decimal:
        return -self.valor if self.tipo == "estorno" else self.valor


def limpar_pagamentos(eventos: list[dict], processos_conhecidos: set[str], relatorio: Relatorio) -> list[Pagamento]:
    pagamentos = []
    for posicao, bruto in enumerate(eventos, start=1):
        pagamento = _converter_evento(bruto, posicao, relatorio)
        if pagamento:
            pagamentos.append(pagamento)

    pagamentos = _manter_versao_mais_recente(pagamentos, relatorio)
    return _remover_sem_precatorio(pagamentos, processos_conhecidos, relatorio)


def total_por_processo(pagamentos: list[Pagamento]) -> dict[str, Decimal]:
    totais = defaultdict(Decimal)
    for pagamento in pagamentos:
        totais[pagamento.processo] += pagamento.valor_com_sinal
    return dict(totais)


def _converter_evento(bruto: dict, posicao: int, relatorio: Relatorio) -> Pagamento | None:
    evento_id = str(bruto.get("evento_id") or "").strip()
    registro = f"{evento_id or 'sem evento_id'} (item {posicao})"
    try:
        if not evento_id:
            raise ValueError("evento sem evento_id")
        processo = normalizar_processo(bruto.get("processo"))
        valor = normalizar_valor(bruto.get("valor"))
        tipo = _validar_tipo_e_valor(bruto.get("tipo"), valor)
        data_pagamento = normalizar_data(bruto.get("data_pagamento"))
        atualizado_em = normalizar_data_hora(bruto.get("atualizado_em"))
    except ValueError as erro:
        relatorio.duvida(ARQUIVO, registro, f"fora da base: {erro}")
        return None

    pagamento = Pagamento(evento_id, processo, tipo, valor, data_pagamento, atualizado_em, origem=registro)
    _registrar_correcoes(bruto, pagamento, relatorio)
    return pagamento


def _validar_tipo_e_valor(tipo, valor: Decimal) -> str:
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo desconhecido {tipo!r}")
    if valor < 0:
        raise ValueError(f"valor negativo ({valor}) com tipo '{tipo}': estorno lançado como pagamento?")
    if valor == 0:
        raise ValueError("valor zero")
    return tipo


def _registrar_correcoes(bruto: dict, pagamento: Pagamento, relatorio: Relatorio):
    if bruto.get("processo") != formatar_processo(pagamento.processo):
        relatorio.corrigido(
            ARQUIVO, pagamento.origem,
            f"processo '{bruto.get('processo')}' fora do padrão CNJ, lido como {formatar_processo(pagamento.processo)}",
        )
    if isinstance(bruto.get("valor"), str):
        relatorio.corrigido(ARQUIVO, pagamento.origem, f"valor veio como texto '{bruto.get('valor')}', lido como {pagamento.valor}")
    if bruto.get("data_pagamento") != pagamento.data_pagamento.isoformat():
        relatorio.corrigido(
            ARQUIVO, pagamento.origem,
            f"data '{bruto.get('data_pagamento')}' fora do formato AAAA-MM-DD, lida como {pagamento.data_pagamento}",
        )


def _manter_versao_mais_recente(pagamentos: list[Pagamento], relatorio: Relatorio) -> list[Pagamento]:
    """O arquivo diário cobre 7 dias e pode ser reimportado, então o mesmo evento_id
    aparece várias vezes. Cópia idêntica conta uma vez só. Conteúdo diferente é
    correção do tribunal: vale a versão com atualizado_em mais recente."""
    escolhidos: dict[str, Pagamento] = {}
    for pagamento in pagamentos:
        anterior = escolhidos.get(pagamento.evento_id)
        if anterior is None:
            escolhidos[pagamento.evento_id] = pagamento
        elif pagamento == anterior:
            relatorio.descartado(ARQUIVO, pagamento.origem, f"cópia idêntica de {anterior.origem}")
        elif pagamento.atualizado_em == anterior.atualizado_em:
            relatorio.duvida(
                ARQUIVO, pagamento.origem,
                f"mesmo atualizado_em de {anterior.origem} mas conteúdo diferente; mantido {anterior.origem}",
            )
        else:
            novo = max(pagamento, anterior, key=lambda p: p.atualizado_em)
            antigo = anterior if novo is pagamento else pagamento
            escolhidos[pagamento.evento_id] = novo
            relatorio.descartado(
                ARQUIVO, antigo.origem,
                f"versão antiga (valor {antigo.valor}, atualizada em {antigo.atualizado_em:%d/%m/%Y %H:%M}); "
                f"vale {novo.origem} (valor {novo.valor}, atualizada em {novo.atualizado_em:%d/%m/%Y %H:%M})",
            )
    return list(escolhidos.values())


def _remover_sem_precatorio(pagamentos: list[Pagamento], processos_conhecidos: set[str], relatorio: Relatorio) -> list[Pagamento]:
    com_precatorio = []
    for pagamento in pagamentos:
        if pagamento.processo in processos_conhecidos:
            com_precatorio.append(pagamento)
        else:
            relatorio.duvida(
                ARQUIVO, pagamento.origem,
                f"processo {formatar_processo(pagamento.processo)} não existe no hub nem no tribunal; "
                f"R$ {pagamento.valor} fora da base",
            )
    return com_precatorio
