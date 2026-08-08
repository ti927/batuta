"""O instrumento "Guardar imagem recebida" (arquivar_imagem): guarda a foto que o
contato enviou (bytes vindos do contexto do turno, `midia_recebida`) e devolve a URL. O
agente decide QUANDO chamar pelo markdown; LER a imagem é automático — isto é só GUARDAR.
"""

import pytest

import instrumentos
import midia_recebida
from instrumentos.arquivar_imagem import ArgsArquivar, ArquivarImagem, ConfigArquivar
from instrumentos.base import FalhaInstrumento


def test_arquivar_guarda_do_contexto_e_devolve_url(monkeypatch):
    salvos = []
    monkeypatch.setattr(
        "arquivos.salvar",
        lambda nome, dados, ct: salvos.append((nome, ct)) or f"https://sto/{nome}",
    )
    imagens = [{"bytes": b"\xff\xd8\xffJPG", "mime": "image/jpeg", "legenda": ""}]
    with midia_recebida.usar_imagens_recebidas(imagens):
        r = ArquivarImagem().executar(ConfigArquivar(), ArgsArquivar())
    assert r["ok"] and r["quantidade"] == 1
    assert r["urls"][0].startswith("https://sto/recebida_")
    assert salvos and salvos[0][1] == "image/jpeg" and salvos[0][0].endswith(".jpg")


def test_arquivar_varias_imagens(monkeypatch):
    monkeypatch.setattr("arquivos.salvar", lambda nome, dados, ct: f"https://sto/{nome}")
    imagens = [
        {"bytes": b"\x89PNG\r\n\x1a\nA", "mime": "image/png", "legenda": ""},
        {"bytes": b"\xff\xd8\xffB", "mime": "image/jpeg", "legenda": ""},
    ]
    with midia_recebida.usar_imagens_recebidas(imagens):
        r = ArquivarImagem().executar(ConfigArquivar(), ArgsArquivar())
    assert r["quantidade"] == 2


def test_arquivar_sem_imagem_falha_claro():
    # fora de um turno de conversa (contexto vazio) → erro claro, não-retentável
    with pytest.raises(FalhaInstrumento):
        ArquivarImagem().executar(ConfigArquivar(), ArgsArquivar())


def test_arquivar_nao_exige_portao():
    # guarda no NOSSO bucket (como gerar_imagem) → não é ação irreversível (sem portão)
    assert instrumentos.acao_irreversivel("arquivar_imagem", {}) is False


def test_arquivar_resgata_quando_nao_ha_foto_fresca(monkeypatch):
    """Fallback entre turnos: sem foto fresca no turno, o `resgatar` re-baixa a imagem
    recente (pelo file_id) → o agente guarda o comprovante num turno POSTERIOR ao envio."""
    monkeypatch.setattr("arquivos.salvar", lambda nome, dados, ct: f"https://sto/{nome}")
    resgatou = {"n": 0}

    def resgatar():
        resgatou["n"] += 1
        return [{"bytes": b"\xff\xd8\xffOLD", "mime": "image/jpeg", "legenda": ""}]

    with midia_recebida.usar_imagens_recebidas([], resgatar=resgatar):
        r = ArquivarImagem().executar(ConfigArquivar(), ArgsArquivar())
    assert r["ok"] and r["quantidade"] == 1
    assert resgatou["n"] == 1  # resgatou porque não havia foto fresca


def test_arquivar_prefere_foto_fresca_sem_resgatar(monkeypatch):
    """Com foto fresca no turno, o `resgatar` NÃO é chamado (lazy — não baixa à toa)."""
    monkeypatch.setattr("arquivos.salvar", lambda nome, dados, ct: f"https://sto/{nome}")
    resgatou = {"n": 0}

    def resgatar():
        resgatou["n"] += 1
        return [{"bytes": b"X", "mime": "image/png", "legenda": ""}]

    fresca = [{"bytes": b"\xff\xd8\xffNEW", "mime": "image/jpeg", "legenda": ""}]
    with midia_recebida.usar_imagens_recebidas(fresca, resgatar=resgatar):
        r = ArquivarImagem().executar(ConfigArquivar(), ArgsArquivar())
    assert r["quantidade"] == 1
    assert resgatou["n"] == 0  # não resgatou (havia foto fresca)


def test_arquivar_resgatar_falha_volta_erro_claro():
    """Se o resgate falha (Telegram fora, file_id expirado), o instrumento avisa claro
    (não trava): o fallback engole a exceção → contexto vazio → FalhaInstrumento."""
    def resgatar():
        raise RuntimeError("telegram fora")

    with midia_recebida.usar_imagens_recebidas([], resgatar=resgatar):
        with pytest.raises(FalhaInstrumento):
            ArquivarImagem().executar(ConfigArquivar(), ArgsArquivar())
