"""Parte A da economia da IA criadora: resumo rolante (`criacao/resumo.py`).

Testa a manutenção do resumo com o modelo MOCKADO — sem LLM real. Cobre: não dobrar
dentro da janela, dobrar e avançar `resumo_ate` quando estoura, ser incremental sobre o
resumo atual, e NUNCA levantar (auxiliar best-effort)."""
from types import SimpleNamespace

from langchain_core.messages import AIMessage

import criacao.resumo as resumo_mod
from criacao.resumo import JANELA_MSGS, manter_resumo


def _modelo_fake(texto):
    return SimpleNamespace(invoke=lambda entrada: AIMessage(content=texto))


def _conversa(n_turnos, resumo=None, resumo_ate=0):
    msgs = []
    for i in range(n_turnos):
        msgs.append({"papel": "usuario", "conteudo": f"pergunta {i}"})
        msgs.append({"papel": "ia", "conteudo": f"resposta {i}"})
    return SimpleNamespace(id="c1", mensagens=msgs, resumo=resumo, resumo_ate=resumo_ate)


def test_nao_resume_dentro_da_janela(monkeypatch):
    chamadas = {"n": 0}

    def _construir(*a, **k):
        chamadas["n"] += 1
        return _modelo_fake("x")

    monkeypatch.setattr(resumo_mod, "construir_modelo", _construir)
    c = _conversa(JANELA_MSGS // 2)  # exatamente a janela (16 msgs) → nada a dobrar
    assert manter_resumo(c) is False
    assert c.resumo_ate == 0 and chamadas["n"] == 0  # nem chegou a chamar o modelo


def test_resume_e_avanca_quando_estoura(monkeypatch):
    monkeypatch.setattr(resumo_mod, "construir_modelo", lambda *a, **k: _modelo_fake("RESUMO NOVO"))
    c = _conversa(12)  # 24 msgs; janela 16 → dobra os 8 primeiros (4 turnos)
    assert manter_resumo(c) is True
    assert c.resumo == "RESUMO NOVO"
    assert c.resumo_ate == 8  # 24 - 16, na fronteira de par (turno = consultor+IA)
    # A próxima janela é mensagens[8:] (16 msgs) — cabe, não dobra de novo.
    assert manter_resumo(c) is False


def test_incrementa_sobre_o_resumo_existente(monkeypatch):
    capt = {}

    def _construir(*a, **k):
        def inv(entrada):
            capt["entrada"] = entrada
            return AIMessage(content="RESUMO 2")
        return SimpleNamespace(invoke=inv)

    monkeypatch.setattr(resumo_mod, "construir_modelo", _construir)
    c = _conversa(12, resumo="RESUMO 1")
    manter_resumo(c)
    assert "RESUMO 1" in capt["entrada"]  # incremental: parte do resumo atual
    assert c.resumo == "RESUMO 2"


def test_manter_resumo_nunca_levanta(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("falha do modelo")

    monkeypatch.setattr(resumo_mod, "construir_modelo", _boom)
    c = _conversa(12)
    assert manter_resumo(c) is False  # engoliu a falha
    assert c.resumo_ate == 0 and c.resumo is None  # e não mexeu na conversa
