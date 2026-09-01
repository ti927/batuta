"""O instrumento "Pedir aprovação e aguardar" — a espera por uma pessoa, no cinto.

Substituiu o PORTÃO (um interruptor no nó do desenho) e a PAREDE (uma trava da
organização). Quem decide que um momento precisa de gente é o agente, chamando este
instrumento porque o markdown dele manda.

Aqui: o envio pelo canal referenciado, os erros que precisam ser honestos (canal que
sumiu, canal sem destinatário, envio recusado) e o modo só-tela.
"""

import uuid

import pytest

import instrumentos as encaixe
from instrumentos.base import FalhaInstrumento
from instrumentos import pedir_aprovacao as mod
from modelos import Instrumento

TIPO = "pedir_aprovacao"


def _cfg(**kw):
    return encaixe.obter_tipo(TIPO).Config.model_validate(kw)


def _args(mensagem="Aprova a capa?"):
    return encaixe.obter_tipo(TIPO).Args.model_validate({"mensagem": mensagem})


def test_esta_no_catalogo_e_para_para_humano():
    tipo = encaixe.obter_tipo(TIPO)
    assert tipo is not None
    assert tipo.pausa_para_humano is True
    assert tipo.campo_mensagem == "mensagem"
    # manda mensagem para fora → ação irreversível (política de falha do PRODUTO §16)
    assert encaixe.acao_irreversivel(TIPO, {}) is True


def test_sem_canal_aprova_pela_tela():
    r = encaixe.obter_tipo(TIPO).executar(_cfg(), _args("Confere isto"))
    assert r["ok"] is True
    assert r["aguardando_aprovacao"] is True
    assert r["onde"] == "tela"
    assert r["mensagem"] == "Confere isto"
    assert "canal_instrumento_id" not in r  # nada a amarrar: a resposta vem da tela


def test_canal_mal_configurado_falha_com_recado_util():
    with pytest.raises(FalhaInstrumento) as e:
        encaixe.obter_tipo(TIPO).executar(_cfg(canal_instrumento_id="nao-e-uuid"), _args())
    assert "configuração do instrumento" in str(e.value)
    assert e.value.retentavel is False


def _com_canal(sessao, dados, monkeypatch, *, destinatario="999", ok=True):
    """Cria um canal real e faz o instrumento usar ESTA sessão de teste."""
    canal = Instrumento(
        time_id=dados["timeA"].id, nome="Bot", tipo="enviar_telegram",
        configuracao={"destinatario_padrao": destinatario},
    )
    sessao.add(canal)
    sessao.flush()
    monkeypatch.setattr(mod, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        mod.segredos_instrumento, "decifrar", lambda s, i: {"token_bot": "T"}
    )
    enviados: list = []

    def envio(config, args):
        enviados.append((config.destinatario_padrao, args.mensagem))
        return {"ok": ok, "descricao": None if ok else "chat not found"}

    monkeypatch.setattr(encaixe.obter_tipo("enviar_telegram"), "executar", envio)
    return canal, enviados


class _SessaoFake:
    """Devolve a sessão do teste e ignora o `close()` (a transação é do pytest)."""

    def __init__(self, real):
        self._real = real

    def get(self, *a, **k):
        return self._real.get(*a, **k)

    def close(self):
        pass


def test_envia_pelo_canal_e_devolve_quem_responde(sessao, dados, monkeypatch):
    canal, enviados = _com_canal(sessao, dados, monkeypatch)
    r = encaixe.obter_tipo(TIPO).executar(
        _cfg(canal_instrumento_id=str(canal.id)), _args("Aprova a capa?")
    )
    assert enviados == [("999", "Aprova a capa?")]
    assert r["onde"] == "canal"
    assert r["canal_instrumento_id"] == str(canal.id)
    # quem responde é o destinatário do canal — FONTE ÚNICA com quem recebeu o pedido
    assert r["destinatario"] == "999"


def test_canal_sem_destinatario_falha_explicando(sessao, dados, monkeypatch):
    canal, _ = _com_canal(sessao, dados, monkeypatch, destinatario="")
    with pytest.raises(FalhaInstrumento) as e:
        encaixe.obter_tipo(TIPO).executar(
            _cfg(canal_instrumento_id=str(canal.id)), _args()
        )
    assert "não tem destinatário" in str(e.value)
    assert "de quem esperar a resposta" in str(e.value)


def test_envio_recusado_nao_vira_espera_silenciosa(sessao, dados, monkeypatch):
    """Se o pedido não chegou a ninguém, esperar seria esperar para sempre."""
    canal, _ = _com_canal(sessao, dados, monkeypatch, ok=False)
    with pytest.raises(FalhaInstrumento) as e:
        encaixe.obter_tipo(TIPO).executar(
            _cfg(canal_instrumento_id=str(canal.id)), _args()
        )
    assert "não chegou a ninguém" in str(e.value)
    assert "chat not found" in str(e.value)


def test_canal_que_sumiu_falha_com_recado_util(sessao, dados, monkeypatch):
    monkeypatch.setattr(mod, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    with pytest.raises(FalhaInstrumento) as e:
        encaixe.obter_tipo(TIPO).executar(
            _cfg(canal_instrumento_id=str(uuid.uuid4())), _args()
        )
    assert "não existe mais" in str(e.value)
    assert e.value.retentavel is False


def test_canal_que_nao_e_de_mensageria_e_recusado(sessao, dados, monkeypatch):
    outro = Instrumento(
        time_id=dados["timeA"].id, nome="Busca", tipo="busca_web", configuracao={}
    )
    sessao.add(outro)
    sessao.flush()
    monkeypatch.setattr(mod, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    with pytest.raises(FalhaInstrumento) as e:
        encaixe.obter_tipo(TIPO).executar(
            _cfg(canal_instrumento_id=str(outro.id)), _args()
        )
    assert "não é um canal de mensageria" in str(e.value)
