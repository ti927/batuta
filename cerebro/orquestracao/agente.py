"""Execução de um agente sozinho (Tarefa 4.2).

Um agente recebe uma entrada, raciocina com sua documentação (os quatro
markdowns) e seus instrumentos (o cinto), e produz uma saída. O laço de
tool-calling é o `create_react_agent` do LangGraph; cada instrumento do cinto
vira uma ferramenta da IA pelo encaixe (instrumentos/base.py).
"""

import json
import re
import unicodedata

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

import instrumentos as encaixe
from instrumentos.base import FalhaInstrumento, acionar_com_retentativa
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


def _ferramenta_unica(inst, tipo, config, falhas: list[str]) -> StructuredTool:
    """A ferramenta única derivada do `executar` de um instrumento (o caso comum).

    Em falha definitiva do instrumento (esgotadas as retentativas, ou falha não
    retentável), registra em `falhas` e informa o erro à IA. A orquestração, ao
    fim do laço, transforma isso numa falha visível — sem depender da narração
    do agente (PRODUTO §16: "nunca morre em silêncio")."""

    def executar(**kwargs) -> str:
        args = tipo.Args.model_validate(kwargs)
        try:
            resultado = acionar_com_retentativa(tipo, config, args)
        except FalhaInstrumento as e:
            msg = f"O instrumento '{inst.nome}' falhou: {e}"
            falhas.append(msg)
            return json.dumps({"ok": False, "erro": msg}, ensure_ascii=False)
        return json.dumps(resultado, ensure_ascii=False, default=str)

    return StructuredTool.from_function(
        func=executar,
        name=_nome_de_ferramenta(inst, tipo.tipo),
        description=f"{tipo.descricao} (instrumento configurado: {inst.nome})",
        args_schema=tipo.Args,
    )


def _ferramentas_de_instrumento(inst: Instrumento, falhas: list[str]) -> list:
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
    return [_ferramenta_unica(inst, tipo, config, falhas)]


def executar_agente(
    agente: Agente, cinto: list[Instrumento], entrada: str
) -> dict:
    """Roda um agente sozinho sobre uma entrada. Devolve a saída em texto e a
    lista de instrumentos que ele acionou (para inspeção).

    Se um instrumento falhar de vez, levanta `FalhaInstrumento` ao fim do laço —
    a execução então fica num estado de falha claro e visível (Tarefa 5.1)."""
    modelo = construir_modelo(agente.modelo_ia)
    falhas: list[str] = []
    ferramentas = [f for i in cinto for f in _ferramentas_de_instrumento(i, falhas)]
    app = create_react_agent(modelo, ferramentas, prompt=montar_instrucoes(agente))
    resultado = app.invoke({"messages": [{"role": "user", "content": entrada}]})

    # Não confiamos na narração do agente: se um instrumento falhou de vez,
    # a execução falha de forma determinística e visível.
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
        "uso": [
            {
                "modelo": modelo_usado,
                "tokens_entrada": tokens_entrada,
                "tokens_saida": tokens_saida,
            }
        ],
    }
