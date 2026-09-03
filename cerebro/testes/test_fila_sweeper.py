"""Sweeper periódico de execuções presas (fila.recuperar_execucoes_presas).

Complementa a recuperação de boot (fila._recuperar_orfas): quando um worker trava
SEM o processo reiniciar (chamada externa pendurada), a execução fica em
`em_andamento` para sempre. O sweeper a marca `falhou` — mas só se ficou sem
progresso além do teto. São TRÊS os sinais de progresso, e a execução só morre quando
os três estão velhos: o início da reivindicação, o último passo concluído e o SINAL DE
VIDA ao vivo (`atividade_em`, Onda 3 lacuna 24). Assim uma cadeia longa que vai
concluindo passos jamais é morta — e, agora, um passo que legitimamente demora dentro
de UM instrumento também não, desde que o instrumento publique que está trabalhando.

Os testes rodam contra o banco real (transação revertida): há execuções reais que
podem casar com a varredura, então afirmamos sobre o ESTADO da execução criada aqui
— não sobre contagens globais. Nada é persistido (rollback ao fim).
"""

from datetime import datetime, timedelta, timezone

import fila
from modelos import Automacao, Execucao, PassoExecucao


def _agora():
    return datetime.now(timezone.utc)


def _execucao(sessao, time_id, estado, iniciada_em, passos_fim=(), atividade_em=None):
    auto = Automacao(time_id=time_id, nome="Auto", tipo_gatilho="manual")
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(
        automacao_id=auto.id,
        estado=estado,
        entrada={"texto": "x"},
        iniciada_em=iniciada_em,
        atividade="Gerando o vídeo…" if atividade_em else None,
        atividade_em=atividade_em,
    )
    sessao.add(ex)
    sessao.flush()
    for i, fim in enumerate(passos_fim, start=1):
        sessao.add(
            PassoExecucao(
                execucao_id=ex.id,
                ordem=i,
                agente_id=None,
                saida={"texto": "ok"},
                estado="concluido",
                finalizado_em=fim,
            )
        )
    sessao.flush()
    return ex


def test_marca_falhou_execucao_travada_sem_passos(dados, sessao):
    ex = _execucao(
        sessao, dados["timeA"].id, "em_andamento", _agora() - timedelta(minutes=20)
    )
    fila.recuperar_execucoes_presas(sessao)
    sessao.refresh(ex)
    assert ex.estado == "falhou"
    assert ex.finalizada_em is not None
    assert "travada" in (ex.resultado or {}).get("erro", "").lower()


def test_nao_mexe_em_execucao_recente(dados, sessao):
    ex = _execucao(
        sessao, dados["timeA"].id, "em_andamento", _agora() - timedelta(minutes=2)
    )
    fila.recuperar_execucoes_presas(sessao)
    sessao.refresh(ex)
    assert ex.estado == "em_andamento"


def test_cadeia_longa_que_progride_nao_e_morta(dados, sessao):
    # Início há 60 min, MAS um passo concluiu há 2 min → heartbeat fresco → vive.
    ex = _execucao(
        sessao,
        dados["timeA"].id,
        "em_andamento",
        _agora() - timedelta(minutes=60),
        passos_fim=[_agora() - timedelta(minutes=30), _agora() - timedelta(minutes=2)],
    )
    fila.recuperar_execucoes_presas(sessao)
    sessao.refresh(ex)
    assert ex.estado == "em_andamento"


def test_travada_dentro_de_um_passo_e_recuperada(dados, sessao):
    # Início e último passo ambos há >15 min → travou no passo seguinte → falhou.
    ex = _execucao(
        sessao,
        dados["timeA"].id,
        "em_andamento",
        _agora() - timedelta(minutes=40),
        passos_fim=[_agora() - timedelta(minutes=20)],
    )
    fila.recuperar_execucoes_presas(sessao)
    sessao.refresh(ex)
    assert ex.estado == "falhou"


def test_retomada_de_portao_nao_e_morta(dados, sessao):
    # Regressão do bug real (execução f5de8d21): a execução ficou ~1h em
    # `aguardando_humano` (último passo há 57 min); ao ser aprovada, o worker a
    # reivindica de novo (iniciada_em = AGORA) e ela volta a `em_andamento`. O sweeper
    # NÃO pode matá-la no instante da retomada só porque o passo anterior à espera é
    # antigo — o iniciada_em fresco conta como progresso.
    ex = _execucao(
        sessao,
        dados["timeA"].id,
        "em_andamento",
        _agora() - timedelta(seconds=5),  # acabou de ser reivindicada (retomada)
        passos_fim=[_agora() - timedelta(minutes=57)],  # passo anterior à espera
    )
    fila.recuperar_execucoes_presas(sessao)
    sessao.refresh(ex)
    assert ex.estado == "em_andamento"


def test_outros_estados_intactos(dados, sessao):
    velho = _agora() - timedelta(minutes=60)
    casos = {
        "aguardando": _execucao(sessao, dados["timeA"].id, "aguardando", velho),
        "aguardando_humano": _execucao(
            sessao, dados["timeA"].id, "aguardando_humano", velho
        ),
        "concluida": _execucao(sessao, dados["timeA"].id, "concluida", velho),
    }
    fila.recuperar_execucoes_presas(sessao)
    for estado, ex in casos.items():
        sessao.refresh(ex)
        assert ex.estado == estado


# ── O sinal de vida ao vivo (Onda 3, lacuna 24) ───────────────────────────────


def test_instrumento_lento_que_da_sinal_de_vida_nao_e_morto(dados, sessao):
    """O caso que motivou a fatia: um passo que demora mais que o teto DENTRO de um
    instrumento (gerar vídeo). Início e último passo velhos, mas o instrumento acabou
    de publicar que está trabalhando → vive. Antes disto, `gerar_video` precisava
    encolher o próprio teto para ~10 min só para não ser morto aqui."""
    ex = _execucao(
        sessao,
        dados["timeA"].id,
        "em_andamento",
        _agora() - timedelta(minutes=40),
        passos_fim=[_agora() - timedelta(minutes=38)],
        atividade_em=_agora() - timedelta(seconds=20),
    )
    fila.recuperar_execucoes_presas(sessao)
    sessao.refresh(ex)
    assert ex.estado == "em_andamento"


def test_sinal_de_vida_VELHO_nao_salva_a_execucao(dados, sessao):
    """O instrumento parou de dar sinal há mais que o teto: aí travou de verdade. Sem
    esta metade, bastaria uma atividade publicada uma vez para a execução virar
    imortal — e o vigia deixaria de existir na prática."""
    ex = _execucao(
        sessao,
        dados["timeA"].id,
        "em_andamento",
        _agora() - timedelta(minutes=40),
        passos_fim=[_agora() - timedelta(minutes=38)],
        atividade_em=_agora() - timedelta(minutes=30),
    )
    fila.recuperar_execucoes_presas(sessao)
    sessao.refresh(ex)
    assert ex.estado == "falhou"


def test_execucao_sem_atividade_publicada_segue_a_regra_antiga(dados, sessao):
    """Sem sinal de vida nenhum, valem os outros dois sinais — exatamente como antes.
    Nada de execução imortal por ausência de dado."""
    ex = _execucao(
        sessao, dados["timeA"].id, "em_andamento", _agora() - timedelta(minutes=20)
    )
    fila.recuperar_execucoes_presas(sessao)
    sessao.refresh(ex)
    assert ex.estado == "falhou"
