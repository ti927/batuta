"""Rotas de execução — foco no `POST /execucoes/{id}/cancelar` num PORTÃO.

Cobre o que faltava: cancelar uma execução pausada num portão DESVINCULA a conversa
do aprovador (lacuna real — antes a Conversa ficava apontando para a execução
cancelada) e respeita a permissão (operador+, não observador) e o 409.
"""

from modelos import Automacao, Conversa, Execucao, Instrumento


def _portao_pausado(sessao, dados, *, com_conversa=True):
    """Uma execução pausada num portão; opcionalmente com a conversa do aprovador
    amarrada (como faz `aprovacao.vincular_pausa`)."""
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual",
        configuracao_gatilho={},
        cadeia={"inicial": "n", "nos": [
            {"id": "n", "tipo": "agente", "ref": "x", "gate": True, "saidas": []}
        ]},
        ativa=False,
    )
    sessao.add(auto)
    sessao.flush()
    execucao = Execucao(
        automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"}
    )
    sessao.add(execucao)
    sessao.flush()
    conv = None
    if com_conversa:
        canal = Instrumento(
            time_id=dados["timeA"].id, nome="Bot", tipo="enviar_telegram",
            configuracao={},
        )
        sessao.add(canal)
        sessao.flush()
        conv = Conversa(
            instrumento_id=canal.id, contato_chave="555",
            estado="aguardando_resposta", execucao_id=execucao.id,
        )
        sessao.add(conv)
        sessao.flush()
    return auto, execucao, conv


def test_cancelar_portao_desvincula_a_conversa(cliente, entrar, dados, sessao):
    _auto, execucao, conv = _portao_pausado(sessao, dados)
    entrar(dados["operador"])
    resp = cliente.post(f"/execucoes/{execucao.id}/cancelar", json={})
    assert resp.status_code == 200
    assert resp.json()["estado"] == "cancelada"
    sessao.refresh(conv)
    assert conv.execucao_id is None  # a conversa do aprovador foi desvinculada


def test_cancelar_exige_operador(cliente, entrar, dados, sessao):
    _auto, execucao, _conv = _portao_pausado(sessao, dados, com_conversa=False)
    entrar(dados["observador"])  # observador responde o portão, mas NÃO cancela
    resp = cliente.post(f"/execucoes/{execucao.id}/cancelar", json={})
    assert resp.status_code == 403


def test_cancelar_ja_encerrada_409(cliente, entrar, dados, sessao):
    auto = Automacao(
        time_id=dados["timeA"].id, nome="F", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=False,
    )
    sessao.add(auto)
    sessao.flush()
    execucao = Execucao(
        automacao_id=auto.id, estado="concluida", entrada={"texto": "x"},
        resultado={"texto": "ok"},
    )
    sessao.add(execucao)
    sessao.flush()
    entrar(dados["operador"])
    resp = cliente.post(f"/execucoes/{execucao.id}/cancelar", json={})
    assert resp.status_code == 409
