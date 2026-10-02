"""Instrumento "Gerar vídeo" (PRODUTO §13; corrente de conteúdo).

Gera um VÍDEO curto (4, 6 ou 8 s, COM ÁUDIO) a partir de uma descrição (prompt) com o
Veo 3.1, a IA de vídeo do Google, e devolve um link público para o MP4. Texto→vídeo;
opcionalmente imagem→vídeo, animando a partir de um quadro inicial (ex.: uma imagem
gerada antes). A chave é a do Google do pool da organização. O arquivo é baixado e
guardado no armazenamento do Batuta — a URL pública serve direto a um instrumento de
publicação (reels, story de vídeo ou carrossel).

HISTÓRIA: até 24/09/2026 este instrumento usava a Sora (OpenAI), que a OpenAI desligou
sem substituto; o Gerar vídeo ficou fora do ar até voltar pelo Google (2026-10-02).
Uma configuração antiga de Sora se converte sozinha para o Veo (`_curar_sora`).

Ciclo ASSÍNCRONO (operação longa do Google): CRIA a operação (`generate_videos`),
ESPERA (consulta a operação até `done` — de ~11 s a 6 min) e BAIXA o vídeo (fica só 2
dias no Google). A espera publica sinal de vida com o tempo decorrido (§12-A), e o
vigia de execuções presas lê esse sinal (Onda 3, lacuna 24).

IDEMPOTÊNCIA: criar um vídeo NÃO é idempotente (re-chamar gera — e cobra — outro). A
orquestração reexecuta um instrumento em falha RETENTÁVEL; então, UMA VEZ criada a
operação, TODA falha aqui é NÃO-retentável, para nunca gerar/cobrar em dobro. Só a
falha ANTES de existir a operação (nada gerado) pode ser retentável.

CATÁLOGO ÚNICO (`CATALOGO_VIDEO`): modelos, proporções, resoluções e durações válidas
de cada um. Dele saem o enum dos campos, a validação e as dependências de UI.
Regra do Google: 1080p e 4K só com 8 segundos. Todo vídeo do Google sai com a marca
invisível SynthID. Preço por segundo: `precos.PRECOS_VIDEO_USD`.
"""

import time
import uuid

from google.genai import errors
from google.genai import types as gtypes
from pydantic import BaseModel, Field, model_validator

import arquivos
from instrumentos import google_servidor as goo
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar
from instrumentos.montar_imagem import _baixar
# `atividade` é folha (só contextvars + logging): importá-la aqui não cria ciclo, e é
# o que deixa o instrumento publicar sinal de vida DURANTE a espera.
from orquestracao import atividade

TIMEOUT_S = 120.0
# Consulta a operação até `done`. O Google diz de 11 s a 6 min; folga para o pico.
POLL_TENTATIVAS = 150  # 150 × 10 s = 25 min
POLL_INTERVALO_S = 10.0
TENTATIVAS_DOWNLOAD = 3
# De quantas em quantas voltas o cronômetro da frase de espera muda (~30 s).
VOLTAS_POR_AVISO = 3


def _frase_espera(volta: int) -> str:
    """O que a tela mostra enquanto o vídeo é gerado, com o tempo decorrido a partir
    de meio minuto (§12-A — o usuário precisa saber o que acontece o tempo todo)."""
    segundos = int(volta * POLL_INTERVALO_S)
    if segundos < 30:
        return "Gerando o vídeo — pode levar minutos…"
    if segundos < 120:
        return f"Gerando o vídeo… ({segundos} s)"
    return f"Gerando o vídeo… ({segundos // 60} min)"


_PROPORCOES = ("9:16", "16:9")
_DURACOES = ("4", "6", "8")

# ── FONTE ÚNICA DA VERDADE: modelos de vídeo e a parametrização válida de cada um ──
# ai.google.dev/gemini-api/docs/veo (2026-10-02). Adicionar um modelo = uma entrada
# aqui (+ preço em precos.PRECOS_VIDEO_USD + registro em ciclo_modelos).
CATALOGO_VIDEO: dict[str, dict] = {
    "veo-3.1-lite-generate-preview": {
        "rotulo": "Veo 3.1 Lite (o mais barato)",
        "tamanhos": _PROPORCOES,
        "resolucoes": ("720p", "1080p"),
        "duracoes": _DURACOES,
    },
    "veo-3.1-fast-generate-preview": {
        "rotulo": "Veo 3.1 Fast (rápido, até 4K)",
        "tamanhos": _PROPORCOES,
        "resolucoes": ("720p", "1080p", "4k"),
        "duracoes": _DURACOES,
    },
    "veo-3.1-generate-preview": {
        "rotulo": "Veo 3.1 (melhor qualidade, até 4K)",
        "tamanhos": _PROPORCOES,
        "resolucoes": ("720p", "1080p", "4k"),
        "duracoes": _DURACOES,
    },
}

MODELO_PADRAO = "veo-3.1-lite-generate-preview"
TAMANHO_PADRAO = "9:16"  # vertical — reels/stories
RESOLUCAO_PADRAO = "720p"
DURACAO_PADRAO = "8"


def _uniao(chave: str) -> list[str]:
    vistos: list[str] = []
    for spec in CATALOGO_VIDEO.values():
        for v in spec[chave]:
            if v not in vistos:
                vistos.append(v)
    return vistos


class ConfigVideo(BaseModel):
    """Configuração fixa (o humano preenche; é o que a medição lê p/ estimar custo).
    Conjuntos fechados derivados do `CATALOGO_VIDEO`, com resolução/duração
    DEPENDENTES do modelo na tela."""

    modelo: str = Field(
        default=MODELO_PADRAO,
        title="Modelo do vídeo",
        description="Veo 3.1 Lite (US$ 0,05 a 0,08 por segundo), Fast (US$ 0,10 a 0,30) "
        "ou o completo (US$ 0,40 a 0,60). Todos geram o áudio junto.",
        json_schema_extra={"enum": list(CATALOGO_VIDEO)},
    )
    tamanho: str = Field(
        default=TAMANHO_PADRAO,
        title="Proporção",
        description="9:16 = vertical (reels, stories); 16:9 = horizontal.",
        json_schema_extra={"enum": _uniao("tamanhos")},
    )
    resolucao: str = Field(
        default=RESOLUCAO_PADRAO,
        title="Resolução",
        description="1080p e 4K custam mais e só saem com 8 segundos.",
        json_schema_extra={"enum": _uniao("resolucoes")},
    )
    duracao_s: str = Field(
        default=DURACAO_PADRAO,
        title="Duração (segundos)",
        description="Cobrado POR SEGUNDO — mais longo custa proporcionalmente mais.",
        json_schema_extra={"enum": list(_DURACOES)},
    )

    @model_validator(mode="before")
    @classmethod
    def _curar_sora(cls, dados):
        """Configuração da época da Sora (desligada em 24/09/2026): vira o Veo, com a
        mesma orientação. Sem migração de banco — a cura acontece ao validar."""
        if not isinstance(dados, dict):
            return dados
        dados = {k: v for k, v in dados.items() if k not in ("provedor", "chave_api")}
        if str(dados.get("modelo") or "").startswith("sora"):
            largura, _, altura = str(dados.get("tamanho") or "720x1280").partition("x")
            vertical = not (largura.isdigit() and altura.isdigit()) or int(altura) >= int(largura)
            dados.update(modelo=MODELO_PADRAO, tamanho="9:16" if vertical else "16:9",
                         resolucao=RESOLUCAO_PADRAO)
            if str(dados.get("duracao_s")) not in _DURACOES:
                dados["duracao_s"] = DURACAO_PADRAO
        return dados

    @model_validator(mode="after")
    def _validar_combinacao(self) -> "ConfigVideo":
        """Modelo×proporção×resolução×duração válidos no catálogo — senão o Google
        recusaria com erro cru. Avisa claro já ao salvar/usar (backstop da IA criadora)."""
        spec = CATALOGO_VIDEO.get(self.modelo)
        if spec is None:
            raise ValueError(
                f"Modelo de vídeo desconhecido: '{self.modelo}'. "
                f"Use um destes: {', '.join(CATALOGO_VIDEO)}."
            )
        for campo, valor, validos in (
            ("proporção", self.tamanho, spec["tamanhos"]),
            ("resolução", self.resolucao, spec["resolucoes"]),
            ("duração", self.duracao_s, spec["duracoes"]),
        ):
            if valor not in validos:
                raise ValueError(
                    f"A {campo} '{valor}' não vale para o modelo '{self.modelo}'. "
                    f"Válidas: {', '.join(validos)}."
                )
        if self.resolucao != "720p" and self.duracao_s != "8":
            raise ValueError("Vídeo em 1080p ou 4K só sai com 8 segundos — ajuste a duração.")
        return self


class ArgsVideo(BaseModel):
    """O que a IA passa: o roteiro e, opcional, uma imagem de partida (quadro inicial)."""

    prompt: str = Field(
        min_length=1,
        description="Descrição/roteiro do vídeo: cena, movimento de câmera, clima e, se "
        "houver, as falas e os sons (o vídeo sai com áudio).",
    )
    imagem_referencia_url: str = Field(
        default="",
        description=(
            "Opcional: URL PÚBLICA de uma imagem para ser o QUADRO INICIAL do vídeo "
            "(anima a partir dela — ex.: uma imagem gerada no passo anterior), de "
            "preferência na mesma proporção do vídeo."
        ),
    )


class GerarVideo(TipoInstrumento):
    tipo = "gerar_video"
    # Instrumento do Google: só existe para a organização que tem a chave dele.
    provedores_ia = ("google",)
    categoria = "Conteúdo"
    nome_exibicao = "Gerar vídeo"
    descricao = (
        "Gera um VÍDEO curto (4 a 8 segundos, com áudio) a partir de uma descrição, com "
        "a IA de vídeo do Google (Veo), e devolve um link público (MP4). Pode ANIMAR a "
        "partir de uma imagem (passe a URL da imagem como quadro inicial — ex.: uma arte "
        "gerada antes). Leva de segundos a alguns minutos. Use o link no instrumento de "
        "publicação para postar como reels, story de vídeo ou item de carrossel."
    )
    Config = ConfigVideo
    Args = ArgsVideo
    # acao_irreversivel = False (padrão): só gera um arquivo; quem PUBLICA (irreversível)
    # é o instrumento de publicação, num passo seguinte.

    def dependencias_ui(self) -> dict:
        """Ao escolher o `modelo`, só aparecem as resoluções e durações válidas dele."""
        return {
            "tamanho": {
                "controlado_por": "modelo",
                "opcoes": {m: list(s["tamanhos"]) for m, s in CATALOGO_VIDEO.items()},
            },
            "resolucao": {
                "controlado_por": "modelo",
                "opcoes": {m: list(s["resolucoes"]) for m, s in CATALOGO_VIDEO.items()},
            },
            "duracao_s": {
                "controlado_por": "modelo",
                "opcoes": {m: list(s["duracoes"]) for m, s in CATALOGO_VIDEO.items()},
            },
        }

    def executar(self, config: ConfigVideo, args: ArgsVideo) -> dict:
        cli = goo.cliente(TIMEOUT_S)
        imagem = None
        ref = (args.imagem_referencia_url or "").strip()
        if ref:
            conteudo_ref, ct_ref = _baixar(ref)  # falha aqui é retentável (nada criado)
            imagem = gtypes.Image(image_bytes=conteudo_ref, mime_type=ct_ref)

        # 1) CRIA a operação. Falha ANTES de haver operação → nada gerado → a tradução
        # decide se vale tentar de novo.
        try:
            operacao = cli.models.generate_videos(
                model=config.modelo, prompt=args.prompt, image=imagem,
                config=gtypes.GenerateVideosConfig(
                    aspect_ratio=config.tamanho, resolution=config.resolucao,
                    duration_seconds=int(config.duracao_s), number_of_videos=1,
                ),
            )
        except errors.APIError as e:
            raise goo.traduzir_excecao(e, config.modelo) from e
        except Exception as e:  # nada foi criado: a tradução decide se vale repetir
            raise goo.falha_inesperada(e) from e

        # 2) ESPERA. A PARTIR DAQUI, TUDO é NÃO-retentável (idempotência).
        operacao = self._aguardar(cli, operacao)
        video = self._video_pronto(operacao)

        # 3) BAIXA o MP4 (também não-retentável: já foi cobrado).
        conteudo = self._baixar_conteudo(cli, video)
        nome = f"{uuid.uuid4().hex}.mp4"
        url = arquivos.salvar(nome, conteudo, "video/mp4")
        return {
            "ok": True,
            "arquivo": nome,
            "url": url,
            "modelo": config.modelo,
            "duracao_s": config.duracao_s,
            "resolucao": config.resolucao,
        }

    def _aguardar(self, cli, operacao):
        """Consulta a operação até `done`. Erro transitório na consulta NÃO sobe (a
        operação existe e cobra): dorme e reconfere. A cada ~30 s publica sinal de
        vida — quem olha a tela vê o cronômetro, e o vigia sabe que o passo está vivo."""
        for volta in range(POLL_TENTATIVAS):
            if getattr(operacao, "done", False):
                return operacao
            if volta % VOLTAS_POR_AVISO == 0:
                atividade.registrar(_frase_espera(volta))
            time.sleep(POLL_INTERVALO_S)
            try:
                operacao = cli.operations.get(operacao)
            except Exception:
                continue
        raise FalhaInstrumento(
            "a geração de vídeo demorou além do tempo limite do Batuta (25 min).",
            retentavel=False,
        )

    def _video_pronto(self, operacao):
        erro = getattr(operacao, "error", None)
        if erro:
            detalhe = erro.get("message") if isinstance(erro, dict) else str(erro)
            raise FalhaInstrumento(
                f"o Google não conseguiu gerar o vídeo: {detalhe or 'sem detalhe'}.",
                retentavel=False,
            )
        resposta = getattr(operacao, "response", None) or getattr(operacao, "result", None)
        videos = list(getattr(resposta, "generated_videos", None) or [])
        if videos and getattr(videos[0], "video", None):
            return videos[0].video
        motivos = list(getattr(resposta, "rai_media_filtered_reasons", None) or [])
        if motivos:
            raise FalhaInstrumento(
                "o Google recusou o vídeo pela política de segurança dele: "
                + "; ".join(str(m) for m in motivos)
                + ". Ajuste o roteiro (ou a imagem de partida) e tente de novo.",
                retentavel=False, codigo="ia.recusa",
            )
        raise FalhaInstrumento("o Google terminou sem devolver o vídeo.", retentavel=False)

    def _baixar_conteudo(self, cli, video) -> bytes:
        """Baixa o MP4 pronto (fica só 2 dias no Google). Não-retentável no nível do
        instrumento (já foi cobrado); tenta algumas vezes por dentro."""
        ultimo = "sem detalhe"
        for _ in range(TENTATIVAS_DOWNLOAD):
            try:
                conteudo = cli.files.download(file=video)
            except Exception as e:
                ultimo = str(e)[:200]
                time.sleep(POLL_INTERVALO_S)
                continue
            if conteudo:
                return conteudo
            ultimo = "arquivo vazio"
        raise FalhaInstrumento(
            f"o vídeo foi gerado mas não pôde ser baixado ({ultimo}).",
            retentavel=False,
        )


registrar(GerarVideo())
