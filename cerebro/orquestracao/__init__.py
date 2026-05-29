"""A orquestração de agentes do Batuta (sobre LangGraph).

Mantida isolada do resto do cérebro (CLAUDE.md §9) para poder ser testada
sozinha. Cresce tarefa a tarefa na Fase 4: começa por chamar uma LLM, depois um
agente sozinho, depois a cadeia encadeada com o LangGraph.
"""
