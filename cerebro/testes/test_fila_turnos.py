"""Testes da fila de TURNOS da IA criadora (turno em segundo plano).

Cobrem o worker (`executar_turno`) sem LLM — `responder_turno` é substituído: conclusão
com resultado gravado, falha marcada de forma VISÍVEL e HUMANA (sem corromper a conversa),
conversa sumida, recuperação de órfãos (reinício) e de turnos presos (worker travado), e a
humanização da mensagem de erro.

Nota de transação: nos testes tudo roda numa transação revertida (savepoints). No worker
de produção o turno já está COMMITADO como `em_andamento` antes de rodar; por isso aqui
comitamos o turno antes de `executar_turno`, para o rollback interno (no caminho de erro)
não descartar o próprio turno — espelhando produção."""

from datetime import datetime, timedelta, timezone

import fila_turnos
from modelos import ConversaCriacao, TurnoCriacao


def _fake_responder_ok(sessao, conversa, mensagem, *, usuario=None, chaves=None,
                       origem="legado", modelo=None, **kw):
    conversa.mensagens = (conversa.mensagens or []) + [
        {"papel": "usuario", "conteudo": mensagem},
        {"papel": "ia", "conteudo": "Feito!", "chips": ["Ok"], "uso": {}},
    ]
    return {
        "resposta": "Feito!", "chips": ["Ok"], "time_id": None, "time": None,
        "memoria": [], "uso": {},
    }


def _turno_committed(sessao, org, usuario, *, estado="em_andamento", **campos):
    conversa = ConversaCriacao(organizacao_id=org.id, criada_por_id=usuario.id)
    sessao.add(conversa)
    sessao.flush()
    turno = TurnoCriacao(
        conversa_id=conversa.id, usuario_id=usuario.id, pergunta="oi",
        estado=estado, **campos,
    )
    sessao.add(turno)
    sessao.commit()
    return conversa, turno


def test_executar_turno_conclui_e_grava_resultado(monkeypatch, sessao, dados):
    monkeypatch.setattr("fila_turnos.responder_turno", _fake_responder_ok)
    conversa, turno = _turno_committed(sessao, dados["orgA"], dados["operador"])

    fila_turnos.executar_turno(sessao, turno)

    assert turno.estado == "concluido"
    assert turno.erro_mensagem is None
    assert turno.resultado["resposta"] == "Feito!"
    assert turno.atividade is None and turno.finalizado_em is not None
    # a conversa recebeu o par de mensagens (a fala não se perdeu)
    assert len(conversa.mensagens) == 2


def test_executar_turno_erro_marca_visivel_e_humano(monkeypatch, sessao, dados):
    def _boom(*a, **k):
        raise RuntimeError("Error 529: Overloaded")

    monkeypatch.setattr("fila_turnos.responder_turno", _boom)
    conversa, turno = _turno_committed(sessao, dados["orgA"], dados["operador"])

    fila_turnos.executar_turno(sessao, turno)

    turno_relido = sessao.get(TurnoCriacao, turno.id)
    assert turno_relido.estado == "erro"
    # mensagem HUMANA (nunca stack trace), reconhecendo a sobrecarga e o Reenviar
    assert "sobrecarregada" in turno_relido.erro_mensagem.lower()
    assert "reenviar" in turno_relido.erro_mensagem.lower()
    # a conversa NÃO foi corrompida (o rollback desfez a mutação parcial)
    assert (conversa.mensagens or []) == []


def test_marcar_orfas_recupera_em_andamento(sessao, dados):
    _, turno = _turno_committed(sessao, dados["orgA"], dados["operador"])

    n = fila_turnos.marcar_orfas(sessao)

    assert n >= 1
    assert sessao.get(TurnoCriacao, turno.id).estado == "erro"
    assert "reinício" in sessao.get(TurnoCriacao, turno.id).erro_mensagem


def test_recuperar_turnos_presos_so_mata_o_travado(sessao, dados):
    agora = datetime.now(timezone.utc)
    velho = agora - timedelta(minutes=fila_turnos.TETO_INATIVIDADE_TURNO_MIN + 5)
    _, preso = _turno_committed(
        sessao, dados["orgA"], dados["operador"],
        iniciado_em=velho, atividade_em=velho,
    )
    _, ativo = _turno_committed(
        sessao, dados["orgA"], dados["observador"],
        iniciado_em=agora, atividade_em=agora,
    )

    n = fila_turnos.recuperar_turnos_presos(sessao)

    assert n == 1
    assert sessao.get(TurnoCriacao, preso.id).estado == "erro"
    # o turno com heartbeat recente NÃO é morto
    assert sessao.get(TurnoCriacao, ativo.id).estado == "em_andamento"


def test_mensagem_humana_categoriza():
    assert "sobrecarregada" in fila_turnos._mensagem_humana(Exception("overloaded 529")).lower()
    assert "demorou" in fila_turnos._mensagem_humana(Exception("Read timeout")).lower()
    # genérico ainda é humano e oferece Reenviar
    generico = fila_turnos._mensagem_humana(Exception("algo inesperado"))
    assert "reenviar" in generico.lower()
