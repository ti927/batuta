"""Testes do instrumento 'Gerar vídeo' (OpenAI/Sora).

Cobrem: registro + catálogo (enums modelo/tamanho/duração, dependências, validação
do trio); o ciclo assíncrono (cria job multipart → poll até `completed` → baixa MP4 →
salva em video/mp4); a imagem de referência virando `input_reference`; a política de
falha (sem chave, chave recusada, 5xx no create retentável, status failed, teto do
poll, download falho — idempotência: só a falha ANTES do id é retentável); e a medição
(custo por segundo, origem = openai). Sem rede: httpx, time.sleep, _baixar e
arquivos.salvar são dublês.
"""

from types import SimpleNamespace

import pytest

import instrumentos as encaixe
import medicao_instrumentos as med
import precos
from instrumentos.base import FalhaInstrumento
from instrumentos.gerar_video import ArgsVideo, ConfigVideo, GerarVideo


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

    def post(self, url, headers=None, files=None):
        self.calls.append(("POST", url, files))
        return self.roteador("POST", url, files=files)

    def get(self, url, headers=None, params=None):
        self.calls.append(("GET", url, params))
        return self.roteador("GET", url, params=params)


def _instalar(monkeypatch, roteador, salvo=None):
    cli = _Client(roteador)
    monkeypatch.setattr("instrumentos.gerar_video.httpx.Client", lambda *a, **k: cli)
    monkeypatch.setattr("instrumentos.gerar_video.time.sleep", lambda s: None)

    def _salvar(nome, conteudo, ct):
        if salvo is not None:
            salvo.update(nome=nome, conteudo=conteudo, ct=ct)
        return f"https://storage/{nome}"

    monkeypatch.setattr("instrumentos.gerar_video.arquivos.salvar", _salvar)
    return cli


CFG = dict(modelo="sora-2", tamanho="720x1280", duracao_s="8", chave_api="sk-x")


# ───────────────────────── registro / catálogo ─────────────────────────


def test_registrado():
    t = encaixe.obter_tipo("gerar_video")
    assert t is not None
    assert t.acao_irreversivel is False and t.categoria == "Conteúdo"
    assert t.chave_compartilhada == ("chave_api", "openai")
    props = t.Config.model_json_schema()["properties"]
    assert set(props["modelo"]["enum"]) == {"sora-2", "sora-2-pro"}
    assert props["duracao_s"]["enum"] == ["4", "8", "12"]
    assert "1920x1080" in props["tamanho"]["enum"]  # união (pro)


def test_dependencias_ui_filtra_por_modelo():
    dep = GerarVideo().dependencias_ui()
    assert dep["tamanho"]["controlado_por"] == "modelo"
    assert dep["tamanho"]["opcoes"]["sora-2"] == ["720x1280", "1280x720"]
    assert "1920x1080" in dep["tamanho"]["opcoes"]["sora-2-pro"]
    assert dep["duracao_s"]["opcoes"]["sora-2"] == ["4", "8", "12"]


def test_valida_trio_1080p_so_no_pro():
    ConfigVideo(modelo="sora-2-pro", tamanho="1920x1080", duracao_s="8")  # ok
    with pytest.raises(ValueError):
        ConfigVideo(modelo="sora-2", tamanho="1920x1080")  # 1080p não no base
    with pytest.raises(ValueError):
        ConfigVideo(modelo="sora-2", duracao_s="20")  # duração fora do enum


# ───────────────────────── ciclo assíncrono ─────────────────────────


def test_fluxo_completo(monkeypatch):
    polls = {"n": 0}

    def r(metodo, url, files=None, params=None):
        if metodo == "POST" and url.endswith("/videos"):
            return _Resp({"id": "vid_1", "status": "queued"})
        if metodo == "GET" and url.endswith("/content"):
            assert params == {"variant": "video"}
            return _Resp(content=b"MP4BYTES")
        if metodo == "GET":  # poll de status
            polls["n"] += 1
            estado = "completed" if polls["n"] >= 2 else "in_progress"
            return _Resp({"id": "vid_1", "status": estado, "progress": 50})
        return _Resp({}, 400)

    salvo: dict = {}
    cli = _instalar(monkeypatch, r, salvo)
    res = GerarVideo().executar(ConfigVideo(**CFG), ArgsVideo(prompt="um gato dançando"))

    assert res["ok"] and res["arquivo"].endswith(".mp4")
    assert res["url"] == "https://storage/" + res["arquivo"]
    assert res["modelo"] == "sora-2" and res["duracao_s"] == "8"
    assert salvo["ct"] == "video/mp4" and salvo["conteudo"] == b"MP4BYTES"
    # o create é multipart: campos de texto como (None, valor); sem input_reference
    create = next(f for m, u, f in cli.calls if m == "POST" and u.endswith("/videos"))
    assert create["model"] == (None, "sora-2")
    assert create["prompt"] == (None, "um gato dançando")
    assert create["size"] == (None, "720x1280")
    assert create["seconds"] == (None, "8")
    assert "input_reference" not in create


def test_imagem_referencia_vira_input_reference(monkeypatch):
    def r(metodo, url, files=None, params=None):
        if metodo == "POST" and url.endswith("/videos"):
            return _Resp({"id": "v2", "status": "queued"})
        if metodo == "GET" and url.endswith("/content"):
            return _Resp(content=b"MP4")
        if metodo == "GET":
            return _Resp({"id": "v2", "status": "completed"})
        return _Resp({}, 400)

    cli = _instalar(monkeypatch, r)
    monkeypatch.setattr(
        "instrumentos.gerar_video._baixar", lambda u: (b"IMGBYTES", "image/png")
    )
    GerarVideo().executar(
        ConfigVideo(**CFG),
        ArgsVideo(prompt="anima esta arte", imagem_referencia_url="http://x/a.png"),
    )
    create = next(f for m, u, f in cli.calls if m == "POST" and u.endswith("/videos"))
    assert create["input_reference"] == ("referencia", b"IMGBYTES", "image/png")


# ───────────────────────── falhas / idempotência ─────────────────────────


def test_sem_chave_nao_retentavel():
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(chave_api=""), ArgsVideo(prompt="x"))
    assert e.value.retentavel is False and "chave" in str(e.value).lower()


def test_chave_recusada_no_create(monkeypatch):
    _instalar(monkeypatch, lambda *a, **k: _Resp({"error": {"message": "no"}}, 401))
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(**CFG), ArgsVideo(prompt="x"))
    assert e.value.retentavel is False


def test_5xx_no_create_e_retentavel(monkeypatch):
    # Falha ANTES de existir o id → nada gerado → PODE retentar.
    _instalar(monkeypatch, lambda *a, **k: _Resp({"error": {"message": "down"}}, 503))
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(**CFG), ArgsVideo(prompt="x"))
    assert e.value.retentavel is True


def test_param_invalido_no_create_nao_retentavel(monkeypatch):
    def r(metodo, url, files=None, params=None):
        return _Resp({"error": {"message": "bad", "param": "size", "code": "invalid"}}, 400)

    _instalar(monkeypatch, r)
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(**CFG), ArgsVideo(prompt="x"))
    assert e.value.retentavel is False and "size" in str(e.value)


def test_status_failed_nao_retentavel(monkeypatch):
    def r(metodo, url, files=None, params=None):
        if metodo == "POST":
            return _Resp({"id": "v", "status": "queued"})
        return _Resp({"id": "v", "status": "failed", "error": {"message": "moderation"}})

    _instalar(monkeypatch, r)
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(**CFG), ArgsVideo(prompt="x"))
    assert e.value.retentavel is False and "moderation" in str(e.value)


def test_teto_do_poll_nao_retentavel(monkeypatch):
    def r(metodo, url, files=None, params=None):
        if metodo == "POST":
            return _Resp({"id": "v", "status": "queued"})
        return _Resp({"id": "v", "status": "in_progress"})  # nunca completa

    _instalar(monkeypatch, r)
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(**CFG), ArgsVideo(prompt="x"))
    assert e.value.retentavel is False and "tempo limite" in str(e.value)


def test_download_falho_nao_retentavel(monkeypatch):
    def r(metodo, url, files=None, params=None):
        if metodo == "POST":
            return _Resp({"id": "v", "status": "queued"})
        if metodo == "GET" and url.endswith("/content"):
            return _Resp({}, 500)
        return _Resp({"id": "v", "status": "completed"})

    _instalar(monkeypatch, r)
    with pytest.raises(FalhaInstrumento) as e:
        GerarVideo().executar(ConfigVideo(**CFG), ArgsVideo(prompt="x"))
    assert e.value.retentavel is False and "baixado" in str(e.value)


# ───────────────────────────── medição / preços ─────────────────────────────


def test_todo_modelo_do_catalogo_tem_preco():
    from instrumentos.gerar_video import CATALOGO_VIDEO

    for modelo in CATALOGO_VIDEO:
        assert modelo in precos.PRECOS_VIDEO_USD


def test_custo_por_video_por_classe_e_familia():
    assert precos.custo_por_video("sora-2", "720x1280", "8") == pytest.approx(0.80)
    assert precos.custo_por_video("sora-2-pro", "1920x1080", "12") == pytest.approx(8.40)
    assert precos.custo_por_video("sora-2-pro", "1280x720", "8") == pytest.approx(2.40)
    # família: sufixo desconhecido cai no 'pro' (prefixo), não no base
    assert precos.custo_por_video("sora-2-pro-x", "1920x1080", "4") == pytest.approx(2.80)
    # modelo totalmente desconhecido → padrão por segundo
    assert precos.custo_por_video("outro", "720x1280", "8") == pytest.approx(0.80)


def test_medicao_video_e_origem():
    assert "gerar_video" in med.TIPOS_PAGOS
    inst = SimpleNamespace(
        tipo="gerar_video",
        configuracao={"modelo": "sora-2-pro", "tamanho": "1920x1080", "duracao_s": "8"},
    )
    entrada, servico = med._entrada_e_servico(inst)
    assert entrada["modelo"] == "sora-2-pro" and entrada["segundos"] == 8
    assert entrada["custo_usd"] == pytest.approx(5.60)  # 0.70 × 8
    assert servico == "openai"  # da chave_compartilhada
