"""Onda 3, fatia 2 — tetos de tempo por passo e por execução (lacunas 22 e 23).

Cada instrumento já tinha o seu limite de rede (15 s no REST, 25 min no vídeo) — o
limite de UMA chamada. Faltava o teto do PASSO INTEIRO: um agente encadeia dez
chamadas, cada uma dentro do seu limite, e leva quarenta minutos assim mesmo. E
faltava o teto da EXECUÇÃO.

Os dois nascem desligados (0), pelo mesmo motivo do teto de custo: um teto que o
consultor não pediu interromperia trabalho legítimo e lento como se fosse defeito.

O ponto mais delicado, e o que mais testamos aqui: o teto da execução conta tempo de
TRABALHO (soma dos passos), nunca o relógio. Uma execução que esperou três dias por
uma aprovação não trabalhou três dias — contar a espera a mataria na retomada.
"""

from datetime import datetime, timedelta, timezone

import pytest

from mensageria.config import config_da_automacao
from modelos import Agente, Automacao, Execucao, PassoExecucao
from orquestracao import disparo, grafo, prazo
from orquestracao.cadeia import TetoDeTempoExcedido, executar_cadeia

NO_1, NO_2, NO_3 = "n1", "n2", "n3"


# ─────────────────────────── o prazo do passo ───────────────────────────


def test_sem_prazo_nada_expira():
    """Fora de um bloco `usar_prazo` (testes, chamadas soltas) nada pode expirar."""
    assert prazo.expirou() is False
    assert prazo.restante_s() is None


def test_prazo_zero_ou_nulo_significa_sem_teto():
    for valor in (0, None, 0.0):
        with prazo.usar_prazo(valor):
            assert prazo.expirou() is False
            assert prazo.restante_s() is None


def test_prazo_futuro_ainda_nao_expirou():
    with prazo.usar_prazo(10):
        assert prazo.expirou() is False
        assert 0 < prazo.restante_s() <= 600


def test_prazo_negativo_ja_nasce_expirado():
    """Um prazo já vencido barra a próxima ação na hora — é como o motor para um
    passo que estourou enquanto uma chamada longa terminava."""
    with prazo.usar_prazo(-1):
        assert prazo.expirou() is True
        assert prazo.restante_s() == 0.0


def test_o_prazo_nao_vaza_de_um_passo_para_o_seguinte():
    """O trabalhador é reutilizado entre execuções: um prazo vazado condenaria o passo
    seguinte de outra execução."""
    with prazo.usar_prazo(-1):
        assert prazo.expirou() is True
    assert prazo.expirou() is False


def test_agente_barra_a_acao_quando_o_prazo_acabou():
    """`_turno_interrompido` é o ponto ÚNICO que impede mais ações num turno — o prazo
    entra ali, junto da falha irreversível e da aprovação pendente."""
    from orquestracao.agente import _turno_interrompido

    assert _turno_interrompido([], None) is None
    with prazo.usar_prazo(-1):
        parado = _turno_interrompido([], None)
    assert parado is not None
    assert "tempo máximo deste passo" in parado
    assert "encerre agora" in parado  # diz o que fazer, não só o que houve


# ──────────────────────── o teto da execução ────────────────────────


@pytest.fixture
def cenario(sessao, dados, monkeypatch):
    ag = Agente(time_id=dados["timeA"].id, nome="Redator", papel="agente")
    sessao.add(ag)
    sessao.flush()
    cadeia = grafo.normalizar({
        "inicial": NO_1,
        "nos": [
            {"id": NO_1, "tipo": "agente", "ref": str(ag.id),
             "saidas": [{"rotulo": "ok", "destino": NO_2}]},
            {"id": NO_2, "tipo": "agente", "ref": str(ag.id),
             "saidas": [{"rotulo": "ok", "destino": NO_3}]},
            {"id": NO_3, "tipo": "agente", "ref": str(ag.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    })
    monkeypatch.setattr(
        "orquestracao.cadeia.executar_agente",
        lambda *a, **k: {
            "saida": "escrevi", "instrumentos_acionados": [], "erros_instrumentos": [],
            "uso": [], "mensagens_enviadas": {}, "ramos_escolhidos": ["ok"],
            "pausado": False, "anotacoes": {},
        },
    )
    return ag, cadeia


def test_sem_teto_a_execucao_roda_ate_o_fim(sessao, cenario):
    _, cadeia = cenario

    r = executar_cadeia(sessao, cadeia, "vai", teto_min_execucao=0)

    assert r["estado"] == "concluida"
    assert len(r["passos"]) == 3


def test_teto_de_tempo_da_execucao_para_o_fluxo(sessao, cenario):
    """`tempo_inicial_s` já vem estourado: o 1º passo fecha a conta."""
    _, cadeia = cenario

    with pytest.raises(TetoDeTempoExcedido) as e:
        executar_cadeia(
            sessao, cadeia, "vai", teto_min_execucao=10, tempo_inicial_s=11 * 60
        )

    texto = str(e.value)
    assert "10 min" in texto  # qual era o teto
    assert "Limites da execução" in texto  # onde mudar — nunca só o que houve


def test_o_ja_trabalhado_atravessa_a_espera(sessao, dados, monkeypatch):
    """É o análogo do `custo_inicial` para tempo: sem ele, o teto zeraria a cada
    retomada de aprovação. Aqui o já-trabalhado quase encosta no teto e UM passo curto
    fecha a conta — que é exatamente o que acontece na volta de uma aprovação."""
    import time as _time

    ag = Agente(time_id=dados["timeA"].id, nome="R", papel="agente")
    sessao.add(ag)
    sessao.flush()
    cadeia = grafo.normalizar({
        "inicial": NO_1,
        "nos": [
            {"id": NO_1, "tipo": "agente", "ref": str(ag.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    })

    def _demora(*a, **k):
        _time.sleep(0.15)  # o passo dura de verdade — é o que soma no teto
        return {
            "saida": "ok", "instrumentos_acionados": [], "erros_instrumentos": [],
            "uso": [], "mensagens_enviadas": {}, "ramos_escolhidos": ["ok"],
            "pausado": False, "anotacoes": {},
        }

    monkeypatch.setattr("orquestracao.cadeia.executar_agente", _demora)

    with pytest.raises(TetoDeTempoExcedido):
        executar_cadeia(
            sessao, cadeia, "vai", teto_min_execucao=5, tempo_inicial_s=5 * 60 - 0.05
        )


# ─────────── o tempo contado é o de TRABALHO, não o do relógio ───────────


def _execucao_com_passos(sessao, dados, duracoes_s, espera_dias=0):
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Post", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    nasceu = datetime.now(timezone.utc) - timedelta(days=espera_dias)
    ex = Execucao(automacao_id=auto.id, estado="em_andamento", entrada={"texto": "x"})
    sessao.add(ex)
    sessao.flush()
    for ordem, dur in enumerate(duracoes_s, 1):
        sessao.add(
            PassoExecucao(
                execucao_id=ex.id, ordem=ordem, no_id=NO_1, entrada={"texto": "e"},
                saida={"texto": "s"}, estado="concluido", tipo="agente",
                iniciado_em=nasceu, finalizado_em=nasceu + timedelta(seconds=dur),
            )
        )
    sessao.flush()
    return auto, ex


def test_tempo_trabalhado_soma_a_duracao_dos_passos(sessao, dados):
    _, ex = _execucao_com_passos(sessao, dados, [30, 90])

    assert disparo.tempo_ja_trabalhado_s(sessao, ex.id) == pytest.approx(120, abs=1)


def test_a_espera_por_uma_aprovacao_NAO_conta_como_trabalho(sessao, dados):
    """O ponto mais importante da fatia. A execução nasceu há 3 dias e só trabalhou 2
    minutos: se o teto contasse relógio, ela morreria no instante em que o humano
    aprovasse — punindo justamente o comportamento que o produto pede."""
    _, ex = _execucao_com_passos(sessao, dados, [60, 60], espera_dias=3)

    assert disparo.tempo_ja_trabalhado_s(sessao, ex.id) == pytest.approx(120, abs=1)


def test_passo_sem_inicio_ou_fim_nao_quebra_a_conta(sessao, dados):
    """Passo em andamento (sem `finalizado_em`) ou passo legado: ignorado, não erro."""
    _, ex = _execucao_com_passos(sessao, dados, [60])
    sessao.add(
        PassoExecucao(
            execucao_id=ex.id, ordem=9, no_id=NO_1, entrada={"texto": "e"},
            saida=None, estado="em_andamento", tipo="agente",
            iniciado_em=datetime.now(timezone.utc), finalizado_em=None,
        )
    )
    sessao.flush()

    assert disparo.tempo_ja_trabalhado_s(sessao, ex.id) == pytest.approx(60, abs=1)


# ──────────────────── a configuração do fluxo ────────────────────


def _auto(sessao, dados, configuracao):
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Post", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=False, configuracao=configuracao,
    )
    sessao.add(auto)
    sessao.flush()
    return auto


def test_os_dois_tetos_nascem_desligados(sessao, dados):
    assert disparo._tetos_de_tempo(_auto(sessao, dados, {})) == (0, 0)
    assert disparo._tetos_de_tempo(None) == (0, 0)
    cfg = config_da_automacao(None)
    assert cfg["teto_min_passo"] == 0 and cfg["teto_min_execucao"] == 0


def test_tetos_saem_dos_ajustes_do_fluxo(sessao, dados):
    auto = _auto(
        sessao, dados,
        {"perfil": "interno", "ajustes": {"teto_min_passo": 5, "teto_min_execucao": 45}},
    )

    assert disparo._tetos_de_tempo(auto) == (5, 45)


def test_valor_estragado_vira_sem_teto(sessao, dados):
    """Config ruim não pode derrubar a execução no meio do fluxo."""
    auto = _auto(sessao, dados, {"ajustes": {"teto_min_passo": "muito"}})

    assert disparo._tetos_de_tempo(auto) == (0, 0)


def test_os_campos_aparecem_no_painel_do_fluxo(cliente, entrar, dados):
    entrar(dados["operador"])

    r = cliente.get("/config/fluxo")

    chaves = [c["chave"] for g in r.json()["grupos"] for c in g["campos"]]
    assert "teto_min_passo" in chaves
    assert "teto_min_execucao" in chaves


def test_o_ajuste_do_NO_vence_o_do_fluxo(sessao, dados, monkeypatch):
    """Lacuna 22: o teto é POR NÓ, com o do fluxo como padrão. Provamos pelo prazo que
    o motor fixa: o nó pede 7 min, o fluxo diz 3 — vale o do nó."""
    vistos: list[float | None] = []
    ag = Agente(time_id=dados["timeA"].id, nome="R", papel="agente")
    sessao.add(ag)
    sessao.flush()
    cadeia = grafo.normalizar({
        "inicial": NO_1,
        "nos": [
            {"id": NO_1, "tipo": "agente", "ref": str(ag.id),
             "config": {"teto_min_passo": 7},
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    })

    def _espia(*a, **k):
        vistos.append(prazo.restante_s())
        return {
            "saida": "ok", "instrumentos_acionados": [], "erros_instrumentos": [],
            "uso": [], "mensagens_enviadas": {}, "ramos_escolhidos": ["ok"],
            "pausado": False, "anotacoes": {},
        }

    monkeypatch.setattr("orquestracao.cadeia.executar_agente", _espia)

    executar_cadeia(sessao, cadeia, "vai", teto_min_passo=3)

    assert vistos and 6 * 60 < vistos[0] <= 7 * 60  # o do nó, não os 3 min do fluxo
