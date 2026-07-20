"""Endpoints de Automações e Execuções.

Uma automação é a definição de um fluxo: o gatilho e a cadeia (o grafo de
agentes com bifurcação). Aqui se monta a automação (CRUD), dispara-se
manualmente (Etapa 1), e cada passo é gravado em `passos_execucao` para a tela
de inspeção (Tarefas 4.3, 4.4 e 4.5).

Acesso por papel (Fase 6): membro vê (observador); operador cria/edita/dispara/
cancela; só admin apaga automação ou execução (apagar histórico). Responder uma
espera-por-humano (portão de aprovação) é ação de observador (MIGRACAO §3.7).
"""

import copy
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from esquemas import (
    AutomacaoCriar,
    AutomacaoEditar,
    AutomacaoLer,
    DispararAutomacao,
    DuplicarAutomacao,
    ExecucaoComPassos,
    ExecucaoLer,
    ExecucaoNaLista,
    PassoExecucaoLer,
    ResponderHumano,
)
import agendador
import auditoria
import duplicacao_comum
import fila
import portao_ativacao
import precos
from auth import usuario_atual
from modelos import (
    Agendamento,
    Agente,
    Automacao,
    Conversa,
    ConversaCriacao,
    Execucao,
    Instrumento,
    Membro,
    MensagemConversa,
    Organizacao,
    PassoExecucao,
    Time,
    Usuario,
)
from chaves import (
    ORIGEM_CONSULTORIA,
    ORIGEM_LEGADO,
    resolver_chaves_por_time,
)
from consultoria import exigir_admin_consultoria
from mensageria import aprovacao, config, retoma
from mensageria.config import painel_config
from orquestracao import grafo
from orquestracao.cadeia import validar_cadeia
from orquestracao.disparo import criar_execucao
from rotas._comum import (
    automacao_acessivel,
    execucao_acessivel,
    organizacao_acessivel,
    time_acessivel,
)
from sessao import obter_sessao

# Estados em que a execução já encerrou (não há mais o que cancelar).
ESTADOS_ENCERRADOS = {"concluida", "falhou", "cancelada"}

rotas = APIRouter(tags=["automacoes"])


def _ids_dos_agentes(sessao: Session, time_id: uuid.UUID) -> set[str]:
    return {
        str(i)
        for i in sessao.scalars(
            select(Agente.id).where(Agente.time_id == time_id)
        ).all()
    }


def _ler_automacao(auto: Automacao) -> AutomacaoLer:
    """Serializa uma automação com a `cadeia` no formato canônico de grafo (normaliza
    na leitura, sem mutar o ORM — cobre linhas legadas ainda no formato antigo)."""
    dados = AutomacaoLer.model_validate(auto)
    dados.cadeia = grafo.normalizar(dados.cadeia or {})
    return dados


def _validar_cadeia_ou_422(sessao: Session, time_id: uuid.UUID, cadeia: dict) -> None:
    try:
        validar_cadeia(cadeia or {}, _ids_dos_agentes(sessao, time_id))
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


def _validar_portao_ou_422(sessao: Session, time_id: uuid.UUID, cadeia: dict) -> None:
    """Parede de ativação: bloqueia ligar uma automação em que um agente de ação
    irreversível não tem portão de aprovação humana antes na cadeia. Só chamada
    quando a automação vai ficar ATIVA — inativa não roda, não há o que blindar."""
    problemas = portao_ativacao.validar(sessao, time_id, cadeia or {})
    if problemas:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, {"problemas": problemas}
        )


# ───────────────────────── CRUD de automações ────────────────────


@rotas.get("/times/{time_id}/automacoes", response_model=list[AutomacaoLer])
def listar(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time_acessivel(sessao, usuario, time_id)
    autos = sessao.scalars(
        select(Automacao)
        .where(Automacao.time_id == time_id)
        .order_by(Automacao.criado_em)
    ).all()
    return [_ler_automacao(a) for a in autos]


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
    if dados.ativa:
        _validar_portao_ou_422(sessao, time_id, dados.cadeia)
    auto = Automacao(time_id=time_id, **dados.model_dump())
    auto.cadeia = grafo.normalizar(auto.cadeia or {})  # grava no formato canônico
    if not (auto.configuracao or {}).get("perfil"):  # nasce com um tipo de fluxo sensato
        auto.configuracao = {**(auto.configuracao or {}), "perfil": config.PERFIL_PADRAO}
    sessao.add(auto)
    sessao.commit()
    sessao.refresh(auto)
    agendador.sincronizar(auto)
    return _ler_automacao(auto)


@rotas.get("/config/fluxo")
def config_fluxo(usuario: Usuario = Depends(usuario_atual)):
    """Metadados para a UI montar as 'Configurações do fluxo': os perfis (com os
    defaults de cada um), os grupos de botões e o padrão global. Fonte única — o
    front renderiza a partir daqui, sem duplicar rótulos/valores."""
    return painel_config()


@rotas.get("/automacoes/{automacao_id}", response_model=AutomacaoLer)
def obter(
    automacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    return _ler_automacao(automacao_acessivel(sessao, usuario, automacao_id))


@rotas.put("/automacoes/{automacao_id}", response_model=AutomacaoLer)
def editar(
    automacao_id: uuid.UUID,
    dados: AutomacaoEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    auto = automacao_acessivel(sessao, usuario, automacao_id, minimo="operador")
    _validar_cadeia_ou_422(sessao, auto.time_id, dados.cadeia)
    if dados.ativa:
        _validar_portao_ou_422(sessao, auto.time_id, dados.cadeia)
    for campo, valor in dados.model_dump().items():
        setattr(auto, campo, valor)
    auto.cadeia = grafo.normalizar(auto.cadeia or {})  # grava no formato canônico
    sessao.commit()
    sessao.refresh(auto)
    agendador.sincronizar(auto)
    return _ler_automacao(auto)


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


@rotas.post(
    "/automacoes/{automacao_id}/duplicar",
    response_model=AutomacaoLer,
    status_code=status.HTTP_201_CREATED,
)
def duplicar(
    automacao_id: uuid.UUID,
    dados: DuplicarAutomacao,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Cria uma cópia independente de uma automação existente. Copia o *design*
    (gatilho, configuração, cadeia) no MESMO time; gera id/datas novos.

    A cópia nasce SEMPRE inativa (decisão do maestro): evita que uma cópia de
    automação agendada/webhook dispare em dobro com a original. O estado de
    execução (execuções, conversas) não existe no modelo — nasce limpo por
    construção. Deep-copy do JSONB isola a cópia da original. Acesso: operador.
    """
    original = automacao_acessivel(sessao, usuario, automacao_id, minimo="operador")

    nome = dados.nome.strip()
    if not nome:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Dê um nome à cópia."
        )

    # Deep-copy + normalização: a cópia fica isolada da original (mutar uma não
    # afeta a outra), no formato canônico que o motor enxerga (cobre linha legada).
    cadeia = grafo.normalizar(copy.deepcopy(original.cadeia or {}))
    # Gatilho de entrada (ex.: comentário do Instagram) nasce "a conectar" na cópia
    # (some a conta) — mesmo helper da duplicação de time, para não divergir.
    config = duplicacao_comum.sanear_gatilho_duplicado(
        original.tipo_gatilho, original.configuracao_gatilho
    )
    config_fluxo = copy.deepcopy(original.configuracao or {})

    # Mesma validação do criar (refs de agente do time). Não validamos o portão de
    # ativação: a cópia nasce inativa, a parede é checada quando o operador ligar.
    _validar_cadeia_ou_422(sessao, original.time_id, cadeia)

    copia = Automacao(
        time_id=original.time_id,
        nome=nome,
        tipo_gatilho=original.tipo_gatilho,
        configuracao_gatilho=config,
        cadeia=cadeia,
        ativa=False,
        configuracao=config_fluxo,
    )
    sessao.add(copia)
    sessao.commit()
    sessao.refresh(copia)
    agendador.sincronizar(copia)  # inativa → garante que nenhum job fica no relógio
    return _ler_automacao(copia)


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
    execucao = criar_execucao(sessao, auto, dados.entrada, origem="manual")
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

    # A mecânica de retoma vive na borda (reutilizada pela mensageria); aqui só a
    # autorização, o 409 e a auditoria. Falta de passo de pausa → 422.
    try:
        retoma.retomar_execucao(
            sessao, execucao, dados.resposta, chaves=chaves, origens=origens
        )
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Não foi possível retomar: passo de pausa ausente.",
        )
    # Coexistência (aprovação por canal): resolver pela tela desfaz o vínculo de
    # qualquer conversa que aguardava esta aprovação por mensageria — a não ser que
    # a cadeia tenha pausado de novo (a retoma já re-vincula nesse caso).
    if execucao.estado != "aguardando_humano":
        aprovacao.desvincular(sessao, execucao.id)
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


# ───────────────────── Agendamentos (disparo futuro por agente) ─────────────────────


@rotas.get("/organizacoes/{organizacao_id}/automacoes")
def listar_automacoes_da_organizacao(
    organizacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Todas as automações da organização (id, nome, time) — alimenta o seletor de
    'automação a agendar' do instrumento `agendar_automacao` (escopo: mesma org)."""
    organizacao_acessivel(sessao, usuario, organizacao_id)
    linhas = sessao.execute(
        select(Automacao.id, Automacao.nome, Time.id, Time.nome)
        .join(Time, Time.id == Automacao.time_id)
        .where(Time.organizacao_id == organizacao_id)
        .order_by(Time.nome, Automacao.nome)
    ).all()
    return [
        {"id": str(aid), "nome": anome, "time_id": str(tid), "time_nome": tnome}
        for aid, anome, tid, tnome in linhas
    ]


@rotas.get("/automacoes/{automacao_id}/agendamentos")
def listar_agendamentos(
    automacao_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Os agendamentos PENDENTES desta automação (próximas execuções agendadas)."""
    automacao_acessivel(sessao, usuario, automacao_id)
    ags = sessao.scalars(
        select(Agendamento)
        .where(
            Agendamento.automacao_id == automacao_id,
            Agendamento.estado == "pendente",
        )
        .order_by(Agendamento.quando_executar)
    ).all()
    return [
        {
            "id": str(a.id),
            "quando_executar": a.quando_executar.isoformat(),
            "criado_em": a.criado_em.isoformat(),
        }
        for a in ags
    ]


@rotas.get("/times/{time_id}/agendamentos")
def listar_agendamentos_do_time(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Agendamentos de TODAS as automações do time: os PENDENTES (próximos disparos, "no
    ar") + os CANCELADOS recentes (7 dias) com o MOTIVO — para nada falhar em silêncio
    (§12-A). Alimenta a aba 'Agendadas' das Execuções: o lugar central para ver o que
    vai/ia rodar, sem caçar automação por automação."""
    time_acessivel(sessao, usuario, time_id)
    corte = datetime.now(timezone.utc) - timedelta(days=7)
    linhas = sessao.execute(
        select(Agendamento, Automacao.nome)
        .join(Automacao, Automacao.id == Agendamento.automacao_id)
        .where(
            Automacao.time_id == time_id,
            or_(
                Agendamento.estado == "pendente",
                and_(
                    Agendamento.estado == "cancelado",
                    Agendamento.quando_executar >= corte,
                ),
            ),
        )
        .order_by(Agendamento.quando_executar)
    ).all()
    return [
        {
            "id": str(a.id),
            "automacao_id": str(a.automacao_id),
            "automacao_nome": nome,
            "quando_executar": a.quando_executar.isoformat(),
            "estado": a.estado,
            "motivo": a.motivo,
            "criado_em": a.criado_em.isoformat(),
        }
        for a, nome in linhas
    ]


@rotas.delete("/agendamentos/{agendamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_agendamento(
    agendamento_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Cancela um agendamento pendente (operador): marca `cancelado` (não apaga)."""
    ag = sessao.get(Agendamento, agendamento_id)
    if ag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agendamento não encontrado")
    auto = automacao_acessivel(sessao, usuario, ag.automacao_id, minimo="operador")
    if ag.estado == "pendente":
        ag.estado = "cancelado"
        ag.motivo = "Cancelado por você."
        auditoria.registrar(
            sessao, usuario=usuario, acao="agendamento.cancelado",
            recurso_tipo="agendamento", recurso_id=ag.id,
            organizacao_id=auditoria.org_do_time(sessao, auto.time_id),
        )
        sessao.commit()


@rotas.get("/times/{time_id}/execucoes", response_model=list[ExecucaoNaLista])
def listar_execucoes_do_time(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """As execuções de TODAS as automações do time, mais recentes primeiro — a
    aba Execuções (master-detail) da página do time. Observador vê."""
    time = time_acessivel(sessao, usuario, time_id)
    consulta = (
        select(Execucao, Automacao.nome)
        .join(Automacao, Automacao.id == Execucao.automacao_id)
        .where(Automacao.time_id == time_id)
        .order_by(Execucao.criado_em.desc())
    )
    return [
        ExecucaoNaLista(
            **ExecucaoLer.model_validate(e).model_dump(),
            automacao_nome=nome,
            organizacao_id=time.organizacao_id,
        )
        for e, nome in sessao.execute(consulta).all()
    ]


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
    time_id: uuid.UUID | None = None,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Medição consolidada (Fase 7.6): soma o uso de TODOS os passos das execuções
    das organizações em que o usuário é membro, com `por_origem` separando o
    consumo por chave (cliente × consultoria × legado). Filtros opcionais por
    organização e por time (o dashboard do time usa `time_id`). O isolamento vem
    do join por `membros` (cada um só vê o seu)."""
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
    if time_id is not None:
        consulta = consulta.where(Automacao.time_id == time_id)
    passos = sessao.scalars(consulta).all()

    # A conversa da IA criadora é da ORGANIZAÇÃO, não de um time. No resumo de uma
    # organização (sem time específico), some também o uso da conversa — senão o
    # gasto do Opus da conversa fica invisível. No resumo de um time, fica só a
    # execução (a conversa não pertence a um time).
    conversas = []
    if time_id is None:
        consulta_conv = (
            select(ConversaCriacao)
            .join(Membro, Membro.organizacao_id == ConversaCriacao.organizacao_id)
            .where(Membro.usuario_id == usuario.id)
        )
        if organizacao_id is not None:
            consulta_conv = consulta_conv.where(
                ConversaCriacao.organizacao_id == organizacao_id
            )
        conversas = sessao.scalars(consulta_conv).all()

    # Mensageria (atendimento): o uso de IA dos turnos vive em `mensagens_conversa.uso`
    # (mensagem do agente). O instrumento de canal pertence a um TIME, então o
    # atendimento entra TANTO no resumo do time quanto no da organização — fechando
    # o furo de a mensageria (e a transcrição de áudio) não aparecerem nos painéis.
    consulta_msg = (
        select(MensagemConversa)
        .join(Conversa, Conversa.id == MensagemConversa.conversa_id)
        .join(Instrumento, Instrumento.id == Conversa.instrumento_id)
        .join(Time, Time.id == Instrumento.time_id)
        .join(Membro, Membro.organizacao_id == Time.organizacao_id)
        .where(Membro.usuario_id == usuario.id)
        .where(MensagemConversa.uso.isnot(None))
    )
    if organizacao_id is not None:
        consulta_msg = consulta_msg.where(Time.organizacao_id == organizacao_id)
    if time_id is not None:
        consulta_msg = consulta_msg.where(Instrumento.time_id == time_id)
    mensagens = sessao.scalars(consulta_msg).all()

    return precos.resumir_uso(passos, conversas, mensagens)


@rotas.get("/uso/consultoria")
def uso_consultoria(
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Painel da consultoria: o consumo que saiu da CHAVE-MÃE (origem 'consultoria'
    ou 'legado' = a ANTHROPIC_API_KEY do .env, que na prática é da consultoria),
    somado entre TODAS as organizações e quebrado por organização. Inclui tanto as
    execuções (agentes) quanto as conversas da IA criadora. Restrito ao admin da
    consultoria."""
    exigir_admin_consultoria(usuario)
    da_consultoria = {ORIGEM_CONSULTORIA, ORIGEM_LEGADO}

    # nome por organização (uma busca só) + acumulador de entradas por org
    nomes = dict(sessao.execute(select(Organizacao.id, Organizacao.nome)).all())
    por_org: dict[uuid.UUID, list] = {}

    def _coletar(org_id, entradas):
        alvo = por_org.setdefault(org_id, [])
        alvo.extend(e for e in entradas if e.get("origem") in da_consultoria)

    linhas = sessao.execute(
        select(PassoExecucao, Time.organizacao_id)
        .join(Execucao, Execucao.id == PassoExecucao.execucao_id)
        .join(Automacao, Automacao.id == Execucao.automacao_id)
        .join(Time, Time.id == Automacao.time_id)
    ).all()
    for passo, org_id in linhas:
        _coletar(org_id, precos.entradas_dos_passos([passo]))
    for conversa in sessao.scalars(select(ConversaCriacao)).all():
        _coletar(conversa.organizacao_id, precos.entradas_das_conversas([conversa]))
    # Mensageria (atendimento + transcrição): o instrumento de canal liga a conversa
    # ao time → organização. Some o que saiu da chave-mãe também no atendimento.
    linhas_msg = sessao.execute(
        select(MensagemConversa, Time.organizacao_id)
        .join(Conversa, Conversa.id == MensagemConversa.conversa_id)
        .join(Instrumento, Instrumento.id == Conversa.instrumento_id)
        .join(Time, Time.id == Instrumento.time_id)
        .where(MensagemConversa.uso.isnot(None))
    ).all()
    for msg, org_id in linhas_msg:
        _coletar(org_id, precos.entradas_das_mensagens([msg]))

    por_organizacao = []
    todas: list = []
    for org_id, entradas in por_org.items():
        if not entradas:
            continue
        r = precos.resumir_uso_de_entradas(entradas)
        todas.extend(entradas)
        por_organizacao.append(
            {
                "organizacao_id": org_id,
                "organizacao_nome": nomes.get(org_id, "—"),
                "tokens_entrada": r["tokens_entrada"],
                "tokens_saida": r["tokens_saida"],
                "custo_usd": r["custo_usd"],
                # A quebra por FUNÇÃO (execução × conversa × atendimento × transcrição)
                # da chave-mãe nesta organização — onde o maestro quer enxergar.
                "por_categoria": r["por_categoria"],
            }
        )
    por_organizacao.sort(key=lambda x: x["custo_usd"], reverse=True)
    return {
        "total": precos.resumir_uso_de_entradas(todas),
        "por_organizacao": por_organizacao,
    }


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
    # Encerrar num portão é uma ação sensível e desvincula a conversa do aprovador —
    # por isso passa pelo helper único (mesma lógica do cancelar por canal).
    era_portao = execucao.estado == "aguardando_humano"
    aprovacao.cancelar_execucao(sessao, execucao, motivo="Cancelada pelo operador.")
    auto = sessao.get(Automacao, execucao.automacao_id)
    auditoria.registrar(
        sessao, usuario=usuario,
        acao="portao.cancelado" if era_portao else "execucao.cancelada",
        recurso_tipo="execucao", recurso_id=execucao.id,
        organizacao_id=auditoria.org_do_time(sessao, auto.time_id) if auto else None,
        detalhe={"origem": "tela"},
    )
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
