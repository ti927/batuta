"""Testes do feedback ao vivo de execução ("o que está acontecendo agora").

Cobrem o sinal (ContextVar `usar_atividade`/`registrar` + mapa de mensagens), o
escritor real (`disparo._escrever_atividade`, que grava numa sessão própria e só
enquanto `em_andamento`) e a limpeza ao sair de `em_andamento`
(`disparo._aplicar_resultado`). Sem rede; o "escritor" é dublê ou a própria sessão
do teste (transação revertida)."""

import uuid
from datetime import datetime, timezone

import orquestracao.atividade as atividade
import orquestracao.disparo as disparo
from modelos import Automacao, Execucao


def _exec(sessao, dados, estado="em_andamento"):
    au = Automacao(
        time_id=dados["timeA"].id, nome="A", tipo_gatilho="webhook", cadeia=[], ativa=True
    )
    sessao.add(au)
    sessao.flush()
    ex = Execucao(automacao_id=au.id, estado=estado, entrada={"texto": "x"})
    sessao.add(ex)
    sessao.flush()
    return ex


# ───────────────────────── sinal (ContextVar) ─────────────────────────


def test_registrar_sem_sink_e_noop():
    # Fora de um bloco `usar_atividade`, não faz nada e não levanta.
    atividade.registrar("oi")


def test_usar_atividade_fixa_e_limpa_o_escritor():
    recebidos: list[str] = []
    with atividade.usar_atividade(recebidos.append):
        atividade.registrar("montando…")
    assert recebidos == ["montando…"]
    # Fora do bloco, volta a ser no-op (não vaza para a próxima execução).
    atividade.registrar("nada")
    assert recebidos == ["montando…"]


def test_registrar_engole_erro_do_escritor():
    def explode(_):
        raise RuntimeError("boom")

    with atividade.usar_atividade(explode):
        atividade.registrar("x")  # best-effort: não propaga


def test_mensagem_para_mapa_e_fallback():
    assert "imagem" in atividade.mensagem_para("montar_imagem", "Foto")
    assert atividade.mensagem_para("tipo_desconhecido", "MeuInst") == "Usando MeuInst…"


# ───────────────────────── escritor real ─────────────────────────


def test_escrever_atividade_grava_em_andamento(monkeypatch, sessao, dados):
    monkeypatch.setattr(sessao, "close", lambda: None)
    monkeypatch.setattr(disparo, "CriadorDeSessao", lambda: sessao)
    ex = _exec(sessao, dados, estado="em_andamento")
    disparo._escrever_atividade(ex.id, "Montando a imagem…")
    sessao.refresh(ex)
    assert ex.atividade == "Montando a imagem…" and ex.atividade_em is not None


def test_escrever_atividade_ignora_finalizada(monkeypatch, sessao, dados):
    # Guarda: não ressuscita atividade numa execução que já saiu de `em_andamento`.
    monkeypatch.setattr(sessao, "close", lambda: None)
    monkeypatch.setattr(disparo, "CriadorDeSessao", lambda: sessao)
    ex = _exec(sessao, dados, estado="concluida")
    disparo._escrever_atividade(ex.id, "não deveria")
    sessao.refresh(ex)
    assert ex.atividade is None


# ───────────────────────── limpeza ─────────────────────────


def test_aplicar_resultado_zera_atividade():
    ex = Execucao(
        automacao_id=uuid.uuid4(),
        estado="em_andamento",
        atividade="Montando a imagem…",
        atividade_em=datetime.now(timezone.utc),
    )
    disparo._aplicar_resultado(ex, {"estado": "concluida", "resultado": "pronto"})
    assert ex.estado == "concluida"
    assert ex.atividade is None and ex.atividade_em is None
