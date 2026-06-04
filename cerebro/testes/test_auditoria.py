"""A auditoria registra as ações sensíveis na mesma transação da ação (§6.4)."""

from sqlalchemy import select

from modelos import Auditoria

AGENTE = {
    "nome": "Ag",
    "papel": "agente",
    "agent_md": "v1",
    "skill_md": None,
    "tools_md": None,
    "soul_md": None,
    "modelo_ia": None,
}


def _linhas(sessao, acao=None):
    q = select(Auditoria)
    if acao:
        q = q.where(Auditoria.acao == acao)
    return sessao.scalars(q).all()


def test_criar_org_gera_auditoria(cliente, entrar, dados, sessao):
    entrar(dados["operador"])  # qualquer autenticado cria org (e vira admin dela)
    r = cliente.post("/organizacoes", json={"nome": "Nova"})
    assert r.status_code == 201
    assert any(
        str(l.recurso_id) == r.json()["id"]
        for l in _linhas(sessao, "organizacao.criada")
    )


def test_criar_time_gera_auditoria(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    r = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/times",
        json={"nome": "T", "descricao": None},
    )
    assert r.status_code == 201
    assert any(str(l.recurso_id) == r.json()["id"] for l in _linhas(sessao, "time.criado"))


def test_alterar_markdown_gera_auditoria(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    r = cliente.post(f"/times/{dados['timeA'].id}/agentes", json=AGENTE)
    assert r.status_code == 201
    aid = r.json()["id"]
    r2 = cliente.put(f"/agentes/{aid}", json={**AGENTE, "agent_md": "v2"})
    assert r2.status_code == 200
    linhas = _linhas(sessao, "agente.markdown_alterado")
    assert any(
        str(l.recurso_id) == aid and "agent_md" in (l.detalhe or {}).get("campos", [])
        for l in linhas
    )
