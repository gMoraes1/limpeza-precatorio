# Limpeza da carteira de precatórios

Lê os arquivos do tribunal e do hub como vieram, sem alterá-los, e gera uma base confiável. Junto, gera um relatório do que foi corrigido, descartado ou ficou em dúvida.

O diagnóstico, as propostas de prevenção e as dúvidas estão em [ANALISE.md](ANALISE.md).

## Como rodar

Requer Python 3.10 ou mais recente. O programa só usa a biblioteca padrão. No Windows, instale também o `tzdata` (`pip install tzdata`), porque o `zoneinfo` precisa dele.

Na raiz do projeto:

```bash
python3 -m limpeza.main
```

O comando lê `exemplo/dados/` e grava em `saida/`:

| Arquivo | Conteúdo |
|---|---|
| `precatorios.csv` | Base reconciliada: ente, valor de face, prazo recalculado, total pago, saldo, se está vencido e de qual fonte veio |
| `pagamentos.csv` | Eventos válidos, sem repetição, na versão mais recente |
| `ocorrencias.csv` | Uma linha por registro corrigido, descartado ou em dúvida, com o motivo |
| `relatorio.md` | Resumo e ocorrências agrupadas, para leitura |

Para rodar os testes:

```bash
pip install pytest
python3 -m pytest
```

Rode pelo módulo (`-m`), não pelo caminho do arquivo. No VSCode, use a configuração **Limpeza** da aba Run and Debug (o `.vscode/launch.json` já está pronto).

## Estrutura

```
limpeza/
  main.py          orquestra: ler → montar precatórios → limpar pagamentos → somar → salvar
  leitura.py       lê CSV e JSON detectando codificação e separador
  normalizacao.py  processo, valor, data (fuso de Brasília) e nome do ente
  prazo.py         regra constitucional de 2 de abril
  pagamentos.py    validação, versão mais recente e estorno
  precatorios.py   junção hub × tribunal × apresentações e divergências
  relatorio.py     registro das ocorrências
  saida.py         gravação da base limpa
tests/             regras de maior risco: prazo, normalização, repetição, versão e estorno
sql/prevencao.sql  migração do banco proposta na análise
```

## Uso de IA

Usei o Claude (Anthropic) no VSCode, pelo Claude Code.

**O que fiz antes, sem IA:** li o enunciado, a documentação e os arquivos e montei o meu mapeamento inicial de problemas, com evidência e efeito.

**O que fiz com a IA:**
- Discuti a estrutura do código antes de escrever qualquer linha: um módulo por responsabilidade, funções puras de normalização e um relatório em que nada some em silêncio.
- A IA escreveu o código, os testes, o SQL de prevenção e complementou esta primeira versão do README e da análise, a partir do que eu tinha pensado.
- A IA acrescentou achados que eu não tinha: a falta de `UNIQUE (evento_id)`, o `CHECK (valor > 0)` que rejeita o `ev-009`, o pagamento anterior à apresentação e o segundo precatório vencido (0034567). Ela também corrigiu um erro meu: eu tinha calculado o prazo do 0067890 como 31/12/2024, e o correto é 31/12/2025.

**Como conferi:**
- Comparei a saída (`saida/relatorio.md`) com o meu mapeamento, caso a caso. Todo problema que eu tinha listado aparece no relatório com o registro certo.
- Refiz à mão os cálculos de prazo e os totais por processo.
- Executei o programa passo a passo no depurador do VSCode para entender o fluxo.
- Os testes cobrem as regras em que um erro custaria mais caro: prazo nos limites de 2 de abril e fuso, repetição e reimportação, versão do evento, estorno e normalização de valor.
- O SQL de prevenção foi executado num PostgreSQL 14 temporário sobre o `schema.sql` original, simulando reimportação, correção de evento e estorno.
