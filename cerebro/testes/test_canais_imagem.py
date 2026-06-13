"""Imagem na entrada — o caso do recibo (Passo 8).

Sem LLM nem rede real: a função pura de conteúdo multimodal, o contextvar
consumido uma vez, o Storage e o download do Telegram (mockados), e o Modo B
guardando a imagem na entrada da execução.
"""

import storage
import canais.telegram as tg
from canais.servico import baixar_anexo  # noqa: F401 (garante import do módulo)
from orquestracao.agente import (
    _conteudo_da_mensagem,
    _imagem_entrada,
    usar_imagem_entrada,
)
from modelos import Automacao, Canal, Execucao, IdentidadeCanal
from sqlalchemy import select


# ───────────────────── conteúdo multimodal (função pura) ─────────────────────


def test_conteudo_so_texto_quando_sem_imagem():
    assert _conteudo_da_mensagem("olá", None) == "olá"


def test_conteudo_multimodal_com_imagem():
    c = _conteudo_da_mensagem("veja", "data:image/jpeg;base64,AAA")
    assert isinstance(c, list)
    assert c[0] == {"type": "text", "text": "veja"}
    assert c[1] == {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAA"}}


def test_conteudo_imagem_sem_texto_tem_fallback():
    c = _conteudo_da_mensagem("", "data:image/png;base64,BBB")
    assert c[0]["text"]  # algum texto-guia não-vazio


def test_usar_imagem_entrada_fixa_e_limpa():
    assert _imagem_entrada.get() is None
    with usar_imagem_entrada("data:image/jpeg;base64,X"):
        assert _imagem_entrada.get() == "data:image/jpeg;base64,X"
    assert _imagem_entrada.get() is None  # limpou ao sair


# ───────────────────────────── Storage (httpx) ───────────────────────────────


class _Resp:
    content = b"BYTES"

    def raise_for_status(self):
        return None


def test_storage_enviar_e_baixar(monkeypatch):
    chamadas = {}

    def fake_post(url, headers=None, content=None, timeout=None):
        chamadas["post"] = (url, headers, content)
        return _Resp()

    def fake_get(url, headers=None, timeout=None):
        chamadas["get"] = (url, headers)
        return _Resp()

    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srv-key")
    monkeypatch.setattr(storage.httpx, "post", fake_post)
    monkeypatch.setattr(storage.httpx, "get", fake_get)

    caminho = storage.enviar("org/exec/f1", b"BYTES", "image/jpeg")
    assert caminho == "org/exec/f1"
    url, headers, content = chamadas["post"]
    assert url == "https://x.supabase.co/storage/v1/object/mensagens/org/exec/f1"
    assert headers["x-upsert"] == "true" and headers["Content-Type"] == "image/jpeg"
    assert content == b"BYTES"

    assert storage.baixar("org/exec/f1") == b"BYTES"
    assert "mensagens/org/exec/f1" in chamadas["get"][0]


# ─────────────────────── download de anexo do Telegram ───────────────────────


class _ClienteArquivo:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None):
        if "getFile" in url:
            return _RespJson({"result": {"file_path": "photos/file_7.jpg"}})
        return _RespArquivo()


class _RespJson:
    def __init__(self, dados):
        self._d = dados

    def json(self):
        return self._d


class _RespArquivo:
    content = b"IMAGEM"

    def raise_for_status(self):
        return None


def test_telegram_baixar_arquivo(monkeypatch):
    monkeypatch.setattr(tg.httpx, "Client", _ClienteArquivo)
    conteudo, content_type = tg.CanalTelegram().baixar_arquivo(
        tg.ConfigTelegram(token="123:ABC"), "file-id-7"
    )
    assert conteudo == b"IMAGEM"
    assert content_type == "image/jpeg"  # inferido da extensão .jpg


# ──────────────────── Modo B guarda a imagem na entrada ───────────────────────


def test_modo_b_com_imagem_guarda_no_storage(cliente, sessao, dados, monkeypatch):
    canal = Canal(
        organizacao_id=dados["orgA"].id, tipo="telegram", nome="Tg", config={}, ativo=True
    )
    sessao.add(canal)
    sessao.flush()
    sessao.add(
        IdentidadeCanal(
            organizacao_id=dados["orgA"].id, canal_id=canal.id,
            identificador_externo="5175", rotulo="Julio",
        )
    )
    sessao.add(
        Automacao(
            time_id=dados["timeA"].id, nome="Recibos", tipo_gatilho="mensagem_recebida",
            configuracao_gatilho={"canal_id": str(canal.id)}, cadeia={}, ativa=True,
        )
    )
    sessao.flush()

    # Mocka o download do provedor e o upload ao Storage.
    monkeypatch.setattr(
        "canais.servico.baixar_anexo", lambda s, c, ref: (b"IMAGEM", "image/jpeg")
    )
    enviados = {}
    monkeypatch.setattr(
        storage, "enviar",
        lambda caminho, conteudo, content_type, **k: enviados.update(
            caminho=caminho, ct=content_type
        )
        or caminho,
    )

    r = cliente.post(
        f"/canais/{canal.id}/webhook",
        json={
            "update_id": 1,
            "message": {
                "chat": {"id": "5175"},
                "caption": "meu recibo",
                "photo": [{"file_id": "peq"}, {"file_id": "grande"}],
            },
        },
    )
    assert r.json()["modo"] == "B"
    execucao = sessao.scalars(
        select(Execucao).where(Execucao.origem_canal_id == canal.id)
    ).first()
    assert execucao is not None
    img = (execucao.entrada or {}).get("imagem")
    assert img is not None
    assert img["media_type"] == "image/jpeg"
    assert img["storage_path"].endswith("/grande")  # a maior resolução
    assert enviados["ct"] == "image/jpeg"
