"""Testes do instrumento 'Descrever/ler imagem (visão)'.

Cobrem: registro + dica de UI (ui:modelo_ia) + enum-união; a mensagem multimodal
(bloco agnóstico {type:image,base64,mime_type}); reuso do _baixar e sua política de
erro; recusa de não-imagem / imagem grande / muitas imagens / URL vazia; erro claro
quando o provedor não tem chave; e a medição (custo por família + origem derivada do
provedor). Sem rede: construir_modelo e _baixar são dublês.
"""

import base64
from types import SimpleNamespace

import pytest

import instrumentos as encaixe
import medicao_instrumentos as med
from instrumentos.base import FalhaInstrumento
from instrumentos.descrever_imagem import (
    ArgsDescrever,
    ConfigDescrever,
    DescreverImagem,
)

_JPEG = b"\xff\xd8\xff\xe0" + b"conteudo-da-foto"  # magic de JPEG + bytes


class _Resp:
    def __init__(self, content):
        self.content = content


class _ModeloFake:
    def __init__(self, capt):
        self._capt = capt

    def invoke(self, msgs):
        self._capt["msgs"] = msgs
        return _Resp("é um pôr do sol na praia")


def _mock(monkeypatch, *, baixar=None, construir=None):
    if baixar is not None:
        monkeypatch.setattr("instrumentos.descrever_imagem._baixar", baixar)
    if construir is not None:
        monkeypatch.setattr("instrumentos.descrever_imagem.construir_modelo", construir)


# ───────────────────────────── registro ─────────────────────────────


def test_registrado_com_ui_modelo():
    t = encaixe.obter_tipo("descrever_imagem")
    assert t is not None and t.acao_irreversivel is False and t.categoria == "Conteúdo"
    prop = t.Config.model_json_schema()["properties"]["modelo"]
    assert prop.get("ui") == "modelo_ia"
    assert "claude-haiku-4-5" in prop["enum"] and "gpt-4o" in prop["enum"]


# ───────────────────────── mensagem multimodal ──────────────────────


def test_monta_mensagem_multimodal(monkeypatch):
    capt: dict = {}
    _mock(
        monkeypatch,
        baixar=lambda u: (_JPEG, "image/jpeg"),
        construir=lambda m: _ModeloFake(capt),
    )
    res = DescreverImagem().executar(
        ConfigDescrever(modelo="claude-haiku-4-5"),
        ArgsDescrever(imagens_url=["http://x/a.jpg", "http://x/b.jpg"], instrucao="o que é?"),
    )
    assert res["ok"] and res["descricao"] == "é um pôr do sol na praia"
    assert res["modelo"] == "claude-haiku-4-5" and res["imagens"] == 2

    content = capt["msgs"][0].content  # HumanMessage.content
    assert content[0] == {"type": "text", "text": "o que é?"}
    imagens = [b for b in content if b.get("type") == "image"]
    assert len(imagens) == 2
    assert imagens[0]["mime_type"] == "image/jpeg"
    assert base64.b64decode(imagens[0]["base64"]) == _JPEG


# ───────────────────────── recusas / erros ──────────────────────────


def test_sem_chave_nao_retentavel(monkeypatch):
    def _raise(m):
        raise RuntimeError("O modelo 'gpt-4o' usa OpenAI, mas não há chave OpenAI...")

    _mock(monkeypatch, construir=_raise)
    with pytest.raises(FalhaInstrumento) as e:
        DescreverImagem().executar(
            ConfigDescrever(modelo="gpt-4o"), ArgsDescrever(imagens_url=["http://x/a.jpg"])
        )
    assert e.value.retentavel is False and "OpenAI" in str(e.value)


def test_conteudo_nao_imagem_recusado(monkeypatch):
    _mock(
        monkeypatch,
        baixar=lambda u: (b"<html>nao sou imagem</html>", "text/html"),
        construir=lambda m: _ModeloFake({}),
    )
    with pytest.raises(FalhaInstrumento) as e:
        DescreverImagem().executar(ConfigDescrever(), ArgsDescrever(imagens_url=["http://x/p"]))
    assert e.value.retentavel is False and "não aponta para uma imagem" in str(e.value)


def test_imagem_grande_recusada(monkeypatch):
    grande = _JPEG[:4] + b"x" * 6_000_000
    _mock(
        monkeypatch,
        baixar=lambda u: (grande, "image/jpeg"),
        construir=lambda m: _ModeloFake({}),
    )
    with pytest.raises(FalhaInstrumento) as e:
        DescreverImagem().executar(ConfigDescrever(), ArgsDescrever(imagens_url=["http://x/big.jpg"]))
    assert e.value.retentavel is False and "grande demais" in str(e.value)


def test_muitas_imagens_recusado():
    urls = [f"http://x/{i}.jpg" for i in range(9)]  # > MAX_IMAGENS (8)
    with pytest.raises(FalhaInstrumento) as e:
        DescreverImagem().executar(ConfigDescrever(), ArgsDescrever(imagens_url=urls))
    assert e.value.retentavel is False


def test_url_em_branco_recusada():
    with pytest.raises(FalhaInstrumento) as e:
        DescreverImagem().executar(ConfigDescrever(), ArgsDescrever(imagens_url=["   "]))
    assert e.value.retentavel is False


def test_download_falha_propaga(monkeypatch):
    def _falha(u):
        raise FalhaInstrumento("não consegui baixar", retentavel=True)

    _mock(monkeypatch, baixar=_falha, construir=lambda m: _ModeloFake({}))
    with pytest.raises(FalhaInstrumento) as e:
        DescreverImagem().executar(ConfigDescrever(), ArgsDescrever(imagens_url=["http://x/a.jpg"]))
    assert e.value.retentavel is True


# ───────────────────────────── medição ──────────────────────────────


def test_medicao_descricao_e_origem():
    """descrever_imagem entra na medição: custo por família + origem = provedor do modelo."""
    assert "descrever_imagem" in med.TIPOS_PAGOS
    inst = SimpleNamespace(
        tipo="descrever_imagem", configuracao={"modelo": "claude-opus-4-8"}
    )
    entrada, servico = med._entrada_e_servico(inst)
    assert entrada["modelo"] == "claude-opus-4-8" and entrada["imagens"] == 1
    assert entrada["custo_usd"] == 0.02  # família opus
    assert servico == "anthropic"  # derivado do provedor do modelo (sem chave_compartilhada)
