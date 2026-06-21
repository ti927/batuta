"""Testes do armazenamento de arquivos gerados.

Em produção sobe para o Supabase Storage (bucket público → URL durável, acessível
pela Meta ao publicar); sem Storage, cai no disco local. Sem rede: o httpx de
`arquivos` é interceptado.
"""

import arquivos


class _Resp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self.text = text


class _Client:
    def __init__(self, roteador):
        self.roteador = roteador
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, headers=None, json=None, content=None):
        self.calls.append({"url": url, "json": json, "content": content})
        return self.roteador(url)


def _instalar(monkeypatch, roteador):
    cli = _Client(roteador)
    monkeypatch.setattr("arquivos.httpx.Client", lambda *a, **k: cli)
    monkeypatch.setattr(arquivos, "_bucket_garantido", False)
    monkeypatch.setattr(arquivos, "_SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setattr(arquivos, "_SUPABASE_KEY", "service-key")
    return cli


def test_salvar_sobe_para_o_storage_e_devolve_url_publica(monkeypatch):
    cli = _instalar(monkeypatch, lambda url: _Resp(200))  # bucket + upload ok
    url = arquivos.salvar("abc.png", b"PNG", "image/png")
    assert url == "https://proj.supabase.co/storage/v1/object/public/arquivos/abc.png"
    upload = next(c for c in cli.calls if "/object/arquivos/abc.png" in c["url"])
    assert upload["content"] == b"PNG"


def test_salvar_cai_no_disco_se_upload_falha(monkeypatch, tmp_path):
    monkeypatch.setattr(arquivos, "DIRETORIO_ARQUIVOS", tmp_path)

    def roteador(url):
        return _Resp(200) if url.endswith("/bucket") else _Resp(500, "erro")

    _instalar(monkeypatch, roteador)
    url = arquivos.salvar("z.png", b"DADO", "image/png")
    assert url == arquivos.url_do_arquivo("z.png")
    assert (tmp_path / "z.png").read_bytes() == b"DADO"


def test_salvar_sem_storage_usa_disco(monkeypatch, tmp_path):
    monkeypatch.setattr(arquivos, "DIRETORIO_ARQUIVOS", tmp_path)
    monkeypatch.setattr(arquivos, "_SUPABASE_URL", "")  # Storage não configurado
    url = arquivos.salvar("w.pdf", b"PDF", "application/pdf")
    assert url == arquivos.url_do_arquivo("w.pdf")
    assert (tmp_path / "w.pdf").read_bytes() == b"PDF"
