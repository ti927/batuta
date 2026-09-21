"""As correções do estudo `docs/FALHAS-DO-MOTOR.md` (incidente de 2026-09-21).

Uma execução ficou 4 h esperando aprovação; a resposta veio pelo Telegram, o agente
regenerou o material sem nunca declarar o ramo, e um clique na TELA entrou na MESMA
execução enquanto o turno do canal ainda rodava. Os dois abriram o mesmo thread do
LangGraph, o checkpoint bifurcou, e a Anthropic recusou o histórico pela metade com um
400 — que matou uma execução que não tinha feito nada de errado.

Cobertos aqui:
- §4.3 o CANAL grava o que a TELA grava (o endereço da aprovação nova, `saida.aprovacao`)
- §4.4 turno de portão que não decide NEM pede aprovação vira alarme, não silêncio
- §4.5 400 de protocolo não mata a execução; falha de verdade desvincula a conversa

`executar_agente` é mockado — sem LLM.
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
    PassoExecucao,
)
from orquestracao import disparo, llm

NO_GATE = "rev"

# O 400 real que a Anthropic devolveu na execução e76224a6 (2026-09-21).
ERRO_400_REAL = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'messages.6: `tool_use` ids were found without `tool_result` blocks "
    "immediately after: toolu_017uzgLmnpWPv8YdZdXbUEYG, toolu_01FAaQjgX5CGydBkNEW5aUKx, "
    "toolu_01VsiQCBmi5EGLHnXZjxytcB. Each `tool_use` block must have a corresponding "
    "`tool_result` block in the next message.'}, 'request_id': 'req_011CfGoxSy1rpDJeYTV7dCQo'}"
)


class _SessaoFake:
    """Reusa a sessão do teste (transação revertida) ignorando close()."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


def _monta(sessao, dados, *, destinatario="555"):
    canal = Instrumento(
        time_id=dados["timeA"].id, nome="Bot", tipo="enviar_telegram",
        configuracao={"destinatario_padrao": destinatario, "saudacao_abertura": ""},
    )
    sessao.add(canal)
    sessao.flush()
    ag = Agente(time_id=dados["timeA"].id, nome="Gerador Carrossel", papel="agente")
    sessao.add(ag)
    sessao.flush()
    no = {
        "id": NO_GATE, "tipo": "agente", "ref": str(ag.id), "gate": True,
        "saidas": [
            {"rotulo": "aprovado", "quando": "ok", "destino": "fim"},
            {"rotulo": "reprovado", "quando": "ajustar", "destino": "fim"},
        ],
    }
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Gerar Posts", tipo_gatilho="manual",
        configuracao_gatilho={},
        cadeia={"inicial": NO_GATE, "nos": [no, {"id": "fim", "tipo": "fim", "saidas": []}]},
        ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    return canal, ag, auto


def _exec_pausada(sessao, auto, ag, canal=None):
    """Execução parada na apresentação do portão — o passo de pausa carrega o ENDEREÇO
    (`saida.aprovacao`), como `cadeia._montar_passo` grava em produção."""
    execucao = Execucao(
        automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"}
    )
    sessao.add(execucao)
    sessao.flush()
    sessao.add(
        PassoExecucao(
            execucao_id=execucao.id, ordem=1, agente_id=ag.id, no_id=NO_GATE,
            tipo="espera_humano",
            entrada={"texto": "rascunho"},
            saida={
                "texto": "3 slides para aprovação", "instrumentos_acionados": [],
                "saida_escolhida": None, "uso": [],
                **({"aprovacao": {"canal_instrumento_id": str(canal.id),
                                  "destinatario": "555"}} if canal else {}),
            },
            estado="concluido",
        )
    )
    sessao.flush()
    return execucao


def _passos(sessao, execucao_id):
    return sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao_id)
        .order_by(PassoExecucao.ordem)
    ).all()


def _setup_canal(sessao, dados, monkeypatch, enviados):
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico.telegram, "enviar",
        lambda token, chat, texto: enviados.append(texto) or {"ok": True},
    )
    canal, ag, auto = _monta(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    execucao = _exec_pausada(sessao, auto, ag, canal)
    aprovacao.vincular_pausa(sessao, execucao)
    return canal, ag, auto, execucao


def _responder_no_canal(sessao, canal, texto):
    conv, deve = servico.registrar_entrada(
        sessao, canal,
        telegram.MensagemEntrante(
            contato_chave="555", contato_nome="Julio", texto=texto, midia=None
        ),
    )
    assert deve
    servico.processar_turno(conv.id)
    return conv


# ───────── §4.3 — o CANAL grava o que a TELA grava ─────────

def test_canal_pedido_de_aprovacao_novo_guarda_o_endereco(sessao, dados, monkeypatch):
    """O agente reprovado regenera o material e chama `pedir_aprovacao` DENTRO do turno
    de portão. O `pausado` era engolido: o passo saía sem o bloco `aprovacao` e a
    execução ficava SEM ENDEREÇO — `config_aprovacao` não achava mais por onde a
    aprovação tinha sido pedida, e a conversa não podia ser re-amarrada."""
    enviados = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    endereco = {"canal_instrumento_id": str(canal.id), "destinatario": "555"}
    monkeypatch.setattr(
        servico, "executar_agente",
        lambda *a, **k: {
            "saida": "Slides refeitos, aprova?", "instrumentos_acionados": ["pedir_aprovacao"],
            "uso": [], "mensagens_enviadas": {}, "ramo_escolhido": None,
            "pausado": True, "aprovacao": endereco,
        },
    )

    _responder_no_canal(sessao, canal, "reprovado, tire a logo")

    ultimo = _passos(sessao, execucao.id)[-1]
    assert ultimo.saida.get("aprovacao") == endereco  # o endereço ficou no rastro
    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"
    # E o endereço é de fato legível por quem re-amarra a conversa:
    assert aprovacao.config_aprovacao(sessao, execucao)["instrumento_id"] == str(canal.id)


def test_canal_pedido_de_aprovacao_novo_nao_anda_o_fluxo(sessao, dados, monkeypatch):
    """Pediu aprovação = está esperando, não trabalhando. Mesmo que um ramo venha junto
    na resposta, nada anda nesta rodada — senão o fluxo passaria por cima de uma
    aprovação que a pessoa ainda nem viu."""
    enviados = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    monkeypatch.setattr(
        servico, "executar_agente",
        lambda *a, **k: {
            "saida": "Aprova?", "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {}, "ramo_escolhido": "aprovado",
            "pausado": True, "aprovacao": {"canal_instrumento_id": str(canal.id)},
        },
    )

    _responder_no_canal(sessao, canal, "reprovado")

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"  # NÃO concluiu pelo ramo "aprovado"
    assert _passos(sessao, execucao.id)[-1].saida["saida_escolhida"] is None


# ───────── §4.4 — silêncio do agente vira alarme ─────────

def test_uma_rodada_sem_decidir_nao_alarma(sessao, dados, monkeypatch):
    """Perguntar UMA vez é legítimo (pedir um esclarecimento). O alarme é para a
    repetição, não para a primeira pergunta."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    eventos = []
    monkeypatch.setattr(retoma, "registrar_evento", lambda **kw: eventos.append(kw))
    monkeypatch.setattr(
        retoma, "executar_agente",
        lambda *a, **k: {
            "saida": "Retirar ou reposicionar a logo?", "instrumentos_acionados": [],
            "uso": [], "mensagens_enviadas": {}, "ramo_escolhido": None,
        },
    )

    retoma.retomar_execucao(sessao, execucao, "reprovado", chaves={}, origens={})

    assert not [e for e in eventos if e.get("acao") == "portao.indeciso"]


def test_portao_indeciso_vira_alarme_na_segunda_rodada(sessao, dados, monkeypatch):
    """Duas rodadas seguidas conversando sem declarar caminho, num nó que TEM dois
    caminhos: é o retrato do markdown que não conhece os rótulos do nó. Antes isso era
    silêncio absoluto e a execução ficava parada para sempre."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    eventos = []
    monkeypatch.setattr(retoma, "registrar_evento", lambda **kw: eventos.append(kw))
    monkeypatch.setattr(
        retoma, "executar_agente",
        lambda *a, **k: {
            "saida": "(conversa)", "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {}, "ramo_escolhido": None,
        },
    )

    retoma.retomar_execucao(sessao, execucao, "reprovado", chaves={}, origens={})
    sessao.refresh(execucao)
    retoma.retomar_execucao(sessao, execucao, "retire", chaves={}, origens={})

    alarmes = [e for e in eventos if e.get("acao") == "portao.indeciso"]
    assert len(alarmes) == 1
    assert alarmes[0]["nivel"] == "error"
    assert alarmes[0]["detalhe"]["agente"] == "Gerador Carrossel"
    assert alarmes[0]["detalhe"]["rodadas_sem_decidir"] == 2
    assert alarmes[0]["detalhe"]["saidas"] == ["aprovado", "reprovado"]


def test_no_de_saida_unica_nunca_alarma(sessao, dados, monkeypatch):
    """Sem caminho a escolher não há indecisão possível — alarme aqui seria ruído, e
    alarme que dispara à toa é alarme que ninguém lê."""
    canal, ag, auto = _monta(sessao, dados)
    auto.cadeia["nos"][0]["saidas"] = [{"rotulo": "segue", "quando": "", "destino": "fim"}]
    execucao = _exec_pausada(sessao, auto, ag, canal)
    assert retoma.alertar_portao_indeciso(
        sessao, execucao, no_id=NO_GATE, agente_nome="X",
        saidas=[{"rotulo": "segue"}],
    ) == 0


def test_a_apresentacao_inicial_nao_conta_como_indecisao(sessao, dados):
    """A contagem para no passo que pediu a aprovação — ele decidiu algo (parar). Sem
    esse corte, toda pausa nasceria com uma rodada de indecisão no placar."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    assert retoma.rodadas_sem_decidir(sessao, execucao.id, NO_GATE) == 0


# ───────── §4.5 — falha não contamina ─────────

def test_reconhece_o_400_de_protocolo_da_anthropic():
    assert llm.historico_invalido(ERRO_400_REAL)
    assert llm.historico_invalido(RuntimeError(ERRO_400_REAL))


def test_nao_confunde_falha_de_trabalho_com_400_de_protocolo():
    """A distinção precisa ser estreita: tratar uma falha real como "entrada recusada"
    deixaria execuções quebradas eternamente em `aguardando_humano`."""
    assert not llm.historico_invalido("Error code: 400 - credit balance is too low")
    assert not llm.historico_invalido("O instrumento 'Publicar' falhou: timeout")
    assert not llm.historico_invalido("Error code: 429 - rate limit")
    assert not llm.historico_invalido(ValueError("tool_use sem tool_result"))  # sem o 400


def test_400_de_protocolo_devolve_a_execucao_a_espera(sessao, dados, monkeypatch):
    """O estrago de 2026-09-21: um 400 de protocolo matou uma execução de quase 4 horas.
    O fluxo não errou nada — quem chegou quebrado foi o estado salvo. A espera continua
    de pé, a pessoa pode responder de novo, e o disjuntor não conta essa falha."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    execucao.retomada_resposta = "reprovado: Retire completamente"
    execucao.estado = "em_andamento"
    sessao.flush()

    eventos = []
    monkeypatch.setattr(disparo, "registrar_evento", lambda **kw: eventos.append(kw))
    monkeypatch.setattr(
        retoma, "executar_agente",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError(ERRO_400_REAL)),
    )

    disparo.rodar_retomada(sessao, execucao)

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"  # a espera continua de pé
    assert execucao.finalizada_em is None  # a execução NÃO foi encerrada
    acoes = [e.get("acao") for e in eventos]
    assert "retomada.entrada_recusada" in acoes
    assert "retomada.falhou" not in acoes


def test_400_de_protocolo_avisa_quem_estava_esperando(sessao, dados, monkeypatch):
    """§12-A: o caminho degradado precisa de recado honesto a quem estava esperando —
    o que houve e o que fazer. Silêncio aqui é a pessoa olhando para o celular."""
    enviados = []
    monkeypatch.setattr(
        aprovacao.telegram, "enviar",
        lambda token, chat, texto: enviados.append(texto) or {"ok": True},
    )
    canal, ag, auto = _monta(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    execucao = _exec_pausada(sessao, auto, ag, canal)
    aprovacao.vincular_pausa(sessao, execucao)
    execucao.retomada_resposta = "reprovado"
    execucao.estado = "em_andamento"
    sessao.flush()

    monkeypatch.setattr(
        retoma, "executar_agente",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError(ERRO_400_REAL)),
    )
    disparo.rodar_retomada(sessao, execucao)

    assert any("continua aberta" in t for t in enviados)
    # E a conversa segue amarrada — a espera não perdeu o endereço.
    assert sessao.scalars(
        select(Conversa).where(Conversa.execucao_id == execucao.id)
    ).first() is not None


def test_falha_de_verdade_mata_e_desvincula_a_conversa(sessao, dados, monkeypatch):
    """O outro lado da moeda: quando a execução morre MESMO, nenhuma conversa pode
    continuar viva apontando para ela. Era assim que o agente seguia conversando (e
    trabalhando) por um canal cujo fluxo já tinha morrido."""
    enviados = []
    monkeypatch.setattr(
        aprovacao.telegram, "enviar",
        lambda token, chat, texto: enviados.append(texto) or {"ok": True},
    )
    canal, ag, auto = _monta(sessao, dados)
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    execucao = _exec_pausada(sessao, auto, ag, canal)
    aprovacao.vincular_pausa(sessao, execucao)
    conversa_id = sessao.scalars(
        select(Conversa).where(Conversa.execucao_id == execucao.id)
    ).first().id
    execucao.retomada_resposta = "aprovado"
    execucao.estado = "em_andamento"
    sessao.flush()

    monkeypatch.setattr(
        retoma, "executar_agente",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("O instrumento 'X' falhou")),
    )
    disparo.rodar_retomada(sessao, execucao)

    sessao.refresh(execucao)
    assert execucao.estado == "falhou"
    conversa = sessao.get(Conversa, conversa_id)
    assert conversa.execucao_id is None  # não sobrou canal apontando para o morto
