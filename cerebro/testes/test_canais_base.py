"""Contrato e registro do encaixe de canais de mensageria (Passo 1).

Sem provedor concreto ainda: um `TipoCanal` falso exercita o registro, a
separação de segredos e o formato normalizado de entrada — a fundação sobre a
qual Telegram (e, no futuro, WhatsApp) vão se encaixar.
"""

import pytest
from pydantic import BaseModel, Field, ValidationError

import canais as encaixe
from canais.base import Anexo, MensagemNormalizada, TipoCanal


class _ConfigFalsa(BaseModel):
    nome_bot: str = Field(default="")
    token: str = Field(default="")  # segredo


class _CanalFalso(TipoCanal):
    tipo = "_falso_teste"
    nome_exibicao = "Canal falso de teste"
    descricao = "Só para os testes do contrato."
    Config = _ConfigFalsa
    campos_secretos = ("token",)

    def enviar(self, config, destinatario, mensagem):
        return {"ok": True, "para": destinatario, "texto": mensagem}

    def normalizar(self, payload):
        if "msg" not in payload:
            return None
        return MensagemNormalizada(
            identificador_externo=str(payload["de"]),
            texto=payload.get("msg", ""),
            id_externo=str(payload["id"]),
        )


@pytest.fixture(autouse=True)
def _registrar_falso():
    encaixe.registrar(_CanalFalso())
    yield
    encaixe.base._REGISTRO.pop("_falso_teste", None)


def test_registro_e_busca():
    t = encaixe.obter_tipo("_falso_teste")
    assert isinstance(t, _CanalFalso)
    assert any(c.tipo == "_falso_teste" for c in encaixe.tipos_disponiveis())
    assert encaixe.obter_tipo("nao_existe") is None


def test_enviar_delega_ao_tipo():
    t = encaixe.obter_tipo("_falso_teste")
    r = t.enviar(_ConfigFalsa(), "chat-1", "olá")
    assert r == {"ok": True, "para": "chat-1", "texto": "olá"}


def test_normalizar_traduz_e_ignora():
    t = encaixe.obter_tipo("_falso_teste")
    m = t.normalizar({"de": 99, "msg": "oi", "id": 7})
    assert isinstance(m, MensagemNormalizada)
    assert m.identificador_externo == "99"
    assert m.texto == "oi"
    assert m.id_externo == "7"
    # Evento que não é mensagem → ignorado.
    assert t.normalizar({"foo": "bar"}) is None


def test_campos_secretos():
    assert encaixe.campos_secretos("_falso_teste") == ("token",)
    assert encaixe.campos_secretos("nao_existe") == ()


def test_preparar_config_separa_segredos():
    publica, segredos = encaixe.preparar_config(
        "_falso_teste", {"nome_bot": "Lure", "token": "abc123"}
    )
    assert publica == {"nome_bot": "Lure"}  # segredo removido da parte pública
    assert segredos == {"token": "abc123"}


def test_preparar_config_ignora_segredo_vazio():
    # Segredo omitido/vazio não entra (na edição, preserva o valor atual).
    _, segredos = encaixe.preparar_config("_falso_teste", {"nome_bot": "Lure"})
    assert segredos == {}
    _, segredos2 = encaixe.preparar_config(
        "_falso_teste", {"nome_bot": "Lure", "token": "   "}
    )
    assert segredos2 == {}


def test_preparar_config_tipo_desconhecido():
    with pytest.raises(ValueError):
        encaixe.preparar_config("nao_existe", {})


def test_mensagem_normalizada_exige_identificador_e_id():
    # identificador_externo e id_externo são obrigatórios (min_length=1).
    with pytest.raises(ValidationError):
        MensagemNormalizada(identificador_externo="", id_externo="1")
    with pytest.raises(ValidationError):
        MensagemNormalizada(identificador_externo="x", id_externo="")


def test_anexos_no_formato_normalizado():
    m = MensagemNormalizada(
        identificador_externo="42",
        id_externo="9",
        anexos=[Anexo(tipo="imagem", ref="file-123", mime="image/jpeg")],
    )
    assert m.texto == ""  # só anexo, sem texto
    assert m.anexos[0].tipo == "imagem"
    assert m.anexos[0].ref == "file-123"
