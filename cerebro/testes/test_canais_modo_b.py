"""Modo B — uma mensagem inicia um fluxo novo (Passo 7).

Contato CONHECIDO manda mensagem ao bot; se há automação ativa com gatilho
'mensagem_recebida' ligada ao canal, nasce uma execução (enfileirada) com a
mensagem como entrada e a ORIGEM carimbada (para a resposta voltar a quem
mandou). Identidade desconhecida é ignorada (mas fica logada).
"""

from sqlalchemy import select

from criacao.ferramentas import _validar_gatilho
from modelos import Automacao, Canal, Execucao, IdentidadeCanal, MensagemCanal


def _setup(sessao, dados, *, com_identidade=True, com_automacao=True, ativa=True):
    canal = Canal(
        organizacao_id=dados["orgA"].id, tipo="telegram", nome="Tg", config={}, ativo=True
    )
    sessao.add(canal)
    sessao.flush()
    if com_identidade:
        sessao.add(
            IdentidadeCanal(
                organizacao_id=dados["orgA"].id,
                canal_id=canal.id,
                identificador_externo="5175",
                rotulo="Julio",
            )
        )
    if com_automacao:
        sessao.add(
            Automacao(
                time_id=dados["timeA"].id,
                nome="Atendimento",
                tipo_gatilho="mensagem_recebida",
                configuracao_gatilho={"canal_id": str(canal.id)},
                cadeia={},
                ativa=ativa,
            )
        )
    sessao.flush()
    return canal


def _update(chat_id="5175", texto="quero saber do meu pedido", update_id=1):
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": texto}}


def _execucoes(sessao, dados):
    return sessao.scalars(
        select(Execucao)
        .join(Automacao, Execucao.automacao_id == Automacao.id)
        .where(Automacao.time_id == dados["timeA"].id)
    ).all()


def test_modo_b_inicia_fluxo_para_contato_conhecido(cliente, sessao, dados):
    canal = _setup(sessao, dados)
    r = cliente.post(f"/canais/{canal.id}/webhook", json=_update())
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["modo"] == "B"
    execs = _execucoes(sessao, dados)
    assert len(execs) == 1
    e = execs[0]
    assert e.estado == "aguardando"  # enfileirada (a fila roda depois)
    assert (e.entrada or {}).get("texto") == "quero saber do meu pedido"
    assert e.origem_canal_id == canal.id
    assert e.origem_identificador == "5175"
    # A mensagem recebida ficou ligada à execução.
    entrada = sessao.scalars(
        select(MensagemCanal).where(MensagemCanal.direcao == "entrada")
    ).first()
    assert entrada.execucao_id == e.id


def test_identidade_desconhecida_e_ignorada_mas_logada(cliente, sessao, dados):
    canal = _setup(sessao, dados, com_identidade=False)
    r = cliente.post(f"/canais/{canal.id}/webhook", json=_update(chat_id="000"))
    assert r.json().get("ignorado") == "identidade desconhecida"
    assert _execucoes(sessao, dados) == []
    # Mas a mensagem foi registrada (log de não-roteada).
    assert sessao.scalars(
        select(MensagemCanal).where(MensagemCanal.canal_id == canal.id)
    ).first() is not None


def test_sem_automacao_ignora(cliente, sessao, dados):
    canal = _setup(sessao, dados, com_automacao=False)
    r = cliente.post(f"/canais/{canal.id}/webhook", json=_update())
    assert r.json().get("ignorado") == "sem automação para este canal"
    assert _execucoes(sessao, dados) == []


def test_automacao_inativa_nao_dispara(cliente, sessao, dados):
    canal = _setup(sessao, dados, ativa=False)
    r = cliente.post(f"/canais/{canal.id}/webhook", json=_update())
    assert r.json().get("ignorado") == "sem automação para este canal"
    assert _execucoes(sessao, dados) == []


# ─────────────────── validação do gatilho mensagem_recebida ──────────────────


def test_gatilho_mensagem_recebida_exige_canal():
    assert _validar_gatilho("mensagem_recebida", {}) is not None
    assert _validar_gatilho("mensagem_recebida", {"canal_id": ""}) is not None
    assert _validar_gatilho("mensagem_recebida", {"canal_id": "abc"}) is None
