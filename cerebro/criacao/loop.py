"""O laço de conversa da IA criadora — conversa eterna sobre o time real.

Um turno: a mensagem do consultor entra, a IA raciocina e usa as ferramentas (que
agora escrevem no TIME REAL, via `criacao.servicos`), e devolvemos a resposta + os
chips + a fotografia do time. Reusa o `create_react_agent` do LangGraph (mesmo motor
de tool-use do `orquestracao.agente`).

A persistência é direta e inspecionável: o histórico vive em
`conversas_criacao.mensagens` (JSONB) e o ESTADO real é o próprio time (tabelas).
`responder_turno` muta a conversa e as linhas do time na sessão recebida, mas NÃO faz
commit — quem chama (a rota) controla a transação do turno.
"""

from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from criacao.ferramentas import (
    ContextoCriacao,
    montar_ferramentas,
    snapshot_time,
)
from criacao.prompt import montar_prompt_criadora
from orquestracao.llm import construir_modelo, texto_da_resposta, usar_chaves

# Modelo da criadora: o MAIS capaz (Opus). A criadora é uma consultora sênior que
# projeta o time inteiro e escreve a documentação de cada agente — qualidade de
# raciocínio importa mais que custo aqui (uso esporádico). É Anthropic, então cai na
# ANTHROPIC_API_KEY do .env quando não há chave de 'criadora' no cofre.
MODELO_CRIADORA = "claude-opus-4-8"


def _historico_para_mensagens(mensagens: list | None) -> list[dict]:
    """Converte o histórico salvo (papel/conteúdo) no formato de mensagens do
    agente. Só as falas de texto entram; o estado real vem do time."""
    saida: list[dict] = []
    for m in mensagens or []:
        papel = m.get("papel")
        conteudo = m.get("conteudo", "")
        if papel == "usuario":
            saida.append({"role": "user", "content": conteudo})
        elif papel == "ia":
            saida.append({"role": "assistant", "content": conteudo})
    return saida


def responder_turno(
    sessao: Session,
    conversa,
    mensagem_usuario: str,
    *,
    usuario=None,
    chaves: dict[str, str] | None = None,
    origem: str = "legado",
    modelo: str = MODELO_CRIADORA,
) -> dict:
    """Roda um turno. Muta `conversa.mensagens` e, via ferramentas, o time real (sem
    commit) e devolve {resposta, chips, time_id, time, uso}."""
    ctx = ContextoCriacao(sessao=sessao, conversa=conversa, usuario=usuario)
    ferramentas = montar_ferramentas(ctx)
    prompt = montar_prompt_criadora(snapshot_time(sessao, conversa))

    historico = _historico_para_mensagens(conversa.mensagens) + [
        {"role": "user", "content": mensagem_usuario}
    ]
    with usar_chaves(chaves):
        modelo_chat = construir_modelo(modelo, temperatura=0.3)
        app = create_react_agent(modelo_chat, ferramentas, prompt=prompt)
        resultado = app.invoke({"messages": historico})

    # O react agent devolve o HISTÓRICO INTEIRO + as mensagens novas deste turno.
    # Só nos interessam as NOVAS (depois do que enviamos).
    novas = resultado["messages"][len(historico) :]

    # Texto da resposta + medição num passo só. O modelo (Anthropic) costuma emitir o
    # texto JUNTO com as chamadas de ferramenta, e o ÚLTIMO AIMessage pode vir vazio —
    # por isso juntamos o texto de TODOS os turnos do modelo deste turno.
    textos: list[str] = []
    tokens_entrada = tokens_saida = 0
    for m in novas:
        if isinstance(m, AIMessage):
            trecho = texto_da_resposta(m).strip()
            if trecho:
                textos.append(trecho)
            u = m.usage_metadata or {}
            tokens_entrada += u.get("input_tokens", 0)
            tokens_saida += u.get("output_tokens", 0)
    resposta_texto = "\n\n".join(textos) if textos else "Pronto, atualizei o time."
    uso = {
        "modelo": modelo,
        "tokens_entrada": tokens_entrada,
        "tokens_saida": tokens_saida,
        "origem": origem,
    }

    conversa.mensagens = (conversa.mensagens or []) + [
        {"papel": "usuario", "conteudo": mensagem_usuario},
        {"papel": "ia", "conteudo": resposta_texto, "chips": ctx.chips, "uso": uso},
    ]
    return {
        "resposta": resposta_texto,
        "chips": ctx.chips,
        "time_id": str(conversa.time_id) if conversa.time_id else None,
        "time": snapshot_time(sessao, conversa),
        "uso": uso,
    }
