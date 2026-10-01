"""Excluir agente pela tela (2026-10-01): o card da aba Agentes ganhou "Excluir", e o
cérebro recusa (409, dizendo qual automação) se o agente faz parte de algum desenho."""

from modelos import Agente, Automacao


def _agente(sessao, time, nome="Redator"):
    ag = Agente(time_id=time.id, nome=nome, papel="agente")
    sessao.add(ag)
    sessao.flush()
    return ag


def _automacao(sessao, time, agente, nome="Publicar post"):
    auto = Automacao(
        time_id=time.id, nome=nome, tipo_gatilho="manual", configuracao_gatilho={},
        cadeia={"inicial": "n1", "nos": [{
            "id": "n1", "tipo": "agente", "ref": str(agente.id),
            "saidas": [{"id": "s0", "rotulo": "ok", "quando": "sempre", "destino": "fim"}],
        }]},
        ativa=False,
    )
    sessao.add(auto)
    sessao.flush()
    return auto


def test_uso_lista_as_automacoes(cliente, entrar, sessao, dados):
    ag = _agente(sessao, dados["timeA"])
    _automacao(sessao, dados["timeA"], ag)
    entrar(dados["operador"])
    r = cliente.get(f"/agentes/{ag.id}/uso")
    assert r.status_code == 200
    assert [a["nome"] for a in r.json()["automacoes"]] == ["Publicar post"]


def test_nao_exclui_agente_que_esta_numa_automacao(cliente, entrar, sessao, dados):
    ag = _agente(sessao, dados["timeA"])
    _automacao(sessao, dados["timeA"], ag)
    entrar(dados["admin"])
    r = cliente.delete(f"/agentes/{ag.id}")
    assert r.status_code == 409
    assert "“Publicar post”" in r.json()["detail"]
    assert sessao.get(Agente, ag.id) is not None


def test_exclui_agente_fora_de_automacao(cliente, entrar, sessao, dados):
    ag = _agente(sessao, dados["timeA"])
    outro = _agente(sessao, dados["timeA"], "Revisor")
    _automacao(sessao, dados["timeA"], outro)
    entrar(dados["admin"])
    assert cliente.get(f"/agentes/{ag.id}/uso").json() == {"automacoes": []}
    assert cliente.delete(f"/agentes/{ag.id}").status_code == 204


def test_operador_nao_exclui(cliente, entrar, sessao, dados):
    ag = _agente(sessao, dados["timeA"])
    entrar(dados["operador"])
    assert cliente.delete(f"/agentes/{ag.id}").status_code == 403
