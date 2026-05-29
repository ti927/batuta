"""Execução de um agente sozinho (Tarefa 4.2).

Um agente recebe uma entrada, raciocina com sua documentação (os quatro
markdowns) e seus instrumentos (o cinto), e produz uma saída. O laço de
tool-calling é o `create_react_agent` do LangGraph; cada instrumento do cinto
vira uma ferramenta da IA pelo encaixe (instrumentos/base.py).
"""

import json
import re
import unicodedata

from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

import instrumentos as encaixe
from modelos import Agente, Instrumento
from orquestracao.llm import construir_modelo, texto_da_resposta


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


def _ferramenta_de_instrumento(inst: Instrumento) -> StructuredTool | None:
    """Transforma um instrumento do cinto numa ferramenta da IA pelo encaixe.
    Devolve None se o tipo for desconhecido (instrumento ignorado)."""
    tipo = encaixe.obter_tipo(inst.tipo)
    if tipo is None:
        return None
    config = tipo.Config.model_validate(inst.configuracao or {})

    def executar(**kwargs) -> str:
        args = tipo.Args.model_validate(kwargs)
        resultado = tipo.executar(config, args)
        return json.dumps(resultado, ensure_ascii=False, default=str)

    return StructuredTool.from_function(
        func=executar,
        name=_nome_de_ferramenta(inst, tipo.tipo),
        description=f"{tipo.descricao} (instrumento configurado: {inst.nome})",
        args_schema=tipo.Args,
    )


def executar_agente(
    agente: Agente, cinto: list[Instrumento], entrada: str
) -> dict:
    """Roda um agente sozinho sobre uma entrada. Devolve a saída em texto e a
    lista de instrumentos que ele acionou (para inspeção)."""
    modelo = construir_modelo(agente.modelo_ia)
    ferramentas = [
        f for f in (_ferramenta_de_instrumento(i) for i in cinto) if f is not None
    ]
    app = create_react_agent(modelo, ferramentas, prompt=montar_instrucoes(agente))
    resultado = app.invoke({"messages": [{"role": "user", "content": entrada}]})

    mensagens = resultado["messages"]
    acionados = [
        chamada.get("name")
        for m in mensagens
        for chamada in (getattr(m, "tool_calls", None) or [])
    ]
    return {
        "saida": texto_da_resposta(mensagens[-1]),
        "instrumentos_acionados": acionados,
    }
