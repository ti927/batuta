"""O agendamento que NÃO disparou: avisar, ver, editar e resgatar.

Três buracos que se agravavam entre si. O texto que o AGENTE monta (`agendamentos.
entrada`) nunca saía do banco — a tela mostrava a hora e nada do conteúdo; não havia
como editar um agendamento, só cancelar; e a queda ia apenas para o log do servidor,
que ninguém lê. O resultado prático: uma automação momentaneamente desativada matava
um disparo importante em silêncio, e refazê-lo à mão exigia adivinhar o que o agente
tinha escrito.

Aqui se prova o conserto das três pontas: o evento no banco de logs (§12-A), a leitura
e a edição de um pendente, e o resgate de um cancelado (rodar agora ou reagendar).
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import agendador
from modelos import Agendamento, Automacao, EventoLog, Execucao


def _auto(sessao, dados, *, ativa=True, nome="Alvo"):
    a = Automacao(
        time_id=dados["timeA"].id,
        nome=nome,
        tipo_gatilho="webhook",
        cadeia=[],
        ativa=ativa,
    )
    sessao.add(a)
    sessao.flush()
    return a


def _pendente(sessao, alvo, *, entrada=None, daqui=timedelta(hours=1)):
    ag = Agendamento(
        automacao_id=alvo.id,
        quando_executar=datetime.now(timezone.utc) + daqui,
        estado="pendente",
        entrada=entrada,
    )
    sessao.add(ag)
    sessao.flush()
    return ag


def _cancelado(sessao, alvo, *, entrada="texto do agente"):
    """Um agendamento que não disparou — o estado de onde parte todo o resgate."""
    ag = Agendamento(
        automacao_id=alvo.id,
        quando_executar=datetime.now(timezone.utc) - timedelta(hours=1),
        estado="cancelado",
        entrada=entrada,
        motivo="A automação-alvo estava desativada (em repouso) quando chegou a hora.",
    )
    sessao.add(ag)
    sessao.flush()
    return ag


def _com_log_na_sessao(monkeypatch, sessao):
    """O escritor de eventos abre a PRÓPRIA sessão — aponta para a do teste."""
    import sessao as sessao_mod
    from observabilidade import escritor

    monkeypatch.setattr(escritor, "EH_LOCAL", False)  # em local ele não persiste
    monkeypatch.setattr(sessao, "close", lambda: None)
    monkeypatch.setattr(sessao_mod, "CriadorDeSessao", lambda: sessao)


# ───────── §12-A: a queda tem endereço no banco de logs, não só no do servidor ───────


def test_cancelamento_por_alvo_inativo_grava_evento(monkeypatch, sessao, dados):
    _com_log_na_sessao(monkeypatch, sessao)
    alvo = _auto(sessao, dados, ativa=False, nome="Semanal")
    ag = _pendente(sessao, alvo, daqui=-timedelta(minutes=1))

    agendador.varrer_agendamentos(sessao)

    evento = sessao.scalars(
        select(EventoLog).where(EventoLog.acao == "agendamento.nao_disparou")
    ).first()
    assert evento is not None, "um disparo que devia acontecer e não aconteceu é falha"
    assert evento.nivel == "error"
    assert evento.detalhe["causa"] == "alvo_desativado"
    assert evento.detalhe["automacao"] == "Semanal"
    assert str(ag.id) == str(evento.recurso_id)


def test_cancelamento_por_alvo_removido_grava_causa_propria(monkeypatch, sessao, dados):
    """Alvo apagado e alvo desligado são problemas diferentes: um se resolve religando,
    o outro não tem volta. O evento precisa distinguir.

    O alvo sumido é um ramo DEFENSIVO: a chave estrangeira é `ondelete=CASCADE`, então
    apagar a automação apaga os agendamentos dela junto — na prática só uma corrida
    (apagar entre a leitura da lista e a leitura do alvo) chega aqui. Por isso o teste
    força a condição em vez de tentar produzi-la apagando algo, o que a FK impediria."""
    _com_log_na_sessao(monkeypatch, sessao)
    alvo = _auto(sessao, dados, ativa=True)
    ag = _pendente(sessao, alvo, daqui=-timedelta(minutes=1))

    get_real = sessao.get
    monkeypatch.setattr(
        sessao,
        "get",
        lambda modelo, ident, *a, **kw: (
            None if modelo is Automacao else get_real(modelo, ident, *a, **kw)
        ),
    )
    agendador.varrer_agendamentos(sessao)
    monkeypatch.undo()

    evento = sessao.scalars(
        select(EventoLog).where(EventoLog.acao == "agendamento.nao_disparou")
    ).first()
    assert evento is not None and evento.detalhe["causa"] == "alvo_removido"


def test_disparo_bem_sucedido_nao_gera_evento_de_falha(monkeypatch, sessao, dados):
    """Controle positivo: sem ele, um evento gravado em TODA varredura passaria nos
    dois testes acima sem provar nada."""
    _com_log_na_sessao(monkeypatch, sessao)
    alvo = _auto(sessao, dados, ativa=True)
    _pendente(sessao, alvo, daqui=-timedelta(minutes=1))

    assert agendador.varrer_agendamentos(sessao) == 1
    assert (
        sessao.scalars(
            select(EventoLog).where(EventoLog.acao == "agendamento.nao_disparou")
        ).first()
        is None
    )


# ───────────────── ver o texto que o agente montou (era invisível) ──────────────────


def test_listagens_mostram_a_entrada_do_agente(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    alvo = _auto(sessao, dados)
    _pendente(sessao, alvo, entrada="Consolidar reembolsos de 01/09 a 05/09")

    por_automacao = cliente.get(f"/automacoes/{alvo.id}/agendamentos").json()
    assert por_automacao[0]["entrada"] == "Consolidar reembolsos de 01/09 a 05/09"

    do_time = cliente.get(f"/times/{dados['timeA'].id}/agendamentos").json()
    assert do_time[0]["entrada"] == "Consolidar reembolsos de 01/09 a 05/09"


def test_lista_do_time_diz_se_o_alvo_esta_ativo(cliente, entrar, dados, sessao):
    """Sem isto a tela deixaria reagendar em silêncio para uma automação ainda
    desligada — e o disparo morreria de novo, pelo mesmo motivo."""
    entrar(dados["operador"])
    desligada = _auto(sessao, dados, ativa=False, nome="Desligada")
    _cancelado(sessao, desligada)

    linha = cliente.get(f"/times/{dados['timeA'].id}/agendamentos").json()[0]
    assert linha["automacao_ativa"] is False
    assert linha["recuperado_em"] is None and linha["execucao_id"] is None


# ─────────────────────────── editar um pendente ────────────────────────────────────


def test_editar_corrige_o_texto_do_agente(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    ag = _pendente(sessao, _auto(sessao, dados), entrada="texto errado do agente")

    r = cliente.patch(f"/agendamentos/{ag.id}", json={"entrada": "texto certo"})
    assert r.status_code == 200 and r.json()["entrada"] == "texto certo"
    sessao.refresh(ag)
    assert ag.entrada == "texto certo"


def test_editar_muda_o_horario(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    ag = _pendente(sessao, _auto(sessao, dados))
    novo = datetime.now(timezone.utc) + timedelta(days=3)

    r = cliente.patch(
        f"/agendamentos/{ag.id}", json={"quando_executar": novo.isoformat()}
    )
    assert r.status_code == 200
    sessao.refresh(ag)
    assert abs((ag.quando_executar - novo).total_seconds()) < 2


def test_editar_recusa_horario_no_passado(cliente, entrar, dados, sessao):
    """Mesma regra do instrumento (piso de ~1 min): a tela e o agente não podem
    aceitar coisas diferentes."""
    entrar(dados["operador"])
    ag = _pendente(sessao, _auto(sessao, dados))
    passado = datetime.now(timezone.utc) - timedelta(hours=1)

    r = cliente.patch(
        f"/agendamentos/{ag.id}", json={"quando_executar": passado.isoformat()}
    )
    assert r.status_code == 400 and "futuro" in r.json()["detail"].lower()


def test_editar_recusa_o_que_ja_nao_e_pendente(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    ag = _cancelado(sessao, _auto(sessao, dados))

    r = cliente.patch(f"/agendamentos/{ag.id}", json={"entrada": "tarde demais"})
    assert r.status_code == 409


def test_editar_exige_operador(cliente, entrar, dados, sessao):
    entrar(dados["observador"])
    ag = _pendente(sessao, _auto(sessao, dados))

    assert cliente.patch(f"/agendamentos/{ag.id}", json={"entrada": "x"}).status_code == 403


# ───────────────────────── resgatar o que não disparou ─────────────────────────────


def test_recuperar_dispara_agora_com_o_texto_guardado(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    # Ainda desligada de propósito: o disparo à mão roda mesmo assim (avisar, não
    # impedir — a mesma decisão do nó "Chamar outra automação").
    alvo = _auto(sessao, dados, ativa=False)
    ag = _cancelado(sessao, alvo, entrada="Consolidar reembolsos")

    r = cliente.post(f"/agendamentos/{ag.id}/recuperar", json={})
    assert r.status_code == 200 and r.json()["modo"] == "disparado"

    sessao.refresh(ag)
    assert ag.recuperado_em is not None and ag.execucao_id is not None
    ex = sessao.get(Execucao, ag.execucao_id)
    assert ex.entrada["texto"] == "Consolidar reembolsos"
    assert ex.estado == "aguardando"


def test_recuperar_nao_conta_no_disjuntor(cliente, entrar, dados, sessao):
    """Quem clicou está olhando a tela. Se o resgate contasse como falha "sozinha", a
    automação poderia ser desligada por baixo de quem a estava resgatando."""
    from orquestracao import circuito

    entrar(dados["operador"])
    ag = _cancelado(sessao, _auto(sessao, dados))

    cliente.post(f"/agendamentos/{ag.id}/recuperar", json={})
    sessao.refresh(ag)
    ex = sessao.get(Execucao, ag.execucao_id)
    assert ex.origem == "recuperacao"
    assert ex.origem not in circuito.ORIGENS_SOZINHA


def test_recuperar_reagenda_para_outro_horario(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    ag = _cancelado(sessao, _auto(sessao, dados), entrada="texto original")
    quando = datetime.now(timezone.utc) + timedelta(days=1)

    r = cliente.post(
        f"/agendamentos/{ag.id}/recuperar", json={"quando_executar": quando.isoformat()}
    )
    assert r.status_code == 200 and r.json()["modo"] == "reagendado"

    novo = sessao.get(Agendamento, uuid.UUID(r.json()["novo_agendamento_id"]))
    assert novo.estado == "pendente" and novo.entrada == "texto original"
    assert abs((novo.quando_executar - quando).total_seconds()) < 2
    sessao.refresh(ag)
    assert ag.recuperado_em is not None  # o original fica marcado como tratado


def test_recuperar_corrige_o_texto_no_mesmo_gesto(cliente, entrar, dados, sessao):
    """É ao resgatar que se percebe que o agente errou o texto."""
    entrar(dados["operador"])
    ag = _cancelado(sessao, _auto(sessao, dados), entrada="texto errado")

    r = cliente.post(
        f"/agendamentos/{ag.id}/recuperar", json={"entrada": "texto corrigido"}
    )
    assert r.status_code == 200
    sessao.refresh(ag)
    assert sessao.get(Execucao, ag.execucao_id).entrada["texto"] == "texto corrigido"


def test_recuperar_so_uma_vez(cliente, entrar, dados, sessao):
    """Duplo clique num fluxo importante = trabalho em dobro de verdade."""
    entrar(dados["operador"])
    ag = _cancelado(sessao, _auto(sessao, dados))

    assert cliente.post(f"/agendamentos/{ag.id}/recuperar", json={}).status_code == 200
    r = cliente.post(f"/agendamentos/{ag.id}/recuperar", json={})
    assert r.status_code == 409 and "recuperado" in r.json()["detail"]


def test_recuperar_recusa_pendente_e_aponta_o_caminho(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    ag = _pendente(sessao, _auto(sessao, dados))

    r = cliente.post(f"/agendamentos/{ag.id}/recuperar", json={})
    assert r.status_code == 409 and "Editar" in r.json()["detail"]


def test_recuperar_recusa_horario_no_passado(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    ag = _cancelado(sessao, _auto(sessao, dados))
    passado = datetime.now(timezone.utc) - timedelta(days=1)

    r = cliente.post(
        f"/agendamentos/{ag.id}/recuperar",
        json={"quando_executar": passado.isoformat()},
    )
    assert r.status_code == 400
    sessao.refresh(ag)
    assert ag.recuperado_em is None  # uma recusa não consome o resgate


def test_recuperar_exige_operador(cliente, entrar, dados, sessao):
    entrar(dados["observador"])
    ag = _cancelado(sessao, _auto(sessao, dados))

    assert cliente.post(f"/agendamentos/{ag.id}/recuperar", json={}).status_code == 403


def test_recuperado_aparece_tratado_na_lista(cliente, entrar, dados, sessao):
    """A linha resgatada precisa dizer que já foi tratada — senão a tela reoferece o
    botão e a falha parece continuar aberta."""
    entrar(dados["operador"])
    ag = _cancelado(sessao, _auto(sessao, dados))
    cliente.post(f"/agendamentos/{ag.id}/recuperar", json={})

    linha = next(
        a
        for a in cliente.get(f"/times/{dados['timeA'].id}/agendamentos").json()
        if a["id"] == str(ag.id)
    )
    assert linha["recuperado_em"] is not None and linha["execucao_id"] is not None
