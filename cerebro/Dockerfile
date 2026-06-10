# Cérebro do Batuta (FastAPI + LangGraph), gerenciado por uv.
# Railway constrói com Root Directory = cerebro/ (o contexto é esta pasta).
FROM python:3.13-slim

# uv (gerenciador de pacotes/venv) — binário da imagem oficial.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Código + lockfile. As dependências de sistema (libpq, openssl) já vêm nos wheels
# binários (psycopg[binary], cryptography), então não há apt-get.
COPY . .

# Instala exatamente o que o uv.lock fixa (sem as deps de dev/teste).
RUN uv sync --frozen --no-dev

ENV PORT=8000

# Aplica as migrations (idempotente) e sobe a API na porta que o Railway injeta.
# Sem --reload (produção). 1 réplica: o agendador e a fila vivem no processo.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
