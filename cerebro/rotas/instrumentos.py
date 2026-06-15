"""Endpoints de Instrumentos.

CRUD de instrumentos de um time, a lista de tipos disponíveis no encaixe, e o
acionamento isolado de um instrumento. Acesso por papel (Fase 6): membro vê;
operador cria/edita/aciona; só admin apaga.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
import instrumentos as encaixe
import segredos_instrumento as segredos
from auth import usuario_atual
from instrumentos.base import FalhaInstrumento
from esquemas import (
    AcionarInstrumento,
    InstrumentoCriar,
    InstrumentoEditar,
    InstrumentoLer,
    TipoInstrumentoLer,
)
from modelos import Credencial, Instrumento, Usuario
from rotas._comum import instrumento_acessivel, time_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["instrumentos"])


def _validar_credencial(
    sessao: Session,
    tipo_instrumento: str,
    organizacao_id: uuid.UUID,
    credencial_id: uuid.UUID | None,
) -> None:
    """Se o instrumento aponta para uma credencial da caixa-forte, valida que ela
    existe, é acessível (da própria org, ou da consultoria E compartilhável) e é
    de um tipo que este instrumento aceita. Levanta 422 caso contrário."""
    if credencial_id is None:
        return
    cred = sessao.get(Credencial, credencial_id)
    if cred is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Credencial não encontrada.")
    if cred.organizacao_id is not None and cred.organizacao_id != organizacao_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Credencial de outra organização."
        )
    if cred.organizacao_id is None and not cred.compartilhavel:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Esta credencial da consultoria não está compartilhada.",
        )
    tipo = encaixe.obter_tipo(tipo_instrumento)
    aceitos = getattr(tipo, "tipos_credencial_aceitos", ()) if tipo else ()
    if cred.tipo not in aceitos:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Este instrumento não aceita credencial do tipo '{cred.tipo}'.",
        )


def _ler(sessao: Session, inst: Instrumento) -> Instrumento:
    """Anexa o resumo mascarado dos segredos (campo → 4 últimos dígitos) e o
    `acao_irreversivel` JÁ RESOLVIDO (tipo+config+interruptor), para o
    `InstrumentoLer` os devolver — segredos nunca expostos."""
    inst.segredos = segredos.resumo(sessao, inst.id)
    inst.acao_irreversivel = encaixe.exige_portao(
        inst.tipo, inst.configuracao, inst.exige_aprovacao
    )
    return inst


# Declarado ANTES de /instrumentos/{id} para que "tipos" não seja lido como UUID.
@rotas.get("/instrumentos/tipos", response_model=list[TipoInstrumentoLer])
def listar_tipos(usuario: Usuario = Depends(usuario_atual)):
    """O catálogo de tipos do encaixe não é de nenhuma organização; basta estar
    autenticado para consultá-lo."""
    return [
        TipoInstrumentoLer(
            tipo=t.tipo,
            nome_exibicao=t.nome_exibicao,
            descricao=t.descricao,
            esquema_config=t.Config.model_json_schema(),
            esquema_args=t.Args.model_json_schema(),
            campos_secretos=list(t.campos_secretos),
            chave_compartilhada=(
                list(t.chave_compartilhada) if t.chave_compartilhada else None
            ),
            tipos_credencial_aceitos=list(t.tipos_credencial_aceitos),
            acao_irreversivel=t.acao_irreversivel,
        )
        for t in encaixe.tipos_disponiveis()
    ]


@rotas.get("/times/{time_id}/instrumentos", response_model=list[InstrumentoLer])
def listar(
    time_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time_acessivel(sessao, usuario, time_id)
    consulta = (
        select(Instrumento)
        .where(Instrumento.time_id == time_id)
        .order_by(Instrumento.criado_em)
    )
    return [_ler(sessao, inst) for inst in sessao.scalars(consulta).all()]


@rotas.post(
    "/times/{time_id}/instrumentos",
    response_model=InstrumentoLer,
    status_code=status.HTTP_201_CREATED,
)
def criar(
    time_id: uuid.UUID,
    dados: InstrumentoCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    time = time_acessivel(sessao, usuario, time_id, minimo="operador")
    try:
        # Fase 7-B: separa os segredos da config pública antes de gravar.
        config_limpa, segredos_novos = encaixe.preparar_config(
            dados.tipo, dados.configuracao
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    _validar_credencial(sessao, dados.tipo, time.organizacao_id, dados.credencial_id)
    inst = Instrumento(
        time_id=time_id,
        nome=dados.nome,
        tipo=dados.tipo,
        configuracao=config_limpa,
        exige_aprovacao=dados.exige_aprovacao,
        credencial_id=dados.credencial_id,
    )
    sessao.add(inst)
    sessao.flush()
    segredos.salvar_segredos(sessao, inst.id, segredos_novos)
    auditoria.registrar(
        sessao, usuario=usuario, acao="instrumento.criado",
        recurso_tipo="instrumento", recurso_id=inst.id,
        organizacao_id=time.organizacao_id,
        detalhe={"segredos": list(segredos_novos)} if segredos_novos else None,
    )
    sessao.commit()
    sessao.refresh(inst)
    return _ler(sessao, inst)


@rotas.get("/instrumentos/{instrumento_id}", response_model=InstrumentoLer)
def obter(
    instrumento_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    return _ler(sessao, instrumento_acessivel(sessao, usuario, instrumento_id))


@rotas.put("/instrumentos/{instrumento_id}", response_model=InstrumentoLer)
def editar(
    instrumento_id: uuid.UUID,
    dados: InstrumentoEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    inst = instrumento_acessivel(sessao, usuario, instrumento_id, minimo="operador")
    try:
        # Fase 7-B: separa os segredos; um segredo omitido preserva o atual.
        config_limpa, segredos_novos = encaixe.preparar_config(
            inst.tipo, dados.configuracao
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    _validar_credencial(
        sessao, inst.tipo,
        auditoria.org_do_time(sessao, inst.time_id), dados.credencial_id,
    )
    aprovacao_antes = inst.exige_aprovacao
    inst.nome = dados.nome
    inst.configuracao = config_limpa
    inst.exige_aprovacao = dados.exige_aprovacao
    inst.credencial_id = dados.credencial_id
    alterados = segredos.salvar_segredos(sessao, inst.id, segredos_novos)
    if alterados:
        auditoria.registrar(
            sessao, usuario=usuario, acao="instrumento.segredo_alterado",
            recurso_tipo="instrumento", recurso_id=inst.id,
            organizacao_id=auditoria.org_do_time(sessao, inst.time_id),
            detalhe={"segredos": alterados},
        )
    # Mudar o interruptor de aprovação afeta a segurança (pode liberar uma escrita
    # sem portão) — fica auditado.
    if dados.exige_aprovacao != aprovacao_antes:
        auditoria.registrar(
            sessao, usuario=usuario, acao="instrumento.aprovacao_alterada",
            recurso_tipo="instrumento", recurso_id=inst.id,
            organizacao_id=auditoria.org_do_time(sessao, inst.time_id),
            detalhe={"de": aprovacao_antes, "para": dados.exige_aprovacao},
        )
    sessao.commit()
    sessao.refresh(inst)
    return _ler(sessao, inst)


@rotas.delete(
    "/instrumentos/{instrumento_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remover(
    instrumento_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    inst = instrumento_acessivel(sessao, usuario, instrumento_id, minimo="admin")
    auditoria.registrar(
        sessao, usuario=usuario, acao="instrumento.removido",
        recurso_tipo="instrumento", recurso_id=inst.id,
        organizacao_id=auditoria.org_do_time(sessao, inst.time_id),
    )
    sessao.delete(inst)
    sessao.commit()


@rotas.post("/instrumentos/{instrumento_id}/acionar")
def acionar(
    instrumento_id: uuid.UUID,
    dados: AcionarInstrumento,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """Aciona o instrumento isoladamente, pelo encaixe — testa o tipo e é a
    base do que a Fase 4 fará durante a orquestração."""
    inst = instrumento_acessivel(sessao, usuario, instrumento_id, minimo="operador")
    tipo = encaixe.obter_tipo(inst.tipo)
    if tipo is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Tipo de instrumento desconhecido: {inst.tipo!r}",
        )
    try:
        # Resolve os segredos como na execução real (borda): inline próprio +
        # credencial da central + pool de serviço (gerar_imagem/busca_web reusam
        # a chave da org). Sem isso, "Testar" não enxergaria credencial nem pool.
        import chaves
        from orquestracao.llm import usar_chaves

        chaves_map, _ = chaves.resolver_chaves_por_time(sessao, inst.time_id)
        with usar_chaves(chaves_map):
            segredos.anexar_aos_instrumentos(sessao, [inst])
        config_efetiva = {
            **(inst.configuracao or {}),
            **getattr(inst, "segredos_decifrados", {}),
        }
        config = tipo.Config.model_validate(config_efetiva)
        args = tipo.Args.model_validate(dados.argumentos or {})
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    try:
        return tipo.executar(config, args)
    except FalhaInstrumento as e:
        # O instrumento não conseguiu operar (sistema externo recusou, config
        # incompleta…). Devolve a mensagem REAL para a tela, em vez de um 500 cru.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
