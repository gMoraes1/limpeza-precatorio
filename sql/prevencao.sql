-- Migração sobre exemplo/schema.sql (PostgreSQL).
-- Objetivo: tornar a importação idempotente, impedir descarte silencioso
-- e tirar do código as regras que hoje divergem (chave do processo, prazo, total pago).

BEGIN;

-- 1. Chave do processo: sempre os 20 dígitos, sem pontuação.
--    O CHAR(20) atual não comporta o formato CNJ (25 caracteres) e não impede o formato misturado.
ALTER TABLE precatorio
    ADD CONSTRAINT precatorio_numero_20_digitos CHECK (numero_processo ~ '^[0-9]{20}$');


-- 2. Data de apresentação e prazo calculado pelo banco, numa regra só.
--    apresentado_em é a data no horário de Brasília; a conversão de data e hora é feita na importação.
ALTER TABLE precatorio ADD COLUMN apresentado_em DATE;
ALTER TABLE precatorio ADD COLUMN prazo_pagamento DATE GENERATED ALWAYS AS (
    make_date(
        EXTRACT(YEAR FROM apresentado_em)::int
            + CASE WHEN (EXTRACT(MONTH FROM apresentado_em), EXTRACT(DAY FROM apresentado_em)) <= (4, 2)
                   THEN 1 ELSE 2 END,
        12, 31)
) STORED;


-- 3. Ente devedor como cadastro, não como texto livre.
CREATE TABLE ente_devedor (
    id   BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);
ALTER TABLE precatorio ADD COLUMN ente_devedor_id BIGINT REFERENCES ente_devedor (id);
-- Depois de preencher ente_devedor_id para todos os registros:
-- ALTER TABLE precatorio ALTER COLUMN ente_devedor_id SET NOT NULL;
-- ALTER TABLE precatorio DROP COLUMN ente_devedor;


-- 4. Um evento do tribunal é uma linha só. Reimportar o arquivo não soma de novo;
--    uma versão mais nova do evento substitui a anterior.
ALTER TABLE pagamento ADD COLUMN atualizado_em TIMESTAMPTZ;
UPDATE pagamento SET atualizado_em = criado_em WHERE atualizado_em IS NULL;
ALTER TABLE pagamento ALTER COLUMN atualizado_em SET NOT NULL;
-- Antes desta linha é preciso remover as duplicatas que já existem (ver consulta no fim do arquivo).
ALTER TABLE pagamento ADD CONSTRAINT pagamento_evento_unico UNIQUE (evento_id);


-- 5. Tudo o que chega fica registrado, inclusive o que não entra. Nada some em silêncio.
CREATE TABLE importacao (
    id           BIGSERIAL PRIMARY KEY,
    arquivo      TEXT        NOT NULL,
    sha256       CHAR(64)    NOT NULL,
    iniciada_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    concluida_em TIMESTAMPTZ
);

CREATE TABLE evento_recebido (
    id            BIGSERIAL PRIMARY KEY,
    importacao_id BIGINT      NOT NULL REFERENCES importacao (id),
    posicao       INT         NOT NULL,
    conteudo      JSONB       NOT NULL,
    status        TEXT        NOT NULL CHECK (status IN ('importado', 'repetido', 'versao_antiga', 'rejeitado')),
    motivo        TEXT,
    UNIQUE (importacao_id, posicao),
    CHECK (status <> 'rejeitado' OR motivo IS NOT NULL)
);


-- 6. Total pago calculado na consulta, nunca acumulado em um campo.
CREATE VIEW precatorio_saldo AS
SELECT p.*,
       p.valor_face - p.total_pago AS saldo,
       p.prazo_pagamento < CURRENT_DATE AND p.valor_face > p.total_pago AS vencido
FROM (
    SELECT pr.id, pr.numero_processo, pr.ente_devedor, pr.valor_face,
           pr.apresentado_em, pr.prazo_pagamento,
           COALESCE(SUM(CASE pg.tipo WHEN 'estorno' THEN -pg.valor ELSE pg.valor END), 0) AS total_pago
    FROM precatorio pr
    LEFT JOIN pagamento pg ON pg.precatorio_id = pr.id
    GROUP BY pr.id
) p;

COMMIT;


#Gravação de um evento pelo script de importação (parâmetros no estilo psycopg).
# Só sobrescreve quando a versão recebida é mais nova; repetir a mesma versão não muda nada.
#
# INSERT INTO pagamento (precatorio_id, evento_id, tipo, valor, pago_em, atualizado_em)
# VALUES (%(precatorio_id)s, %(evento_id)s, %(tipo)s, %(valor)s, %(pago_em)s, %(atualizado_em)s)
# ON CONFLICT (evento_id) DO UPDATE
#    SET precatorio_id = EXCLUDED.precatorio_id,
#        tipo          = EXCLUDED.tipo,
#        valor         = EXCLUDED.valor,
#        pago_em       = EXCLUDED.pago_em,
#        atualizado_em = EXCLUDED.atualizado_em
#  WHERE pagamento.atualizado_em < EXCLUDED.atualizado_em;


# Duplicatas já existentes (rodar antes do passo 4):
#
# SELECT evento_id, count(*), array_agg(id ORDER BY criado_em) AS ids
# FROM pagamento
# GROUP BY evento_id
# HAVING count(*) > 1;
