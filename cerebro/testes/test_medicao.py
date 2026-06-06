"""Testes da medição de uso refinada por origem da chave (Fase 7.6).

Cobrem a agregação `por_origem` (cliente × consultoria × legado) e o endpoint
consolidado `/uso/resumo`, incluindo o isolamento entre organizações.
"""

from types import SimpleNamespace

import precos
from modelos import Automacao, Execucao, PassoExecucao


def _passo(uso):
    return SimpleNamespace(saida={"uso": uso})


def test_resumir_uso_separa_por_origem():
    passos = [
        _passo([{"modelo": "haiku", "tokens_entrada": 100, "tokens_saida": 50, "origem": "organizacao"}]),
        _passo([{"modelo": "haiku", "tokens_entrada": 200, "tokens_saida": 80, "origem": "consultoria"}]),
        _passo([{"modelo": "haiku", "tokens_entrada": 10, "tokens_saida": 5}]),  # sem origem
    ]
    r = precos.resumir_uso(passos)
    assert r["tokens_entrada"] == 310 and r["tokens_saida"] == 135
    assert r["por_origem"]["organizacao"]["tokens_entrada"] == 100
    assert r["por_origem"]["consultoria"]["tokens_saida"] == 80
    # Passo sem origem registrada cai em 'desconhecida' (compat. com passos antigos).
    assert r["por_origem"]["desconhecida"]["tokens_entrada"] == 10


def _semear_passo(sessao, time_id, origem, te, ts):
    auto = Automacao(time_id=time_id, nome="Auto", tipo_gatilho="manual")
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(automacao_id=auto.id, estado="concluida")
    sessao.add(ex)
    sessao.flush()
    sessao.add(
        PassoExecucao(
            execucao_id=ex.id,
            ordem=1,
            agente_id=None,
            saida={"uso": [{"modelo": "claude-haiku-4-5", "tokens_entrada": te, "tokens_saida": ts, "origem": origem}]},
            estado="concluido",
        )
    )
    sessao.flush()


def test_resumo_uso_endpoint_agrega_por_origem(cliente, entrar, dados, sessao):
    _semear_passo(sessao, dados["timeA"].id, "organizacao", 100, 40)
    _semear_passo(sessao, dados["timeA"].id, "consultoria", 200, 70)
    entrar(dados["admin"])
    r = cliente.get("/uso/resumo")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["tokens_entrada"] == 300
    assert corpo["por_origem"]["organizacao"]["tokens_saida"] == 40
    assert corpo["por_origem"]["consultoria"]["tokens_entrada"] == 200


def test_resumo_uso_isolado_entre_organizacoes(cliente, entrar, dados, sessao):
    _semear_passo(sessao, dados["timeA"].id, "organizacao", 100, 40)
    # 'estranho' é membro só da Org B; não enxerga o consumo da Org A.
    entrar(dados["estranho"])
    corpo = cliente.get("/uso/resumo").json()
    assert corpo["tokens_entrada"] == 0 and corpo["por_origem"] == {}
