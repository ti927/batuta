"""Onda 4, Fatia 1 — a execução guarda o desenho que ela rodou (lacunas 28 e 29).

Até aqui o motor e a retomada liam a `automacoes.cadeia` VIVA. Duas consequências:
inspecionar uma execução antiga mostrava o fluxo de HOJE, e — o bug de verdade —
editar a automação com uma aprovação em aberto mudava o caminho NO MEIO da corrida.

Aqui provamos as quatro pontas: a foto é tirada no disparo; o motor roda a foto mesmo
depois de a automação mudar; a retomada idem; e execução ANTIGA (sem foto) continua
lendo a cadeia viva, sem regressão.
"""

from mensageria import retoma
from modelos import Agente, Automacao, Execucao, PassoExecucao
from orquestracao import disparo, grafo

NO_A, NO_B, NO_C = "a", "b", "c"


def _cadeia(destino_de_a: str) -> dict:
    """Grafo mínimo: A → (destino) e dois destinos possíveis, B e C."""
    return {
        "inicial": NO_A,
        "nos": [
            {"id": NO_A, "tipo": "agente", "ref": "",
             "saidas": [{"rotulo": "segue", "quando": "sempre", "destino": destino_de_a}]},
            {"id": NO_B, "tipo": "agente", "ref": "",
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": NO_C, "tipo": "agente", "ref": "",
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }


def _automacao(sessao, dados, destino_de_a: str = NO_B):
    ag = Agente(time_id=dados["timeA"].id, nome="Revisor", papel="agente")
    sessao.add(ag)
    sessao.flush()
    cadeia = _cadeia(destino_de_a)
    for no in cadeia["nos"]:
        if no["tipo"] == "agente":
            no["ref"] = str(ag.id)
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia=grafo.normalizar(cadeia), ativa=False,
        configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    return auto, ag


def _destino_do_a(cadeia: dict) -> str:
    no = grafo.indexar(grafo.normalizar(cadeia)).no(NO_A)
    return no["saidas"][0]["destino"]


# ───────────────────────────── a foto ─────────────────────────────


def test_disparo_fotografa_o_desenho(sessao, dados):
    """`criar_execucao` é o funil único dos 4 gatilhos: a foto nasce ali."""
    auto, _ = _automacao(sessao, dados)
    execucao = disparo.criar_execucao(sessao, auto, "entrada", origem="manual")
    assert execucao.desenho, "a execução tem de nascer com o desenho do momento"
    assert _destino_do_a(execucao.desenho) == NO_B


def test_execucao_roda_a_foto_mesmo_depois_de_a_automacao_mudar(sessao, dados, monkeypatch):
    """O coração da lacuna 29: editar a automação não muda a execução já disparada."""
    auto, _ = _automacao(sessao, dados, destino_de_a=NO_B)
    execucao = disparo.criar_execucao(sessao, auto, "entrada", origem="manual")

    # Alguém edita a automação DEPOIS do disparo: agora A leva a C.
    auto.cadeia = grafo.normalizar(_cadeia(NO_C))
    sessao.commit()

    vistas: list[dict] = []

    def _fake(sessao_, cadeia, entrada, **kw):
        vistas.append(cadeia)
        return {"estado": "concluida", "resultado": "ok", "ordem": 0,
                "passos": [], "avisos": []}

    monkeypatch.setattr(disparo, "executar_cadeia", _fake)
    disparo.rodar_execucao(sessao, execucao)

    assert vistas, "o motor precisa ter sido chamado"
    assert _destino_do_a(vistas[0]) == NO_B, "rodou o desenho de hoje, não o do disparo"


def test_execucao_antiga_sem_foto_usa_a_cadeia_viva(sessao, dados, monkeypatch):
    """Execução anterior a esta onda: `desenho` nulo → comportamento de antes."""
    auto, _ = _automacao(sessao, dados, destino_de_a=NO_C)
    execucao = Execucao(automacao_id=auto.id, estado="aguardando", entrada={"texto": "x"})
    sessao.add(execucao)
    sessao.flush()
    assert execucao.desenho is None

    vistas: list[dict] = []
    monkeypatch.setattr(
        disparo, "executar_cadeia",
        lambda s, cadeia, entrada, **kw: (
            vistas.append(cadeia)
            or {"estado": "concluida", "resultado": "ok", "ordem": 0,
                "passos": [], "avisos": []}
        ),
    )
    disparo.rodar_execucao(sessao, execucao)
    assert _destino_do_a(vistas[0]) == NO_C


def test_retomada_localiza_o_no_pelo_desenho_da_execucao(sessao, dados):
    """A retomada de uma aprovação lê a foto — não as setas que alguém acabou de mexer."""
    auto, ag = _automacao(sessao, dados, destino_de_a=NO_B)
    execucao = disparo.criar_execucao(sessao, auto, "entrada", origem="manual")
    execucao.estado = "aguardando_humano"
    sessao.add(
        PassoExecucao(
            execucao_id=execucao.id, ordem=1, agente_id=ag.id, no_id=NO_A,
            entrada={"texto": "rascunho"},
            saida={"texto": "APRESENTADO", "instrumentos_acionados": [],
                   "saida_escolhida": None, "uso": []},
            estado="concluido", tipo="espera_humano",
        )
    )
    # A automação muda embaixo da aprovação aberta.
    auto.cadeia = grafo.normalizar(_cadeia(NO_C))
    sessao.commit()

    _ultimo, no, no_id, cadeia, _idx = retoma.localizar_no_pausado(sessao, execucao)
    assert no_id == NO_A
    assert no["saidas"][0]["destino"] == NO_B, "a retomada seguiria pelo caminho novo"
    assert _destino_do_a(cadeia) == NO_B


# ─────────────────── a comparação (o que é "editar o fluxo") ───────────────────


def test_mesmo_desenho_ignora_cosmetico_e_ve_mudanca_real(sessao, dados):
    """Mover uma caixa na tela não é editar o fluxo; trocar o destino de uma seta é."""
    a = grafo.normalizar(_cadeia(NO_B))
    b = grafo.normalizar(_cadeia(NO_B))
    for no in b["nos"]:
        no["x"], no["y"] = 999, 999
        for s in no.get("saidas") or []:
            s["tone"] = "loop"
    assert grafo.mesmo_desenho(a, b)

    c = grafo.normalizar(_cadeia(NO_C))
    assert not grafo.mesmo_desenho(a, c)


def test_desenho_que_roda_cai_para_a_cadeia_viva():
    """Sem foto, vale a cadeia da automação; sem nenhuma das duas, grafo vazio."""
    viva = _cadeia(NO_C)
    assert _destino_do_a(grafo.desenho_que_roda(None, viva)) == NO_C
    assert _destino_do_a(grafo.desenho_que_roda(_cadeia(NO_B), viva)) == NO_B
    assert grafo.desenho_que_roda(None, None) == {}


# ─────────────────────────── o que a tela recebe ───────────────────────────


def test_inspecao_devolve_a_ficha_e_avisa_o_desenho_editado(cliente, entrar, dados, sessao):
    """Duas coisas na mesma resposta: a FICHA da Onda 2 (que nunca chegava à tela) e o
    aviso de que a automação mudou depois desta execução."""
    entrar(dados["operador"])
    auto, _ = _automacao(sessao, dados, destino_de_a=NO_B)
    execucao = disparo.criar_execucao(sessao, auto, "entrada", origem="manual")
    execucao.dados = {"entrada": "o artigo", "titulo": "Um título"}
    sessao.commit()

    r = cliente.get(f"/execucoes/{execucao.id}")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["dados"] == {"entrada": "o artigo", "titulo": "Um título"}
    assert corpo["desenho_editado_depois"] is False

    auto.cadeia = grafo.normalizar(_cadeia(NO_C))
    sessao.commit()
    corpo2 = cliente.get(f"/execucoes/{execucao.id}").json()
    assert corpo2["desenho_editado_depois"] is True


def test_execucao_sem_foto_nunca_afirma_que_foi_editada(cliente, entrar, dados, sessao):
    """Sem foto não há como saber — e afirmar seria pior do que calar."""
    entrar(dados["operador"])
    auto, _ = _automacao(sessao, dados)
    execucao = Execucao(automacao_id=auto.id, estado="concluida", entrada={"texto": "x"})
    sessao.add(execucao)
    sessao.commit()
    corpo = cliente.get(f"/execucoes/{execucao.id}").json()
    assert corpo["desenho_editado_depois"] is False
