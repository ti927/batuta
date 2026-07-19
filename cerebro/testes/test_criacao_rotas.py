"""Testes das rotas da IA criadora — conversa eterna.

Cobrem o gating por papel (observador vê; operador conversa), o isolamento entre
organizações, e o ciclo iniciar → conversar. Não há mais aprovar/descartar/rascunho:
a IA escreve no time real e o consultor ativa pela tela do time.

O turno agora roda em SEGUNDO PLANO: o POST /mensagens só ENFILEIRA (cria o turno
`aguardando`) e devolve na hora — quem roda é o pool de `fila_turnos` (testado à parte,
em test_fila_turnos.py). Aqui se testa a rota: enfileirar, a guarda de concorrência e o
acompanhamento, sem LLM."""

import uuid

from modelos import ConversaCriacao, TurnoCriacao


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


def test_iniciar_com_mensagem_enfileira_turno(cliente, entrar, dados):
    entrar(dados["operador"])
    resp = cliente.post(
        f"/organizacoes/{dados['orgA'].id}/conversas-criacao",
        json={"mensagem_inicial": "Quero um time de blog"},
    )
    assert resp.status_code == 201
    # O turno roda em segundo plano: a conversa abre já com um turno em andamento, para a
    # tela acompanhar (não bloqueia a abertura numa requisição longa).
    corpo = resp.json()
    assert corpo["turno_em_andamento"] is not None
    assert corpo["turno_em_andamento"]["estado"] == "aguardando"


def test_observador_nao_inicia(cliente, entrar, dados):
    entrar(dados["observador"])
    resp = cliente.post(f"/organizacoes/{dados['orgA'].id}/conversas-criacao", json={})
    assert resp.status_code == 403


def test_estranho_nao_enxerga_organizacao(cliente, entrar, dados):
    entrar(dados["estranho"])  # membro só da Org B
    resp = cliente.post(f"/organizacoes/{dados['orgA'].id}/conversas-criacao", json={})
    assert resp.status_code == 404


def test_enviar_mensagem_operador_enfileira(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    cid = _conversa(sessao, dados["orgA"], dados["operador"])
    resp = cliente.post(
        f"/conversas-criacao/{cid}/mensagens", json={"mensagem": "Adiciona um redator"}
    )
    assert resp.status_code == 202
    corpo = resp.json()
    assert corpo["estado"] == "aguardando"
    # O turno foi criado e aguarda o worker (a fala não se perde — está persistida).
    turno = sessao.get(TurnoCriacao, uuid.UUID(corpo["turno_id"]))
    assert turno is not None and turno.pergunta == "Adiciona um redator"
    assert turno.usuario_id == dados["operador"].id


def test_segundo_envio_bloqueia_enquanto_o_primeiro_roda(cliente, entrar, dados, sessao):
    """Um turno de cada vez por conversa (a história é compartilhada): o segundo envio
    enquanto o primeiro ainda roda é recusado com 409, não vira dois turnos concorrentes."""
    entrar(dados["operador"])
    cid = _conversa(sessao, dados["orgA"], dados["operador"])
    primeiro = cliente.post(f"/conversas-criacao/{cid}/mensagens", json={"mensagem": "um"})
    assert primeiro.status_code == 202
    segundo = cliente.post(f"/conversas-criacao/{cid}/mensagens", json={"mensagem": "dois"})
    assert segundo.status_code == 409


def test_acompanhar_turno(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    cid = _conversa(sessao, dados["orgA"], dados["operador"])
    turno = TurnoCriacao(
        conversa_id=cid, usuario_id=dados["operador"].id, pergunta="oi",
        estado="concluido",
        resultado={"resposta": "Pronto!", "chips": ["Ok"], "uso": {}},
    )
    sessao.add(turno)
    sessao.commit()
    resp = cliente.get(f"/conversas-criacao/{cid}/turnos/{turno.id}")
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["estado"] == "concluido"
    assert corpo["resultado"]["resposta"] == "Pronto!"


def test_acompanhar_turno_de_outra_conversa_404(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    cid = _conversa(sessao, dados["orgA"], dados["operador"])
    outra = _conversa(sessao, dados["orgA"], dados["operador"])
    turno = TurnoCriacao(
        conversa_id=outra, usuario_id=dados["operador"].id, pergunta="oi",
        estado="aguardando",
    )
    sessao.add(turno)
    sessao.commit()
    # o turno existe, mas não pertence a `cid` → 404
    resp = cliente.get(f"/conversas-criacao/{cid}/turnos/{turno.id}")
    assert resp.status_code == 404


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
