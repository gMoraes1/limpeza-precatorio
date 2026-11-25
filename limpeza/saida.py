import csv
from datetime import date
from pathlib import Path

from limpeza.normalizacao import formatar_processo
from limpeza.pagamentos import Pagamento
from limpeza.precatorios import Precatorio


def salvar_precatorios(precatorios: list[Precatorio], caminho: Path, hoje: date):
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow([
            "processo", "ente_devedor", "valor_face", "apresentado_em", "prazo_pagamento",
            "total_pago", "saldo", "vencido", "fontes",
        ])
        for p in precatorios:
            escritor.writerow([
                formatar_processo(p.processo), p.ente_devedor, p.valor_face,
                p.apresentado_em or "", p.prazo_pagamento or "",
                p.total_pago, p.saldo, "sim" if p.vencido_em(hoje) else "não", p.fontes,
            ])


def salvar_pagamentos(pagamentos: list[Pagamento], caminho: Path):
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(["evento_id", "processo", "tipo", "valor", "data_pagamento", "atualizado_em"])
        for p in pagamentos:
            escritor.writerow([
                p.evento_id, formatar_processo(p.processo), p.tipo, p.valor,
                p.data_pagamento, p.atualizado_em.isoformat(),
            ])
