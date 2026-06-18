"""Testes do instrumento Busca na web (Tavily).

Cobrem as correções de robustez: consulta vazia é barrada com mensagem clara
(antes virava um "HTTP 400" opaco do Tavily), e o detalhe do erro do Tavily é
extraído para a mensagem ser acionável. Não fazem chamada de rede real.
"""

import httpx
import pytest

from instrumentos.base import FalhaInstrumento
from instrumentos.busca_web import (
    ArgsBuscaWeb,
    BuscaWeb,
    ConfigBuscaWeb,
    _detalhe_erro,
)


def test_consulta_vazia_barrada_sem_chamar_rede():
    inst = BuscaWeb()
    config = ConfigBuscaWeb(chave_api="qualquer")  # passa pela checagem de chave
    args = ArgsBuscaWeb(consulta="   ")  # 3 espaços: válido p/ pydantic, vazio após strip
    with pytest.raises(FalhaInstrumento) as exc:
        inst.executar(config, args)
    assert "vazia" in str(exc.value)


def test_detalhe_erro_extrai_motivo_do_json():
    resp = httpx.Response(400, json={"detail": "query too short"})
    assert _detalhe_erro(resp) == "query too short"


def test_detalhe_erro_cai_no_texto_cru():
    resp = httpx.Response(400, text="Bad Request")
    assert "Bad Request" in _detalhe_erro(resp)
