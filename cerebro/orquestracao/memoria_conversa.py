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

# Validador de conexão do próprio psycopg, resolvido uma vez: o pool o chama antes de
# emprestar uma conexão e descarta a que não responde (ver `preparar`).
_CHECAR_CONEXAO = ConnectionPool.check_connection

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
        connect_timeout=10,
        # TCP keepalive: sem isto, uma conexão que o pooler do Supabase matou do lado
        # dele parece viva aqui, e a próxima consulta espera uma resposta que nunca vem
        # — sem erro, sem fim. O keepalive detecta o socket morto em ~1 min.
        keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
        # E o irmão do keepalive para o caso OPOSTO (dados enviados sem confirmação):
        # corta em 30 s a conexão cujo envio ninguém confirma — foi o modo de falha do
        # congelamento de 2026-08-27 (bytes retransmitidos 15 min para um buraco negro).
        # Sem efeito no Windows local; ativo no Linux (Railway).
        tcp_user_timeout=30000,
        # Cinto de segurança final: NENHUMA operação do checkpointer pode pendurar o
        # turno para sempre. As consultas dele são de milissegundos; 20 s é folga
        # enorme e ainda assim finito. Falhar rápido cai no modo legado (a conversa
        # atende sem memória) — infinitamente melhor que o atendimento travar.
        options="-c statement_timeout=20000",
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
            # `check` é a correção do travamento de 2026-08-26: SEM ele (o padrão do
            # psycopg é não checar), o pool entrega a conexão que estava guardada há
            # horas — e se o pooler do Supabase a matou nesse meio-tempo, a consulta
            # fica esperando resposta para sempre. Foi o que prendeu um atendimento
            # inteiro em "bot respondendo": o turno travou ANTES do agente rodar, na
            # primeira leitura do checkpointer (zero checkpoints gravados). Com o
            # check, o pool testa a conexão ao emprestar e descarta a morta.
            check=_CHECAR_CONEXAO,
            # E não guarda conexão ociosa por muito tempo: recicla antes de ela virar
            # candidata a ser morta do outro lado.
            max_idle=120.0,
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


def esta_saudavel() -> bool:
    """Se a memória entre turnos está de pé. `False` = modo degradado: a conversa
    ainda atende, mas cada turno recomeça do texto e a trava nativa de ação
    irreversível fica inativa. Lido pelo `/saude` para o selo da barra lateral
    avisar — foi a queda que passou três dias invisível em agosto/2026."""
    return _saver is not None


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


def sondar() -> None:
    """Sonda do vigia dos elos: um SELECT 1 pelo pool do checkpointer, com o
    timeout do próprio pool. Levanta em falha (pool fora, conexão morta)."""
    if _pool is None:
        raise RuntimeError("pool do checkpointer não está de pé")
    with _pool.connection() as conn:
        conn.execute("select 1")


def reconectar() -> None:
    """Cura do elo: derruba o pool e o reconstrói (mesmo caminho do boot). Se a
    reconstrução falhar, `preparar` registra o evento e o modo legado assume —
    a sonda seguinte conta a verdade."""
    desligar()
    preparar()


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
