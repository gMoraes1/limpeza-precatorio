from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from limpeza.leitura import Linha
from limpeza.normalizacao import (
    formatar_processo,
    normalizar_data,
    normalizar_nome,
    normalizar_processo,
    normalizar_valor,
)
from limpeza.pagamentos import Pagamento, total_por_processo
from limpeza.prazo import calcular_prazo
from limpeza.relatorio import Relatorio

ARQ_HUB = "hub.csv"
ARQ_TRIBUNAL = "tribunal.csv"
ARQ_APRESENTACOES = "apresentacoes.json"
ARQ_PAGAMENTOS = "pagamentos.json"


@dataclass
class Cadastro:
    """Uma linha do hub ou do tribunal já normalizada."""
    linha: int
    processo: str
    ente: str
    valor_face: Decimal
    campos: dict[str, str]


@dataclass
class Precatorio:
    processo: str
    ente_devedor: str
    valor_face: Decimal
    fontes: str
    apresentado_em: date | None = None
    prazo_pagamento: date | None = None
    total_pago: Decimal = Decimal("0.00")

    @property
    def saldo(self) -> Decimal:
        return self.valor_face - self.total_pago

    def vencido_em(self, hoje: date) -> bool:
        return self.prazo_pagamento is not None and self.prazo_pagamento < hoje and self.saldo > 0


def ler_cadastro(linhas: list[Linha], arquivo: str, campo_processo: str, campo_ente: str, relatorio: Relatorio) -> dict[str, Cadastro]:
    cadastros: dict[str, Cadastro] = {}
    for numero, campos in linhas:
        registro = f"linha {numero}"
        try:
            processo = normalizar_processo(campos.get(campo_processo))
            valor_face = normalizar_valor(campos.get("valor_face"))
        except ValueError as erro:
            relatorio.duvida(arquivo, registro, f"fora da base: {erro}")
            continue

        if campos[campo_processo] != formatar_processo(processo):
            relatorio.corrigido(
                arquivo, registro,
                f"processo '{campos[campo_processo]}' fora do padrão CNJ, lido como {formatar_processo(processo)}",
            )
        if processo in cadastros:
            relatorio.duvida(arquivo, registro, f"processo repetido (já na linha {cadastros[processo].linha}); mantida a primeira")
            continue
        cadastros[processo] = Cadastro(numero, processo, campos.get(campo_ente, ""), valor_face, campos)
    return cadastros


def ler_apresentacoes(registros: list[dict], relatorio: Relatorio) -> dict[str, date]:
    apresentacoes: dict[str, date] = {}
    for posicao, bruto in enumerate(registros, start=1):
        registro = f"item {posicao}"
        try:
            processo = normalizar_processo(bruto.get("processo"))
            apresentado_em = normalizar_data(bruto.get("apresentado_em"))
        except ValueError as erro:
            relatorio.duvida(ARQ_APRESENTACOES, registro, f"fora da base: {erro}")
            continue
        if bruto.get("apresentado_em") != apresentado_em.isoformat():
            relatorio.corrigido(
                ARQ_APRESENTACOES, registro,
                f"'{bruto.get('apresentado_em')}' convertido para {apresentado_em} no horário de Brasília",
            )
        apresentacoes[processo] = apresentado_em
    return apresentacoes


def montar_precatorios(hub: dict[str, Cadastro], tribunal: dict[str, Cadastro], apresentacoes: dict[str, date], relatorio: Relatorio) -> dict[str, Precatorio]:
    precatorios = {}
    for processo in sorted(hub.keys() | tribunal.keys()):
        do_hub, do_tribunal = hub.get(processo), tribunal.get(processo)
        precatorio = _reconciliar(processo, do_hub, do_tribunal, relatorio)
        _definir_prazo(precatorio, do_hub, apresentacoes.get(processo), relatorio)
        precatorios[processo] = precatorio
    return precatorios


def somar_pagamentos(precatorios: dict[str, Precatorio], pagamentos: list[Pagamento], relatorio: Relatorio):
    for processo, total in total_por_processo(pagamentos).items():
        precatorios[processo].total_pago = total

    for pagamento in pagamentos:
        apresentado_em = precatorios[pagamento.processo].apresentado_em
        if apresentado_em and pagamento.data_pagamento < apresentado_em:
            relatorio.duvida(
                ARQ_PAGAMENTOS, pagamento.origem,
                f"pago em {pagamento.data_pagamento}, antes da apresentação do precatório ({apresentado_em})",
            )

    for precatorio in precatorios.values():
        registro = formatar_processo(precatorio.processo)
        if precatorio.total_pago < 0:
            relatorio.duvida(ARQ_PAGAMENTOS, registro, f"estornos maiores que pagamentos (total {precatorio.total_pago})")
        elif precatorio.total_pago > precatorio.valor_face:
            relatorio.duvida(
                ARQ_PAGAMENTOS, registro,
                f"total pago {precatorio.total_pago} acima do valor de face {precatorio.valor_face}",
            )


def _reconciliar(processo: str, do_hub: Cadastro | None, do_tribunal: Cadastro | None, relatorio: Relatorio) -> Precatorio:
    """Quando o processo está nos dois arquivos, o tribunal é a fonte da verdade
    e cada divergência com o hub é registrada. Quando está em um só, entra na base
    mesmo assim, marcado como dúvida, para não sumir da carteira."""
    registro = formatar_processo(processo)

    if do_hub and do_tribunal:
        _comparar_ente(do_hub, do_tribunal, relatorio)
        if do_hub.valor_face != do_tribunal.valor_face:
            relatorio.duvida(
                ARQ_HUB, f"linha {do_hub.linha}",
                f"valor de face diverge: hub {do_hub.valor_face}, tribunal {do_tribunal.valor_face}; mantido o do tribunal",
            )
        return Precatorio(processo, do_tribunal.ente, do_tribunal.valor_face, fontes="hub e tribunal")

    if do_tribunal:
        relatorio.duvida(ARQ_TRIBUNAL, registro, "está no tribunal mas não no hub: precatório fora da carteira")
        return Precatorio(processo, do_tribunal.ente, do_tribunal.valor_face, fontes="só tribunal")

    relatorio.duvida(ARQ_HUB, registro, "está no hub mas não na lista do tribunal: quitado, cancelado ou cadastro errado?")
    return Precatorio(processo, do_hub.ente, do_hub.valor_face, fontes="só hub")


def _comparar_ente(do_hub: Cadastro, do_tribunal: Cadastro, relatorio: Relatorio):
    if do_hub.ente == do_tribunal.ente:
        return
    registro = f"linha {do_hub.linha}"
    if normalizar_nome(do_hub.ente) == normalizar_nome(do_tribunal.ente):
        relatorio.corrigido(ARQ_HUB, registro, f"ente '{do_hub.ente}' padronizado como '{do_tribunal.ente}'")
    else:
        relatorio.duvida(
            ARQ_HUB, registro,
            f"ente diverge: hub '{do_hub.ente}', tribunal '{do_tribunal.ente}'; mantido o do tribunal",
        )


def _definir_prazo(precatorio: Precatorio, do_hub: Cadastro | None, apresentado_em: date | None, relatorio: Relatorio):
    registro = formatar_processo(precatorio.processo)
    apresentado_no_hub = _data_ou_none(do_hub.campos.get("apresentado_em")) if do_hub else None

    if apresentado_em and apresentado_no_hub and apresentado_em != apresentado_no_hub:
        relatorio.duvida(
            ARQ_HUB, f"linha {do_hub.linha}",
            f"apresentação diverge: hub {apresentado_no_hub}, {ARQ_APRESENTACOES} {apresentado_em}; mantida a de {ARQ_APRESENTACOES}",
        )
    apresentado_em = apresentado_em or apresentado_no_hub
    if apresentado_em is None:
        relatorio.duvida(ARQ_APRESENTACOES, registro, "sem data de apresentação: prazo não calculado")
        return

    precatorio.apresentado_em = apresentado_em
    precatorio.prazo_pagamento = calcular_prazo(apresentado_em)

    prazo_no_hub = _data_ou_none(do_hub.campos.get("prazo_pagamento")) if do_hub else None
    if prazo_no_hub and prazo_no_hub != precatorio.prazo_pagamento:
        relatorio.corrigido(
            ARQ_HUB, f"linha {do_hub.linha}",
            f"prazo {prazo_no_hub} recalculado para {precatorio.prazo_pagamento} (apresentado em {apresentado_em})",
        )


def _data_ou_none(texto: str | None) -> date | None:
    try:
        return normalizar_data(texto)
    except ValueError:
        return None
