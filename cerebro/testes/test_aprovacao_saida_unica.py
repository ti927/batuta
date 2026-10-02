"""Aprovação num passo de UMA saída (decisão do maestro, 2026-10-02).

Achado no uso real: "aprova e depois publica" no mesmo agente nunca publicava pelo
Telegram — num nó de uma saída, o canal seguia direto, sem devolver a vez ao agente. Pela
TELA era o contrário: o agente publicava, mas o fluxo não andava e a mesma aprovação
reaparecia duas, três vezes. Agora é igual nas duas portas: o agente que pediu volta,
age e o fluxo segue sozinho pela única saída — a menos que ele peça aprovação de novo.

`executar_agente` é mockado — sem LLM.
"""

from testes.test_falhas_do_motor import (
    _exec_pausada,
    _monta,
    _passos,
    _responder_no_canal,
    _setup_canal,
)

from mensageria import retoma, servico

UMA_SAIDA = [{"rotulo": "segue", "quando": "", "destino": "fim"}]


def _uma_saida(sessao, auto):
    """Grava o desenho com o nó de uma saída (o canal relê a automação do banco)."""
    cadeia = dict(auto.cadeia)
    nos = [dict(n) for n in cadeia["nos"]]
    nos[0]["saidas"] = list(UMA_SAIDA)
    auto.cadeia = {**cadeia, "nos": nos}
    sessao.flush()


def _agente_que_publica(chamadas):
    def rodar(*a, **k):
        chamadas.append(k.get("saidas"))
        return {
            "saida": "Publicado no blog.", "instrumentos_acionados": ["publicar"],
            "uso": [], "mensagens_enviadas": {}, "ramo_escolhido": None,
            "ramos_escolhidos": [],
        }
    return rodar


def test_tela_o_agente_volta_age_e_o_fluxo_segue(sessao, dados, monkeypatch):
    canal, ag, auto = _monta(sessao, dados)
    _uma_saida(sessao, auto)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    chamadas: list = []
    monkeypatch.setattr(retoma, "executar_agente", _agente_que_publica(chamadas))

    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    sessao.refresh(execucao)
    assert len(chamadas) == 1  # o agente teve a vez (e publicou)
    assert execucao.estado != "aguardando_humano"  # e o fluxo andou — sem reapresentar
    agiu = [p for p in _passos(sessao, execucao.id) if p.agente_id == ag.id][-1]
    assert agiu.tipo == "agente" and agiu.saida["texto"] == "Publicado no blog."


def test_tela_pedir_aprovacao_de_novo_segue_esperando(sessao, dados, monkeypatch):
    canal, ag, auto = _monta(sessao, dados)
    _uma_saida(sessao, auto)
    execucao = _exec_pausada(sessao, auto, ag, canal)
    monkeypatch.setattr(retoma, "executar_agente", lambda *a, **k: {
        "saida": "Refiz o título, aprova?", "instrumentos_acionados": ["pedir_aprovacao"],
        "uso": [], "mensagens_enviadas": {}, "ramo_escolhido": None,
        "pausado": True, "aprovacao": {"canal_instrumento_id": str(canal.id)},
    })

    retoma.retomar_execucao(sessao, execucao, "muda o título", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"


def test_canal_o_agente_volta_age_e_o_fluxo_segue(sessao, dados, monkeypatch):
    enviados: list = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    _uma_saida(sessao, auto)
    chamadas: list = []
    monkeypatch.setattr(servico, "executar_agente", _agente_que_publica(chamadas))

    _responder_no_canal(sessao, canal, "aprovado")

    sessao.refresh(execucao)
    assert len(chamadas) == 1  # antes: o canal seguia direto, sem rodar o agente
    assert execucao.estado != "aguardando_humano"


def test_canal_pedir_aprovacao_de_novo_segue_esperando(sessao, dados, monkeypatch):
    enviados: list = []
    canal, ag, auto, execucao = _setup_canal(sessao, dados, monkeypatch, enviados)
    _uma_saida(sessao, auto)
    monkeypatch.setattr(servico, "executar_agente", lambda *a, **k: {
        "saida": "Refiz, aprova?", "instrumentos_acionados": ["pedir_aprovacao"],
        "uso": [], "mensagens_enviadas": {}, "ramo_escolhido": None,
        "pausado": True, "aprovacao": {"canal_instrumento_id": str(canal.id), "destinatario": "555"},
    })

    _responder_no_canal(sessao, canal, "muda o título")

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"


def test_duas_saidas_continua_exigindo_que_o_agente_declare(sessao, dados, monkeypatch):
    """A regra nova é só para UMA saída: com duas, sem `seguir_para` segue esperando."""
    canal, ag, auto = _monta(sessao, dados)  # nó com "aprovado" e "reprovado"
    execucao = _exec_pausada(sessao, auto, ag, canal)
    monkeypatch.setattr(retoma, "executar_agente", _agente_que_publica([]))

    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"
