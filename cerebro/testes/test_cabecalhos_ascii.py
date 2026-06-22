"""Cabeçalhos HTTP só aceitam ASCII.

Regressão da exec f694cf0c: um instrumento de webhook estava com `titulo`/`legenda`/
`subtitulo` (valores acentuados, ex.: "Seu título aqui") colados nos CABEÇALHOS por
engano. O httpx codifica valor de cabeçalho em ascii e a chamada estourava
`'ascii' codec can't encode character '\\xed' in position 5` — um erro que NÃO é
`httpx.HTTPError` e escapava o tratamento, derrubando a execução com mensagem
críptica. Agora `validar_cabecalhos_ascii` falha CEDO, CLARO e não-retentável,
apontando que texto com acento vai no CORPO (payload), não nos cabeçalhos.
"""

import pytest

from instrumentos.base import FalhaInstrumento, validar_cabecalhos_ascii
from instrumentos.rest import ArgsRest, ChamarApiRest, ConfigRest
from instrumentos.webhook_saida import ArgsWebhook, ConfigWebhook, DispararWebhook


def test_helper_aceita_ascii():
    # não levanta nada
    validar_cabecalhos_ascii({"Content-Type": "application/json", "X-Token": "abc123"})
    validar_cabecalhos_ascii({})
    validar_cabecalhos_ascii(None)


def test_helper_recusa_acento_no_valor():
    with pytest.raises(FalhaInstrumento) as ei:
        validar_cabecalhos_ascii({"titulo": "Seu título aqui"})
    assert ei.value.retentavel is False
    assert "ASCII" in str(ei.value) and "payload" in str(ei.value)


def test_helper_recusa_acento_no_nome():
    with pytest.raises(FalhaInstrumento):
        validar_cabecalhos_ascii({"infração": "x"})


def test_webhook_falha_claro_com_cabecalho_acentuado():
    # Falha ANTES da chamada HTTP (sem rede): o validador roda primeiro.
    inst = DispararWebhook()
    with pytest.raises(FalhaInstrumento) as ei:
        inst.executar(
            ConfigWebhook(url="https://x", cabecalhos={"titulo": "Seu título aqui"}),
            ArgsWebhook(payload={"ok": True}),
        )
    assert ei.value.retentavel is False


def test_rest_falha_claro_com_cabecalho_acentuado():
    inst = ChamarApiRest()
    with pytest.raises(FalhaInstrumento) as ei:
        inst.executar(
            ConfigRest(url="https://x", metodo="POST", cabecalhos={"x": "abç"}),
            ArgsRest(corpo={"ok": True}),
        )
    assert ei.value.retentavel is False
