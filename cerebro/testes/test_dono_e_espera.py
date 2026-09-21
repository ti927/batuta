"""A execução ganha DONO, e a espera por humano ganha PRAZO.

§4.1 e §4.2 de `docs/FALHAS-DO-MOTOR.md` — as duas metades do mesmo defeito estrutural:
estado que pertence à EXECUÇÃO morava só na borda.

- A TRAVA morava em `conversas.estado`, que a tela não enxerga. Em 2026-09-21 uma
  resposta pelo Telegram e um clique na tela entraram na mesma execução com 1m45s de
  diferença, abriram o mesmo thread do LangGraph e o checkpoint bifurcou; a Anthropic
  recusou o histórico pela metade com um 400 e quase quatro horas de trabalho morreram.
- O RELÓGIO morava em `conversas.aguardando_ate`, então uma aprovação pedida só pela tela
  não era varrida por vigia nenhum — o único estado "em andamento" do sistema sem quem o
  varresse. Ficava parada para sempre, em silêncio.

`executar_agente` é mockado — sem LLM.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

import segredos_instrumento as si
from mensageria import aprovacao, aviso, retoma, servico, telegram
from modelos import Agente, Automacao, Execucao, Instrumento, PassoExecucao
from orquestracao import dono, espera

NO_GATE = "rev"


class _SessaoFake:
    """Reusa a sessão do teste (transação revertida) ignorando close()."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


def _monta(sessao, dados):
    canal = Instrumento(
        time_id=dados["timeA"].id, nome="Bot", tipo="enviar_telegram",
        configuracao={"destinatario_padrao": "555", "saudacao_abertura": ""},
    )
    sessao.add(canal)
    sessao.flush()
    ag = Agente(time_id=dados["timeA"].id, nome="Revisor", papel="agente")
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
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual",
        configuracao_gatilho={},
        cadeia={"inicial": NO_GATE, "nos": [no, {"id": "fim", "tipo": "fim", "saidas": []}]},
        ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    return canal, ag, auto


def _exec_pausada(sessao, auto, ag, canal=None):
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
                "texto": "ARTIGO", "instrumentos_acionados": [],
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
        select(PassoExecucao).where(PassoExecucao.execucao_id == execucao_id)
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


# ───────── §4.1 — um DONO por execução ─────────

def test_dono_e_exclusivo_entre_superficies(sessao, dados):
    """O cruzamento que faltava travar: a tela e o canal são duas portas da MESMA
    espera, e cada uma tinha a sua trava, invisível para a outra."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)

    assert dono.tomar(sessao, execucao.id, dono.TELA)
    assert not dono.tomar(sessao, execucao.id, dono.CANAL)
    assert dono.quem_tem(sessao, execucao.id) == dono.TELA


def test_a_mesma_superficie_renova_sem_conflito(sessao, dados):
    """Retomar pelo mesmo lugar é seguro e já é serializado por outros meios. Travar
    contra si mesma só criaria um impasse artificial."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    assert dono.tomar(sessao, execucao.id, dono.TELA)
    assert dono.tomar(sessao, execucao.id, dono.TELA)


def test_dono_vencido_e_assumido_pelo_proximo(sessao, dados):
    """Todo dono tem prazo: um processo que morre segurando a trava não pode deixar a
    execução inacessível para sempre — seria trocar um caos por uma paralisia."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    dono.tomar(sessao, execucao.id, dono.TELA)
    execucao.dono_ate = datetime.now(timezone.utc) - timedelta(seconds=1)
    sessao.flush()

    assert dono.quem_tem(sessao, execucao.id) is None  # vencido conta como livre
    assert dono.tomar(sessao, execucao.id, dono.CANAL)


def test_devolver_nunca_rouba_de_quem_assumiu_depois(sessao, dados):
    """Se o prazo venceu e outro assumiu, o trabalho DAQUELE é que vale — quem chegou
    atrasado para soltar a trava não pode derrubar o dono novo."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    dono.tomar(sessao, execucao.id, dono.CANAL)
    dono.devolver(sessao, execucao.id, dono.TELA)  # a tela tenta soltar o que não é dela
    assert dono.quem_tem(sessao, execucao.id) == dono.CANAL


def test_posse_solta_a_trava_mesmo_quando_o_bloco_falha(sessao, dados):
    """Senão uma exceção deixaria a execução trancada até o prazo vencer — quinze
    minutos de paralisia por causa de um erro que durou um milissegundo."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    with pytest.raises(RuntimeError):
        with dono.posse(sessao, execucao.id, dono.CANAL):
            raise RuntimeError("estourou no meio")
    assert dono.quem_tem(sessao, execucao.id) is None


def test_posse_recusa_quando_outro_esta_dentro(sessao, dados):
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    dono.tomar(sessao, execucao.id, dono.TELA)
    with pytest.raises(dono.ExecucaoOcupada) as e:
        with dono.posse(sessao, execucao.id, dono.CANAL):
            pass
    assert e.value.dono == dono.TELA


def test_tela_recusa_enquanto_o_canal_responde(cliente, entrar, dados, sessao):
    """O clique fatal de 2026-09-21. Agora é recusado — e a recusa DIZ o que está
    acontecendo, em português, em vez de um 409 seco (§12-A)."""
    entrar(dados["operador"])
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    dono.tomar(sessao, execucao.id, dono.CANAL)  # o Telegram está no meio de um turno
    sessao.commit()

    r = cliente.post(
        f"/execucoes/{execucao.id}/responder", json={"resposta": "reprovado"}
    )

    assert r.status_code == 409
    assert "Telegram" in r.json()["detail"]
    sessao.expire_all()
    ex = sessao.get(Execucao, execucao.id)
    assert ex.estado == "aguardando_humano"  # não entrou na fila por cima do turno vivo
    assert ex.retomada_resposta is None


def test_tela_livre_responde_e_fica_dona(cliente, entrar, dados, sessao):
    """Sem ninguém no caminho o clique funciona como sempre — e a posse fica registrada,
    para o canal não entrar entre o clique e o trabalho do worker."""
    entrar(dados["operador"])
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    sessao.commit()

    r = cliente.post(
        f"/execucoes/{execucao.id}/responder", json={"resposta": "aprovado"}
    )

    assert r.status_code == 200
    sessao.expire_all()
    ex = sessao.get(Execucao, execucao.id)
    assert ex.estado == "aguardando"
    assert ex.dono == dono.TELA


def test_canal_recusa_enquanto_a_tela_responde(sessao, dados, monkeypatch):
    """A porta simétrica. A mensagem da pessoa NÃO se perde: fica na thread e ela pode
    reenviar — mesmo critério do vigia de turno preso (não reprocessar sozinho algo que
    já pode ter tido efeito externo)."""
    enviados = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    dono.tomar(sessao, execucao.id, dono.TELA)  # a tela está retomando agora
    chamou = []
    monkeypatch.setattr(
        servico, "executar_agente", lambda *a, **k: chamou.append(1) or {}
    )

    _responder_no_canal(sessao, canal, "reprovado")

    assert not chamou  # o agente NÃO rodou por cima da retomada da tela
    assert any("aplicativo" in t for t in enviados)  # e a pessoa soube por quê
    assert len(_passos(sessao, execucao.id)) == 1  # nenhum passo novo no rastro


def test_canal_livre_roda_e_devolve_a_trava(sessao, dados, monkeypatch):
    """Depois do turno a execução volta a ficar livre — principalmente para o humano
    que vai responder pela outra porta."""
    enviados = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    monkeypatch.setattr(
        servico, "executar_agente",
        lambda *a, **k: {
            "saida": "Por que reprovou?", "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {}, "ramo_escolhido": None,
        },
    )

    _responder_no_canal(sessao, canal, "reprovado")

    assert dono.quem_tem(sessao, execucao.id) is None
    assert len(_passos(sessao, execucao.id)) == 2


# ───────── §4.2 — toda espera tem prazo próprio ─────────

def test_pausa_carimba_o_prazo_da_espera(sessao, dados, monkeypatch):
    """Sem canal amarrado, esta espera não tinha relógio NENHUM — era o único estado do
    sistema sem vigia. Agora a própria execução carrega quando ela vira alarme."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag)  # sem canal, de propósito
    execucao.espera_ate = None
    monkeypatch.setattr(
        retoma, "executar_agente",
        lambda *a, **k: {
            "saida": "(pergunta)", "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {}, "ramo_escolhido": None,
        },
    )

    retoma.retomar_execucao(sessao, execucao, "reprovado", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.espera_ate is not None


def test_prazo_zero_nunca_alarma(sessao, dados):
    """Limite configurável, como todo limite — e desligável, para o fluxo que espera
    semanas de propósito não virar um alarme recorrente."""
    canal, ag, auto = _monta(sessao, dados)
    auto.configuracao = {"ajustes": {"teto_espera_humano_min": 0}}
    sessao.flush()
    execucao = _exec_pausada(sessao, auto, ag, canal)
    espera.marcar(sessao, execucao)
    assert execucao.espera_ate is None


def test_espera_esquecida_vira_alarme_e_avisa(sessao, dados, monkeypatch):
    """O fim do silêncio. Antes disto, uma aprovação que ninguém respondeu ficava parada
    para sempre e NINGUÉM ficava sabendo — nem log, nem aviso, nem tela."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    execucao.espera_ate = datetime.now(timezone.utc) - timedelta(minutes=1)
    sessao.flush()
    eventos, avisos = [], []
    monkeypatch.setattr(espera, "registrar_evento", lambda **kw: eventos.append(kw))
    monkeypatch.setattr(
        aviso, "avisar_time", lambda s, ex, texto, **k: avisos.append(texto) or True
    )

    assert espera.varrer_esquecidas(sessao) == 1

    alarmes = [e for e in eventos if e.get("acao") == "espera.esquecida"]
    assert len(alarmes) == 1 and alarmes[0]["nivel"] == "error"
    assert any("esperando uma aprovação" in t for t in avisos)


def test_espera_esquecida_NAO_encerra_a_execucao(sessao, dados, monkeypatch):
    """Esperar dias por uma aprovação é legítimo: quem aprova viaja, dorme, tem
    segunda-feira. Matar o trabalho por isso seria trocar silêncio por prejuízo."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    execucao.espera_ate = datetime.now(timezone.utc) - timedelta(minutes=1)
    sessao.flush()
    monkeypatch.setattr(aviso, "avisar_time", lambda *a, **k: True)

    espera.varrer_esquecidas(sessao)

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"
    assert execucao.finalizada_em is None


def test_espera_esquecida_avisa_uma_vez_so(sessao, dados, monkeypatch):
    """Alarme que repete sem novidade é alarme que ninguém lê — e aí a página de status
    perde a única serventia que tem."""
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    execucao.espera_ate = datetime.now(timezone.utc) - timedelta(minutes=1)
    sessao.flush()
    avisos = []
    monkeypatch.setattr(
        aviso, "avisar_time", lambda s, ex, t, **k: avisos.append(t) or True
    )

    assert espera.varrer_esquecidas(sessao) == 1
    assert espera.varrer_esquecidas(sessao) == 0
    assert len(avisos) == 1


def test_espera_dentro_do_prazo_e_deixada_em_paz(sessao, dados, monkeypatch):
    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    execucao.espera_ate = datetime.now(timezone.utc) + timedelta(hours=1)
    sessao.flush()
    monkeypatch.setattr(aviso, "avisar_time", lambda *a, **k: True)
    assert espera.varrer_esquecidas(sessao) == 0


def test_o_vigia_da_espera_carimba_o_batimento(sessao, dados, monkeypatch):
    """§12-A um nível acima: nenhum vigia pode ficar sem quem o vigie. Sem o carimbo,
    um job que passasse a levantar exceção continuaria parecendo saudável."""
    import vigias

    from sessao import CriadorDeSessao  # noqa: F401 — documenta de onde vem a sessão

    monkeypatch.setattr(espera, "varrer_esquecidas", lambda s: 0)
    monkeypatch.setitem(vigias.BATIMENTOS, "esperas_humanas", None)
    vigias.BATIMENTOS.pop("esperas_humanas", None)

    espera.varrer_esquecidas_job()

    assert vigias.atraso_s("esperas_humanas") is not None


def test_retomada_adia_quando_a_posse_venceu_e_o_canal_assumiu(sessao, dados, monkeypatch):
    """O furo estreito: a posse da tela tem prazo, e uma retomada que ficou na fila mais
    tempo que o prazo poderia rodar em cima de um turno do canal — recriando exatamente
    a concorrencia que este mecanismo existe para impedir. A resposta do humano NAO e
    consumida: so se consome o que se vai usar."""
    from orquestracao import disparo

    canal, ag, auto = _monta(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    execucao.retomada_resposta = "aprovado"
    execucao.estado = "em_andamento"
    sessao.flush()
    dono.tomar(sessao, execucao.id, dono.CANAL)  # o canal assumiu no intervalo
    rodou = []
    monkeypatch.setattr(retoma, "executar_agente", lambda *a, **k: rodou.append(1) or {})

    disparo.rodar_retomada(sessao, execucao)

    assert not rodou
    sessao.refresh(execucao)
    assert execucao.estado == "aguardando"            # volta para a fila
    assert execucao.retomada_resposta == "aprovado"   # e a resposta esta intacta
