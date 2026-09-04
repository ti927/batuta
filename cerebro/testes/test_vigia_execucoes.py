"""O vigia dos vigias — a página de status enxerga os jobs que soltam execução parada.

As Ondas 3 e 4 criaram o padrão "a execução pausa e um vigia a solta". Se o vigia
morre, ela fica parada para sempre — e, até aqui, em SILÊNCIO: `agendador.esta_saudavel`
só devolve `_scheduler.running`, ou seja, diz que o relógio gira, não que os jobs
disparam. Um job que passasse a levantar exceção a cada volta deixaria o `/saude`
respondendo `agendador: true` e a página `/status` toda verde.

Aqui provamos o batimento, a tolerância por job, o que a sonda diz em cada situação e
— o que mais importa — que os três jobs de verdade carimbam o ponto.
"""

from datetime import datetime, timedelta, timezone

import pytest

import fila
import saude_elos
import vigias
from orquestracao import sub_fluxo


@pytest.fixture(autouse=True)
def batimentos_limpos():
    """`BATIMENTOS` é global do processo: sem isolar, um teste contamina o outro."""
    antes = dict(vigias.BATIMENTOS)
    vigias.BATIMENTOS.clear()
    yield
    vigias.BATIMENTOS.clear()
    vigias.BATIMENTOS.update(antes)


def _bateu_ha(nome: str, segundos: float) -> None:
    vigias.BATIMENTOS[nome] = datetime.now(timezone.utc) - timedelta(seconds=segundos)


# ─────────────────────────── o batimento ───────────────────────────


def test_bater_registra_a_hora():
    assert vigias.atraso_s("esperas") is None  # nunca rodou
    vigias.bateu("esperas")
    assert vigias.atraso_s("esperas") < 2


def test_no_boot_nenhum_vigia_rodou_ainda():
    assert set(vigias.nunca_rodaram()) == set(vigias.VIGIAS)
    vigias.bateu("esperas")
    assert "esperas" not in vigias.nunca_rodaram()


def test_a_tolerancia_e_folgada_de_proposito():
    """Alarme que dispara à toa é alarme que ninguém lê — e aí a página perde a única
    serventia que tem. Um vigia de 30 s atrasado 3 min ainda está saudável."""
    _bateu_ha("esperas", 180)
    assert vigias.quebrados() == []


def test_vigia_parado_alem_da_tolerancia_e_quebrado():
    _bateu_ha("esperas", 600)
    quebrados = dict(vigias.quebrados())
    assert "esperas" in quebrados


def test_cada_vigia_tem_a_SUA_tolerancia():
    """O de execuções travadas roda a cada 2 min; cobrar dele o mesmo dos de 30 s
    inventaria defeito."""
    _bateu_ha("esperas", 400)  # de 30 s: quebrado (teto 300)
    _bateu_ha("presas", 400)  # de 120 s: ainda em dia (teto 600)
    assert [n for n, _ in vigias.quebrados()] == ["esperas"]


def test_o_mais_atrasado_vem_primeiro():
    _bateu_ha("esperas", 400)
    _bateu_ha("sub_fluxos", 900)
    assert [n for n, _ in vigias.quebrados()] == ["sub_fluxos", "esperas"]


def test_a_frase_diz_a_CONSEQUENCIA_nao_o_nome_do_job():
    """Quem lê a página de status precisa saber o que parou de funcionar."""
    frase = vigias.frase_do_atraso("sub_fluxos", 400)
    assert "Chamar outra automação" in frase
    assert "6 min" in frase and "a cada 30 s" in frase


# ─────────────────────────── a sonda ───────────────────────────


def test_no_boot_a_sonda_diz_DEGRADADO_e_nao_quebrado():
    """Um app que acabou de subir não tem atraso nenhum a explicar."""
    with pytest.raises(saude_elos.EloDegradado, match="primeira volta"):
        saude_elos._sonda_vigias_execucao()


def test_com_todos_em_dia_a_sonda_passa():
    for nome in vigias.VIGIAS:
        vigias.bateu(nome)
    assert "em dia" in saude_elos._sonda_vigias_execucao()


def test_a_sonda_falha_NOMEANDO_quem_parou():
    for nome in vigias.VIGIAS:
        vigias.bateu(nome)
    _bateu_ha("sub_fluxos", 900)

    with pytest.raises(RuntimeError) as e:
        saude_elos._sonda_vigias_execucao()

    assert "Chamar outra automação" in str(e.value)


def test_o_elo_aparece_na_pagina_de_status():
    elos = {e.id: e for e in saude_elos.montar_elos()}
    assert "vigia_execucoes" in elos
    # Grupo `interno` — é onde a página agrupa o que não é rede nem borda.
    assert elos["vigia_execucoes"].grupo == "interno"
    assert elos["vigia_execucoes"].reconectar is not None  # tem botão de religar


# ──────────────── os jobs de verdade carimbam o ponto ────────────────
# O teste que realmente protege: sem ele, a sonda estaria certa e ninguém batendo.


def test_o_job_das_esperas_carimba(sessao):
    fila.soltar_esperas_job()
    assert vigias.atraso_s("esperas") is not None


def test_o_job_dos_sub_fluxos_carimba(sessao):
    sub_fluxo.soltar_sub_fluxos_job()
    assert vigias.atraso_s("sub_fluxos") is not None


def test_o_job_das_presas_carimba(sessao):
    fila.varrer_presas_job()
    assert vigias.atraso_s("presas") is not None
