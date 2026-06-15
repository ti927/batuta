"""Teste do acionamento isolado: uma FalhaInstrumento vira erro LEGÍVEL (502
com a mensagem real), em vez de um 500 cru — assim a tela "Testar" mostra o que
de fato houve (ex.: site não configurado, autenticação recusada)."""

import instrumentos as encaixe
from instrumentos.base import FalhaInstrumento
from modelos import Instrumento


def test_acionar_falha_de_instrumento_vira_502_com_mensagem(
    cliente, entrar, dados, sessao, monkeypatch
):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="rest", tipo="chamar_api_rest",
        configuracao={"url": "https://exemplo.invalido", "metodo": "GET"},
    )
    sessao.add(inst)
    sessao.flush()

    def explode(config, args):
        raise FalhaInstrumento("o sistema externo recusou (teste)")

    monkeypatch.setattr(encaixe.obter_tipo("chamar_api_rest"), "executar", explode)

    entrar(dados["operador"])
    r = cliente.post(f"/instrumentos/{inst.id}/acionar", json={"argumentos": {}})
    assert r.status_code == 502
    assert "recusou" in r.json()["detail"]
