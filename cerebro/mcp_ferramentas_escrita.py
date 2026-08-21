"""Ferramentas de ESCRITA do Batuta-MCP (Fatia 2 — criação núcleo).

O Claude do consultor passa a MONTAR de verdade: criar/editar times, agentes,
instrumentos (inclusive conector a partir de doc de API), montar automações e ativar.
Tudo reusa a MESMA porta de escrita validada do Batuta — `criacao/servicos.py` (a mesma
por onde a IA criadora e as rotas REST escrevem) — e é escopado por papel: a maioria
exige `operador`; criar uma organização/time novo exige `admin`.

Padrão: o decorator `_ferramenta_escrita` abre a sessão, resolve o consultor pelo `sub`,
executa a função (que chama `servicos.*`, que só dá `flush`), COMITA no sucesso e faz
ROLLBACK + mensagem humana em qualquer erro de domínio/acesso (`ConflitoDominio`,
`FalhaInstrumento`, 403/404). O cérebro (motor de orquestração) fica intocado.
"""

import functools
import json
import uuid

from fastapi import HTTPException

import mcp_escopo
import segredos_instrumento as segredos
from criacao import servicos
from criacao.ferramentas import _validar_gatilho
from criacao.servicos import ConflitoDominio
from instrumentos.base import FalhaInstrumento
from mcp_escopo import SemAcesso
from mcp_ferramentas import _traduzir_acesso, _uuid
from modelos import Instrumento, Time
from sessao import CriadorDeSessao


def _ferramenta_escrita(fn):
    """Sessão + identidade + commit/rollback + tradução de erro, numa fonte só. A função
    recebe `(sessao, usuario, *args)`, chama `servicos.*` (que só faz flush) e devolve a
    mensagem; o commit é do decorator."""

    @functools.wraps(fn)
    def wrapper(sub, *args):
        sessao = CriadorDeSessao()
        try:
            usuario = mcp_escopo.usuario_do_sub(sessao, sub)
            resultado = fn(sessao, usuario, *args)
            sessao.commit()
            return resultado
        except SemAcesso as e:
            sessao.rollback()
            return str(e)
        except HTTPException as e:
            sessao.rollback()
            return _traduzir_acesso(e)
        except (ConflitoDominio, FalhaInstrumento) as e:
            sessao.rollback()
            return f"Não deu para fazer: {e}"
        finally:
            sessao.close()

    return wrapper


def _campos(**kv) -> dict:
    """Só os campos realmente informados (não-None), para edições parciais."""
    return {k: v for k, v in kv.items() if v is not None}


# ───────────────────────────── Times ─────────────────────────────

@_ferramenta_escrita
def criar_time(sessao, usuario, organizacao_id, nome, descricao) -> str:
    org_id = _uuid(organizacao_id)
    if org_id is None:
        return f"Id de organização inválido: {organizacao_id}."
    nome = (nome or "").strip()
    if not nome:
        return "Dê um nome ao time."
    # Criar time é ação de admin da organização.
    mcp_escopo.organizacao_acessivel(sessao, usuario, org_id, "admin")
    time = servicos.criar_time(sessao, org_id, nome, (descricao or None), usuario=usuario)
    return f"Time '{time.nome}' criado (id {time.id})."


@_ferramenta_escrita
def editar_time(sessao, usuario, time_id, nome, descricao) -> str:
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    time = mcp_escopo.time_acessivel(sessao, usuario, tid, "operador")
    campos = _campos(nome=(nome or None), descricao=descricao)
    if not campos:
        return "Nada para mudar — passe um novo nome e/ou descrição."
    servicos.editar_time(sessao, time, **campos)
    return f"Time '{time.nome}' atualizado."


# ───────────────────────────── Agentes ─────────────────────────────

@_ferramenta_escrita
def criar_agente(sessao, usuario, time_id, nome, papel, agent_md, skill_md, tools_md, soul_md, modelo_ia) -> str:
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    nome = (nome or "").strip()
    if not nome:
        return "Dê um nome ao agente."
    time = mcp_escopo.time_acessivel(sessao, usuario, tid, "operador")
    agente = servicos.adicionar_agente(
        sessao, time, nome=nome, papel=(papel or "agente"),
        agent_md=agent_md, skill_md=skill_md, tools_md=tools_md, soul_md=soul_md,
        modelo_ia=modelo_ia, usuario=usuario,
    )
    return f"Agente '{agente.nome}' criado no time '{time.nome}' (id {agente.id}, papel {agente.papel})."


@_ferramenta_escrita
def editar_agente(sessao, usuario, agente_id, nome, papel, agent_md, skill_md, tools_md, soul_md, modelo_ia) -> str:
    aid = _uuid(agente_id)
    if aid is None:
        return f"Id de agente inválido: {agente_id}."
    agente = mcp_escopo.agente_acessivel(sessao, usuario, aid, "operador")
    campos = _campos(
        nome=(nome or None), papel=papel, agent_md=agent_md, skill_md=skill_md,
        tools_md=tools_md, soul_md=soul_md, modelo_ia=modelo_ia,
    )
    if not campos:
        return "Nada para mudar — passe algum campo (nome, papel ou um dos markdowns)."
    servicos.editar_agente(sessao, agente, usuario=usuario, **campos)
    return f"Agente '{agente.nome}' atualizado (id {agente.id})."


@_ferramenta_escrita
def remover_agente(sessao, usuario, agente_id) -> str:
    aid = _uuid(agente_id)
    if aid is None:
        return f"Id de agente inválido: {agente_id}."
    agente = mcp_escopo.agente_acessivel(sessao, usuario, aid, "operador")
    nome = agente.nome
    servicos.remover_agente(sessao, agente, usuario=usuario)
    return f"Agente '{nome}' removido."


# ───────────────────────────── Instrumentos ─────────────────────────────

@_ferramenta_escrita
def configurar_instrumento(sessao, usuario, time_id, nome, tipo, configuracao) -> str:
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    nome = (nome or "").strip()
    if not nome or not tipo:
        return "Instrumento precisa de nome e tipo (veja os tipos em listar_tipos_instrumento)."
    time = mcp_escopo.time_acessivel(sessao, usuario, tid, "operador")
    inst, pendentes = servicos.configurar_instrumento(
        sessao, time, nome=nome, tipo=tipo, configuracao=(configuracao or {}), usuario=usuario
    )
    return json.dumps(
        {
            "mensagem": f"Instrumento '{inst.nome}' criado.",
            "id": str(inst.id),
            "segredos_pendentes": pendentes,
            "lembrete": (
                "Peça ao consultor para colar os segredos pendentes no cofre (você não pluga token)."
                if pendentes else "Sem segredos pendentes."
            ),
        },
        ensure_ascii=False,
    )


@_ferramenta_escrita
def editar_instrumento(sessao, usuario, instrumento_id, nome, configuracao) -> str:
    iid = _uuid(instrumento_id)
    if iid is None:
        return f"Id de instrumento inválido: {instrumento_id}."
    inst = mcp_escopo.instrumento_acessivel(sessao, usuario, iid, "operador")
    campos = _campos(nome=(nome or None), configuracao=configuracao)
    if not campos:
        return "Nada para mudar — passe um novo nome e/ou configuração."
    servicos.editar_instrumento(sessao, inst, usuario=usuario, **campos)
    return f"Instrumento '{inst.nome}' atualizado."


@_ferramenta_escrita
def montar_conector(sessao, usuario, time_id, conector, conector_id) -> str:
    conector = conector or {}
    nome = str(conector.get("nome") or "").strip()
    dados = {k: v for k, v in conector.items() if k != "nome"}
    dados.pop("auth_segredo", None)  # a IA nunca pluga o token (fica pendente no cofre)
    auth = str(dados.get("auth_tipo") or "nenhuma")
    lembrete = (
        "Peça ao consultor para colar o token no cofre; depois teste com testar_operacao_conector."
        if auth != "nenhuma"
        else "Sem autenticação. Teste as operações com testar_operacao_conector."
    )
    if conector_id:
        cid = _uuid(conector_id)
        inst = mcp_escopo.instrumento_acessivel(sessao, usuario, cid, "operador") if cid else None
        if inst is None or inst.tipo != "conector":
            return f"Não há conector com id {conector_id} no seu escopo."
        servicos.editar_instrumento(sessao, inst, nome=(nome or None), configuracao=dados, usuario=usuario)
        return json.dumps(
            {"mensagem": f"Conector '{inst.nome}' atualizado.", "id": str(inst.id), "lembrete": lembrete},
            ensure_ascii=False,
        )
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    if not nome:
        return "O conector precisa de um nome (campo 'nome' no objeto)."
    time = mcp_escopo.time_acessivel(sessao, usuario, tid, "operador")
    inst, pendentes = servicos.configurar_instrumento(
        sessao, time, nome=nome, tipo="conector", configuracao=dados, usuario=usuario
    )
    if auth == "nenhuma":
        pendentes = [p for p in pendentes if p != "auth_segredo"]
    return json.dumps(
        {"mensagem": f"Conector '{nome}' criado.", "id": str(inst.id),
         "segredos_pendentes": pendentes, "lembrete": lembrete},
        ensure_ascii=False,
    )


@_ferramenta_escrita
def testar_operacao_conector(sessao, usuario, conector_id, operacao, valores) -> str:
    cid = _uuid(conector_id)
    inst = mcp_escopo.instrumento_acessivel(sessao, usuario, cid, "operador") if cid else None
    if inst is None or inst.tipo != "conector":
        return f"Não há conector com id {conector_id} no seu escopo."
    from instrumentos.base import obter_tipo

    tipo = obter_tipo("conector")
    secretos = segredos.decifrar(sessao, inst.id)
    config = tipo.Config.model_validate({**(inst.configuracao or {}), **secretos})
    resultado = tipo.testar_operacao(config, operacao, valores or {})  # FalhaInstrumento → decorator
    return json.dumps({"mensagem": "Teste executado.", "resultado": resultado}, ensure_ascii=False)


# ───────────────────────────── Cinto (instrumento ↔ agente) ─────────────────────────────

@_ferramenta_escrita
def encaixar_instrumento(sessao, usuario, agente_id, instrumento_id) -> str:
    aid = _uuid(agente_id)
    if aid is None:
        return f"Id de agente inválido: {agente_id}."
    agente = mcp_escopo.agente_acessivel(sessao, usuario, aid, "operador")
    iid = _uuid(instrumento_id)
    inst = sessao.get(Instrumento, iid) if iid else None
    if inst is None:
        return f"Não há instrumento com id {instrumento_id}."
    servicos.encaixar(sessao, agente, inst)  # ConflitoDominio se de outro time → decorator
    return f"Instrumento '{inst.nome}' encaixado no cinto de '{agente.nome}'."


@_ferramenta_escrita
def desencaixar_instrumento(sessao, usuario, agente_id, instrumento_id) -> str:
    aid = _uuid(agente_id)
    if aid is None:
        return f"Id de agente inválido: {agente_id}."
    agente = mcp_escopo.agente_acessivel(sessao, usuario, aid, "operador")
    iid = _uuid(instrumento_id)
    if iid is None:
        return f"Id de instrumento inválido: {instrumento_id}."
    servicos.desencaixar(sessao, agente.id, iid)
    return "Instrumento tirado do cinto."


# ───────────────────────────── Automações ─────────────────────────────

@_ferramenta_escrita
def criar_automacao(sessao, usuario, time_id, nome) -> str:
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    nome = (nome or "").strip()
    if not nome:
        return "Dê um nome à automação."
    time = mcp_escopo.time_acessivel(sessao, usuario, tid, "operador")
    auto = servicos.criar_automacao(sessao, time, nome=nome, usuario=usuario)
    return f"Automação '{auto.nome}' criada (id {auto.id})."


def _auto_e_time(sessao, usuario, automacao_id):
    """Resolve a automação pelo escopo (operador) e devolve (auto, time)."""
    aid = _uuid(automacao_id)
    if aid is None:
        return None, None
    auto = mcp_escopo.automacao_acessivel(sessao, usuario, aid, "operador")
    time = sessao.get(Time, auto.time_id)
    return auto, time


@_ferramenta_escrita
def renomear_automacao(sessao, usuario, automacao_id, nome) -> str:
    auto, time = _auto_e_time(sessao, usuario, automacao_id)
    if auto is None:
        return f"Id de automação inválido: {automacao_id}."
    servicos.renomear_automacao(sessao, time, automacao_id=auto.id, nome=nome, usuario=usuario)
    return f"Automação renomeada para '{(nome or '').strip()}'."


@_ferramenta_escrita
def montar_cadeia(sessao, usuario, automacao_id, cadeia) -> str:
    auto, time = _auto_e_time(sessao, usuario, automacao_id)
    if auto is None:
        return f"Id de automação inválido: {automacao_id}."
    servicos.definir_cadeia(sessao, time, cadeia or {}, automacao_id=auto.id, usuario=usuario)
    return f"Cadeia (fluxo) da automação '{auto.nome}' montada."


@_ferramenta_escrita
def definir_gatilho(sessao, usuario, automacao_id, tipo_gatilho, configuracao_gatilho) -> str:
    auto, time = _auto_e_time(sessao, usuario, automacao_id)
    if auto is None:
        return f"Id de automação inválido: {automacao_id}."
    config = configuracao_gatilho or {}
    erro = _validar_gatilho(tipo_gatilho, config)
    if erro:
        return erro
    servicos.definir_gatilho(
        sessao, time, tipo_gatilho=tipo_gatilho, configuracao_gatilho=config,
        automacao_id=auto.id, usuario=usuario,
    )
    nota = (
        " (o agendamento entra no relógio em até ~1 minuto)"
        if tipo_gatilho == "agendamento" else ""
    )
    return f"Gatilho '{tipo_gatilho}' definido na automação '{auto.nome}'.{nota}"


@_ferramenta_escrita
def ativar_time(sessao, usuario, automacao_id) -> str:
    aid = _uuid(automacao_id)
    if aid is None:
        return f"Id de automação inválido: {automacao_id}."
    auto = mcp_escopo.automacao_acessivel(sessao, usuario, aid, "operador")
    # servicos.ativar levanta ConflitoDominio (com os problemas da parede) → decorator.
    servicos.ativar(sessao, auto, usuario=usuario)
    return f"Automação '{auto.nome}' ativada (passa a poder disparar)."


@_ferramenta_escrita
def desativar_time(sessao, usuario, automacao_id) -> str:
    aid = _uuid(automacao_id)
    if aid is None:
        return f"Id de automação inválido: {automacao_id}."
    auto = mcp_escopo.automacao_acessivel(sessao, usuario, aid, "operador")
    servicos.desativar(sessao, auto, usuario=usuario)
    return f"Automação '{auto.nome}' desativada (desligada)."
