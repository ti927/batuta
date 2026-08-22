"""Prepara (ou recria) o Postgres LOCAL usado pela suíte de testes.

Por que existe um banco local
-----------------------------
A suíte roda contra um banco de verdade — não há banco de mentira. Enquanto esse
banco era o de produção (nos EUA), cada consulta atravessava o continente e a
suíte inteira levava ~40 minutos; contra o Postgres local, leva menos de um
minuto. De quebra, nenhum teste tem como escrever no banco dos clientes.

Os testes não precisam dos DADOS de produção: cada teste cria o que precisa
dentro de uma transação que é revertida no fim. Precisam só da ESTRUTURA — que é
exatamente o que `alembic upgrade head` produz, o mesmo comando que a produção
roda a cada deploy.

O ajuste do `clock_timestamp()`
-------------------------------
Em PostgreSQL, `now()` devolve o horário de INÍCIO DA TRANSAÇÃO — constante até o
commit. Como a fixture `sessao` roda cada teste inteiro numa transação só, TODAS
as linhas criadas por um teste nasceriam com o MESMO `criado_em`. Várias
consultas do produto pedem "a última mensagem" (`ORDER BY criado_em DESC LIMIT
1`); com todos os horários iguais, qual linha volta é indeterminado — o banco
pode devolver a primeira. Isso torna testes de conversa/portão intermitentes, e
o desempate muda de servidor para servidor (foi o que quebrou ao migrar o banco).

A correção é trocar o default para `clock_timestamp()` (o relógio de verdade,
que avança dentro da transação) NO BANCO DE TESTES. Isso não é uma licença
poética: em produção duas mensagens chegam em requisições — e portanto
transações — diferentes, e de fato recebem horários distintos. O
`clock_timestamp()` faz o banco de testes modelar a produção com MAIS fidelidade
do que o `now()` sob uma transação única, e some com uma classe inteira de
teste intermitente.

Uso
---
    uv run python banco_testes.py

Lê a `DATABASE_URL_TESTES` do `.env` (o container Docker `batuta-testes`).
Rode de novo sempre que criar uma migração nova.
"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

_ALVO = os.environ.get("DATABASE_URL_TESTES", "").strip()
if not _ALVO:
    sys.exit(
        "DATABASE_URL_TESTES não está no .env — sem ela, não existe banco local de\n"
        "testes para preparar. Suba o container e acrescente a variável:\n"
        "  docker run -d --name batuta-testes --restart unless-stopped \\\n"
        "    -e POSTGRES_PASSWORD=... -e POSTGRES_DB=batuta_testes -p 5433:5432 \\\n"
        "    -v batuta-testes-dados:/var/lib/postgresql/data postgres:17"
    )

# O `db` monta o engine na importação, a partir da DATABASE_URL. Apontamos para o
# banco de testes ANTES de importar — o `load_dotenv` de lá não sobrescreve o que
# já está no ambiente. Assim o alembic (que usa o mesmo engine) também acerta o alvo.
os.environ["DATABASE_URL"] = _ALVO

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from db import engine  # noqa: E402

# Troca do default para o relógio de verdade, em toda coluna de data que o
# alembic tenha criado com `now()`. Feito por varredura (e não coluna a coluna)
# para continuar valendo quando tabelas novas surgirem.
_TROCAR_DEFAULT = """
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT table_name, column_name
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND column_name IN ('criado_em', 'atualizado_em')
           AND column_default LIKE '%now()%'
    LOOP
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN %I SET DEFAULT clock_timestamp()',
            r.table_name, r.column_name
        );
    END LOOP;
END $$;
"""

_CONTAR = """
SELECT count(*) FROM information_schema.columns
 WHERE table_schema = 'public'
   AND column_name IN ('criado_em', 'atualizado_em')
   AND column_default LIKE '%clock_timestamp()%'
"""


def main() -> None:
    print(f"Banco de testes: {engine.url.host}:{engine.url.port}/{engine.url.database}")

    print("→ criando/atualizando as tabelas (alembic upgrade head)...")
    command.upgrade(Config("alembic.ini"), "head")

    print("→ trocando o default das datas para clock_timestamp()...")
    with engine.begin() as conn:
        conn.execute(text(_TROCAR_DEFAULT))
        n = conn.execute(text(_CONTAR)).scalar()
    print(f"   {n} colunas de data agora usam o relógio de verdade.")

    print("Pronto. Rode a suíte com: uv run pytest -q")


if __name__ == "__main__":
    main()
