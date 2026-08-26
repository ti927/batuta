"""Testes do instrumento Publicar no WordPress — foco na IMAGEM DESTACADA
(featured_media, 2026-06-18).

As chamadas HTTP são mockadas. Provam: publicar sem imagem segue igual (1 chamada,
sem featured_media); publicar com imagem faz 2 chamadas (mídia → post) na ordem
certa, lê os bytes do disco local (gerar_imagem), manda os cabeçalhos corretos e põe
`featured_media` no post; falha no upload NÃO publica; 403 fala de permissão; mime
sai do sufixo; URL externa é baixada.
"""

import pytest

import instrumentos.wordpress as wp
from arquivos import DIRETORIO_ARQUIVOS
from instrumentos.base import FalhaInstrumento


class _Resp:
    def __init__(self, status=200, payload=None, text="", content=b""):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self._payload = {} if payload is None else payload
        self.text = text
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.is_success:
            raise AssertionError(f"HTTP {self.status_code}")


def _suf(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def _factory(respostas: dict, registro: list):
    """Fábrica de httpx.Client falso: registra as chamadas e devolve respostas por
    sufixo de rota (media/posts/tags/categories). Default razoável p/ rotas livres."""

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            registro.append(("GET", url, {"params": params}))
            return respostas.get(("GET", _suf(url)), _Resp(200, []))

        def post(self, url, json=None, content=None, headers=None):
            registro.append(
                ("POST", url, {"json": json, "content": content, "headers": headers})
            )
            return respostas.get(("POST", _suf(url)), _Resp(201, {"id": 999, "link": "http://x"}))

    return _Client


def _config():
    return wp.ConfigWordpress(site_url="https://blog.x", usuario="u", senha_app="p")


def _arquivo_local(nome: str, conteudo: bytes = b"PNGDATA"):
    arq = DIRETORIO_ARQUIVOS / nome
    arq.write_bytes(conteudo)
    return arq


def test_publica_sem_imagem_uma_chamada(monkeypatch):
    registro: list = []
    respostas = {("POST", "posts"): _Resp(201, {"id": 10, "link": "http://x/10", "status": "draft"})}
    monkeypatch.setattr(wp.http_saida, "cliente", _factory(respostas, registro))
    r = wp.PublicarWordpress().executar(
        _config(), wp.ArgsWordpress(titulo="T", conteudo="C")
    )
    assert r["ok"] is True and r["featured_media"] is None
    posts = [c for c in registro if c[0] == "POST" and c[1].endswith("/posts")]
    midia = [c for c in registro if c[0] == "POST" and c[1].endswith("/media")]
    assert len(posts) == 1 and len(midia) == 0
    assert "featured_media" not in posts[0][2]["json"]


def test_publica_com_imagem_destacada(monkeypatch):
    arq = _arquivo_local("wptest_img.png", b"PNGDATA")
    try:
        registro: list = []
        respostas = {
            ("POST", "media"): _Resp(201, {"id": 77, "source_url": "http://b/img.png"}),
            ("POST", "posts"): _Resp(201, {"id": 10, "link": "http://x/10", "status": "publish"}),
        }
        monkeypatch.setattr(wp.http_saida, "cliente", _factory(respostas, registro))
        r = wp.PublicarWordpress().executar(
            _config(), wp.ArgsWordpress(titulo="T", conteudo="C", imagem_url="wptest_img.png")
        )
        assert r["featured_media"] == 77
        # 2 chamadas, mídia ANTES do post
        ordem = [_suf(c[1]) for c in registro if c[0] == "POST"]
        assert ordem == ["media", "posts"]
        post = next(c for c in registro if c[1].endswith("/posts"))
        assert post[2]["json"]["featured_media"] == 77
        # subiu os bytes do disco + cabeçalhos corretos
        mid = next(c for c in registro if c[1].endswith("/media"))
        assert mid[2]["content"] == b"PNGDATA"
        assert 'filename="wptest_img.png"' in mid[2]["headers"]["Content-Disposition"]
        assert mid[2]["headers"]["Content-Type"] == "image/png"
    finally:
        arq.unlink(missing_ok=True)


def test_falha_no_upload_da_imagem_nao_publica(monkeypatch):
    arq = _arquivo_local("wptest_img2.png", b"X")
    try:
        registro: list = []
        respostas = {("POST", "media"): _Resp(400, {}, text="bad image")}
        monkeypatch.setattr(wp.http_saida, "cliente", _factory(respostas, registro))
        with pytest.raises(FalhaInstrumento, match="imagem"):
            wp.PublicarWordpress().executar(
                _config(), wp.ArgsWordpress(titulo="T", conteudo="C", imagem_url="wptest_img2.png")
            )
        assert not any(c[1].endswith("/posts") for c in registro)  # não chegou a postar
    finally:
        arq.unlink(missing_ok=True)


def test_upload_403_fala_de_permissao(monkeypatch):
    arq = _arquivo_local("wptest_img3.png", b"X")
    try:
        monkeypatch.setattr(
            wp.http_saida, "cliente", _factory({("POST", "media"): _Resp(403, {})}, [])
        )
        with pytest.raises(FalhaInstrumento, match="permissão"):
            wp.PublicarWordpress().executar(
                _config(), wp.ArgsWordpress(titulo="T", conteudo="C", imagem_url="wptest_img3.png")
            )
    finally:
        arq.unlink(missing_ok=True)


def test_mime_sai_do_sufixo_jpg(monkeypatch):
    arq = _arquivo_local("wptest_img.jpg", b"JPG")
    try:
        registro: list = []
        respostas = {
            ("POST", "media"): _Resp(201, {"id": 5}),
            ("POST", "posts"): _Resp(201, {"id": 1, "link": "x"}),
        }
        monkeypatch.setattr(wp.http_saida, "cliente", _factory(respostas, registro))
        wp.PublicarWordpress().executar(
            _config(), wp.ArgsWordpress(titulo="T", conteudo="C", imagem_url="wptest_img.jpg")
        )
        mid = next(c for c in registro if c[1].endswith("/media"))
        assert mid[2]["headers"]["Content-Type"] == "image/jpeg"
    finally:
        arq.unlink(missing_ok=True)


def test_imagem_externa_e_baixada(monkeypatch):
    registro: list = []
    respostas = {
        ("POST", "media"): _Resp(201, {"id": 9}),
        ("POST", "posts"): _Resp(201, {"id": 1, "link": "x"}),
    }
    # O download da imagem externa passa pela MESMA porta de saída (queda p/ IPv4).
    respostas[("GET", "foto.webp")] = _Resp(200, content=b"EXTBYTES")
    monkeypatch.setattr(wp.http_saida, "cliente", _factory(respostas, registro))
    r = wp.PublicarWordpress().executar(
        _config(),
        wp.ArgsWordpress(
            titulo="T", conteudo="C", imagem_url="https://externa.com/foto.webp"
        ),
    )
    assert r["featured_media"] == 9
    mid = next(c for c in registro if c[1].endswith("/media"))
    assert mid[2]["content"] == b"EXTBYTES"
    assert mid[2]["headers"]["Content-Type"] == "image/webp"
