"""A resposta de aprovação vai para a EXECUÇÃO certa (2026-09-29).

Antes a resposta era roteada pela conversa (bot + chat), que guarda UMA execução: com
duas esperando a mesma pessoa no mesmo bot, a resposta ia para a mais recente e a
outra ficava órfã — ou uma aprovação valia para o pedido errado. Agora cada pedido
tem um código (nos botões Aprovar/Recusar) e o id da mensagem enviada (resposta
arrastada); sem apontar, só vale se houver um pedido aberto — senão o bot pergunta.
"""

import pytest
from sqlalchemy import select

import segredos_instrumento as si
from mensageria import aprovacao, servico, telegram
from modelos import Execucao, MensagemConversa, PassoExecucao, PedidoAprovacao
from test_aprovacao_por_canal import NO_GATE, _SessaoFake, _agente, _automacao, _canal


def _pausada_com_pedido(sessao, auto, agente, canal, *, codigo, mensagem_id, contato="555"):
    ex = Execucao(automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"})
    sessao.add(ex)
    sessao.flush()
    sessao.add(PassoExecucao(
        execucao_id=ex.id, ordem=1, agente_id=agente.id, no_id=NO_GATE,
        entrada={"texto": "x"}, estado="concluido",
        saida={"texto": "Aprova?", "instrumentos_acionados": ["pedir_aprovacao"],
               "saida_escolhida": None, "uso": [],
               "aprovacao": {"mensagem": "Aprova?", "canal_instrumento_id": str(canal.id),
                             "destinatario": contato, "codigo": codigo, "mensagem_id": mensagem_id}},
    ))
    sessao.flush()
    aprovacao.vincular_pausa(sessao, ex)
    return ex


@pytest.fixture
def dois_pedidos(sessao, dados, monkeypatch):
    enviados: list[str] = []
    monkeypatch.setattr(servico.telegram, "enviar",
                        lambda token, chat, texto: enviados.append(texto) or {"ok": True})
    canal = _canal(sessao, dados, destinatario="555")
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok-x"})
    ag = _agente(sessao, dados)
    auto_a = _automacao(sessao, dados, ag, canal=canal)
    auto_b = _automacao(sessao, dados, ag, canal=canal)
    a = _pausada_com_pedido(sessao, auto_a, ag, canal, codigo="codA", mensagem_id=101)
    b = _pausada_com_pedido(sessao, auto_b, ag, canal, codigo="codB", mensagem_id=202)
    return {"canal": canal, "a": a, "b": b, "enviados": enviados}


def _msg(texto="Aprovado", **kw):
    return telegram.MensagemEntrante(contato_chave="555", contato_nome="Julio", texto=texto, midia=None, **kw)


# ───────────────────────────── a leitura do Telegram ─────────────────────────────

def test_toque_no_botao_vira_resposta_com_o_codigo():
    m = telegram.extrair_update({"callback_query": {
        "id": "cb1", "data": "apv:codB:s", "from": {"id": 555, "first_name": "Julio"},
        "message": {"message_id": 202, "chat": {"id": 555}},
    }})
    assert (m.texto, m.botao_codigo, m.botao_id, m.contato_chave) == ("Aprovado", "codB", "cb1", "555")
    recusa = telegram.extrair_update({"callback_query": {
        "id": "cb2", "data": "apv:codB:n", "message": {"message_id": 1, "chat": {"id": 5}}}})
    assert recusa.texto == "Recusado"
    # botão que não é nosso é ignorado
    assert telegram.extrair_update({"callback_query": {"id": "x", "data": "outra-coisa"}}) is None


def test_resposta_arrastada_traz_a_mensagem_respondida():
    m = telegram.extrair_update({"message": {
        "chat": {"id": 555}, "text": "pode publicar", "reply_to_message": {"message_id": 101}}})
    assert m.responde_a == 101


def test_botoes_carregam_o_codigo():
    [[aprovar, recusar]] = telegram.botoes_de_aprovacao("abc")
    assert aprovar["callback_data"] == "apv:abc:s" and recusar["callback_data"] == "apv:abc:n"


# ───────────────────────────── o roteamento ─────────────────────────────

def test_duas_esperando_e_texto_solto_pergunta_qual(sessao, dois_pedidos):
    conv, processar = servico.registrar_entrada(sessao, dois_pedidos["canal"], _msg("aprovado"))
    assert processar is False
    assert "2 pedidos esperando" in dois_pedidos["enviados"][-1]
    # nenhuma das duas andou
    for k in ("a", "b"):
        sessao.refresh(dois_pedidos[k])
        assert dois_pedidos[k].estado == "aguardando_humano"


def test_botao_vai_para_a_execucao_do_pedido_mesmo_a_mais_antiga(sessao, dois_pedidos):
    """O caso que quebrava: a conversa apontava para a MAIS RECENTE (b)."""
    conv, processar = servico.registrar_entrada(
        sessao, dois_pedidos["canal"], _msg(botao_codigo="codA", botao_id="cb"))
    assert processar is True and conv.execucao_id == dois_pedidos["a"].id


def test_resposta_arrastada_vai_para_o_pedido_respondido(sessao, dois_pedidos):
    conv, processar = servico.registrar_entrada(
        sessao, dois_pedidos["canal"], _msg("pode", responde_a=101))
    assert processar is True and conv.execucao_id == dois_pedidos["a"].id


def test_um_so_pedido_aberto_texto_solto_vale(sessao, dois_pedidos):
    dois_pedidos["b"].estado = "concluida"
    sessao.flush()
    conv, processar = servico.registrar_entrada(sessao, dois_pedidos["canal"], _msg("ok"))
    assert processar is True and conv.execucao_id == dois_pedidos["a"].id


def test_botao_de_pedido_substituido_nao_aprova_a_pergunta_nova(sessao, dados, dois_pedidos):
    """A MESMA execução apresentou um pedido novo: o botão do anterior não vale mais."""
    a = dois_pedidos["a"]
    passo = sessao.scalars(select(PassoExecucao).where(PassoExecucao.execucao_id == a.id)).first()
    sessao.add(PassoExecucao(
        execucao_id=a.id, ordem=2, agente_id=passo.agente_id, no_id=NO_GATE,
        entrada={"texto": "x"}, estado="concluido",
        saida={**passo.saida, "aprovacao": {**passo.saida["aprovacao"], "codigo": "codA2", "mensagem_id": 303}},
    ))
    sessao.flush()
    aprovacao.vincular_pausa(sessao, a)
    conv, processar = servico.registrar_entrada(
        sessao, dois_pedidos["canal"], _msg(botao_codigo="codA", botao_id="cb"))
    assert processar is False
    assert "já foi respondido" in dois_pedidos["enviados"][-1]
    assert sessao.scalars(select(PedidoAprovacao.ativo).where(PedidoAprovacao.codigo == "codA")).one() is False


def test_ocupada_com_outro_pedido_nao_troca_no_meio(sessao, dois_pedidos):
    conv, _ = servico.registrar_entrada(
        sessao, dois_pedidos["canal"], _msg(botao_codigo="codA", botao_id="cb"))
    assert conv.estado == "bot_respondendo" and conv.execucao_id == dois_pedidos["a"].id
    conv, processar = servico.registrar_entrada(
        sessao, dois_pedidos["canal"], _msg(botao_codigo="codB", botao_id="cb2"))
    assert processar is False and conv.execucao_id == dois_pedidos["a"].id
    assert "outro pedido" in dois_pedidos["enviados"][-1]


def test_aprovar_a_antiga_pelo_botao_conclui_so_ela(sessao, dados, dois_pedidos, monkeypatch):
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    conv, processar = servico.registrar_entrada(
        sessao, dois_pedidos["canal"], _msg(botao_codigo="codA", botao_id="cb"))
    assert processar
    servico.processar_turno(conv.id)
    sessao.refresh(dois_pedidos["a"])
    sessao.refresh(dois_pedidos["b"])
    assert dois_pedidos["a"].estado == "concluida"
    assert dois_pedidos["b"].estado == "aguardando_humano"
    # e agora um texto solto vai para a que sobrou
    conv, processar = servico.registrar_entrada(sessao, dois_pedidos["canal"], _msg("aprovado"))
    assert processar and conv.execucao_id == dois_pedidos["b"].id


def test_registro_do_pedido_guarda_codigo_e_mensagem(sessao, dois_pedidos):
    p = sessao.scalars(select(PedidoAprovacao).where(PedidoAprovacao.codigo == "codB")).one()
    assert p.execucao_id == dois_pedidos["b"].id and p.mensagem_id == 202 and p.ativo


# ───────────────────────────── o envio com botões ─────────────────────────────

def test_pedido_sai_com_botoes_e_o_webhook_passa_a_receber_toques(sessao, dados, monkeypatch):
    from instrumentos import pedir_aprovacao as pa
    from instrumentos.enviar_telegram import EnviarTelegram

    canal = _canal(sessao, dados, destinatario="555")
    canal.webhook_secret = "cracha"
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok-x"})
    sessao.flush()
    monkeypatch.setattr(pa, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    webhooks: list = []
    monkeypatch.setattr(telegram, "configurar_webhook",
                        lambda token, url, segredo: webhooks.append((url, segredo)) or {"ok": True})
    enviados: list = []
    monkeypatch.setattr(EnviarTelegram, "enviar",
                        lambda self, cfg, args, botoes=None: enviados.append(botoes) or {"ok": True, "mensagem_id": 77})
    tipo = pa.PedirAprovacao()
    r = tipo.executar(tipo.Config(canal_instrumento_id=str(canal.id)), tipo.Args(mensagem="Aprova?"))
    assert r["mensagem_id"] == 77 and r["codigo"]
    assert enviados[0][0][0]["callback_data"] == f"apv:{r['codigo']}:s"
    assert webhooks and webhooks[0][1] == "cracha" and webhooks[0][0].endswith(f"/mensageria/{canal.id}/entrada")
    assert canal.conexao["botoes"] is True
    tipo.executar(tipo.Config(canal_instrumento_id=str(canal.id)), tipo.Args(mensagem="De novo?"))
    assert len(webhooks) == 1  # só na primeira vez


def test_canal_nao_conectado_manda_sem_botoes(sessao, dados, monkeypatch):
    from instrumentos import pedir_aprovacao as pa
    from instrumentos.enviar_telegram import EnviarTelegram

    canal = _canal(sessao, dados, destinatario="555")
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok-x"})
    sessao.flush()
    monkeypatch.setattr(pa, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    chamadas: list = []
    monkeypatch.setattr(EnviarTelegram, "enviar",
                        lambda self, cfg, args, botoes=None: chamadas.append(botoes) or {"ok": True, "mensagem_id": 5})
    tipo = pa.PedirAprovacao()
    tipo.executar(tipo.Config(canal_instrumento_id=str(canal.id)), tipo.Args(mensagem="Aprova?"))
    assert chamadas == [None]
