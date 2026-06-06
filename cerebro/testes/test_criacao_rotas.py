"""Testes das rotas da IA criadora (Fase 9).

Cobrem o gating por papel (observador vê, operador conversa, só admin aprova),
o isolamento entre organizações, o ciclo conversar → aprovar/descartar, e a
recusa de rascunho inválido. O turno da IA é MOCKADO (sem LLM): aqui se testa a
rota e a transação, não o modelo."""

import uuid

import pytest
from sqlalchemy import select

from criacao.rascunho import AgenteRascunho, Rascunho
from modelos import ConversaCriacao, Time


@pytest.fixture
def turno_falso(monkeypatch):
    """Substitui o turno da IA por um que monta um rascunho fixo, sem LLM."""

    def _fake(conversa, mensagem, *, chaves=None, origem="legado", **kw):
        conversa.rascunho = {"time_nome": "Time Proposto", "agentes": []}
        conversa.mensagens = (conversa.mensagens or []) + [
            {"papel": "usuario", "conteudo": mensagem},
            {
                "papel": "ia",
                "conteudo": "Proposta montada!",
                "chips": ["Sim", "Ajustar"],
                "uso": {"modelo": "x", "tokens_entrada": 1, "tokens_saida": 1, "origem": origem},
            },
        ]
        return {
            "resposta": "Proposta montada!",
            "chips": ["Sim", "Ajustar"],
            "rascunho": conversa.rascunho,
            "uso": {},
        }

    monkeypatch.setattr("rotas.criacao.responder_turno", _fake)


def _conversa_com_rascunho(sessao, org, usuario, rascunho: Rascunho) -> uuid.UUID:
    c = ConversaCriacao(
        organizacao_id=org.id,
        criada_por_id=usuario.id,
        rascunho=rascunho.model_dump(mode="json"),
    )
    sessao.add(c)
    sessao.commit()
    return c.id


def test_iniciar_sem_mensagem(cliente, entrar, dados):
    entrar(dados["operador"])
    resp = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/conversas-criacao", json={}
    )
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["estado"] == "rascunho"
    assert corpo["mensagens"] == []


def test_iniciar_com_mensagem_roda_turno(cliente, entrar, dados, turno_falso):
    entrar(dados["operador"])
    resp = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/conversas-criacao",
        json={"mensagem_inicial": "Quero um time de blog"},
    )
    assert resp.status_code == 201
    corpo = resp.json()
    assert len(corpo["mensagens"]) == 2
    assert corpo["rascunho"]["time_nome"] == "Time Proposto"


def test_observador_nao_inicia(cliente, entrar, dados):
    entrar(dados["observador"])
    resp = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/conversas-criacao", json={}
    )
    assert resp.status_code == 403


def test_estranho_nao_enxerga_organizacao(cliente, entrar, dados):
    entrar(dados["estranho"])  # membro só da Org B
    resp = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/conversas-criacao", json={}
    )
    assert resp.status_code == 404


def test_enviar_mensagem_operador(cliente, entrar, dados, turno_falso, sessao):
    entrar(dados["operador"])
    cid = _conversa_com_rascunho(sessao, dados["orgA"], dados["operador"], Rascunho())
    resp = cliente.post(
        f"/conversas-criacao/{cid}/mensagens", json={"mensagem": "Adiciona um redator"}
    )
    assert resp.status_code == 200
    assert resp.json()["resposta"] == "Proposta montada!"
    assert resp.json()["chips"] == ["Sim", "Ajustar"]


def test_observador_nao_envia_mensagem(cliente, entrar, dados, sessao):
    entrar(dados["observador"])
    cid = _conversa_com_rascunho(sessao, dados["orgA"], dados["admin"], Rascunho())
    resp = cliente.post(
        f"/conversas-criacao/{cid}/mensagens", json={"mensagem": "oi"}
    )
    assert resp.status_code == 403


def test_observador_ve_a_conversa(cliente, entrar, dados, sessao):
    entrar(dados["observador"])
    cid = _conversa_com_rascunho(sessao, dados["orgA"], dados["admin"], Rascunho())
    resp = cliente.get(f"/conversas-criacao/{cid}")
    assert resp.status_code == 200


def test_aprovar_so_admin(cliente, entrar, dados, sessao):
    rasc = Rascunho(
        time_nome="Time Aprovado",
        agentes=[AgenteRascunho(nome="Chefe", papel="lider")],
    )
    cid = _conversa_com_rascunho(sessao, dados["orgA"], dados["admin"], rasc)

    # operador NÃO aprova
    entrar(dados["operador"])
    assert cliente.post(f"/conversas-criacao/{cid}/aprovar").status_code == 403

    # admin aprova → cria o time
    entrar(dados["admin"])
    resp = cliente.post(f"/conversas-criacao/{cid}/aprovar")
    assert resp.status_code == 200
    assert resp.json()["agentes"] == 1
    assert sessao.scalars(
        select(Time).where(Time.nome == "Time Aprovado")
    ).first() is not None


def test_aprovar_rascunho_invalido_422(cliente, entrar, dados, sessao):
    cid = _conversa_com_rascunho(sessao, dados["orgA"], dados["admin"], Rascunho())
    entrar(dados["admin"])
    resp = cliente.post(f"/conversas-criacao/{cid}/aprovar")
    assert resp.status_code == 422


def test_descartar_e_depois_bloqueia(cliente, entrar, dados, sessao):
    cid = _conversa_com_rascunho(sessao, dados["orgA"], dados["operador"], Rascunho())
    entrar(dados["operador"])
    assert cliente.post(f"/conversas-criacao/{cid}/descartar").status_code == 204
    # mensagem após descartar → 409
    resp = cliente.post(
        f"/conversas-criacao/{cid}/mensagens", json={"mensagem": "oi"}
    )
    assert resp.status_code == 409
