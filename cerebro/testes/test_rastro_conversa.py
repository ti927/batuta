"""Rastro-sombra da conversa (Frente A, Fatia 1a).

O motor de conversa passa a deixar rastro nos MESMOS trilhos da orquestração: cada
turno conversacional vira um `PassoExecucao` de uma `Execucao` modo='conversa' (a
"sombra"), com entrada, saída, instrumentos acionados, ERROS de instrumento e uso —
o que faltava para inspecionar o agente conversacional (ex.: o time do Bubble) passo
a passo.

Invariantes protegidas aqui:
- a sombra vive no estado próprio 'conversa' → fora do alcance da fila ('aguardando')
  e dos recuperadores de órfãs/presas ('em_andamento'); nenhum reinício a marca falha;
- o turno de PORTÃO (gate) NÃO cria sombra — ele pertence ao rastro do FLUXO;
- gravar o rastro é à prova de falha: nunca quebra o atendimento.

`executar_agente` e `telegram.enviar` são mockados — sem LLM, sem rede.
"""

from sqlalchemy import select

import segredos_instrumento as si
from mensageria import servico, telegram
from mensageria.config import resolver_config
from modelos import (
    Agente,
    AgenteInstrumento,
    Execucao,
    Instrumento,
    PassoExecucao,
)


class _SessaoFake:
    """Reusa a sessão do teste (transação revertida) ignorando close(), p/ o
    processar_turno e o rastro-sombra (que abrem a própria sessão) verem os
    mesmos dados."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


def _setup_conversa(sessao, dados, monkeypatch, enviados):
    """Um canal Telegram + um agente atendente (com o canal no cinto). Assim
    `registrar_entrada` abre uma conversa modo conversacional e `processar_turno`
    roda `_rodar_turno(gate=False)`."""
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


def _mock_agente(monkeypatch, *, saida="Olá!", instrumentos=None, erros=None, ramo=None):
    def fake(agente, cinto, entrada, **k):
        r = {
            "saida": saida,
            "instrumentos_acionados": instrumentos or [],
            "uso": [],
            "mensagens_enviadas": {},
            "ramo_escolhido": ramo,
        }
        if erros is not None:
            r["erros_instrumentos"] = erros
        return r
    monkeypatch.setattr(servico, "executar_agente", fake)


def _responder(sessao, canal, texto, nome="Cliente"):
    conv, deve = servico.registrar_entrada(
        sessao, canal,
        telegram.MensagemEntrante(
            contato_chave="555", contato_nome=nome, texto=texto, midia=None
        ),
    )
    assert deve
    servico.processar_turno(conv.id)
    return conv


def _sombra(sessao, conversa_id):
    return sessao.scalars(
        select(Execucao).where(
            Execucao.conversa_id == conversa_id, Execucao.modo == "conversa"
        )
    ).first()


def _passos(sessao, execucao_id):
    return sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao_id)
        .order_by(PassoExecucao.ordem)
    ).all()


def test_conversa_cria_sombra_com_passo(sessao, dados, monkeypatch):
    enviados = []
    canal, ag = _setup_conversa(sessao, dados, monkeypatch, enviados)
    _mock_agente(monkeypatch, saida="Oi, como posso ajudar?")

    conv = _responder(sessao, canal, "bom dia")

    sombra = _sombra(sessao, conv.id)
    assert sombra is not None
    assert sombra.automacao_id is None      # nasce do agente, não de automação
    assert sombra.modo == "conversa"
    assert sombra.estado == "conversa"       # estado próprio (fora da fila/recuperadores)
    passos = _passos(sessao, sombra.id)
    assert len(passos) == 1
    assert passos[0].ordem == 1
    assert passos[0].agente_id == ag.id
    assert passos[0].saida["texto"] == "Oi, como posso ajudar?"
    assert passos[0].estado == "concluido"


def test_segundo_turno_anexa_passo_na_mesma_sombra(sessao, dados, monkeypatch):
    enviados = []
    canal, ag = _setup_conversa(sessao, dados, monkeypatch, enviados)

    _mock_agente(monkeypatch, saida="primeira resposta")
    conv = _responder(sessao, canal, "oi")
    _mock_agente(monkeypatch, saida="segunda resposta")
    _responder(sessao, canal, "e agora?")

    sombra = _sombra(sessao, conv.id)
    passos = _passos(sessao, sombra.id)
    assert len(passos) == 2                 # MESMA sombra, dois passos
    assert [p.ordem for p in passos] == [1, 2]
    assert passos[0].saida["texto"] == "primeira resposta"
    assert passos[1].saida["texto"] == "segunda resposta"


def test_rastro_captura_erros_de_instrumento(sessao, dados, monkeypatch):
    """O ouro para depurar: os erros CRUS dos instrumentos do turno chegam ao passo
    (é o que estava invisível no motor de conversa — ex.: a chamada REST do Bubble)."""
    enviados = []
    canal, ag = _setup_conversa(sessao, dados, monkeypatch, enviados)
    erros = [{"instrumento": "rest", "erro": "422 constraint inválida"}]
    _mock_agente(
        monkeypatch, saida="Deu um problema ao consultar.",
        instrumentos=["rest"], erros=erros,
    )

    conv = _responder(sessao, canal, "busca meu reembolso")

    passos = _passos(sessao, _sombra(sessao, conv.id).id)
    assert passos[0].saida["instrumentos_acionados"] == ["rest"]
    assert passos[0].saida["erros_instrumentos"] == erros


def test_falha_dura_vira_passo_de_erro(sessao, dados, monkeypatch):
    """Se o agente estoura (LLM/instrumento cai), o rastro registra um passo de ERRO —
    o atendimento falha com graça (não quebra) e a falha não fica em silêncio."""
    enviados = []
    canal, ag = _setup_conversa(sessao, dados, monkeypatch, enviados)

    def boom(*a, **k):
        raise RuntimeError("LLM caiu")
    monkeypatch.setattr(servico, "executar_agente", boom)

    conv = _responder(sessao, canal, "oi")   # não deve levantar

    sombra = _sombra(sessao, conv.id)
    assert sombra is not None
    passos = _passos(sessao, sombra.id)
    assert len(passos) == 1
    assert passos[0].estado == "erro"
    assert "LLM caiu" in passos[0].saida.get("erro", "")


def test_sombra_fica_fora_do_alcance_dos_recuperadores(sessao, dados, monkeypatch):
    """A sombra vive em 'conversa'. A fila casa 'aguardando' e os recuperadores de
    órfãs/presas casam 'em_andamento' — logo a sombra nunca entra nesses conjuntos e
    NÃO vira 'falhou' a cada reinício do servidor."""
    enviados = []
    canal, ag = _setup_conversa(sessao, dados, monkeypatch, enviados)
    _mock_agente(monkeypatch, saida="oi")
    conv = _responder(sessao, canal, "oi")
    sombra = _sombra(sessao, conv.id)

    em_andamento = sessao.scalars(
        select(Execucao.id).where(Execucao.estado == "em_andamento")
    ).all()
    aguardando = sessao.scalars(
        select(Execucao.id).where(Execucao.estado == "aguardando")
    ).all()
    assert sombra.id not in em_andamento
    assert sombra.id not in aguardando
    assert sombra.estado == "conversa"


def test_portao_gate_nao_cria_sombra(sessao, dados, monkeypatch):
    """O turno de PORTÃO (gate=True) pertence ao rastro do FLUXO — não gera uma
    execução-sombra de conversa."""
    enviados = []
    canal, ag = _setup_conversa(sessao, dados, monkeypatch, enviados)
    _mock_agente(monkeypatch, saida="pergunta do portão?", ramo=None)

    conv, _ = servico.registrar_entrada(
        sessao, canal,
        telegram.MensagemEntrante(
            contato_chave="555", contato_nome="Chefe", texto="oi", midia=None
        ),
    )
    conf = resolver_config(sessao, conv)
    servico._rodar_turno(
        sessao, conv, "tok", ag, conf,
        saidas=[
            {"rotulo": "aprovado", "destino": "fim"},
            {"rotulo": "reprovado", "destino": "fim"},
        ],
        gate=True, chaves={}, origens={},
    )

    assert _sombra(sessao, conv.id) is None
