"""Retomada de portão em SEGUNDO PLANO (§12-A).

Aprovar um portão pela TELA rodava a retomada DENTRO do request (`retomar_execucao`),
que executa o próximo passo — muitas vezes pesado (publicar, gerar mídia). Passando do
tempo-limite do proxy, a conexão caía e o navegador dizia "a conexão falhou", sempre.

Agora a rota `responder` ENFILEIRA (guarda a resposta em `retomada_resposta`, volta a
`aguardando`, cutuca a fila e devolve na hora) e um trabalhador roda a retomada via
`disparo.rodar_retomada` (que delega ao MESMO `retoma.retomar_execucao`). Estes testes
cobrem a rota (enfileira, não roda inline; guardas 409/422) e o worker (avança o fluxo).
`executar_agente` é mockado — sem LLM."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from mensageria import retoma
from modelos import Agente, Automacao, Execucao, PassoExecucao

NO_GATE = "rev"


def _automacao(sessao, dados):
    ag = Agente(time_id=dados["timeA"].id, nome="Revisor", papel="agente")
    sessao.add(ag)
    sessao.flush()
    no = {
        "id": NO_GATE, "tipo": "agente", "ref": str(ag.id), "gate": True,
        "saidas": [
            {"rotulo": "aprovado", "quando": "ok", "destino": "fim"},
            {"rotulo": "reprovado", "quando": "nao", "destino": "fim"},
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
    return auto, ag


def _exec_pausada(sessao, auto, ag, *, com_passo=True):
    execucao = Execucao(
        automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"}
    )
    sessao.add(execucao)
    sessao.flush()
    if com_passo:
        sessao.add(
            PassoExecucao(
                execucao_id=execucao.id, ordem=1, agente_id=ag.id, no_id=NO_GATE,
                entrada={"texto": "rascunho"},
                saida={"texto": "ARTIGO", "instrumentos_acionados": [],
                       "saida_escolhida": None, "uso": []},
                estado="concluido",
            )
        )
    sessao.flush()
    return execucao


def _n_passos(sessao, execucao_id):
    return len(
        sessao.scalars(
            select(PassoExecucao).where(PassoExecucao.execucao_id == execucao_id)
        ).all()
    )


# ─────────────────────── a ROTA enfileira (não roda inline) ───────────────────────


def test_responder_enfileira_e_nao_roda_inline(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    auto, ag = _automacao(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag)
    sessao.commit()

    r = cliente.post(
        f"/execucoes/{execucao.id}/responder", json={"resposta": "aprovado"}
    )
    assert r.status_code == 200
    sessao.expire_all()
    ex = sessao.get(Execucao, execucao.id)
    assert ex.estado == "aguardando"           # voltou para a fila
    assert ex.retomada_resposta == "aprovado"  # a resposta ficou guardada
    # NÃO rodou inline: segue com 1 passo só (a apresentação do portão), sem o publisher.
    assert _n_passos(sessao, execucao.id) == 1


def test_responder_409_se_nao_esta_aguardando(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    auto, _ag = _automacao(sessao, dados)
    execucao = Execucao(automacao_id=auto.id, estado="concluida", entrada={"texto": "x"})
    sessao.add(execucao)
    sessao.commit()
    r = cliente.post(f"/execucoes/{execucao.id}/responder", json={"resposta": "ok"})
    assert r.status_code == 409


def test_responder_422_sem_passo_de_pausa(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    auto, ag = _automacao(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag, com_passo=False)
    sessao.commit()
    r = cliente.post(f"/execucoes/{execucao.id}/responder", json={"resposta": "ok"})
    assert r.status_code == 422


# ─────────────────── o WORKER roda a retomada e avança o fluxo ───────────────────


def test_retomada_inline_sobrevive_ao_sweeper_concorrente(sessao, dados, monkeypatch):
    """Regressão do bug real (execução f5de8d21): retomada INLINE de um portão (o
    caminho do CANAL/Telegram, que NÃO passa pela fila) após uma longa espera. Ao
    avançar para `em_andamento`, `iniciada_em` é reiniciado — senão o sweeper de presas,
    rodando concorrente durante o próximo passo, mata a execução porque o último passo
    (o do portão) é anterior à espera. Simula o sweeper DENTRO do passo pós-portão."""
    import fila

    # Cadeia: portão → publicador (nó NÃO-fim, para forçar o em_andamento) → fim.
    ag = Agente(time_id=dados["timeA"].id, nome="Revisor", papel="agente")
    pub = Agente(time_id=dados["timeA"].id, nome="Publicador", papel="agente")
    sessao.add_all([ag, pub])
    sessao.flush()
    cadeia = {
        "inicial": NO_GATE,
        "nos": [
            {"id": NO_GATE, "tipo": "agente", "ref": str(ag.id), "gate": True, "saidas": [
                {"rotulo": "aprovado", "quando": "ok", "destino": "pub"},
                {"rotulo": "reprovado", "quando": "nao", "destino": "fim"}]},
            {"id": "pub", "tipo": "agente", "ref": str(pub.id),
             "saidas": [{"rotulo": "0", "quando": "", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia=cadeia, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()

    velho = datetime.now(timezone.utc) - timedelta(minutes=60)  # ~1h de espera no portão
    execucao = Execucao(
        automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"},
        iniciada_em=velho,
    )
    sessao.add(execucao)
    sessao.flush()
    sessao.add(PassoExecucao(
        execucao_id=execucao.id, ordem=1, agente_id=ag.id, no_id=NO_GATE,
        entrada={"texto": "rascunho"},
        saida={"texto": "ARTIGO", "instrumentos_acionados": [], "saida_escolhida": None, "uso": []},
        estado="concluido", finalizado_em=velho,  # passo do portão: anterior à espera
    ))
    sessao.flush()

    # Caminho MECÂNICO (permitir_conversa=False, como o CANAL/Telegram): a resposta
    # escolhe a saída SEM re-rodar o agente — logo NÃO cria um passo novo antes de
    # avançar, então o único passo (o do portão) segue antigo. É o caso vulnerável.
    monkeypatch.setattr(retoma, "_escolher_saida", lambda resposta, saidas: (saidas[0], None))
    # O passo pós-portão: DENTRO dele, o sweeper roda concorrente. Com a correção, a
    # execução (em_andamento, iniciada_em fresco) sobrevive; sem ela, seria morta aqui.
    visto = {}

    def cadeia_stub(*a, **k):
        fila.recuperar_execucoes_presas(sessao)
        sessao.refresh(execucao)
        visto["estado_durante"] = execucao.estado
        return {"estado": "concluida", "resultado": "publicado"}

    monkeypatch.setattr(retoma, "executar_cadeia", cadeia_stub)

    retoma.retomar_execucao(
        sessao, execucao, "aprovado", chaves={}, origens={}, permitir_conversa=False
    )

    assert visto["estado_durante"] == "em_andamento"  # NÃO foi morta pelo sweeper
    sessao.refresh(execucao)
    assert execucao.estado == "concluida"


def test_rodar_retomada_avanca_o_fluxo_e_consome_a_resposta(sessao, dados, monkeypatch):
    from orquestracao import disparo

    auto, ag = _automacao(sessao, dados)
    execucao = _exec_pausada(sessao, auto, ag)
    # Estado como o worker deixa após reivindicar da fila.
    execucao.retomada_resposta = "ok"
    execucao.estado = "em_andamento"
    sessao.flush()

    # A re-rodada do agente decide "aprovado" → ramo → fim → concluída (sem LLM).
    monkeypatch.setattr(
        retoma, "executar_agente",
        lambda *a, **k: {
            "saida": "(narração)", "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {}, "ramo_escolhido": "aprovado",
        },
    )
    disparo.rodar_retomada(sessao, execucao)

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"
    assert execucao.retomada_resposta is None  # consumida ao rodar
    assert _n_passos(sessao, execucao.id) == 2  # apresentação + a rodada da retomada
