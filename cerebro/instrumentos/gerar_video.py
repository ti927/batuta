"""Instrumento "Gerar vídeo" (PRODUTO §13; corrente de conteúdo).

Gera um VÍDEO curto a partir de uma descrição (prompt) usando a API de vídeo da
OpenAI (Sora) e devolve um link público para o MP4. Texto→vídeo; opcionalmente
imagem→vídeo, animando a partir de um quadro inicial (ex.: uma imagem gerada
antes). A chave é um SEGREDO reusado do pool da organização (a mesma chave OpenAI
do gerar_imagem). O arquivo é salvo e servido pelo cérebro/Storage — a URL pública
serve direto ao "Instagram: publicar" (reels, story de vídeo ou item de carrossel).

Ciclo ASSÍNCRONO da API (3 passos): CRIA o job (POST /v1/videos, multipart),
ESPERA processar (GET /v1/videos/{id} até `status == completed` — leva minutos) e
BAIXA o conteúdo (GET /v1/videos/{id}/content?variant=video → MP4). Como a geração
demora, o poll é feito INLINE (o worker da fila fica ocupado o tempo todo) — por
isso os padrões são rápidos (sora-2, clipe curto) e o teto do poll fica ABAIXO do
sweeper da fila (15 min), para o instrumento falhar LIMPO em vez de ser morto.

A OpenAI embute uma MARCA D'ÁGUA visível ("Sora") em todo vídeo (mais um selo C2PA
invisível de "gerado por IA") — não há como removê-la pela API. Restrições de
conteúdo: sem pessoas reais/figuras públicas (inclusive na imagem de referência).

IDEMPOTÊNCIA: criar um vídeo NÃO é idempotente (re-chamar gera — e cobra — outro).
A orquestração reexecuta um instrumento em falha RETENTÁVEL; então, UMA VEZ criado
o job, TODA falha aqui é NÃO-retentável, para nunca gerar/cobrar em dobro. Só a
falha de transporte ANTES de existir o job (nada gerado) é retentável.

CATÁLOGO ÚNICO (`CATALOGO_VIDEO`) é a fonte da verdade dos modelos e da
parametrização válida (tamanhos e durações por modelo). Dele saem o enum dos
campos, a validação do trio e as dependências de UI — como no gerar_imagem. Como a
OpenAI muda os parâmetros aceitos com o tempo, o `executar` traduz o erro da API
num recado ACIONÁVEL (qual parâmetro/mensagem/código foi recusado).
"""

import time
import uuid

import httpx
from pydantic import BaseModel, Field, model_validator

import arquivos
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar
from instrumentos.montar_imagem import _baixar
# `atividade` é folha (só contextvars + logging): importá-la aqui não cria ciclo, e é
# o que deixa o instrumento publicar sinal de vida DURANTE a espera.
from orquestracao import atividade

# Rede: cada request é rápido; o poll é o laço. Timeout generoso por request.
TIMEOUT_S = 60.0
URL_OPENAI = "https://api.openai.com/v1/videos"
# Poll até `completed`. Vídeo Sora leva minutos — e agora o teto é o que a GERAÇÃO
# precisa, não o que o vigia da fila permitia. Até 2026-09-03 este número era 120
# (~10 min) escolhido "para ficar abaixo do sweeper (TETO_INATIVIDADE_EXEC_MIN=15)":
# um instrumento contorcendo o próprio limite para fugir de um vigia que não olhava o
# sinal de vida. Com o vigia corrigido (Onda 3, lacuna 24), o laço publica atividade a
# cada volta e pode esperar o tempo real de um vídeo de 12 s em 1080p.
POLL_TENTATIVAS = 300  # 300 × 5 s = 25 min
POLL_INTERVALO_S = 5.0
TENTATIVAS_DOWNLOAD = 3
# De quantas em quantas voltas o cronômetro da frase de espera muda (~30 s).
VOLTAS_POR_AVISO = 6

def _frase_espera(volta: int) -> str:
    """O que a tela mostra enquanto o vídeo é gerado. Com o tempo decorrido a partir
    de meio minuto: sem número, uma espera de 20 minutos é indistinguível de um
    travamento (§12-A — o usuário precisa saber o que acontece o tempo todo)."""
    segundos = int(volta * POLL_INTERVALO_S)
    if segundos < 30:
        return "Gerando o vídeo — pode levar minutos…"
    if segundos < 120:
        return f"Gerando o vídeo… ({segundos} s)"
    return f"Gerando o vídeo… ({segundos // 60} min)"


_TAMANHOS_720 = ("720x1280", "1280x720")
_TAMANHOS_1080 = ("1080x1920", "1920x1080")
# Durações aceitas pela API de criação (enum "4"/"8"/"12" — verificado na doc OpenAI).
_DURACOES = ("4", "8", "12")

# ── FONTE ÚNICA DA VERDADE: modelos de vídeo e a parametrização válida de cada um ──
# Adicionar um modelo = uma entrada aqui (+ preço em precos.PRECOS_VIDEO_USD). O 1080p
# é só do pro; a doc confirma 16/20s no create tb, mas mantemos clipes curtos por custo
# (o preço é POR SEGUNDO) — 16/20 podem entrar aqui depois se preciso.
CATALOGO_VIDEO: dict[str, dict] = {
    "sora-2": {
        "rotulo": "Sora 2 (rápido e econômico, 720p)",
        "tamanhos": _TAMANHOS_720,
        "duracoes": _DURACOES,
    },
    "sora-2-pro": {
        "rotulo": "Sora 2 Pro (alta qualidade, até 1080p)",
        "tamanhos": _TAMANHOS_720 + _TAMANHOS_1080,
        "duracoes": _DURACOES,
    },
}

MODELO_PADRAO = "sora-2"
TAMANHO_PADRAO = "720x1280"  # vertical — reels/stories do Instagram
DURACAO_PADRAO = "8"


def _uniao_tamanhos() -> list[str]:
    """A união (sem repetir, ordem estável) de todos os tamanhos do catálogo — é o
    `enum` do campo `tamanho`; a UI o filtra por modelo via `dependencias_ui`."""
    vistos: list[str] = []
    for spec in CATALOGO_VIDEO.values():
        for t in spec["tamanhos"]:
            if t not in vistos:
                vistos.append(t)
    return vistos


class ConfigVideo(BaseModel):
    """Configuração fixa (o humano preenche; é o que a medição lê p/ estimar custo).

    `modelo`, `tamanho` e `duracao_s` são conjuntos fechados derivados do
    `CATALOGO_VIDEO` (a interface os mostra como dropdown, com tamanho/duração
    DEPENDENTES do modelo). `chave_api` é SEGREDO reusado do pool OpenAI da org."""

    provedor: str = Field(
        default="openai",
        title="Provedor",
        description="Provedor de geração de vídeo (por ora, só OpenAI/Sora).",
        json_schema_extra={"enum": ["openai"]},
    )
    modelo: str = Field(
        default=MODELO_PADRAO,
        title="Modelo do vídeo",
        description="sora-2 (mais barato, 720p) ou sora-2-pro (até 1080p, com áudio).",
        json_schema_extra={"enum": list(CATALOGO_VIDEO)},
    )
    tamanho: str = Field(
        default=TAMANHO_PADRAO,
        title="Tamanho",
        description="Resolução do vídeo (as opções dependem do modelo; 1080p só no pro).",
        json_schema_extra={"enum": _uniao_tamanhos()},
    )
    duracao_s: str = Field(
        default=DURACAO_PADRAO,
        title="Duração (segundos)",
        description="Duração do clipe. Cobrado POR SEGUNDO — mais longo custa proporcionalmente mais.",
        json_schema_extra={"enum": list(_DURACOES)},
    )
    chave_api: str = Field(
        default="",
        title="Chave da API (opcional)",
        description="Chave da API OpenAI (segredo). Em branco, usa a chave OpenAI da organização.",
    )

    @model_validator(mode="after")
    def _validar_combinacao(self) -> "ConfigVideo":
        """O trio modelo×tamanho×duração precisa ser válido no catálogo — senão a
        OpenAI recusaria com erro cru. Avisa claro já ao salvar/usar (backstop da
        IA criadora)."""
        spec = CATALOGO_VIDEO.get(self.modelo)
        if spec is None:
            raise ValueError(
                f"Modelo de vídeo desconhecido: '{self.modelo}'. "
                f"Use um destes: {', '.join(CATALOGO_VIDEO)}."
            )
        if self.tamanho not in spec["tamanhos"]:
            raise ValueError(
                f"O tamanho '{self.tamanho}' não vale para o modelo '{self.modelo}'. "
                f"Tamanhos válidos: {', '.join(spec['tamanhos'])}."
            )
        if self.duracao_s not in spec["duracoes"]:
            raise ValueError(
                f"A duração '{self.duracao_s}s' não vale para o modelo '{self.modelo}'. "
                f"Durações válidas: {', '.join(spec['duracoes'])} segundos."
            )
        return self


class ArgsVideo(BaseModel):
    """O que a IA passa: o roteiro e, opcional, uma imagem de partida (quadro inicial)."""

    prompt: str = Field(min_length=1, description="Descrição/roteiro do vídeo a gerar.")
    imagem_referencia_url: str = Field(
        default="",
        description=(
            "Opcional: URL PÚBLICA de uma imagem para ser o QUADRO INICIAL do vídeo "
            "(anima a partir dela — ex.: uma imagem gerada no passo anterior). A imagem "
            "deve ter a MESMA resolução (tamanho) configurada no instrumento. Sem rostos "
            "de pessoas reais/figuras públicas (a OpenAI recusa)."
        ),
    )


def _dimensoes_imagem(conteudo: bytes) -> tuple[int, int] | None:
    """Largura×altura de um PNG ou JPEG a partir dos bytes (sem dependência de
    imagem — lê o cabeçalho). Devolve (w, h) ou None quando não reconhece o formato
    (aí o pré-check de dimensão é PULADO, e a própria OpenAI valida)."""
    b = conteudo or b""
    if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:  # PNG: IHDR em offset 16
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    if b[:2] == b"\xff\xd8":  # JPEG: varre os marcadores até um SOF
        i, n = 2, len(b)
        while i + 9 < n:
            if b[i] != 0xFF:
                i += 1
                continue
            marcador = b[i + 1]
            # SOF0..SOF15 trazem as dimensões; DHT/JPG/DAC (C4/C8/CC) não.
            if 0xC0 <= marcador <= 0xCF and marcador not in (0xC4, 0xC8, 0xCC):
                if i + 9 <= n:
                    return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
                return None
            if i + 4 > n:
                break
            i += 2 + int.from_bytes(b[i + 2:i + 4], "big")  # pula o segmento
    return None


def _tamanho_para_par(tamanho: str) -> tuple[int, int] | None:
    """'720x1280' → (720, 1280). None se não for 'LxA' de inteiros."""
    try:
        w, h = (tamanho or "").lower().split("x")
        return int(w), int(h)
    except (ValueError, AttributeError):
        return None


def _erro_openai(status: int, resposta) -> str:
    """Traduz o erro da OpenAI num recado ACIONÁVEL: qual parâmetro, mensagem e
    código a API recusou (o que ajustar no catálogo quando a OpenAI mudar)."""
    try:
        erro = (resposta.json() or {}).get("error") or {}
    except ValueError:
        erro = {}
    mensagem = (erro.get("message") or (resposta.text or "")[:500] or "sem detalhes.").strip()
    codigo = erro.get("code")
    param = erro.get("param")
    cabeca = f"a geração de vídeo falhou (HTTP {status})"
    if param:
        cabeca += f" no parâmetro '{param}'"
    if codigo:
        mensagem = f"{mensagem} [{codigo}]"
    return f"{cabeca}: {mensagem}"


class GerarVideo(TipoInstrumento):
    tipo = "gerar_video"
    categoria = "Conteúdo"
    nome_exibicao = "Gerar vídeo"
    descricao = (
        "Gera um VÍDEO curto a partir de uma descrição (prompt), com a IA de vídeo da "
        "OpenAI (Sora), e devolve um link público (MP4). Pode ANIMAR a partir de uma "
        "imagem (passe a URL da imagem como quadro inicial — ex.: uma arte gerada antes). "
        "O vídeo sai com a marca d'água da OpenAI e leva alguns minutos para ficar pronto. "
        "Use o link no 'Instagram: publicar' para postar como reels, story de vídeo ou "
        "item de carrossel."
    )
    Config = ConfigVideo
    Args = ArgsVideo
    campos_secretos = ("chave_api",)
    # Reusa a chave OpenAI da organização ("Chaves de IA") quando o instrumento não
    # tem chave própria — a borda a injeta. Ver instrumentos/base.py.
    chave_compartilhada = ("chave_api", "openai")
    # acao_irreversivel = False (padrão): só gera um arquivo; quem PUBLICA (irreversível)
    # é o instrumento de publicação, num passo SEGUINTE com portão.

    def dependencias_ui(self) -> dict:
        """Ao escolher o `modelo`, só aparecem os tamanhos e durações válidos dele
        (do catálogo). Mecanismo genérico — ver `TipoInstrumento.dependencias_ui`."""
        return {
            "tamanho": {
                "controlado_por": "modelo",
                "opcoes": {m: list(s["tamanhos"]) for m, s in CATALOGO_VIDEO.items()},
            },
            "duracao_s": {
                "controlado_por": "modelo",
                "opcoes": {m: list(s["duracoes"]) for m, s in CATALOGO_VIDEO.items()},
            },
        }

    def executar(self, config: ConfigVideo, args: ArgsVideo) -> dict:
        if not config.chave_api:
            raise FalhaInstrumento(
                "falta a chave de API da OpenAI — configure-a no instrumento ou "
                "cadastre a chave OpenAI da organização em Chaves de IA.",
                retentavel=False,
            )
        headers = {"Authorization": f"Bearer {config.chave_api}"}
        # multipart/form-data: campos de texto como (None, valor) forçam o multipart
        # mesmo sem arquivo; o quadro inicial (se houver) vira um part de arquivo.
        partes: dict = {
            "model": (None, config.modelo),
            "prompt": (None, args.prompt),
            "size": (None, config.tamanho),
            "seconds": (None, str(config.duracao_s)),
        }
        ref = (args.imagem_referencia_url or "").strip()
        if ref:
            conteudo_ref, ct_ref = _baixar(ref)  # falha aqui é retentável (job ainda não existe)
            # Pré-checa a dimensão: a Sora EXIGE que a imagem de referência tenha
            # EXATAMENTE o tamanho do vídeo. Falhar aqui (com os números reais) é bem
            # mais claro do que o erro cru da OpenAI — e evita gastar uma chamada.
            dims = _dimensoes_imagem(conteudo_ref)
            alvo = _tamanho_para_par(config.tamanho)
            if dims is not None and alvo is not None and dims != alvo:
                raise FalhaInstrumento(
                    f"a imagem de referência é {dims[0]}×{dims[1]}, mas o vídeo está "
                    f"configurado para {config.tamanho}. A Sora exige que a imagem tenha "
                    f"EXATAMENTE o mesmo tamanho do vídeo — gere ou forneça a imagem em "
                    f"{config.tamanho} (ou ajuste o tamanho do vídeo no instrumento).",
                    retentavel=False,
                )
            partes["input_reference"] = ("referencia", conteudo_ref, ct_ref)

        with httpx.Client(timeout=TIMEOUT_S) as cli:
            # 1) CRIA o job. Falha ANTES de haver id → nada gerado → pode retentar.
            try:
                r = cli.post(URL_OPENAI, headers=headers, files=partes)
            except httpx.HTTPError as e:
                raise FalhaInstrumento(
                    f"não foi possível iniciar a geração de vídeo: {e}", retentavel=True
                )
            status = r.status_code
            if status in (401, 403):
                raise FalhaInstrumento(
                    "a chave de API da OpenAI foi recusada — verifique-a.",
                    retentavel=False,
                )
            if status == 429 or 500 <= status < 600:
                raise FalhaInstrumento(
                    f"o serviço de vídeo respondeu HTTP {status} ao iniciar.",
                    retentavel=True,
                )
            if not r.is_success:
                raise FalhaInstrumento(_erro_openai(status, r), retentavel=False)
            video_id = (r.json() or {}).get("id")
            if not video_id:
                raise FalhaInstrumento(
                    "a OpenAI não devolveu o id do vídeo.", retentavel=False
                )

            # 2) ESPERA o job. A PARTIR DAQUI, TUDO é NÃO-retentável (idempotência):
            # re-rodar o executar geraria/cobraria outro vídeo. Erros transitórios do
            # poll são reabsorvidos DENTRO do laço (dorme e reconfere), não sobem.
            estado = self._aguardar(cli, headers, video_id)
            if estado != "completed":
                raise FalhaInstrumento(
                    f"a geração de vídeo terminou em '{estado}'.", retentavel=False
                )

            # 3) BAIXA o MP4. Falha aqui também é NÃO-retentável (o job já foi cobrado);
            # tenta algumas vezes dentro do próprio passo.
            conteudo = self._baixar_conteudo(cli, headers, video_id)

        nome = f"{uuid.uuid4().hex}.mp4"
        url = arquivos.salvar(nome, conteudo, "video/mp4")
        return {
            "ok": True,
            "arquivo": nome,
            "url": url,
            "modelo": config.modelo,
            "duracao_s": config.duracao_s,
        }

    def _aguardar(self, cli, headers, video_id: str) -> str:
        """Poll do job até um estado terminal. Erros transitórios do GET NÃO sobem
        como retentáveis (o job existe/cobra) — dorme e reconfere. Devolve
        'completed'; `failed`/estouro do teto viram FalhaInstrumento não-retentável.

        A cada volta o laço PUBLICA sinal de vida (Onda 3, lacuna 24). Isso serve a
        duas pessoas ao mesmo tempo: quem olha a tela vê o cronômetro andando em vez de
        uma tela parada, e o vigia de execuções presas sabe que este passo está vivo —
        antes ele só via passos concluídos, e por isso este instrumento precisava
        encolher o próprio teto para não ser morto."""
        for volta in range(POLL_TENTATIVAS):
            # A cada ~30 s, não a cada volta: o batimento precisa ser MUITO mais
            # frequente que o teto do vigia (15 min), não a cada 5 s — isso seria uma
            # escrita no banco por volta, à toa.
            if volta % VOLTAS_POR_AVISO == 0:
                atividade.registrar(_frase_espera(volta))
            try:
                r = cli.get(f"{URL_OPENAI}/{video_id}", headers=headers)
            except httpx.HTTPError:
                time.sleep(POLL_INTERVALO_S)
                continue
            if r.is_success:
                dados = r.json() or {}
                estado = dados.get("status")
                if estado == "completed":
                    return "completed"
                if estado == "failed":
                    erro = dados.get("error") or {}
                    detalhe = erro.get("message") or erro.get("code") or "sem detalhe"
                    codigo = str(erro.get("code") or "")
                    alvo_moder = f"{detalhe} {codigo}".lower()
                    dica = ""
                    if any(t in alvo_moder for t in ("moderation", "moderação", "sentinel", "blocked")):
                        dica = (
                            " A Sora recusa pessoas reais, rostos reconhecíveis e figuras "
                            "públicas — tanto no roteiro quanto na imagem de referência. "
                            "Ajuste o prompt/imagem e tente de novo."
                        )
                    raise FalhaInstrumento(
                        f"a OpenAI não conseguiu gerar o vídeo: {detalhe}.{dica}",
                        retentavel=False,
                    )
                # queued / in_progress → continua o laço
            elif r.status_code in (401, 403):
                raise FalhaInstrumento(
                    "a chave de API da OpenAI foi recusada durante o acompanhamento.",
                    retentavel=False,
                )
            time.sleep(POLL_INTERVALO_S)
        raise FalhaInstrumento(
            "a geração de vídeo demorou além do tempo limite do Batuta.",
            retentavel=False,
        )

    def _baixar_conteudo(self, cli, headers, video_id: str) -> bytes:
        """Baixa o MP4 pronto. Não-retentável no nível do instrumento (o job já foi
        cobrado); tenta algumas vezes por dentro antes de desistir."""
        url = f"{URL_OPENAI}/{video_id}/content"
        ultimo = "sem detalhe"
        for _ in range(TENTATIVAS_DOWNLOAD):
            try:
                r = cli.get(url, headers=headers, params={"variant": "video"})
            except httpx.HTTPError as e:
                ultimo = str(e)
                time.sleep(POLL_INTERVALO_S)
                continue
            if r.is_success and r.content:
                return r.content
            ultimo = f"HTTP {r.status_code}"
            time.sleep(POLL_INTERVALO_S)
        raise FalhaInstrumento(
            f"o vídeo foi gerado mas não pôde ser baixado ({ultimo}).",
            retentavel=False,
        )


registrar(GerarVideo())
