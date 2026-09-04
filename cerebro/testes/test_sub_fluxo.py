"""Onda 3, fatia 4 — o nó "Chamar outra automação" (lacuna 21).

Uma automação só conseguia acionar outra pelo instrumento `agendar_automacao`, que é
fogo-e-esquece: dispara e nunca fica sabendo o que aconteceu. Um time de conteúdo não
conseguia chamar o time de revisão e USAR o parecer.

Aqui provamos o ciclo inteiro: a chamada (que cria uma execução-filha de verdade e
pausa o chamador), os freios (laço, profundidade, alvo que sumiu), o retorno (a ficha
que volta, o texto que vira a entrada do próximo passo, o passo reescrito) e as bordas
que costumam morder — filha que falha, filha apagada, chamador confundido com execução
travada, e os tetos de custo/tempo, que só valem alguma coisa se enxergarem o que o
sub-fluxo gastou.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

import fila
from modelos import Agente, Automacao, Execucao, PassoExecucao
from orquestracao import circuito, disparo, grafo, sub_fluxo
from orquestracao.cadeia import AVISO_TESTE_CHAMOU, executar_cadeia, validar_cadeia

NO_1, CHAMAR, NO_2, NO_ERRO = "n1", "ch", "n2", "nerr"


def _cadeia(ag_id: str, alvo: str | None, *, com_erro=False, sem_saida=False) -> dict:
    """O fluxo dos testes: agente → "Chamar outra automação" → agente."""
    saidas_chamar = [] if sem_saida else [{"rotulo": "depois", "destino": NO_2}]
    if com_erro:
        saidas_chamar = saidas_chamar + [
            {"rotulo": "se der erro", "destino": NO_ERRO, "tipo": "erro"}
        ]
    return grafo.normalizar({
        "inicial": NO_1,
        "nos": [
            {"id": NO_1, "tipo": "agente", "ref": ag_id,
             "saidas": [{"rotulo": "ok", "destino": CHAMAR}]},
            {"id": CHAMAR, "tipo": "chamar", "nome": "Chamar a Revisão",
             **({"chamar": {"automacao_id": alvo}} if alvo else {}),
             "saidas": saidas_chamar},
            {"id": NO_2, "tipo": "agente", "ref": ag_id,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": NO_ERRO, "tipo": "agente", "ref": ag_id,
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    })


def _automacao(sessao, dados, nome="Alvo") -> Automacao:
    a = Automacao(
        time_id=dados["timeA"].id, nome=nome, tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=True, configuracao={},
    )
    sessao.add(a)
    sessao.flush()
    return a


def _filhas(chamador_id):
    return select(Execucao).where(Execucao.chamada_por_execucao_id == chamador_id)


def _execucao(sessao, automacao, **kw) -> Execucao:
    ex = Execucao(
        automacao_id=automacao.id, entrada={"texto": "x"},
        estado=kw.pop("estado", "em_andamento"), **kw,
    )
    sessao.add(ex)
    sessao.flush()
    return ex


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


# ─────────────────────── o vocabulário do grafo ───────────────────────


def test_chamar_e_um_tipo_de_no_valido_e_estrutural():
    """Estrutural porque não roda IA por si: o trabalho é da automação chamada, que
    tem execução e rastro próprios."""
    assert "chamar" in grafo.TIPOS_VALIDOS
    assert "chamar" in grafo.TIPOS_ESTRUTURAIS


def test_automacao_chamada_le_o_alvo_do_no():
    assert grafo.automacao_chamada({"chamar": {"automacao_id": "abc"}}) == "abc"
    assert grafo.automacao_chamada({"chamar": {"automacao_id": "  abc  "}}) == "abc"


def test_alvo_ausente_ou_vazio_vale_None():
    """`None` faz o nó FALHAR ao ser alcançado — diferente do "Esperar" sem tempo, que
    segue adiante. Uma espera sem tempo é inofensiva; uma chamada sem alvo é trabalho
    que não foi feito."""
    assert grafo.automacao_chamada({}) is None
    assert grafo.automacao_chamada({"chamar": {}}) is None
    assert grafo.automacao_chamada({"chamar": {"automacao_id": "   "}}) is None
    assert grafo.automacao_chamada(None) is None


def test_validar_recusa_chamar_sem_alvo(sessao, dados, ag):
    """Barrar ao SALVAR é melhor que descobrir no meio de uma execução."""
    with pytest.raises(ValueError, match="não diz QUAL"):
        validar_cadeia(_cadeia(str(ag.id), None), {str(ag.id)})


def test_validar_aceita_chamar_com_alvo(sessao, dados, ag):
    alvo = _automacao(sessao, dados)
    validar_cadeia(_cadeia(str(ag.id), str(alvo.id)), {str(ag.id)})  # não levanta


# ─────────────────────────── a chamada ───────────────────────────


def test_o_fluxo_para_no_no_chamar_e_cria_a_filha(sessao, dados, ag):
    alvo = _automacao(sessao, dados, "Revisão")
    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))

    r = executar_cadeia(
        sessao, _cadeia(str(ag.id), str(alvo.id)), "vai", execucao_id=chamador.id
    )

    assert r["estado"] == "aguardando_sub_fluxo"
    assert [p["tipo"] for p in r["passos"]] == ["agente", "sub_fluxo"]
    assert "Revisão" in r["passos"][1]["saida"]
    filha = sessao.scalars(_filhas(chamador.id)).one()
    assert filha.automacao_id == alvo.id


def test_a_filha_nasce_com_a_ficha_do_chamador(sessao, dados, ag):
    """A razão de existir do nó: `agendar_automacao` perdia tudo isto."""
    alvo = _automacao(sessao, dados, "Revisão")
    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))

    executar_cadeia(
        sessao, _cadeia(str(ag.id), str(alvo.id)), "vai",
        ficha={"titulo": "Um título", "url": "http://x"}, execucao_id=chamador.id,
    )

    filha = sessao.scalars(_filhas(chamador.id)).one()
    assert filha.dados["titulo"] == "Um título"
    assert filha.dados["url"] == "http://x"
    assert (filha.entrada or {})["texto"] == "escrevi"  # o que o passo anterior produziu


def test_a_filha_carrega_a_linhagem_e_a_origem(sessao, dados, ag):
    alvo = _automacao(sessao, dados, "Revisão")
    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))

    executar_cadeia(
        sessao, _cadeia(str(ag.id), str(alvo.id)), "vai", execucao_id=chamador.id
    )

    filha = sessao.scalars(_filhas(chamador.id)).one()
    assert filha.chamada_por_execucao_id == chamador.id
    assert filha.origem == "sub_fluxo"


def test_a_pendencia_guarda_qual_filha_esperar_e_por_onde_seguir(sessao, dados, ag):
    alvo = _automacao(sessao, dados, "Revisão")
    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))

    r = executar_cadeia(
        sessao, _cadeia(str(ag.id), str(alvo.id)), "vai", execucao_id=chamador.id
    )

    filha = sessao.scalars(_filhas(chamador.id)).one()
    espera = r["pendentes"][0]
    assert espera["no"] == NO_2
    assert espera["aguarda_execucao"] == str(filha.id)
    assert espera["passo_ordem"] == 2  # o passo do `chamar`, para reescrever na volta


def test_sem_saida_desenhada_o_ramo_volta_para_o_fim(sessao, dados, ag):
    """Ainda assim ESPERA. Um `chamar` no fim do fluxo que não esperasse tornaria a
    palavra "síncrono" mentira — e o resultado da filha se perderia."""
    alvo = _automacao(sessao, dados, "Revisão")
    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))

    r = executar_cadeia(
        sessao, _cadeia(str(ag.id), str(alvo.id), sem_saida=True), "vai",
        execucao_id=chamador.id,
    )

    assert r["estado"] == "aguardando_sub_fluxo"
    assert r["pendentes"][0]["no"] == "fim"


# ─────────────────────────── os freios ───────────────────────────


def test_sem_alvo_o_no_falha_dizendo_o_que_fazer(sessao, dados, ag):
    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))

    with pytest.raises(ValueError, match="nenhuma foi escolhida"):
        executar_cadeia(
            sessao, _cadeia(str(ag.id), None), "vai", execucao_id=chamador.id
        )


def test_alvo_apagado_falha_com_recado_honesto(sessao, dados, ag):
    import uuid as _uuid

    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))

    with pytest.raises(ValueError, match="foi apagada"):
        executar_cadeia(
            sessao, _cadeia(str(ag.id), str(_uuid.uuid4())), "vai",
            execucao_id=chamador.id,
        )


def test_a_falha_da_chamada_segue_pela_saida_de_erro(sessao, dados, ag):
    """A falha vira um CAMINHO quando o desenho previu um — como em qualquer nó."""
    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))

    r = executar_cadeia(
        sessao, _cadeia(str(ag.id), None, com_erro=True), "vai",
        execucao_id=chamador.id,
    )

    assert r["estado"] == "concluida"
    assert [p["no_id"] for p in r["passos"]] == [NO_1, CHAMAR, NO_ERRO]
    assert r["passos"][1]["estado"] == "falhou"


def test_uma_automacao_nao_pode_chamar_a_si_mesma(sessao, dados):
    """A→A rodaria para sempre, gastando dinheiro de verdade a cada volta."""
    auto = _automacao(sessao, dados, "Conteúdo")
    ex = _execucao(sessao, auto)

    alvo, problema = sub_fluxo.pode_chamar(sessao, ex.id, str(auto.id))

    assert alvo is None
    assert "laço sem fim" in problema


def test_o_laco_indireto_tambem_e_barrado(sessao, dados):
    """A→B→A: só se enxerga subindo a linhagem, que é para isso que ela existe."""
    a = _automacao(sessao, dados, "A")
    b = _automacao(sessao, dados, "B")
    ex_a = _execucao(sessao, a)
    ex_b = _execucao(sessao, b, chamada_por_execucao_id=ex_a.id)

    _, problema = sub_fluxo.pode_chamar(sessao, ex_b.id, str(a.id))

    assert "laço sem fim" in problema


def test_a_corrente_tem_profundidade_maxima(sessao, dados):
    """Sem ciclo nenhum, A→B→C→D dá no mesmo prejuízo."""
    autos = [_automacao(sessao, dados, f"A{i}") for i in range(5)]
    anterior = None
    for a in autos[:grafo.MAX_PROFUNDIDADE_CHAMADA]:
        anterior = _execucao(sessao, a, chamada_por_execucao_id=(anterior.id if anterior else None))

    _, problema = sub_fluxo.pode_chamar(sessao, anterior.id, str(autos[-1].id))

    assert "automações encadeadas" in problema


def test_uma_corrente_curta_passa(sessao, dados):
    a, b = _automacao(sessao, dados, "A"), _automacao(sessao, dados, "B")
    ex = _execucao(sessao, a)

    alvo, problema = sub_fluxo.pode_chamar(sessao, ex.id, str(b.id))

    assert problema is None
    assert alvo.id == b.id


def test_fora_de_uma_execucao_de_verdade_a_chamada_falha(sessao, dados, ag):
    """Uma filha sem chamador rodaria sozinha, cobrada, sem ninguém esperando por ela."""
    alvo = _automacao(sessao, dados, "Revisão")

    with pytest.raises(ValueError, match="execução de verdade"):
        executar_cadeia(sessao, _cadeia(str(ag.id), str(alvo.id)), "vai")


def test_a_linhagem_sobe_a_corrente(sessao, dados):
    a, b, c = (_automacao(sessao, dados, n) for n in "ABC")
    ex_a = _execucao(sessao, a)
    ex_b = _execucao(sessao, b, chamada_por_execucao_id=ex_a.id)
    ex_c = _execucao(sessao, c, chamada_por_execucao_id=ex_b.id)

    assert sub_fluxo.linhagem(sessao, ex_c.id) == [c.id, b.id, a.id]


# ─────────────────────────── o retorno ───────────────────────────


def _pausado(sessao, dados, filha_id, ordem=2, destinos_erro=None, **kw):
    """Um chamador parado esperando a filha, como o motor o deixa."""
    chamador = _execucao(
        sessao, _automacao(sessao, dados, "Conteúdo"),
        estado=sub_fluxo.ESTADO_CHAMADOR,
        pendencias=[{
            "no": NO_2, "entradas": [], "aguarda_execucao": str(filha_id),
            "passo_ordem": ordem,
            **({"destinos_erro": destinos_erro} if destinos_erro else {}),
        }],
        **kw,
    )
    return chamador


def test_o_vigia_devolve_o_chamador_quando_a_filha_conclui(sessao, dados):
    filha = _execucao(
        sessao, _automacao(sessao, dados, "Revisão"),
        estado="concluida", resultado={"texto": "parecer: aprovado"},
    )
    chamador = _pausado(sessao, dados, filha.id)

    assert sub_fluxo.soltar_chamadores_concluidos(sessao) == 1

    sessao.refresh(chamador)
    assert chamador.estado == "aguardando"  # de volta à fila
    # O RESULTADO da filha vira a entrada do próximo passo — é o ponto da fatia.
    assert chamador.pendencias[0]["entradas"] == ["parecer: aprovado"]
    assert "aguarda_execucao" not in chamador.pendencias[0]


def test_o_vigia_nao_solta_enquanto_a_filha_roda(sessao, dados):
    filha = _execucao(sessao, _automacao(sessao, dados, "Revisão"), estado="em_andamento")
    chamador = _pausado(sessao, dados, filha.id)

    assert sub_fluxo.soltar_chamadores_concluidos(sessao) == 0

    sessao.refresh(chamador)
    assert chamador.estado == sub_fluxo.ESTADO_CHAMADOR


def test_a_filha_parada_numa_aprovacao_nao_solta_o_chamador(sessao, dados):
    """Cai de graça por reusar a máquina da pausa: o chamador simplesmente continua
    parado enquanto a filha espera uma pessoa."""
    filha = _execucao(
        sessao, _automacao(sessao, dados, "Revisão"), estado="aguardando_humano"
    )
    chamador = _pausado(sessao, dados, filha.id)

    assert sub_fluxo.soltar_chamadores_concluidos(sessao) == 0
    sessao.refresh(chamador)
    assert chamador.estado == sub_fluxo.ESTADO_CHAMADOR


def test_a_ficha_da_filha_volta_por_cima_da_do_chamador(sessao, dados):
    """Ela partiu de uma cópia da do chamador: toda diferença é trabalho dela."""
    filha = _execucao(
        sessao, _automacao(sessao, dados, "Revisão"), estado="concluida",
        resultado={"texto": "ok"}, dados={"titulo": "Título revisado", "nota": "8"},
    )
    chamador = _pausado(sessao, dados, filha.id)
    chamador.dados = {"titulo": "Título original", "url": "http://x"}

    sub_fluxo.soltar_chamadores_concluidos(sessao)

    sessao.refresh(chamador)
    assert chamador.dados["titulo"] == "Título revisado"  # a filha venceu
    assert chamador.dados["nota"] == "8"  # o que ela acrescentou
    assert chamador.dados["url"] == "http://x"  # o que ela não tocou sobrevive


def test_o_passo_e_reescrito_com_o_que_voltou(sessao, dados):
    """Sem isto a linha do tempo mentiria: o passo ficaria verde dizendo "chamou" ao
    lado de uma filha que falhou."""
    filha = _execucao(
        sessao, _automacao(sessao, dados, "Revisão"), estado="concluida",
        resultado={"texto": "parecer: aprovado"},
    )
    chamador = _pausado(sessao, dados, filha.id)
    agora = datetime.now(timezone.utc)
    sessao.add(PassoExecucao(
        execucao_id=chamador.id, ordem=2, no_id=CHAMAR, tipo="sub_fluxo",
        entrada={"texto": "x"},
        saida={
            "texto": "Chamou e está esperando",
            # O elo é gravado JÁ NA CHAMADA (é enquanto a filha roda que se quer
            # abrir o rastro dela); o retorno só carimba o desfecho no mesmo lugar.
            "sub_execucao": {"id": str(filha.id), "time_id": "t1", "nome": "Revisão"},
        },
        estado="concluido", iniciado_em=agora, finalizado_em=agora,
    ))
    sessao.flush()

    sub_fluxo.soltar_chamadores_concluidos(sessao)

    passo = sessao.scalars(
        select(PassoExecucao).where(PassoExecucao.execucao_id == chamador.id)
    ).one()
    assert passo.saida["texto"] == "parecer: aprovado"
    assert passo.saida["sub_execucao"]["id"] == str(filha.id)
    assert passo.saida["sub_execucao"]["estado"] == "concluida"
    assert passo.saida["sub_execucao"]["nome"] == "Revisão"  # o elo da chamada sobrevive
    assert passo.estado == "concluido"


# ────────────────────── quando a filha não termina bem ──────────────────────


def test_filha_que_falha_leva_o_chamador_pela_saida_de_erro(sessao, dados):
    filha = _execucao(
        sessao, _automacao(sessao, dados, "Revisão"), estado="falhou",
        resultado={"erro": "a API caiu"},
    )
    chamador = _pausado(sessao, dados, filha.id, destinos_erro=[NO_ERRO])

    sub_fluxo.soltar_chamadores_concluidos(sessao)

    sessao.refresh(chamador)
    assert chamador.estado == "aguardando"
    assert chamador.pendencias[0]["no"] == NO_ERRO
    assert "a API caiu" in chamador.pendencias[0]["entradas"][0]


def test_filha_que_falha_sem_saida_de_erro_derruba_o_chamador(sessao, dados):
    """Seguir adiante com um resultado que não existe entregaria trabalho pela metade
    narrado como inteiro."""
    filha = _execucao(
        sessao, _automacao(sessao, dados, "Revisão"), estado="falhou",
        resultado={"erro": "a API caiu"},
    )
    chamador = _pausado(sessao, dados, filha.id)

    sub_fluxo.soltar_chamadores_concluidos(sessao)

    sessao.refresh(chamador)
    assert chamador.estado == "falhou"
    assert "a API caiu" in chamador.resultado["erro"]
    assert chamador.finalizada_em is not None


def test_filha_cancelada_conta_como_nao_ter_terminado_bem(sessao, dados):
    filha = _execucao(
        sessao, _automacao(sessao, dados, "Revisão"), estado="cancelada",
    )
    chamador = _pausado(sessao, dados, filha.id)

    sub_fluxo.soltar_chamadores_concluidos(sessao)

    sessao.refresh(chamador)
    assert chamador.estado == "falhou"
    assert "cancelada" in chamador.resultado["erro"]


def test_filha_apagada_nao_deixa_o_chamador_preso_para_sempre(sessao, dados):
    """§12-A: nenhum estado "em andamento" pode ficar sem quem o varra."""
    import uuid as _uuid

    chamador = _pausado(sessao, dados, _uuid.uuid4())

    assert sub_fluxo.soltar_chamadores_concluidos(sessao) == 1

    sessao.refresh(chamador)
    assert chamador.estado == "falhou"
    assert "não existe mais" in chamador.resultado["erro"]


def test_chamador_sem_pendencia_de_espera_nao_fica_preso(sessao, dados):
    """Dado estragado — parado esperando, mas sem dizer o quê. Não deixar preso importa
    mais que entender como chegou lá: com um ramo legítimo sobrando, o fluxo segue por
    ele (perde-se o resultado do sub-fluxo, não a execução inteira)."""
    chamador = _execucao(
        sessao, _automacao(sessao, dados, "Conteúdo"),
        estado=sub_fluxo.ESTADO_CHAMADOR, pendencias=[{"no": NO_2, "entradas": ["a"]}],
    )

    assert sub_fluxo.soltar_chamadores_concluidos(sessao) == 1

    sessao.refresh(chamador)
    assert chamador.estado == "aguardando"
    assert chamador.pendencias == [{"no": NO_2, "entradas": ["a"]}]


def test_chamador_estragado_e_sem_nada_a_fazer_falha_visivelmente(sessao, dados):
    """Sem ramo nenhum sobrando não há como seguir — e ficar parado para sempre é o
    único desfecho proibido (§12-A)."""
    chamador = _execucao(
        sessao, _automacao(sessao, dados, "Conteúdo"),
        estado=sub_fluxo.ESTADO_CHAMADOR, pendencias=[],
    )

    assert sub_fluxo.soltar_chamadores_concluidos(sessao) == 1

    sessao.refresh(chamador)
    assert chamador.estado == "falhou"
    assert chamador.finalizada_em is not None


# ─────────────────────────── as bordas ───────────────────────────


def test_chamador_esperando_NAO_e_morto_pelo_vigia_de_presas(sessao, dados):
    """O vigia de presas só olha `em_andamento`. Um chamador que espera oito minutos
    por um sub-fluxo não pode ser confundido com uma execução travada."""
    filha = _execucao(sessao, _automacao(sessao, dados, "Revisão"))
    chamador = _pausado(sessao, dados, filha.id)
    chamador.iniciada_em = datetime.now(timezone.utc) - timedelta(hours=3)

    fila.recuperar_execucoes_presas(sessao)

    sessao.refresh(chamador)
    assert chamador.estado == sub_fluxo.ESTADO_CHAMADOR


def test_testar_um_passo_deixa_a_filha_rodar_de_verdade_e_para(sessao, dados, ag):
    """Fingir enganaria sobre o que o teste prova — mas um teste de um passo só não
    pode rodar dois."""
    filha = _execucao(
        sessao, _automacao(sessao, dados, "Revisão"), estado="concluida",
        resultado={"texto": "parecer"},
    )
    chamador = _pausado(sessao, dados, filha.id, teste_de_no=True)

    sub_fluxo.soltar_chamadores_concluidos(sessao)

    sessao.refresh(chamador)
    assert chamador.estado == "concluida"  # não voltou para a fila
    assert chamador.resultado["texto"] == "parecer"
    assert chamador.pendencias is None


def test_o_teste_avisa_que_o_fluxo_nao_seguiu(sessao, dados, ag):
    alvo = _automacao(sessao, dados, "Revisão")
    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))

    r = executar_cadeia(
        sessao, _cadeia(str(ag.id), str(alvo.id)), "vai",
        no_inicial=CHAMAR, so_um_passo=True, execucao_id=chamador.id,
    )

    assert AVISO_TESTE_CHAMOU in r["avisos"]


def test_os_outros_ramos_da_onda_sobrevivem_a_pausa(sessao, dados, ag):
    """Sem guardá-los, o trabalho dos outros ramos sumiria em silêncio."""
    alvo = _automacao(sessao, dados, "Revisão")
    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))
    cadeia = _cadeia(str(ag.id), str(alvo.id))

    r = executar_cadeia(
        sessao, cadeia, "vai",
        frente_inicial=[
            {"no": CHAMAR, "entradas": ["a"]},
            {"no": NO_2, "entradas": ["b"]},
        ],
        execucao_id=chamador.id,
    )

    assert [p["no"] for p in r["pendentes"]] == [NO_2, NO_2]


# ─────────────────── os tetos enxergam o sub-fluxo ───────────────────


def test_a_arvore_reune_a_execucao_e_as_filhas(sessao, dados):
    a, b, c = (_automacao(sessao, dados, n) for n in "ABC")
    pai = _execucao(sessao, a)
    f1 = _execucao(sessao, b, chamada_por_execucao_id=pai.id)
    neta = _execucao(sessao, c, chamada_por_execucao_id=f1.id)

    arvore = sub_fluxo.ids_da_arvore(sessao, pai.id)

    assert set(arvore) == {pai.id, f1.id, neta.id}


def test_o_teto_de_custo_conta_o_que_o_sub_fluxo_gastou(sessao, dados):
    """Senão bastaria pôr o trabalho caro num sub-fluxo para o teto virar enfeite."""
    pai = _execucao(sessao, _automacao(sessao, dados, "A"))
    filha = _execucao(
        sessao, _automacao(sessao, dados, "B"), chamada_por_execucao_id=pai.id
    )
    agora = datetime.now(timezone.utc)
    sessao.add(PassoExecucao(
        execucao_id=filha.id, ordem=1, entrada={"texto": "x"},
        saida={"texto": "y", "uso": [
            {"modelo": "claude-sonnet-4-5", "tokens_entrada": 1_000_000,
             "tokens_saida": 1_000_000},
        ]},
        estado="concluido", iniciado_em=agora, finalizado_em=agora,
    ))
    sessao.flush()

    assert disparo.custo_ja_gasto(sessao, pai.id) > 0


def test_o_teto_de_tempo_conta_o_trabalho_do_sub_fluxo(sessao, dados):
    pai = _execucao(sessao, _automacao(sessao, dados, "A"))
    filha = _execucao(
        sessao, _automacao(sessao, dados, "B"), chamada_por_execucao_id=pai.id
    )
    inicio = datetime.now(timezone.utc)
    sessao.add(PassoExecucao(
        execucao_id=filha.id, ordem=1, entrada={"texto": "x"}, saida={"texto": "y"},
        estado="concluido", iniciado_em=inicio,
        finalizado_em=inicio + timedelta(seconds=90),
    ))
    sessao.flush()

    assert disparo.tempo_ja_trabalhado_s(sessao, pai.id) == pytest.approx(90, abs=1)


def test_o_elo_para_a_filha_e_gravado_JA_na_chamada(sessao, dados, ag):
    """É ENQUANTO a filha roda que se quer abrir o rastro dela — esperar o retorno para
    só então gravar o elo deixaria a tela sem link justo na hora em que ele importa."""
    alvo = _automacao(sessao, dados, "Revisão")
    chamador = _execucao(sessao, _automacao(sessao, dados, "Conteúdo"))

    r = executar_cadeia(
        sessao, _cadeia(str(ag.id), str(alvo.id)), "vai", execucao_id=chamador.id
    )

    filha = sessao.scalars(_filhas(chamador.id)).one()
    elo = r["passos"][1]["sub_execucao"]
    assert elo["id"] == str(filha.id)
    assert elo["nome"] == "Revisão"
    # O TIME da automação chamada, que pode ser outro: o link da inspeção é por time, e
    # mandar o time errado carregaria os agentes errados na tela da filha.
    assert elo["time_id"] == str(alvo.time_id)


def test_as_duas_pausas_que_nao_pedem_nada_tem_frase_propria():
    """Sem elas o diagnóstico devolvia o nome cru do estado, e quem lesse
    "aguardando_tempo" concluiria que a execução travou."""
    from diagnostico_execucao import resumo_estado

    assert "volta sozinha" in resumo_estado("aguardando_tempo", None)
    assert "chamou" in resumo_estado("aguardando_sub_fluxo", None)


# ─────────────────── o disjuntor ignora o sub-fluxo ───────────────────


def test_falha_de_sub_fluxo_nao_desliga_a_automacao_chamada(sessao, dados):
    """O disjuntor conta o que falha rodando SOZINHO. Aqui quem rodou foi o chamador —
    e a falha já conta para ele. Sem isso, uma automação usada como sub-fluxo por um
    chamador quebrado se desligaria por culpa alheia."""
    assert sub_fluxo.ORIGEM not in circuito.ORIGENS_SOZINHA
    alvo = _automacao(sessao, dados, "Revisão")
    for _ in range(circuito.FALHAS_PARA_DESLIGAR + 1):
        _execucao(
            sessao, alvo, estado="falhou", origem=sub_fluxo.ORIGEM,
            resultado={"erro": "x"},
        )

    assert circuito.falhas_seguidas(sessao, alvo) == 0
