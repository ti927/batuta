"""Fatia 2 — a MEDIÇÃO da conversa vem da timeline-sombra (fonte única).

`servico.medir_conversa` lê os passos da execução-sombra e devolve (turnos, custo).
Estes testes provam a EQUIVALÊNCIA com o contador de hoje (`conversa.turnos`/
`custo_acumulado_usd`), que passa a ser só cache: o MESMO número — inclusive quando o
turno tem custo ALÉM do agente (transcrição/visão/instrumento pago), que antes NÃO
entrava no passo (o passo guardava só o uso do agente). Também protegem as regras que
o contador já seguia: turno sem produto e turno de erro rodam o agente mas NÃO contam;
o portão fica de fora (pertence ao rastro do fluxo, entra na timeline só na Fatia 4).

`executar_agente` e `telegram.enviar` são mockados — sem LLM, sem rede.
"""

from sqlalchemy import select

import segredos_instrumento as si
from mensageria import servico, telegram
from modelos import Agente, AgenteInstrumento, Execucao, Instrumento, PassoExecucao


class _SessaoFake:
    """Reusa a sessão do teste (transação revertida) ignorando close(), p/ o
    processar_turno e o rastro-sombra (que abrem a própria sessão) verem os mesmos
    dados."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


def _setup(sessao, dados, monkeypatch, enviados):
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico.telegram, "enviar",
        lambda token, chat, texto: enviados.append(texto) or {"ok": True},
    )
    canal = Instrumento(
        time_id=dados["timeA"].id, nome="Bot", tipo="enviar_telegram",
        configuracao={"destinatario_padrao": "555", "saudacao_abertura": ""},
    )
    sessao.add(canal)
    sessao.flush()
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    ag = Agente(time_id=dados["timeA"].id, nome="Atendente", papel="agente")
    sessao.add(ag)
    sessao.flush()
    sessao.add(AgenteInstrumento(agente_id=ag.id, instrumento_id=canal.id))
    sessao.flush()
    return canal, ag


def _mock_agente(monkeypatch, *, saida="Olá!", uso=None, ramo=None):
    def fake(agente, cinto, entrada, **k):
        return {
            "saida": saida, "instrumentos_acionados": [], "uso": uso or [],
            "mensagens_enviadas": {}, "ramo_escolhido": ramo,
        }
    monkeypatch.setattr(servico, "executar_agente", fake)


def _responder(sessao, canal, texto):
    conv, deve = servico.registrar_entrada(
        sessao, canal,
        telegram.MensagemEntrante(
            contato_chave="555", contato_nome="Cliente", texto=texto, midia=None
        ),
    )
    assert deve
    servico.processar_turno(conv.id)
    return conv


def _passos_sombra(sessao, conversa_id):
    sombra = sessao.scalars(
        select(Execucao).where(
            Execucao.conversa_id == conversa_id, Execucao.modo == "conversa"
        )
    ).first()
    if sombra is None:
        return None, []
    passos = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == sombra.id)
        .order_by(PassoExecucao.ordem)
    ).all()
    return sombra, passos


def test_medir_bate_com_o_contador_em_chat_puro(sessao, dados, monkeypatch):
    enviados = []
    canal, _ = _setup(sessao, dados, monkeypatch, enviados)
    _mock_agente(monkeypatch, saida="oi", uso=[{"custo_usd": 0.10}])
    conv = _responder(sessao, canal, "bom dia")
    _mock_agente(monkeypatch, saida="tudo bem?", uso=[{"custo_usd": 0.05}])
    _responder(sessao, canal, "e aí")
    sessao.refresh(conv)

    turnos, custo = servico.medir_conversa(sessao, conv)
    # A timeline devolve exatamente o que o contador acumulou (que virou só cache).
    assert turnos == conv.turnos == 2
    assert round(custo, 6) == round(float(conv.custo_acumulado_usd), 6) == 0.15


def test_medir_inclui_custo_alem_do_agente(sessao, dados, monkeypatch):
    """A correção da Fatia 2: o passo passa a guardar o uso CHEIO do turno (agente +
    transcrição + visão + instrumento pago). Antes guardava só o do agente, e a medição
    pela timeline ficaria MENOR que o contador — afrouxando o teto. Prova que batem."""
    enviados = []
    canal, _ = _setup(sessao, dados, monkeypatch, enviados)
    _mock_agente(monkeypatch, saida="pronto", uso=[{"custo_usd": 0.10}])
    # Custo que NÃO vem do agente (transcrição/visão/instrumento pago).
    monkeypatch.setattr(
        servico, "_transcrever_pendentes",
        lambda *a, **k: [{"custo_usd": 0.02, "categoria": "transcricao"}],
    )
    monkeypatch.setattr(
        servico, "_descrever_imagens_pendentes",
        lambda *a, **k: ([{"custo_usd": 0.03, "categoria": "visao"}], []),
    )
    monkeypatch.setattr(
        servico.medicao_instrumentos, "uso_de_instrumentos_pagos",
        lambda *a, **k: [{"custo_usd": 0.05, "categoria": "instrumento"}],
    )

    conv = _responder(sessao, canal, "olha essa foto")
    sessao.refresh(conv)

    _, passos = _passos_sombra(sessao, conv.id)
    assert len(passos) == 1
    assert len(passos[0].saida["uso"]) == 4  # agente + transcrição + visão + instrumento

    turnos, custo = servico.medir_conversa(sessao, conv)
    assert turnos == conv.turnos == 1
    # 0.10 + 0.02 + 0.03 + 0.05 — a timeline e o contador chegam ao mesmo custo.
    assert round(custo, 6) == round(float(conv.custo_acumulado_usd), 6) == 0.20


def test_turno_sem_produto_nao_conta(sessao, dados, monkeypatch):
    """Turno em que o agente não fala nem decide: roda (gasta), mas o contador não
    conta — e a timeline tem que espelhar isso (passo existe, mas não é produtivo)."""
    enviados = []
    canal, _ = _setup(sessao, dados, monkeypatch, enviados)
    _mock_agente(monkeypatch, saida="", ramo=None, uso=[{"custo_usd": 0.09}])
    conv = _responder(sessao, canal, "oi")
    sessao.refresh(conv)

    _, passos = _passos_sombra(sessao, conv.id)
    assert len(passos) == 1  # o passo é gravado (rastro), mas não é produtivo
    turnos, custo = servico.medir_conversa(sessao, conv)
    assert turnos == conv.turnos == 0
    assert custo == float(conv.custo_acumulado_usd) == 0.0


def test_turno_de_erro_nao_conta(sessao, dados, monkeypatch):
    """Falha dura (LLM caiu): vira passo de ERRO, mas não conta turno nem custo —
    igual ao contador (que nem chega a incrementar)."""
    enviados = []
    canal, _ = _setup(sessao, dados, monkeypatch, enviados)

    def boom(*a, **k):
        raise RuntimeError("LLM caiu")
    monkeypatch.setattr(servico, "executar_agente", boom)

    conv = _responder(sessao, canal, "oi")
    sessao.refresh(conv)

    _, passos = _passos_sombra(sessao, conv.id)
    assert len(passos) == 1 and passos[0].estado == "erro"
    turnos, custo = servico.medir_conversa(sessao, conv)
    assert turnos == conv.turnos == 0
    assert custo == 0.0


def test_sem_sombra_ainda_e_zero(sessao, dados, monkeypatch):
    """No 1º turno (antes de qualquer passo), a conversa ainda não tem sombra —
    a medição é (0, 0.0), como o contador zerado."""
    enviados = []
    canal, _ = _setup(sessao, dados, monkeypatch, enviados)
    conv, _ = servico.registrar_entrada(
        sessao, canal,
        telegram.MensagemEntrante(
            contato_chave="555", contato_nome="Cliente", texto="oi", midia=None
        ),
    )
    assert servico.medir_conversa(sessao, conv) == (0, 0.0)
