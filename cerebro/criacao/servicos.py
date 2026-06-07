"""Serviços de domínio: a porta ÚNICA e validada que escreve no TIME REAL.

No paradigma de conversa eterna, a IA criadora opera sobre as linhas reais
(Time/Agente/Instrumento/cinto/Automacao) desde o começo — não mais sobre um
rascunho JSON. Estas funções concentram a regra (líder único, validação de
config/cadeia, limpeza de referências) num só lugar, para a IA e as rotas REST
escreverem pela MESMA porta.

Transação: estas funções NÃO fazem commit — fazem `flush` para o id existir e as
leituras seguintes enxergarem. Quem chama controla a transação (a rota commita por
requisição; o laço da IA commita ao fim do turno). Erros de regra de negócio viram
`ConflitoDominio` (o chamador traduz para 409/texto).

Segurança (parede de ativação): `ativar` exige portão humano antes de agente com
ação irreversível — ver `portao_ativacao`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
import instrumentos as encaixe
import portao_ativacao
import segredos_instrumento as segredos
from modelos import Agente, AgenteInstrumento, Automacao, Instrumento, Time, Usuario
from orquestracao.cadeia import validar_cadeia

_DESTINOS_FIM = {None, "", "fim", "FIM"}


class ConflitoDominio(Exception):
    """Uma regra de negócio impediu a operação (líder duplicado, cadeia inválida,
    instrumento de outro time, etc.). Mensagem em português, pronta para o humano."""


def _audit(sessao, usuario, acao, recurso_tipo, recurso_id, organizacao_id, **detalhe):
    auditoria.registrar(
        sessao, usuario=usuario, acao=acao, recurso_tipo=recurso_tipo,
        recurso_id=recurso_id, organizacao_id=organizacao_id,
        detalhe=detalhe or None,
    )


# ─────────────────────────────── Time ───────────────────────────────

def criar_time(
    sessao: Session, organizacao_id: uuid.UUID, nome: str,
    descricao: str | None = None, *, usuario: Usuario | None = None,
) -> Time:
    time = Time(organizacao_id=organizacao_id, nome=nome, descricao=descricao)
    sessao.add(time)
    sessao.flush()
    _audit(sessao, usuario, "time.criado", "time", time.id, organizacao_id)
    return time


def editar_time(
    sessao: Session, time: Time, *, nome: str | None = None,
    descricao: str | None = None,
) -> Time:
    if nome is not None:
        time.nome = nome
    if descricao is not None:
        time.descricao = descricao
    sessao.flush()
    return time


# ────────────────────────────── Agente ──────────────────────────────

def _tem_lider(sessao: Session, time_id: uuid.UUID, ignorar: uuid.UUID | None = None) -> bool:
    consulta = select(Agente.id).where(Agente.time_id == time_id, Agente.papel == "lider")
    if ignorar is not None:
        consulta = consulta.where(Agente.id != ignorar)
    return sessao.scalars(consulta).first() is not None


def adicionar_agente(
    sessao: Session, time: Time, *, nome: str, papel: str = "agente",
    agent_md: str | None = None, skill_md: str | None = None,
    tools_md: str | None = None, soul_md: str | None = None,
    modelo_ia: str | None = None, usuario: Usuario | None = None,
) -> Agente:
    if papel not in ("lider", "agente"):
        raise ConflitoDominio("O papel precisa ser 'lider' ou 'agente'.")
    if papel == "lider" and _tem_lider(sessao, time.id):
        raise ConflitoDominio("Este time já tem um Líder. Cada time pode ter apenas um.")
    agente = Agente(
        time_id=time.id, nome=nome, papel=papel, agent_md=agent_md, skill_md=skill_md,
        tools_md=tools_md, soul_md=soul_md, modelo_ia=modelo_ia,
    )
    sessao.add(agente)
    sessao.flush()
    _audit(sessao, usuario, "agente.criado", "agente", agente.id, time.organizacao_id)
    return agente


def editar_agente(
    sessao: Session, agente: Agente, *, usuario: Usuario | None = None, **campos
) -> Agente:
    """Atualiza só os campos passados (não-None). Valida líder único se o papel mudar."""
    if campos.get("papel") == "lider" and _tem_lider(sessao, agente.time_id, ignorar=agente.id):
        raise ConflitoDominio("Este time já tem um Líder. Cada time pode ter apenas um.")
    permitidos = ("nome", "papel", "agent_md", "skill_md", "tools_md", "soul_md", "modelo_ia")
    md = ("agent_md", "skill_md", "tools_md", "soul_md")
    md_alterados = [
        c for c in md if c in campos and campos[c] is not None and getattr(agente, c) != campos[c]
    ]
    for campo in permitidos:
        if campo in campos and campos[campo] is not None:
            setattr(agente, campo, campos[campo])
    sessao.flush()
    if md_alterados:
        _audit(
            sessao, usuario, "agente.markdown_alterado", "agente", agente.id,
            auditoria.org_do_time(sessao, agente.time_id), campos=md_alterados,
        )
    return agente


def remover_agente(sessao: Session, agente: Agente, *, usuario: Usuario | None = None) -> None:
    org_id = auditoria.org_do_time(sessao, agente.time_id)
    _limpar_agente_das_cadeias(sessao, agente.time_id, str(agente.id))
    _audit(sessao, usuario, "agente.removido", "agente", agente.id, org_id)
    sessao.delete(agente)
    sessao.flush()


def _limpar_agente_das_cadeias(sessao: Session, time_id: uuid.UUID, agente_id: str) -> None:
    """Tira um agente removido das cadeias das automações do time: apaga o nó, as
    saídas que apontavam para ele, e zera o `inicio` se era ele (evita cadeia órfã)."""
    autos = sessao.scalars(select(Automacao).where(Automacao.time_id == time_id)).all()
    for auto in autos:
        cadeia = dict(auto.cadeia or {})
        nos = dict(cadeia.get("nos") or {})
        if agente_id not in nos and cadeia.get("inicio") != agente_id:
            continue
        nos.pop(agente_id, None)
        for no in nos.values():
            no["saidas"] = [
                s for s in (no.get("saidas") or []) if s.get("destino") != agente_id
            ]
        cadeia["nos"] = nos
        if cadeia.get("inicio") == agente_id:
            cadeia["inicio"] = None
        auto.cadeia = cadeia  # reatribui: o ORM detecta a troca do JSONB


# ──────────────────────────── Instrumento ───────────────────────────

def configurar_instrumento(
    sessao: Session, time: Time, *, nome: str, tipo: str, configuracao: dict | None = None,
    usuario: Usuario | None = None,
) -> tuple[Instrumento, list[str]]:
    """Cria um instrumento, separando os segredos (cifrados no cofre) da config
    pública. Devolve `(instrumento, segredos_pendentes)` — os pendentes são campos
    secretos que o consultor ainda precisa preencher no cofre."""
    try:
        config_publica, segredos_novos = encaixe.preparar_config(tipo, configuracao or {})
    except ValueError as e:
        raise ConflitoDominio(str(e))
    inst = Instrumento(time_id=time.id, nome=nome, tipo=tipo, configuracao=config_publica)
    sessao.add(inst)
    sessao.flush()
    if segredos_novos:
        segredos.salvar_segredos(sessao, inst.id, segredos_novos)
    _audit(sessao, usuario, "instrumento.criado", "instrumento", inst.id, time.organizacao_id)
    pendentes = [c for c in encaixe.campos_secretos(tipo) if c not in segredos_novos]
    return inst, pendentes


def editar_instrumento(
    sessao: Session, inst: Instrumento, *, nome: str | None = None,
    configuracao: dict | None = None, usuario: Usuario | None = None,
) -> Instrumento:
    if nome is not None:
        inst.nome = nome
    if configuracao is not None:
        try:
            config_publica, segredos_novos = encaixe.preparar_config(inst.tipo, configuracao)
        except ValueError as e:
            raise ConflitoDominio(str(e))
        inst.configuracao = config_publica
        if segredos_novos:
            segredos.salvar_segredos(sessao, inst.id, segredos_novos)
    sessao.flush()
    return inst


# ─────────────────────────────── Cinto ──────────────────────────────

def encaixar(sessao: Session, agente: Agente, instrumento: Instrumento) -> None:
    if instrumento.time_id != agente.time_id:
        raise ConflitoDominio("O instrumento é de outro time.")
    if sessao.get(AgenteInstrumento, (agente.id, instrumento.id)) is not None:
        return  # idempotente: já está no cinto
    sessao.add(AgenteInstrumento(agente_id=agente.id, instrumento_id=instrumento.id))
    sessao.flush()


def desencaixar(sessao: Session, agente_id: uuid.UUID, instrumento_id: uuid.UUID) -> None:
    vinculo = sessao.get(AgenteInstrumento, (agente_id, instrumento_id))
    if vinculo is not None:
        sessao.delete(vinculo)
        sessao.flush()


# ───────────────────────────── Automação ────────────────────────────

def _ids_agentes(sessao: Session, time_id: uuid.UUID) -> set[str]:
    return {
        str(i) for i in sessao.scalars(select(Agente.id).where(Agente.time_id == time_id)).all()
    }


def definir_automacao(
    sessao: Session, time: Time, *, nome: str, tipo_gatilho: str,
    configuracao_gatilho: dict | None = None, cadeia: dict | None = None,
    usuario: Usuario | None = None,
) -> Automacao:
    """Cria OU atualiza a automação do time (no fluxo da IA, uma por time). Valida a
    cadeia contra os agentes reais. Nasce/segue INATIVA — ativar é passo à parte."""
    cadeia = cadeia or {}
    try:
        validar_cadeia(cadeia, _ids_agentes(sessao, time.id))
    except ValueError as e:
        raise ConflitoDominio(f"Cadeia inválida: {e}")
    auto = sessao.scalars(
        select(Automacao).where(Automacao.time_id == time.id).order_by(Automacao.criado_em)
    ).first()
    if auto is None:
        auto = Automacao(
            time_id=time.id, nome=nome, tipo_gatilho=tipo_gatilho,
            configuracao_gatilho=configuracao_gatilho or {}, cadeia=cadeia, ativa=False,
        )
        sessao.add(auto)
    else:
        auto.nome = nome
        auto.tipo_gatilho = tipo_gatilho
        auto.configuracao_gatilho = configuracao_gatilho or {}
        auto.cadeia = cadeia
    sessao.flush()
    _audit(sessao, usuario, "automacao.definida", "automacao", auto.id, time.organizacao_id)
    return auto


def ativar(sessao: Session, auto: Automacao, *, usuario: Usuario | None = None) -> Automacao:
    """Liga a automação — A PAREDE: se algum agente com instrumento de ação
    irreversível não tiver portão humano antes na cadeia, recusa com `ConflitoDominio`."""
    problemas = portao_ativacao.validar(sessao, auto.time_id, auto.cadeia or {})
    if problemas:
        raise ConflitoDominio(" ".join(problemas))
    auto.ativa = True
    sessao.flush()
    _audit(sessao, usuario, "automacao.ativada", "automacao", auto.id,
           auditoria.org_do_time(sessao, auto.time_id))
    return auto


def desativar(sessao: Session, auto: Automacao, *, usuario: Usuario | None = None) -> Automacao:
    auto.ativa = False
    sessao.flush()
    _audit(sessao, usuario, "automacao.desativada", "automacao", auto.id,
           auditoria.org_do_time(sessao, auto.time_id))
    return auto
