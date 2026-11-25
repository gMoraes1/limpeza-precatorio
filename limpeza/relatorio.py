import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CORRIGIDO = "corrigido"
DESCARTADO = "descartado"
DUVIDA = "duvida"

TITULOS = {
    DUVIDA: "Dúvidas (precisam de resposta antes de ir para produção)",
    CORRIGIDO: "Corrigidos",
    DESCARTADO: "Descartados",
}


@dataclass(frozen=True)
class Ocorrencia:
    tipo: str
    arquivo: str
    registro: str
    motivo: str


class Relatorio:
    def __init__(self):
        self.ocorrencias: list[Ocorrencia] = []

    def corrigido(self, arquivo: str, registro: str, motivo: str):
        self.ocorrencias.append(Ocorrencia(CORRIGIDO, arquivo, registro, motivo))

    def descartado(self, arquivo: str, registro: str, motivo: str):
        self.ocorrencias.append(Ocorrencia(DESCARTADO, arquivo, registro, motivo))

    def duvida(self, arquivo: str, registro: str, motivo: str):
        self.ocorrencias.append(Ocorrencia(DUVIDA, arquivo, registro, motivo))

    def do_tipo(self, tipo: str) -> list[Ocorrencia]:
        return [o for o in self.ocorrencias if o.tipo == tipo]

    def salvar_csv(self, caminho: Path):
        with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(["tipo", "arquivo", "registro", "motivo"])
            for o in self.ocorrencias:
                escritor.writerow([o.tipo, o.arquivo, o.registro, o.motivo])

    def salvar_markdown(self, caminho: Path, resumo: list[str]):
        linhas = [
            "# Relatório da limpeza",
            "",
            f"Gerado em {datetime.now():%d/%m/%Y %H:%M}.",
            "",
            "## Resumo",
            "",
            *[f"- {item}" for item in resumo],
        ]
        for tipo, titulo in TITULOS.items():
            ocorrencias = self.do_tipo(tipo)
            linhas += ["", f"## {titulo} ({len(ocorrencias)})", ""]
            if not ocorrencias:
                linhas.append("Nenhum.")
                continue
            linhas += ["| Arquivo | Registro | Motivo |", "|---|---|---|"]
            linhas += [f"| {o.arquivo} | {o.registro} | {_escapar(o.motivo)} |" for o in ocorrencias]
        caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _escapar(texto: str) -> str:
    return texto.replace("|", "\\|")
