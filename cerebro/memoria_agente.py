"""Memória do AGENTE — o agente aprende com o próprio trabalho (funções puras).

Molde da memória da IA criadora (`criacao/memoria.py`), mas para o AGENTE em runtime:
FICHA POR ASSUNTO com UPSERT (uma ficha por assunto — edita, não empilha), destilada
(sem embeddings; recuperação por recência/filtro simples). Diferente da `MemoriaProjeto`
(memória da criadora sobre o time, para o consultor).

Estas funções PURAS não decidem transação: a ferramenta injetada (`orquestracao/agente.py`)
abre a PRÓPRIA sessão e COMITA (o aprendizado persiste mesmo se o run falhar depois); as
rotas comitam por requisição. O `registrar` faz upsert ATÔMICO (`ON CONFLICT`) — seguro
sob concorrência de duas execuções do mesmo agente gravando o mesmo assunto.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from modelos import MemoriaAgente

# Freios contra inchar a memória (o principal é o upsert por assunto):
MAX_ASSUNTO = 200  # tamanho do título da ficha
MAX_CONTEUDO = 4000  # a ficha é um resumo enxuto, não um documento
TETO_FICHAS = 200  # máx. de fichas (assuntos distintos) por agente
LIMITE_CONTEXTO = 40  # fichas injetadas no prompt no modo "sempre" (resto vira índice)
MAX_ESCRITAS_POR_RUN = 20  # anti-loop: máx. de gravações numa única execução


def serializar(m: MemoriaAgente) -> dict:
    """Uma ficha no formato que vai para a IA (prompt/ferramenta) e para o painel."""
    return {
        "id": str(m.id),
        "assunto": m.assunto,
        "conteudo": m.conteudo,
        "atualizado_em": m.atualizado_em.isoformat() if m.atualizado_em else None,
    }


def registrar(
    sessao: Session, agente_id: uuid.UUID, assunto: str, conteudo: str
) -> tuple[MemoriaAgente | None, str]:
    """UPSERT de uma ficha (uma por assunto). Devolve `(memoria, status)` com status em
    {'criada','atualizada','recusada:vazio','recusada:teto'}. Não comita (quem chama
    controla). O write é ATÔMICO (`ON CONFLICT DO UPDATE`) → seguro sob concorrência."""
    assunto = (assunto or "").strip()[:MAX_ASSUNTO]
    conteudo = (conteudo or "").strip()[:MAX_CONTEUDO]
    if not assunto or not conteudo:
        return None, "recusada:vazio"
    ja_existe = sessao.scalar(
        select(MemoriaAgente.id).where(
            MemoriaAgente.agente_id == agente_id, MemoriaAgente.assunto == assunto
        )
    )
    if ja_existe is None:
        # Teto só barra ASSUNTO NOVO (editar ficha existente sempre pode). Pré-checagem
        # best-effort: uma corrida rara pode passar por 1 — aceitável (teto é suave).
        total = sessao.scalar(
            select(func.count())
            .select_from(MemoriaAgente)
            .where(MemoriaAgente.agente_id == agente_id)
        )
        if total is not None and total >= TETO_FICHAS:
            return None, "recusada:teto"
    stmt = (
        pg_insert(MemoriaAgente)
        .values(agente_id=agente_id, assunto=assunto, conteudo=conteudo)
        .on_conflict_do_update(
            index_elements=["agente_id", "assunto"],
            set_={"conteudo": conteudo, "atualizado_em": func.now()},
        )
    )
    sessao.execute(stmt)
    sessao.flush()
    # populate_existing: o upsert é um statement Core (não passa pelo ORM), então um
    # objeto já no identity map ficaria com o `conteudo` antigo; força reler do banco.
    m = sessao.execute(
        select(MemoriaAgente)
        .where(
            MemoriaAgente.agente_id == agente_id, MemoriaAgente.assunto == assunto
        )
        .execution_options(populate_existing=True)
    ).scalar_one()
    return m, ("atualizada" if ja_existe is not None else "criada")


def listar(
    sessao: Session,
    agente_id: uuid.UUID,
    *,
    busca: str | None = None,
    limite: int | None = None,
) -> list[MemoriaAgente]:
    """As fichas do agente, da mais recente para a mais antiga. `busca` filtra por
    substring (case-insensitive) em assunto+conteúdo; `limite` corta o número."""
    fichas = list(
        sessao.scalars(
            select(MemoriaAgente)
            .where(MemoriaAgente.agente_id == agente_id)
            .order_by(MemoriaAgente.atualizado_em.desc())
        ).all()
    )
    if busca:
        termo = busca.lower()
        fichas = [
            m
            for m in fichas
            if termo in m.assunto.lower() or termo in m.conteudo.lower()
        ]
    if limite is not None:
        fichas = fichas[:limite]
    return fichas


def pesquisar(
    sessao: Session, agente_id: uuid.UUID, termo: str | None = None
) -> list[dict]:
    """Para a ferramenta `pesquisar_memoria`: fichas casadas (ou todas, se `termo`
    vazio), já serializadas. NUNCA levanta — sem match devolve lista vazia."""
    return [serializar(m) for m in listar(sessao, agente_id, busca=termo)]


def para_o_prompt(sessao: Session, agente_id: uuid.UUID) -> dict:
    """Para o modo 'sempre': as fichas (até LIMITE_CONTEXTO) + o ÍNDICE (só os assuntos)
    do excedente. Assim o prompt fica barato mesmo com muita memória — o resto o agente
    puxa com `pesquisar_memoria`."""
    todas = listar(sessao, agente_id)
    fichas = [serializar(m) for m in todas[:LIMITE_CONTEXTO]]
    indice_extra = [m.assunto for m in todas[LIMITE_CONTEXTO:]]
    return {"fichas": fichas, "indice_extra": indice_extra}


def contar(sessao: Session, agente_id: uuid.UUID) -> int:
    """Quantas fichas o agente tem (para o retrato do time da IA criadora)."""
    return sessao.scalar(
        select(func.count())
        .select_from(MemoriaAgente)
        .where(MemoriaAgente.agente_id == agente_id)
    ) or 0


# ───────────────────────── CRUD para a tela (humano) ─────────────────────────


def obter(sessao: Session, memoria_id: uuid.UUID) -> MemoriaAgente | None:
    return sessao.get(MemoriaAgente, memoria_id)


def editar(
    sessao: Session,
    memoria: MemoriaAgente,
    *,
    assunto: str | None = None,
    conteudo: str | None = None,
) -> tuple[bool, str]:
    """Edita uma ficha pela tela. Devolve (ok, motivo). Renomear para um assunto que já
    existe em OUTRA ficha do mesmo agente é recusado (a unicidade é por assunto)."""
    if assunto is not None:
        assunto = assunto.strip()[:MAX_ASSUNTO]
        if not assunto:
            return False, "assunto vazio"
        colisao = sessao.scalar(
            select(MemoriaAgente.id).where(
                MemoriaAgente.agente_id == memoria.agente_id,
                MemoriaAgente.assunto == assunto,
                MemoriaAgente.id != memoria.id,
            )
        )
        if colisao is not None:
            return False, "já existe uma ficha com esse assunto"
        memoria.assunto = assunto
    if conteudo is not None:
        conteudo = conteudo.strip()[:MAX_CONTEUDO]
        if not conteudo:
            return False, "conteúdo vazio"
        memoria.conteudo = conteudo
    sessao.flush()  # atualizado_em vem do onupdate do IdData
    return True, "ok"


def apagar(sessao: Session, memoria: MemoriaAgente) -> None:
    sessao.delete(memoria)
    sessao.flush()
