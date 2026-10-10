"""Sessão de banco por requisição.

Cada requisição do FastAPI recebe uma sessão própria via a dependência
`obter_sessao`, que garante o fechamento ao fim — mesmo se houver erro.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from db import engine, engine_log

CriadorDeSessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Só para o banco de logs (`registrar_evento`): pool próprio, nunca disputa conexão com
# a requisição ou a execução que está registrando o evento (ver `db.engine_log`).
CriadorDeSessaoDoLog = sessionmaker(bind=engine_log, autoflush=False, expire_on_commit=False)


def obter_sessao() -> Generator[Session, None, None]:
    """Dependência do FastAPI: entrega uma sessão e a fecha ao fim."""
    sessao = CriadorDeSessao()
    try:
        yield sessao
    finally:
        sessao.close()
