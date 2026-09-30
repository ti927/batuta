"""Gatilho WEBHOOK endurecido (2026-09-30): assinatura, tipo do aviso, eco da própria
conta, aviso repetido, filtros por campo e teto por hora — peça genérica, pensada para
serviços que avisam por webhook (redes sociais, ERPs, gateways) sem nome de fornecedor.

E o segredo da assinatura: entra pela tela (campo só de escrita), mora cifrado FORA da
config do gatilho, nunca volta numa leitura e a IA não consegue gravá-lo.
"""

import hashlib
import hmac
import json

import pytest
from sqlalchemy import select

import cofre
import webhook_entrada as regras
from criacao import servicos
from modelos import Automacao, EventoWebhook, Execucao

SEGREDO = "segredo-de-teste-123"


def _auto(sessao, dados, cfg=None, *, segredo=None, ativa=True):
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Moderar comentários", tipo_gatilho="webhook",
        configuracao_gatilho=cfg or {}, cadeia={}, ativa=ativa,
    )
    if segredo:
        auto.segredo_webhook_cifrado = cofre.cifrar(segredo)
        auto.segredo_webhook_ultimos4 = cofre.ultimos4(segredo)
    sessao.add(auto)
    sessao.flush()
    return auto


def _aviso(evento_id="ev-1", evento="comment.received", proprio=False, texto="Ótimo post!"):
    return {
        "id": evento_id,
        "event": evento,
        "comment": {
            "id": "C1", "platformPostId": "P1", "text": texto, "isReply": False,
            "author": {"id": "A1", "username": "fulano", "isOwnAccount": proprio},
        },
        "post": {"platformPostId": "P1", "content": "legenda"},
        "account": {"accountId": "ACC"},
    }


def _enviar(cliente, auto, payload, *, segredo=SEGREDO, assinar=True, cabecalhos=None):
    corpo = json.dumps(payload).encode()
    h = {"Content-Type": "application/json", **(cabecalhos or {})}
    if assinar and segredo:
        h["X-Servico-Signature"] = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return cliente.post(f"/webhooks/automacoes/{auto.id}", content=corpo, headers=h)


def _execs(sessao, auto):
    return sessao.scalars(select(Execucao).where(Execucao.automacao_id == auto.id)).all()


# ───────────────────────────── assinatura ─────────────────────────────

def test_sem_segredo_segue_aceitando_como_antes(cliente, sessao, dados):
    auto = _auto(sessao, dados)
    r = _enviar(cliente, auto, {"entrada": "oi"}, assinar=False)
    assert r.status_code == 200 and "execucao_id" in r.json()
    assert _execs(sessao, auto)[0].entrada["texto"] == "oi"


def test_com_segredo_assinatura_certa_dispara(cliente, sessao, dados):
    auto = _auto(sessao, dados, segredo=SEGREDO)
    r = _enviar(cliente, auto, _aviso())
    assert r.status_code == 200 and "execucao_id" in r.json()
    # o corpo inteiro vira a entrada: o agente lê o comentário e o post dali
    entrada = json.loads(_execs(sessao, auto)[0].entrada["texto"])
    assert entrada["comment"]["text"] == "Ótimo post!"


def test_com_segredo_assinatura_errada_ou_ausente_recusa(cliente, sessao, dados):
    auto = _auto(sessao, dados, segredo=SEGREDO)
    assert _enviar(cliente, auto, _aviso(), segredo="outro").status_code == 401
    assert _enviar(cliente, auto, _aviso("ev-2"), assinar=False).status_code == 401
    assert _execs(sessao, auto) == []


def test_assinatura_com_prefixo_sha256_e_cabecalho_configurado(cliente, sessao, dados):
    auto = _auto(sessao, dados, {"cabecalho_assinatura": "X-Assinatura"}, segredo=SEGREDO)
    corpo = json.dumps(_aviso()).encode()
    assinatura = "sha256=" + hmac.new(SEGREDO.encode(), corpo, hashlib.sha256).hexdigest()
    r = cliente.post(f"/webhooks/automacoes/{auto.id}", content=corpo,
                     headers={"X-Assinatura": assinatura})
    assert r.status_code == 200 and "execucao_id" in r.json()


# ───────────────────────────── filtros ─────────────────────────────

def test_so_o_tipo_de_aviso_escolhido_dispara(cliente, sessao, dados):
    auto = _auto(sessao, dados, {"evento": "comment.received"}, segredo=SEGREDO)
    # o aviso de teste do serviço chega, responde 200 (senão ele reenvia) e não dispara
    r = _enviar(cliente, auto, {"id": "t1", "event": "webhook.test"})
    assert r.status_code == 200 and r.json()["ignorado"] is True
    assert _enviar(cliente, auto, _aviso()).json().get("execucao_id")
    assert len(_execs(sessao, auto)) == 1


def test_aviso_da_propria_conta_nao_dispara(cliente, sessao, dados):
    """A resposta que o agente publica volta como comentário novo: sem este filtro,
    ele responderia a si mesmo em loop."""
    auto = _auto(sessao, dados, segredo=SEGREDO)
    r = _enviar(cliente, auto, _aviso(proprio=True))
    assert r.json()["ignorado"] is True and _execs(sessao, auto) == []


def test_nunca_quando_e_so_quando(cliente, sessao, dados):
    auto = _auto(sessao, dados, {
        "so_quando": [{"campo": "account.accountId", "valor": "ACC"}],
        "nunca_quando": [{"campo": "comment.isReply", "valor": True}],
    }, segredo=SEGREDO)
    resposta = _aviso("ev-r")
    resposta["comment"]["isReply"] = True
    assert _enviar(cliente, auto, resposta).json()["ignorado"] is True
    outra_conta = _aviso("ev-o")
    outra_conta["account"]["accountId"] = "OUTRA"
    assert _enviar(cliente, auto, outra_conta).json()["ignorado"] is True
    assert _enviar(cliente, auto, _aviso("ev-ok")).json().get("execucao_id")
    assert len(_execs(sessao, auto)) == 1


# ───────────────────────────── repetido e teto ─────────────────────────────

def test_aviso_repetido_dispara_uma_vez_so(cliente, sessao, dados):
    auto = _auto(sessao, dados, segredo=SEGREDO)
    assert _enviar(cliente, auto, _aviso("ev-9")).json().get("execucao_id")
    r = _enviar(cliente, auto, _aviso("ev-9"))
    assert r.status_code == 200 and r.json()["ignorado"] is True
    assert len(_execs(sessao, auto)) == 1


def test_id_do_aviso_pelo_cabecalho(cliente, sessao, dados):
    auto = _auto(sessao, dados, segredo=SEGREDO)
    for corpo_id in ("a", "b"):  # corpo diferente, mesmo id no cabeçalho
        _enviar(cliente, auto, _aviso(corpo_id), cabecalhos={"X-Servico-Event-Id": "H1"})
    assert len(_execs(sessao, auto)) == 1


def test_teto_por_hora(cliente, sessao, dados):
    auto = _auto(sessao, dados, {"teto_por_hora": 2}, segredo=SEGREDO)
    for i in range(3):
        _enviar(cliente, auto, _aviso(f"ev-{i}"))
    assert len(_execs(sessao, auto)) == 2
    assert sessao.scalar(
        select(EventoWebhook.execucao_id).where(EventoWebhook.evento_id == "ev-0")
    ) is not None


# ───────────────────────────── o segredo ─────────────────────────────

def test_segredo_pela_tela_fica_cifrado_fora_da_config(cliente, entrar, sessao, dados):
    auto = _auto(sessao, dados, ativa=False)
    entrar(dados["operador"])
    corpo = {"nome": auto.nome, "tipo_gatilho": "webhook", "cadeia": {}, "ativa": False,
             "configuracao_gatilho": {"evento": "comment.received", "segredo": "abc-123-XYZ"}}
    r = cliente.put(f"/automacoes/{auto.id}", json=corpo)
    assert r.status_code == 200
    lido = r.json()
    assert lido["configuracao_gatilho"] == {"evento": "comment.received"}
    assert lido["segredo_webhook_ultimos4"] == "-XYZ"
    assert "abc-123" not in json.dumps(lido)
    sessao.refresh(auto)
    assert cofre.decifrar(auto.segredo_webhook_cifrado) == "abc-123-XYZ"

    # salvar de novo sem o segredo (campo em branco) mantém o guardado
    corpo["configuracao_gatilho"] = {"evento": "comment.received", "segredo": ""}
    cliente.put(f"/automacoes/{auto.id}", json=corpo)
    sessao.refresh(auto)
    assert cofre.decifrar(auto.segredo_webhook_cifrado) == "abc-123-XYZ"

    # e dá para apagar
    corpo["configuracao_gatilho"] = {"remover_segredo": True}
    assert cliente.put(f"/automacoes/{auto.id}", json=corpo).json()["segredo_webhook_ultimos4"] is None


def test_ia_nao_grava_segredo(sessao, dados):
    auto = _auto(sessao, dados, segredo=SEGREDO, ativa=False)
    servicos.definir_gatilho(
        sessao, dados["timeA"], tipo_gatilho="webhook",
        configuracao_gatilho={"evento": "x", "segredo": "da-ia", "remover_segredo": True},
        automacao_id=auto.id,
    )
    assert auto.configuracao_gatilho == {"evento": "x"}
    assert cofre.decifrar(auto.segredo_webhook_cifrado) == SEGREDO  # nem troca nem apaga


def test_validacao_da_ia_recusa_segredo_e_filtro_malformado():
    from criacao.ferramentas import _validar_gatilho

    assert "consultor" in _validar_gatilho("webhook", {"segredo": "x"})
    assert _validar_gatilho("webhook", {"nunca_quando": [{"valor": 1}]})
    assert _validar_gatilho("webhook", {"evento": "comment.received", "teto_por_hora": 30,
                                        "nunca_quando": [{"campo": "a.b", "valor": True}]}) is None


@pytest.mark.parametrize("dados_aviso,esperado", [
    ({"a": {"isOwnAccount": True}}, True),
    ({"a": [{"is_echo": True}]}, True),
    ({"a": {"isOwnAccount": False}}, False),
    ({"isOwnAccount": "true"}, False),  # só booleano verdadeiro conta
])
def test_eco(dados_aviso, esperado):
    assert regras.eh_eco(dados_aviso) is esperado


def test_ia_externa_ve_o_endereco_publico(monkeypatch):
    """O serviço do MCP não tem CEREBRO_PUBLIC_URL; o endereço mostrado não pode sair
    como localhost (saiu, em 2026-09-30)."""
    import mcp_ferramentas

    monkeypatch.delenv("CEREBRO_PUBLIC_URL", raising=False)
    monkeypatch.setenv("CEREBRO_URL", "https://api.exemplo/")
    assert mcp_ferramentas._url_publica_cerebro() == "https://api.exemplo"
    monkeypatch.delenv("CEREBRO_URL")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert mcp_ferramentas._url_publica_cerebro() == "https://api.batuta.team"
