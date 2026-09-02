"""Onda 4, fatia 2 — "Rodar de novo a partir daqui" (lacuna 25).

Quando um fluxo morre no meio, a única saída era rodar a automação INTEIRA de novo,
jogando fora os passos bons e pagando tudo outra vez. Aconteceu em 02/09: o artigo do
EST tinha 4 passos prontos e morreu no último.

A re-rodada cria uma execução NOVA (histórico não se reescreve) que herda o DESENHO, a
FICHA e a ENTRADA EXATA daquele passo. Aqui provamos isso e as recusas honestas: não se
re-roda o que ainda anda, nem um nó que não rodou, nem um nó fora do fluxo.
"""

import uuid

from mensageria.aprovacao import ESTADOS_ENCERRADOS
from modelos import Agente, Automacao, Execucao, PassoExecucao
from orquestracao import disparo, grafo

NO_1, NO_2 = "n1", "n2"


def _cenario(sessao, dados, estado="falhou"):
    """Execução com dois passos: n1 correu bem, n2 é onde queremos recomeçar."""
    ag = Agente(time_id=dados["timeA"].id, nome="Redator", papel="agente")
    sessao.add(ag)
    sessao.flush()
    cadeia = grafo.normalizar({
        "inicial": NO_1,
        "nos": [
            {"id": NO_1, "tipo": "agente", "ref": str(ag.id),
             "saidas": [{"rotulo": "ok", "destino": NO_2}]},
            {"id": NO_2, "tipo": "agente", "ref": str(ag.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    })
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Post", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia=cadeia, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    execucao = disparo.criar_execucao(sessao, auto, "a pauta", origem="manual")
    execucao.estado = estado
    execucao.dados = {"entrada": "a pauta", "titulo": "Um título"}
    for ordem, (no_id, texto) in enumerate([(NO_1, "rascunho"), (NO_2, "revisado")], 1):
        sessao.add(
            PassoExecucao(
                execucao_id=execucao.id, ordem=ordem, agente_id=ag.id, no_id=no_id,
                entrada={"texto": texto},
                saida={"texto": "saiu", "instrumentos_acionados": [], "uso": []},
                estado="concluido", tipo="agente",
            )
        )
    sessao.commit()
    return auto, execucao, ag


def test_rodar_de_novo_cria_execucao_nova_herdando_tudo(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    auto, original, _ = _cenario(sessao, dados)

    r = cliente.post(f"/execucoes/{original.id}/rodar-de-novo", json={"no_id": NO_2})
    assert r.status_code == 200, r.text
    corpo = r.json()

    assert corpo["id"] != str(original.id), "a antiga não pode ser reescrita"
    assert corpo["no_inicial"] == NO_2
    assert corpo["origem_execucao_id"] == str(original.id)
    # A entrada é a EXATA que aquele passo recebeu — não a entrada do gatilho.
    assert corpo["entrada"]["texto"] == "revisado"
    # A ficha veio junto: a re-rodada não recomeça sem o que já se sabia.
    assert corpo["dados"] == {"entrada": "a pauta", "titulo": "Um título"}
    assert corpo["estado"] == "aguardando"
    assert corpo["passos"] == []

    # A original ficou intacta, com os dois passos.
    sessao.refresh(original)
    assert original.estado == "falhou"
    assert len(cliente.get(f"/execucoes/{original.id}").json()["passos"]) == 2


def test_a_re_rodada_percorre_o_desenho_da_original(cliente, entrar, dados, sessao):
    """Mesmo que a automação tenha mudado depois, a re-rodada repete o MESMO fluxo."""
    entrar(dados["operador"])
    auto, original, ag = _cenario(sessao, dados)
    auto.cadeia = grafo.normalizar({
        "inicial": NO_1,
        "nos": [
            {"id": NO_1, "tipo": "agente", "ref": str(ag.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},  # n2 saiu do fluxo
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    })
    sessao.commit()

    r = cliente.post(f"/execucoes/{original.id}/rodar-de-novo", json={"no_id": NO_2})
    assert r.status_code == 200, r.text
    nova = sessao.get(Execucao, uuid.UUID(r.json()["id"]))
    assert grafo.indexar(nova.desenho).no(NO_2) is not None


def test_o_motor_comeca_pelo_no_pedido(sessao, dados, monkeypatch):
    """A ponta do motor: `rodar_execucao` repassa o `no_inicial` da execução."""
    auto, original, _ = _cenario(sessao, dados)
    nova = disparo.criar_execucao(
        sessao, auto, "revisado", origem="reexecucao",
        desenho=original.desenho, dados=original.dados,
        no_inicial=NO_2, origem_execucao_id=original.id,
    )
    visto: dict = {}
    monkeypatch.setattr(
        disparo, "executar_cadeia",
        lambda s, cadeia, entrada, **kw: (
            visto.update(kw) or {"estado": "concluida", "resultado": "ok", "ordem": 0,
                                 "passos": [], "avisos": []}
        ),
    )
    disparo.rodar_execucao(sessao, nova)
    assert visto["no_inicial"] == NO_2
    assert visto["ficha"]["titulo"] == "Um título"


# ─────────────────────────── as recusas honestas ───────────────────────────


def test_recusa_enquanto_a_execucao_ainda_anda(cliente, entrar, dados, sessao):
    """Re-rodar por cima do que ainda anda duplicaria o trabalho — e a publicação."""
    entrar(dados["operador"])
    for estado in ("aguardando", "em_andamento", "aguardando_humano"):
        _auto, original, _ = _cenario(sessao, dados, estado=estado)
        r = cliente.post(f"/execucoes/{original.id}/rodar-de-novo", json={"no_id": NO_2})
        assert r.status_code == 409, estado
        assert "ainda não terminou" in r.json()["detail"]
    assert "aguardando_humano" not in ESTADOS_ENCERRADOS  # a guarda é essa mesma


def test_recusa_no_que_nao_rodou_e_no_que_nao_existe(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    _auto, original, _ = _cenario(sessao, dados)
    # Nó fora do fluxo desta execução.
    r = cliente.post(f"/execucoes/{original.id}/rodar-de-novo", json={"no_id": "zzz"})
    assert r.status_code == 422
    assert "não existe no fluxo" in r.json()["detail"]
    # Nó estrutural (o motor não o executa).
    r2 = cliente.post(f"/execucoes/{original.id}/rodar-de-novo", json={"no_id": "fim"})
    assert r2.status_code == 422
    # Nó do fluxo que não chegou a rodar nesta execução.
    sessao.query(PassoExecucao).filter(
        PassoExecucao.execucao_id == original.id, PassoExecucao.no_id == NO_2
    ).delete()
    sessao.commit()
    r3 = cliente.post(f"/execucoes/{original.id}/rodar-de-novo", json={"no_id": NO_2})
    assert r3.status_code == 422
    assert "não chegou a rodar" in r3.json()["detail"]


def test_observador_nao_roda_de_novo(cliente, entrar, dados, sessao):
    """Re-rodar gasta dinheiro e pode publicar: é ação de operador para cima."""
    _auto, original, _ = _cenario(sessao, dados)
    entrar(dados["observador"])
    r = cliente.post(f"/execucoes/{original.id}/rodar-de-novo", json={"no_id": NO_2})
    assert r.status_code == 403


def test_rastro_de_conversa_nao_se_re_roda(cliente, entrar, dados, sessao):
    entrar(dados["operador"])
    sombra = Execucao(estado="conversa", modo="conversa", entrada={"texto": "oi"})
    sessao.add(sombra)
    sessao.commit()
    r = cliente.post(f"/execucoes/{sombra.id}/rodar-de-novo", json={"no_id": NO_2})
    assert r.status_code in (403, 404, 409)
