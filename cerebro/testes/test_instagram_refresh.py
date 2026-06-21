"""Testes da renovação automática dos tokens do Instagram (Fase 1).

Cobrem o núcleo `agendador.renovar_tokens_instagram(sessao)`: renova só o que está
perto de expirar, ignora token longe do fim e outros tipos, e isola a falha de uma
credencial (commit por credencial). O `instagram_tokens.renovar` é dublado — sem rede.
"""

import uuid
from datetime import datetime, timedelta, timezone

import agendador
import credenciais_cofre as cc
from modelos import Credencial


def _cred_ig(sessao, *, token, dias_para_expirar, tipo="instagram"):
    cred = Credencial(organizacao_id=None, nome=f"IG-{uuid.uuid4().hex[:8]}", tipo=tipo)
    cc.gravar(cred, {"token": token, "ig_user_id": "123"})
    cred.expira_em = datetime.now(timezone.utc) + timedelta(days=dias_para_expirar)
    sessao.add(cred)
    sessao.commit()  # baseline (savepoint) — o rollback do job não desfaz o setup
    return cred


def test_renova_credencial_perto_de_expirar(sessao, monkeypatch):
    cred = _cred_ig(sessao, token="TOKVELHO1", dias_para_expirar=5)
    monkeypatch.setattr(
        "instagram_tokens.renovar",
        lambda token: {
            "token": "TOKNOVO",
            "expira_em": datetime.now(timezone.utc) + timedelta(days=60),
        },
    )
    assert agendador.renovar_tokens_instagram(sessao) == 1
    saco = cc.decifrar(sessao.get(Credencial, cred.id))
    assert saco["token"] == "TOKNOVO"
    assert saco["ig_user_id"] == "123"  # preservado
    assert sessao.get(Credencial, cred.id).expira_em > datetime.now(timezone.utc) + timedelta(days=59)


def test_ignora_token_longe_de_expirar(sessao, monkeypatch):
    cred = _cred_ig(sessao, token="TOKVELHO2", dias_para_expirar=30)

    def _boom(token):
        raise AssertionError("não deve renovar token longe de expirar")

    monkeypatch.setattr("instagram_tokens.renovar", _boom)
    assert agendador.renovar_tokens_instagram(sessao) == 0
    assert cc.decifrar(sessao.get(Credencial, cred.id))["token"] == "TOKVELHO2"


def test_ignora_outros_tipos(sessao, monkeypatch):
    # Mesmo perto de expirar, um tipo != instagram não é tocado pelo job.
    cred = Credencial(organizacao_id=None, nome=f"TG-{uuid.uuid4().hex[:8]}", tipo="telegram_bot")
    cc.gravar(cred, {"token_bot": "bot12345"})
    cred.expira_em = datetime.now(timezone.utc) + timedelta(days=2)
    sessao.add(cred)
    sessao.commit()

    def _boom(token):
        raise AssertionError("não deve renovar credencial de outro tipo")

    monkeypatch.setattr("instagram_tokens.renovar", _boom)
    assert agendador.renovar_tokens_instagram(sessao) == 0


def test_falha_em_uma_nao_derruba_as_outras(sessao, monkeypatch):
    ok = _cred_ig(sessao, token="OKTOKEN1", dias_para_expirar=3)
    falha = _cred_ig(sessao, token="FAILTOKEN", dias_para_expirar=3)

    def _renovar(token):
        if "FAIL" in token:
            raise RuntimeError("o Instagram caiu para esta")
        return {
            "token": "RENOVADO",
            "expira_em": datetime.now(timezone.utc) + timedelta(days=60),
        }

    monkeypatch.setattr("instagram_tokens.renovar", _renovar)
    assert agendador.renovar_tokens_instagram(sessao) == 1
    assert cc.decifrar(sessao.get(Credencial, ok.id))["token"] == "RENOVADO"
    assert cc.decifrar(sessao.get(Credencial, falha.id))["token"] == "FAILTOKEN"  # intacto
