"""Instrumento "Gerar vídeo a partir de foto" (imagem→vídeo via fal.ai).

Anima uma FOTO (URL pública) num clipe de vídeo, usando a fila da fal.ai — um
agregador que, com UMA chave, dá vários modelos. Diferente do "Gerar vídeo" (Sora,
texto→vídeo): aqui a entrada principal é a IMAGEM, e os modelos ACEITAM rosto de
pessoa real (o que a Sora bloqueia) e não exigem tamanho exato. Ideal para o dono
do negócio animar a própria foto para marketing. A conta paga (tier) entrega o
vídeo SEM marca d'água.

Modelos (v1): Kling (melhor para rosto/pessoa — padrão), Luma Ray 2
(cinematográfico), Hailuo (movimento dinâmico, econômico). A chave `fal` é um
SEGREDO reusado do pool da organização (cofre), como a do OpenAI no gerar_imagem.

Ciclo da FILA da fal.ai (3 passos): ENVIA o job (POST na fila), ESPERA processar
(GET status até COMPLETED — leva minutos) e PEGA o resultado (GET response →
`video.url`). O mp4 é BAIXADO e salvo no Storage (URL durável que serve direto ao
"Instagram: publicar"). Poll INLINE (o worker fica ocupado) com teto abaixo do
sweeper da fila (15 min) — por isso os clipes são curtos.

CATÁLOGO ÚNICO (`CATALOGO_FAL`) é a fonte da verdade dos modelos: cada entrada tem o
`endpoint` (id do modelo na fal) e as `duracoes` válidas (que variam por modelo, e o
valor é passado VERBATIM à API). Dele saem enums, validação e dependências de UI.

IDEMPOTÊNCIA: depois de o job existir (request_id), TODA falha é NÃO-retentável (a
orquestração reexecuta em falha retentável — não podemos re-submeter e cobrar de
novo). Só a falha de transporte ANTES do envio é retentável.
"""

import time
import uuid

import httpx
from pydantic import BaseModel, Field, model_validator

import arquivos
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

TIMEOUT_S = 60.0
FILA = "https://queue.fal.run"
# Vídeo leva minutos; teto ~10 min (120 × 5s), abaixo do sweeper da fila (15 min).
POLL_TENTATIVAS = 120
POLL_INTERVALO_S = 5.0
TENTATIVAS_DOWNLOAD = 3

# ── FONTE ÚNICA DA VERDADE: modelos de imagem→vídeo na fal.ai ──
# Cada entrada: endpoint (id do modelo) + durações válidas (formato próprio do
# modelo, passado VERBATIM à API). Todos aceitam `prompt` + `image_url`.
CATALOGO_FAL: dict[str, dict] = {
    "kling": {
        "rotulo": "Kling 2.1 (melhor para rosto/pessoa)",
        "endpoint": "fal-ai/kling-video/v2.1/standard/image-to-video",
        "duracoes": ("5", "10"),
    },
    "luma": {
        "rotulo": "Luma Ray 2 (cinematográfico)",
        "endpoint": "fal-ai/luma-dream-machine/ray-2/image-to-video",
        "duracoes": ("5s", "9s"),
    },
    "hailuo": {
        "rotulo": "Hailuo 02 (movimento dinâmico, econômico)",
        "endpoint": "fal-ai/minimax/hailuo-02/standard/image-to-video",
        "duracoes": ("6", "10"),
    },
}

MODELO_PADRAO = "kling"
DURACAO_PADRAO = "5"


def _uniao_duracoes() -> list[str]:
    vistos: list[str] = []
    for spec in CATALOGO_FAL.values():
        for d in spec["duracoes"]:
            if d not in vistos:
                vistos.append(d)
    return vistos


class ConfigVideoFal(BaseModel):
    """Configuração fixa (o humano escolhe; é o que a medição lê). `chave_api` é
    SEGREDO reusado do pool `fal` da organização."""

    modelo: str = Field(
        default=MODELO_PADRAO,
        title="Modelo do vídeo",
        description="kling (melhor para rosto), luma (cinematográfico) ou hailuo (econômico).",
        json_schema_extra={"enum": list(CATALOGO_FAL)},
    )
    duracao: str = Field(
        default=DURACAO_PADRAO,
        title="Duração",
        description="Duração do clipe (as opções dependem do modelo).",
        json_schema_extra={"enum": _uniao_duracoes()},
    )
    chave_api: str = Field(
        default="",
        title="Chave da fal.ai (opcional)",
        description="Chave da fal.ai (segredo). Em branco, usa a chave 'fal' da organização.",
    )

    @model_validator(mode="after")
    def _validar_combinacao(self) -> "ConfigVideoFal":
        spec = CATALOGO_FAL.get(self.modelo)
        if spec is None:
            raise ValueError(
                f"Modelo de vídeo desconhecido: '{self.modelo}'. "
                f"Use um destes: {', '.join(CATALOGO_FAL)}."
            )
        if self.duracao not in spec["duracoes"]:
            raise ValueError(
                f"A duração '{self.duracao}' não vale para o modelo '{self.modelo}'. "
                f"Durações válidas: {', '.join(spec['duracoes'])}."
            )
        return self


class ArgsVideoFal(BaseModel):
    """O que a IA passa: a foto a animar e o roteiro do movimento/cena."""

    imagem_url: str = Field(
        min_length=1,
        description="URL PÚBLICA da foto a animar (o primeiro quadro do vídeo).",
    )
    prompt: str = Field(
        min_length=1,
        description="Roteiro: o movimento e a cena do vídeo a partir da foto.",
    )


def _detalhe_erro(resposta: httpx.Response) -> str:
    """O motivo que a fal devolveu (campo `detail`/`error`), ou o texto cru."""
    try:
        dados = resposta.json()
        if isinstance(dados, dict):
            det = dados.get("detail") or dados.get("error") or dados.get("message")
            if det:
                return str(det)[:300]
    except ValueError:
        pass
    return (resposta.text or "sem detalhe").strip()[:300]


class GerarVideoFal(TipoInstrumento):
    tipo = "gerar_video_fal"
    categoria = "Conteúdo"
    nome_exibicao = "Gerar vídeo a partir de foto"
    descricao = (
        "Anima uma FOTO (URL pública) num clipe de vídeo, via fal.ai (Kling/Luma/Hailuo). "
        "Aceita rosto de pessoa real (ao contrário da Sora) — ideal para animar a própria "
        "foto em conteúdo de marketing. Acione com a URL da foto e um roteiro do movimento/"
        "cena; devolve um link público (MP4) que serve ao 'Instagram: publicar'. Leva alguns "
        "minutos. A conta paga entrega sem marca d'água."
    )
    Config = ConfigVideoFal
    Args = ArgsVideoFal
    campos_secretos = ("chave_api",)
    # Reusa a chave 'fal' da organização (Chaves de IA) quando não há chave própria.
    chave_compartilhada = ("chave_api", "fal")
    # acao_irreversivel = False: só gera um arquivo; quem publica é que é irreversível.

    def dependencias_ui(self) -> dict:
        return {
            "duracao": {
                "controlado_por": "modelo",
                "opcoes": {m: list(s["duracoes"]) for m, s in CATALOGO_FAL.items()},
            },
        }

    def executar(self, config: ConfigVideoFal, args: ArgsVideoFal) -> dict:
        if not config.chave_api:
            raise FalhaInstrumento(
                "falta a chave da fal.ai — configure-a no instrumento ou cadastre a "
                "chave 'fal' da organização em Chaves de IA.",
                retentavel=False,
            )
        spec = CATALOGO_FAL[config.modelo]
        headers = {"Authorization": f"Key {config.chave_api}"}
        corpo = {
            "prompt": args.prompt,
            "image_url": args.imagem_url,
            "duration": config.duracao,
        }
        with httpx.Client(timeout=TIMEOUT_S) as cli:
            # 1) ENVIA o job. Falha ANTES do request_id → nada gerado → pode retentar.
            try:
                r = cli.post(f"{FILA}/{spec['endpoint']}", headers=headers, json=corpo)
            except httpx.HTTPError as e:
                raise FalhaInstrumento(
                    f"não foi possível enviar o vídeo à fal.ai: {e}", retentavel=True
                )
            status = r.status_code
            if status in (401, 403):
                raise FalhaInstrumento(
                    "a chave da fal.ai foi recusada — verifique-a.", retentavel=False
                )
            if status == 429 or 500 <= status < 600:
                raise FalhaInstrumento(
                    f"a fal.ai respondeu HTTP {status} ao enviar.", retentavel=True
                )
            if not r.is_success:
                raise FalhaInstrumento(
                    f"a fal.ai recusou o pedido (HTTP {status}): {_detalhe_erro(r)}",
                    retentavel=False,
                )
            dados = r.json() or {}
            request_id = dados.get("request_id")
            if not request_id:
                raise FalhaInstrumento(
                    "a fal.ai não devolveu o id do job.", retentavel=False
                )
            base = f"{FILA}/{spec['endpoint']}/requests/{request_id}"
            status_url = dados.get("status_url") or f"{base}/status"
            response_url = dados.get("response_url") or f"{base}/response"

            # 2) ESPERA. A PARTIR DAQUI, TUDO é NÃO-retentável (idempotência).
            self._aguardar(cli, headers, status_url)

            # 3) PEGA o resultado e a URL do vídeo.
            url_video = self._url_do_video(cli, headers, response_url)

            # 4) BAIXA o mp4 e guarda no Storage (URL durável para publicar).
            conteudo = self._baixar(cli, url_video)

        nome = f"{uuid.uuid4().hex}.mp4"
        url = arquivos.salvar(nome, conteudo, "video/mp4")
        return {
            "ok": True,
            "arquivo": nome,
            "url": url,
            "modelo": config.modelo,
            "duracao": config.duracao,
        }

    def _aguardar(self, cli, headers, status_url: str) -> None:
        """Poll do status até COMPLETED. Erros transitórios do GET NÃO sobem como
        retentáveis (o job existe/cobra) — dorme e reconfere; estoura em não-retentável."""
        for _ in range(POLL_TENTATIVAS):
            try:
                r = cli.get(status_url, headers=headers)
            except httpx.HTTPError:
                time.sleep(POLL_INTERVALO_S)
                continue
            if r.is_success:
                estado = (r.json() or {}).get("status")
                if estado == "COMPLETED":
                    return
                # IN_QUEUE / IN_PROGRESS → continua
            elif r.status_code in (401, 403):
                raise FalhaInstrumento(
                    "a chave da fal.ai foi recusada durante o acompanhamento.",
                    retentavel=False,
                )
            time.sleep(POLL_INTERVALO_S)
        raise FalhaInstrumento(
            "a geração de vídeo demorou além do tempo limite do Batuta.",
            retentavel=False,
        )

    def _url_do_video(self, cli, headers, response_url: str) -> str:
        """Pega o resultado do job e extrai `video.url`. Falha aqui é NÃO-retentável
        (o job já foi cobrado); tenta algumas vezes por dentro."""
        ultimo = "sem detalhe"
        for _ in range(TENTATIVAS_DOWNLOAD):
            try:
                r = cli.get(response_url, headers=headers)
            except httpx.HTTPError as e:
                ultimo = str(e)
                time.sleep(POLL_INTERVALO_S)
                continue
            if r.is_success:
                video = (r.json() or {}).get("video") or {}
                url = video.get("url")
                if url:
                    return url
                raise FalhaInstrumento(
                    "a fal.ai concluiu mas não devolveu a URL do vídeo.",
                    retentavel=False,
                )
            ultimo = f"HTTP {r.status_code}: {_detalhe_erro(r)}"
            # 4xx com detalhe = o job falhou (ex.: moderação) — não adianta reconferir.
            if 400 <= r.status_code < 500:
                raise FalhaInstrumento(
                    f"a fal.ai não gerou o vídeo: {_detalhe_erro(r)}", retentavel=False
                )
            time.sleep(POLL_INTERVALO_S)
        raise FalhaInstrumento(
            f"não foi possível obter o resultado do vídeo ({ultimo}).", retentavel=False
        )

    def _baixar(self, cli, url_video: str) -> bytes:
        """Baixa o mp4 gerado. Não-retentável (o job já foi cobrado)."""
        ultimo = "sem detalhe"
        for _ in range(TENTATIVAS_DOWNLOAD):
            try:
                r = cli.get(url_video, follow_redirects=True)
            except httpx.HTTPError as e:
                ultimo = str(e)
                time.sleep(POLL_INTERVALO_S)
                continue
            if r.is_success and r.content:
                return r.content
            ultimo = f"HTTP {r.status_code}"
            time.sleep(POLL_INTERVALO_S)
        raise FalhaInstrumento(
            f"o vídeo foi gerado mas não pôde ser baixado ({ultimo}).", retentavel=False
        )


registrar(GerarVideoFal())
