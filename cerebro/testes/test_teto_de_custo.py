"""Onda 4, fatia 4 — teto de custo por execução (lacuna 30).

Até aqui o custo era só MEDIDO: a aba Uso mostrava o estrago depois de feito. Um
fluxo que entra em laço caro, ou um "Para cada item" com uma lista maior do que se
esperava, gastava até o fim sem nada para segurá-lo.

Agora o fluxo pode ter um teto em dólares. Ele é OPCIONAL (zero = sem teto, o
padrão), vale por EXECUÇÃO — somando as retomadas, senão uma execução que para duas
vezes numa aprovação gastaria o teto três vezes — e, ao estourar, para com um recado
que diz quanto gastou, qual era o teto e o que fazer.
"""

import pytest

from mensageria.config import config_da_automacao
from modelos import Agente, Automacao, Execucao, PassoExecucao
from orquestracao import disparo, grafo
from orquestracao.cadeia import TetoDeCustoExcedido, executar_cadeia

NO_1, NO_2, NO_3 = "n1", "n2", "n3"

# 1000 tokens de saída de um sonnet ($15/Mtok) = US$ 0,015 por passo.
USO_PASSO = [{"modelo": "claude-sonnet-4-6", "tokens_entrada": 0, "tokens_saida": 1000}]


def _cadeia_de_tres(ag_id: str) -> dict:
    return grafo.normalizar({
        "inicial": NO_1,
        "nos": [
            {"id": NO_1, "tipo": "agente", "ref": ag_id,
             "saidas": [{"rotulo": "ok", "destino": NO_2}]},
            {"id": NO_2, "tipo": "agente", "ref": ag_id,
             "saidas": [{"rotulo": "ok", "destino": NO_3}]},
            {"id": NO_3, "tipo": "agente", "ref": ag_id,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    })


@pytest.fixture
def cenario(sessao, dados, monkeypatch):
    """Três agentes em fila, cada passo custando US$ 0,015."""
    ag = Agente(time_id=dados["timeA"].id, nome="Redator", papel="agente")
    sessao.add(ag)
    sessao.flush()

    def _fake(*a, **k):
        return {
            "saida": "escrevi", "instrumentos_acionados": [], "erros_instrumentos": [],
            "uso": list(USO_PASSO), "mensagens_enviadas": {}, "ramos_escolhidos": ["ok"],
            "pausado": False, "anotacoes": {},
        }

    monkeypatch.setattr("orquestracao.cadeia.executar_agente", _fake)
    return ag, _cadeia_de_tres(str(ag.id))


def test_sem_teto_a_execucao_roda_ate_o_fim(sessao, cenario):
    """Zero = sem teto, e é o padrão: o caminho tem de ficar idêntico ao de sempre."""
    _, cadeia = cenario

    r = executar_cadeia(sessao, cadeia, "vai", teto_usd=0.0)

    assert r["estado"] == "concluida"
    assert len(r["passos"]) == 3


def test_teto_alto_nao_atrapalha(sessao, cenario):
    _, cadeia = cenario

    r = executar_cadeia(sessao, cadeia, "vai", teto_usd=10.0)

    assert r["estado"] == "concluida"
    assert len(r["passos"]) == 3


def test_teto_baixo_para_a_execucao_no_meio(sessao, cenario):
    """US$ 0,02 dá para UM passo (0,015) e estoura no segundo (0,030)."""
    _, cadeia = cenario

    with pytest.raises(TetoDeCustoExcedido) as e:
        executar_cadeia(sessao, cadeia, "vai", teto_usd=0.02)

    texto = str(e.value)
    assert "0.03" in texto and "0.02" in texto  # quanto gastou e qual era o teto
    assert "Limites da execução" in texto  # onde mudar — nunca só o que houve
    # O aviso pelo canal corta o motivo em 300 caracteres: a mensagem tem de caber
    # INTEIRA, senão o "o que fazer" (que vem no fim) é justamente o que se perde.
    from mensageria.aviso import MAX_ERRO

    assert len(texto) <= MAX_ERRO


def test_o_passo_que_estourou_fica_no_rastro(sessao, cenario):
    """O trabalho já foi pago; escondê-lo faria a conta não fechar na aba Uso."""
    _, cadeia = cenario
    registrados: list[dict] = []

    with pytest.raises(TetoDeCustoExcedido):
        executar_cadeia(
            sessao, cadeia, "vai", teto_usd=0.02,
            registrar_passo=lambda p, o: registrados.append(p),
        )

    assert len(registrados) == 2  # o que coube e o que estourou
    assert all(p["estado"] == "concluido" for p in registrados)


def test_o_ja_gasto_conta_o_teto_atravessa_a_espera(sessao, cenario):
    """`custo_inicial` é o análogo do `ordem_inicial` para dinheiro: sem ele, o teto
    zeraria a cada retomada de aprovação."""
    _, cadeia = cenario

    with pytest.raises(TetoDeCustoExcedido):
        # Já gastou 0,019 antes da aprovação; o teto de 0,02 estoura no 1º passo.
        executar_cadeia(sessao, cadeia, "vai", teto_usd=0.02, custo_inicial=0.019)


def test_custo_ja_gasto_soma_os_passos_gravados(sessao, dados):
    """A fonte de preço é a MESMA da aba Uso (`precos.custo_de_entrada`)."""
    ag = Agente(time_id=dados["timeA"].id, nome="Redator", papel="agente")
    sessao.add(ag)
    sessao.flush()
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Post", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(automacao_id=auto.id, estado="em_andamento", entrada={"texto": "x"})
    sessao.add(ex)
    sessao.flush()
    for ordem in (1, 2):
        sessao.add(
            PassoExecucao(
                execucao_id=ex.id, ordem=ordem, agente_id=ag.id, no_id=NO_1,
                entrada={"texto": "e"}, saida={"texto": "s", "uso": list(USO_PASSO)},
                estado="concluido", tipo="agente",
            )
        )
    sessao.flush()

    assert disparo.custo_ja_gasto(sessao, ex.id) == pytest.approx(0.03, abs=1e-6)


def test_execucao_sem_passo_nao_custou_nada(sessao, dados):
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Post", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(automacao_id=auto.id, estado="aguardando", entrada={"texto": "x"})
    sessao.add(ex)
    sessao.flush()

    assert disparo.custo_ja_gasto(sessao, ex.id) == 0.0


# ─────────────────────── o teto vem da config do fluxo ───────────────────────


def _auto(sessao, dados, configuracao):
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Post", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=False, configuracao=configuracao,
    )
    sessao.add(auto)
    sessao.flush()
    return auto


def test_teto_padrao_e_desligado(sessao, dados):
    """A fatia é OPCIONAL: ligar um teto sem o consultor pedir interromperia fluxos
    legitimamente caros (gerar vídeo, for-each grande) como se fosse defeito."""
    assert disparo._teto_de_custo(_auto(sessao, dados, {})) == 0.0
    assert disparo._teto_de_custo(None) == 0.0
    assert config_da_automacao(None)["teto_usd_execucao"] == 0.0


def test_teto_sai_dos_ajustes_do_fluxo(sessao, dados):
    auto = _auto(sessao, dados, {"perfil": "interno", "ajustes": {"teto_usd_execucao": 2.5}})

    assert disparo._teto_de_custo(auto) == 2.5


def test_valor_estragado_na_config_nao_derruba_a_execucao(sessao, dados):
    """Config ruim vira "sem teto", não uma exceção no meio do fluxo."""
    auto = _auto(sessao, dados, {"ajustes": {"teto_usd_execucao": "muito"}})

    assert disparo._teto_de_custo(auto) == 0.0


def test_o_campo_aparece_no_painel_do_fluxo(cliente, entrar, dados):
    """O painel é montado a partir do backend (fonte única), então o campo novo chega
    à tela sem mudança no front."""
    entrar(dados["operador"])

    r = cliente.get("/config/fluxo")

    assert r.status_code == 200
    chaves = [
        c["chave"] for g in r.json()["grupos"] for c in g["campos"]
    ]
    assert "teto_usd_execucao" in chaves
    assert r.json()["padrao_global"]["teto_usd_execucao"] == 0.0
