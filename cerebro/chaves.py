"""Resolução da chave de IA para a execução (Fase 7.3, MIGRACAO Virada 5).

Dada uma execução, decide QUAL chave de API usar, nesta ordem de fallback:

  1. a chave da Organização (o cliente), se cadastrada e ativa;
  2. a chave-mãe da consultoria (`organizacao_id` nulo na `chaves_api`);
  3. None — o chamador então cai na ANTHROPIC_API_KEY legada do .env.

Assim, no estado atual (cofre vazio), nada quebra: a resolução devolve None e o
motor segue usando a chave do ambiente como sempre. A chave decifrada existe só
em memória, na hora de executar; nunca volta ao banco nem à interface (PRODUTO
§26). Nesta fase só a IA 'executora' é consumida pelo motor (MIGRACAO Virada 4).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from cofre import decifrar
from modelos import ChaveApi, Time


def _buscar(
    sessao: Session,
    organizacao_id: uuid.UUID | None,
    tipo_ia: str,
    provedor: str,
    *,
    mae: bool,
) -> str | None:
    """Busca uma chave ativa e a decifra. `mae=True` busca a chave da consultoria
    (organizacao_id nulo); `mae=False`, a chave da organização dada."""
    condicao_org = (
        ChaveApi.organizacao_id.is_(None)
        if mae
        else ChaveApi.organizacao_id == organizacao_id
    )
    chave = sessao.scalars(
        select(ChaveApi).where(
            condicao_org,
            ChaveApi.tipo_ia == tipo_ia,
            ChaveApi.provedor == provedor,
            ChaveApi.ativa.is_(True),
        )
    ).first()
    return decifrar(chave.valor_cifrado) if chave else None


def resolver_chave(
    sessao: Session,
    organizacao_id: uuid.UUID | None,
    *,
    tipo_ia: str = "executora",
    provedor: str = "anthropic",
) -> str | None:
    """Resolve a chave de IA pela ordem de fallback. Devolve a chave decifrada
    ou None (quando nem a organização nem a consultoria têm chave cadastrada)."""
    if organizacao_id is not None:
        propria = _buscar(sessao, organizacao_id, tipo_ia, provedor, mae=False)
        if propria:
            return propria
    return _buscar(sessao, None, tipo_ia, provedor, mae=True)


def resolver_chave_por_time(
    sessao: Session,
    time_id: uuid.UUID | None,
    *,
    tipo_ia: str = "executora",
    provedor: str = "anthropic",
) -> str | None:
    """Conveniência para as fronteiras do motor, que conhecem o time da execução
    (automação ou agente): descobre a organização do time e resolve a chave."""
    organizacao_id = (
        sessao.scalar(select(Time.organizacao_id).where(Time.id == time_id))
        if time_id is not None
        else None
    )
    return resolver_chave(
        sessao, organizacao_id, tipo_ia=tipo_ia, provedor=provedor
    )
