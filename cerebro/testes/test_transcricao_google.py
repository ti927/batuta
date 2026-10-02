"""Transcrição dos áudios do Telegram pelo Google (2026-10-02): com a chave do Google,
ele transcreve primeiro (aceita o OGG do Telegram e não tem data para sair); se falhar
e houver chave da OpenAI, cai no Whisper — registrando a queda, nunca calado."""

import pytest

import precos
from mensageria import transcricao


def test_com_a_chave_do_google_transcreve_pelo_google(monkeypatch):
    chamadas = []
    monkeypatch.setattr(transcricao, "transcrever_google",
                        lambda audio, chave: chamadas.append(chave) or "Quero o preço")
    monkeypatch.setattr(transcricao, "transcrever", lambda *a, **k: pytest.fail("não devia ir à OpenAI"))
    texto, modelo, provedor = transcricao.transcrever_com_a_chave_que_houver(
        b"ogg", {"google": "g", "openai": "o"})
    assert (texto, modelo, provedor) == ("Quero o preço", transcricao.MODELO_GOOGLE, "google")
    assert chamadas == ["g"]


def test_google_falhou_cai_na_openai_e_registra(monkeypatch):
    eventos = []
    import observabilidade.escritor as escritor

    monkeypatch.setattr(escritor, "registrar_evento", lambda **kw: eventos.append(kw))
    monkeypatch.setattr(transcricao, "transcrever_google",
                        lambda audio, chave: (_ for _ in ()).throw(RuntimeError("sem crédito")))
    monkeypatch.setattr(transcricao, "transcrever", lambda audio, chave, **k: "pela openai")
    texto, modelo, provedor = transcricao.transcrever_com_a_chave_que_houver(
        b"ogg", {"google": "g", "openai": "o"})
    assert (texto, provedor) == ("pela openai", "openai")
    assert eventos[0]["acao"] == "transcricao.google_falhou"
    assert eventos[0]["detalhe"] == {"cai_para_openai": True}


def test_so_openai_segue_como_antes(monkeypatch):
    monkeypatch.setattr(transcricao, "transcrever", lambda audio, chave, **k: "ok")
    assert transcricao.transcrever_com_a_chave_que_houver(b"ogg", {"openai": "o"})[2] == "openai"


def test_sem_chave_nenhuma_levanta():
    with pytest.raises(RuntimeError):
        transcricao.transcrever_com_a_chave_que_houver(b"ogg", {})


def test_custo_por_minuto_de_cada_ia():
    assert precos.custo_transcricao("gemini-3.5-flash-lite", 120) == pytest.approx(0.01)
    assert precos.custo_transcricao("whisper-1", 60) == precos.PRECO_WHISPER_MIN


def test_turno_registra_a_transcricao_do_google_com_a_origem_certa(sessao, dados, monkeypatch):
    from mensageria import servico, telegram
    from modelos import MensagemConversa
    from testes.test_mensageria import _agente_com, _bot

    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    voz = telegram.MensagemEntrante("555", "João", None, {"tipo": "voz", "file_id": "F", "duracao_s": 60})
    conversa, _ = servico.registrar_entrada(sessao, inst, voz)
    monkeypatch.setattr("mensageria.telegram.baixar_arquivo", lambda token, fid: b"ogg")
    monkeypatch.setattr(transcricao, "transcrever_google", lambda audio, chave: "Oi, tudo bem?")
    usos = servico._transcrever_pendentes(
        sessao, conversa, "tok", {"google": "g"}, {"google": "consultoria"})
    assert usos == [{
        "modelo": transcricao.MODELO_GOOGLE, "segundos": 60, "custo_usd": 0.005,
        "origem": "consultoria", "categoria": "transcricao",
    }]
    msg = sessao.query(MensagemConversa).filter_by(conversa_id=conversa.id).one()
    assert msg.conteudo == "Oi, tudo bem?" and msg.midia["transcrito"] is True
