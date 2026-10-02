"""Onda 3, fatia 1 — o batimento bate durante a espera (lacuna 24).

O vigia de execuções presas passou a respeitar o sinal de vida — mas isso só serve se
o sinal EXISTIR. Até aqui `atividade.registrar` era chamado UMA vez, antes de acionar
o instrumento, e nunca mais: um vídeo de 20 minutos publicava "gerando…" no minuto
zero e ficava mudo até o fim.

Aqui provamos que o instrumento que ESPERA em laço (vídeo do Google) publica
sinal de vida ao longo da espera, com o tempo decorrido — e que o teto deles deixou de
ser refém do vigia.
"""

import instrumentos.gerar_video as gv
from orquestracao import atividade


def test_a_frase_ganha_cronometro_conforme_a_espera():
    """Sem número, uma espera de 20 minutos é indistinguível de um travamento."""
    assert "minutos" in gv._frase_espera(0)  # começo: só a expectativa
    assert "60 s" in gv._frase_espera(6)  # 6 × 10 s
    assert "5 min" in gv._frase_espera(30)  # 30 × 10 s


def test_o_teto_deixou_de_ser_refem_do_vigia():
    """Eram 120 voltas (~10 min) escolhidas para "ficar abaixo do sweeper de 15 min" —
    um instrumento contorcendo o próprio limite por causa de um vigia cego. Com o vigia
    corrigido, o teto passa a ser o que a geração pede."""
    from fila import TETO_INATIVIDADE_EXEC_MIN

    minutos = gv.POLL_TENTATIVAS * gv.POLL_INTERVALO_S / 60
    assert minutos > TETO_INATIVIDADE_EXEC_MIN


def test_o_batimento_e_bem_mais_frequente_que_o_teto_do_vigia():
    """O intervalo entre batimentos tem de ser MUITO menor que o teto — senão o vigia
    mata a execução entre um batimento e outro."""
    from fila import TETO_INATIVIDADE_EXEC_MIN

    seg_entre_batimentos = gv.VOLTAS_POR_AVISO * gv.POLL_INTERVALO_S
    assert seg_entre_batimentos < TETO_INATIVIDADE_EXEC_MIN * 60 / 10


class _Operacao:
    def __init__(self, done):
        self.done = done


class _Cli:
    """Cliente falso do Google: a operação termina depois de `voltas` consultas."""

    def __init__(self, voltas):
        self.n, self.voltas = 0, voltas
        self.operations = self

    def get(self, operacao):
        self.n += 1
        return _Operacao(self.n >= self.voltas)


def test_veo_publica_sinal_de_vida_durante_a_espera(monkeypatch):
    publicadas: list[str] = []
    monkeypatch.setattr(gv.time, "sleep", lambda s: None)
    with atividade.usar_atividade(publicadas.append):
        gv.GerarVideo()._aguardar(_Cli(20), _Operacao(False))
    assert len(publicadas) >= 3  # publicou ao longo da espera, não só no começo
    assert all("vídeo" in f for f in publicadas)


def test_fora_de_uma_execucao_publicar_e_inofensivo(monkeypatch):
    """`registrar` é no-op sem escritor no contexto: testar/chamar o instrumento solto
    não pode quebrar por causa do feedback."""
    monkeypatch.setattr(gv.time, "sleep", lambda s: None)
    assert gv.GerarVideo()._aguardar(_Cli(1), _Operacao(False)).done
