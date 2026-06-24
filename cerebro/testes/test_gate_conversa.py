"""Portão CONVERSACIONAL e o ciclo de vida de mensageria.

Duas superfícies:
- TELA (`retoma.retomar_execucao` direto): re-roda o agente; pergunta → passo;
  decide → anda. (Sem ciclo de mensageria.)
- CANAL (`servico.processar_turno`): o turno do portão roda pela BORDA — entrega no
  Telegram, conta turno, rearma o relógio de inatividade; o sweeper encerra e
  cancela/estaciona a execução conforme o config. (Corrige o bug do dia 19/06: a
  pergunta saía só na thread interna e a conversa ficava aberta pra sempre.)

`executar_agente` é mockado — sem LLM.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import segredos_instrumento as si
from mensageria import aprovacao, retoma, servico, telegram
from modelos import (
    Agente,
    Automacao,
    Conversa,
    Execucao,
    Instrumento,
    MensagemConversa,
    PassoExecucao,
)

NO_GATE = "rev"


class _SessaoFake:
    """Reusa a sessão do teste (transação revertida) ignorando close(), p/ o
    processar_turno (que abre a própria sessão) ver os mesmos dados."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


def _canal(sessao, dados, destinatario="555"):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="Bot", tipo="enviar_telegram",
        configuracao={"destinatario_padrao": destinatario, "saudacao_abertura": ""},
    )
    sessao.add(inst)
    sessao.flush()
    return inst


def _agente(sessao, dados):
    ag = Agente(time_id=dados["timeA"].id, nome="Revisor", papel="agente")
    sessao.add(ag)
    sessao.flush()
    return ag


def _automacao(sessao, dados, agente, canal, configuracao=None):
    """Portão de nó-agente com DUAS saídas (gate conversacional) — ambas → fim para
    o teste exercitar a conversa sem rodar agentes a jusante."""
    no = {
        "id": NO_GATE, "tipo": "agente", "ref": str(agente.id), "gate": True,
        "aprovacao": {"instrumento_id": str(canal.id), "destinatario": "555"},
        "saidas": [
            {"rotulo": "aprovado", "quando": "ok", "destino": "fim"},
            {"rotulo": "reprovado", "quando": "ajustar", "destino": "fim"},
        ],
    }
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual",
        configuracao_gatilho={},
        cadeia={"inicial": NO_GATE, "nos": [no, {"id": "fim", "tipo": "fim", "saidas": []}]},
        ativa=False, configuracao=configuracao or {},
    )
    sessao.add(auto)
    sessao.flush()
    return auto


def _exec_pausada(sessao, auto, agente, texto="ARTIGO PARA APROVAR"):
    execucao = Execucao(
        automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"}
    )
    sessao.add(execucao)
    sessao.flush()
    sessao.add(
        PassoExecucao(
            execucao_id=execucao.id, ordem=1, agente_id=agente.id, no_id=NO_GATE,
            entrada={"texto": "rascunho"},
            saida={"texto": texto, "instrumentos_acionados": [], "saida_escolhida": None, "uso": []},
            estado="concluido",
        )
    )
    sessao.flush()
    return execucao


def _conv(sessao, execucao_id):
    return sessao.scalars(
        select(Conversa).where(Conversa.execucao_id == execucao_id)
    ).first()


def _passos(sessao, execucao_id):
    return sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao_id)
        .order_by(PassoExecucao.ordem)
    ).all()


# ─────────────────────────── TELA (retoma direto) ───────────────────────────

def _mock_rerun_tela(monkeypatch, *, ramo=None, mensagens=None):
    def fake(agente, cinto, entrada, **kwargs):
        return {
            "saida": "(narração)", "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": mensagens or {}, "ramo_escolhido": ramo,
        }
    monkeypatch.setattr(retoma, "executar_agente", fake)


def test_tela_agente_pergunta_vira_passo_e_segue_aguardando(sessao, dados, monkeypatch):
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag)

    _mock_rerun_tela(monkeypatch, ramo=None, mensagens={str(canal.id): ["Por que reprovou?"]})
    retoma.retomar_execucao(sessao, execucao, "reprovado", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"
    assert _passos(sessao, execucao.id)[-1].saida["texto"] == "Por que reprovou?"


def test_tela_agente_decide_e_o_fluxo_anda(sessao, dados, monkeypatch):
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag)

    _mock_rerun_tela(monkeypatch, ramo="aprovado")
    retoma.retomar_execucao(sessao, execucao, "ok", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"


def test_tela_teto_de_rodadas_cai_no_roteador(sessao, dados, monkeypatch):
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag)

    monkeypatch.setattr(retoma, "MAX_RODADAS_GATE", 1)

    def explode(*a, **k):
        raise AssertionError("não devia re-rodar o agente após o teto")
    monkeypatch.setattr(retoma, "executar_agente", explode)
    monkeypatch.setattr(
        retoma, "_escolher_saida",
        lambda resp, saidas: ({"rotulo": "aprovado", "destino": "fim"}, {}),
    )
    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"


def test_tela_conversa_repassa_conteudo_aprovado_ao_proximo_no(sessao, dados, monkeypatch):
    """Regressão (exec c52d7bdb): portão na TELA com 2 saídas, ao aprovar, deve
    repassar ao nó SEGUINTE o conteúdo APRESENTADO (ex.: URL+legenda do post) — e não
    o texto curto da rodada que só roteia ('aprovado!'). Sem isto o publicador recebia
    'aprovado!' sem a URL/legenda e pedia de novo, e nada era publicado."""
    canal = _canal(sessao, dados)
    n1 = _agente(sessao, dados)  # gera e apresenta (o nó-portão)
    pub = Agente(time_id=dados["timeA"].id, nome="Publicador", papel="agente")
    sessao.add(pub)
    sessao.flush()
    cadeia = {
        "inicial": NO_GATE,
        "nos": [
            {"id": NO_GATE, "tipo": "agente", "ref": str(n1.id), "gate": True,
             "saidas": [
                 {"rotulo": "aprovado", "quando": "ok", "destino": "pub"},
                 {"rotulo": "reprovado", "quando": "ajustar", "destino": NO_GATE},
             ]},
            {"id": "pub", "tipo": "agente", "ref": str(pub.id), "gate": False,
             "saidas": [{"rotulo": "publicado", "quando": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia=cadeia, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    execucao = _exec_pausada(
        sessao, auto, n1, texto="URL: http://x/y.png | LEGENDA: gatinho fofinho"
    )

    capturado: dict = {}

    def fake(agente, cinto, entrada, **kwargs):
        if kwargs.get("gate"):  # re-rodada do nó-portão: só roteia, texto curto
            return {"saida": "(aprovado!)", "instrumentos_acionados": [], "uso": [],
                    "mensagens_enviadas": {}, "ramo_escolhido": "aprovado"}
        capturado["entrada_pub"] = entrada  # o nó publicador, a jusante
        return {"saida": "publiquei", "instrumentos_acionados": ["publicar_instagram"],
                "uso": [], "mensagens_enviadas": {}, "ramo_escolhido": None}

    import orquestracao.cadeia as motor
    monkeypatch.setattr(retoma, "executar_agente", fake)
    monkeypatch.setattr(motor, "executar_agente", fake)

    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    # O publicador recebeu o conteúdo apresentado (URL + legenda), não só "aprovado!".
    assert "URL: http://x/y.png" in capturado["entrada_pub"]
    assert "LEGENDA: gatinho fofinho" in capturado["entrada_pub"]
    sessao.refresh(execucao)
    assert execucao.estado == "concluida"


def test_tela_aprova_e_agente_confirma_no_canal_nao_perde_o_conteudo(
    sessao, dados, monkeypatch
):
    """Regressão (exec 132bcaa6, 2026-06-23): aprovação pela TELA de um nó-portão cujo
    agente, ao aprovar, TAMBÉM dispara uma confirmação curta pelo canal ("aprovado!").
    Antes, o envio pelo canal ligava `veio_de_canal` e a falinha descia no lugar do
    conteúdo apresentado — o artigo se perdia e o nó seguinte publicava 'aprovado!'.
    O conteúdo apresentado (`ultimo.saida`) deve seguir adiante, não a confirmação."""
    canal = _canal(sessao, dados)
    n1 = _agente(sessao, dados)  # nó-portão: apresenta o artigo
    pub = Agente(time_id=dados["timeA"].id, nome="Publicador", papel="agente")
    sessao.add(pub)
    sessao.flush()
    cadeia = {
        "inicial": NO_GATE,
        "nos": [
            {"id": NO_GATE, "tipo": "agente", "ref": str(n1.id), "gate": True,
             "aprovacao": {"instrumento_id": str(canal.id), "destinatario": "555"},
             "saidas": [
                 {"rotulo": "aprovado", "quando": "ok", "destino": "pub"},
                 {"rotulo": "reprovado", "quando": "ajustar", "destino": NO_GATE},
             ]},
            {"id": "pub", "tipo": "agente", "ref": str(pub.id), "gate": False,
             "saidas": [{"rotulo": "publicado", "quando": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia=cadeia, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    execucao = _exec_pausada(sessao, auto, n1, texto="ARTIGO COMPLETO SOBRE CONCILIAÇÃO")

    capturado: dict = {}

    def fake(agente, cinto, entrada, **kwargs):
        if kwargs.get("gate"):  # rodada do nó-portão: decide E confirma pelo canal
            return {
                "saida": "✅ Artigo aprovado! Seguindo para publicação agora.",
                "instrumentos_acionados": ["enviar_telegram", "seguir_para"], "uso": [],
                "mensagens_enviadas": {
                    str(canal.id): ["✅ Artigo aprovado! Seguindo para publicação agora."]
                },
                "ramo_escolhido": "aprovado",
            }
        capturado["entrada_pub"] = entrada  # o nó publicador, a jusante
        return {"saida": "publiquei", "instrumentos_acionados": ["publicar_wordpress"],
                "uso": [], "mensagens_enviadas": {}, "ramo_escolhido": None}

    import orquestracao.cadeia as motor
    monkeypatch.setattr(retoma, "executar_agente", fake)
    monkeypatch.setattr(motor, "executar_agente", fake)

    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    # O publicador recebe o ARTIGO apresentado, NÃO a confirmação "aprovado!".
    assert "ARTIGO COMPLETO SOBRE CONCILIAÇÃO" in capturado["entrada_pub"]
    assert "Seguindo para publicação agora" not in capturado["entrada_pub"]
    sessao.refresh(execucao)
    assert execucao.estado == "concluida"


# ─────────────────────────── CANAL (processar_turno) ───────────────────────────

def _setup_canal(sessao, dados, monkeypatch, enviados, configuracao=None):
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico.telegram, "enviar",
        lambda token, chat, texto: enviados.append(texto) or {"ok": True},
    )
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal, configuracao=configuracao)
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)
    return canal, ag, auto, execucao


def _mock_servico_agente(monkeypatch, *, ramo=None, saida="(resposta)"):
    def fake(agente, cinto, entrada, **k):
        return {
            "saida": saida, "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {}, "ramo_escolhido": ramo,
        }
    monkeypatch.setattr(servico, "executar_agente", fake)


def _responder(sessao, canal, texto):
    conv, deve = servico.registrar_entrada(
        sessao, canal,
        telegram.MensagemEntrante(contato_chave="555", contato_nome="Chefe", texto=texto, midia=None),
    )
    assert deve
    servico.processar_turno(conv.id)
    return conv


def test_canal_vincular_pausa_arma_relogio(sessao, dados):
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)
    conv = _conv(sessao, execucao.id)
    assert conv.aguardando_ate is not None  # portão entra no sweeper (não fica aberto pra sempre)


def test_canal_agente_pergunta_entrega_no_telegram_e_segue(sessao, dados, monkeypatch):
    enviados = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    _mock_servico_agente(monkeypatch, ramo=None, saida="Por que você reprovou?")

    conv = _responder(sessao, canal, "reprovado")

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"  # segue aguardando a pessoa
    # A BORDA entregou a pergunta no Telegram (o bug era ficar só na thread interna).
    assert any("Por que você reprovou?" in t for t in enviados)
    # E não duplica o ack genérico ("ainda há etapa aguardando").
    assert not any("Ainda há uma etapa" in t for t in enviados)
    sessao.refresh(conv)
    assert conv.aguardando_ate is not None  # relógio rearmado


def test_canal_agente_decide_e_conclui(sessao, dados, monkeypatch):
    enviados = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    _mock_servico_agente(monkeypatch, ramo="aprovado", saida="Aprovado, seguindo.")

    _responder(sessao, canal, "pode aprovar")

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"  # aprovado → fim


def test_canal_agente_decide_SEM_texto_o_fluxo_anda(sessao, dados, monkeypatch):
    """O BUG do dia 19/06: o agente decidiu (chamou `seguir_para`) mas sem escrever
    nada → a borda descartava a decisão e a execução ficava 'aguardando_humano' para
    sempre. Agora a decisão é honrada mesmo sem texto, e a pessoa recebe um retorno."""
    enviados = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    _mock_servico_agente(monkeypatch, ramo="reprovado", saida="")  # decide, não fala

    conv = _responder(sessao, canal, "esse tema já foi usado, busca outro")

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"  # decisão honrada → o fluxo andou (reprovado → fim)
    sessao.refresh(conv)
    assert conv.execucao_id is None  # desvinculou ao concluir
    assert conv.turnos == 1  # o turno de decisão CONTA (anti-loop uniforme)
    # A pessoa não fica no vácuo: recebe um retorno curto pelo Telegram.
    assert any("Decisão registrada" in t for t in enviados)


def test_canal_turno_vazio_nao_fica_aberto_pra_sempre(sessao, dados, monkeypatch):
    """Turno degenerado (agente não fala NEM decide): a conversa fica
    'aguardando_resposta' (governada pelo sweeper), nunca 'aberta' para sempre."""
    enviados = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    _mock_servico_agente(monkeypatch, ramo=None, saida="")  # nada

    conv = _responder(sessao, canal, "???")

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"  # nada decidido → segue aguardando
    sessao.refresh(conv)
    assert conv.estado == "aguardando_resposta"  # entra no sweeper (não fica "aberta")
    assert conv.aguardando_ate is not None


def test_canal_teto_passa_humano_e_cancela_execucao(sessao, dados, monkeypatch):
    enviados = []
    # perfil interno → portao_acao_abandono = cancelar (default global tb é cancelar)
    canal, ag, auto, execucao = _setup_canal(
        sessao, dados, monkeypatch, enviados, configuracao={"perfil": "interno"}
    )
    conv = _conv(sessao, execucao.id)
    conv.custo_acumulado_usd = 999  # estoura o teto
    sessao.commit()

    def explode(*a, **k):
        raise AssertionError("não devia rodar o agente após o teto")
    monkeypatch.setattr(servico, "executar_agente", explode)

    _responder(sessao, canal, "reprovado")

    sessao.refresh(conv)
    sessao.refresh(execucao)
    assert conv.estado == "humano_assumiu"
    assert execucao.estado == "cancelada"  # abandono → cancelar (perfil interno)


def test_canal_portao_direto_roteia_mecanico(sessao, dados, monkeypatch):
    enviados = []
    # perfil disparo → portao_forma = direto: a palavra escolhe a saída (sem re-rodar)
    canal, ag, auto, execucao = _setup_canal(
        sessao, dados, monkeypatch, enviados, configuracao={"perfil": "disparo"}
    )

    def explode(*a, **k):
        raise AssertionError("portão direto não re-roda o agente")
    monkeypatch.setattr(servico, "executar_agente", explode)
    # roteador mecânico (mockado): a resposta "aprovado" casa a saída "aprovado"
    monkeypatch.setattr(
        "mensageria.retoma._escolher_saida",
        lambda resp, saidas: ({"rotulo": "aprovado", "destino": "fim"}, {}),
    )
    _responder(sessao, canal, "aprovado")

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"
    assert any("Decisão registrada" in t for t in enviados)  # ack mecânico


def test_canal_cancelar_nao_roda_o_agente_e_encerra(sessao, dados, monkeypatch):
    """No portão CONVERSA, responder 'cancelar' encerra ANTES de ramificar — o agente
    NÃO roda (a detecção é o 1º statement de _turno_de_portao)."""
    enviados = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)

    def explode(*a, **k):
        raise AssertionError("o agente não deve rodar quando a pessoa cancela")
    monkeypatch.setattr(servico, "executar_agente", explode)

    conv = _responder(sessao, canal, "cancelar")

    sessao.refresh(execucao)
    assert execucao.estado == "cancelada"  # encerrada sem rodar o agente
    sessao.refresh(conv)
    assert conv.execucao_id is None  # desvinculada
    assert any("encerrei" in t.lower() for t in enviados)  # ack "⛔"


def test_sweeper_encerra_portao_e_cancela_execucao(sessao, dados, monkeypatch):
    from mensageria import sweeper

    enviados = []
    monkeypatch.setattr(
        "mensageria.telegram.enviar", lambda t, c, x: enviados.append(x) or {"ok": True}
    )
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)  # sem perfil → global acao_ao_encerrar=cancelar
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)
    conv = _conv(sessao, execucao.id)
    conv.nudge_enviado = True  # já cutucado → a varredura encerra
    conv.aguardando_ate = datetime.now(timezone.utc) - timedelta(minutes=1)
    sessao.commit()

    sweeper.varrer(sessao)

    sessao.refresh(conv)
    sessao.refresh(execucao)
    assert conv.estado == "fechada"
    assert execucao.estado == "cancelada"  # portão abandonado por inatividade → cancela
    assert conv.execucao_id is None
