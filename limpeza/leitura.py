import csv
import io
import json
from pathlib import Path

from limpeza.relatorio import Relatorio

Linha = tuple[int, dict[str, str]]


def ler_json(caminho: Path) -> list[dict]:
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def ler_csv(caminho: Path, relatorio: Relatorio) -> list[Linha]:
    """Lê o CSV como ele veio de fato, sem confiar na documentação: tenta UTF-8 e,
    se falhar, cp1252 (o padrão do Excel no Windows). O separador é deduzido do
    cabeçalho. O que fugir de UTF-8 com vírgula vai para o relatório.
    Devolve (número da linha no arquivo, campos) para servir de evidência."""
    conteudo = caminho.read_bytes()
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = conteudo.decode("cp1252")
        relatorio.corrigido(caminho.name, "arquivo inteiro", "lido como cp1252 (Windows/Excel), não está em UTF-8")

    if not texto.strip():
        raise ValueError(f"{caminho.name} está vazio")

    cabecalho = texto.splitlines()[0]
    separador = ";" if cabecalho.count(";") > cabecalho.count(",") else ","
    if separador != ",":
        relatorio.corrigido(caminho.name, "arquivo inteiro", f"campos separados por '{separador}', não por vírgula")

    leitor = csv.DictReader(io.StringIO(texto, newline=""), delimiter=separador)
    return [
        (numero, {campo: (valor or "").strip() for campo, valor in linha.items()})
        for numero, linha in enumerate(leitor, start=2)
    ]
