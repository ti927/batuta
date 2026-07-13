"""Testes do instrumento 'Gerar vídeo a partir de foto' (fal.ai: Kling/Luma/Hailuo).

Cobrem: registro + catálogo (modelos, durações por modelo, dependências, validação);
o ciclo da FILA (submit → poll status até COMPLETED → response → baixa mp4 → salva
video/mp4); e a política de falha (sem chave; chave recusada; 5xx no submit retentável;
job que falha no response não-retentável; idempotência pós-request_id). Medição por
vídeo, origem `fal`. Sem rede: httpx, time.sleep e arquivos.salvar são dublês.
"""

from types import SimpleNamespace

import pytest

import instrumentos as encaixe
import medicao_instrumentos as med
from instrumentos.base import FalhaInstrumento
from instrumentos.gerar_video_fal import ArgsVideoFal, ConfigVideoFal, GerarVideoFal


class _Resp:
    def __init__(self, body=None, status=200, content=b""):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self._b = body
        self.content = content

    def json(self):
        return self._b

    @property
    def text(self):
        return str(self._b)


class _Client:
    def __init__(self, roteador):
        self.roteador = roteador
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, headers=None, json=None):
        self.calls.append(("POST", url, json))
        return self.roteador("POST", url, json=json)

    def get(self, url, headers=None, params=None, follow_redirects=False):
        self.calls.append(("GET", url, None))
        return self.roteador("GET", url)


def _instalar(monkeypatch, roteador, salvo=None):
    cli = _Client(roteador)
    monkeypatch.setattr("instrumentos.gerar_video_fal.httpx.Client", lambda *a, **k: cli)
    monkeypatch.setattr("instrumentos.gerar_video_fal.time.sleep", lambda s: None)

    def _salvar(nome, conteudo, ct):
        if salvo is not None:
            salvo.update(nome=nome, conteudo=conteudo, ct=ct)
        return f"https://storage/{nome}"

    monkeypatch.setattr("instrumentos.gerar_video_fal.arquivos.salvar", _salvar)
    return cli


CFG = dict(modelo="kling", duracao="5", chave_api="fal-x")


# ───────────────────────── registro / catálogo ─────────────────────────


def test_registrado():
    t = encaixe.obter_tipo("gerar_video_fal")
    assert t is not None
    assert t.acao_irreversivel is False and t.categoria == "Conteúdo"
    assert t.chave_compartilhada == ("chave_api", "fal")
    props = t.Config.model_json_schema()["properties"]
    assert set(props["modelo"]["enum"]) == {"kling", "luma", "hailuo"}
    assert "9s" in props["duracao"]["enum"] and "5" in props["duracao"]["enum"]


def test_dependencias_e_validacao():
    dep = GerarVideoFal().dependencias_ui()
    assert dep["duracao"]["opcoes"]["kling"] == ["5", "10"]
    assert dep["duracao"]["opcoes"]["luma"] == ["5s", "9s"]
    ConfigVideoFal(modelo="hailuo", duracao="6")  # ok
    with pytest.raises(ValueError):
        ConfigVideoFal(modelo="kling", duracao="6")  # 6 não vale p/ kling


# ───────────────────────── ciclo da fila ─────────────────────────


def test_fluxo_completo(monkeypatch):
    polls = {"n": 0}

    def r(metodo, url, json=None):
        if metodo == "POST":
            return _Resp({"request_id": "req1", "status_url": "S", "response_url": "R"})
        if url == "S":
            polls["n"] += 1
            return _Resp({"status": "COMPLETED" if polls["n"] >= 2 else "IN_PROGRESS"})
        if url == "R":
            return _Resp({"video": {"url": "https://v.fal/out.mp4"}})
        if url == "https://v.fal/out.mp4":
            return _Resp(content=b"MP4")
        return _Resp({}, 400)

    salvo: dict = {}
    cli = _instalar(monkeypatch, r, salvo)
    res = GerarVideoFal().executar(
        ConfigVideoFal(**CFG), ArgsVideoFal(imagem_url="http://x/a.jpg", prompt="anima")
    )
    assert res["ok"] and res["arquivo"].endswith(".mp4")
    assert res["url"] == "https://storage/" + res["arquivo"]
    assert res["modelo"] == "kling" and res["duracao"] == "5"
    assert salvo["ct"] == "video/mp4" and salvo["conteudo"] == b"MP4"
    submit = next(j for m, u, j in cli.calls if m == "POST")
    # Kling: manda o freio (negative_prompt + cfg_scale) e NÃO tem quadro final.
    assert submit["prompt"] == "anima" and submit["image_url"] == "http://x/a.jpg"
    assert submit["duration"] == "5" and submit["cfg_scale"] == 0.5
    assert "distorted text" in submit["negative_prompt"]
    assert "end_image_url" not in submit
    post_url = next(u for m, u, j in cli.calls if m == "POST")
    assert post_url.endswith("fal-ai/kling-video/v2.1/standard/image-to-video")


# ───────────────────────── freios por modelo (corpo do job) ─────────────────────────


def _corpo_submetido(monkeypatch, config, imagem="http://x/a.jpg"):
    """Roda o instrumento com a fila dublada e devolve o corpo do POST de submit."""

    def r(metodo, url, json=None):
        if metodo == "POST":
            return _Resp({"request_id": "q", "status_url": "S", "response_url": "R"})
        if url == "S":
            return _Resp({"status": "COMPLETED"})
        if url == "R":
            return _Resp({"video": {"url": "https://v/out.mp4"}})
        return _Resp(content=b"MP4")

    cli = _instalar(monkeypatch, r)
    GerarVideoFal().executar(config, ArgsVideoFal(imagem_url=imagem, prompt="anima"))
    return next(j for m, u, j in cli.calls if m == "POST")


def test_luma_trava_composicao_e_proporcao(monkeypatch):
    corpo = _corpo_submetido(
        monkeypatch, ConfigVideoFal(modelo="luma", duracao="5s", chave_api="k")
    )
    # Trava = quadro final igual à imagem inicial; proporção 9:16 por padrão.
    assert corpo["end_image_url"] == "http://x/a.jpg"
    assert corpo["aspect_ratio"] == "9:16"
    # campos de outro modelo não vazam
    assert "negative_prompt" not in corpo and "cfg_scale" not in corpo


def test_hailuo_trava_desliga_otimizador(monkeypatch):
    corpo = _corpo_submetido(
        monkeypatch, ConfigVideoFal(modelo="hailuo", duracao="6", chave_api="k")
    )
    assert corpo["end_image_url"] == "http://x/a.jpg"
    assert corpo["prompt_optimizer"] is False  # travado → não injeta movimento


def test_travar_desligado_nao_manda_quadro_final(monkeypatch):
    corpo = _corpo_submetido(
        monkeypatch,
        ConfigVideoFal(modelo="hailuo", duracao="6", chave_api="k", travar_composicao=False),
    )
    assert "end_image_url" not in corpo
    assert corpo["prompt_optimizer"] is True  # sem travar → otimizador ligado (padrão)


def test_kling_prompt_negativo_customizado(monkeypatch):
    corpo = _corpo_submetido(
        monkeypatch,
        ConfigVideoFal(modelo="kling", duracao="5", chave_api="k", prompt_negativo="sem gente"),
    )
    assert corpo["negative_prompt"] == "sem gente"


# ───────────────────────── falhas / idempotência ─────────────────────────


def test_sem_chave():
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideoFal().executar(
            ConfigVideoFal(chave_api=""), ArgsVideoFal(imagem_url="u", prompt="p")
        )
    assert e.value.retentavel is False


def test_chave_recusada(monkeypatch):
    _instalar(monkeypatch, lambda *a, **k: _Resp({"detail": "no"}, 401))
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideoFal().executar(ConfigVideoFal(**CFG), ArgsVideoFal(imagem_url="u", prompt="p"))
    assert e.value.retentavel is False


def test_5xx_no_submit_retentavel(monkeypatch):
    _instalar(monkeypatch, lambda *a, **k: _Resp({"detail": "down"}, 503))
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideoFal().executar(ConfigVideoFal(**CFG), ArgsVideoFal(imagem_url="u", prompt="p"))
    assert e.value.retentavel is True


def test_job_falha_no_response_nao_retentavel(monkeypatch):
    def r(metodo, url, json=None):
        if metodo == "POST":
            return _Resp({"request_id": "q"})
        if url.endswith("/status"):
            return _Resp({"status": "COMPLETED"})
        if url.endswith("/response"):
            return _Resp({"detail": "flagged by moderation"}, 422)
        return _Resp({}, 400)

    _instalar(monkeypatch, r)
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideoFal().executar(ConfigVideoFal(**CFG), ArgsVideoFal(imagem_url="u", prompt="p"))
    assert e.value.retentavel is False and "moderation" in str(e.value)


# ───────────────────────── medição ─────────────────────────


def test_medicao_fal_e_origem():
    assert "gerar_video_fal" in med.TIPOS_PAGOS
    inst = SimpleNamespace(tipo="gerar_video_fal", configuracao={"modelo": "kling"})
    entrada, servico = med._entrada_e_servico(inst)
    assert entrada["modelo"] == "kling" and entrada["videos"] == 1
    assert entrada["custo_usd"] == pytest.approx(0.35)
    assert servico == "fal"  # da chave_compartilhada
