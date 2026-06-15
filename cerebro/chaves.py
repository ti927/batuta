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

import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from cofre import decifrar
from modelos import ChaveApi, Time
from orquestracao.modelos_ia import PROVEDOR_ANTHROPIC, PROVEDORES

# Serviço de busca (Tavily): não é provedor de MODELO, mas é uma chave de serviço
# COMPARTILHADA que a organização cadastra uma vez e o instrumento `busca_web`
# reusa do pool (mesma lógica de queda org→consultoria→legado). Não entra em
# PROVEDORES (que é só de modelos), mas entra no pool resolvido abaixo.
SERVICO_TAVILY = "tavily"

# Todos os serviços resolvidos pelo pool da organização: provedores de IA +
# serviços compartilháveis de instrumento.
SERVICOS = (*PROVEDORES, SERVICO_TAVILY)

# Serviços com queda de legado no `.env` do cérebro (na prática, da consultoria):
# Anthropic (ANTHROPIC_API_KEY) e Tavily (TAVILY_API_KEY). Os demais exigem chave
# do cofre.
SERVICOS_COM_LEGADO = frozenset({PROVEDOR_ANTHROPIC, SERVICO_TAVILY})


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
    condicoes = [
        condicao_org,
        ChaveApi.tipo_ia == tipo_ia,
        ChaveApi.provedor == provedor,
        ChaveApi.ativa.is_(True),
    ]
    # A chave-mãe da consultoria só serve de reserva às organizações se estiver
    # marcada como compartilhável (toggle). A chave PRÓPRIA da organização não
    # passa por esse filtro (é dela). Ver docs/CAIXA-FORTE-PLANO.md.
    if mae:
        condicoes.append(ChaveApi.compartilhavel.is_(True))
    chave = sessao.scalars(select(ChaveApi).where(*condicoes)).first()
    return decifrar(chave.valor_cifrado) if chave else None


# Rótulos de ORIGEM da chave, para a medição refinada (Fase 7.6): de qual chave
# saiu o consumo de cada passo. "legado" = nenhuma chave no cofre, caiu na
# ANTHROPIC_API_KEY do .env (que, na prática, é da consultoria).
ORIGEM_ORGANIZACAO = "organizacao"  # chave própria do cliente
ORIGEM_CONSULTORIA = "consultoria"  # chave-mãe da consultoria
ORIGEM_LEGADO = "legado"  # .env legado (sem chave cadastrada)


def _resolver(
    sessao: Session, organizacao_id: uuid.UUID | None, tipo_ia: str, provedor: str
) -> tuple[str | None, str | None]:
    """Núcleo da resolução: devolve (chave, origem). origem é ORIGEM_ORGANIZACAO
    ou ORIGEM_CONSULTORIA quando achou no cofre; (None, None) quando nada há."""
    if organizacao_id is not None:
        propria = _buscar(sessao, organizacao_id, tipo_ia, provedor, mae=False)
        if propria:
            return propria, ORIGEM_ORGANIZACAO
    mae = _buscar(sessao, None, tipo_ia, provedor, mae=True)
    if mae:
        return mae, ORIGEM_CONSULTORIA
    return None, None


def resolver_chave(
    sessao: Session,
    organizacao_id: uuid.UUID | None,
    *,
    tipo_ia: str = "executora",
    provedor: str = "anthropic",
) -> str | None:
    """Resolve a chave de IA pela ordem de fallback. Devolve a chave decifrada
    ou None (quando nem a organização nem a consultoria têm chave cadastrada)."""
    return _resolver(sessao, organizacao_id, tipo_ia, provedor)[0]


def _org_do_time(sessao: Session, time_id: uuid.UUID | None) -> uuid.UUID | None:
    if time_id is None:
        return None
    return sessao.scalar(select(Time.organizacao_id).where(Time.id == time_id))


def resolver_chave_por_time(
    sessao: Session,
    time_id: uuid.UUID | None,
    *,
    tipo_ia: str = "executora",
    provedor: str = "anthropic",
) -> str | None:
    """Conveniência para as fronteiras do motor, que conhecem o time da execução
    (automação ou agente): descobre a organização do time e resolve a chave."""
    organizacao_id = _org_do_time(sessao, time_id)
    return resolver_chave(
        sessao, organizacao_id, tipo_ia=tipo_ia, provedor=provedor
    )


def resolver_chave_e_origem_por_time(
    sessao: Session,
    time_id: uuid.UUID | None,
    *,
    tipo_ia: str = "executora",
    provedor: str = "anthropic",
) -> tuple[str | None, str]:
    """Como `resolver_chave_por_time`, mas devolve também a ORIGEM da chave para
    a medição (Fase 7.6). Quando nada há no cofre, a origem é ORIGEM_LEGADO (o
    motor usará a ANTHROPIC_API_KEY do .env)."""
    organizacao_id = _org_do_time(sessao, time_id)
    chave, origem = _resolver(sessao, organizacao_id, tipo_ia, provedor)
    return chave, (origem or ORIGEM_LEGADO)


def resolver_chaves_por_organizacao(
    sessao: Session,
    organizacao_id: uuid.UUID | None,
    *,
    tipo_ia: str = "executora",
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve a chave de CADA provedor suportado para uma ORGANIZAÇÃO (Fase 7-A:
    multi-provedor). Devolve dois mapas por provedor: `chaves` {provedor: chave}
    (só os provedores com chave no cofre) e `origens` {provedor: origem} (medição
    7.6).

    A Anthropic ganha origem ORIGEM_LEGADO mesmo sem chave no cofre, pois o motor
    cai na ANTHROPIC_API_KEY do .env; OpenAI/Google sem chave ficam de fora (o
    motor exige a chave do cofre e falha de forma clara se um modelo deles rodar).

    É por aqui que a IA criadora (Fase 9) resolve sua chave: ela trabalha por
    organização (o time ainda não existe), com `tipo_ia='criadora'`."""
    chaves: dict[str, str] = {}
    origens: dict[str, str] = {}
    for servico in SERVICOS:
        chave, origem = _resolver(sessao, organizacao_id, tipo_ia, servico)
        if chave:
            chaves[servico] = chave
            origens[servico] = origem
        elif servico in SERVICOS_COM_LEGADO:
            origens[servico] = ORIGEM_LEGADO
    return chaves, origens


def resolver_chaves_por_time(
    sessao: Session,
    time_id: uuid.UUID | None,
    *,
    tipo_ia: str = "executora",
) -> tuple[dict[str, str], dict[str, str]]:
    """Como `resolver_chaves_por_organizacao`, mas a partir do time da execução
    (automação ou agente): descobre a organização do time e resolve por ela."""
    return resolver_chaves_por_organizacao(
        sessao, _org_do_time(sessao, time_id), tipo_ia=tipo_ia
    )


def provedores_disponiveis(
    sessao: Session,
    organizacao_id: uuid.UUID | None,
    *,
    tipo_ia: str = "executora",
) -> dict[str, bool]:
    """Quais provedores têm chave RESOLVÍVEL para esta organização e tipo de IA —
    contando o fallback da consultoria. A Anthropic também conta como disponível
    quando há `ANTHROPIC_API_KEY` no ambiente (o motor cai nela como legado). Só
    booleanos: não expõe nenhum segredo. Alimenta o seletor de modelos da tela
    (não adianta oferecer um modelo cujo provedor não tem chave)."""
    chaves, _ = resolver_chaves_por_organizacao(
        sessao, organizacao_id, tipo_ia=tipo_ia
    )
    disponiveis = {provedor: provedor in chaves for provedor in PROVEDORES}
    if not disponiveis[PROVEDOR_ANTHROPIC] and os.environ.get("ANTHROPIC_API_KEY"):
        disponiveis[PROVEDOR_ANTHROPIC] = True
    return disponiveis
