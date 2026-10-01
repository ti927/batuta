"""Instrumento da ORGANIZAÇÃO × do TIME (Fase 4, 2026-09-29).

Um instrumento da organização aparece para todos os times dela, vai para o cinto de
qualquer agente, só admin o configura; rebaixar é recusado enquanto outro time o usa;
excluir é recusado enquanto está em uso; duplicar um time o referencia; excluir o time
de origem o muda de casa; custo fica com o time que executou; bot da organização não
atende conversa.
"""

import uuid

import pytest
from sqlalchemy import select

import segredos_instrumento as si
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    Conversa,
    Instrumento,
    MensagemConversa,
    Time,
)


@pytest.fixture
def org(sessao, dados):
    """Time A (origem) e time B na mesma organização; um instrumento da organização
    morando em A; um agente em cada time."""
    time_b = Time(organizacao_id=dados["orgA"].id, nome="Time B")
    sessao.add(time_b)
    sessao.flush()
    inst = Instrumento(time_id=dados["timeA"].id, nome="WordPress da empresa",
                       tipo="gerar_pdf", configuracao={}, escopo="organizacao")
    so_a = Instrumento(time_id=dados["timeA"].id, nome="Só do A", tipo="gerar_pdf", configuracao={})
    ag_a = Agente(time_id=dados["timeA"].id, nome="Agente A", papel="agente")
    ag_b = Agente(time_id=time_b.id, nome="Agente B", papel="agente")
    sessao.add_all([inst, so_a, ag_a, ag_b])
    sessao.flush()
    return {"time_b": time_b, "inst": inst, "so_a": so_a, "ag_a": ag_a, "ag_b": ag_b}


def _ids(r):
    return {i["id"] for i in r.json()}


# ───────────────────────────── ver e encaixar ─────────────────────────────

def test_time_b_ve_o_da_organizacao_mas_nao_o_do_time_a(cliente, entrar, dados, org):
    entrar(dados["operador"])
    ids = _ids(cliente.get(f"/times/{org['time_b'].id}/instrumentos"))
    assert str(org["inst"].id) in ids and str(org["so_a"].id) not in ids
    lido = next(i for i in cliente.get(f"/times/{org['time_b'].id}/instrumentos").json()
                if i["id"] == str(org["inst"].id))
    assert lido["escopo"] == "organizacao"


def test_outra_organizacao_nao_ve(cliente, entrar, dados, org, sessao):
    time_x = Time(organizacao_id=dados["orgB"].id, nome="X")
    sessao.add(time_x)
    sessao.flush()
    entrar(dados["estranho"])
    assert str(org["inst"].id) not in _ids(cliente.get(f"/times/{time_x.id}/instrumentos"))


def test_operador_encaixa_o_da_organizacao_em_agente_de_outro_time(cliente, entrar, dados, org):
    entrar(dados["operador"])
    r = cliente.post(f"/agentes/{org['ag_b'].id}/instrumentos", json={"instrumento_id": str(org["inst"].id)})
    assert r.status_code in (200, 201), r.text
    # mas não o que é só do time A
    r = cliente.post(f"/agentes/{org['ag_b'].id}/instrumentos", json={"instrumento_id": str(org["so_a"].id)})
    assert r.status_code == 404


# ───────────────────────────── quem configura ─────────────────────────────

def test_so_admin_cria_da_organizacao(cliente, entrar, dados):
    corpo = {"nome": "Bot avisos", "tipo": "gerar_pdf", "configuracao": {}, "escopo": "organizacao"}
    entrar(dados["operador"])
    assert cliente.post(f"/times/{dados['timeA'].id}/instrumentos", json=corpo).status_code == 403
    entrar(dados["admin"])
    r = cliente.post(f"/times/{dados['timeA'].id}/instrumentos", json=corpo)
    assert r.status_code == 201 and r.json()["escopo"] == "organizacao"


def test_so_admin_mexe_no_da_organizacao(cliente, entrar, dados, org):
    corpo = {"nome": "WordPress da empresa", "configuracao": {}}
    entrar(dados["operador"])
    assert cliente.put(f"/instrumentos/{org['inst'].id}", json=corpo).status_code == 403
    entrar(dados["admin"])
    assert cliente.put(f"/instrumentos/{org['inst'].id}", json=corpo).status_code == 200


def test_promover_e_rebaixar(cliente, entrar, dados, org, sessao):
    entrar(dados["operador"])
    promover = {"nome": "Só do A", "configuracao": {}, "escopo": "organizacao"}
    assert cliente.put(f"/instrumentos/{org['so_a'].id}", json=promover).status_code == 403
    entrar(dados["admin"])
    assert cliente.put(f"/instrumentos/{org['so_a'].id}", json=promover).json()["escopo"] == "organizacao"
    # usado pelo time B → não dá para rebaixar
    sessao.add(AgenteInstrumento(agente_id=org["ag_b"].id, instrumento_id=org["so_a"].id))
    sessao.flush()
    r = cliente.put(f"/instrumentos/{org['so_a'].id}", json={**promover, "escopo": "time"})
    assert r.status_code == 409 and "Time B" in r.json()["detail"]


# ───────────────────────────── usado por e excluir ─────────────────────────────

def test_usado_por_e_excluir_bloqueado(cliente, entrar, dados, org, sessao):
    sessao.add(AgenteInstrumento(agente_id=org["ag_b"].id, instrumento_id=org["inst"].id))
    auto = Automacao(time_id=org["time_b"].id, nome="Fluxo B", tipo_gatilho="manual",
                     configuracao_gatilho={}, ativa=False,
                     cadeia={"inicial": "n", "nos": [{"id": "n", "tipo": "agente", "ref": str(org["ag_b"].id), "saidas": []}]})
    sessao.add(auto)
    sessao.flush()
    entrar(dados["admin"])
    uso = cliente.get(f"/instrumentos/{org['inst'].id}/uso").json()
    assert [t["nome"] for t in uso["times"]] == ["Time B"]
    assert [a["nome"] for a in uso["agentes"]] == ["Agente B"]
    assert [a["nome"] for a in uso["automacoes"]] == ["Fluxo B"]
    r = cliente.delete(f"/instrumentos/{org['inst'].id}")
    assert r.status_code == 409 and "Agente B" in r.json()["detail"]
    assert cliente.delete(f"/instrumentos/{org['so_a'].id}").status_code == 204  # sem uso


# ───────────────────────────── duplicar e excluir time ─────────────────────────────

def test_duplicar_referencia_o_da_organizacao(cliente, entrar, dados, org, sessao):
    si.salvar_segredos(sessao, org["inst"].id, {"chave_api": "SEGREDO"})
    sessao.add(AgenteInstrumento(agente_id=org["ag_b"].id, instrumento_id=org["inst"].id))
    sessao.flush()
    entrar(dados["admin"])
    novo = cliente.post(f"/times/{org['time_b'].id}/duplicar", json={"nome": "B2"}).json()
    ag_copia = sessao.scalars(select(Agente).where(Agente.time_id == uuid.UUID(novo["id"]))).one()
    cinto = sessao.scalars(select(AgenteInstrumento.instrumento_id).where(AgenteInstrumento.agente_id == ag_copia.id)).all()
    assert cinto == [org["inst"].id]  # o MESMO instrumento, não uma cópia
    assert sessao.scalars(select(Instrumento).where(Instrumento.time_id == uuid.UUID(novo["id"]))).all() == []
    assert "WordPress da empresa" not in novo["instrumentos_a_conectar"]


def test_excluir_o_time_de_origem_muda_a_casa(cliente, entrar, dados, org, sessao):
    sessao.add(AgenteInstrumento(agente_id=org["ag_b"].id, instrumento_id=org["inst"].id))
    sessao.flush()
    entrar(dados["admin"])
    assert cliente.delete(f"/times/{dados['timeA'].id}").status_code == 204
    sessao.refresh(org["inst"])
    assert org["inst"].time_id == org["time_b"].id  # foi para quem o usa


# ───────────────────────────── bot da organização ─────────────────────────────

def test_bot_da_organizacao_nao_atende_conversa(sessao, dados, org, monkeypatch):
    from mensageria import servico, telegram

    enviados = []
    monkeypatch.setattr(servico.telegram, "enviar", lambda t, c, x: enviados.append(x) or {"ok": True})
    bot = Instrumento(time_id=dados["timeA"].id, nome="Bot avisos", tipo="enviar_telegram",
                      configuracao={"destinatario_padrao": "555"}, escopo="organizacao")
    sessao.add(bot)
    sessao.flush()
    si.salvar_segredos(sessao, bot.id, {"token_bot": "tok"})
    sessao.add(AgenteInstrumento(agente_id=org["ag_a"].id, instrumento_id=bot.id))
    sessao.flush()
    assert servico.agente_atendente(sessao, bot.id) is None
    conv, processar = servico.registrar_entrada(
        sessao, bot, telegram.MensagemEntrante("555", "Julio", "oi", None))
    assert processar is False and "só envia avisos" in enviados[-1]


def test_aprovacao_de_outro_time_pelo_bot_da_organizacao(sessao, dados, org):
    from mensageria import aprovacao, servico, telegram
    from test_aprovacao_por_execucao import _pausada_com_pedido
    from test_aprovacao_por_canal import _automacao

    bot = Instrumento(time_id=dados["timeA"].id, nome="Bot avisos", tipo="enviar_telegram",
                      configuracao={"destinatario_padrao": "555"}, escopo="organizacao")
    sessao.add(bot)
    sessao.flush()
    # automação do time B pede aprovação pelo bot que mora no time A
    auto_b = _automacao(sessao, {"timeA": org["time_b"]}, org["ag_b"], canal=bot)
    ex = _pausada_com_pedido(sessao, auto_b, org["ag_b"], bot, codigo="cB", mensagem_id=9)
    conv, processar = servico.registrar_entrada(
        sessao, bot, telegram.MensagemEntrante("555", "Julio", "Aprovado", None, botao_codigo="cB", botao_id="x"))
    assert processar and conv.execucao_id == ex.id


def test_custo_da_aprovacao_vai_para_o_time_que_executou(sessao, dados, org):
    import custos_time

    bot = Instrumento(time_id=dados["timeA"].id, nome="Bot avisos", tipo="enviar_telegram",
                      configuracao={}, escopo="organizacao")
    sessao.add(bot)
    sessao.flush()
    conv = Conversa(instrumento_id=bot.id, contato_chave="555", estado="aberta")
    sessao.add(conv)
    sessao.flush()
    sessao.add(MensagemConversa(conversa_id=conv.id, papel="agente", conteudo="ok", uso=[{
        "modelo": "claude-haiku-4-5", "tokens_entrada": 1000, "tokens_saida": 100,
        "categoria": "mensageria", "agente_id": str(org["ag_b"].id)}]))
    sessao.flush()
    assert len(custos_time.mensagens_do_time(sessao, org["time_b"].id)) == 1
    assert custos_time.mensagens_do_time(sessao, dados["timeA"].id) == []


def test_cinto_do_agente_traz_o_resumo_dos_segredos(cliente, entrar, dados, org, sessao):
    """O editor aberto a partir do cinto precisa saber o que já está guardado; sem o
    resumo, ele pedia endereço e token de novo e barrava o salvar (Zernio, 29/09)."""
    si.salvar_segredos(sessao, org["inst"].id, {"url": "https://mcp.exemplo/abcd"})
    sessao.add(AgenteInstrumento(agente_id=org["ag_b"].id, instrumento_id=org["inst"].id))
    sessao.flush()
    entrar(dados["operador"])
    cinto = cliente.get(f"/agentes/{org['ag_b'].id}/instrumentos").json()
    lido = next(i for i in cinto if i["id"] == str(org["inst"].id))
    assert lido["segredos"] == {"url": "abcd"}
