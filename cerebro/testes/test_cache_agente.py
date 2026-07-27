"""Cache de prompt do agente (motor de conversa e de execução): SÓ na Anthropic.

O `create_react_agent` reenvia [ferramentas + prompt de sistema] a cada passo do laço
e a cada turno; marcar o `cache_control` no `SystemMessage` faz esses reenvios custarem
~10% (economia de tokens). `cache_control` é específico da Anthropic — em OpenAI/Google
(ou modelo desconhecido) o prompt vai como texto puro, senão quebraria/seria ignorado.
Espelha o guard da IA criadora (`criacao/prompt.prompt_criadora`)."""

from langchain_core.messages import SystemMessage

from orquestracao.agente import _prompt_de_sistema


def test_prompt_de_sistema_cacheia_so_na_anthropic():
    for modelo in ("claude-sonnet-5", "claude-opus-4-8"):
        p = _prompt_de_sistema("INSTRUÇÕES", modelo)
        assert isinstance(p, SystemMessage)
        assert p.content[0]["text"] == "INSTRUÇÕES"
        assert p.content[0]["cache_control"] == {"type": "ephemeral"}


def test_prompt_de_sistema_texto_puro_nos_outros_provedores():
    # OpenAI/Google/desconhecido → texto puro (sem cache_control, que quebraria lá).
    for modelo in ("gpt-4o", "gemini-2.5-pro", "modelo-desconhecido-xyz"):
        p = _prompt_de_sistema("INSTRUÇÕES", modelo)
        assert p == "INSTRUÇÕES"
