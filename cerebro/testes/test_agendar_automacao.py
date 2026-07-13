"""Testes do agendamento por agente: instrumento `agendar_automacao`, o sweeper que
dispara os vencidos, os endpoints (listar automações da org / listar-cancelar
agendamentos) e a validação de escopo (mesma organização).

O instrumento abre a PRÓPRIA sessão (`CriadorDeSessao`) — nos testes, apontamos essa
sessão para a do teste (transação revertida) e neutralizamos o `close`, para o
instrumento enxergar os dados do fixture e nada persistir.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

import agendador
import instrumentos.agendar_automacao as mod
from instrumentos.agendar_automacao import AgendarAutomacao, ArgsAgendar, ConfigAgendar
from instrumentos.base import FalhaInstrumento
from modelos import (
    Agendamento,
    Agente,
    AgenteInstrumento,
    Automacao,
    Execucao,
    Instrumento,
    Time,
)


def _auto(sessao, dados, *, tipo="webhook", ativa=True, time=None, nome="Alvo"):
    a = Automacao(
        time_id=(time or dados["timeA"]).id,
        nome=nome,
        tipo_gatilho=tipo,
        cadeia=[],
        ativa=ativa,
    )
    sessao.add(a)
    sessao.flush()
    return a


def _usar_sessao_do_teste(monkeypatch, sessao):
    """Faz o instrumento usar a MESMA sessão do teste (transação revertida)."""
    monkeypatch.setattr(sessao, "close", lambda: None)
    monkeypatch.setattr(mod, "CriadorDeSessao", lambda: sessao)


# ───────────────────────── instrumento ─────────────────────────


def test_registrado():
    from instrumentos.base import obter_tipo

    t = obter_tipo("agendar_automacao")
    assert t is not None and t.acao_irreversivel is False
    prop = t.Config.model_json_schema()["properties"]["automacao_alvo_id"]
    assert prop.get("ui") == "automacao_alvo"


def test_agenda_relativo(monkeypatch, sessao, dados):
    _usar_sessao_do_teste(monkeypatch, sessao)
    alvo = _auto(sessao, dados)
    res = AgendarAutomacao().executar(
        ConfigAgendar(automacao_alvo_id=str(alvo.id)), ArgsAgendar(dias=10)
    )
    assert res["ok"] and res["automacao_id"] == str(alvo.id)
    ag = sessao.get(Agendamento, uuid.UUID(res["agendamento_id"]))
    assert ag.estado == "pendente" and ag.automacao_id == alvo.id
    delta = ag.quando_executar - datetime.now(timezone.utc)
    assert timedelta(days=9, hours=23) < delta < timedelta(days=10, minutes=1)


def test_sem_alvo_falha():
    with pytest.raises(FalhaInstrumento) as e:
        AgendarAutomacao().executar(
            ConfigAgendar(automacao_alvo_id=""), ArgsAgendar(dias=1)
        )
    assert e.value.retentavel is False


def test_sem_tempo_falha():
    with pytest.raises(FalhaInstrumento) as e:
        AgendarAutomacao().executar(
            ConfigAgendar(automacao_alvo_id=str(uuid.uuid4())), ArgsAgendar()
        )
    assert e.value.retentavel is False and "quanto tempo" in str(e.value)


def test_data_passada_falha():
    with pytest.raises(FalhaInstrumento) as e:
        AgendarAutomacao().executar(
            ConfigAgendar(automacao_alvo_id=str(uuid.uuid4())),
            ArgsAgendar(data_hora="2020-01-01T00:00"),
        )
    assert e.value.retentavel is False


def test_data_absoluta_brt_vira_utc():
    # 09:00 em Brasília (UTC-3, sem horário de verão) = 12:00 UTC.
    q = mod._quando(ArgsAgendar(data_hora="2099-01-01T09:00"))
    assert q is not None and q.tzinfo is not None and q.hour == 12


def test_teto_de_pendentes(monkeypatch, sessao, dados):
    _usar_sessao_do_teste(monkeypatch, sessao)
    alvo = _auto(sessao, dados)
    futuro = datetime.now(timezone.utc) + timedelta(days=1)
    for _ in range(mod.TETO_PENDENTES):
        sessao.add(
            Agendamento(automacao_id=alvo.id, quando_executar=futuro, estado="pendente")
        )
    sessao.flush()
    with pytest.raises(FalhaInstrumento) as e:
        AgendarAutomacao().executar(
            ConfigAgendar(automacao_alvo_id=str(alvo.id)), ArgsAgendar(dias=1)
        )
    assert e.value.retentavel is False and "pendentes" in str(e.value)


# ───────────────────────── sweeper ─────────────────────────


def test_sweeper_dispara_vencido(sessao, dados):
    alvo = _auto(sessao, dados, ativa=True)
    ag = Agendamento(
        automacao_id=alvo.id,
        quando_executar=datetime.now(timezone.utc) - timedelta(minutes=1),
        estado="pendente",
        entrada="rodar isso",
    )
    sessao.add(ag)
    sessao.flush()
    assert agendador.varrer_agendamentos(sessao) == 1
    sessao.refresh(ag)
    assert ag.estado == "enfileirado" and ag.execucao_id is not None
    ex = sessao.get(Execucao, ag.execucao_id)
    assert ex.automacao_id == alvo.id and ex.estado == "aguardando"


def test_sweeper_pula_futuro(sessao, dados):
    alvo = _auto(sessao, dados)
    ag = Agendamento(
        automacao_id=alvo.id,
        quando_executar=datetime.now(timezone.utc) + timedelta(days=1),
        estado="pendente",
    )
    sessao.add(ag)
    sessao.flush()
    assert agendador.varrer_agendamentos(sessao) == 0
    sessao.refresh(ag)
    assert ag.estado == "pendente"


def test_sweeper_cancela_alvo_inativo(sessao, dados):
    alvo = _auto(sessao, dados, ativa=False)
    ag = Agendamento(
        automacao_id=alvo.id,
        quando_executar=datetime.now(timezone.utc) - timedelta(minutes=1),
        estado="pendente",
    )
    sessao.add(ag)
    sessao.flush()
    assert agendador.varrer_agendamentos(sessao) == 0
    sessao.refresh(ag)
    assert ag.estado == "cancelado"


# ───────────────────────── endpoints ─────────────────────────


def test_listar_automacoes_da_org(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    alvo = _auto(sessao, dados)
    r = cliente.get(f"/organizacoes/{dados['orgA'].id}/automacoes")
    assert r.status_code == 200
    assert any(
        a["id"] == str(alvo.id) and a["time_nome"] == "Time A" for a in r.json()
    )


def test_listar_e_cancelar_agendamento(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    alvo = _auto(sessao, dados)
    ag = Agendamento(
        automacao_id=alvo.id,
        quando_executar=datetime.now(timezone.utc) + timedelta(days=1),
        estado="pendente",
    )
    sessao.add(ag)
    sessao.flush()
    r = cliente.get(f"/automacoes/{alvo.id}/agendamentos")
    assert r.status_code == 200 and len(r.json()) == 1
    r = cliente.delete(f"/agendamentos/{ag.id}")
    assert r.status_code == 204
    sessao.refresh(ag)
    assert ag.estado == "cancelado"


def test_alvo_de_outra_org_recusado(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    timeB = Time(organizacao_id=dados["orgB"].id, nome="Time B")
    sessao.add(timeB)
    sessao.flush()
    autoB = _auto(sessao, dados, time=timeB, nome="B", ativa=False)
    r = cliente.post(
        f"/times/{dados['timeA'].id}/instrumentos",
        json={
            "nome": "Agendar",
            "tipo": "agendar_automacao",
            "configuracao": {"automacao_alvo_id": str(autoB.id)},
        },
    )
    assert r.status_code == 422


# ───────────────────────── duplicação (remap do alvo) ─────────────────────────


def test_duplicacao_remapeia_alvo_interno(sessao, dados):
    import duplicacao_time

    alvo = _auto(sessao, dados, nome="Semanal")
    ag = Agente(time_id=dados["timeA"].id, nome="Ag", papel="agente")
    sessao.add(ag)
    sessao.flush()
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="Agendar", tipo="agendar_automacao",
        configuracao={"automacao_alvo_id": str(alvo.id)},
    )
    sessao.add(inst)
    sessao.flush()
    sessao.add(AgenteInstrumento(agente_id=ag.id, instrumento_id=inst.id))
    sessao.flush()

    novo = duplicacao_time.duplicar_time(
        sessao, dados["timeA"], "Time A cópia", dados["admin"].id
    )
    copiado = sessao.scalars(
        select(Instrumento).where(
            Instrumento.time_id == novo.id, Instrumento.tipo == "agendar_automacao"
        )
    ).first()
    novo_auto = sessao.scalars(
        select(Automacao).where(Automacao.time_id == novo.id)
    ).first()
    # a cópia reprograma a si mesma (aponta para a automação copiada), não a original.
    assert copiado.configuracao["automacao_alvo_id"] == str(novo_auto.id)
    assert copiado.configuracao["automacao_alvo_id"] != str(alvo.id)
