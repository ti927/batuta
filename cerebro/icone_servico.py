"""O ÍCONE do serviço de um instrumento personalizado — buscado pelo cérebro, guardado.

Um servidor MCP pode anunciar os próprios ícones (`serverInfo.icons` no protocolo) e o
site dele; uma API tem um endereço, e o site do serviço tem um ícone. O cérebro baixa
esse ícone UMA vez e guarda como `data:` no instrumento (`icone_auto`): a tela não
busca nada fora, e o ícone não quebra se o site mudar.

Borda de rede com os mesmos cuidados de toda saída: tempo curto, tamanho máximo, só
https e só endereço público (nada de `localhost`, IP privado ou rede interna — o
endereço vem da configuração de quem montou o instrumento). Falhar aqui não é erro de
ninguém: sem ícone, a tela usa o escolhido ou o genérico.
"""

from __future__ import annotations

import base64
import ipaddress
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import http_saida
from observabilidade.escritor import registrar_evento

TEMPO_S = 5.0
MAX_ICONE = 100_000  # bytes
MAX_PAGINA = 400_000
# Prefixos de subdomínio de API que não são o site do serviço (api.zernio.com → zernio.com).
_PREFIXOS_TECNICOS = {"api", "apis", "mcp", "app", "rest", "gateway", "www", "services"}


def endereco_publico(url: str) -> bool:
    """Só https, host com nome, que resolve para IP público."""
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname:
        return False
    host = p.hostname
    if host == "localhost" or host.endswith((".internal", ".local", ".railway.internal")):
        return False
    try:
        ips = {info[4][0] for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)}
    except OSError:
        return False
    return all(ipaddress.ip_address(ip.split("%")[0]).is_global for ip in ips)


def site_do_servico(url_api: str) -> str | None:
    """O site de um serviço a partir do endereço da API: https://api.zernio.com/v1 →
    https://zernio.com."""
    p = urlparse(url_api or "")
    if not p.hostname:
        return None
    partes = p.hostname.split(".")
    if len(partes) > 2 and partes[0] in _PREFIXOS_TECNICOS:
        partes = partes[1:]
    return "https://" + ".".join(partes)


class _Links(HTMLParser):
    """Os `<link rel="icon">` de uma página, com o tamanho declarado."""

    def __init__(self):
        super().__init__()
        self.icones: list[tuple[int, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        rel = a.get("rel", "").lower()
        if "icon" not in rel or not a.get("href"):
            return
        tamanhos = [int(n) for n in re.findall(r"(\d+)x\d+", a.get("sizes", ""))]
        tamanho = max(tamanhos) if tamanhos else (180 if "apple-touch" in rel else 32)
        self.icones.append((tamanho, a["href"]))


def _baixar(url: str, limite: int) -> tuple[bytes, str] | None:
    if url.startswith("data:image/"):
        return None  # já é data: — quem chama usa direto
    # Redirecionamento seguido À MÃO: cada destino passa pela mesma conferência de
    # endereço público (senão um site poderia mandar o cérebro para a rede interna).
    for _ in range(4):
        if not endereco_publico(url):
            return None
        try:
            with http_saida.cliente(timeout=TEMPO_S, follow_redirects=False) as c:
                r = c.get(url, headers={"User-Agent": "Batuta/1.0 (+icone do servico)"})
        except Exception:  # noqa: BLE001 — rede de terceiro; sem ícone não é erro
            return None
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            url = urljoin(url, r.headers["location"])
            continue
        if r.status_code != 200 or len(r.content) > limite:
            return None
        return r.content, r.headers.get("content-type", "").split(";")[0].strip().lower()
    return None


def _como_data(conteudo: bytes, tipo: str, url: str) -> str | None:
    if not tipo.startswith("image/"):
        if url.lower().endswith(".ico"):
            tipo = "image/x-icon"
        elif url.lower().endswith(".svg"):
            tipo = "image/svg+xml"
        else:
            return None
    if tipo == "image/svg+xml" and b"<script" in conteudo.lower():
        return None  # SVG com script não entra, nem como imagem
    return f"data:{tipo};base64," + base64.b64encode(conteudo).decode("ascii")


def icone_de_url(url: str) -> str | None:
    """Um ícone (endereço de imagem ou `data:`) virando `data:` guardável."""
    if url.startswith("data:image/"):
        return url if len(url) <= MAX_ICONE * 1.4 else None
    baixado = _baixar(url, MAX_ICONE)
    return _como_data(*baixado, url) if baixado else None


def icone_do_site(site: str) -> str | None:
    """O ícone de um site: o maior `<link rel=icon>` da página inicial; senão, o
    `/favicon.ico`."""
    pagina = _baixar(site, MAX_PAGINA)
    candidatos: list[str] = []
    if pagina and "html" in pagina[1]:
        leitor = _Links()
        try:
            leitor.feed(pagina[0].decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            pass
        # Preferência: 64 a 256 px (nítido no cartão sem pesar); depois o maior.
        ordem = sorted(leitor.icones, key=lambda t: (not 64 <= t[0] <= 256, -t[0]))
        candidatos = [urljoin(site + "/", href) for _t, href in ordem]
    candidatos.append(urljoin(site + "/", "/favicon.ico"))
    for url in candidatos[:4]:
        icone = icone_de_url(url)
        if icone:
            return icone
    return None


def icone_do_instrumento(tipo: str, configuracao: dict, conexao: dict | None, url_secreta: str | None = None) -> str | None:
    """O ícone automático de um instrumento personalizado (None = não achou)."""
    if tipo == "conectar_mcp":
        servidor = (conexao or {}).get("servidor") or {}
        for icone in servidor.get("icones") or []:
            achado = icone_de_url(icone)
            if achado:
                return achado
        site = servidor.get("site") or (site_do_servico(url_secreta) if url_secreta else None)
        return icone_do_site(site) if site else None
    if tipo == "conector":
        for op in (configuracao or {}).get("operacoes") or []:
            site = site_do_servico(op.get("url", ""))
            if site:
                return icone_do_site(site)
    return None


def atualizar(instrumento_id) -> None:
    """Segundo plano: busca e grava o ícone automático de um instrumento. Abre a
    própria sessão (a da requisição já fechou). Grava a TENTATIVA mesmo sem achar."""
    import segredos_instrumento
    from modelos import Instrumento
    from sessao import CriadorDeSessao

    sessao = CriadorDeSessao()
    try:
        inst = sessao.get(Instrumento, instrumento_id)
        if inst is None:
            return
        url_mcp = None
        if inst.tipo == "conectar_mcp":
            # O endereço do MCP é segredo (costuma levar a chave): só o domínio é usado,
            # e nada dele sai daqui.
            url_mcp = segredos_instrumento.decifrar(sessao, inst.id).get("url")
        try:
            inst.icone_auto = icone_do_instrumento(
                inst.tipo, inst.configuracao or {}, inst.conexao, url_mcp
            )
        except Exception as e:  # noqa: BLE001
            inst.icone_auto = None
            registrar_evento(
                categoria="instrumento", acao="instrumento.icone_falhou", nivel="warning",
                recurso_tipo="instrumento", recurso_id=str(instrumento_id),
                erro=type(e).__name__,
            )
        inst.icone_auto_em = datetime.now(timezone.utc)
        sessao.commit()
    finally:
        sessao.close()
