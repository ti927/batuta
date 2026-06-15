"""Instrumento "Publicar no WordPress" (PRODUTO §13).

Publica um artigo no WordPress pela API REST (`/wp-json/wp/v2/posts`). O agente
entrega título, conteúdo e (opcional) tags e resumo; o cérebro monta a
autenticação, traduz nomes de categoria/tag em IDs e envia o post. As
credenciais vêm do ambiente do cérebro (`WORDPRESS_*`) — nunca do banco nem da
interface (CLAUDE §8), como na busca na web. Na Etapa 2 migram para o cofre de
segredos por-cliente.

Autentica com usuário + senha de aplicativo (HTTP Basic Auth). Segue a política
de falha do encaixe (Tarefa 5.1): transporte/5xx/429 são retentáveis;
autenticação recusada (401/403) e configuração ausente não. A resolução de
categorias/tags é "best-effort": uma que não resolva é ignorada, sem derrubar a
publicação.
"""

import os
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

TIMEOUT_S = 20.0


class ConfigWordpress(BaseModel):
    """Configuração fixa (quem monta o agente). A `senha_app` é SEGREDO (cofre,
    Fase 7-B); `site_url`/`usuario` são públicos. Se vazios, caem no `.env`
    legado (WORDPRESS_*), preservando os instrumentos já configurados."""

    status: Literal["draft", "publish"] = Field(
        default="draft",
        description="Como publicar: 'draft' (rascunho) ou 'publish' (no ar).",
    )
    categorias: list[str] = Field(
        default_factory=list,
        description=(
            "Nomes das categorias onde publicar (ex.: ['Controladoria Financeira']). "
            "Vazio = categoria padrão do site. Categoria inexistente é ignorada."
        ),
    )
    site_url: str = Field(
        default="", description="Endereço do site WordPress (ex.: https://blog.x.com)."
    )
    usuario: str = Field(default="", description="Usuário do WordPress.")
    senha_app: str = Field(
        default="", description="Senha de aplicativo do WordPress (segredo)."
    )


class ArgsWordpress(BaseModel):
    """O que a IA passa ao acionar: título, conteúdo e, opcionalmente, tags/resumo."""

    titulo: str = Field(min_length=1, description="Título do artigo.")
    conteudo: str = Field(min_length=1, description="O corpo do artigo (texto/HTML).")
    tags: list[str] = Field(
        default_factory=list,
        description="Etiquetas do post (ex.: ['controladoria','varejo']). Criadas se não existirem.",
    )
    resumo: str = Field(
        default="",
        description="Resumo curto do artigo (excerpt), 1-2 frases. Opcional.",
    )


def _categorias_para_ids(cliente: httpx.Client, base: str, nomes: list[str]) -> list[int]:
    """Traduz nomes de categoria em IDs (casa pelo nome, sem distinção de caixa).
    Categoria não encontrada é ignorada — não se cria categoria automaticamente."""
    ids: list[int] = []
    for nome in nomes:
        alvo = nome.strip()
        if not alvo:
            continue
        try:
            r = cliente.get(f"{base}/categories", params={"search": alvo})
        except httpx.HTTPError:
            continue
        if not r.is_success:
            continue
        achados = r.json() if isinstance(r.json(), list) else []
        exato = next(
            (c for c in achados if c.get("name", "").strip().lower() == alvo.lower()),
            None,
        )
        escolhido = exato or (achados[0] if achados else None)
        if escolhido and escolhido.get("id"):
            ids.append(escolhido["id"])
    return ids


def _tags_para_ids(cliente: httpx.Client, base: str, nomes: list[str]) -> list[int]:
    """Traduz nomes de tag em IDs; cria a tag se ainda não existir."""
    ids: list[int] = []
    for nome in nomes:
        alvo = nome.strip()
        if not alvo:
            continue
        tid = None
        try:
            r = cliente.get(f"{base}/tags", params={"search": alvo})
            if r.is_success:
                tid = next(
                    (t["id"] for t in r.json()
                     if t.get("name", "").strip().lower() == alvo.lower()),
                    None,
                )
            if tid is None:
                cr = cliente.post(f"{base}/tags", json={"name": alvo})
                if cr.is_success:
                    tid = cr.json().get("id")
                elif cr.status_code == 400:
                    # tag já existe: o WordPress devolve o term_id no erro
                    tid = (cr.json().get("data") or {}).get("term_id")
        except httpx.HTTPError:
            continue
        if tid:
            ids.append(tid)
    return ids


class PublicarWordpress(TipoInstrumento):
    tipo = "publicar_wordpress"
    nome_exibicao = "Publicar no WordPress"
    descricao = (
        "Publica um artigo no WordPress e devolve o link do post. Acione com o "
        "título e o conteúdo do artigo já pronto; pode passar também tags "
        "(etiquetas) e um resumo curto. A categoria é definida na configuração."
    )
    Config = ConfigWordpress
    Args = ArgsWordpress
    campos_secretos = ("senha_app",)
    tipos_credencial_aceitos = ("wordpress",)
    acao_irreversivel = True  # publica no blog do cliente

    def executar(self, config: ConfigWordpress, args: ArgsWordpress) -> dict:
        # Fase 7-B: prioriza o cofre (config), com o .env como fallback legado.
        url = config.site_url or os.environ.get("WORDPRESS_URL")
        usuario = config.usuario or os.environ.get("WORDPRESS_USUARIO")
        senha = config.senha_app or os.environ.get("WORDPRESS_APP_PASSWORD")
        if not (url and usuario and senha):
            raise FalhaInstrumento(
                "o WordPress não está configurado no cérebro (faltam WORDPRESS_URL, "
                "WORDPRESS_USUARIO ou WORDPRESS_APP_PASSWORD).",
                retentavel=False,
            )

        # A senha de aplicativo é exibida com espaços por legibilidade; o
        # WordPress os ignora, mas removemos para não correr risco.
        senha = senha.replace(" ", "")
        base = url.rstrip("/") + "/wp-json/wp/v2"

        with httpx.Client(timeout=TIMEOUT_S, auth=httpx.BasicAuth(usuario, senha)) as cliente:
            cat_ids = _categorias_para_ids(cliente, base, config.categorias)
            tag_ids = _tags_para_ids(cliente, base, args.tags)

            corpo: dict = {
                "title": args.titulo,
                "content": args.conteudo,
                "status": config.status,
            }
            if args.resumo.strip():
                corpo["excerpt"] = args.resumo.strip()
            if cat_ids:
                corpo["categories"] = cat_ids
            if tag_ids:
                corpo["tags"] = tag_ids

            try:
                resposta = cliente.post(f"{base}/posts", json=corpo)
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
            "categorias": cat_ids,
            "tags": tag_ids,
        }


registrar(PublicarWordpress())
