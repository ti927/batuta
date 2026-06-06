"""Testes do instrumento Gerar imagem (Fase adicional).

A chamada real à API de imagem é paga; aqui ela é mockada. Provam o registro, o
segredo (chave_api), o erro claro sem chave, e o caminho feliz: salva o arquivo
e devolve o link.
"""

import base64

import pytest

import instrumentos as encaixe
import instrumentos.gerar_imagem as gi
from arquivos import DIRETORIO_ARQUIVOS
from instrumentos.base import FalhaInstrumento
from instrumentos.gerar_imagem import ArgsImagem, ConfigImagem, GerarImagem


class _FakeResp:
    status_code = 200
    is_success = True

    def json(self):
        return {"data": [{"b64_json": base64.b64encode(b"PNGDATA").decode()}]}


class _FakeClient:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, *a, **k):
        return _FakeResp()


def test_gerar_imagem_registrado_com_chave_secreta():
    t = encaixe.obter_tipo("gerar_imagem")
    assert t is not None and t.campos_secretos == ("chave_api",)
    assert "gerar_imagem" in [x.tipo for x in encaixe.tipos_disponiveis()]


def test_sem_chave_falha_clara():
    with pytest.raises(FalhaInstrumento, match="chave"):
        GerarImagem().executar(ConfigImagem(), ArgsImagem(prompt="um gato"))


def test_gera_salva_arquivo_e_devolve_link(monkeypatch):
    monkeypatch.setattr(gi.httpx, "Client", _FakeClient)
    r = GerarImagem().executar(
        ConfigImagem(chave_api="sk-fake"), ArgsImagem(prompt="um gato astronauta")
    )
    assert r["ok"] is True and r["url"].endswith(r["arquivo"])
    caminho = DIRETORIO_ARQUIVOS / r["arquivo"]
    try:
        assert caminho.exists() and caminho.read_bytes() == b"PNGDATA"
    finally:
        caminho.unlink(missing_ok=True)  # não deixa lixo do teste
