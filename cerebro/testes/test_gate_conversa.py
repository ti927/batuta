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


def test_tela_portao_com_memoria_semeia_depois_so_resposta(sessao, dados, monkeypatch):
    """P3c-B: o portão de esteira pela TELA ganha MEMÓRIA (checkpointer + thread
    `execucao:no`). 1ª retomada SEMEIA (entrada = apresentado + resposta); a 2ª usa SÓ a
    resposta do humano (o agente lembra o resto, não re-deriva)."""
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag, texto="PROPOSTA X")

    saver = object()  # checkpointer "presente" (o executar_agente é mockado)
    estado = {"tem": False}  # 1ª retomada: sem estado (semeia); 2ª: com estado
    monkeypatch.setattr(retoma.memoria_conversa, "obter", lambda: saver)
    monkeypatch.setattr(retoma.memoria_conversa, "tem_estado", lambda tid: estado["tem"])

    capt: dict = {}

    def fake(agente, cinto, entrada, **kwargs):
        capt["entrada"] = entrada
        capt["kwargs"] = kwargs
        # perguntou (ramo=None) → segue aguardando, permitindo a 2ª rodada
        return {"saida": "(pergunta)", "instrumentos_acionados": [], "uso": [],
                "mensagens_enviadas": {}, "ramo_escolhido": None}

    monkeypatch.setattr(retoma, "executar_agente", fake)

    # 1ª retomada: SEMEIA (entrada = apresentado + resposta) + passa checkpointer/thread
    retoma.retomar_execucao(sessao, execucao, "por que?", chaves={}, origens={})
    assert capt["kwargs"].get("checkpointer") is saver
    assert capt["kwargs"].get("thread_id") == f"{execucao.id}:{NO_GATE}"
    assert "PROPOSTA X" in capt["entrada"] and "por que?" in capt["entrada"]

    # 2ª retomada: já tem estado → entrada = SÓ a resposta (não re-deriva o apresentado)
    estado["tem"] = True
    sessao.refresh(execucao)
    retoma.retomar_execucao(sessao, execucao, "agora sim", chaves={}, origens={})
    assert capt["kwargs"].get("thread_id") == f"{execucao.id}:{NO_GATE}"
    assert "PROPOSTA X" not in capt["entrada"] and "agora sim" in capt["entrada"]


def test_tela_portao_sem_checkpointer_e_identico_a_hoje(sessao, dados, monkeypatch):
    """Sem checkpointer (obter()=None), a retomada pela tela usa `entrada_rerun` como
    sempre e NÃO passa checkpointer/thread — byte-idêntico ao comportamento legado."""
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag, texto="PROPOSTA Y")
    monkeypatch.setattr(retoma.memoria_conversa, "obter", lambda: None)

    capt: dict = {}

    def fake(agente, cinto, entrada, **kwargs):
        capt["entrada"] = entrada
        capt["kwargs"] = kwargs
        return {"saida": "ok", "instrumentos_acionados": [], "uso": [],
                "mensagens_enviadas": {}, "ramo_escolhido": "aprovado"}

    monkeypatch.setattr(retoma, "executar_agente", fake)
    retoma.retomar_execucao(sessao, execucao, "ok", chaves={}, origens={})
    assert "checkpointer" not in capt["kwargs"] and "thread_id" not in capt["kwargs"]
    assert "PROPOSTA Y" in capt["entrada"]  # entrada_rerun completo, como hoje


def test_tela_teto_de_rodadas_cai_no_roteador(sessao, dados, monkeypatch):
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    # Teto DIRIGIDO PELA CONFIG (Tipo de fluxo): `portao_max_rodadas` agora VALE (antes
    # o teste monkeypatchava a constante `MAX_RODADAS_GATE`, que virou só o default).
    auto = _automacao(
        sessao, dados, ag, canal, configuracao={"ajustes": {"portao_max_rodadas": 1}}
    )
    execucao = _exec_pausada(sessao, auto, ag)

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


def test_tela_teto_de_rodadas_do_no_vence_o_fluxo(sessao, dados, monkeypatch):
    """O teto DESTE portão (`no.config.portao_max_rodadas`) sobrepõe o do Tipo de fluxo:
    com 1 no nó (e o fluxo no default 8), a 1ª resposta já cai no roteador — não re-roda
    o agente. É o ganho da Onda 1: ajuste por-nó honrado também na retoma pela tela."""
    from sqlalchemy.orm.attributes import flag_modified

    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)  # fluxo sem teto → default 8
    auto.cadeia["nos"][0]["config"] = {"portao_max_rodadas": 1}
    flag_modified(auto, "cadeia")
    sessao.flush()
    execucao = _exec_pausada(sessao, auto, ag)

    def explode(*a, **k):
        raise AssertionError("não devia re-rodar o agente após o teto do nó")
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


def test_canal_portao_deixa_passo_espera_humano_no_fluxo(sessao, dados, monkeypatch):
    """Fatia 4.2 (unificação do rastro): o portão pelo CANAL passa a deixar rastro na
    timeline do FLUXO — um passo `espera_humano`, como a tela já fazia. Antes o re-run
    pelo canal sumia da inspeção de execução (a lacuna 'canal não gera passo')."""
    enviados = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    _mock_servico_agente(monkeypatch, ramo=None, saida="Por que você reprovou?")

    _responder(sessao, canal, "reprovado")

    passos = _passos(sessao, execucao.id)
    assert len(passos) == 2  # a pausa inicial (ordem 1) + o re-run pelo canal (ordem 2)
    assert passos[1].ordem == 2
    assert passos[1].tipo == "espera_humano"
    assert passos[1].agente_id == ag.id
    assert "Por que você reprovou?" in (passos[1].saida or {}).get("texto", "")
    # uso VAZIO no passo: o custo do turno vive na MensagemConversa (não conta em dobro).
    assert (passos[1].saida or {}).get("uso") == []


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
    # ajuste explícito: abandono do portão = cancelar (o default agora é estacionar)
    canal, ag, auto, execucao = _setup_canal(
        sessao, dados, monkeypatch, enviados,
        configuracao={"ajustes": {"portao_acao_abandono": "cancelar"}},
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
    # portao_forma = direto (ajuste do fluxo): a palavra escolhe a saída (sem re-rodar)
    canal, ag, auto, execucao = _setup_canal(
        sessao, dados, monkeypatch, enviados,
        configuracao={"ajustes": {"portao_forma": "direto"}},
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


def test_sweeper_estaciona_portao_por_default(sessao, dados, monkeypatch):
    """Default (estacionar): o sweeper encerra a CONVERSA do portão, mas a execução
    fica `aguardando_humano` (retomável por resposta tardia ou pela tela). Não cancela."""
    from mensageria import sweeper

    enviados = []
    monkeypatch.setattr(
        "mensageria.telegram.enviar", lambda t, c, x: enviados.append(x) or {"ok": True}
    )
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)  # sem perfil → global: estacionar
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)
    conv = _conv(sessao, execucao.id)
    conv.nudge_enviado = True  # já cutucado → a varredura encerra a conversa
    conv.aguardando_ate = datetime.now(timezone.utc) - timedelta(minutes=1)
    sessao.commit()

    sweeper.varrer(sessao)

    sessao.refresh(conv)
    sessao.refresh(execucao)
    assert conv.estado == "fechada"
    assert execucao.estado == "aguardando_humano"  # ESTACIONADA, não cancelada
    assert conv.execucao_id is None  # desvinculada — uma resposta tardia religa (Fix 2)
    assert any("aprovação ainda pode ser feita" in t for t in enviados)  # despedida cita o app


def test_sweeper_cancela_portao_quando_configurado(sessao, dados, monkeypatch):
    """Config explícito `cancelar`: o sweeper encerra a conversa E cancela a execução."""
    from mensageria import sweeper

    enviados = []
    monkeypatch.setattr(
        "mensageria.telegram.enviar", lambda t, c, x: enviados.append(x) or {"ok": True}
    )
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = _agente(sessao, dados)
    auto = _automacao(
        sessao, dados, ag, canal,
        configuracao={"ajustes": {"portao_acao_abandono": "cancelar"}},
    )
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)
    conv = _conv(sessao, execucao.id)
    conv.nudge_enviado = True
    conv.aguardando_ate = datetime.now(timezone.utc) - timedelta(minutes=1)
    sessao.commit()

    sweeper.varrer(sessao)

    sessao.refresh(conv)
    sessao.refresh(execucao)
    assert conv.estado == "fechada"
    assert execucao.estado == "cancelada"
    assert conv.execucao_id is None
    assert any("cancelando o fluxo" in t for t in enviados)  # despedida avisa o cancelamento


def test_sweeper_respeita_no_config(sessao, dados, monkeypatch):
    """Ganho da Onda 1: o sweeper honra o ajuste DESTE portão (`no.config`). O fluxo está
    no default (estacionar), mas o NÓ manda cancelar → a varredura cancela a execução."""
    from sqlalchemy.orm.attributes import flag_modified

    from mensageria import sweeper

    enviados = []
    monkeypatch.setattr(
        "mensageria.telegram.enviar", lambda t, c, x: enviados.append(x) or {"ok": True}
    )
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)  # fluxo sem ajuste → estacionar
    auto.cadeia["nos"][0]["config"] = {"portao_acao_abandono": "cancelar"}
    flag_modified(auto, "cadeia")
    sessao.flush()
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)
    conv = _conv(sessao, execucao.id)
    conv.nudge_enviado = True
    conv.aguardando_ate = datetime.now(timezone.utc) - timedelta(minutes=1)
    sessao.commit()

    sweeper.varrer(sessao)

    sessao.refresh(conv)
    sessao.refresh(execucao)
    assert conv.estado == "fechada"
    assert execucao.estado == "cancelada"  # o ajuste do NÓ venceu o default do fluxo
    assert any("cancelando o fluxo" in t for t in enviados)


def test_vincular_pausa_respeita_no_config_timeout(sessao, dados, monkeypatch):
    """O relógio de inatividade do portão usa o `timeout_min` DESTE nó quando ajustado
    (Onda 1). Fluxo no default (60 min); o nó pede 5 → `aguardando_ate` ~= agora + 5 min."""
    from sqlalchemy.orm.attributes import flag_modified

    monkeypatch.setattr("mensageria.telegram.enviar", lambda t, c, x: {"ok": True})
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)  # fluxo default (60 min)
    auto.cadeia["nos"][0]["config"] = {"timeout_min": 5}
    flag_modified(auto, "cadeia")
    sessao.flush()
    execucao = _exec_pausada(sessao, auto, ag)

    antes = datetime.now(timezone.utc)
    aprovacao.vincular_pausa(sessao, execucao)
    conv = _conv(sessao, execucao.id)

    delta_min = (conv.aguardando_ate - antes).total_seconds() / 60
    assert 4 <= delta_min <= 6  # ~5 min do nó, não os 60 do default do fluxo


# ── portao.md: instruções de FECHAMENTO chegam ao agente (Onda 2) ────────────

def test_tela_fechamento_injeta_portao_md(sessao, dados, monkeypatch):
    """Fechamento pela TELA: as instruções de FECHAMENTO do nó chegam ao agente
    (`texto_portao`). É o que faz o agente agendar E encaminhar ao aprovar."""
    from sqlalchemy.orm.attributes import flag_modified

    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    auto.cadeia["nos"][0]["instrucoes"] = {"fechamento": "AO APROVAR, AGENDE E SIGA"}
    flag_modified(auto, "cadeia")
    sessao.flush()
    execucao = _exec_pausada(sessao, auto, ag)

    capturado: dict = {}

    def fake(agente, cinto, entrada, **kwargs):
        capturado.update(kwargs)
        return {
            "saida": "ok", "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {}, "ramo_escolhido": "aprovado",
        }

    monkeypatch.setattr(retoma, "executar_agente", fake)
    retoma.retomar_execucao(sessao, execucao, "ok", chaves={}, origens={})
    assert capturado.get("texto_portao") == "AO APROVAR, AGENDE E SIGA"


def test_canal_fechamento_injeta_portao_md(sessao, dados, monkeypatch):
    """Fechamento por CANAL: idem, pela borda (`_turno_de_portao` → `_rodar_turno`)."""
    from sqlalchemy.orm.attributes import flag_modified

    enviados: list = []
    capturado: dict = {}

    def fake(agente, cinto, entrada, **k):
        capturado.update(k)
        return {
            "saida": "", "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {}, "ramo_escolhido": "aprovado",
        }

    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    auto.cadeia["nos"][0]["instrucoes"] = {"fechamento": "AO APROVAR, AGENDE PELO CANAL"}
    flag_modified(auto, "cadeia")
    sessao.flush()
    monkeypatch.setattr(servico, "executar_agente", fake)
    _responder(sessao, canal, "pode aprovar")
    assert capturado.get("texto_portao") == "AO APROVAR, AGENDE PELO CANAL"


# ─────── Aviso de expectativa do portão (derivado do Tipo de fluxo) ───────
# O agente manda o pedido; a borda (`vincular_pausa`) acrescenta UM aviso do que acontece
# se o humano não responder — prazo + destino da aprovação — montado dos parâmetros reais.

def test_vincular_pausa_avisa_expectativa_estacionar(sessao, dados, monkeypatch):
    enviados = []
    monkeypatch.setattr(telegram, "enviar", lambda t, c, x: enviados.append(x) or {"ok": True})
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)  # sem perfil → global: estacionar, 60/30
    execucao = _exec_pausada(sessao, auto, ag)

    aprovacao.vincular_pausa(sessao, execucao)

    avisos = [t for t in enviados if "batuta.team" in t]
    assert len(avisos) == 1
    assert "encerro esta conversa" in avisos[0]
    assert "90 min" in avisos[0]  # global: timeout 60 + nudge 30
    assert "continua disponível" in avisos[0]  # estacionar: aprovação segue no app

    # 2ª chamada da MESMA pausa não duplica o aviso (idempotente por passo)
    aprovacao.vincular_pausa(sessao, execucao)
    assert len([t for t in enviados if "batuta.team" in t]) == 1


def test_vincular_pausa_avisa_cancelamento_quando_abandono_cancela(sessao, dados, monkeypatch):
    enviados = []
    monkeypatch.setattr(telegram, "enviar", lambda t, c, x: enviados.append(x) or {"ok": True})
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = _agente(sessao, dados)
    # portao_acao_abandono = cancelar (ajuste do fluxo; antes vinha do preset "disparo")
    auto = _automacao(
        sessao, dados, ag, canal,
        configuracao={"ajustes": {"portao_acao_abandono": "cancelar"}},
    )
    execucao = _exec_pausada(sessao, auto, ag)

    aprovacao.vincular_pausa(sessao, execucao)

    aviso = next(t for t in enviados if "encerro esta conversa" in t)
    assert "cancelado" in aviso
    assert "continua disponível" not in aviso  # cancelar ≠ estacionar


def test_vincular_pausa_sem_encerrar_por_inatividade_nao_avisa(sessao, dados, monkeypatch):
    enviados = []
    monkeypatch.setattr(telegram, "enviar", lambda t, c, x: enviados.append(x) or {"ok": True})
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = _agente(sessao, dados)
    auto = _automacao(
        sessao, dados, ag, canal,
        configuracao={"ajustes": {"encerrar_por_inatividade": False}},
    )
    execucao = _exec_pausada(sessao, auto, ag)

    aprovacao.vincular_pausa(sessao, execucao)
    assert not any("batuta.team" in t for t in enviados)  # sem timeout → nada a avisar


def test_vincular_pausa_avisar_e_a_prova_de_falha(sessao, dados, monkeypatch):
    """O envio do aviso roda no `try` de disparo/retoma — uma falha de rede NÃO pode
    propagar (senão marcaria a execução como falhou)."""
    def boom(*a, **k):
        raise RuntimeError("telegram fora do ar")
    monkeypatch.setattr(telegram, "enviar", boom)
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag)

    aprovacao.vincular_pausa(sessao, execucao)  # NÃO deve levantar

    conv = _conv(sessao, execucao.id)
    assert conv is not None  # a pausa foi vinculada apesar da falha de envio
    # o aviso fica registrado como não-entregue
    msgs = sessao.scalars(
        select(MensagemConversa).where(MensagemConversa.conversa_id == conv.id)
    ).all()
    aviso = next(m for m in msgs if (m.midia or {}).get("tipo") == "aviso_portao")
    assert aviso.entregue is False
