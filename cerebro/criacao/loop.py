"""O laço de conversa da IA criadora — conversa eterna sobre o time real.

Um turno: a mensagem do consultor entra, a IA raciocina e usa as ferramentas (que
agora escrevem no TIME REAL, via `criacao.servicos`), e devolvemos a resposta + os
chips + a fotografia do time. Reusa o `create_react_agent` do LangGraph (mesmo motor
de tool-use do `orquestracao.agente`).

A persistência é direta e inspecionável: o histórico vive em
`conversas_criacao.mensagens` (JSONB) e o ESTADO real é o próprio time (tabelas).
`responder_turno` muta a conversa e as linhas do time na sessão recebida, mas NÃO faz
commit — quem chama (a rota) controla a transação do turno.

PEGADINHA ESTRUTURAL (corrigida): se o histórico reenviado ao modelo a cada turno for
só TEXTO (sem as chamadas de ferramenta dos turnos passados), numa conversa longa o
modelo passa a imitar o padrão "responder com prosa" e PARA de chamar as ferramentas —
ele diz que editou, mas não chama editar_agente. Por isso guardamos, em cada turno da
IA, a sequência REAL de mensagens (AIMessage com tool_calls + ToolMessage) no campo
`lc`, e a reproduzimos no próximo turno. Assim o modelo vê que, nesta conversa, agir =
chamar ferramenta. (Os resultados de ferramenta são truncados ao guardar para não
inflar o histórico — o estado atual de verdade já é injetado no prompt do sistema.)
"""

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
    messages_from_dict,
    messages_to_dict,
)
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from criacao import memoria
from criacao.ferramentas import (
    ContextoCriacao,
    montar_ferramentas,
    snapshot_time,
)
from criacao.prompt import montar_prompt_criadora
from orquestracao.llm import construir_modelo, texto_da_resposta, usar_chaves

# Modelo padrão da IA de conversa: Sonnet 5 — forte e econômico (perto do Opus por
# bem menos custo), bom para a consultora sênior que projeta o time e escreve a
# documentação de cada agente. Quem quiser o raciocínio mais exigente troca para o
# Opus na tela (por organização). É Anthropic, então cai na ANTHROPIC_API_KEY do
# .env quando não há chave no cofre.
MODELO_CRIADORA = "claude-sonnet-5"

# Teto do conteúdo de um resultado de ferramenta guardado no histórico. O modelo só
# precisa VER que chamou a ferramenta e que veio um retorno — não do retorno inteiro
# (o estado real vem fresco no prompt). Truncar evita inflar o JSONB e os tokens.
_MAX_RESULTADO_FERRAMENTA = 500


def _compactar_para_guardar(mensagens: list) -> list:
    """Trunca o conteúdo dos ToolMessage antes de serializar para o histórico, sem
    perder a marca de que a ferramenta foi chamada (preserva tool_calls e ids)."""
    compactas = []
    for m in mensagens:
        if (
            isinstance(m, ToolMessage)
            and isinstance(m.content, str)
            and len(m.content) > _MAX_RESULTADO_FERRAMENTA
        ):
            m = m.model_copy(
                update={"content": m.content[:_MAX_RESULTADO_FERRAMENTA] + "…(truncado)"}
            )
        compactas.append(m)
    return compactas


def _historico_para_mensagens(mensagens: list | None) -> list:
    """Reconstrói o histórico de mensagens para o modelo. Para cada turno da IA, se
    houver a sequência real salva em `lc` (com as chamadas de ferramenta), reproduz
    ela inteira — é o que mantém o modelo agindo por ferramenta numa conversa longa.
    Mensagens antigas (sem `lc`) caem no texto puro."""
    saida: list = []
    for m in mensagens or []:
        papel = m.get("papel")
        if papel == "usuario":
            saida.append(HumanMessage(content=m.get("conteudo", "")))
        elif papel == "ia":
            lc = m.get("lc")
            if lc:
                saida.extend(messages_from_dict(lc))
            else:
                saida.append(AIMessage(content=m.get("conteudo", "")))
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
    prompt = montar_prompt_criadora(
        snapshot_time(sessao, conversa), memoria.para_o_prompt(sessao, conversa)
    )

    historico = _historico_para_mensagens(conversa.mensagens) + [
        HumanMessage(content=mensagem_usuario)
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
        "categoria": "conversa",
    }

    conversa.mensagens = (conversa.mensagens or []) + [
        {"papel": "usuario", "conteudo": mensagem_usuario},
        {
            "papel": "ia",
            "conteudo": resposta_texto,
            "chips": ctx.chips,
            "uso": uso,
            # A sequência REAL deste turno (com as chamadas de ferramenta), para o
            # próximo turno reproduzir o padrão de AGIR por ferramenta. Ver a nota no
            # topo do módulo. O front ignora `lc`; lê só papel/conteudo/chips.
            "lc": messages_to_dict(_compactar_para_guardar(novas)),
        },
    ]
    return {
        "resposta": resposta_texto,
        "chips": ctx.chips,
        "time_id": str(conversa.time_id) if conversa.time_id else None,
        "time": snapshot_time(sessao, conversa),
        # Recalculada DEPOIS do turno: a IA pode ter acabado de lembrar/esquecer algo.
        "memoria": memoria.para_o_prompt(sessao, conversa),
        "uso": uso,
    }
