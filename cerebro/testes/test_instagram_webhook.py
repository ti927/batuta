"""Testes do webhook de COMENTÁRIOS do Instagram (GAP 2).

Cobrem a BORDA do receptor: assinatura `X-Hub-Signature-256` e handshake de
verificação (camada HTTP), e — chamando `processar_entrada` direto, sem depender
do timing da BackgroundTask — o dedupe por (comment_id, automacao_id), o anti-loop
(resposta da própria conta e resposta aninhada), o fan-out por organização+conta+
filtros, o teto/hora, a resolução de conta inexistente e o bloco de entrada.

O receptor abre a própria sessão via `CriadorDeSessao`; monkeypatchamos para reusar
a sessão do teste (revertida ao fim), como faz a mensageria.
"""

import hashlib
import hmac
import json

import pytest
from sqlalchemy import select

import instagram_webhook as ig
from modelos import Automacao, Credencial, EventoComentarioInstagram, Execucao
from rotas import instagram_webhook as rota_ig

SEGREDO = "app-secret-de-teste"
IGID = "17841400000000001"


class _SessaoFake:
    """Reusa a sessão do teste e ignora close() — o receptor abre a própria sessão
    e precisa operar sobre os mesmos dados para o teste conferir depois."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


@pytest.fixture
def ambiente(sessao, dados, monkeypatch):
    """Credencial instagram (ig_user_id=IGID) na orgA + fábrica de automações com
    gatilho de comentário. Monkeypatcha o app secret e a sessão do receptor."""
    monkeypatch.setenv("INSTAGRAM_APP_SECRET", SEGREDO)
    monkeypatch.setattr(rota_ig, "CriadorDeSessao", lambda: _SessaoFake(sessao))

    cred = Credencial(
        organizacao_id=dados["orgA"].id,
        nome="Instagram: @conta",
        tipo="instagram",
        dados_cifrado="",
        resumo={"ig_user_id": {"valor": IGID, "secreto": False}},
    )
    sessao.add(cred)
    sessao.flush()

    def nova_auto(nome, cfg, *, ativa=True):
        a = Automacao(
            time_id=dados["timeA"].id,
            nome=nome,
            tipo_gatilho="comentario_instagram",
            configuracao_gatilho=cfg,
            cadeia={},
            ativa=ativa,
        )
        sessao.add(a)
        sessao.flush()
        return a

    return {"cred": cred, "nova_auto": nova_auto, "sessao": sessao}


# ───────────────────────────── helpers ──────────────────────────────


def _payload(
    comment_id,
    *,
    ig_user_id=IGID,
    media_id="MEDIA1",
    texto="Vocês entregam?",
    autor_id="55501",
    autor_nome="cliente",
    parent_id=None,
):
    value = {
        "id": comment_id,
        "text": texto,
        "media": {"id": media_id},
        "from": {"id": autor_id, "username": autor_nome},
    }
    if parent_id:
        value["parent_id"] = parent_id
    return {
        "object": "instagram",
        "entry": [{"id": ig_user_id, "changes": [{"field": "comments", "value": value}]}],
    }


def _corpo(payload):
    return json.dumps(payload).encode("utf-8")


def _assinar(corpo, secret=SEGREDO):
    return "sha256=" + hmac.new(secret.encode(), corpo, hashlib.sha256).hexdigest()


def _entregar(payload):
    """Simula a chegada do webhook: chama o processamento de segundo plano direto."""
    rota_ig.processar_entrada(_corpo(payload))


def _execs(sessao, automacao_id):
    return sessao.scalars(
        select(Execucao).where(Execucao.automacao_id == automacao_id)
    ).all()


# ─────────────────────────── camada HTTP ────────────────────────────


def test_post_assinatura_invalida_403(cliente, ambiente):
    ambiente["nova_auto"]("A", {"credencial_id": str(ambiente["cred"].id), "midias": "todas"})
    corpo = _corpo(_payload("C1"))
    r = cliente.post(
        "/instagram/webhook",
        content=corpo,
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "Content-Type": "application/json"},
    )
    assert r.status_code == 403


def test_post_sem_assinatura_403(cliente, ambiente):
    corpo = _corpo(_payload("C1"))
    r = cliente.post(
        "/instagram/webhook", content=corpo, headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 403


def test_post_valido_200_e_dispara(cliente, ambiente):
    auto = ambiente["nova_auto"](
        "A", {"credencial_id": str(ambiente["cred"].id), "midias": "todas"}
    )
    corpo = _corpo(_payload("C1"))
    r = cliente.post(
        "/instagram/webhook",
        content=corpo,
        headers={"X-Hub-Signature-256": _assinar(corpo), "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    # a BackgroundTask do TestClient roda antes do retorno → a execução já existe
    assert len(_execs(ambiente["sessao"], auto.id)) == 1


def test_handshake_ok(cliente, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "TOK")
    r = cliente.get(
        "/instagram/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "TOK", "hub.challenge": "1234"},
    )
    assert r.status_code == 200
    assert r.text == "1234"


def test_handshake_token_errado_403(cliente, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "TOK")
    r = cliente.get(
        "/instagram/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "ERRADO", "hub.challenge": "1234"},
    )
    assert r.status_code == 403


# ───────────────────── lógica (processar_entrada) ───────────────────


def test_dedupe_reentrega(ambiente):
    auto = ambiente["nova_auto"]("A", {"credencial_id": str(ambiente["cred"].id), "midias": "todas"})
    _entregar(_payload("MESMO"))
    _entregar(_payload("MESMO"))  # a Meta reentregou
    assert len(_execs(ambiente["sessao"], auto.id)) == 1
    eventos = ambiente["sessao"].scalars(
        select(EventoComentarioInstagram).where(
            EventoComentarioInstagram.automacao_id == auto.id
        )
    ).all()
    assert len(eventos) == 1
    assert eventos[0].execucao_id is not None  # vínculo comentário→execução gravado


def test_ignora_resposta_da_propria_conta(ambiente):
    auto = ambiente["nova_auto"]("A", {"credencial_id": str(ambiente["cred"].id), "midias": "todas"})
    _entregar(_payload("C1", autor_id=IGID))  # autor == a própria conta (eco)
    assert _execs(ambiente["sessao"], auto.id) == []


def test_ignora_resposta_aninhada(ambiente):
    auto = ambiente["nova_auto"]("A", {"credencial_id": str(ambiente["cred"].id), "midias": "todas"})
    _entregar(_payload("C1", parent_id="PARENT"))  # resposta a outro comentário
    assert _execs(ambiente["sessao"], auto.id) == []


def test_comentario_de_topo_sem_from_processa(ambiente):
    auto = ambiente["nova_auto"]("A", {"credencial_id": str(ambiente["cred"].id), "midias": "todas"})
    payload = _payload("C1")
    payload["entry"][0]["changes"][0]["value"].pop("from")  # Meta omitiu o autor
    rota_ig.processar_entrada(_corpo(payload))
    assert len(_execs(ambiente["sessao"], auto.id)) == 1


def test_fanout_so_as_que_casam(ambiente):
    cid = str(ambiente["cred"].id)
    a_todas = ambiente["nova_auto"]("todas", {"credencial_id": cid, "midias": "todas"})
    a_post = ambiente["nova_auto"]("post", {"credencial_id": cid, "midias": ["MEDIA1"]})
    a_outro = ambiente["nova_auto"]("outro", {"credencial_id": cid, "midias": ["OUTRO"]})
    a_palavra = ambiente["nova_auto"](
        "palavra", {"credencial_id": cid, "midias": "todas", "palavra_chave": "preço"}
    )
    a_inativa = ambiente["nova_auto"](
        "inativa", {"credencial_id": cid, "midias": "todas"}, ativa=False
    )
    _entregar(_payload("C1", media_id="MEDIA1", texto="Vocês entregam?"))
    s = ambiente["sessao"]
    assert len(_execs(s, a_todas.id)) == 1       # casa: todas
    assert len(_execs(s, a_post.id)) == 1        # casa: media MEDIA1
    assert _execs(s, a_outro.id) == []           # não casa: outro post
    assert _execs(s, a_palavra.id) == []         # não casa: sem "preço"
    assert _execs(s, a_inativa.id) == []         # inativa não dispara


def test_entrada_carrega_comment_id_e_instrumento(ambiente):
    auto = ambiente["nova_auto"]("A", {"credencial_id": str(ambiente["cred"].id), "midias": "todas"})
    _entregar(_payload("COMENT-XYZ", media_id="M9", autor_nome="joao"))
    exe = _execs(ambiente["sessao"], auto.id)[0]
    texto = exe.entrada["texto"]
    assert "COMENT-XYZ" in texto and "M9" in texto and "@joao" in texto
    assert "instagram_responder_comentario" in texto


def test_gatilho_sem_conta_nao_dispara(ambiente):
    # cópia duplicada nasce "a conectar" (sem credencial_id) → nunca casa
    auto = ambiente["nova_auto"]("copia", {"midias": "todas"})
    _entregar(_payload("C1"))
    assert _execs(ambiente["sessao"], auto.id) == []


def test_teto_por_hora(ambiente):
    auto = ambiente["nova_auto"](
        "A", {"credencial_id": str(ambiente["cred"].id), "midias": "todas", "teto_por_hora": 2}
    )
    for i in range(3):
        _entregar(_payload(f"C{i}"))
    assert len(_execs(ambiente["sessao"], auto.id)) == 2  # o 3º estourou o teto


def test_conta_nao_conectada_ignora(ambiente):
    auto = ambiente["nova_auto"]("A", {"credencial_id": str(ambiente["cred"].id), "midias": "todas"})
    _entregar(_payload("C1", ig_user_id="99999_desconhecida"))
    assert _execs(ambiente["sessao"], auto.id) == []


# ───────────────────────── helpers puros ────────────────────────────


def test_montar_entrada_sem_autor():
    bloco = ig.montar_entrada(
        {"comment_id": "C1", "media_id": "M1", "texto": "oi", "autor_nome": None}
    )
    assert "C1" in bloco and "(não informado)" in bloco
    assert "instagram_responder_comentario" in bloco


def test_extrair_ignora_campo_diferente():
    corpo = {
        "object": "instagram",
        "entry": [{"id": IGID, "changes": [{"field": "mentions", "value": {"id": "X"}}]}],
    }
    assert ig.extrair_comentarios(corpo) == []


def test_verificar_assinatura(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_APP_SECRET", SEGREDO)
    corpo = b'{"ok": true}'
    assert ig.verificar_assinatura(corpo, _assinar(corpo)) is True
    assert ig.verificar_assinatura(corpo, "sha256=errado") is False
    assert ig.verificar_assinatura(corpo, None) is False
