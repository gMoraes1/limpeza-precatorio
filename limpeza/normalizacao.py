import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")
CENTAVO = Decimal("0.01")


def normalizar_processo(bruto) -> str:
    digitos = re.sub(r"\D", "", str(bruto or ""))
    if len(digitos) != 20:
        raise ValueError(f"processo deve ter 20 dígitos, veio {bruto!r}")
    return digitos


def formatar_processo(chave: str) -> str:
    return f"{chave[:7]}-{chave[7:9]}.{chave[9:13]}.{chave[13]}.{chave[14:16]}.{chave[16:]}"


def normalizar_valor(bruto) -> Decimal:
    """Aceita número do JSON (15000.0) ou texto, em formato brasileiro ("2.500,50")
    ou com ponto decimal ("45000.00"). Texto como "1.500" é recusado por ser
    ambíguo: pode ser mil e quinhentos ou um e meio."""
    if bruto is None or isinstance(bruto, bool) or str(bruto).strip() == "":
        raise ValueError("valor ausente")

    if isinstance(bruto, (int, float)):
        texto = str(bruto)
    else:
        texto = bruto.strip()
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", texto):
            raise ValueError(f"valor ambíguo {bruto!r}: separador de milhar ou decimal?")

    try:
        return Decimal(texto).quantize(CENTAVO)
    except InvalidOperation:
        raise ValueError(f"valor inválido {bruto!r}") from None


def normalizar_data_hora(bruto) -> datetime:
    """Devolve o momento no horário de Brasília. Sem fuso informado, assume Brasília."""
    texto = str(bruto or "").strip()
    if not texto:
        raise ValueError("data e hora ausente")
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"data e hora inválida {bruto!r}") from None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=FUSO_BRASILIA)
    return momento.astimezone(FUSO_BRASILIA)


def normalizar_data(bruto) -> date:
    """Aceita AAAA-MM-DD, DD/MM/AAAA ou data e hora ISO. Data e hora é convertida
    para o horário de Brasília antes de virar data: 2025-04-03T01:00Z é 02/04."""
    texto = str(bruto or "").strip()
    if not texto:
        raise ValueError("data ausente")
    try:
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto):
            return datetime.strptime(texto, "%d/%m/%Y").date()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
            return date.fromisoformat(texto)
    except ValueError:
        raise ValueError(f"data inválida {bruto!r}") from None
    return normalizar_data_hora(texto).date()


def normalizar_nome(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())
