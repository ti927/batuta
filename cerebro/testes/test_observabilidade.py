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

    monkeypatch.setattr(sessao_mod, "CriadorDeSessaoDoLog", _proibido)
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

    monkeypatch.setattr(sessao_mod, "CriadorDeSessaoDoLog", lambda: SessaoQuebrada())
    # Logar NUNCA pode derrubar o chamador — não deve levantar.
    escritor.registrar_evento(categoria="execucao", acao="x", persistir=True)


def test_registrar_evento_grava_linha_redigida(monkeypatch, sessao):
    monkeypatch.setattr(escritor, "EH_LOCAL", False)
    monkeypatch.setattr(sessao, "close", lambda: None)  # não fecha a sessão do teste
    monkeypatch.setattr(sessao_mod, "CriadorDeSessaoDoLog", lambda: sessao)

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
    monkeypatch.setattr(sessao_mod, "CriadorDeSessaoDoLog", lambda: sessao)
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


# ───── pool esgotado (incidente de 2026-10-10): o log não disputa conexão com quem loga ─────


def test_evento_grava_mesmo_com_o_pool_do_trabalho_cheio(monkeypatch):
    """14 leituras de links de quadro travaram o pool: cada uma segurava uma conexão e
    pedia OUTRA ao mesmo pool para gravar o evento da leitura. Aqui o pool do trabalho
    fica 100% ocupado por quem loga — e o evento precisa gravar na hora, sem esperar."""
    import time

    from sqlalchemy import create_engine, delete

    from db import _CONNECT_ARGS, _url, engine, engine_log

    assert sessao_mod.CriadorDeSessaoDoLog.kw["bind"] is engine_log is not engine
    monkeypatch.setattr(escritor, "EH_LOCAL", False)
    apertado = create_engine(_url, pool_size=1, max_overflow=0, pool_timeout=1,
                             connect_args=_CONNECT_ARGS)
    monkeypatch.setattr(sessao_mod.CriadorDeSessao, "kw", {**sessao_mod.CriadorDeSessao.kw, "bind": apertado})
    acao = f"teste.pool_cheio.{uuid.uuid4().hex[:8]}"
    try:
        with apertado.connect():  # a "requisição" segura a única conexão do pool
            inicio = time.perf_counter()
            escritor.registrar_evento(categoria="execucao", acao=acao, persistir=True)
            assert time.perf_counter() - inicio < 1  # não esperou o pool do trabalho
        with engine_log.connect() as c:
            assert c.scalar(select(EventoLog.id).where(EventoLog.acao == acao)) is not None
    finally:
        with engine_log.begin() as c:
            c.execute(delete(EventoLog).where(EventoLog.acao == acao))
        apertado.dispose()


def test_pool_esgotado_responde_503_com_tente_de_novo(cliente, monkeypatch):
    """Sem conexão livre: 503 + Retry-After e frase humana, em vez de pendurar até o
    proxy cortar. Na leitura pública, no formato e com o CORS dela (o painel lê)."""
    from sqlalchemy.exc import TimeoutError as TimeoutDoPool

    import main
    from quadros import links

    def _esgotado(*a, **k):
        raise TimeoutDoPool("QueuePool limit of size 5 overflow 7 reached")

    eventos = []
    monkeypatch.setattr(links, "abrir", _esgotado)
    monkeypatch.setattr(main, "registrar_evento", lambda **k: eventos.append(k))
    r = cliente.get("/publico/quadros/bq_qualquer?formato=json")
    assert r.status_code == 503
    assert r.headers["retry-after"] == "5"
    assert r.headers["access-control-allow-origin"] == "*"
    assert "Tente de novo em alguns segundos" in r.json()["erro"]
    assert eventos and eventos[0]["acao"] == "banco.pool_esgotado" and eventos[0]["nivel"] == "error"
