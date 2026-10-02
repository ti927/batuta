"""Testes do instrumento 'Gerar vídeo' (Google/Veo 3.1, desde 2026-10-02 — a Sora da
OpenAI foi desligada em 24/09/2026).

Cobrem: catálogo (enums, dependências, validação, 1080p/4K só com 8 s, cura da config
antiga de Sora); o ciclo assíncrono (cria operação → consulta até `done` → baixa MP4 →
salva em video/mp4); a imagem de partida; a política de falha (sem chave, conta sem
crédito antes de criar, recusa por segurança, teto da espera, download falho —
idempotência: depois de criada a operação nada é retentável); e a medição (custo por
segundo, origem = google). Sem rede: o cliente do Google, time.sleep, _baixar e
arquivos.salvar são dublês.
"""

from types import SimpleNamespace as NS

import pytest
from google.genai import errors

import instrumentos as encaixe
import instrumentos.gerar_video as gv
import medicao_instrumentos as med
import precos
from instrumentos import google_servidor as goo
from instrumentos.base import FalhaInstrumento
from instrumentos.gerar_video import ArgsVideo, ConfigVideo, GerarVideo
from orquestracao.llm import usar_chaves


class _Cliente:
    def __init__(self, *, criar=None, voltas=2, final=None, baixar=(b"mp4-bytes",)):
        self.pedidos: list[dict] = []
        self._criar, self._voltas, self._final = criar, voltas, final
        self._baixar = list(baixar)
        self.n = 0
        cli = self

        class Modelos:
            def generate_videos(self, **kw):
                cli.pedidos.append(kw)
                if isinstance(cli._criar, Exception):
                    raise cli._criar
                return NS(done=False, error=None, response=None)

        class Operacoes:
            def get(self, operacao):
                cli.n += 1
                if cli.n < cli._voltas:
                    return NS(done=False, error=None, response=None)
                return cli._final or NS(done=True, error=None, response=NS(
                    generated_videos=[NS(video=NS(uri="files/v1"))], rai_media_filtered_reasons=[],
                ))

        class Arquivos:
            def download(self, file):
                item = cli._baixar.pop(0) if cli._baixar else b""
                if isinstance(item, Exception):
                    raise item
                return item

        self.models, self.operations, self.files = Modelos(), Operacoes(), Arquivos()


@pytest.fixture
def ambiente(monkeypatch):
    salvos: list = []
    monkeypatch.setattr(gv.time, "sleep", lambda s: None)
    monkeypatch.setattr(gv.arquivos, "salvar",
                        lambda nome, c, t: salvos.append((nome, c, t)) or f"https://armazem/{nome}")

    def com(cli):
        monkeypatch.setattr(goo, "cliente", lambda timeout=None: cli)
        return cli

    return NS(salvos=salvos, com=com)


# ── catálogo e validação ─────────────────────────────────────────────────────────


def test_registrado_como_instrumento_do_google_e_criavel():
    tipo = encaixe.obter_tipo("gerar_video")
    assert tipo.provedores_ia == ("google",)
    assert tipo.substituido_por is None  # voltou ao ar
    assert encaixe.motivo_para_nao_criar("gerar_video") is None


def test_padrao_e_o_mais_barato_vertical():
    c = ConfigVideo()
    assert (c.modelo, c.tamanho, c.resolucao, c.duracao_s) == (
        "veo-3.1-lite-generate-preview", "9:16", "720p", "8")


def test_1080p_e_4k_so_com_8_segundos():
    with pytest.raises(ValueError, match="8 segundos"):
        ConfigVideo(resolucao="1080p", duracao_s="4")
    ConfigVideo(resolucao="1080p", duracao_s="8")


def test_4k_nao_existe_no_lite():
    with pytest.raises(ValueError, match="resolução"):
        ConfigVideo(resolucao="4k")
    ConfigVideo(modelo="veo-3.1-fast-generate-preview", resolucao="4k")


def test_config_antiga_de_sora_vira_veo():
    vertical = ConfigVideo(modelo="sora-2", tamanho="720x1280", duracao_s="12", chave_api="sk")
    assert (vertical.modelo, vertical.tamanho, vertical.duracao_s) == (
        gv.MODELO_PADRAO, "9:16", "8")
    assert ConfigVideo(modelo="sora-2-pro", tamanho="1920x1080").tamanho == "16:9"


def test_dependencias_ui_casam_com_o_catalogo():
    deps = GerarVideo().dependencias_ui()
    for m, spec in gv.CATALOGO_VIDEO.items():
        assert deps["resolucao"]["opcoes"][m] == list(spec["resolucoes"])
        assert deps["duracao_s"]["opcoes"][m] == list(spec["duracoes"])


def test_todo_modelo_e_resolucao_tem_preco():
    for m, spec in gv.CATALOGO_VIDEO.items():
        for r in spec["resolucoes"]:
            assert r in precos.PRECOS_VIDEO_USD[m], f"falta preço {m}/{r}"


# ── o ciclo ──────────────────────────────────────────────────────────────────────


def test_gera_espera_baixa_e_guarda(ambiente):
    cli = ambiente.com(_Cliente(voltas=3))
    cfg = ConfigVideo(modelo="veo-3.1-fast-generate-preview", tamanho="16:9", resolucao="1080p")
    with usar_chaves({"google": "g"}):
        r = GerarVideo().executar(cfg, ArgsVideo(prompt="um café sendo servido, som ambiente"))
    pedido = cli.pedidos[0]
    assert pedido["model"] == "veo-3.1-fast-generate-preview" and pedido["image"] is None
    assert (pedido["config"].aspect_ratio, pedido["config"].resolution,
            pedido["config"].duration_seconds) == ("16:9", "1080p", 8)
    assert ambiente.salvos[0][1] == b"mp4-bytes" and ambiente.salvos[0][2] == "video/mp4"
    assert r["ok"] and r["url"].endswith(".mp4") and r["resolucao"] == "1080p"


def test_imagem_de_partida_vai_junto(ambiente, monkeypatch):
    cli = ambiente.com(_Cliente())
    monkeypatch.setattr(gv, "_baixar", lambda url: (b"png-bytes", "image/png"))
    with usar_chaves({"google": "g"}):
        GerarVideo().executar(ConfigVideo(), ArgsVideo(prompt="anime", imagem_referencia_url="https://x/a.png"))
    imagem = cli.pedidos[0]["image"]
    assert imagem.image_bytes == b"png-bytes" and imagem.mime_type == "image/png"


def test_sem_chave_do_google(ambiente):
    with usar_chaves({"openai": "o"}), pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(), ArgsVideo(prompt="x"))
    assert e.value.codigo == "ia.sem_chave"


def test_sem_credito_antes_de_criar_nao_gera_nada(ambiente):
    erro = errors.ClientError(402, {"error": {"code": 402, "message": "Your prepayment credits are depleted."}})
    ambiente.com(_Cliente(criar=erro))
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(), ArgsVideo(prompt="x"))
    assert e.value.codigo == "ia.sem_credito"


def test_google_fora_ao_criar_e_retentavel(ambiente):
    ambiente.com(_Cliente(criar=errors.ServerError(503, {"error": {"code": 503, "message": "overloaded"}})))
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(), ArgsVideo(prompt="x"))
    assert e.value.retentavel  # nada foi criado ainda


def test_recusa_por_seguranca_explica_e_nao_retenta(ambiente):
    final = NS(done=True, error=None, response=NS(
        generated_videos=[], rai_media_filtered_reasons=["Contém uma pessoa pública."]))
    ambiente.com(_Cliente(final=final))
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(), ArgsVideo(prompt="x"))
    assert e.value.codigo == "ia.recusa" and not e.value.retentavel
    assert "pessoa pública" in str(e.value)


def test_operacao_com_erro_nao_retenta(ambiente):
    ambiente.com(_Cliente(final=NS(done=True, error={"message": "quota"}, response=None)))
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(), ArgsVideo(prompt="x"))
    assert not e.value.retentavel and "quota" in str(e.value)


def test_teto_da_espera_nao_retenta(ambiente, monkeypatch):
    monkeypatch.setattr(gv, "POLL_TENTATIVAS", 3)
    ambiente.com(_Cliente(voltas=99))
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(), ArgsVideo(prompt="x"))
    assert not e.value.retentavel and "tempo limite" in str(e.value)


def test_download_falho_tenta_de_novo_por_dentro_e_nao_retenta(ambiente):
    ambiente.com(_Cliente(baixar=(RuntimeError("rede"), b"mp4-ok")))
    with usar_chaves({"google": "g"}):
        r = GerarVideo().executar(ConfigVideo(), ArgsVideo(prompt="x"))
    assert r["ok"]
    ambiente.com(_Cliente(baixar=(RuntimeError("rede"),) * 3))
    with usar_chaves({"google": "g"}), pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(), ArgsVideo(prompt="x"))
    assert not e.value.retentavel and "não pôde ser baixado" in str(e.value)


# ── medição ──────────────────────────────────────────────────────────────────────


def test_custo_por_segundo_e_origem_google():
    inst = NS(tipo="gerar_video", configuracao={
        "modelo": "veo-3.1-fast-generate-preview", "resolucao": "1080p", "duracao_s": "8"})
    entrada, servico = med._entrada_e_servico(inst)
    assert entrada["segundos"] == 8 and entrada["custo_usd"] == pytest.approx(0.96)
    assert servico == "google"
    assert precos.custo_por_video("veo-3.1-lite-generate-preview", "720p", "4") == pytest.approx(0.20)
