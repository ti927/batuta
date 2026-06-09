"""A parede de ativação: ação irreversível só ativa com portão humano antes.

Cobre a lógica pura (`problemas_de_portao`, sem banco) em todos os casos e o
comportamento na rota de automações (ativar com publicador sem portão → 422)."""

from modelos import Agente, AgenteInstrumento, Instrumento
from portao_ativacao import problemas_de_portao


# ───────────────────────── lógica pura ─────────────────────────

def _cadeia(lider_saida, *, inicio="a", nos_extra=None):
    nos = {"a": lider_saida, "x": {"saidas": [{"rotulo": "1", "destino": None}]}}
    if nos_extra:
        nos.update(nos_extra)
    return {"inicio": inicio, "nos": nos}


def test_reversivel_sem_portao_pode_ativar():
    cadeia = _cadeia({"saidas": [{"rotulo": "1", "destino": "x"}]})
    assert problemas_de_portao(cadeia, {"a": "Líder", "x": "Redator"}, set()) == []


def test_irreversivel_com_portao_no_anterior_pode_ativar():
    cadeia = _cadeia({"pausa_humano": True, "saidas": [{"rotulo": "1", "destino": "x"}]})
    assert problemas_de_portao(cadeia, {"a": "Guardião", "x": "Publicador"}, {"x"}) == []


def test_irreversivel_sem_portao_no_anterior_bloqueia():
    cadeia = _cadeia({"saidas": [{"rotulo": "1", "destino": "x"}]})
    probs = problemas_de_portao(cadeia, {"a": "Guardião", "x": "Publicador"}, {"x"})
    assert len(probs) == 1
    assert "Publicador" in probs[0] and "Guardião" in probs[0]


def test_irreversivel_no_inicio_bloqueia():
    cadeia = {"inicio": "x", "nos": {"x": {"saidas": [{"rotulo": "1", "destino": None}]}}}
    probs = problemas_de_portao(cadeia, {"x": "Publicador"}, {"x"})
    assert len(probs) == 1 and "início" in probs[0]


def test_irreversivel_fora_da_cadeia_nao_roda_entao_ok():
    # 'x' é irreversível mas não é início nem destino de ninguém: não roda aqui.
    cadeia = {"inicio": "a", "nos": {"a": {"saidas": [{"rotulo": "1", "destino": None}]}}}
    assert problemas_de_portao(cadeia, {"a": "Líder", "x": "Publicador"}, {"x"}) == []


def test_um_anterior_com_portao_e_outro_sem_bloqueia():
    # dois nós levam a 'x'; só um tem portão → ainda bloqueia (todos precisam ter)
    cadeia = {
        "inicio": "a",
        "nos": {
            "a": {"pausa_humano": True, "saidas": [{"rotulo": "1", "destino": "x"}]},
            "b": {"saidas": [{"rotulo": "1", "destino": "x"}]},
            "x": {"saidas": [{"rotulo": "1", "destino": None}]},
        },
    }
    probs = problemas_de_portao(cadeia, {"a": "A", "b": "B", "x": "Pub"}, {"x"})
    assert len(probs) == 1 and "'B'" in probs[0]


# ───────────────────────── na rota ─────────────────────────

def _time_com_publicador(sessao, time, *, com_portao: bool):
    lider = Agente(time_id=time.id, nome="Guardião", papel="lider")
    pub = Agente(time_id=time.id, nome="Publicador", papel="agente")
    sessao.add_all([lider, pub])
    sessao.flush()
    inst = Instrumento(
        time_id=time.id, nome="WordPress", tipo="publicar_wordpress", configuracao={}
    )
    sessao.add(inst)
    sessao.flush()
    sessao.add(AgenteInstrumento(agente_id=pub.id, instrumento_id=inst.id))
    sessao.flush()
    no_lider = {"saidas": [{"rotulo": "1", "quando": "sempre", "destino": str(pub.id)}]}
    if com_portao:
        no_lider["pausa_humano"] = True
    cadeia = {
        "inicio": str(lider.id),
        "nos": {
            str(lider.id): no_lider,
            str(pub.id): {"saidas": [{"rotulo": "1", "quando": "fim", "destino": None}]},
        },
    }
    return cadeia


def _payload(cadeia, ativa):
    return {
        "nome": "Publicar no blog",
        "tipo_gatilho": "manual",
        "configuracao_gatilho": {},
        "cadeia": cadeia,
        "ativa": ativa,
    }


def test_ativar_publicador_sem_portao_bloqueia_422(cliente, entrar, dados, sessao):
    cadeia = _time_com_publicador(sessao, dados["timeA"], com_portao=False)
    entrar(dados["operador"])
    resp = cliente.post(
        f"/times/{dados['timeA'].id}/automacoes", json=_payload(cadeia, ativa=True)
    )
    assert resp.status_code == 422
    assert "Publicador" in str(resp.json()["detail"])


def test_criar_inativa_com_publicador_sem_portao_passa(cliente, entrar, dados, sessao):
    # inativa não roda → a parede não se aplica
    cadeia = _time_com_publicador(sessao, dados["timeA"], com_portao=False)
    entrar(dados["operador"])
    resp = cliente.post(
        f"/times/{dados['timeA'].id}/automacoes", json=_payload(cadeia, ativa=False)
    )
    assert resp.status_code == 201
    assert resp.json()["ativa"] is False


def test_ativar_publicador_com_portao_passa(cliente, entrar, dados, sessao):
    cadeia = _time_com_publicador(sessao, dados["timeA"], com_portao=True)
    entrar(dados["operador"])
    resp = cliente.post(
        f"/times/{dados['timeA'].id}/automacoes", json=_payload(cadeia, ativa=True)
    )
    assert resp.status_code == 201
    assert resp.json()["ativa"] is True


# ───── resolução POR INSTÂNCIA (config + interruptor) na rota ─────

def _time_com_instrumento(sessao, time, *, tipo, configuracao, exige=None, portao=False):
    """Líder → Operador (com o instrumento dado). Devolve a cadeia."""
    lider = Agente(time_id=time.id, nome="Líder", papel="lider")
    operador = Agente(time_id=time.id, nome="Operador", papel="agente")
    sessao.add_all([lider, operador])
    sessao.flush()
    inst = Instrumento(
        time_id=time.id, nome="Inst", tipo=tipo,
        configuracao=configuracao, exige_aprovacao=exige,
    )
    sessao.add(inst)
    sessao.flush()
    sessao.add(AgenteInstrumento(agente_id=operador.id, instrumento_id=inst.id))
    sessao.flush()
    no_lider = {"saidas": [{"rotulo": "1", "quando": "s", "destino": str(operador.id)}]}
    if portao:
        no_lider["pausa_humano"] = True
    return {
        "inicio": str(lider.id),
        "nos": {
            str(lider.id): no_lider,
            str(operador.id): {"saidas": [{"rotulo": "1", "quando": "fim", "destino": None}]},
        },
    }


def _ativar(cliente, time_id, cadeia):
    return cliente.post(f"/times/{time_id}/automacoes", json=_payload(cadeia, ativa=True))


def test_rest_get_sem_portao_ativa(cliente, entrar, dados, sessao):
    cadeia = _time_com_instrumento(
        sessao, dados["timeA"], tipo="chamar_api_rest",
        configuracao={"url": "https://x", "metodo": "GET"},
    )
    entrar(dados["operador"])
    assert _ativar(cliente, dados["timeA"].id, cadeia).status_code == 201


def test_rest_post_sem_portao_bloqueia(cliente, entrar, dados, sessao):
    cadeia = _time_com_instrumento(
        sessao, dados["timeA"], tipo="chamar_api_rest",
        configuracao={"url": "https://x", "metodo": "POST"},
    )
    entrar(dados["operador"])
    resp = _ativar(cliente, dados["timeA"].id, cadeia)
    assert resp.status_code == 422 and "Operador" in str(resp.json()["detail"])


def test_rest_get_com_override_sempre_bloqueia(cliente, entrar, dados, sessao):
    # interruptor "sempre" (True) força portão até num GET
    cadeia = _time_com_instrumento(
        sessao, dados["timeA"], tipo="chamar_api_rest",
        configuracao={"url": "https://x", "metodo": "GET"}, exige=True,
    )
    entrar(dados["operador"])
    assert _ativar(cliente, dados["timeA"].id, cadeia).status_code == 422


def test_sql_somente_leitura_sem_portao_ativa(cliente, entrar, dados, sessao):
    cadeia = _time_com_instrumento(
        sessao, dados["timeA"], tipo="banco_sql",
        configuracao={"host": "h", "banco": "b", "usuario": "u", "somente_leitura": True},
    )
    entrar(dados["operador"])
    assert _ativar(cliente, dados["timeA"].id, cadeia).status_code == 201
