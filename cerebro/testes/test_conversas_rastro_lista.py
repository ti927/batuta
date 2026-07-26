"""Fatia 1b — as execuções-sombra de conversa aparecem no filtro 'Conversas' da aba
Execuções, e o detalhe (passo a passo) abre pela MESMA tela de inspeção, com acesso
escopado ao time pela conversa → agente atendente.

Nível HTTP (client + acesso por papel). A sombra é criada direto por ORM (o rastro
em si é provado em `test_rastro_conversa.py`)."""

from modelos import Agente, Conversa, Execucao, Instrumento, PassoExecucao


def _sombra_de_conversa(sessao, time, *, contato="Maria", canal="telegram"):
    inst = Instrumento(
        time_id=time.id, nome="Bot", tipo="enviar_telegram", configuracao={}
    )
    sessao.add(inst)
    sessao.flush()
    ag = Agente(time_id=time.id, nome="Atendente", papel="agente")
    sessao.add(ag)
    sessao.flush()
    conv = Conversa(
        instrumento_id=inst.id, contato_chave="555", contato_nome=contato,
        canal=canal, estado="aberta", destino_tipo="agente", destino_id=ag.id,
    )
    sessao.add(conv)
    sessao.flush()
    sombra = Execucao(
        automacao_id=None, modo="conversa", conversa_id=conv.id,
        estado="conversa", entrada={"texto": "Atendimento"},
    )
    sessao.add(sombra)
    sessao.flush()
    sessao.add(
        PassoExecucao(
            execucao_id=sombra.id, ordem=1, agente_id=ag.id,
            entrada={"texto": "oi"},
            saida={
                "texto": "olá!", "instrumentos_acionados": [],
                "saida_escolhida": None, "uso": [],
            },
            estado="concluido",
        )
    )
    sessao.flush()
    return inst, ag, conv, sombra


def test_lista_conversas_rastro_do_time(cliente, entrar, dados, sessao):
    _sombra_de_conversa(sessao, dados["timeA"], contato="Maria")
    entrar(dados["admin"])
    r = cliente.get(f"/times/{dados['timeA'].id}/conversas-rastro")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["modo"] == "conversa"
    assert body[0]["automacao_id"] is None
    # rótulo pelo contato + canal (não por automação, que não existe)
    assert "Maria" in body[0]["automacao_nome"]
    assert "telegram" in body[0]["automacao_nome"]


def test_conversas_rastro_nao_vaza_de_outro_time(cliente, entrar, dados, sessao):
    """A sombra é do timeA; um estranho (orgB) não é membro da orgA → 404 (não revela)."""
    _sombra_de_conversa(sessao, dados["timeA"])
    entrar(dados["estranho"])
    r = cliente.get(f"/times/{dados['timeA'].id}/conversas-rastro")
    assert r.status_code == 404


def test_detalhe_da_sombra_abre_para_membro(cliente, entrar, dados, sessao):
    """O passo a passo abre pela MESMA tela de detalhe (endpoint /execucoes/{id}),
    mesmo sem automação — o acesso é resolvido pela conversa → agente → time."""
    _, _, _, sombra = _sombra_de_conversa(sessao, dados["timeA"])
    entrar(dados["observador"])  # observador vê
    r = cliente.get(f"/execucoes/{sombra.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["modo"] == "conversa"
    assert body["automacao_id"] is None
    assert len(body["passos"]) == 1
    assert body["passos"][0]["saida"]["texto"] == "olá!"


def test_detalhe_da_sombra_negado_a_estranho(cliente, entrar, dados, sessao):
    _, _, _, sombra = _sombra_de_conversa(sessao, dados["timeA"])
    entrar(dados["estranho"])
    r = cliente.get(f"/execucoes/{sombra.id}")
    assert r.status_code == 404  # não-membro → 404 (não revela existência)
