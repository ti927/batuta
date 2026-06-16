"""Endpoints da IA criadora — UMA conversa que nunca termina (paradigma novo).

A conversa nasce na ORGANIZAÇÃO e ganha um time assim que a IA o cria (no primeiro
`definir_time`). A partir daí a IA escreve no TIME REAL pela porta de
`criacao.servicos`; nada roda até o consultor ATIVAR (parede de ativação). Não há
mais 'aprovar/descartar' nem rascunho.

Acesso por papel (Fase 6): observador VÊ; operador CONVERSA (cria e edita o time pela
IA). Criar/editar via IA é equiparado ao CRUD de operador.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import agendador
import auditoria
from auth import usuario_atual
from chaves import ORIGEM_LEGADO, resolver_chaves_por_organizacao
from criacao import memoria
from criacao.ferramentas import snapshot_time
from criacao.loop import MODELO_CRIADORA, responder_turno
from esquemas import (
    ConversaCriacaoLer,
    ConversaCriacaoResumo,
    IniciarConversaCriacao,
    MensagemTurno,
    RespostaTurno,
)
from modelos import Automacao, ConversaCriacao, Organizacao, Time, Usuario
from orquestracao.modelos_ia import provedor_do_modelo
from rotas._comum import conversa_criacao_acessivel, organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["criacao"])


def _rodar_turno(
    sessao: Session, conversa: ConversaCriacao, mensagem: str, usuario: Usuario
) -> dict:
    """Resolve a chave da criadora (por organização) e roda um turno, persistindo a
    conversa e o time real. Depois, sincroniza o agendador (a IA pode ter ativado/
    mudado o gatilho). Devolve {resposta, chips, time_id, time, uso}."""
    chaves, origens = resolver_chaves_por_organizacao(
        sessao, conversa.organizacao_id
    )
    # O modelo da conversa é escolhido por organização (nulo = padrão Opus). A origem
    # da medição sai do provedor DESSE modelo, não mais fixa no de Opus.
    org = sessao.get(Organizacao, conversa.organizacao_id)
    modelo = (org.modelo_criadora if org else None) or MODELO_CRIADORA
    origem = origens.get(provedor_do_modelo(modelo), ORIGEM_LEGADO)
    resultado = responder_turno(
        sessao, conversa, mensagem, usuario=usuario, chaves=chaves, origem=origem,
        modelo=modelo,
    )
    sessao.commit()
    # A IA pode ter ativado a automação ou mudado o gatilho: (re)agenda no relógio.
    if conversa.time_id:
        auto = sessao.scalars(
            select(Automacao)
            .where(Automacao.time_id == conversa.time_id)
            .order_by(Automacao.criado_em)
        ).first()
        if auto is not None:
            agendador.sincronizar(auto)
    return resultado


def _ler(sessao: Session, conversa: ConversaCriacao) -> ConversaCriacaoLer:
    """A conversa + a fotografia do time real + a memória de longo prazo (para o
    front desenhar o canvas e o painel 'O que eu sei deste projeto')."""
    lido = ConversaCriacaoLer.model_validate(conversa)
    lido.time = snapshot_time(sessao, conversa)
    lido.memoria = memoria.para_o_prompt(sessao, conversa)
    return lido


@rotas.post(
    "/organizacoes/{organizacao_id}/conversas-criacao",
    response_model=ConversaCriacaoLer,
    status_code=status.HTTP_201_CREATED,
)
def iniciar(
    organizacao_id: uuid.UUID,
    dados: IniciarConversaCriacao,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id, minimo="operador")
    conversa = ConversaCriacao(
        organizacao_id=organizacao_id, criada_por_id=usuario.id, titulo=dados.titulo
    )
    sessao.add(conversa)
    sessao.flush()
    auditoria.registrar(
        sessao, usuario=usuario, acao="criacao.conversa_iniciada",
        recurso_tipo="conversa_criacao", recurso_id=conversa.id,
        organizacao_id=organizacao_id,
    )
    if dados.mensagem_inicial:
        _rodar_turno(sessao, conversa, dados.mensagem_inicial, usuario)
    else:
        sessao.commit()
    sessao.refresh(conversa)
    return _ler(sessao, conversa)


@rotas.get(
    "/organizacoes/{organizacao_id}/conversas-criacao",
    response_model=list[ConversaCriacaoResumo],
)
def listar(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, organizacao_id)
    # Junta o nome do time (LEFT JOIN: a conversa pode ainda não ter criado um) para a
    # tela de retomar projeto rotular cada conversa. Mais recentes primeiro.
    linhas = sessao.execute(
        select(ConversaCriacao, Time.nome)
        .outerjoin(Time, Time.id == ConversaCriacao.time_id)
        .where(ConversaCriacao.organizacao_id == organizacao_id)
        .order_by(ConversaCriacao.atualizado_em.desc())
    ).all()
    resumos: list[ConversaCriacaoResumo] = []
    for conversa, time_nome in linhas:
        resumo = ConversaCriacaoResumo.model_validate(conversa)
        resumo.time_nome = time_nome
        resumos.append(resumo)
    return resumos


@rotas.get("/conversas-criacao/{conversa_id}", response_model=ConversaCriacaoLer)
def obter(
    conversa_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    conversa = conversa_criacao_acessivel(sessao, usuario, conversa_id)
    return _ler(sessao, conversa)


@rotas.post("/conversas-criacao/{conversa_id}/mensagens", response_model=RespostaTurno)
def enviar_mensagem(
    conversa_id: uuid.UUID,
    dados: MensagemTurno,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    conversa = conversa_criacao_acessivel(sessao, usuario, conversa_id, minimo="operador")
    return _rodar_turno(sessao, conversa, dados.mensagem, usuario)
