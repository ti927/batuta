"""Testes do instrumento Publicar no Instagram (Fase 2).

Cobrem o fluxo de 3 passos (contêiner → espera FINISHED → publica), o carrossel
(filhos + pai), os erros (não conectado, sem URL, carrossel curto, status ERROR) e
a regra de idempotência (toda falha é NÃO-retentável, para a orquestração nunca
republicar por reexecução). Sem rede: o httpx e o time.sleep são interceptados.
"""

import pytest

from instrumentos.base import FalhaInstrumento
from instrumentos.publicar_instagram import (
    ArgsPublicarInstagram,
    ConfigPublicarInstagram,
    PublicarInstagram,
)

CFG = ConfigPublicarInstagram(ig_user_id="178", token="TOK")


class _Resp:
    def __init__(self, body, status=200):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self._b = body

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

    def post(self, url, data=None):
        self.calls.append(("POST", url, data))
        return self.roteador("POST", url, data)

    def get(self, url, params=None):
        self.calls.append(("GET", url, params))
        return self.roteador("GET", url, params)


def _instalar(monkeypatch, roteador):
    cli = _Client(roteador)
    monkeypatch.setattr(
        "instrumentos.publicar_instagram.httpx.Client", lambda *a, **k: cli
    )
    monkeypatch.setattr("instrumentos.publicar_instagram.time.sleep", lambda s: None)
    return cli


def _router_ok(metodo, url, dados):
    if metodo == "POST" and url.endswith("/media_publish"):
        return _Resp({"id": "MEDIA1"})
    if metodo == "POST" and url.endswith("/media"):
        return _Resp({"id": "CONT1"})
    if metodo == "GET":
        return _Resp({"status_code": "FINISHED"})
    return _Resp({}, 400)


def test_publica_imagem_fluxo_completo(monkeypatch):
    cli = _instalar(monkeypatch, _router_ok)
    res = PublicarInstagram().executar(
        CFG,
        ArgsPublicarInstagram(tipo_midia="imagem", midia_urls=["https://x/y.jpg"], legenda="Olá"),
    )
    assert res == {"ok": True, "media_id": "MEDIA1", "tipo_midia": "imagem"}
    post_media = next(d for m, u, d in cli.calls if m == "POST" and u.endswith("/media"))
    assert post_media["image_url"] == "https://x/y.jpg"
    assert post_media["caption"] == "Olá"
    # publicação usa o id do contêiner
    pub = next(d for m, u, d in cli.calls if u.endswith("/media_publish"))
    assert pub["creation_id"] == "CONT1"


def test_reels_usa_media_type_e_video_url(monkeypatch):
    cli = _instalar(monkeypatch, _router_ok)
    PublicarInstagram().executar(
        CFG, ArgsPublicarInstagram(tipo_midia="reels", midia_urls=["v.mp4"], legenda="L")
    )
    post_media = next(d for m, u, d in cli.calls if m == "POST" and u.endswith("/media"))
    assert post_media["media_type"] == "REELS"
    assert post_media["video_url"] == "v.mp4"


def test_stories_nao_leva_legenda(monkeypatch):
    cli = _instalar(monkeypatch, _router_ok)
    PublicarInstagram().executar(
        CFG, ArgsPublicarInstagram(tipo_midia="stories", midia_urls=["s.jpg"], legenda="ignorada")
    )
    post_media = next(d for m, u, d in cli.calls if m == "POST" and u.endswith("/media"))
    assert post_media["media_type"] == "STORIES"
    assert "caption" not in post_media


def test_carrossel_monta_filhos_e_publica(monkeypatch):
    estado = {"n": 0}

    def r(metodo, url, dados):
        if metodo == "POST" and url.endswith("/media_publish"):
            return _Resp({"id": "MEDIAC"})
        if metodo == "POST" and url.endswith("/media"):
            estado["n"] += 1
            return _Resp({"id": f"C{estado['n']}"})
        if metodo == "GET":
            return _Resp({"status_code": "FINISHED"})
        return _Resp({}, 400)

    cli = _instalar(monkeypatch, r)
    res = PublicarInstagram().executar(
        CFG, ArgsPublicarInstagram(tipo_midia="carrossel", midia_urls=["u1", "u2"], legenda="leg")
    )
    assert res["ok"] and res["tipo_midia"] == "carrossel"
    posts_media = [d for m, u, d in cli.calls if m == "POST" and u.endswith("/media")]
    itens = [d for d in posts_media if d.get("is_carousel_item") == "true"]
    pai = [d for d in posts_media if d.get("media_type") == "CAROUSEL"]
    assert len(itens) == 2 and len(pai) == 1
    assert pai[0]["children"] == "C1,C2"


def test_carrossel_exige_min_2(monkeypatch):
    _instalar(monkeypatch, _router_ok)
    with pytest.raises(FalhaInstrumento) as e:
        PublicarInstagram().executar(
            CFG, ArgsPublicarInstagram(tipo_midia="carrossel", midia_urls=["u1"])
        )
    assert "carrossel" in str(e.value)


def test_nao_conectado_falha():
    with pytest.raises(FalhaInstrumento) as e:
        PublicarInstagram().executar(
            ConfigPublicarInstagram(), ArgsPublicarInstagram(midia_urls=["u"])
        )
    assert "conectado" in str(e.value)
    assert e.value.retentavel is False


def test_sem_url_falha():
    with pytest.raises(FalhaInstrumento) as e:
        PublicarInstagram().executar(CFG, ArgsPublicarInstagram(midia_urls=[]))
    assert e.value.retentavel is False


def test_status_error_falha(monkeypatch):
    def r(metodo, url, dados):
        if metodo == "POST" and url.endswith("/media"):
            return _Resp({"id": "CONT1"})
        if metodo == "GET":
            return _Resp({"status_code": "ERROR"})
        return _Resp({}, 400)

    _instalar(monkeypatch, r)
    with pytest.raises(FalhaInstrumento) as e:
        PublicarInstagram().executar(CFG, ArgsPublicarInstagram(midia_urls=["u"]))
    assert e.value.retentavel is False


def test_status_error_inclui_o_motivo_da_meta(monkeypatch):
    # Quando a Meta explica o motivo no campo `status`, a mensagem TEM que trazê-lo —
    # antes ficava só "status ERROR", sem dizer proporção/resolução/duração/formato.
    motivo = "Error: 2207026 - Unsupported aspect ratio. Use 9:16."

    def r(metodo, url, dados):
        if metodo == "POST" and url.endswith("/media"):
            return _Resp({"id": "CONT1"})
        if metodo == "GET":
            return _Resp({"status_code": "ERROR", "status": motivo})
        return _Resp({}, 400)

    _instalar(monkeypatch, r)
    with pytest.raises(FalhaInstrumento) as e:
        PublicarInstagram().executar(CFG, ArgsPublicarInstagram(midia_urls=["u"]))
    assert motivo in str(e.value)
    assert e.value.retentavel is False


def test_falha_de_publicacao_nunca_e_retentavel(monkeypatch):
    # 500 no media_publish: NÃO pode ser retentável (idempotência → sem republicar).
    def r(metodo, url, dados):
        if metodo == "POST" and url.endswith("/media_publish"):
            return _Resp({"error": {"message": "down"}}, 500)
        if metodo == "POST" and url.endswith("/media"):
            return _Resp({"id": "CONT1"})
        if metodo == "GET":
            return _Resp({"status_code": "FINISHED"})
        return _Resp({}, 400)

    _instalar(monkeypatch, r)
    with pytest.raises(FalhaInstrumento) as e:
        PublicarInstagram().executar(CFG, ArgsPublicarInstagram(midia_urls=["u"]))
    assert e.value.retentavel is False


# ───────────────────── vídeo: carrossel misto e story de vídeo ─────────────────────


def test_story_de_video_usa_video_url(monkeypatch):
    cli = _instalar(monkeypatch, _router_ok)
    PublicarInstagram().executar(
        CFG,
        ArgsPublicarInstagram(
            tipo_midia="stories", midia_urls=["s.mp4"], tipos_midia_itens=["video"]
        ),
    )
    post_media = next(d for m, u, d in cli.calls if m == "POST" and u.endswith("/media"))
    assert post_media["media_type"] == "STORIES"
    assert post_media["video_url"] == "s.mp4"
    assert "image_url" not in post_media


def test_carrossel_misto_imagem_e_video(monkeypatch):
    estado = {"n": 0}

    def r(metodo, url, dados):
        if metodo == "POST" and url.endswith("/media_publish"):
            return _Resp({"id": "MEDIAC"})
        if metodo == "POST" and url.endswith("/media"):
            estado["n"] += 1
            return _Resp({"id": f"C{estado['n']}"})
        if metodo == "GET":
            return _Resp({"status_code": "FINISHED"})
        return _Resp({}, 400)

    cli = _instalar(monkeypatch, r)
    res = PublicarInstagram().executar(
        CFG,
        ArgsPublicarInstagram(
            tipo_midia="carrossel",
            midia_urls=["foto.jpg", "clip.mp4"],
            tipos_midia_itens=["imagem", "video"],
            legenda="misto",
        ),
    )
    assert res["ok"] and res["tipo_midia"] == "carrossel"
    itens = [
        d for m, u, d in cli.calls
        if m == "POST" and u.endswith("/media") and d.get("is_carousel_item") == "true"
    ]
    assert len(itens) == 2
    img = next(d for d in itens if "image_url" in d)
    vid = next(d for d in itens if d.get("media_type") == "VIDEO")
    assert img["image_url"] == "foto.jpg"
    assert vid["video_url"] == "clip.mp4" and "image_url" not in vid


def test_tipos_itens_vazio_mantem_tudo_imagem(monkeypatch):
    """Regressão: sem `tipos_midia_itens`, story/carrossel seguem só-imagem (image_url)."""
    cli = _instalar(monkeypatch, _router_ok)
    PublicarInstagram().executar(
        CFG, ArgsPublicarInstagram(tipo_midia="stories", midia_urls=["s.jpg"])
    )
    post_media = next(d for m, u, d in cli.calls if m == "POST" and u.endswith("/media"))
    assert post_media["media_type"] == "STORIES" and post_media["image_url"] == "s.jpg"
    assert "video_url" not in post_media
