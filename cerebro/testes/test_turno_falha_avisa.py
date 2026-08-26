"""Turno de atendimento que falha: o contato é avisado, e a espera é curta.

Origem (2026-08-26, ao vivo): o time de Reembolsos ficou preso em "bot respondendo".
O agente estava num modelo lento e a chamada de IA usava os limites das automações de
fundo — 300 s × 6 retentativas, quase meia hora antes de desistir. Pior: quando o turno
falhava, a mensagem de erro era gravada como nota INTERNA (`entregue=False`) e o contato
não recebia nada. Duas correções, provadas aqui.
"""

import uuid

import pytest
import segredos_instrumento as si
from sqlalchemy import select

import orquestracao.llm as llm
from mensageria import servico, telegram
from modelos import Agente, AgenteInstrumento, Instrumento, MensagemConversa


def _bot(sessao, dados):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="Bot", tipo="enviar_telegram",
        configuracao={"destinatario_padrao": "555", "saudacao_abertura": ""},
    )
    sessao.add(inst)
    sessao.flush()
    si.salvar_segredos(sessao, inst.id, {"token_bot": "tok"})
    return inst


def _agente_com(sessao, dados, inst):
    ag = Agente(time_id=dados["timeA"].id, nome="Atendente", papel="agente")
    sessao.add(ag)
    sessao.flush()
    sessao.add(AgenteInstrumento(agente_id=ag.id, instrumento_id=inst.id))
    sessao.flush()
    return ag


class _SessaoFake:
    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


def test_falha_no_turno_avisa_o_contato(sessao, dados, monkeypatch):
    """A pessoa mandou mensagem e a IA estourou: ela precisa SABER, na hora."""
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    enviados: list[str] = []
    monkeypatch.setattr(
        servico.telegram, "enviar",
        lambda token, chat, texto: enviados.append(texto) or {"ok": True},
    )
    monkeypatch.setattr(
        servico, "resolver_chaves_por_time", lambda s, t: ({"anthropic": "K"}, {})
    )

    def morre(*a, **k):
        raise TimeoutError("a IA não respondeu a tempo")

    monkeypatch.setattr(servico, "executar_agente", morre)

    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(
        sessao, inst,
        telegram.MensagemEntrante(
            contato_chave="555", contato_nome="Julio", texto="lança meu reembolso", midia=None
        ),
    )
    servico.processar_turno(conversa.id)

    assert enviados, "o contato tem de receber um aviso quando o turno falha"
    assert "Não consegui responder agora" in enviados[-1]
    # o aviso fica na thread como mensagem ENTREGUE (não uma nota interna invisível)
    msgs = sessao.scalars(
        select(MensagemConversa)
        .where(MensagemConversa.conversa_id == conversa.id)
        .order_by(MensagemConversa.criado_em)
    ).all()
    assert any(m.entregue and "Não consegui responder" in (m.conteudo or "") for m in msgs)
    sessao.refresh(conversa)
    assert conversa.estado == "aberta"  # a bola volta a ser nossa; não fica presa


# ── Os limites de espera: fundo × atendimento ──


class _Capturado:
    def __init__(self, **k):
        self.k = k


@pytest.fixture
def capturar_openai(monkeypatch):
    capturas: list[dict] = []
    import langchain_openai

    monkeypatch.setattr(
        langchain_openai, "ChatOpenAI", lambda **k: capturas.append(k) or _Capturado(**k)
    )
    monkeypatch.setattr(llm, "_chaves_ia", llm._chaves_ia)
    return capturas


def test_chat_espera_pouco_e_fundo_espera_muito(capturar_openai):
    """Mesmo modelo, dois contextos: no atendimento a falha chega em ~1 min; numa
    automação de fundo continua valendo a paciência longa (ninguém está olhando)."""
    with llm.usar_chaves({"openai": "sk-teste"}):
        llm.construir_modelo("gpt-5.6-luna", interativo=True)
        llm.construir_modelo("gpt-5.6-luna")

    chat, fundo = capturar_openai
    assert chat["timeout"] == llm.TIMEOUT_IA_CHAT_S
    assert chat["max_retries"] == llm.MAX_RETENTATIVAS_IA_CHAT
    assert fundo["timeout"] == llm.TIMEOUT_IA_S
    assert fundo["max_retries"] == llm.MAX_RETENTATIVAS_IA
    # a espera do chat tem de ser MUITO menor no pior caso (timeout × tentativas)
    pior_chat = llm.TIMEOUT_IA_CHAT_S * (llm.MAX_RETENTATIVAS_IA_CHAT + 1)
    pior_fundo = llm.TIMEOUT_IA_S * (llm.MAX_RETENTATIVAS_IA + 1)
    assert pior_chat < 180 and pior_fundo > pior_chat * 5


def test_agente_interativo_repassa_o_limite(monkeypatch):
    """O `executar_agente` do atendimento pede o modelo em modo interativo."""
    visto: dict = {}

    def fake_construir(modelo_ia=None, temperatura=0.0, *, interativo=False):
        visto["interativo"] = interativo
        return object()

    monkeypatch.setattr("orquestracao.agente.construir_modelo", fake_construir)
    monkeypatch.setattr(
        "orquestracao.agente.create_agent",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("parou aqui de propósito")),
    )
    ag = Agente(time_id=uuid.uuid4(), nome="A", papel="agente")
    ag.id = uuid.uuid4()
    with pytest.raises(RuntimeError):
        from orquestracao.agente import executar_agente

        executar_agente(ag, [], "oi", interativo=True)
    assert visto["interativo"] is True
