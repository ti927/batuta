"""Endpoints de Automações e Execuções.

Uma automação é a definição de um fluxo: o gatilho e a cadeia (o grafo de
agentes com bifurcação). Aqui se monta a automação (CRUD), dispara-se
manualmente (Etapa 1), e cada passo é gravado em `passos_execucao` para a tela
de inspeção (Tarefas 4.3, 4.4 e 4.5).

Acesso por papel (Fase 6): membro vê (observador); operador cria/edita/dispara/
cancela; só admin apaga automação ou execução (apagar histórico). Responder uma
espera-por-humano (portão de aprovação) é ação de observador (MIGRACAO §3.7).
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from esquemas import (
    AutomacaoCriar,
    AutomacaoEditar,
    AutomacaoLer,
    DispararAutomacao,
    ExecucaoComPassos,
    ExecucaoLer,
    ExecucaoNaLista,
    PassoExecucaoLer,
    ResponderHumano,
)
import agendador
import auditoria
import fila
import precos
from auth import usuario_atual
from modelos import (
    Agente,
    Automacao,
    Execucao,
    Membro,
    Organizacao,
    PassoExecucao,
    Time,
    Usuario,
)
from chaves import resolver_chaves_por_time
from orquestracao.cadeia import (
    _DESTINOS_FIM,
    _escolher_saida,
    executar_cadeia,
    validar_cadeia,
)
from orquestracao.llm import usar_chaves
from orquestracao.disparo import (
    _aplicar_resultado,
    _fazer_registrador,
    criar_execucao,
)
from rotas._comum import automacao_acessivel, execucao_acessivel, time_acessivel
from sessao import obter_sessao

# Estados em que a execução já encerrou (não há mais o que cancelar).
ESTADOS_ENCERRADOS = {"concluida", "falhou", "cancelada"}

rotas = APIRouter(tags=["automacoes"])


def _entrada_retomada(saida_pausada: str, resposta: str) -> str:
    """A entrada do próximo nó ao retomar uma pausa: o trabalho que o agente
    produziu + a decisão/feedback do humano, separados e rotulados."""
    return f"{saida_pausada}\n\n---\n[Resposta do humano]\n{resposta}"


def _ids_dos_agentes(sessao: Session, time_id: uuid.UUID) -> set[str]:
    return {
        str(i)
        for i in sessao.scalars(
            select(Agente.id).where(Agente.time_id == time_id)
        ).all()
    }


def _validar_cadeia_ou_422(sessao: Session, time_id: uuid.UUID, cadeia: dict) -> None:
    try:
        validar_cadeia(cadeia or {}, _ids_dos_agentes(sessao, time_id))
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


# ───────────────────────── CRUD de automações ────────────────────


@rotas.get("/times/{time_id}/automacoes", response_model=list[AutomacaoLer])
def listar(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time_acessivel(sessao, usuario, time_id)
    return sessao.scalars(
        select(Automacao)
        .where(Automacao.time_id == time_id)
        .order_by(Automacao.criado_em)
    ).all()


@rotas.post(
    "/times/{time_id}/automacoes",
    response_model=AutomacaoLer,
    status_code=status.HTTP_201_CREATED,
)
def criar(
    time_id: uuid.UUID,
    dados: AutomacaoCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time_acessivel(sessao, usuario, time_id, minimo="operador")
    _validar_cadeia_ou_422(sessao, time_id, dados.cadeia)
    auto = Automacao(time_id=time_id, **dados.model_dump())
    sessao.add(auto)
    sessao.commit()
    sessao.refresh(auto)
    agendador.sincronizar(auto)
    return auto


@rotas.get("/automacoes/{automacao_id}", response_model=AutomacaoLer)
def obter(
    automacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    return automacao_acessivel(sessao, usuario, automacao_id)


@rotas.put("/automacoes/{automacao_id}", response_model=AutomacaoLer)
def editar(
    automacao_id: uuid.UUID,
    dados: AutomacaoEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    auto = automacao_acessivel(sessao, usuario, automacao_id, minimo="operador")
    _validar_cadeia_ou_422(sessao, auto.time_id, dados.cadeia)
    for campo, valor in dados.model_dump().items():
        setattr(auto, campo, valor)
    sessao.commit()
    sessao.refresh(auto)
    agendador.sincronizar(auto)
    return auto


@rotas.delete("/automacoes/{automacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    automacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    auto = automacao_acessivel(sessao, usuario, automacao_id, minimo="admin")
    sessao.delete(auto)
    sessao.commit()
    agendador.remover(automacao_id)


# ─────────────────────── Disparo e inspeção ──────────────────────


def _montar_com_passos(sessao: Session, execucao: Execucao) -> ExecucaoComPassos:
    passos = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem)
    ).all()
    base = ExecucaoLer.model_validate(execucao).model_dump()
    return ExecucaoComPassos(
        **base,
        passos=[PassoExecucaoLer.model_validate(p) for p in passos],
        uso=precos.resumir_uso(passos),
    )


@rotas.post(
    "/automacoes/{automacao_id}/disparar", response_model=ExecucaoComPassos
)
def disparar(
    automacao_id: uuid.UUID,
    dados: DispararAutomacao,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Disparo manual (botão de teste): roda independente do gatilho da
    automação. Não bloqueia: enfileira a execução e devolve o id na hora."""
    auto = automacao_acessivel(sessao, usuario, automacao_id, minimo="operador")
    execucao = criar_execucao(sessao, auto, dados.entrada)
    fila.enfileirar()
    return _montar_com_passos(sessao, execucao)


@rotas.post("/execucoes/{execucao_id}/responder", response_model=ExecucaoComPassos)
def responder(
    execucao_id: uuid.UUID,
    dados: ResponderHumano,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Retoma uma execução pausada (espera-por-humano): a resposta do humano
    vira a entrada do próximo agente, e a cadeia continua de onde parou.
    Responder o portão de aprovação é ação permitida ao observador (§3.7)."""
    execucao = execucao_acessivel(sessao, usuario, execucao_id)
    auto = sessao.get(Automacao, execucao.automacao_id)
    if execucao.estado != "aguardando_humano":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Esta execução não está aguardando resposta."
        )

    # Fases 7.3/7.6/7-A: as mesmas chaves (por provedor) da organização valem para
    # o roteamento da retomada e para o restante da cadeia (fallback consultoria →
    # .env legado p/ Anthropic), com as origens para carimbar a medição.
    chaves, origens = resolver_chaves_por_time(sessao, auto.time_id)

    # Auditoria (§3.7): a aprovação humana de um portão é ação sensível.
    auditoria.registrar(
        sessao, usuario=usuario, acao="portao.aprovado", recurso_tipo="execucao",
        recurso_id=execucao.id,
        organizacao_id=auditoria.org_do_time(sessao, auto.time_id),
        detalhe={"resposta": dados.resposta[:200]},
    )

    # O ponto de retomada é derivado do último passo (onde pausou) + a cadeia.
    ultimo = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()
    if ultimo is None or ultimo.agente_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Não foi possível retomar: passo de pausa ausente.",
        )

    cadeia = auto.cadeia or {}
    no = (cadeia.get("nos") or {}).get(str(ultimo.agente_id)) or {}
    saidas = no.get("saidas") or []

    # Portão de aprovação (PRODUTO §14): a RESPOSTA DO HUMANO escolhe o caminho.
    if len(saidas) == 0:
        escolhida = None
    elif len(saidas) == 1:
        escolhida = saidas[0]
    else:
        with usar_chaves(chaves):
            escolhida, _ = _escolher_saida(dados.resposta, saidas)
    destino = escolhida.get("destino") if escolhida else None
    proximo = None if destino in _DESTINOS_FIM else destino

    entrada_proxima = _entrada_retomada(
        (ultimo.saida or {}).get("texto", ""), dados.resposta
    )

    # Sem próximo agente (destino fim): encerra com o trabalho + a decisão.
    if proximo is None:
        execucao.estado = "concluida"
        execucao.resultado = {"texto": entrada_proxima}
        execucao.finalizada_em = datetime.now(timezone.utc)
        sessao.commit()
        sessao.refresh(execucao)
        return _montar_com_passos(sessao, execucao)

    execucao.estado = "em_andamento"
    sessao.commit()
    try:
        with usar_chaves(chaves):
            r = executar_cadeia(
                sessao,
                cadeia,
                entrada_proxima,
                no_inicial=proximo,
                ordem_inicial=ultimo.ordem,
                registrar_passo=_fazer_registrador(sessao, execucao.id, origens),
            )
        _aplicar_resultado(execucao, r)
    except Exception as e:
        execucao.estado = "falhou"
        execucao.resultado = {"erro": str(e)}
        execucao.finalizada_em = datetime.now(timezone.utc)
    sessao.commit()
    sessao.refresh(execucao)
    return _montar_com_passos(sessao, execucao)


@rotas.get(
    "/automacoes/{automacao_id}/execucoes", response_model=list[ExecucaoLer]
)
def listar_execucoes(
    automacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    automacao_acessivel(sessao, usuario, automacao_id)
    return sessao.scalars(
        select(Execucao)
        .where(Execucao.automacao_id == automacao_id)
        .order_by(Execucao.criado_em.desc())
    ).all()


@rotas.get("/execucoes", response_model=list[ExecucaoNaLista])
def listar_todas_execucoes(
    estado: str | None = None,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Visão consolidada de execuções das organizações em que o usuário é membro,
    com filtro opcional por estado (gestão de execuções, Tarefa 5.5)."""
    consulta = (
        select(Execucao, Automacao.nome, Organizacao.id)
        .join(Automacao, Automacao.id == Execucao.automacao_id)
        .join(Time, Time.id == Automacao.time_id)
        .join(Organizacao, Organizacao.id == Time.organizacao_id)
        .join(Membro, Membro.organizacao_id == Organizacao.id)
        .where(Membro.usuario_id == usuario.id)
        .order_by(Execucao.criado_em.desc())
    )
    if estado:
        consulta = consulta.where(Execucao.estado == estado)
    return [
        ExecucaoNaLista(
            **ExecucaoLer.model_validate(e).model_dump(),
            automacao_nome=nome,
            organizacao_id=org_id,
        )
        for e, nome, org_id in sessao.execute(consulta).all()
    ]


@rotas.get("/uso/resumo")
def resumo_uso(
    organizacao_id: uuid.UUID | None = None,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Medição consolidada (Fase 7.6): soma o uso de TODOS os passos das execuções
    das organizações em que o usuário é membro, com `por_origem` separando o
    consumo por chave (cliente × consultoria × legado). Filtro opcional por
    organização. O isolamento vem do join por `membros` (cada um só vê o seu)."""
    consulta = (
        select(PassoExecucao)
        .join(Execucao, Execucao.id == PassoExecucao.execucao_id)
        .join(Automacao, Automacao.id == Execucao.automacao_id)
        .join(Time, Time.id == Automacao.time_id)
        .join(Membro, Membro.organizacao_id == Time.organizacao_id)
        .where(Membro.usuario_id == usuario.id)
    )
    if organizacao_id is not None:
        consulta = consulta.where(Time.organizacao_id == organizacao_id)
    passos = sessao.scalars(consulta).all()
    return precos.resumir_uso(passos)


@rotas.get("/execucoes/{execucao_id}", response_model=ExecucaoComPassos)
def obter_execucao(
    execucao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    execucao = execucao_acessivel(sessao, usuario, execucao_id)
    return _montar_com_passos(sessao, execucao)


@rotas.post("/execucoes/{execucao_id}/cancelar", response_model=ExecucaoComPassos)
def cancelar_execucao(
    execucao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Cancela uma execução enfileirada, em andamento ou pausada. Se estiver
    rodando, o trabalhador para no próximo passo (cancelamento cooperativo)."""
    execucao = execucao_acessivel(sessao, usuario, execucao_id, minimo="operador")
    if execucao.estado in ESTADOS_ENCERRADOS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Esta execução já encerrou."
        )
    execucao.estado = "cancelada"
    if not execucao.resultado:
        execucao.resultado = {"texto": "Cancelada pelo operador."}
    execucao.finalizada_em = datetime.now(timezone.utc)
    sessao.commit()
    sessao.refresh(execucao)
    return _montar_com_passos(sessao, execucao)


@rotas.delete("/execucoes/{execucao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_execucao(
    execucao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Apaga o registro de uma execução já encerrada (e seus passos, em cascata).
    Apagar histórico é ação de admin (§3.7)."""
    execucao = execucao_acessivel(sessao, usuario, execucao_id, minimo="admin")
    if execucao.estado not in ESTADOS_ENCERRADOS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cancele a execução antes de apagá-la."
        )
    sessao.delete(execucao)
    sessao.commit()
