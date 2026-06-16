"""Testes do instrumento Gerar imagem (Fase adicional).

A chamada real à API de imagem é paga; aqui ela é mockada. Provam o registro, o
segredo (chave_api), o erro claro sem chave, e o caminho feliz: salva o arquivo
e devolve o link.
"""

import base64

import pydantic
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


# ─────────────── config guiada: modelo/tamanho como conjunto fechado ───────────


def test_modelo_e_tamanho_padrao():
    """Default funciona de saída: gpt-image-1 (mais novo) + 1024x1024 (vale p/ todos)."""
    cfg = ConfigImagem()
    assert cfg.modelo == "gpt-image-1" and cfg.tamanho == "1024x1024"


def test_combinacao_modelo_tamanho_valida_passa():
    cfg = ConfigImagem(modelo="dall-e-3", tamanho="1024x1792")
    assert cfg.modelo == "dall-e-3" and cfg.tamanho == "1024x1792"


def test_combinacao_modelo_tamanho_invalida_recusa_com_mensagem():
    # 1024x1536 é do gpt-image-1, não do dall-e-3 → erro claro.
    with pytest.raises(pydantic.ValidationError, match="não vale para o modelo"):
        ConfigImagem(modelo="dall-e-3", tamanho="1024x1536")


def test_modelo_fora_do_conjunto_recusado():
    """`modelo` é um Literal — valor inventado nem é aceito (vira dropdown na UI)."""
    with pytest.raises(pydantic.ValidationError):
        ConfigImagem(modelo="dall-e-4")


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
