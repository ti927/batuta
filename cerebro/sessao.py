"""Sessão de banco por requisição.

Cada requisição do FastAPI recebe uma sessão própria via a dependência
`obter_sessao`, que garante o fechamento ao fim — mesmo se houver erro.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from db import engine

CriadorDeSessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def obter_sessao() -> Generator[Session, None, None]:
    """Dependência do FastAPI: entrega uma sessão e a fecha ao fim."""
    sessao = CriadorDeSessao()
    try:
        yield sessao
    finally:
        sessao.close()
