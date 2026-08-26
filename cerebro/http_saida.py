"""Saída HTTP do Batuta para hosts que o CONSULTOR escolhe (REST, conector, webhook…).

Existe por causa de uma falha real (3ª bateria do teste do MCP, 2026-08-26): a mesma
chamada ao ViaCEP que funcionara no dia anterior passou a morrer com

    [Errno 101] Network is unreachable

enquanto `api.github.com` respondia 200 no mesmo conector. A diferença entre os dois
hosts é que o ViaCEP publica endereço **IPv6** (`AAAA`) e o GitHub não. O servidor
resolve o nome, recebe uma lista de endereços e tenta um por um; quando a rota IPv6
do container não existe, a tentativa morre com `ENETUNREACH` — e o erro que sobra é
o da ÚLTIMA tentativa, mesmo que exista um IPv4 perfeitamente alcançável.

Duas coisas, então, e as duas valem para toda saída:

1. **Queda para IPv4.** Numa falha de rota, a chamada é refeita uma vez amarrada a
   IPv4 (`local_address="0.0.0.0"`), que ignora os endereços IPv6 na resolução. Só o
   caminho de FALHA muda: quem conecta de primeira não passa por aqui.
2. **Erro honesto** (§12-A). "Network is unreachable" não diz nada a quem montou o
   instrumento; a mensagem passa a nomear o host e a dizer o que costuma ser.

Não é para os instrumentos de serviço fixo (Telegram, Instagram, OpenAI…), que falam
com hosts conhecidos e comprovadamente alcançáveis — é para onde a URL é do usuário.
"""

import contextlib
import re

import httpx

# Assinaturas de "não consegui nem chegar no destino" (rota/rede), que merecem a
# segunda tentativa em IPv4. Erro de DNS, recusa de conexão e timeout NÃO entram:
# nesses, tentar de novo pelo outro protocolo não muda nada.
_SEM_ROTA = re.compile(
    r"errno 101|network is unreachable|errno 113|no route to host|"
    r"errno 65|address family not supported|unreachable",
    re.IGNORECASE,
)


def falha_de_rota(e: BaseException) -> bool:
    """Se o erro é de ROTA até o host (não de DNS, recusa ou timeout)."""
    return bool(_SEM_ROTA.search(str(e)))


def mensagem_de_rede(url: str, e: BaseException) -> str:
    """O texto que chega a quem montou o instrumento — nomeia o host e o provável."""
    if falha_de_rota(e):
        return (
            f"o servidor do Batuta não conseguiu alcançar {url} pela rede "
            f"(sem rota até o destino, inclusive tentando por IPv4). Confirme o "
            f"endereço; se estiver certo, o destino pode estar fora do ar ou "
            f"bloqueando servidores de nuvem. Detalhe técnico: {e}"
        )
    return f"não foi possível chamar {url}: {e}"


@contextlib.contextmanager
def cliente(*, timeout: float, cert=None, auth=None, **kwargs):
    """Um `httpx.Client` que refaz a chamada em IPv4 quando a rota falha.

    Use exatamente como o `httpx.Client` (`with cliente(timeout=…) as c:`). O
    fallback é por REQUISIÇÃO e acontece dentro do transporte, então vale para
    qualquer método e sobrevive a redirecionamentos."""
    with httpx.Client(
        timeout=timeout,
        auth=auth,
        transport=_TransporteComQuedaIPv4(cert=cert),
        **kwargs,
    ) as c:
        yield c


class _TransporteComQuedaIPv4(httpx.HTTPTransport):
    """Transporte normal; em falha de ROTA, uma segunda tentativa amarrada a IPv4."""

    def __init__(self, *, cert=None, **kwargs):
        self._cert = cert
        super().__init__(cert=cert, **kwargs)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        try:
            return super().handle_request(request)
        except httpx.ConnectError as e:
            if not falha_de_rota(e):
                raise
            # `local_address="0.0.0.0"` amarra o socket a IPv4: a resolução passa a
            # considerar só os endereços A. É a queda, não o padrão.
            ipv4 = httpx.HTTPTransport(cert=self._cert, local_address="0.0.0.0")
            try:
                return ipv4.handle_request(request)
            finally:
                ipv4.close()
