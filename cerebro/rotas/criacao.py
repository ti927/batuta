"""Endpoints da IA criadora — UMA conversa que nunca termina (paradigma novo).

A conversa nasce na ORGANIZAÇÃO e ganha um time assim que a IA o cria (no primeiro
`definir_time`). A partir daí a IA escreve no TIME REAL pela porta de
`criacao.servicos`; nada roda até o consultor ATIVAR (parede de ativação). Não há
mais 'aprovar/descartar' nem rascunho.

Acesso por papel (Fase 6): observador VÊ; operador CONVERSA (cria e edita o time pela
IA). Criar/editar via IA é equiparado ao CRUD de operador.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
import fila_turnos
from auth import usuario_atual
from criacao import memoria
from criacao.ferramentas import snapshot_time
from esquemas import (
    ConversaCriacaoLer,
    ConversaCriacaoResumo,
    IniciarConversaCriacao,
    MensagemTurno,
    ResumoProjeto,
    TurnoCriacaoLer,
    TurnoEnfileirado,
)
from modelos import ConversaCriacao, Time, TurnoCriacao, Usuario
from rotas._comum import (
    conversa_criacao_acessivel,
    organizacao_acessivel,
    time_acessivel,
)
from sessao import obter_sessao

rotas = APIRouter(tags=["criacao"])


def _turno_em_voo(sessao: Session, conversa_id: uuid.UUID) -> TurnoCriacao | None:
    """O turno ainda não-terminal (aguardando/em_andamento) desta conversa, se houver.
    É a base tanto da guarda de concorrência quanto da retomada após reload."""
    return sessao.scalars(
        select(TurnoCriacao)
        .where(
            TurnoCriacao.conversa_id == conversa_id,
            TurnoCriacao.estado.in_(("aguardando", "em_andamento")),
        )
        .order_by(TurnoCriacao.criado_em.desc())
    ).first()


def _enfileirar_turno(
    sessao: Session, conversa: ConversaCriacao, mensagem: str, usuario: Usuario
) -> TurnoCriacao:
    """Cria o turno `aguardando` e cutuca a fila de fundo — devolve NA HORA (o turno roda
    em segundo plano, sem prender a requisição). Recusa 409 se já há um turno em voo nesta
    conversa: a história é compartilhada, então um turno de cada vez (a trava de banco
    `uq_turno_ativo_por_conversa` fecha a corrida de dois envios simultâneos)."""
    if _turno_em_voo(sessao, conversa.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A IA ainda está respondendo à mensagem anterior. Aguarde ela terminar.",
        )
    turno = TurnoCriacao(
        conversa_id=conversa.id,
        usuario_id=usuario.id,
        pergunta=mensagem,
        estado="aguardando",
    )
    sessao.add(turno)
    sessao.commit()
    sessao.refresh(turno)
    fila_turnos.enfileirar()
    return turno


def _ler(sessao: Session, conversa: ConversaCriacao) -> ConversaCriacaoLer:
    """A conversa + a fotografia do time real + a memória de longo prazo (para o front
    desenhar o canvas e o painel 'O que eu sei deste projeto') + o turno em andamento (se
    houver), para a tela RETOMAR o acompanhamento após um reload."""
    lido = ConversaCriacaoLer.model_validate(conversa)
    lido.time = snapshot_time(sessao, conversa)
    lido.memoria = memoria.para_o_prompt(sessao, conversa)
    em_voo = _turno_em_voo(sessao, conversa.id)
    if em_voo is not None:
        lido.turno_em_andamento = TurnoCriacaoLer.model_validate(em_voo)
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
        # Enfileira o primeiro turno (roda em segundo plano); a tela abre na hora e
        # acompanha por `turno_em_andamento`.
        _enfileirar_turno(sessao, conversa, dados.mensagem_inicial, usuario)
    else:
        sessao.commit()
    sessao.refresh(conversa)
    return _ler(sessao, conversa)


@rotas.post(
    "/times/{time_id}/conversa",
    response_model=ConversaCriacaoLer,
    status_code=status.HTTP_201_CREATED,
)
def obter_ou_criar_conversa_do_time(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """A conversa eterna deste time, para o painel da IA dentro de `/times/[id]`.
    Devolve a conversa existente (a mais recente que aponta para o time) ou cria
    uma já amarrada ao time — caminho de borda para times criados sem a IA (pelo
    CRUD manual). A conversa criada pela IA já nasce com `time_id`; aqui só
    garantimos que sempre exista uma. Acesso: operador."""
    time = time_acessivel(sessao, usuario, time_id, minimo="operador")
    conversa = sessao.scalars(
        select(ConversaCriacao)
        .where(ConversaCriacao.time_id == time_id)
        .order_by(ConversaCriacao.atualizado_em.desc())
    ).first()
    if conversa is None:
        conversa = ConversaCriacao(
            organizacao_id=time.organizacao_id,
            criada_por_id=usuario.id,
            titulo=time.nome,
            time_id=time_id,
        )
        sessao.add(conversa)
        sessao.flush()
        auditoria.registrar(
            sessao, usuario=usuario, acao="criacao.conversa_iniciada",
            recurso_tipo="conversa_criacao", recurso_id=conversa.id,
            organizacao_id=time.organizacao_id,
        )
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


@rotas.get("/conversas-criacao/{conversa_id}/resumo", response_model=ResumoProjeto)
def obter_resumo(
    conversa_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """O resumo atual do projeto (leitura leve — sem a foto do time). O painel 'Sobre
    este time' busca por aqui ao abrir, para refletir o que a IA acabou de escrever no
    resumo durante a conversa (a versão carregada com a página pode estar defasada)."""
    conversa = conversa_criacao_acessivel(sessao, usuario, conversa_id)
    return ResumoProjeto(resumo=conversa.resumo)


@rotas.put("/conversas-criacao/{conversa_id}/resumo", response_model=ResumoProjeto)
def editar_resumo(
    conversa_id: uuid.UUID,
    dados: ResumoProjeto,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Edita o resumo do projeto (o painel 'Sobre este time'): a versão humana VENCE a
    da IA, que segue refinando a partir dela (o resumidor rolante parte do `resumo`
    atual). Acesso: operador (mesmo nível de quem conversa/edita o time)."""
    conversa = conversa_criacao_acessivel(
        sessao, usuario, conversa_id, minimo="operador"
    )
    conversa.resumo = (dados.resumo or "").strip() or None
    auditoria.registrar(
        sessao, usuario=usuario, acao="criacao.resumo_editado",
        recurso_tipo="conversa_criacao", recurso_id=conversa.id,
        organizacao_id=conversa.organizacao_id,
    )
    sessao.commit()
    return ResumoProjeto(resumo=conversa.resumo)


@rotas.post(
    "/conversas-criacao/{conversa_id}/mensagens",
    response_model=TurnoEnfileirado,
    status_code=status.HTTP_202_ACCEPTED,
)
def enviar_mensagem(
    conversa_id: uuid.UUID,
    dados: MensagemTurno,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Enfileira o turno e devolve NA HORA (roda em segundo plano). A tela acompanha o
    andamento — atividade ao vivo + resultado — por `GET .../turnos/{turno_id}`."""
    conversa = conversa_criacao_acessivel(
        sessao, usuario, conversa_id, minimo="operador"
    )
    turno = _enfileirar_turno(sessao, conversa, dados.mensagem, usuario)
    return TurnoEnfileirado(turno_id=turno.id, estado=turno.estado)


@rotas.get(
    "/conversas-criacao/{conversa_id}/turnos/{turno_id}",
    response_model=TurnoCriacaoLer,
)
def acompanhar_turno(
    conversa_id: uuid.UUID,
    turno_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """O andamento de um turno (a tela consulta ~1,5s): atividade ao vivo enquanto roda,
    resultado ao concluir, mensagem humana ao falhar. Acesso de leitura (observador vê)."""
    conversa = conversa_criacao_acessivel(sessao, usuario, conversa_id)
    turno = sessao.get(TurnoCriacao, turno_id)
    if turno is None or turno.conversa_id != conversa.id:
        raise HTTPException(status_code=404, detail="Turno não encontrado.")
    return turno
