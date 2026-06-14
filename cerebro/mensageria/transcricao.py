"""Transcrição de áudio (Fase H) — fala vira texto antes de chegar ao agente.

Usa a API de transcrição da OpenAI (Whisper), reusando a chave OpenAI do cofre
(resolvida por organização). Mantida isolada para o resto da mensageria não
conhecer o provedor. Não toca o núcleo de orquestração.
"""

import httpx

API = "https://api.openai.com/v1/audio/transcriptions"
MODELO = "whisper-1"
TIMEOUT_S = 60.0


def transcrever(audio: bytes, chave_openai: str, *, nome: str = "audio.oga") -> str:
    """Transcreve o áudio (bytes) para texto. Levanta em falha de rede/HTTP —
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
