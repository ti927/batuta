"""Transcrição de áudio (Fase H) — fala vira texto antes de chegar ao agente.

Duas IAs, escolhidas pela chave da organização (2026-10-02):

- GOOGLE primeiro, quando há a chave dele: aceita o áudio do Telegram como ele chega
  (OGG/Opus) e não tem data para sair;
- OPENAI (Whisper) como antes. O `whisper-1` sai em 26/02/2027, e o substituto
  (`gpt-transcribe`) não aceita OGG — para quem só tem a chave da OpenAI, isso ainda
  precisa de solução antes dessa data.

Se o Google falha e há chave da OpenAI, tenta a OpenAI (o atendimento não depende de
uma IA só). Mantida isolada para o resto da mensageria não conhecer o provedor.
"""

import httpx

API = "https://api.openai.com/v1/audio/transcriptions"
MODELO = "whisper-1"
# Flash-Lite: o mais barato que entende áudio (ai.google.dev/gemini-api/docs/audio).
MODELO_GOOGLE = "gemini-3.5-flash-lite"
TIMEOUT_S = 60.0
INSTRUCAO_GOOGLE = (
    "Transcreva este áudio em português, palavra por palavra, sem comentar, resumir ou "
    "traduzir. Devolva só o texto falado. Se não houver fala, devolva vazio."
)


def transcrever(audio: bytes, chave_openai: str, *, nome: str = "audio.oga") -> str:
    """Transcreve o áudio (bytes) pela OpenAI (Whisper). Levanta em falha de rede/HTTP —
    o chamador trata (cai num aviso gentil)."""
    with httpx.Client(timeout=TIMEOUT_S) as cliente:
        resposta = cliente.post(
            API,
            headers={"Authorization": f"Bearer {chave_openai}"},
            files={"file": (nome, audio, "audio/ogg")},
            data={"model": MODELO},
        )
    resposta.raise_for_status()
    return (resposta.json().get("text") or "").strip()


def transcrever_google(audio: bytes, chave_google: str) -> str:
    """Transcreve o áudio (bytes, OGG) pelo Google. Levanta em falha — o chamador trata."""
    from google import genai
    from google.genai import types

    cliente = genai.Client(
        api_key=chave_google, http_options=types.HttpOptions(timeout=int(TIMEOUT_S * 1000)),
    )
    resposta = cliente.models.generate_content(
        model=MODELO_GOOGLE,
        contents=[types.Part.from_bytes(data=audio, mime_type="audio/ogg"), INSTRUCAO_GOOGLE],
    )
    return (resposta.text or "").strip()


def transcrever_com_a_chave_que_houver(audio: bytes, chaves: dict) -> tuple[str, str, str]:
    """(texto, modelo, provedor) pela melhor IA com chave. Levanta se nenhuma deu certo
    (ou se não há chave de nenhuma)."""
    erro: Exception | None = None
    if chaves.get("google"):
        try:
            return transcrever_google(audio, chaves["google"]), MODELO_GOOGLE, "google"
        except Exception as e:  # cai para a OpenAI, se houver — mas nunca calado
            erro = e
            from observabilidade.escritor import registrar_evento

            registrar_evento(
                categoria="mensageria", acao="transcricao.google_falhou", nivel="warning",
                erro=e, detalhe={"cai_para_openai": bool(chaves.get("openai"))},
            )
    if chaves.get("openai"):
        return transcrever(audio, chaves["openai"]), MODELO, "openai"
    raise erro or RuntimeError("sem chave de IA para transcrever áudio")
