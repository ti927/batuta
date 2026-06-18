"""Execução de um agente sozinho (Tarefa 4.2).

Um agente recebe uma entrada, raciocina com sua documentação (os quatro
markdowns) e seus instrumentos (o cinto), e produz uma saída. O laço de
tool-calling é o `create_react_agent` do LangGraph; cada instrumento do cinto
vira uma ferramenta da IA pelo encaixe (instrumentos/base.py).
"""

import json
import re
import unicodedata
from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from pydantic import Field, create_model

import instrumentos as encaixe
from instrumentos.base import (
    FalhaInstrumento,
    acao_irreversivel,
    acionar_com_retentativa,
)
from modelos import Agente, Instrumento
from orquestracao.llm import MODELO_PADRAO, construir_modelo, texto_da_resposta


def montar_instrucoes(agente: Agente) -> str:
    """Compõe o prompt de sistema a partir dos quatro markdowns do agente."""
    secoes = [
        ("Quem você é", agente.agent_md),
        ("Suas habilidades", agente.skill_md),
        ("Seus instrumentos", agente.tools_md),
        ("Sua personalidade e tom", agente.soul_md),
    ]
    partes = [
        f"## {titulo}\n{conteudo.strip()}"
        for titulo, conteudo in secoes
        if conteudo and conteudo.strip()
    ]
    if not partes:
        return "Você é um agente do Batuta. Cumpra a tarefa recebida com clareza."
    return "\n\n".join(partes)


def _nome_de_ferramenta(inst: Instrumento, tipo_fallback: str) -> str:
    """Nome válido para a IA (^[a-zA-Z0-9_-]{1,64}$), único por instrumento."""
    base = unicodedata.normalize("NFKD", inst.nome).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-zA-Z0-9_-]+", "_", base).strip("_")[:40]
    return f"{base or tipo_fallback}_{inst.id.hex[:8]}"


def _ferramenta_unica(
    inst, tipo, config, falhas: list[str], mensagens_enviadas: dict[str, list[str]]
) -> StructuredTool:
    """A ferramenta única derivada do `executar` de um instrumento (o caso comum).

    Em falha definitiva (esgotadas as retentativas, ou falha não retentável), o
    erro SEMPRE volta para a IA. A diferença é o que acontece com a EXECUÇÃO:

    - Instrumento de AÇÃO IRREVERSÍVEL (publicar/enviar/gravar): a falha é
      registrada em `falhas` e a orquestração, ao fim do laço, transforma isso
      numa falha VISÍVEL — nunca fingir que a ação aconteceu (PRODUTO §16).
    - Instrumento de LEITURA (busca, consulta, gerar artefato): a falha NÃO
      derruba o fluxo — o agente recebe o erro e decide pela sua documentação
      (tentar de novo, ajustar a entrada, ou seguir sem o dado). Assim uma busca
      instável não joga fora todo o trabalho dos passos anteriores.

    Quando o instrumento APRESENTA uma mensagem a um humano (`tipo.campo_mensagem`,
    ex.: um canal de mensageria), o texto enviado COM SUCESSO é acumulado em
    `mensagens_enviadas` (por id de instrumento). É o que o portão de aprovação usa
    para carregar adiante exatamente o que a pessoa viu (e não o status que o agente
    narra depois)."""

    # Derivado por instância (REST pelo método, SQL pelo somente_leitura). É o
    # mesmo critério da parede de ativação — uma fonte de verdade só.
    irreversivel = acao_irreversivel(tipo.tipo, inst.configuracao or {})
    campo_msg = getattr(tipo, "campo_mensagem", None)

    def executar(**kwargs) -> str:
        args = tipo.Args.model_validate(kwargs)
        try:
            resultado = acionar_com_retentativa(tipo, config, args)
        except FalhaInstrumento as e:
            msg = f"O instrumento '{inst.nome}' falhou: {e}"
            if irreversivel:
                falhas.append(msg)
                return json.dumps({"ok": False, "erro": msg}, ensure_ascii=False)
            return json.dumps(
                {
                    "ok": False,
                    "erro": msg,
                    "dica": "Falha numa ação de leitura — tente de novo com outra "
                    "entrada ou siga sem este resultado; não invente o dado.",
                },
                ensure_ascii=False,
            )
        # Envio bem-sucedido por um canal: registra o texto apresentado ao humano.
        if campo_msg:
            texto = getattr(args, campo_msg, None)
            if texto:
                mensagens_enviadas.setdefault(str(inst.id), []).append(str(texto))
        return json.dumps(resultado, ensure_ascii=False, default=str)

    return StructuredTool.from_function(
        func=executar,
        name=_nome_de_ferramenta(inst, tipo.tipo),
        description=f"{tipo.descricao} (instrumento configurado: {inst.nome})",
        args_schema=tipo.Args,
    )


def _ferramentas_de_instrumento(
    inst: Instrumento, falhas: list[str], mensagens_enviadas: dict[str, list[str]]
) -> list:
    """As ferramentas que um instrumento do cinto oferece à IA pelo encaixe.

    O caso comum é UMA ferramenta (derivada do `executar`). Um instrumento
    MULTI-FERRAMENTA (MCP) devolve VÁRIAS, via `expandir_ferramentas`. Tipo
    desconhecido → nenhuma (instrumento ignorado)."""
    tipo = encaixe.obter_tipo(inst.tipo)
    if tipo is None:
        return []
    # Fase 7-B: mescla os segredos decifrados (anexados ao carregar o cinto) na
    # config; ficam só em memória, nunca no banco em claro.
    config = tipo.Config.model_validate(
        {**(inst.configuracao or {}), **getattr(inst, "segredos_decifrados", {})}
    )
    expandidas = tipo.expandir_ferramentas(config)
    if expandidas is not None:
        return expandidas
    return [_ferramenta_unica(inst, tipo, config, falhas, mensagens_enviadas)]


def _opcoes_das_saidas(saidas: list[dict]) -> str:
    """As saídas do nó como uma lista legível 'rótulo: quando' (para a IA escolher)."""
    return "\n".join(
        f'- "{s["rotulo"]}": {s.get("quando") or "(sem descrição)"}'
        for s in saidas
        if s.get("rotulo")
    )


def _ferramenta_seguir_para(saidas: list[dict], escolha: dict) -> StructuredTool:
    """Ferramenta de DECISÃO DE FLUXO: o PRÓPRIO agente declara por qual saída do nó
    o fluxo segue — em vez de uma LLM roteadora separada adivinhar pela prosa. O
    `rotulo` é um enum dos rótulos das saídas (a IA não inventa caminho); a escolha
    é registrada no dict `escolha` do closure (mesmo padrão de `mensagens_enviadas`)."""
    rotulos = [s["rotulo"] for s in saidas if s.get("rotulo")]
    Args = create_model(
        "SeguirParaArgs",
        rotulo=(
            Literal[tuple(rotulos)],  # type: ignore[valid-type]
            Field(description="O rótulo exato do caminho a seguir."),
        ),
    )
    descricao = (
        "Decide por qual caminho o fluxo segue depois deste passo. Chame UMA vez, ao "
        f"concluir, com o rótulo do caminho escolhido.\nCaminhos:\n{_opcoes_das_saidas(saidas)}"
    )

    def seguir(**kwargs) -> str:
        args = Args.model_validate(kwargs)
        escolha["rotulo"] = args.rotulo
        return json.dumps({"ok": True, "rotulo": args.rotulo}, ensure_ascii=False)

    return StructuredTool.from_function(
        func=seguir, name="seguir_para", description=descricao, args_schema=Args
    )


def _instrucao_de_fluxo(saidas: list[dict], gate: bool) -> str:
    """Apêndice mecânico (não comportamental) que diz ao agente quais saídas o nó
    tem e como declarar a escolha. É a topologia que antes ficava ESCONDIDA dele."""
    opcoes = _opcoes_das_saidas(saidas)
    if gate:
        return (
            "## Caminhos do fluxo (este passo aguarda uma pessoa)\n"
            "Quando você tiver a decisão da pessoa, chame a ferramenta `seguir_para` "
            "com o rótulo do caminho escolhido. Se ainda precisar de algo dela "
            "(perguntar, esclarecer), apenas responda normalmente, SEM chamar "
            "`seguir_para` — o fluxo segue aguardando a resposta dela.\n"
            f"Caminhos:\n{opcoes}"
        )
    return (
        "## Caminhos do fluxo\n"
        "Ao terminar este passo, escolha por qual caminho o fluxo segue: chame a "
        "ferramenta `seguir_para` com o rótulo do caminho.\n"
        f"Caminhos:\n{opcoes}"
    )


def executar_agente(
    agente: Agente,
    cinto: list[Instrumento],
    entrada: str,
    *,
    saidas: list[dict] | None = None,
    gate: bool = False,
) -> dict:
    """Roda um agente sozinho sobre uma entrada. Devolve a saída em texto e a
    lista de instrumentos que ele acionou (para inspeção).

    Quando o nó tem 2+ saídas, o agente recebe a ferramenta `seguir_para` e o
    apêndice de caminhos: é ELE quem declara o ramo (devolvido em `ramo_escolhido`),
    em vez de uma LLM roteadora adivinhar pela prosa. Nó de 1 saída segue direto.

    Se um instrumento de AÇÃO IRREVERSÍVEL falhar de vez, levanta
    `FalhaInstrumento` ao fim do laço — a execução fica num estado de falha claro
    e visível (Tarefa 5.1). Falha de instrumento de LEITURA não derruba o fluxo:
    volta para o agente decidir (ver `_ferramenta_unica`)."""
    modelo = construir_modelo(agente.modelo_ia)
    falhas: list[str] = []
    # Por instrumento (id → textos): o que o agente APRESENTOU a um humano por canal
    # neste turno. O portão de aprovação usa isto para carregar adiante o que a
    # pessoa viu, em vez do status que o agente narra depois.
    mensagens_enviadas: dict[str, list[str]] = {}
    escolha: dict[str, str] = {}  # o ramo que o agente declarar via `seguir_para`
    ferramentas = [
        f
        for i in cinto
        for f in _ferramentas_de_instrumento(i, falhas, mensagens_enviadas)
    ]
    saidas = saidas or []
    instrucoes = montar_instrucoes(agente)
    if len(saidas) >= 2:
        ferramentas.append(_ferramenta_seguir_para(saidas, escolha))
        instrucoes += "\n\n" + _instrucao_de_fluxo(saidas, gate)
    app = create_react_agent(modelo, ferramentas, prompt=instrucoes)
    resultado = app.invoke({"messages": [{"role": "user", "content": entrada}]})

    # Não confiamos na narração do agente: se uma ação IRREVERSÍVEL falhou,
    # a execução falha de forma determinística e visível (nunca em silêncio).
    if falhas:
        raise FalhaInstrumento(falhas[0])

    mensagens = resultado["messages"]
    acionados = [
        chamada.get("name")
        for m in mensagens
        for chamada in (getattr(m, "tool_calls", None) or [])
    ]

    # Uso (Tarefa 5.4): soma os tokens de cada turno do modelo. Num laço de
    # tool-calling há vários AIMessage; cada turno reenvia o contexto, então a
    # soma reflete o que foi de fato consumido.
    tokens_entrada = tokens_saida = 0
    for m in mensagens:
        if isinstance(m, AIMessage):
            u = m.usage_metadata or {}
            tokens_entrada += u.get("input_tokens", 0)
            tokens_saida += u.get("output_tokens", 0)
    modelo_usado = agente.modelo_ia or MODELO_PADRAO

    return {
        "saida": texto_da_resposta(mensagens[-1]),
        "instrumentos_acionados": acionados,
        "mensagens_enviadas": mensagens_enviadas,
        "ramo_escolhido": escolha.get("rotulo"),
        "uso": [
            {
                "modelo": modelo_usado,
                "tokens_entrada": tokens_entrada,
                "tokens_saida": tokens_saida,
            }
        ],
    }
