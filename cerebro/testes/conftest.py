"""Fixtures dos testes de acesso (Fase 6).

Cada teste roda numa transação revertida ao fim — nada persiste no banco. O
TestClient é instanciado SEM `with` de propósito: assim o lifespan do app
(fila de execuções e agendador) NÃO sobe durante os testes.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

import auth
import main
from db import engine
from modelos import ChaveApi, Membro, Organizacao, Time, Usuario
from sessao import obter_sessao


@pytest.fixture
def sessao():
    """Sessão ligada a uma transação externa que é sempre revertida. As escritas
    das rotas (commit) caem em savepoints internos; ao fim, o rollback descarta
    tudo — os testes não sujam o banco real.

    Como os testes rodam contra o banco real (que em produção já tem chaves da
    consultoria cadastradas), esvaziamos o cofre `chaves_api` no início de cada
    teste — DENTRO da transação revertida, então o rollback restaura tudo e nada
    é comitado. Assim a resolução de chave parte sempre de um cofre vazio e os
    testes ficam determinísticos, independentemente do estado real do banco."""
    conexao = engine.connect()
    trans = conexao.begin()
    s = Session(bind=conexao, join_transaction_mode="create_savepoint")
    s.execute(delete(ChaveApi))
    s.flush()
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        conexao.close()


@pytest.fixture
def cliente(sessao):
    main.app.dependency_overrides[obter_sessao] = lambda: sessao
    c = TestClient(main.app)
    yield c
    main.app.dependency_overrides.clear()


@pytest.fixture
def entrar():
    """Devolve uma função que faz o app tratar as requisições como vindas do
    usuário dado (substitui a dependência de autenticação)."""

    def _entrar(usuario):
        main.app.dependency_overrides[auth.usuario_atual] = lambda: usuario

    return _entrar


@pytest.fixture
def dados(sessao):
    """Org A com um usuário de cada papel; Org B com um 'estranho' (para testar
    isolamento). Um time em A."""

    def usuario(nome):
        u = Usuario(
            nome=nome,
            email=f"{nome}-{uuid.uuid4().hex[:6]}@x.com",
            auth_id=uuid.uuid4(),
            ativo=True,
        )
        sessao.add(u)
        sessao.flush()
        return u

    admin = usuario("admin")
    operador = usuario("operador")
    observador = usuario("observador")
    estranho = usuario("estranho")

    orgA = Organizacao(nome="Org A", dono_id=admin.id)
    orgB = Organizacao(nome="Org B", dono_id=estranho.id)
    sessao.add_all([orgA, orgB])
    sessao.flush()

    sessao.add_all(
        [
            Membro(usuario_id=admin.id, organizacao_id=orgA.id, papel="admin"),
            Membro(usuario_id=operador.id, organizacao_id=orgA.id, papel="operador"),
            Membro(usuario_id=observador.id, organizacao_id=orgA.id, papel="observador"),
            Membro(usuario_id=estranho.id, organizacao_id=orgB.id, papel="admin"),
        ]
    )
    timeA = Time(organizacao_id=orgA.id, nome="Time A")
    sessao.add(timeA)
    sessao.flush()

    return {
        "admin": admin,
        "operador": operador,
        "observador": observador,
        "estranho": estranho,
        "orgA": orgA,
        "orgB": orgB,
        "timeA": timeA,
    }
