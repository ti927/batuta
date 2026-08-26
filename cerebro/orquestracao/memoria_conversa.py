"""Memória durável entre turnos da CONVERSA (Fatia 4.3 / P2a) — a cura do "renasce".

Um `PostgresSaver` do LangGraph, com pool de conexões, guarda o fio do agente
(mensagens + resultados de ferramenta) por conversa (`thread_id` = `conversa.id`). O
agente **retoma do estado salvo** em vez de reconstruir do texto → fim da re-busca.

Escopo: SÓ a conversa em modo chat usa isto. A orquestração clássica (tarefa one-shot)
e o PORTÃO **não** usam (o portão é a P3). O `executar_agente` só ativa a memória
quando recebe `checkpointer` + `thread_id`.

À prova de falha (lei §12-A): se o checkpointer não subir (banco/pooler), `obter()`
devolve `None` e a conversa cai no comportamento LEGADO (reconstrói do texto) — o
atendimento nunca quebra por causa da memória. `preparar()` é chamado no boot
(`main.ciclo_de_vida`); em teste (sem lifespan) `obter()` devolve `None` → modo legado.
"""

import logging

from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool

from db import _montar_url
from observabilidade.escritor import registrar_evento

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
_saver = None
_indisponivel = False


def _conninfo() -> str:
    """Conninfo libpq a partir da MESMA fonte do app (`db._montar_url`), montada por
    componentes para não quebrar com caracteres especiais na senha ($ * ,). O
    `sslmode` também vem de lá (`require` na nuvem; um `?sslmode=` na URL manda,
    como no banco local de testes)."""
    u, sslmode = _montar_url()
    return make_conninfo(
        host=u.host, port=u.port, user=u.username,
        password=u.password, dbname=u.database, sslmode=sslmode,
    )


def preparar() -> None:
    """Boot: abre o pool e garante as tabelas de checkpoint (`setup()`, idempotente).
    À prova de falha — em erro, marca indisponível e a conversa segue no modo legado."""
    global _pool, _saver, _indisponivel
    if _saver is not None:
        return
    try:
        # Import tardio: só quem tem o pacote (P0) e vai usar memória paga o custo.
        from langgraph.checkpoint.postgres import PostgresSaver

        _pool = ConnectionPool(
            _conninfo(), min_size=1, max_size=4, open=True, timeout=10,
            # autocommit + prepare_threshold=0: exigência do PostgresSaver e
            # compatível com o pooler do Supabase (sem prepared statements presas).
            # connect_timeout: nunca deixa o boot travar se o banco demorar.
            kwargs={"autocommit": True, "prepare_threshold": 0, "connect_timeout": 10},
        )
        saver = PostgresSaver(_pool)
        saver.setup()
        _saver = saver
        _indisponivel = False
        logger.info("memoria_conversa: checkpointer PostgresSaver pronto.")
    except Exception as e:
        _indisponivel = True
        _saver = None
        if _pool is not None:
            try:
                _pool.close()
            except Exception:
                pass
            _pool = None
        logger.warning(
            "memoria_conversa: checkpointer INDISPONÍVEL — a conversa usa o modo legado "
            "(reconstrói do texto). Não afeta o atendimento.", exc_info=True,
        )
        # Modo degradado NUNCA é silencioso: além do log técnico, o evento fica no
        # banco de observabilidade (GET /logs) — sem isto, a queda de 2026-08-22
        # passou 3 dias invisível (só descoberta por inspeção externa).
        registrar_evento(
            categoria="sistema",
            acao="memoria.checkpointer_indisponivel",
            nivel="error",
            resultado="falha",
            erro=e,
            persistir=True,
            detalhe={
                "efeito": "conversas seguem no modo legado (sem memória entre "
                "turnos e sem a trava nativa de aprovação) até o próximo deploy/restart",
            },
        )


def obter():
    """O checkpointer, ou `None` se não preparado/indisponível (fallback legado).
    NÃO sobe sozinho: em teste (sem lifespan) devolve `None` → modo legado."""
    return _saver


def tem_estado(thread_id: str) -> bool:
    """Se a conversa já tem fio salvo (para decidir SEMEAR o histórico no 1º turno)."""
    s = obter()
    if s is None:
        return False
    try:
        return s.get_tuple({"configurable": {"thread_id": thread_id}}) is not None
    except Exception:
        return False


def ha_interrupcao(thread_id: str) -> bool:
    """Se a conversa está PAUSADA num portão NATIVO (Fatia 4.3 / P3): o checkpoint tem um
    write pendente no canal `__interrupt__` (o HITL interrompeu antes de uma ação
    irreversível). É o que distingue, no próximo turno, uma RESPOSTA de aprovação
    (`retomar` com Command resume) de uma mensagem nova (turno normal). Lê o checkpointer
    cru (`pending_writes` = tuplas `(task_id, canal, valor)`), sem montar o agente. À prova
    de falha: qualquer erro → False (trata como turno normal — nunca trava o atendimento)."""
    s = obter()
    if s is None:
        return False
    try:
        tup = s.get_tuple({"configurable": {"thread_id": thread_id}})
        writes = getattr(tup, "pending_writes", None) or []
        return any(len(w) >= 2 and w[1] == "__interrupt__" for w in writes)
    except Exception:
        return False


def desligar() -> None:
    """Shutdown do app: fecha o pool."""
    global _pool, _saver, _indisponivel
    if _pool is not None:
        try:
            _pool.close()
        except Exception:
            pass
    _pool = None
    _saver = None
    _indisponivel = False
