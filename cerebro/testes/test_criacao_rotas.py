"""Testes das rotas da IA criadora — conversa eterna.

Cobrem o gating por papel (observador vê; operador conversa), o isolamento entre
organizações, e o ciclo iniciar → conversar. Não há mais aprovar/descartar/rascunho:
a IA escreve no time real e o consultor ativa pela tela do time. O turno é MOCKADO
(sem LLM): aqui se testa a rota e a transação, não o modelo."""

import uuid

import pytest

from modelos import ConversaCriacao


@pytest.fixture
def turno_falso(monkeypatch):
    """Substitui o turno da IA por um que só registra a fala, sem LLM nem time."""

    def _fake(sessao, conversa, mensagem, *, usuario=None, chaves=None, origem="legado", **kw):
        conversa.mensagens = (conversa.mensagens or []) + [
            {"papel": "usuario", "conteudo": mensagem},
            {"papel": "ia", "conteudo": "Proposta montada!", "chips": ["Sim", "Ajustar"], "uso": {}},
        ]
        return {
            "resposta": "Proposta montada!", "chips": ["Sim", "Ajustar"],
            "time_id": None, "time": None, "uso": {},
        }

    monkeypatch.setattr("rotas.criacao.responder_turno", _fake)


def _conversa(sessao, org, usuario) -> uuid.UUID:
    c = ConversaCriacao(organizacao_id=org.id, criada_por_id=usuario.id)
    sessao.add(c)
    sessao.commit()
    return c.id


def test_iniciar_sem_mensagem(cliente, entrar, dados):
    entrar(dados["operador"])
    resp = cliente.post(f"/organizacoes/{dados['orgA'].id}/conversas-criacao", json={})
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["mensagens"] == []
    assert corpo["time_id"] is None and corpo["time"] is None


def test_iniciar_com_mensagem_roda_turno(cliente, entrar, dados, turno_falso):
    entrar(dados["operador"])
    resp = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/conversas-criacao",
        json={"mensagem_inicial": "Quero um time de blog"},
    )
    assert resp.status_code == 201
    assert len(resp.json()["mensagens"]) == 2


def test_observador_nao_inicia(cliente, entrar, dados):
    entrar(dados["observador"])
    resp = cliente.post(f"/organizacoes/{dados['orgA'].id}/conversas-criacao", json={})
    assert resp.status_code == 403


def test_estranho_nao_enxerga_organizacao(cliente, entrar, dados):
    entrar(dados["estranho"])  # membro só da Org B
    resp = cliente.post(f"/organizacoes/{dados['orgA'].id}/conversas-criacao", json={})
    assert resp.status_code == 404


def test_enviar_mensagem_operador(cliente, entrar, dados, turno_falso, sessao):
    entrar(dados["operador"])
    cid = _conversa(sessao, dados["orgA"], dados["operador"])
    resp = cliente.post(
        f"/conversas-criacao/{cid}/mensagens", json={"mensagem": "Adiciona um redator"}
    )
    assert resp.status_code == 200
    assert resp.json()["resposta"] == "Proposta montada!"
    assert resp.json()["chips"] == ["Sim", "Ajustar"]


def test_observador_nao_envia_mensagem(cliente, entrar, dados, sessao):
    entrar(dados["observador"])
    cid = _conversa(sessao, dados["orgA"], dados["admin"])
    resp = cliente.post(f"/conversas-criacao/{cid}/mensagens", json={"mensagem": "oi"})
    assert resp.status_code == 403


def test_observador_ve_a_conversa(cliente, entrar, dados, sessao):
    entrar(dados["observador"])
    cid = _conversa(sessao, dados["orgA"], dados["admin"])
    resp = cliente.get(f"/conversas-criacao/{cid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(cid)
