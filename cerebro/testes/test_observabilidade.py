"""Testes da observabilidade: formatador JSON, redação de segredos, política de
persistência (incl. `local` nunca grava), best-effort (erro ao persistir não propaga),
gravação de uma linha em `evento_log`, e o controle de acesso do `GET /logs`.
"""

import json
import logging
import uuid

from sqlalchemy import select

import sessao as sessao_mod
from modelos import EventoLog
from observabilidade import contexto, escritor
from observabilidade.log import FormatadorJSON, redigir


# ───────────────────────── formatador + redação ─────────────────────────


def test_formatador_json_tem_identidade_de_servidor():
    rec = logging.LogRecord("batuta.x", logging.INFO, __file__, 1, "oi", (), None)
    d = json.loads(FormatadorJSON().format(rec))
    assert d["msg"] == "oi" and d["nivel"] == "INFO" and d["logger"] == "batuta.x"
    assert "host" in d and "pid" in d and d["ambiente"] in ("railway", "local")
    assert "ts" in d


def test_formatador_inclui_contexto_e_extras():
    with contexto.usar_contexto(request_id="req-123"):
        rec = logging.LogRecord("batuta.x", logging.INFO, __file__, 1, "acao", (), None)
        rec.categoria = "http"  # extra
        d = json.loads(FormatadorJSON().format(rec))
    assert d["request_id"] == "req-123"
    assert d["categoria"] == "http"


def test_redigir_mascara_segredos_recursivamente():
    entrada = {
        "Authorization": "Bearer abc",
        "token_bot": "xyz",
        "nome": "ok",
        "ninho": {"api_key": "z", "valor": 1},
        "lista": [{"senha": "p"}],
    }
    saida = redigir(entrada)
    assert saida["Authorization"] == "***"
    assert saida["token_bot"] == "***"
    assert saida["nome"] == "ok"  # campo comum intacto
    assert saida["ninho"]["api_key"] == "***"
    assert saida["ninho"]["valor"] == 1
    assert saida["lista"][0]["senha"] == "***"


# ───────────────────────── política de persistência ─────────────────────────


def test_deve_persistir(monkeypatch):
    monkeypatch.setattr(escritor, "EH_LOCAL", False)
    # Categorias de ação/efeito persistem mesmo em info; leitura http info, não.
    assert escritor._deve_persistir("execucao", "INFO", None) is True
    assert escritor._deve_persistir("http", "INFO", None) is False
    assert escritor._deve_persistir("http", "INFO", True) is True  # forçado
    assert escritor._deve_persistir("http", "ERROR", None) is True  # erro sempre
    # Em ambiente LOCAL, NADA persiste (banco compartilhado com produção).
    monkeypatch.setattr(escritor, "EH_LOCAL", True)
    assert escritor._deve_persistir("execucao", "ERROR", True) is False


def test_local_nunca_abre_sessao(monkeypatch):
    monkeypatch.setattr(escritor, "EH_LOCAL", True)

    def _proibido():
        raise AssertionError("não deveria tocar o banco em ambiente local")

    monkeypatch.setattr(sessao_mod, "CriadorDeSessao", _proibido)
    # Não persiste e não levanta.
    escritor.registrar_evento(categoria="execucao", acao="x", persistir=True)


def test_falha_ao_persistir_nao_propaga(monkeypatch):
    monkeypatch.setattr(escritor, "EH_LOCAL", False)

    class SessaoQuebrada:
        def add(self, *a, **k):
            pass

        def commit(self):
            raise RuntimeError("banco fora do ar")

        def close(self):
            pass

    monkeypatch.setattr(sessao_mod, "CriadorDeSessao", lambda: SessaoQuebrada())
    # Logar NUNCA pode derrubar o chamador — não deve levantar.
    escritor.registrar_evento(categoria="execucao", acao="x", persistir=True)


def test_registrar_evento_grava_linha_redigida(monkeypatch, sessao):
    monkeypatch.setattr(escritor, "EH_LOCAL", False)
    monkeypatch.setattr(sessao, "close", lambda: None)  # não fecha a sessão do teste
    monkeypatch.setattr(sessao_mod, "CriadorDeSessao", lambda: sessao)

    acao = f"teste.evento.{uuid.uuid4().hex[:8]}"
    escritor.registrar_evento(
        categoria="execucao",
        acao=acao,
        nivel="info",
        origem="fila",
        detalhe={"token": "SEGREDO", "ok": 1},
    )
    linha = sessao.scalars(select(EventoLog).where(EventoLog.acao == acao)).first()
    assert linha is not None
    assert linha.categoria == "execucao"
    assert linha.origem == "fila"
    assert linha.ambiente in ("railway", "local")
    assert linha.host  # identidade de servidor carimbada
    assert linha.detalhe["token"] == "***"  # segredo redigido
    assert linha.detalhe["ok"] == 1


def test_erro_grava_stack(monkeypatch, sessao):
    monkeypatch.setattr(escritor, "EH_LOCAL", False)
    monkeypatch.setattr(sessao, "close", lambda: None)
    monkeypatch.setattr(sessao_mod, "CriadorDeSessao", lambda: sessao)
    acao = f"teste.erro.{uuid.uuid4().hex[:8]}"
    try:
        raise ValueError("explodiu de propósito")
    except ValueError as e:
        escritor.registrar_evento(
            categoria="execucao", acao=acao, nivel="error", erro=e
        )
    linha = sessao.scalars(select(EventoLog).where(EventoLog.acao == acao)).first()
    assert linha is not None and linha.nivel == "error"
    assert "explodiu de propósito" in (linha.erro_texto or "")
    assert "Traceback" in (linha.erro_texto or "")  # stack completo, não só str(e)


# ───────────────────────── endpoint GET /logs ─────────────────────────


def test_logs_exige_admin_consultoria(cliente, entrar, dados):
    """Sem ser admin da consultoria → 403 (antes de qualquer consulta)."""
    entrar(dados["admin"])  # admin da ORG, não da consultoria
    r = cliente.get("/logs")
    assert r.status_code == 403
