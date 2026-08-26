"""Saída HTTP resiliente a rota (queda para IPv4) e com erro humano.

Origem: 3ª bateria do teste do MCP (2026-08-26). A mesma chamada ao ViaCEP que
respondera 200 no dia anterior passou a morrer com `[Errno 101] Network is
unreachable`, enquanto `api.github.com` respondia normalmente no mesmo conector —
a diferença é que o ViaCEP publica endereço IPv6 e o GitHub não.
"""

import httpx
import pytest

import http_saida


def test_reconhece_falha_de_rota_e_ignora_o_resto():
    assert http_saida.falha_de_rota(Exception("[Errno 101] Network is unreachable"))
    assert http_saida.falha_de_rota(Exception("[Errno 113] No route to host"))
    # DNS, recusa e timeout NÃO são rota: repetir por IPv4 não mudaria nada.
    assert not http_saida.falha_de_rota(Exception("[Errno -2] Name or service not known"))
    assert not http_saida.falha_de_rota(Exception("[Errno 111] Connection refused"))
    assert not http_saida.falha_de_rota(httpx.ReadTimeout("timed out"))


def test_mensagem_de_rede_nomeia_o_host_e_explica():
    msg = http_saida.mensagem_de_rede(
        "https://viacep.com.br/ws/01311300/json/",
        httpx.ConnectError("[Errno 101] Network is unreachable"),
    )
    assert "viacep.com.br" in msg
    assert "IPv4" in msg  # diz que a queda foi tentada — não é um "tente de novo" vago
    assert "Errno 101" in msg  # o detalhe técnico continua, no fim


def test_mensagem_comum_para_erro_que_nao_e_de_rota():
    msg = http_saida.mensagem_de_rede("https://x.com", httpx.ReadTimeout("timed out"))
    assert msg.startswith("não foi possível chamar https://x.com")


def test_queda_para_ipv4_refaz_a_chamada(monkeypatch):
    """Falha de rota → uma segunda tentativa amarrada a IPv4, e o resultado dela
    é o que volta. O caminho feliz não passa por aqui."""
    tentativas = []

    def handle(self, request):
        # `local_address` é o que distingue o transporte de queda do normal.
        tentativas.append(getattr(self, "_local_address_teste", None))
        if tentativas[-1] != "0.0.0.0":
            raise httpx.ConnectError("[Errno 101] Network is unreachable")
        return httpx.Response(200, text="ok pelo IPv4")

    def init(self, *a, cert=None, local_address=None, **k):
        self._local_address_teste = local_address

    monkeypatch.setattr(httpx.HTTPTransport, "__init__", init)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    monkeypatch.setattr(httpx.HTTPTransport, "close", lambda self: None)

    t = http_saida._TransporteComQuedaIPv4(cert=None)
    resposta = t.handle_request(httpx.Request("GET", "https://viacep.com.br/ws/x/json/"))
    assert resposta.status_code == 200
    assert tentativas == [None, "0.0.0.0"]  # tentou normal, caiu para IPv4


def test_erro_que_nao_e_de_rota_nao_repete(monkeypatch):
    """Recusa de conexão sobe na hora — repetir por IPv4 só atrasaria o usuário."""
    tentativas = []

    def handle(self, request):
        tentativas.append(1)
        raise httpx.ConnectError("[Errno 111] Connection refused")

    monkeypatch.setattr(httpx.HTTPTransport, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)

    t = http_saida._TransporteComQuedaIPv4(cert=None)
    with pytest.raises(httpx.ConnectError):
        t.handle_request(httpx.Request("GET", "https://x.com"))
    assert len(tentativas) == 1
