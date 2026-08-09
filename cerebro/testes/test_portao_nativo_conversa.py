"""Portão NATIVO no modo CONVERSA (Fatia 4.3 / P3b).

Integração de verdade: `_rodar_turno` REAL + `HumanInTheLoopMiddleware` REAL + checkpointer
(MemorySaver) + modelo FALSO roteirizado. Prova o comportamento da TRAVA na conversa:
- ação irreversível PAUSA e apresenta ao contato (não executa);
- contato responde "sim" → executa EXATAMENTE 1×; "não" → 0×; ambíguo → re-pergunta;
- interruptor do time DESLIGADO → comportamento de hoje (roda direto, sem pausa).

O interruptor é por time (env `PORTAO_NATIVO_CONVERSA_TIMES`); aqui ligamos por monkeypatch.
"""

import uuid
from datetime import datetime, timedelta, timezone

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

import orquestracao.agente as agente_mod
from instrumentos.base import TipoInstrumento, registrar
from mensageria import servico
from modelos import (
    Agente,
    AgenteInstrumento,
    Conversa,
    Instrumento,
    MensagemConversa,
    Organizacao,
)
from orquestracao import memoria_conversa

cont = {"pub": 0}
_NOME_PUB = {"v": ""}


class _ConfVazia(BaseModel):
    pass


class _TipoPubC(TipoInstrumento):
    tipo = "p3c_pub"
    nome_exibicao = "Criar Reembolso"
    descricao = "lança um reembolso (irreversível)"
    Config = _ConfVazia
    Args = _ConfVazia
    acao_irreversivel = True

    def executar(self, config, args):
        cont["pub"] += 1
        return {"ok": True}


registrar(_TipoPubC())


# Texto que o agente escreve NO passo em que decide agir (vazio = fake "mudo").
_TEXTO_ACAO = {"v": ""}


class _FakeModelo(BaseChatModel):
    """Chama a ação irreversível (com ou sem texto); depois de tê-la (ToolMessage), conclui."""

    @property
    def _llm_type(self) -> str:
        return "fake-p3c"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        feitas = {m.name for m in messages if isinstance(m, ToolMessage)}
        if _NOME_PUB["v"] not in feitas:
            ai = AIMessage(content=_TEXTO_ACAO["v"], tool_calls=[
                {"name": _NOME_PUB["v"], "args": {}, "id": "c1", "type": "tool_call"}])
        else:
            ai = AIMessage(content="Feito!")
        return ChatResult(generations=[ChatGeneration(message=ai)])


def _cenario(sessao, dados, monkeypatch, saver, *, ligado=True, texto_acao=""):
    cont["pub"] = 0
    time_id = dados["timeA"].id
    canal = Instrumento(time_id=time_id, nome="Bot", tipo="enviar_telegram",
                        configuracao={"destinatario_padrao": "555"})
    ag = Agente(time_id=time_id, nome="Atendente", papel="agente",
                modelo_ia="claude-sonnet-5")
    sessao.add_all([canal, ag])
    sessao.flush()
    pub = Instrumento(time_id=time_id, nome="Criar Reembolso", tipo="p3c_pub",
                      configuracao={})
    sessao.add(pub)
    sessao.flush()
    sessao.add(AgenteInstrumento(agente_id=ag.id, instrumento_id=pub.id))
    conversa = Conversa(
        instrumento_id=canal.id, canal="telegram", contato_chave="555",
        contato_nome="Cliente", estado="aberta",
        destino_tipo="agente", destino_id=ag.id,
    )
    sessao.add(conversa)
    sessao.flush()
    _NOME_PUB["v"] = agente_mod._nome_de_ferramenta(pub, "p3c_pub")
    _TEXTO_ACAO["v"] = texto_acao

    # Governança DEFINITIVA: a trava respeita a PAREDE DE APROVAÇÃO da org (não env/Railway).
    org = sessao.get(Organizacao, dados["timeA"].organizacao_id)
    org.parede_ativacao = ligado
    sessao.flush()

    enviados: list[str] = []
    monkeypatch.setattr(agente_mod, "construir_modelo", lambda m: _FakeModelo())
    monkeypatch.setattr(memoria_conversa, "obter", lambda: saver)
    monkeypatch.setattr(
        servico.telegram, "enviar",
        lambda token, chat, texto: enviados.append(texto) or {"ok": True},
    )
    return ag, conversa, enviados


_n = {"i": 0}


def _contato(sessao, conversa, texto):
    """Registra uma mensagem do contato com criado_em crescente (p/ 'última' ser estável)."""
    _n["i"] += 1
    sessao.add(MensagemConversa(
        conversa_id=conversa.id, papel="contato", conteudo=texto, entregue=True,
        criado_em=datetime.now(timezone.utc) + timedelta(seconds=_n["i"]),
    ))
    sessao.flush()
    conversa.ultima_entrada_em = datetime.now(timezone.utc) + timedelta(seconds=_n["i"])


def _turno(sessao, conversa, ag):
    return servico._rodar_turno(
        sessao, conversa, "tok", ag, {"timeout_min": 60},
        saidas=[], gate=False, chaves={}, origens={},
    )


def test_acao_irreversivel_pausa_e_apresenta(sessao, dados, monkeypatch):
    ag, conversa, enviados = _cenario(sessao, dados, monkeypatch, MemorySaver())
    _contato(sessao, conversa, "quero lançar meu reembolso")
    _turno(sessao, conversa, ag)
    assert cont["pub"] == 0                                   # NÃO executou
    assert any("confirmar" in m.lower() for m in enviados)    # apresentou o pedido
    assert any("Criar Reembolso" in m for m in enviados)      # com o nome da ação
    assert conversa.estado == "aguardando_resposta"           # estacionou (sweeper governa)


def test_aprovar_executa_uma_vez(sessao, dados, monkeypatch):
    saver = MemorySaver()
    ag, conversa, enviados = _cenario(sessao, dados, monkeypatch, saver)
    _contato(sessao, conversa, "quero lançar")
    _turno(sessao, conversa, ag)          # pausa
    assert cont["pub"] == 0
    _contato(sessao, conversa, "sim")
    _turno(sessao, conversa, ag)          # retoma aprovando
    assert cont["pub"] == 1                                   # executou 1×
    assert any("Feito" in m for m in enviados)


def test_recusar_nao_executa(sessao, dados, monkeypatch):
    saver = MemorySaver()
    ag, conversa, enviados = _cenario(sessao, dados, monkeypatch, saver)
    _contato(sessao, conversa, "quero lançar")
    _turno(sessao, conversa, ag)          # pausa
    _contato(sessao, conversa, "não")
    _turno(sessao, conversa, ag)          # retoma recusando
    assert cont["pub"] == 0                                   # NÃO executou


def test_ambiguo_repergunta_e_nao_executa(sessao, dados, monkeypatch):
    saver = MemorySaver()
    ag, conversa, enviados = _cenario(sessao, dados, monkeypatch, saver)
    _contato(sessao, conversa, "quero lançar")
    _turno(sessao, conversa, ag)          # pausa
    enviados.clear()
    _contato(sessao, conversa, "talvez mais tarde")
    _turno(sessao, conversa, ag)          # ambíguo → re-pergunta
    assert cont["pub"] == 0
    assert any("não entendi" in m.lower() for m in enviados)
    assert conversa.estado == "aguardando_resposta"           # segue aguardando


def test_parede_desligada_nao_pausa(sessao, dados, monkeypatch):
    """Parede de aprovação da org DESLIGADA = sem trava: a ação roda direto (escolha da org)."""
    ag, conversa, enviados = _cenario(
        sessao, dados, monkeypatch, MemorySaver(), ligado=False
    )
    _contato(sessao, conversa, "quero lançar")
    _turno(sessao, conversa, ag)
    assert cont["pub"] == 1                                   # rodou direto (sem pausa)


def test_apresenta_na_voz_do_agente(sessao, dados, monkeypatch):
    """P3d: quando o agente já escreve a frase da ação no passo em que decide agir, o
    sistema apresenta ESSA frase (não uma genérica) — evita confirmação em dobro."""
    ag, conversa, enviados = _cenario(
        sessao, dados, monkeypatch, MemorySaver(),
        texto_acao="Vou lançar o reembolso de R$320 no projeto Alfa.",
    )
    _contato(sessao, conversa, "manda ver")
    _turno(sessao, conversa, ag)
    assert cont["pub"] == 0
    # a mensagem sai NA VOZ do agente + o pedido de sim/não
    assert any("Vou lançar o reembolso de R$320" in m for m in enviados)
    assert any("sim" in m.lower() and "não" in m.lower() for m in enviados)


class _SessaoFake:
    """Reusa a sessão do teste ignorando close() (processar_turno abre a própria)."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


def test_ponta_a_ponta_pausa_e_retoma_via_processar_turno(sessao, dados, monkeypatch):
    """Fluxo REAL pela borda (processar_turno): pausa → apresenta → 'sim' → executa 1×.
    Cobre o estado da conversa (aguardando_resposta na pausa, NÃO 'aberta')."""
    import segredos_instrumento as si

    saver = MemorySaver()
    ag, conversa, enviados = _cenario(sessao, dados, monkeypatch, saver)
    canal = sessao.get(Instrumento, conversa.instrumento_id)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))

    def _entrar(texto):
        conv, deve = servico.registrar_entrada(
            sessao, canal,
            servico.telegram.MensagemEntrante(
                contato_chave="555", contato_nome="Cliente", texto=texto, midia=None),
        )
        assert deve
        servico.processar_turno(conv.id)
        return conv

    conv = _entrar("quero lançar meu reembolso")     # pausa
    sessao.refresh(conv)
    assert cont["pub"] == 0
    assert conv.estado == "aguardando_resposta"        # NÃO 'aberta' (a bola é do contato)
    assert conv.aguardando_ate is not None             # entra no sweeper
    assert any("confirmar" in m.lower() for m in enviados)

    _entrar("sim")                                      # retoma aprovando
    sessao.refresh(conv)
    assert cont["pub"] == 1                             # executou 1×
    assert any("Feito" in m for m in enviados)


def test_classificar_aprovacao():
    assert servico._classificar_aprovacao("sim") == "approve"
    assert servico._classificar_aprovacao("Pode confirmar!") == "approve"
    assert servico._classificar_aprovacao("não") == "reject"
    assert servico._classificar_aprovacao("nao pode") == "reject"
    assert servico._classificar_aprovacao("cancelar") == "reject"
    assert servico._classificar_aprovacao("talvez") is None    # ambíguo → não aprova
    assert servico._classificar_aprovacao("") is None
    assert servico._classificar_aprovacao("sim, mas não agora") is None  # dúvida → seguro
