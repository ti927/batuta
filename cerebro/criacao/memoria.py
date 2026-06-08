"""Memória de longo prazo da IA sobre um projeto — abordagem DESTILADA (Fase 10).

A IA cura o que vale lembrar entre sessões: fatos do cliente, decisões tomadas com
o consultor, preferências de tom/forma. NÃO é busca vetorial (decisão do maestro
2026-06-07): um projeto acumula dezenas de memórias, não milhares — cabem no
contexto do modelo, então a recuperação é por recência/filtro de texto simples, sem
embeddings nem provedor extra.

Isolamento estrito: tudo é preso à CONVERSA (o fio eterno do projeto) e carrega a
`organizacao_id` como parede dura. Estas funções NÃO fazem commit — quem chama
controla a transação (como `criacao/servicos.py`): a rota commita por requisição; o
laço da IA commita ao fim do turno.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from modelos import ConversaCriacao, MemoriaProjeto

CATEGORIAS = ("fato", "decisao", "preferencia")

# Quantas memórias (as mais recentes) entram no prompt por turno. Teto generoso:
# um projeto real fica bem abaixo disso, mas evita o prompt crescer sem limite se a
# IA guardar demais. Acima do teto, a IA ainda pode buscar o resto com `recordar`.
LIMITE_CONTEXTO = 60


def serializar(m: MemoriaProjeto) -> dict:
    """Uma memória no formato que vai para a IA (prompt/recordar) e para o painel."""
    return {
        "id": str(m.id),
        "categoria": m.categoria,
        "conteudo": m.conteudo,
        "criado_em": m.criado_em.isoformat() if m.criado_em else None,
    }


def lembrar(
    sessao: Session, conversa: ConversaCriacao, *, categoria: str, conteudo: str
) -> MemoriaProjeto:
    """Guarda uma memória de longo prazo para o projeto desta conversa. `categoria`
    fora do conjunto vira 'fato' (a IA às vezes inventa rótulo)."""
    cat = categoria if categoria in CATEGORIAS else "fato"
    memoria = MemoriaProjeto(
        conversa_id=conversa.id,
        organizacao_id=conversa.organizacao_id,
        categoria=cat,
        conteudo=conteudo.strip(),
    )
    sessao.add(memoria)
    sessao.flush()
    return memoria


def listar(
    sessao: Session,
    conversa: ConversaCriacao,
    *,
    busca: str | None = None,
    limite: int | None = None,
) -> list[MemoriaProjeto]:
    """As memórias do projeto desta conversa, da mais recente para a mais antiga.
    `busca` filtra por substring (case-insensitive) no conteúdo; `limite` corta o
    número devolvido. O isolamento é automático: filtra por `conversa_id` (e a
    organização já é a parede de acesso a montante)."""
    memorias = sessao.scalars(
        select(MemoriaProjeto)
        .where(MemoriaProjeto.conversa_id == conversa.id)
        .order_by(MemoriaProjeto.criado_em.desc())
    ).all()
    if busca:
        termo = busca.lower()
        memorias = [m for m in memorias if termo in m.conteudo.lower()]
    if limite is not None:
        memorias = memorias[:limite]
    return list(memorias)


def esquecer(
    sessao: Session, conversa: ConversaCriacao, memoria_id: uuid.UUID
) -> bool:
    """Apaga uma memória (quando o consultor mudou de ideia ou ela ficou errada).
    Só apaga se a memória for DESTA conversa — a parede de isolamento. Devolve True
    se apagou, False se não existe ou é de outro projeto."""
    memoria = sessao.get(MemoriaProjeto, memoria_id)
    if memoria is None or memoria.conversa_id != conversa.id:
        return False
    sessao.delete(memoria)
    sessao.flush()
    return True


def para_o_prompt(sessao: Session, conversa: ConversaCriacao) -> list[dict]:
    """As memórias recentes do projeto, prontas para injetar no prompt da conversa."""
    return [serializar(m) for m in listar(sessao, conversa, limite=LIMITE_CONTEXTO)]
