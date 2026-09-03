"""Onda 3, fatia 1 — o batimento bate durante a espera (lacuna 24).

O vigia de execuções presas passou a respeitar o sinal de vida — mas isso só serve se
o sinal EXISTIR. Até aqui `atividade.registrar` era chamado UMA vez, antes de acionar
o instrumento, e nunca mais: um vídeo de 20 minutos publicava "gerando…" no minuto
zero e ficava mudo até o fim.

Aqui provamos que os dois instrumentos que ESPERAM em laço (Sora e fal.ai) publicam
sinal de vida ao longo da espera, com o tempo decorrido — e que o teto deles deixou de
ser refém do vigia.
"""

import instrumentos.gerar_video as gv
import instrumentos.gerar_video_fal as gvf
from orquestracao import atividade


def test_a_frase_ganha_cronometro_conforme_a_espera():
    """Sem número, uma espera de 20 minutos é indistinguível de um travamento."""
    for mod in (gv, gvf):
        assert "minutos" in mod._frase_espera(0)  # começo: só a expectativa
        assert "60 s" in mod._frase_espera(12)  # 12 × 5 s
        assert "5 min" in mod._frase_espera(60)  # 60 × 5 s


def test_o_teto_dos_dois_instrumentos_deixou_de_ser_refem_do_vigia():
    """Eram 120 voltas (~10 min) escolhidas para "ficar abaixo do sweeper de 15 min" —
    um instrumento contorcendo o próprio limite por causa de um vigia cego. Com o vigia
    corrigido, o teto passa a ser o que a geração pede."""
    from fila import TETO_INATIVIDADE_EXEC_MIN

    for mod in (gv, gvf):
        minutos = mod.POLL_TENTATIVAS * mod.POLL_INTERVALO_S / 60
        assert minutos > TETO_INATIVIDADE_EXEC_MIN


def test_o_batimento_e_bem_mais_frequente_que_o_teto_do_vigia():
    """O intervalo entre batimentos tem de ser MUITO menor que o teto — senão o vigia
    mata a execução entre um batimento e outro."""
    from fila import TETO_INATIVIDADE_EXEC_MIN

    for mod in (gv, gvf):
        seg_entre_batimentos = mod.VOLTAS_POR_AVISO * mod.POLL_INTERVALO_S
        assert seg_entre_batimentos < TETO_INATIVIDADE_EXEC_MIN * 60 / 10


def _capturar(monkeypatch, modulo, respostas):
    """Roda `_aguardar` com um cliente falso e devolve as frases publicadas."""
    publicadas: list[str] = []
    monkeypatch.setattr(modulo.time, "sleep", lambda s: None)

    class _Resp:
        def __init__(self, corpo):
            self.is_success = True
            self.status_code = 200
            self._corpo = corpo

        def json(self):
            return self._corpo

    class _Cli:
        def __init__(self):
            self.n = 0

        def get(self, *a, **k):
            r = _Resp(respostas[min(self.n, len(respostas) - 1)])
            self.n += 1
            return r

    with atividade.usar_atividade(publicadas.append):
        if modulo is gv:
            modulo.GerarVideo()._aguardar(_Cli(), {}, "vid_1")
        else:
            modulo.GerarVideoFal()._aguardar(_Cli(), {}, "http://x")
    return publicadas


def test_sora_publica_sinal_de_vida_durante_a_espera(monkeypatch):
    em_curso = {"status": "in_progress"}
    pronto = {"status": "completed"}
    respostas = [em_curso] * 20 + [pronto]

    publicadas = _capturar(monkeypatch, gv, respostas)

    assert len(publicadas) >= 3  # publicou ao longo da espera, não só no começo
    assert all("vídeo" in f for f in publicadas)


def test_fal_publica_sinal_de_vida_durante_a_espera(monkeypatch):
    respostas = [{"status": "IN_PROGRESS"}] * 20 + [{"status": "COMPLETED"}]

    publicadas = _capturar(monkeypatch, gvf, respostas)

    assert len(publicadas) >= 3
    assert all("vídeo" in f for f in publicadas)


def test_fora_de_uma_execucao_publicar_e_inofensivo(monkeypatch):
    """`registrar` é no-op sem escritor no contexto: testar/chamar o instrumento solto
    não pode quebrar por causa do feedback."""
    monkeypatch.setattr(gv.time, "sleep", lambda s: None)

    class _R:
        is_success = True
        status_code = 200

        def json(self):
            return {"status": "completed"}

    class _C:
        def get(self, *a, **k):
            return _R()

    assert gv.GerarVideo()._aguardar(_C(), {}, "vid_1") == "completed"
