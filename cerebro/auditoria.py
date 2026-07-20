"""Auditoria nominal de ações sensíveis (Fase 6, MIGRACAO §6.4).

`registrar` apenas adiciona a linha à sessão — NÃO faz commit. Assim o registro
entra na MESMA transação da ação que o gerou: ou a ação e seu rastro entram
juntos, ou nenhum dos dois (atômico). Quem chama é responsável pelo commit, que
já acontece no fluxo normal da rota.

`recurso_id`/`organizacao_id` são UUID soltos (não FK) no modelo, de propósito:
o registro sobrevive à exclusão do recurso auditado.
"""

import uuid

from sqlalchemy.orm import Session

from modelos import Auditoria, Time, Usuario
from observabilidade.escritor import registrar_evento


def registrar(
    sessao: Session,
    *,
    usuario: Usuario | None,
    acao: str,
    recurso_tipo: str | None = None,
    recurso_id: uuid.UUID | None = None,
    organizacao_id: uuid.UUID | None = None,
    detalhe: dict | None = None,
) -> None:
    sessao.add(
        Auditoria(
            usuario_id=usuario.id if usuario else None,
            acao=acao,
            recurso_tipo=recurso_tipo,
            recurso_id=recurso_id,
            organizacao_id=organizacao_id,
            detalhe=detalhe,
        )
    )
    # Espelha no banco de logs (busca unificada). Best-effort e em transação própria — a
    # `Auditoria` acima segue sendo a fonte atômica (entra/sai com a transação da ação).
    registrar_evento(
        categoria="escrita",
        acao=acao,
        usuario_id=usuario.id if usuario else None,
        organizacao_id=organizacao_id,
        recurso_tipo=recurso_tipo,
        recurso_id=recurso_id,
        detalhe=detalhe,
    )


def org_do_time(sessao: Session, time_id: uuid.UUID) -> uuid.UUID | None:
    """Conveniência: a organização de um time, para carimbar a auditoria com a
    partição por cliente (organizacao_id)."""
    time = sessao.get(Time, time_id)
    return time.organizacao_id if time else None
