"""Instrumento "Publicar no WordPress" (PRODUTO §13).

Publica um artigo no WordPress pela API REST (`/wp-json/wp/v2/posts`). O agente
só entrega título e conteúdo; o cérebro monta a autenticação e o corpo. As
credenciais vêm do ambiente do cérebro (`WORDPRESS_*`) — nunca do banco nem da
interface (CLAUDE §8), como na busca na web. Na Etapa 2 migram para o cofre de
segredos por-cliente.

Autentica com usuário + senha de aplicativo (HTTP Basic Auth). Segue a política
de falha do encaixe (Tarefa 5.1): transporte/5xx/429 são retentáveis;
autenticação recusada (401/403) e configuração ausente não.
"""

import os
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

TIMEOUT_S = 20.0


class ConfigWordpress(BaseModel):
    """Configuração fixa. As credenciais NÃO ficam aqui (vêm do ambiente)."""

    status: Literal["draft", "publish"] = Field(
        default="draft",
        description="Como publicar: 'draft' (rascunho) ou 'publish' (no ar).",
    )


class ArgsWordpress(BaseModel):
    """O que a IA passa ao acionar: o título e o corpo do artigo."""

    titulo: str = Field(min_length=1, description="Título do artigo.")
    conteudo: str = Field(min_length=1, description="O corpo do artigo (texto/HTML).")


class PublicarWordpress(TipoInstrumento):
    tipo = "publicar_wordpress"
    nome_exibicao = "Publicar no WordPress"
    descricao = (
        "Publica um artigo no WordPress e devolve o link do post. Acione com o "
        "título e o conteúdo do artigo já pronto. Use para publicar o texto final."
    )
    Config = ConfigWordpress
    Args = ArgsWordpress

    def executar(self, config: ConfigWordpress, args: ArgsWordpress) -> dict:
        url = os.environ.get("WORDPRESS_URL")
        usuario = os.environ.get("WORDPRESS_USUARIO")
        senha = os.environ.get("WORDPRESS_APP_PASSWORD")
        if not (url and usuario and senha):
            raise FalhaInstrumento(
                "o WordPress não está configurado no cérebro (faltam WORDPRESS_URL, "
                "WORDPRESS_USUARIO ou WORDPRESS_APP_PASSWORD).",
                retentavel=False,
            )

        # A senha de aplicativo é exibida com espaços por legibilidade; o
        # WordPress os ignora, mas removemos para não correr risco.
        senha = senha.replace(" ", "")
        endpoint = url.rstrip("/") + "/wp-json/wp/v2/posts"
        corpo = {
            "title": args.titulo,
            "content": args.conteudo,
            "status": config.status,
        }
        try:
            with httpx.Client(timeout=TIMEOUT_S) as cliente:
                resposta = cliente.post(
                    endpoint, auth=httpx.BasicAuth(usuario, senha), json=corpo
                )
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não foi possível publicar no WordPress: {e}", retentavel=True
            )

        status = resposta.status_code
        if status in (401, 403):
            raise FalhaInstrumento(
                "o WordPress recusou a autenticação (usuário ou senha de "
                "aplicativo inválidos).",
                retentavel=False,
            )
        if status == 429 or 500 <= status < 600:
            raise FalhaInstrumento(
                f"o WordPress respondeu HTTP {status}.", retentavel=True
            )
        if not resposta.is_success:
            raise FalhaInstrumento(
                f"a publicação falhou (HTTP {status}): {resposta.text[:300]}",
                retentavel=False,
            )

        dados = resposta.json()
        return {
            "ok": True,
            "id": dados.get("id"),
            "link": dados.get("link"),
            "status": dados.get("status"),
        }


registrar(PublicarWordpress())
