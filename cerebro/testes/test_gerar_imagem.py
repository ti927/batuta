"""Testes do instrumento Gerar imagem (reformulado 2026-06-18).

A chamada real à API de imagem é paga; aqui ela é mockada. Provam: o registro e o
segredo (chave_api); o CATÁLOGO como fonte da verdade; a validação do trio
modelo×tamanho×qualidade; a auto-cura de modelos legados (DALL·E → padrão); o
payload correto (com qualidade, SEM response_format); e o erro acionável da OpenAI.
"""

import base64

import pydantic
import pytest

import instrumentos as encaixe
import instrumentos.gerar_imagem as gi
import precos
from arquivos import DIRETORIO_ARQUIVOS
from instrumentos.base import FalhaInstrumento
from instrumentos.gerar_imagem import ArgsImagem, ConfigImagem, GerarImagem


# ─────────────────────────── fakes de HTTP ───────────────────────────


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("sem json")
        return self._payload


def _mock_post(monkeypatch, resp, capt=None):
    """Substitui httpx.Client por um fake que captura o corpo e devolve `resp`."""

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None, content=None):
            # Captura só a chamada à API de imagem (tem 'model'); ignora as do
            # Supabase Storage (criar bucket / upload), que reusam o mesmo httpx.
            if capt is not None and isinstance(json, dict) and "model" in json:
                capt["url"], capt["headers"], capt["json"] = url, headers, json
            return resp

    monkeypatch.setattr(gi.httpx, "Client", _Client)


def _resp_ok():
    return _Resp(200, {"data": [{"b64_json": base64.b64encode(b"PNGDATA").decode()}]})


@pytest.fixture(autouse=True)
def _sem_vigia(monkeypatch):
    # O vigia (diagnostico_imagem) grava no Storage; nos testes é no-op para não
    # tocar a rede nem deixar artefato.
    monkeypatch.setattr(gi.diagnostico_imagem, "registrar", lambda *a, **k: None)


# ─────────────────────────── registro / chave ───────────────────────────


def test_gerar_imagem_registrado_com_chave_secreta():
    t = encaixe.obter_tipo("gerar_imagem")
    assert t is not None and t.campos_secretos == ("chave_api",)
    assert "gerar_imagem" in [x.tipo for x in encaixe.tipos_disponiveis()]


def test_sem_chave_falha_clara():
    with pytest.raises(FalhaInstrumento, match="chave"):
        GerarImagem().executar(ConfigImagem(), ArgsImagem(prompt="um gato"))


# ───────────── catálogo como fonte da verdade + dependências ─────────────


def test_so_familia_gpt_image_no_catalogo():
    # DALL·E foi aposentado: não é oferecido (mas se auto-cura, ver abaixo).
    assert set(gi.CATALOGO_IMAGEM) == {
        "gpt-image-1", "gpt-image-1-mini", "gpt-image-1.5", "gpt-image-2"
    }


def test_todo_modelo_do_catalogo_tem_preco():
    """Guarda contra drift: todo modelo (e cada qualidade dele) tem preço."""
    for modelo, spec in gi.CATALOGO_IMAGEM.items():
        assert modelo in precos.PRECOS_IMAGEM_USD, f"falta preço de {modelo}"
        for q in spec["qualidades"]:
            assert q in precos.PRECOS_IMAGEM_USD[modelo], f"falta preço {modelo}/{q}"


def test_dependencias_ui_casa_com_catalogo():
    deps = GerarImagem().dependencias_ui()
    assert deps["tamanho"]["controlado_por"] == "modelo"
    assert deps["qualidade"]["controlado_por"] == "modelo"
    for modelo, spec in gi.CATALOGO_IMAGEM.items():
        assert deps["tamanho"]["opcoes"][modelo] == list(spec["tamanhos"])
        assert deps["qualidade"]["opcoes"][modelo] == list(spec["qualidades"])


def test_esquema_config_tem_enum_para_dropdown():
    # o front monta o dropdown do `enum`; o catálogo precisa chegar lá.
    props = ConfigImagem.model_json_schema()["properties"]
    assert props["modelo"]["enum"] == list(gi.CATALOGO_IMAGEM)
    assert props["qualidade"]["enum"] == list(gi._QUALIDADES_GPT)
    assert "1024x1024" in props["tamanho"]["enum"]


# ─────────────────────────── validação do trio ───────────────────────────


def test_padrao_funciona_de_saida():
    cfg = ConfigImagem()
    assert cfg.modelo == "gpt-image-1"
    assert cfg.tamanho == "1024x1024"
    assert cfg.qualidade == "medium"


def test_combinacao_valida_passa():
    cfg = ConfigImagem(modelo="gpt-image-2", tamanho="1536x864", qualidade="high")
    assert cfg.modelo == "gpt-image-2" and cfg.tamanho == "1536x864"


def test_tamanho_invalido_para_o_modelo_recusa_com_mensagem():
    # 1536x864 é do gpt-image-2, não do gpt-image-1 → erro claro.
    with pytest.raises(pydantic.ValidationError, match="não vale para o modelo"):
        ConfigImagem(modelo="gpt-image-1", tamanho="1536x864")


def test_qualidade_invalida_recusa_com_mensagem():
    with pytest.raises(pydantic.ValidationError, match="qualidade"):
        ConfigImagem(modelo="gpt-image-1", qualidade="ultra")


def test_modelo_desconhecido_recusado():
    with pytest.raises(pydantic.ValidationError, match="desconhecido"):
        ConfigImagem(modelo="gpt-image-99")


def test_modelo_legado_se_cura_para_o_padrao():
    """Instrumento antigo com DALL·E (aposentado) vira o padrão, sem crashar —
    é o que faz o instrumento que falhava voltar a funcionar sem mexer no banco."""
    cfg = ConfigImagem(modelo="dall-e-3", tamanho="1024x1792")
    assert cfg.modelo == "gpt-image-1"
    assert cfg.tamanho == "1024x1024"  # tamanho do DALL·E não vale → cai no padrão


# ─────────────────────────── execução ───────────────────────────


def test_payload_tem_qualidade_e_nao_tem_response_format(monkeypatch):
    capt: dict = {}
    _mock_post(monkeypatch, _resp_ok(), capt)
    GerarImagem().executar(
        ConfigImagem(chave_api="sk-fake", modelo="gpt-image-1", qualidade="high"),
        ArgsImagem(prompt="um gato"),
    )
    corpo = capt["json"]
    assert corpo["model"] == "gpt-image-1"
    assert corpo["quality"] == "high"
    assert corpo["size"] == "1024x1024"
    assert "response_format" not in corpo  # gpt-image sempre devolve base64


def test_formato_padrao_png_nao_envia_output_format(monkeypatch):
    # PNG é o padrão: caminho intocado, sem `output_format` (byte-idêntico ao de antes).
    capt: dict = {}
    _mock_post(monkeypatch, _resp_ok(), capt)
    GerarImagem().executar(ConfigImagem(chave_api="sk-fake"), ArgsImagem(prompt="um gato"))
    assert "output_format" not in capt["json"]


def test_formato_jpeg_pede_output_format_e_salva_jpg(monkeypatch):
    # JPEG: pede o formato à OpenAI (seletor da API) e salva o arquivo como .jpg.
    monkeypatch.setattr("arquivos.storage_configurado", lambda: False)
    capt: dict = {}
    _mock_post(
        monkeypatch,
        _Resp(200, {"data": [{"b64_json": base64.b64encode(b"JPEGDATA").decode()}]}),
        capt,
    )
    r = GerarImagem().executar(
        ConfigImagem(chave_api="sk-fake", formato="jpeg"), ArgsImagem(prompt="um gato")
    )
    assert capt["json"]["output_format"] == "jpeg"
    assert r["arquivo"].endswith(".jpg")
    caminho = DIRETORIO_ARQUIVOS / r["arquivo"]
    try:
        assert caminho.exists() and caminho.read_bytes() == b"JPEGDATA"
    finally:
        caminho.unlink(missing_ok=True)


def test_gera_salva_arquivo_e_devolve_link(monkeypatch):
    # Sem Storage (caminho de fallback de dev): o arquivo cai no disco local. O
    # caminho do Supabase Storage é coberto em test_arquivos.
    monkeypatch.setattr("arquivos.storage_configurado", lambda: False)
    _mock_post(monkeypatch, _resp_ok())
    r = GerarImagem().executar(
        ConfigImagem(chave_api="sk-fake"), ArgsImagem(prompt="um gato astronauta")
    )
    assert r["ok"] is True and r["url"].endswith(r["arquivo"])
    caminho = DIRETORIO_ARQUIVOS / r["arquivo"]
    try:
        assert caminho.exists() and caminho.read_bytes() == b"PNGDATA"
    finally:
        caminho.unlink(missing_ok=True)  # não deixa lixo do teste


def test_erro_da_openai_vira_mensagem_acionavel(monkeypatch):
    """O motor traduz o erro da OpenAI citando parâmetro/mensagem/código — é o que
    diz o que ajustar quando a OpenAI mudar os parâmetros aceitos."""
    resp = _Resp(
        400,
        {
            "error": {
                "message": "The model 'x' does not exist.",
                "param": "model",
                "code": "invalid_value",
            }
        },
    )
    _mock_post(monkeypatch, resp)
    with pytest.raises(FalhaInstrumento) as exc:
        GerarImagem().executar(
            ConfigImagem(chave_api="sk-fake"), ArgsImagem(prompt="x")
        )
    msg = str(exc.value)
    assert "HTTP 400" in msg
    assert "model" in msg  # o parâmetro recusado
    assert "does not exist" in msg  # a mensagem da OpenAI
    assert "invalid_value" in msg  # o código


def test_chave_recusada_401(monkeypatch):
    _mock_post(monkeypatch, _Resp(401, {"error": {"message": "bad key"}}))
    with pytest.raises(FalhaInstrumento, match="recusada"):
        GerarImagem().executar(
            ConfigImagem(chave_api="sk-ruim"), ArgsImagem(prompt="x")
        )
