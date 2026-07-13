"""Instrumento "Publicar no Instagram" (Fase 2 — instrumentos de Instagram).

Publica foto, Reels, Stories (imagem OU vídeo) ou carrossel (misturando imagens e
vídeos) numa conta Instagram profissional, pela Instagram API with Instagram Login
(`graph.instagram.com`). O `token` e o `ig_user_id` vêm da credencial nomeada
`instagram` (caixa-forte) — o agente só passa a mídia e a legenda.

Fluxo da Graph (3 passos): cria um CONTÊINER de mídia (POST /{ig-user-id}/media),
ESPERA processar (GET /{container}?fields=status_code até FINISHED — Reels/vídeo
demoram) e PUBLICA (POST /{ig-user-id}/media_publish). Carrossel: um contêiner por
item (is_carousel_item) + um contêiner pai CAROUSEL com os filhos.

TIPO DE CADA MÍDIA: por padrão tudo é IMAGEM. Para VÍDEO — item de vídeo no
carrossel (`media_type=VIDEO` + `is_carousel_item` + `video_url`; NÃO `REELS`, que
não entra em carrossel) ou story de vídeo (`media_type=STORIES` + `video_url`) — a
IA marca o tipo de cada URL em `tipos_midia_itens` (paralelo a `midia_urls`). Todo
contêiner de vídeo processa de forma assíncrona → o poll até FINISHED (que já roda
em cada item e no contêiner final) é o que garante a publicação.

IDEMPOTÊNCIA: `media_publish` NÃO é idempotente (re-chamar publica de novo). A
orquestração reexecuta um instrumento em falha RETENTÁVEL — então aqui TODAS as
falhas são NÃO-retentáveis, para nunca republicar por reexecução. O erro sobe
claro ao agente, que decide se tenta de novo.

A mídia precisa estar numa URL PÚBLICA acessível pela Meta (a Graph BAIXA a mídia
da URL; não há upload de arquivo). Use o link da imagem gerada no passo anterior
(servida em /arquivos) ou um link externo público.
"""

import time
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

API = "https://graph.instagram.com/v23.0"
TIMEOUT_S = 30.0
MAX_LEGENDA = 2200  # limite de legenda do Instagram
POLL_TENTATIVAS = 20  # espera o contêiner processar (Reels/vídeo demoram)
POLL_INTERVALO_S = 3.0
MIN_CARROSSEL = 2
MAX_CARROSSEL = 10


def _detalhe_erro(resposta: httpx.Response) -> str:
    """O motivo que a Meta devolveu (campo `error.message`). Cai no texto cru."""
    try:
        dados = resposta.json()
        if isinstance(dados, dict):
            erro = dados.get("error")
            if isinstance(erro, dict):
                return str(erro.get("message") or erro)[:200]
            return str(dados.get("message") or dados)[:200]
    except Exception:
        pass
    return (resposta.text or "sem detalhe").strip()[:200]


def _conferir(resposta: httpx.Response) -> None:
    """Qualquer falha de publicação é NÃO-retentável (idempotência: ver módulo)."""
    if not resposta.is_success:
        raise FalhaInstrumento(
            f"o Instagram recusou a operação (HTTP {resposta.status_code}): "
            f"{_detalhe_erro(resposta)}",
            retentavel=False,
        )


def _post(cli: httpx.Client, url: str, dados: dict) -> dict:
    try:
        r = cli.post(url, data=dados)
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível falar com o Instagram: {e}", retentavel=False
        )
    _conferir(r)
    return r.json()


def _get(cli: httpx.Client, url: str, params: dict) -> dict:
    try:
        r = cli.get(url, params=params)
    except httpx.HTTPError as e:
        raise FalhaInstrumento(
            f"não foi possível falar com o Instagram: {e}", retentavel=False
        )
    _conferir(r)
    return r.json()


def _criar_container(
    cli, config, tipo_midia: str, url: str, legenda: str, tipo_item: str = "imagem"
) -> str:
    dados = {"access_token": config.token}
    if tipo_midia == "reels":
        dados.update(media_type="REELS", video_url=url)
    elif tipo_midia == "stories":
        # Story pode ser imagem OU vídeo (o tipo do item decide o campo da mídia).
        if tipo_item == "video":
            dados.update(media_type="STORIES", video_url=url)
        else:
            dados.update(media_type="STORIES", image_url=url)
    else:  # imagem (foto no feed) — vídeo de feed é 'reels', não este ramo
        dados["image_url"] = url
    if tipo_midia != "stories" and legenda:  # stories não têm legenda
        dados["caption"] = legenda
    cid = _post(cli, f"{API}/{config.ig_user_id}/media", dados).get("id")
    if not cid:
        raise FalhaInstrumento(
            "o Instagram não devolveu o id do contêiner de mídia.", retentavel=False
        )
    return cid


def _criar_item_carrossel(cli, config, url: str, tipo_item: str = "imagem") -> str:
    dados = {"access_token": config.token, "is_carousel_item": "true"}
    if tipo_item == "video":
        # Item de vídeo no carrossel: media_type=VIDEO (NÃO REELS) + video_url.
        dados.update(media_type="VIDEO", video_url=url)
    else:
        dados["image_url"] = url
    cid = _post(cli, f"{API}/{config.ig_user_id}/media", dados).get("id")
    if not cid:
        raise FalhaInstrumento(
            "o Instagram não devolveu o id de um item do carrossel.", retentavel=False
        )
    return cid


def _montar_carrossel(cli, config, itens: list[tuple[str, str]], legenda: str) -> str:
    filhos = []
    for url, tipo_item in itens:
        item = _criar_item_carrossel(cli, config, url, tipo_item)
        _aguardar_finished(cli, config, item)
        filhos.append(item)
    dados = {
        "access_token": config.token,
        "media_type": "CAROUSEL",
        "children": ",".join(filhos),
    }
    if legenda:
        dados["caption"] = legenda
    cid = _post(cli, f"{API}/{config.ig_user_id}/media", dados).get("id")
    if not cid:
        raise FalhaInstrumento(
            "o Instagram não devolveu o id do carrossel.", retentavel=False
        )
    return cid


def _aguardar_finished(cli, config, container_id: str) -> None:
    """Espera o contêiner ficar FINISHED (loop próprio, NÃO via retentativa da
    orquestração — ver idempotência no topo do módulo)."""
    for _ in range(POLL_TENTATIVAS):
        status = _get(
            cli,
            f"{API}/{container_id}",
            {"fields": "status_code", "access_token": config.token},
        ).get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise FalhaInstrumento(
                f"o Instagram não conseguiu processar a mídia (status {status}).",
                retentavel=False,
            )
        time.sleep(POLL_INTERVALO_S)
    raise FalhaInstrumento(
        "a mídia demorou demais para processar no Instagram (tempo esgotado).",
        retentavel=False,
    )


def _publicar(cli, config, container_id: str) -> str:
    mid = _post(
        cli,
        f"{API}/{config.ig_user_id}/media_publish",
        {"access_token": config.token, "creation_id": container_id},
    ).get("id")
    if not mid:
        raise FalhaInstrumento(
            "o Instagram não confirmou a publicação (sem id de mídia).",
            retentavel=False,
        )
    return mid


class ConfigPublicarInstagram(BaseModel):
    """Vem da credencial `instagram` (caixa-forte): a conta e o token. Os nomes
    batem com os campos da credencial, de propósito (a borda mescla direto)."""

    ig_user_id: str = Field(
        default="", description="ID da conta Instagram (vem da credencial)."
    )
    token: str = Field(
        default="",
        description="Token de acesso do Instagram (segredo; vem da credencial).",
    )


class ArgsPublicarInstagram(BaseModel):
    """O que a IA passa ao acionar: o tipo de mídia, a(s) URL(s) e a legenda."""

    tipo_midia: Literal["imagem", "reels", "stories", "carrossel"] = Field(
        default="imagem",
        description="O que publicar: imagem (foto no feed), reels (vídeo), stories "
        "(imagem ou vídeo) ou carrossel (2 a 10 itens, misturando imagens e vídeos).",
    )
    midia_urls: list[str] = Field(
        default_factory=list,
        description="URL(s) PÚBLICA(s) da mídia. 1 para imagem/reels/stories; 2 a 10 "
        "para carrossel. A Meta baixa a mídia desta URL — ela precisa estar acessível "
        "na hora da publicação. Vídeo precisa ser MP4/MOV (H264/HEVC, áudio AAC).",
    )
    tipos_midia_itens: list[Literal["imagem", "video"]] = Field(
        default_factory=list,
        description="Opcional: o tipo de CADA mídia em `midia_urls`, na MESMA ordem (1 "
        "entrada por URL). Use 'video' para um item de VÍDEO do carrossel ou para um "
        "STORY de vídeo; 'imagem' para foto. Se omitido, tudo é tratado como imagem. "
        "Não se aplica a 'reels' (já é vídeo) nem à foto de feed.",
    )
    legenda: str = Field(
        default="", description="Legenda do post (ignorada em stories)."
    )


class PublicarInstagram(TipoInstrumento):
    tipo = "publicar_instagram"
    categoria = "Instagram"
    nome_exibicao = "Instagram: publicar"
    descricao = (
        "Publica no Instagram (foto no feed, Reels, Stories de imagem OU vídeo, ou "
        "carrossel de até 10 itens misturando imagens e vídeos) e devolve o id da mídia "
        "publicada. Acione com o tipo de mídia, a(s) URL(s) PÚBLICA(s) e a legenda; para "
        "vídeo em carrossel ou story de vídeo, marque o tipo de cada mídia em "
        "`tipos_midia_itens` (mesma ordem das URLs). A conta vem da credencial 'instagram'."
    )
    Config = ConfigPublicarInstagram
    Args = ArgsPublicarInstagram
    campos_secretos = ("token",)
    tipos_credencial_aceitos = ("instagram",)
    acao_irreversivel = True  # publica para fora — exige portão de aprovação
    # Sem `campo_mensagem`: a legenda é conteúdo publicado, não uma mensagem de
    # canal apresentada a um humano para aprovação (mesma escolha do WordPress).
    # `campo_mensagem` fica para o canal de DM (Fase 4).

    def executar(
        self, config: ConfigPublicarInstagram, args: ArgsPublicarInstagram
    ) -> dict:
        if not (config.token and config.ig_user_id):
            raise FalhaInstrumento(
                "o Instagram não está conectado — configure a credencial 'instagram' "
                "(token + conta).",
                retentavel=False,
            )
        # Pareia cada URL ao seu tipo (imagem/vídeo), na ORDEM original — filtrando
        # vazios sem desalinhar os índices de `tipos_midia_itens`. Tipo ausente = imagem.
        tipos = list(args.tipos_midia_itens or [])
        itens: list[tuple[str, str]] = []
        for i, u in enumerate(args.midia_urls or []):
            if not (u and u.strip()):
                continue
            tipo_item = tipos[i] if i < len(tipos) else "imagem"
            itens.append((u.strip(), tipo_item))
        if not itens:
            raise FalhaInstrumento(
                "nenhuma URL de mídia foi informada — passe o link público da "
                "imagem/vídeo a publicar.",
                retentavel=False,
            )
        legenda = (args.legenda or "")[:MAX_LEGENDA]
        with httpx.Client(timeout=TIMEOUT_S) as cli:
            if args.tipo_midia == "carrossel":
                if not (MIN_CARROSSEL <= len(itens) <= MAX_CARROSSEL):
                    raise FalhaInstrumento(
                        f"um carrossel precisa de {MIN_CARROSSEL} a {MAX_CARROSSEL} "
                        f"imagens/vídeos (recebi {len(itens)}).",
                        retentavel=False,
                    )
                container = _montar_carrossel(cli, config, itens, legenda)
            else:
                url0, tipo0 = itens[0]
                container = _criar_container(
                    cli, config, args.tipo_midia, url0, legenda, tipo_item=tipo0
                )
            _aguardar_finished(cli, config, container)
            media_id = _publicar(cli, config, container)
        return {"ok": True, "media_id": media_id, "tipo_midia": args.tipo_midia}


registrar(PublicarInstagram())
