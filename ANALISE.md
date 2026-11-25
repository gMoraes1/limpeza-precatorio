# Análise: por que os números não batem com os do tribunal

Os números citados aqui vêm dos arquivos em `exemplo/dados/` e da execução de `python3 -m limpeza.main`. A data de referência é 25/11/2026, e o relatório completo fica em `saida/relatorio.md`.

## Resumo

A principal causa é a importação diária. Ela **soma** cada evento recebido sem verificar se ele já foi somado antes. O mesmo evento chega em até 7 arquivos seguidos, é somado de novo quando o operador reexecuta o script e volta a ser somado quando o tribunal o corrige. Na outra direção, eventos que o script não consegue ler **desaparecem sem aviso**. Por isso os totais divergem nas duas direções: ficam inflados pela soma repetida e reduzidos pelo descarte.

Há ainda dois problemas de cadastro que não dependem da importação. O prazo de pagamento está errado no hub, e a conferência semanal entre hub e tribunal é feita por comparação exata de texto, então não detecta as divergências. Juntos, esses problemas deixaram **dois precatórios vencidos sem que ninguém percebesse**, e um deles nem está cadastrado no hub.

## 1. Diagnóstico

Os problemas estão ordenados do mais grave para o menos grave. A coluna "Relação" diz se o problema é causa ou consequência de outro.

| # | Problema | Gravidade | Relação |
|---|---|---|---|
| 1 | A importação soma o mesmo evento mais de uma vez | Crítica | Causa raiz |
| 2 | Correção e estorno são somados como pagamento novo | Crítica | Causa; agravada por 1 |
| 3 | Eventos rejeitados somem sem aviso | Crítica | Causa |
| 4 | Precatórios vencidos fora do radar | Crítica | Consequência de 2, 3, 5 e 7 |
| 5 | Prazo de pagamento errado no hub | Alta | Causa independente |
| 6 | Número do processo gravado em dois formatos | Alta | Causa de 3 e 7 |
| 7 | Hub e tribunal divergem e a conferência manual não detecta | Alta | Consequência de 6 e do processo manual |
| 8 | A documentação não descreve os arquivos reais | Média | Causa de 3 e 6 |
| 9 | Pagamento registrado antes da apresentação do precatório | Média | A confirmar |
| 10 | Dígitos verificadores do número CNJ não conferem | Baixa | A confirmar |

### 1. A importação soma o mesmo evento mais de uma vez

**Evidência**
- O enunciado diz que o script "soma cada valor ao total pago" e que o arquivo diário traz "os últimos 7 dias". Ou seja, um evento chega em até 7 arquivos diferentes.
- Quando a importação falha no meio, o operador roda o script de novo com o mesmo arquivo. Os eventos que já tinham sido gravados são somados outra vez.
- `pagamentos.json`, itens 2 e 4: o `ev-002` aparece duas vezes, com conteúdo idêntico, no mesmo arquivo.
- `schema.sql`: a tabela `pagamento` não tem `UNIQUE (evento_id)`, então o banco não impede a repetição.

**Impacto.** Só neste arquivo, somando tudo, o processo 0012345-10.2019.8.26.0053 apareceria com **R$ 35.501,00 pagos**. O valor correto é **R$ 18.000,50**. Com a janela de 7 dias, o erro se repete a cada novo arquivo. O total pago fica inflado e o saldo devedor fica subestimado, então a carteira parece mais quitada do que está.

**Relação.** É a causa raiz. O problema não está nos dados: o processo foi desenhado para somar, quando o correto seria gravar o estado de cada evento.

### 2. Correção e estorno são somados como pagamento novo

**Evidência**
- `ev-001` aparece duas vezes. O item 1 tem valor 15.000, atualizado em 10/03/2025. O item 9 tem valor 15.500, atualizado em 11/03/2025. É o tribunal corrigindo o próprio registro, e só a versão mais nova deveria valer.
- `ev-006` é um pagamento de 5.000 e `ev-007` é um **estorno** de 5.000, ambos no processo 0034567-32.2018.8.26.0405. O resultado líquido é zero.
- `ev-009` tem valor −200 com tipo `"pagamento"`. Pode ser um estorno lançado no tipo errado ou um erro de digitação.

**Impacto.** O processo 0034567 apareceria com **R$ 10.000 pagos quando o valor real é R$ 0**. Esse mesmo precatório está vencido (ver problema 4). O campo `atualizado_em` existe justamente para identificar versões, mas o processo atual não o usa.

**Relação.** É uma causa própria, agravada pelo problema 1. Mesmo sem repetição de arquivos, ignorar o tipo e a versão do evento já distorce o total.

### 3. Eventos rejeitados somem sem aviso

**Evidência**

| Evento | O que tem de errado | O que acontece hoje |
|---|---|---|
| `ev-004` | `valor: null` | Descartado. É um pagamento real de valor desconhecido. |
| `ev-010` | `processo: ""` | Descartado. São R$ 750 sem dono. |
| `ev-009` | valor −200 | O banco recusa, porque o `schema.sql` tem `CHECK (valor > 0)`. |
| `ev-011` | processo 0067890 não existe no hub | A FK `precatorio_id` não encontra o precatório e o evento é descartado. São R$ 4.000. |

O enunciado confirma o comportamento: "o script ignora e segue. Ninguém é avisado".

**Impacto.** Pelo menos R$ 4.750 em pagamentos conhecidos, mais o valor desconhecido do `ev-004`, ficam fora do sistema sem que ninguém saiba. Como não há registro do que foi rejeitado, é impossível dizer depois **onde** está a diferença. Isso explica o "ninguém sabe dizer onde nem por quê".

**Relação.** É causa. Também é ela que esconde o problema 4.

### 4. Precatórios vencidos fora do radar

**Evidência**
- **0067890-65.2016.8.26.0053.** Foi apresentado em 31/12/2023, depois de 2 de abril, então o prazo era **31/12/2025**. Já foram pagos R$ 4.000 de R$ 7.000 (`ev-011`), e o precatório **não está no hub**. Ele só aparece no `tribunal.csv`.
- **0034567-32.2018.8.26.0405.** Foi apresentado em 29/02/2024, com prazo em **31/12/2025**. O único pagamento foi estornado, então o saldo é de **R$ 12.500 e nada foi pago**. Somando pagamento e estorno como faz o processo atual, ele apareceria com R$ 10.000 pagos (problema 2).

**Impacto.** É o risco de negócio mais alto. A equipe prioriza a carteira pelo prazo, e esses dois casos, os únicos já vencidos, não aparecem como prioridade. Um porque nem está cadastrado, o outro porque parece quase quitado.

**Relação.** É consequência. O 0067890 escapa pelos problemas 3 e 7. O 0034567 escapa pelo problema 2.

### 5. Prazo de pagamento errado no hub

**Evidência.** A regra é: apresentado até 2 de abril, paga até 31/12 do ano seguinte; apresentado depois, até 31/12 do ano subsequente ao seguinte. As datas de apresentação abaixo foram convertidas para o horário de Brasília.

| Processo | Apresentado em (Brasília) | Hub diz | Correto |
|---|---|---|---|
| 0012345 | 02/04/2025 | 31/12/2027 | **31/12/2026** |
| 0056789 | 02/04/2025 22:00 (`2025-04-03T01:00:00Z`) | 31/12/2027 | **31/12/2026** |
| 0045678 | 02/04/2025 23:30 | 31/12/2026 | 31/12/2026 ✓ |
| 0023456 | 03/04/2025 | 31/12/2027 | 31/12/2027 ✓ |
| 0034567 | 29/02/2024 | 31/12/2025 | 31/12/2025 ✓ |

Dois erros aparecem aqui. O primeiro é o próprio dia 2 de abril sendo tratado como "depois do limite", como se a regra usasse `<` em vez de `<=`. O segundo é a data em UTC sendo usada sem conversão: às 01:00 UTC de 03/04 ainda é dia 02/04 em Brasília. O 0045678, com o mesmo dia 02/04, saiu certo, o que mostra que **o cálculo nem é consistente**. Sem o código do sistema não dá para saber qual regra ele aplica (ver Dúvidas).

O hub também mistura formatos na coluna `apresentado_em`: há data pura, data e hora com fuso `-03:00` e data e hora em UTC.


**Impacto.** Dois precatórios aparecem com um ano a mais de prazo. Na prática, a equipe deixa para depois algo que vence antes.

**Relação.** É causa independente. O `schema.sql` não tem coluna de apresentação nem de prazo, então a regra vive fora do banco, sem uma fonte única.

### 6. Número do processo gravado em dois formatos

**Evidência**
- `hub.csv`, linha 3, e `pagamentos.json`, `ev-005`, trazem `00234562120208260053`, sem pontuação. Os demais registros usam o formato CNJ, `0023456-21.2020.8.26.0053`.
- `schema.sql`: `numero_processo CHAR(20)`. O formato CNJ tem 25 caracteres e **não cabe na coluna**. Quem grava no banco é obrigado a tirar a pontuação, e quem exporta e compara usa o formato com pontuação.

**Impacto.** Qualquer comparação "exatamente como está escrito" falha. O mesmo precatório pode virar um registro duplicado ou um registro órfão.

**Relação.** É causa dos problemas 3 e 7.

### 7. Hub e tribunal divergem e a conferência manual não detecta

**Evidência**

| Processo | Hub | Tribunal |
|---|---|---|
| 0045678 | Município de Santos | **União** |
| 0023456 | valor de face 31.000,00 | **30.000,00** |
| 0056789 | existe | **não existe** |
| 0067890 | **não existe** | existe |
| 0012345 | `MUNICIPIO DE SAO PAULO` | `Município de São Paulo` |

O processo descrito é abrir o arquivo no Excel, conferir, **salvar** e procurar o nome e o número "exatamente como estão escritos". Esse processo tem três falhas:
- acusa diferença onde só há variação de escrita, como acento ou maiúsculas;
- não detecta divergências que estão em outros campos, como o valor de face;
- ao salvar, o Excel pode remover zeros à esquerda e mudar a codificação, alterando o arquivo de origem.

**Impacto.** Um precatório da União pode estar sendo cobrado do Município de Santos. Os valores de face divergem. E um precatório vencido fica fora da carteira (problema 4).

**Relação.** É consequência do problema 6 e de depender de uma conferência manual.

### 8. A documentação não descreve os arquivos reais

**Evidência**

| A documentação diz | O arquivo tem |
|---|---|
| `tribunal.csv` em UTF-8 | cp1252/Latin-1. Ler como UTF-8 dá erro no byte `0xED` (o `í` de "Município"). |
| Campos separados por vírgula | Separados por `;` |
| Valor com ponto decimal | `45.000,00`, com ponto de milhar e vírgula decimal |
| `valor` é número | `ev-002` traz o texto `"2.500,50"` |
| `data_pagamento` em AAAA-MM-DD | `ev-002` traz `10/04/2025` |
| `tipo` é sempre `"pagamento"` | `ev-007` é `"estorno"` |
| (não menciona) | Existe um `apresentacoes.json`, sem documentação |

**Impacto.** Quem implementar seguindo a documentação vai ler acentos corrompidos, valores errados (`45.000,00` lido como 45) e vai ignorar estornos. Isso explica parte dos descartes do problema 3.

**Relação.** É causa dos problemas 3 e 6. A documentação é a versão 2.1 e provavelmente ficou desatualizada em relação ao sistema do tribunal.


### 9. Pagamento registrado antes da apresentação do precatório

**Evidência.** O `ev-001`, do processo 0012345, foi pago em **10/03/2025**. O precatório foi apresentado em **02/04/2025**, segundo `apresentacoes.json` e `hub.csv`.

**Impacto.** Uma das duas datas está errada. Se a errada for a de apresentação, o prazo do problema 5 muda de novo.

**Relação.** A confirmar com o tribunal.

### 10. Dígitos verificadores do número CNJ não conferem

**Evidência.** O cálculo do dígito verificador CNJ (módulo 97, Resolução 65/2008) não confere em **nenhum** dos 6 processos. Por exemplo, 0012345-**10** deveria ter dígito 72.

**Impacto.** Se os números forem reais, há erro de cadastro na origem. Se forem anonimizados, não há impacto. Por isso a limpeza **não** usa o dígito para rejeitar registros.

**Relação.** A confirmar.

## 2. Limpeza

O programa está em `limpeza/`. O README explica como rodar. As regras são:

- **Nada some.** Todo registro que não entra na base gera uma ocorrência, classificada como *corrigido*, *descartado* ou *dúvida*, com arquivo, registro e motivo.
- **Chave do processo = 20 dígitos.** Funciona com e sem pontuação e casa com o `CHAR(20)` do banco.
- **Um evento conta uma vez.** Uma cópia idêntica é descartada. Uma versão diferente é resolvida pelo `atualizado_em` mais recente. Se duas versões diferentes tiverem o mesmo `atualizado_em`, o caso vira dúvida.
- **Estorno subtrai.** Valor negativo, nulo ou zero vira dúvida e não é somado.
- **O tribunal é a fonte da verdade** para ente e valor de face. A divergência com o hub é registrada como dúvida, e a diferença só de escrita (acento, maiúsculas) é registrada como correção.
- **Precatório presente em um só lado entra na base marcado**, para não sumir da carteira.
- **O prazo é recalculado** a partir da data de apresentação convertida para Brasília. A divergência com o hub é registrada.
- **Valor ambíguo não é adivinhado.** Um texto como `"1.500"` pode ser mil e quinhentos ou um e meio, então vira dúvida.

Resultado: 6 precatórios e 8 dos 13 eventos na base. São 13 correções, 2 descartes e 8 dúvidas.

## 3. Prevenção

### Processo

1. **Receber os arquivos por integração, não por e-mail.** A melhor opção é uma API ou SFTP do tribunal. Se isso não for possível, um script que busca o anexo e guarda o arquivo original com data e hash, sem intervenção manual.
2. **Eliminar o passo de abrir e salvar no Excel.** A conferência semanal passa a ser o relatório de divergências gerado pela limpeza. O operador trata as dúvidas, não procura diferenças.
3. **Ter um dono para as dúvidas**, com prazo. Uma dúvida sem resposta em X dias é escalada.
4. **Pedir ao tribunal que atualize a documentação** (versão 2.2), incluindo estorno, a codificação real, o formato do valor e o `apresentacoes.json`. Até lá, o importador valida os arquivos contra o formato observado e não contra a documentação.
5. **Fazer um alerta semanal de vencidos e a vencer**, a partir da view `precatorio_saldo`.

### Script de importação

1. **Gravar o estado do evento em vez de somar.** É um *upsert* por `evento_id`, que só sobrescreve quando o `atualizado_em` recebido é mais novo. Assim reimportar o mesmo arquivo, ou receber o evento em 7 arquivos seguidos, não muda nada.
2. **Calcular o total pago com uma consulta** (`SUM` de pagamentos menos estornos), nunca acumulando num campo.
3. **Registrar todo evento recebido** com o status importado, repetido, versão antiga ou rejeitado, e o motivo. No fim, enviar um resumo com o número de rejeitados para a operação.
4. **Gravar a importação inteira em uma transação.** Se falhar no meio, nada é gravado e a reexecução é segura.
5. **Normalizar a entrada** com as mesmas funções da limpeza (`limpeza/normalizacao.py`): processo em 20 dígitos, valor brasileiro ou numérico, data com fuso convertida para Brasília. Também detectar a codificação e o separador e avisar se mudarem.
6. **Não descartar evento de processo desconhecido.** Ele fica pendente até o precatório ser cadastrado.

### Banco

O SQL completo está em [`sql/prevencao.sql`](sql/prevencao.sql). Foi testado no PostgreSQL 14 sobre o `schema.sql` original: reimportar um evento não o duplica, a versão nova substitui a antiga, o estorno zera o total e o prazo é calculado pelo próprio banco.

```sql
-- Chave única do processo
ALTER TABLE precatorio
    ADD CONSTRAINT precatorio_numero_20_digitos CHECK (numero_processo ~ '^[0-9]{20}$');

-- Prazo calculado pelo banco, numa regra só
ALTER TABLE precatorio ADD COLUMN apresentado_em DATE;
ALTER TABLE precatorio ADD COLUMN prazo_pagamento DATE GENERATED ALWAYS AS (
    make_date(
        EXTRACT(YEAR FROM apresentado_em)::int
            + CASE WHEN (EXTRACT(MONTH FROM apresentado_em), EXTRACT(DAY FROM apresentado_em)) <= (4, 2)
                   THEN 1 ELSE 2 END,
        12, 31)
) STORED;

-- Um evento é uma linha só; versão mais nova substitui
ALTER TABLE pagamento ADD COLUMN atualizado_em TIMESTAMPTZ;  -- preenchido e tornado NOT NULL no script completo
ALTER TABLE pagamento ADD CONSTRAINT pagamento_evento_unico UNIQUE (evento_id);

INSERT INTO pagamento (precatorio_id, evento_id, tipo, valor, pago_em, atualizado_em)
VALUES (...)
ON CONFLICT (evento_id) DO UPDATE
   SET precatorio_id = EXCLUDED.precatorio_id, tipo = EXCLUDED.tipo, valor = EXCLUDED.valor,
       pago_em = EXCLUDED.pago_em, atualizado_em = EXCLUDED.atualizado_em
 WHERE pagamento.atualizado_em < EXCLUDED.atualizado_em;

-- Nada some: tudo o que chega fica registrado
CREATE TABLE evento_recebido (
    id            BIGSERIAL PRIMARY KEY,
    importacao_id BIGINT NOT NULL REFERENCES importacao (id),
    posicao       INT    NOT NULL,
    conteudo      JSONB  NOT NULL,
    status        TEXT   NOT NULL CHECK (status IN ('importado', 'repetido', 'versao_antiga', 'rejeitado')),
    motivo        TEXT,
    UNIQUE (importacao_id, posicao),
    CHECK (status <> 'rejeitado' OR motivo IS NOT NULL)
);

-- Total pago e vencidos sempre calculados
CREATE VIEW precatorio_saldo AS ...;  -- ver sql/prevencao.sql
```

O script também cria a tabela `ente_devedor`, para o ente deixar de ser texto livre, e a tabela `importacao`, com nome e hash do arquivo. Ele traz ainda a consulta para encontrar as duplicatas que já existem antes de criar o `UNIQUE`.

## 4. Dúvidas antes de pôr em produção

### Para o tribunal

1. A documentação 2.1 está desatualizada? Qual é o leiaute real: codificação, separador, formato do valor e da data, tipos possíveis de evento?
2. O que é um evento com o mesmo `evento_id` e valor diferente? Uma correção que substitui o anterior (é o que a limpeza assume) ou um complemento?
3. O estorno sempre vem com valor positivo e `tipo = "estorno"`? O que significa o `ev-009` (−200 com tipo `"pagamento"`)?
4. Qual é o valor do `ev-004`, que veio com valor nulo? E de qual processo é o `ev-010`, que veio sem processo e tem R$ 750?
5. O ente do 0045678 é a União ou o Município de Santos? Qual é o valor de face correto do 0023456, 30.000 ou 31.000?
6. O 0056789 saiu da lista por quê: foi quitado, cancelado ou é um erro? E o 0067890 é um precatório ativo?
7. O `apresentacoes.json` é oficial? A data e hora de apresentação está em que fuso, e qual referência vale para a regra de 2 de abril?
8. O pagamento do `ev-001` (10/03/2025) é anterior à apresentação do 0012345 (02/04/2025). Qual das duas datas está certa?
9. Os números de processo estão anonimizados? Os dígitos verificadores não conferem.
10. Datas no formato `DD/MM/AAAA` são sempre dia/mês?

### Para a operação

1. Onde fica o "total pago" que o script soma? O `schema.sql` não tem esse campo. Existe outra tabela ou planilha?
2. Quantas vezes o script já foi reexecutado após falha? Existe log? Isso permite estimar quanto do total atual está inflado.
3. Como o sistema calcula o prazo hoje? Ele trata o dia 2 de abril como dentro ou fora do limite e considera o fuso horário? O 0045678 saiu certo e o 0012345 não, com a mesma data.
4. Quem cadastra precatórios no hub, e por que o 0067890 não foi cadastrado?
5. Se hub e tribunal divergirem, quem decide qual vale? A limpeza assume o tribunal.
6. A base limpa vai substituir os dados do sistema ou só servir de conferência? Isso define se as correções do relatório precisam de aprovação antes de serem aplicadas.
