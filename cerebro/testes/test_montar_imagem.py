"""Testes do instrumento "Montar imagem (a partir de fotos)".

A chamada real à OpenAI é paga; aqui o `httpx` do instrumento é interceptado (o
download das fotos-base E o POST multipart de edição). Provam: o registro/segredo;
que NÃO é irreversível (não exige portão); que é contabilizado como instrumento
pago; o multipart correto (`image[]` + `input_fidelity` só nos modelos que aceitam);
e os erros acionáveis (chave recusada, foto-base inacessível, parâmetro inválido).
"""

import base64

import pydantic
import pytest

import instrumentos as encaixe
import instrumentos.montar_imagem as mi
from arquivos import DIRETORIO_ARQUIVOS
from instrumentos.base import FalhaInstrumento
from instrumentos.montar_imagem import ArgsMontagem, ConfigMontagem, MontarImagem
from medicao_instrumentos import TIPOS_PAGOS


# ─────────────────────────── fakes de HTTP ───────────────────────────


class _Resp:
    def __init__(self, status, payload=None, content=b"", headers=None, text=""):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self._payload = payload
        self.content = content
        self.headers = headers or {}
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("sem json")
        return self._payload


def _resp_ok():
    return _Resp(200, {"data": [{"b64_json": base64.b64encode(b"ARTE").decode()}]})


def _foto_ok():
    return _Resp(200, content=b"FOTO", headers={"content-type": "image/png"})


def _instalar(monkeypatch, resp_post, capt=None, resp_get=None):
    """Intercepta o download da foto (httpx.get) e o POST de edição (httpx.Client)."""
    monkeypatch.setattr("arquivos.storage_configurado", lambda: False)  # cai no disco
    # O vigia (diagnostico_imagem) grava no Storage; no-op nos testes.
    monkeypatch.setattr(mi.diagnostico_imagem, "registrar", lambda *a, **k: None)
    monkeypatch.setattr(mi.httpx, "get", lambda url, **k: resp_get or _foto_ok())

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, data=None, files=None, json=None, content=None):
            if capt is not None:
                capt.update(url=url, headers=headers, data=data, files=files)
            return resp_post

    monkeypatch.setattr(mi.httpx, "Client", _Client)


def _limpar(r):
    (DIRETORIO_ARQUIVOS / r["arquivo"]).unlink(missing_ok=True)


# ─────────────────────────── registro / natureza ───────────────────────────


def test_registrado_com_chave_e_pool_openai():
    t = encaixe.obter_tipo("montar_imagem")
    assert t is not None
    assert t.campos_secretos == ("chave_api",)
    assert t.chave_compartilhada == ("chave_api", "openai")
    assert "montar_imagem" in [x.tipo for x in encaixe.tipos_disponiveis()]


def test_nao_e_irreversivel_nao_exige_portao():
    # Gerar/montar imagem não age no mundo externo → SEM portão.
    assert encaixe.acao_irreversivel("montar_imagem", {}) is False


def test_e_instrumento_pago():
    assert "montar_imagem" in TIPOS_PAGOS


def test_padroes_voltados_a_montagem():
    cfg = ConfigMontagem()
    assert cfg.modelo == "gpt-image-1.5"
    assert cfg.tamanho == "1024x1536"  # retrato
    assert cfg.qualidade == "high"


# ─────────────────────────── validação dos args ───────────────────────────


def test_sem_foto_base_recusa():
    with pytest.raises(pydantic.ValidationError):
        ArgsMontagem(prompt="um tema", imagens_url=[])


def test_sem_chave_falha_clara():
    with pytest.raises(FalhaInstrumento, match="chave"):
        MontarImagem().executar(
            ConfigMontagem(), ArgsMontagem(prompt="t", imagens_url=["http://x/f.png"])
        )


# ─────────────────────────── execução / multipart ───────────────────────────


def test_monta_envia_multipart_com_fidelity_e_salva(monkeypatch):
    capt: dict = {}
    _instalar(monkeypatch, _resp_ok(), capt)
    r = MontarImagem().executar(
        ConfigMontagem(chave_api="sk-fake", modelo="gpt-image-1.5"),
        ArgsMontagem(prompt="a pessoa num escritório", imagens_url=["http://x/eu.png"]),
    )
    try:
        assert r["ok"] is True and r["url"].endswith(r["arquivo"])
        # a foto vai como image[] (multipart), o modelo e a fidelidade no corpo
        assert [f[0] for f in capt["files"]] == ["image[]"]
        assert capt["data"]["model"] == "gpt-image-1.5"
        assert capt["data"]["input_fidelity"] == "high"
        assert capt["data"]["size"] == "1024x1536"
        # o arquivo final foi salvo (disco, no teste) com os bytes da resposta
        assert (DIRETORIO_ARQUIVOS / r["arquivo"]).read_bytes() == b"ARTE"
    finally:
        _limpar(r)


def test_varias_fotos_a_primeira_vai_primeiro(monkeypatch):
    capt: dict = {}
    _instalar(monkeypatch, _resp_ok(), capt)
    r = MontarImagem().executar(
        ConfigMontagem(chave_api="sk-fake"),
        ArgsMontagem(prompt="t", imagens_url=["http://x/a.png", "http://x/b.png"]),
    )
    try:
        nomes_campo = [f[0] for f in capt["files"]]
        assert nomes_campo == ["image[]", "image[]"]
        # ordem preservada: base0 (a primeira) antes de base1
        nomes_arq = [f[1][0] for f in capt["files"]]
        assert nomes_arq[0].startswith("base0") and nomes_arq[1].startswith("base1")
    finally:
        _limpar(r)


def test_gpt_image_2_nao_envia_input_fidelity(monkeypatch):
    capt: dict = {}
    _instalar(monkeypatch, _resp_ok(), capt)
    r = MontarImagem().executar(
        ConfigMontagem(chave_api="sk-fake", modelo="gpt-image-2", tamanho="1024x1536"),
        ArgsMontagem(prompt="t", imagens_url=["http://x/f.png"]),
    )
    try:
        # gpt-image-2 processa em alta fidelidade sozinho; o parâmetro é recusado.
        assert "input_fidelity" not in capt["data"]
    finally:
        _limpar(r)


# ─────────────────────────── erros ───────────────────────────


def test_foto_base_inacessivel_da_erro_claro(monkeypatch):
    _instalar(monkeypatch, _resp_ok(), resp_get=_Resp(404, text="nao achei"))
    with pytest.raises(FalhaInstrumento, match="baixad"):
        MontarImagem().executar(
            ConfigMontagem(chave_api="sk-fake"),
            ArgsMontagem(prompt="t", imagens_url=["http://x/sumiu.png"]),
        )


def test_timeout_na_montagem_falha_clara_sem_retentar(monkeypatch):
    # Geração pesada que estoura o tempo: falha NÃO retentável (não re-sobe os MB).
    import httpx

    monkeypatch.setattr("arquivos.storage_configurado", lambda: False)
    monkeypatch.setattr(mi.diagnostico_imagem, "registrar", lambda *a, **k: None)
    monkeypatch.setattr(mi.httpx, "get", lambda url, **k: _foto_ok())

    class _ClientTimeout:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            raise httpx.ReadTimeout("demorou demais")

    monkeypatch.setattr(mi.httpx, "Client", _ClientTimeout)
    with pytest.raises(FalhaInstrumento) as exc:
        MontarImagem().executar(
            ConfigMontagem(chave_api="sk-fake"),
            ArgsMontagem(prompt="t", imagens_url=["http://x/f.png"]),
        )
    assert exc.value.retentavel is False
    assert "tempo limite" in str(exc.value)


def test_quatro_por_cinco_disponivel_no_gpt_image_2():
    # 4:5 (feed do Instagram) válido no gpt-image-2; o config aceita sem erro.
    cfg = ConfigMontagem(modelo="gpt-image-2", tamanho="1024x1280", qualidade="high")
    assert cfg.tamanho == "1024x1280"


def test_chave_recusada_401(monkeypatch):
    _instalar(monkeypatch, _Resp(401, {"error": {"message": "bad key"}}))
    with pytest.raises(FalhaInstrumento, match="recusada"):
        MontarImagem().executar(
            ConfigMontagem(chave_api="sk-ruim"),
            ArgsMontagem(prompt="t", imagens_url=["http://x/f.png"]),
        )


def test_erro_de_parametro_vira_mensagem_acionavel(monkeypatch):
    resp = _Resp(
        400,
        {"error": {"message": "Invalid image.", "param": "image", "code": "invalid_value"}},
    )
    _instalar(monkeypatch, resp)
    with pytest.raises(FalhaInstrumento) as exc:
        MontarImagem().executar(
            ConfigMontagem(chave_api="sk-fake"),
            ArgsMontagem(prompt="t", imagens_url=["http://x/f.png"]),
        )
    msg = str(exc.value)
    assert "HTTP 400" in msg and "image" in msg and "invalid_value" in msg
