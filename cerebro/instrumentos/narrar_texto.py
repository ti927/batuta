"""Instrumento "Narrar texto" — transforma um texto em ÁUDIO falado, com a voz do Google
(Gemini TTS, 2026-10-02). Serve para: a versão em áudio de um post, uma mensagem de voz
para o cliente, a locução de um vídeo.

Devolve um link público para o arquivo WAV (24 kHz, mono). O Google devolve o áudio
pronto (com cabeçalho WAV) ou cru (PCM 16 bits) — no segundo caso o Batuta põe o
cabeçalho (`wave`, sem dependência nova). Preço: por token de áudio gerado (cerca de
US$ 0,002 a cada 10 s no Flash, menos no Flash-Lite; sobe em 01/01/2027), devolvido em
`uso` para a medição real. Só gera um arquivo → não é ação irreversível.

Fora de propósito: OpenAI. A OpenAI anunciou em 01/10/2026 o desligamento dos modelos
de voz dela em 06/01/2027, com substituto de outro tipo (tempo real).
"""

import io
import uuid
import wave

from google.genai import errors
from google.genai import types as gtypes
from pydantic import BaseModel, Field

import arquivos
from instrumentos import google_servidor as goo
from instrumentos.anthropic_servidor import _com_batimento
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

TIMEOUT_S = 180.0
TAXA_HZ = 24_000
MAX_CARACTERES = 5_000

# ai.google.dev/gemini-api/docs/pricing (2026-10-02): por 1 milhão de tokens.
# O áudio de SAÍDA custa bem mais que o texto de entrada.
PRECOS_VOZ = {
    "gemini-3.8-flash-tts": (0.50, 9.00),
    "gemini-3.8-flash-lite-tts": (0.50, 6.00),
}
MODELO_PADRAO = "gemini-3.8-flash-lite-tts"

# As 30 vozes prontas do Google (o caráter de cada uma, segundo o Google).
VOZES = {
    "Kore": "firme", "Puck": "animada", "Charon": "informativa", "Fenrir": "empolgada",
    "Leda": "jovem", "Orus": "firme", "Aoede": "leve", "Zephyr": "clara",
    "Callirrhoe": "tranquila", "Autonoe": "clara", "Enceladus": "sussurrada",
    "Iapetus": "nítida", "Umbriel": "tranquila", "Algieba": "suave", "Despina": "suave",
    "Erinome": "nítida", "Algenib": "rouca", "Rasalgethi": "informativa",
    "Laomedeia": "animada", "Achernar": "macia", "Alnilam": "firme", "Schedar": "equilibrada",
    "Gacrux": "madura", "Pulcherrima": "direta", "Achird": "amigável",
    "Zubenelgenubi": "descontraída", "Vindemiatrix": "gentil", "Sadachbia": "vivaz",
    "Sadaltager": "experiente", "Sulafat": "calorosa",
}


class ConfigNarrar(BaseModel):
    modelo: str = Field(
        default=MODELO_PADRAO,
        title="Modelo da voz",
        description="Flash-Lite (mais barato) ou Flash (mais expressivo).",
        json_schema_extra={"enum": list(PRECOS_VOZ)},
    )
    voz: str = Field(
        default="Kore",
        title="Voz",
        description="Algumas: Kore (firme), Puck (animada), Charon (informativa), Achird "
        "(amigável), Sulafat (calorosa), Gacrux (madura). Vale ouvir antes de escolher.",
        json_schema_extra={"enum": list(VOZES)},
    )
    tom: str = Field(
        default="",
        title="Jeito de falar (opcional)",
        description="Ex.: animado e próximo, como num podcast; calmo e acolhedor.",
    )


class ArgsNarrar(BaseModel):
    texto: str = Field(
        min_length=1, max_length=MAX_CARACTERES,
        description="O texto a ser falado, exatamente como deve soar (até 5 mil "
        "caracteres). Pausas e respirações podem ir entre sinais: <short pause>, <sigh>.",
    )


def _como_wav(dados: bytes) -> bytes:
    """O áudio como WAV: se já vem com cabeçalho, como veio; se vem cru (PCM 16 bits,
    24 kHz, mono), com o cabeçalho que falta."""
    if dados[:4] == b"RIFF":
        return dados
    saida = io.BytesIO()
    with wave.open(saida, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA_HZ)
        arquivo.writeframes(dados)
    return saida.getvalue()


def _segundos(wav: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav), "rb") as arquivo:
            return round(arquivo.getnframes() / float(arquivo.getframerate() or TAXA_HZ), 1)
    except (wave.Error, EOFError):
        return 0.0


class NarrarTexto(TipoInstrumento):
    tipo = "narrar_texto"
    provedores_ia = ("google",)
    categoria = "Conteúdo"
    nome_exibicao = "Narrar texto (voz)"
    descricao = (
        "Transforma um texto em ÁUDIO falado, em português, com uma voz do Google, e "
        "devolve o link do arquivo (WAV). Use para a versão em áudio de um conteúdo, uma "
        "mensagem de voz ou a locução de um vídeo."
    )
    Config = ConfigNarrar
    Args = ArgsNarrar

    def executar(self, config: ConfigNarrar, args: ArgsNarrar) -> dict:
        cli = goo.cliente(TIMEOUT_S)
        # O jeito de falar vai entre colchetes antes do texto: o modelo de voz não aceita
        # instrução de sistema, e o que está entre colchetes ele usa sem ler em voz alta
        # (conferido ao vivo em 02/10/2026, transcrevendo o próprio áudio gerado).
        texto = f"[{config.tom.strip()}] {args.texto}" if config.tom.strip() else args.texto
        criar = lambda: cli.models.generate_content(  # noqa: E731
            model=config.modelo,
            contents=[texto],
            config=gtypes.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=gtypes.SpeechConfig(
                    language_code="pt-BR",
                    voice_config=gtypes.VoiceConfig(
                        prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(voice_name=config.voz),
                    ),
                ),
            ),
        )
        try:
            resposta = _com_batimento(criar, "Gravando a narração")
        except errors.APIError as e:
            raise goo.traduzir_excecao(e, config.modelo) from e
        except Exception as e:
            raise goo.falha_inesperada(e) from e

        audio = None
        for candidato in resposta.candidates or []:
            for parte in getattr(candidato.content, "parts", None) or []:
                dados = getattr(parte, "inline_data", None)
                if dados and dados.data:
                    audio = dados.data
                    break
        if not audio:
            raise FalhaInstrumento(
                "o Google não devolveu o áudio (pode ter recusado o texto pela política de "
                "segurança dele).", retentavel=False, codigo="google.sem_audio",
            )
        wav = _como_wav(audio)
        nome = f"{uuid.uuid4().hex}.wav"
        url = arquivos.salvar(nome, wav, "audio/wav")
        return {
            "ok": True, "arquivo": nome, "url": url, "segundos": _segundos(wav),
            "uso": _uso(config.modelo, resposta),
        }


def _uso(modelo: str, resposta) -> dict:
    u = resposta.usage_metadata
    entrada = getattr(u, "prompt_token_count", 0) or 0
    saida = getattr(u, "candidates_token_count", 0) or 0
    pe, ps = PRECOS_VOZ.get(modelo, PRECOS_VOZ[MODELO_PADRAO])
    return {
        "modelo": modelo, "tokens_entrada": entrada, "tokens_saida": saida,
        "custo_usd": round((entrada * pe + saida * ps) / 1_000_000, 6),
    }


registrar(NarrarTexto())
