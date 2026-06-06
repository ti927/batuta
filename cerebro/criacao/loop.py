"""O laço de conversa da IA criadora (Fase 9).

Um turno: a mensagem do consultor entra, a IA raciocina e usa as ferramentas
(que mutam o rascunho em memória), e devolvemos a resposta + os chips + o rascunho
atualizado. Reusa o `create_react_agent` do LangGraph (mesmo motor de tool-use do
`orquestracao.agente`).

A persistência entre turnos é simples e inspecionável: o histórico vive em
`conversas_criacao.mensagens` (JSONB) e o ESTADO real (o rascunho) em
`conversas_criacao.rascunho` (JSONB). A cada turno, recarregamos os dois,
rodamos, e regravamos — sem checkpointer do LangGraph. `responder_turno` muta o
objeto da conversa mas NÃO faz commit; quem chama (a rota) controla a transação.
"""

from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from criacao.ferramentas import EstadoCriacao, montar_ferramentas
from criacao.prompt import montar_prompt_criadora
from criacao.rascunho import Rascunho
from orquestracao.llm import construir_modelo, texto_da_resposta, usar_chaves

# Modelo da criadora: um modelo forte de raciocínio monta uma estrutura melhor.
# É Anthropic, então cai na ANTHROPIC_API_KEY do .env quando não há chave de
# 'criadora' no cofre. Facilmente trocável.
MODELO_CRIADORA = "claude-sonnet-4-6"


def _historico_para_mensagens(mensagens: list | None) -> list[dict]:
    """Converte o histórico salvo (papel/conteúdo) no formato de mensagens do
    agente. Só as falas de texto entram; o estado real vem do rascunho."""
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
    conversa,
    mensagem_usuario: str,
    *,
    chaves: dict[str, str] | None = None,
    origem: str = "legado",
    modelo: str = MODELO_CRIADORA,
) -> dict:
    """Roda um turno da conversa. Muta `conversa.rascunho` e `conversa.mensagens`
    (sem commit) e devolve {resposta, chips, rascunho, uso}."""
    estado = EstadoCriacao(rascunho=Rascunho.model_validate(conversa.rascunho or {}))
    ferramentas = montar_ferramentas(estado)
    prompt = montar_prompt_criadora(estado.rascunho)

    with usar_chaves(chaves):
        modelo_chat = construir_modelo(modelo, temperatura=0.3)
        app = create_react_agent(modelo_chat, ferramentas, prompt=prompt)
        historico = _historico_para_mensagens(conversa.mensagens) + [
            {"role": "user", "content": mensagem_usuario}
        ]
        resultado = app.invoke({"messages": historico})

    mensagens_resultado = resultado["messages"]
    resposta_texto = texto_da_resposta(mensagens_resultado[-1])

    # Medição (MIGRACAO §3.6): soma os tokens dos turnos do modelo, com a origem
    # da chave (cliente × consultoria × legado) carimbada para a transparência.
    tokens_entrada = tokens_saida = 0
    for m in mensagens_resultado:
        if isinstance(m, AIMessage):
            u = m.usage_metadata or {}
            tokens_entrada += u.get("input_tokens", 0)
            tokens_saida += u.get("output_tokens", 0)
    uso = {
        "modelo": modelo,
        "tokens_entrada": tokens_entrada,
        "tokens_saida": tokens_saida,
        "origem": origem,
    }

    # Persiste reatribuindo (o ORM detecta a troca do JSONB; mutação in-place não).
    conversa.rascunho = estado.rascunho.model_dump(mode="json")
    conversa.mensagens = (conversa.mensagens or []) + [
        {"papel": "usuario", "conteudo": mensagem_usuario},
        {
            "papel": "ia",
            "conteudo": resposta_texto,
            "chips": estado.chips,
            "uso": uso,
        },
    ]
    return {
        "resposta": resposta_texto,
        "chips": estado.chips,
        "rascunho": conversa.rascunho,
        "uso": uso,
    }
