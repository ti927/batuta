"""Portão CONVERSACIONAL: o agente conversa e decide (não um roteador de palavra).

Quando uma execução pausa num portão de nó-agente com 2+ saídas e a pessoa
responde, o motor RE-RODA o agente (não casa a palavra num roteador). O agente
então: pergunta de volta (sem declarar saída) → segue aguardando; ou declara a
saída via `seguir_para` → o fluxo anda. Trilho anti-loop: após o teto de rodadas,
cai no roteamento mecânico. `executar_agente` é mockado — sem LLM.
"""

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


def _automacao(sessao, dados, agente, canal):
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
        configuracao_gatilho={}, cadeia={"inicial": NO_GATE, "nos": [no, {"id": "fim", "tipo": "fim", "saidas": []}]},
        ativa=False,
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


def _mock_rerun(monkeypatch, *, ramo=None, mensagens=None):
    """Mocka `executar_agente` (visto pela retoma): declara um ramo ou não, e pode
    devolver o que 'enviou' por canal (mensagens_enviadas)."""
    def fake(agente, cinto, entrada, **kwargs):
        return {
            "saida": "(narração do agente)",
            "instrumentos_acionados": [],
            "uso": [],
            "mensagens_enviadas": mensagens or {},
            "ramo_escolhido": ramo,
        }
    monkeypatch.setattr(retoma, "executar_agente", fake)


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


def test_agente_pergunta_de_volta_e_segue_aguardando(sessao, dados, monkeypatch):
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)  # registra o apresentado inicial

    # o agente, ao ser reprovado, PERGUNTA o porquê (não declara saída)
    _mock_rerun(monkeypatch, ramo=None, mensagens={str(canal.id): ["Por que você reprovou?"]})
    retoma.retomar_execucao(sessao, execucao, "reprovado", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"  # continua aguardando a pessoa
    passos = _passos(sessao, execucao.id)
    assert len(passos) == 2  # rodada de pergunta virou novo passo
    assert passos[-1].saida["texto"] == "Por que você reprovou?"
    # a pergunta foi para a thread de Conversas (não só pro Telegram)
    conv = _conv(sessao, execucao.id)
    msgs = [
        m.conteudo for m in sessao.scalars(
            select(MensagemConversa)
            .where(MensagemConversa.conversa_id == conv.id)
            .where(MensagemConversa.papel == "agente")
        )
    ]
    assert "Por que você reprovou?" in msgs


def test_agente_decide_e_o_fluxo_anda(sessao, dados, monkeypatch):
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)

    # o agente DECIDE aprovar (declara o ramo) → "aprovado" → fim → conclui
    _mock_rerun(monkeypatch, ramo="aprovado", mensagens={})
    retoma.retomar_execucao(sessao, execucao, "ok, aprovo", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"
    assert _passos(sessao, execucao.id)[-1].saida["saida_escolhida"] == "aprovado"


def test_teto_de_rodadas_cai_no_roteador_mecanico(sessao, dados, monkeypatch):
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag)  # já há 1 passo no nó

    monkeypatch.setattr(retoma, "MAX_RODADAS_GATE", 1)  # teto baixo: 1 já estoura

    def explode(*a, **k):
        raise AssertionError("não devia re-rodar o agente após o teto")
    monkeypatch.setattr(retoma, "executar_agente", explode)
    monkeypatch.setattr(
        retoma, "_escolher_saida",
        lambda resp, saidas: ({"rotulo": "aprovado", "destino": "fim"}, {}),
    )
    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"  # roteador mecânico resolveu


def test_processar_turno_nao_duplica_ack_quando_agente_pergunta(sessao, dados, monkeypatch):
    enviados = []
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico.telegram, "enviar",
        lambda token, chat, texto: enviados.append(texto) or {"ok": True},
    )
    canal = _canal(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok-x"})
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal)
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)

    _mock_rerun(monkeypatch, ramo=None, mensagens={str(canal.id): ["Por que você reprovou?"]})
    msg = telegram.MensagemEntrante(
        contato_chave="555", contato_nome="Chefe", texto="reprovado", midia=None
    )
    conv, deve = servico.registrar_entrada(sessao, canal, msg)
    assert deve
    servico.processar_turno(conv.id)

    # o agente já perguntou pelo canal → NÃO sai o ack genérico "Recebido, ainda..."
    assert not any("Ainda há uma etapa" in t for t in enviados)
