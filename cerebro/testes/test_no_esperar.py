"""Onda 3, fatia 3 — o nó "Esperar" (lacuna 20).

Não havia espera temporal no fluxo. Para "publique isto daqui a dois dias" só existia
agendar OUTRA execução — que começa do zero, sem a ficha e sem o ponto do grafo: todo
o contexto apurado até ali morria no caminho.

O motor já sabia pausar e retomar mantendo tudo (é o que a aprovação faz). Faltava um
motivo de pausa que não fosse gente: o relógio. Aqui provamos que a espera guarda o
ponto do fluxo e a ficha, que o vigia devolve a execução à fila no tempo certo, e as
bordas que costumam morder — espera não configurada, ramos que ainda não rodaram, e a
numeração dos passos ao voltar.
"""

from datetime import datetime, timedelta, timezone

import pytest

import fila
from modelos import Agente, Automacao, Execucao, PassoExecucao
from orquestracao import disparo, grafo
from orquestracao.cadeia import _texto_da_espera, executar_cadeia

NO_1, ESPERA, NO_2 = "n1", "esp", "n2"


def _cadeia(ag_id: str, espera: dict | None) -> dict:
    return grafo.normalizar({
        "inicial": NO_1,
        "nos": [
            {"id": NO_1, "tipo": "agente", "ref": ag_id,
             "saidas": [{"rotulo": "ok", "destino": ESPERA}]},
            {"id": ESPERA, "tipo": "esperar", "nome": "Esperar",
             **({"espera": espera} if espera else {}),
             "saidas": [{"rotulo": "depois", "destino": NO_2}]},
            {"id": NO_2, "tipo": "agente", "ref": ag_id,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    })


@pytest.fixture
def ag(sessao, dados, monkeypatch):
    a = Agente(time_id=dados["timeA"].id, nome="Redator", papel="agente")
    sessao.add(a)
    sessao.flush()
    monkeypatch.setattr(
        "orquestracao.cadeia.executar_agente",
        lambda *x, **k: {
            "saida": "escrevi", "instrumentos_acionados": [], "erros_instrumentos": [],
            "uso": [], "mensagens_enviadas": {}, "ramos_escolhidos": ["ok", "depois"],
            "pausado": False, "anotacoes": {},
        },
    )
    return a


# ─────────────────────── a duração em português ───────────────────────


def test_a_duracao_e_escrita_na_maior_unidade_que_couber():
    """"2 dias" se lê; "2880 minutos", não."""
    assert _texto_da_espera(1) == "1 minuto"
    assert _texto_da_espera(45) == "45 minutos"
    assert _texto_da_espera(60) == "1 hora"
    assert _texto_da_espera(180) == "3 horas"
    assert _texto_da_espera(60 * 24) == "1 dia"
    assert _texto_da_espera(60 * 24 * 2) == "2 dias"
    assert _texto_da_espera(90) == "90 minutos"  # não cabe em hora inteira


def test_minutos_de_espera_converte_a_unidade():
    assert grafo.minutos_de_espera({"espera": {"quanto": 30, "unidade": "minutos"}}) == 30
    assert grafo.minutos_de_espera({"espera": {"quanto": 2, "unidade": "horas"}}) == 120
    assert grafo.minutos_de_espera({"espera": {"quanto": 3, "unidade": "dias"}}) == 4320


def test_espera_ausente_ou_estragada_vale_zero():
    """Zero = "não espera", e o motor segue adiante avisando — nunca para para sempre."""
    assert grafo.minutos_de_espera({}) == 0
    assert grafo.minutos_de_espera({"espera": {}}) == 0
    assert grafo.minutos_de_espera({"espera": {"quanto": "muito"}}) == 0
    assert grafo.minutos_de_espera(None) == 0


def test_a_espera_tem_teto_de_sanidade():
    """Um zero a mais não pode virar uma execução parada até o ano que vem."""
    assert grafo.minutos_de_espera(
        {"espera": {"quanto": 9999, "unidade": "dias"}}
    ) == grafo.MAX_ESPERA_MIN


# ─────────────────────────── a pausa ───────────────────────────


def test_o_fluxo_para_no_no_esperar(sessao, ag):
    cadeia = _cadeia(str(ag.id), {"quanto": 2, "unidade": "horas"})

    r = executar_cadeia(sessao, cadeia, "vai")

    assert r["estado"] == "aguardando_tempo"
    assert r["retomar_em"] > datetime.now(timezone.utc) + timedelta(minutes=115)
    # o passo do agente + o passo da espera
    assert [p["tipo"] for p in r["passos"]] == ["agente", "espera_tempo"]
    assert "2 horas" in r["passos"][1]["saida"]


def test_a_pendencia_guarda_por_onde_continuar(sessao, ag):
    """É o que faz a execução voltar EXATAMENTE daqui, e não do começo."""
    cadeia = _cadeia(str(ag.id), {"quanto": 5, "unidade": "minutos"})

    r = executar_cadeia(sessao, cadeia, "vai")

    assert [p["no"] for p in r["pendentes"]] == [NO_2]
    assert r["pendentes"][0]["entradas"] == ["escrevi"]  # o que o passo anterior produziu


def test_a_ficha_atravessa_a_espera(sessao, ag):
    """A razão de existir do nó: agendar outra execução perdia isto."""
    cadeia = _cadeia(str(ag.id), {"quanto": 5, "unidade": "minutos"})

    r = executar_cadeia(sessao, cadeia, "vai", ficha={"titulo": "Um título"})

    assert r["ficha"]["titulo"] == "Um título"


def test_espera_sem_tempo_configurado_segue_adiante_avisando(sessao, ag):
    """Parar para sempre por causa de um campo vazio seria o pior desfecho. Segue —
    mas nunca em silêncio (§12-A)."""
    cadeia = _cadeia(str(ag.id), None)

    r = executar_cadeia(sessao, cadeia, "vai")

    assert r["estado"] == "concluida"
    assert any("não diz quanto tempo esperar" in a for a in r["avisos"])


def test_retomar_da_pendencia_continua_de_onde_parou(sessao, ag):
    """A volta: `frente_inicial` com o que a pausa guardou roda só o que faltava."""
    cadeia = _cadeia(str(ag.id), {"quanto": 5, "unidade": "minutos"})
    pausada = executar_cadeia(sessao, cadeia, "vai")

    r = executar_cadeia(
        sessao, cadeia, "",
        frente_inicial=pausada["pendentes"],
        ficha=pausada["ficha"],
        ordem_inicial=pausada["ordem"],
    )

    assert r["estado"] == "concluida"
    assert [p["no_id"] for p in r["passos"]] == [NO_2]  # só o que faltava
    assert r["passos"][0]["ordem"] > pausada["ordem"] if "ordem" in r["passos"][0] else True


# ────────────────────── o vigia que solta ──────────────────────


def _execucao_esperando(sessao, dados, retomar_em, pendencias=None):
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Post", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=True, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(
        automacao_id=auto.id, estado="aguardando_tempo", entrada={"texto": "x"},
        retomar_em=retomar_em, pendencias=pendencias or [{"no": NO_2, "entradas": ["a"]}],
    )
    sessao.add(ex)
    sessao.flush()
    return ex


def test_o_vigia_devolve_a_execucao_a_fila_quando_o_tempo_vence(sessao, dados):
    ex = _execucao_esperando(
        sessao, dados, datetime.now(timezone.utc) - timedelta(minutes=1)
    )

    fila.soltar_esperas_vencidas(sessao)

    sessao.refresh(ex)
    assert ex.estado == "aguardando"  # de volta à fila
    assert ex.retomar_em is None
    assert ex.pendencias  # preservadas: é por onde ela continua


def test_o_vigia_nao_solta_antes_da_hora(sessao, dados):
    ex = _execucao_esperando(
        sessao, dados, datetime.now(timezone.utc) + timedelta(hours=2)
    )

    fila.soltar_esperas_vencidas(sessao)

    sessao.refresh(ex)
    assert ex.estado == "aguardando_tempo"


def test_execucao_esperando_NAO_e_morta_pelo_vigia_de_presas(sessao, dados):
    """O vigia de presas só olha `em_andamento`. Uma execução que espera dois dias não
    pode ser confundida com uma travada — senão a fatia inteira se anula."""
    ex = _execucao_esperando(
        sessao, dados, datetime.now(timezone.utc) + timedelta(days=2)
    )
    ex.iniciada_em = datetime.now(timezone.utc) - timedelta(hours=5)
    sessao.flush()

    fila.recuperar_execucoes_presas(sessao)

    sessao.refresh(ex)
    assert ex.estado == "aguardando_tempo"


# ────────────────── a numeração dos passos ao voltar ──────────────────


def test_a_numeracao_continua_de_onde_parou(sessao, dados, ag):
    """Sem isto a linha do tempo teria dois "passo 1" e o teto de passos por execução
    perderia o sentido."""
    auto = Automacao(
        time_id=dados["timeA"].id, nome="P", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=True, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(automacao_id=auto.id, estado="aguardando", entrada={"texto": "x"})
    sessao.add(ex)
    sessao.flush()
    for ordem in (1, 2, 3):
        sessao.add(
            PassoExecucao(
                execucao_id=ex.id, ordem=ordem, no_id=NO_1, entrada={"texto": "e"},
                saida={"texto": "s"}, estado="concluido", tipo="agente",
            )
        )
    sessao.flush()

    assert disparo._ordem_ja_gravada(sessao, ex.id) == 3


def test_execucao_nova_comeca_do_zero(sessao, dados):
    auto = Automacao(
        time_id=dados["timeA"].id, nome="P", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=True, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(automacao_id=auto.id, estado="aguardando", entrada={"texto": "x"})
    sessao.add(ex)
    sessao.flush()

    assert disparo._ordem_ja_gravada(sessao, ex.id) == 0


# ─────────────────────── o tipo de nó ───────────────────────


def test_esperar_e_um_tipo_valido_e_estrutural():
    """Estrutural porque não produz trabalho — o que também faz "testar este passo" e
    "rodar de novo daqui" o recusarem, com razão."""
    assert "esperar" in grafo.TIPOS_VALIDOS
    assert "esperar" in grafo.TIPOS_ESTRUTURAIS
