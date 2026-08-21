"""Ferramentas de LEITURA do Batuta-MCP (Fatia 1) — a lógica por baixo das tools.

Cada função abre a própria sessão, resolve o consultor pelo `sub` do token e checa o
acesso pelos MESMOS guardas das rotas REST (`mcp_escopo`/`rotas._comum`). Reusa o que o
Batuta já tem pronto e SEM vazar segredo: `diagnostico_execucao.diagnosticar` (avisos +
ação sugerida), `memoria_agente`, `precos.resumir_uso`, o catálogo de instrumentos e a
Central de Conhecimento. Nada aqui escreve — é tudo leitura.

O `mcp_servidor` registra as tools (async, finas) que leem o `sub` do token e delegam
para estas funções numa thread (o banco síncrono não pode bloquear o loop; e o `sub`
vem por parâmetro porque o contextvar do token não atravessa a thread).
"""

import functools
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import and_, or_, select

import credenciais_cofre as cofre_cred
import diagnostico_execucao
import mcp_escopo
import memoria_agente
import precos
import tipos_credencial as tc
from chaves import PROVEDORES
from criacao.ferramentas import catalogo_de_instrumentos
from mcp_escopo import SemAcesso
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    ChaveApi,
    Conversa,
    Credencial,
    Execucao,
    Instrumento,
    MensagemConversa,
    PassoExecucao,
)
from orquestracao import grafo
from sessao import CriadorDeSessao

_ESTADOS_PROBLEMA = ("falhou", "aguardando_humano", "em_andamento", "aguardando")


def _trunc(texto, n: int = 800) -> str | None:
    if not texto:
        return None
    s = str(texto)
    return s if len(s) <= n else s[:n] + "…"


def _traduzir_acesso(e: HTTPException) -> str:
    if e.status_code == 404:
        return "Não encontrei isso entre as suas organizações/times (ou não existe)."
    if e.status_code == 403:
        return f"Você não tem permissão para isso. {e.detail}"
    return str(e.detail)


def _ferramenta(fn):
    """Abre a sessão, resolve o consultor pelo `sub` e traduz os erros de acesso em
    texto. A função recebe `(sessao, usuario, *args)` e só cuida da leitura em si."""

    @functools.wraps(fn)
    def wrapper(sub, *args):
        sessao = CriadorDeSessao()
        try:
            usuario = mcp_escopo.usuario_do_sub(sessao, sub)
            return fn(sessao, usuario, *args)
        except SemAcesso as e:
            return str(e)
        except HTTPException as e:
            return _traduzir_acesso(e)
        finally:
            sessao.close()

    return wrapper


def _uuid(valor) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(valor))
    except (ValueError, TypeError):
        return None


# ───────────────────────────── Organização / time ─────────────────────────────

@_ferramenta
def listar_organizacoes(sessao, usuario) -> str:
    orgs = mcp_escopo.organizacoes_do_usuario(sessao, usuario)
    if not orgs:
        return "Você ainda não participa de nenhuma organização no Batuta."
    linhas = [f"- {org.nome} (id {org.id}) — seu papel: {papel}" for org, papel in orgs]
    return "Suas organizações:\n" + "\n".join(linhas)


@_ferramenta
def listar_times(sessao, usuario, organizacao_id) -> str:
    org_id = None
    if organizacao_id:
        org_id = _uuid(organizacao_id)
        if org_id is None:
            return f"Id de organização inválido: {organizacao_id}."
        mcp_escopo.organizacao_acessivel(sessao, usuario, org_id)
    times = mcp_escopo.times_do_usuario(sessao, usuario, org_id)
    if not times:
        return "Nenhum time encontrado no seu escopo."
    linhas = [f"- {t.nome} (id {t.id}) — organização {t.organizacao_id}" for t in times]
    return "Times que você pode ver:\n" + "\n".join(linhas)


@_ferramenta
def descrever_time(sessao, usuario, time_id) -> str:
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    time = mcp_escopo.time_acessivel(sessao, usuario, tid)
    n = mcp_escopo.contar_agentes(sessao, time.id)
    return (
        f"Time '{time.nome}' (id {time.id}) — {n} agente(s). "
        f"Organização {time.organizacao_id}."
        + (f" {time.descricao}" if time.descricao else "")
    )


# ───────────────────────────── Agentes ─────────────────────────────

@_ferramenta
def listar_agentes(sessao, usuario, time_id) -> str:
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    time = mcp_escopo.time_acessivel(sessao, usuario, tid)
    agentes = sessao.scalars(
        select(Agente).where(Agente.time_id == time.id).order_by(Agente.criado_em)
    ).all()
    if not agentes:
        return f"O time '{time.nome}' ainda não tem agentes."
    linhas = [
        f"- {a.nome} ({a.papel}) — id {a.id}, modelo {a.modelo_ia or 'padrão'}"
        f"{', memória ligada' if a.memoria_ativa else ''}"
        for a in agentes
    ]
    return f"Agentes do time '{time.nome}':\n" + "\n".join(linhas)


@_ferramenta
def ver_agente(sessao, usuario, agente_id) -> str:
    aid = _uuid(agente_id)
    if aid is None:
        return f"Id de agente inválido: {agente_id}."
    agente = mcp_escopo.agente_acessivel(sessao, usuario, aid)
    cinto = [
        str(iid)
        for (iid,) in sessao.execute(
            select(AgenteInstrumento.instrumento_id).where(
                AgenteInstrumento.agente_id == agente.id
            )
        ).all()
    ]
    return json.dumps(
        {
            "id": str(agente.id),
            "nome": agente.nome,
            "papel": agente.papel,
            "modelo_ia": agente.modelo_ia,
            "memoria_ativa": agente.memoria_ativa,
            "agent_md": agente.agent_md,
            "skill_md": agente.skill_md,
            "tools_md": agente.tools_md,
            "soul_md": agente.soul_md,
            "cinto": cinto,
        },
        ensure_ascii=False,
    )


@_ferramenta
def ver_memoria_agente(sessao, usuario, agente_id) -> str:
    aid = _uuid(agente_id)
    if aid is None:
        return f"Id de agente inválido: {agente_id}."
    agente = mcp_escopo.agente_acessivel(sessao, usuario, aid)
    if not agente.memoria_ativa:
        return f"O agente '{agente.nome}' está com a memória desligada."
    fichas = memoria_agente.pesquisar(sessao, agente.id)
    if not fichas:
        return f"O agente '{agente.nome}' ainda não aprendeu nada (memória vazia)."
    return json.dumps(
        {"agente": agente.nome, "memorias": fichas}, ensure_ascii=False
    )


# ───────────────────────────── Automações ─────────────────────────────

@_ferramenta
def listar_automacoes(sessao, usuario, time_id) -> str:
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    time = mcp_escopo.time_acessivel(sessao, usuario, tid)
    autos = sessao.scalars(
        select(Automacao).where(Automacao.time_id == time.id).order_by(Automacao.criado_em)
    ).all()
    if not autos:
        return f"O time '{time.nome}' ainda não tem automações."
    linhas = [
        f"- {a.nome} (id {a.id}) — gatilho {a.tipo_gatilho}, "
        f"{'ATIVA' if a.ativa else 'inativa'}"
        for a in autos
    ]
    return f"Automações do time '{time.nome}':\n" + "\n".join(linhas)


@_ferramenta
def ver_automacao(sessao, usuario, automacao_id) -> str:
    aid = _uuid(automacao_id)
    if aid is None:
        return f"Id de automação inválido: {automacao_id}."
    auto = mcp_escopo.automacao_acessivel(sessao, usuario, aid)
    return json.dumps(
        {
            "id": str(auto.id),
            "nome": auto.nome,
            "tipo_gatilho": auto.tipo_gatilho,
            "configuracao_gatilho": auto.configuracao_gatilho,
            "cadeia": grafo.normalizar(auto.cadeia or {}),
            "ativa": auto.ativa,
        },
        ensure_ascii=False,
    )


# ───────────────────────────── Execuções / diagnóstico ─────────────────────────────

@_ferramenta
def listar_execucoes(sessao, usuario, time_id, automacao_id, apenas_problemas, limite) -> str:
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    time = mcp_escopo.time_acessivel(sessao, usuario, tid)
    q = (
        select(Execucao, Automacao.nome)
        .join(Automacao, Automacao.id == Execucao.automacao_id)
        .where(Automacao.time_id == time.id)
    )
    if automacao_id:
        aid = _uuid(automacao_id)
        if aid is None:
            return f"Id de automação inválido: {automacao_id}."
        q = q.where(Execucao.automacao_id == aid)
    if apenas_problemas:
        q = q.where(Execucao.estado.in_(_ESTADOS_PROBLEMA))
    q = q.order_by(Execucao.criado_em.desc()).limit(max(1, min(int(limite or 10), 30)))
    itens = [
        {
            "execucao_id": str(ex.id),
            "automacao": nome,
            "estado": ex.estado,
            "quando": ex.criado_em.isoformat() if ex.criado_em else None,
            "resumo": diagnostico_execucao.resumo_estado(ex.estado, ex.resultado),
        }
        for ex, nome in sessao.execute(q).all()
    ]
    if not itens:
        return "Nenhuma execução encontrada com esse filtro."
    return json.dumps({"execucoes": itens}, ensure_ascii=False)


@_ferramenta
def diagnosticar_execucao(sessao, usuario, execucao_id) -> str:
    eid = _uuid(execucao_id)
    if eid is None:
        return f"Id de execução inválido: {execucao_id}."
    # Escopo: execucao_acessivel resolve a org pela automação/conversa e checa o papel.
    mcp_escopo.execucao_acessivel(sessao, usuario, eid)
    diag = diagnostico_execucao.diagnosticar(sessao, eid)
    return json.dumps(diag, ensure_ascii=False)


# ───────────────────────────── Conversas (mensageria) ─────────────────────────────

@_ferramenta
def listar_conversas(sessao, usuario, time_id, estado) -> str:
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    mcp_escopo.time_acessivel(sessao, usuario, tid)
    consulta = (
        select(Conversa)
        .join(Instrumento, Instrumento.id == Conversa.instrumento_id)
        .where(Instrumento.time_id == tid)
        .order_by(Conversa.atualizado_em.desc())
        .limit(40)
    )
    if estado:
        consulta = consulta.where(Conversa.estado == estado)
    conversas = sessao.scalars(consulta).all()
    if not conversas:
        return "Nenhuma conversa de mensageria neste time."
    linhas = [
        f"- {c.contato_nome or c.contato_chave} ({c.canal}) — estado {c.estado}, "
        f"{c.turnos or 0} turno(s), id {c.id}"
        for c in conversas
    ]
    return "Conversas do time (mensageria):\n" + "\n".join(linhas)


@_ferramenta
def ler_conversa(sessao, usuario, conversa_id) -> str:
    cid = _uuid(conversa_id)
    if cid is None:
        return f"Id de conversa inválido: {conversa_id}."
    conversa = mcp_escopo.conversa_acessivel(sessao, usuario, cid)
    mensagens = sessao.scalars(
        select(MensagemConversa)
        .where(MensagemConversa.conversa_id == conversa.id)
        .order_by(MensagemConversa.criado_em)
    ).all()
    thread = [
        {
            "papel": m.papel,
            "conteudo": _trunc(m.conteudo, 1200),
            "quando": m.criado_em.isoformat() if m.criado_em else None,
        }
        for m in mensagens[-40:]
    ]
    return json.dumps(
        {
            "contato": conversa.contato_nome or conversa.contato_chave,
            "canal": conversa.canal,
            "estado": conversa.estado,
            "mensagens": thread,
        },
        ensure_ascii=False,
    )


# ───────────────────────────── Custo ─────────────────────────────

@_ferramenta
def ver_uso(sessao, usuario, time_id) -> str:
    tid = _uuid(time_id)
    if tid is None:
        return f"Id de time inválido: {time_id}."
    time = mcp_escopo.time_acessivel(sessao, usuario, tid)
    passos = sessao.scalars(
        select(PassoExecucao)
        .join(Execucao, Execucao.id == PassoExecucao.execucao_id)
        .join(Automacao, Automacao.id == Execucao.automacao_id)
        .where(Automacao.time_id == time.id)
    ).all()
    mensagens = sessao.scalars(
        select(MensagemConversa)
        .join(Conversa, Conversa.id == MensagemConversa.conversa_id)
        .join(Instrumento, Instrumento.id == Conversa.instrumento_id)
        .where(Instrumento.time_id == time.id)
    ).all()
    resumo = precos.resumir_uso(passos=passos, mensagens=mensagens)
    return json.dumps(
        {
            "time": time.nome,
            "custo_usd": round(resumo.get("custo_usd", 0.0), 4),
            "tokens_entrada": resumo.get("tokens_entrada", 0),
            "tokens_saida": resumo.get("tokens_saida", 0),
            "por_categoria": resumo.get("por_categoria", {}),
            "observacao": "Execuções + mensageria deste time. O custo da IA criadora é por organização.",
        },
        ensure_ascii=False,
    )


# ───────────────────────────── Catálogo / conhecimento ─────────────────────────────

@_ferramenta
def listar_tipos_instrumento(sessao, usuario) -> str:
    # Catálogo é global; basta estar autenticado (o `_ferramenta` já garante o usuário).
    return json.dumps(catalogo_de_instrumentos(), ensure_ascii=False)


@_ferramenta
def listar_tipos_credencial(sessao, usuario) -> str:
    # Catálogo global de tipos de credencial (basta estar autenticado). Sem segredo.
    tipos = [
        {
            "tipo": t.tipo,
            "nome": t.nome_exibicao,
            "campos": [
                {"nome": c.nome, "rotulo": c.rotulo, "secreto": c.secreto}
                for c in t.campos
            ],
        }
        for t in tc.tipos_disponiveis()
    ]
    return json.dumps({"tipos_credencial": tipos}, ensure_ascii=False)


@_ferramenta
def listar_credenciais(sessao, usuario, organizacao_id) -> str:
    org_id = _uuid(organizacao_id)
    if org_id is None:
        return f"Id de organização inválido: {organizacao_id}."
    mcp_escopo.organizacao_acessivel(sessao, usuario, org_id, "operador")
    # As da organização + as da consultoria marcadas como compartilháveis (como a tela).
    linhas = sessao.scalars(
        select(Credencial)
        .where(
            or_(
                Credencial.organizacao_id == org_id,
                and_(
                    Credencial.organizacao_id.is_(None),
                    Credencial.compartilhavel.is_(True),
                ),
            )
        )
        .order_by(Credencial.nome)
    ).all()
    if not linhas:
        return "Nenhuma credencial nesta organização."
    itens = [
        {
            "id": str(c.id),
            "nome": c.nome,
            "tipo": c.tipo,
            "da_consultoria": c.organizacao_id is None,
            "usado_por": cofre_cred.usado_por(sessao, c.id),
            "resumo": c.resumo,  # já mascarado (segredos = só últimos 4)
            "preenchida": bool(c.dados_cifrado),
        }
        for c in linhas
    ]
    return json.dumps({"credenciais": itens}, ensure_ascii=False)


@_ferramenta
def ver_chaves_de_ia(sessao, usuario, organizacao_id) -> str:
    org_id = _uuid(organizacao_id)
    if org_id is None:
        return f"Id de organização inválido: {organizacao_id}."
    mcp_escopo.organizacao_acessivel(sessao, usuario, org_id)  # observador
    # Existência de chave (da org OU da consultoria-mãe), ativa — SEM decifrar: o MCP não
    # precisa da chave-mestra do cofre (least-privilege). Só booleanos, nenhum segredo.
    tem = set(
        sessao.scalars(
            select(ChaveApi.provedor).where(
                or_(
                    ChaveApi.organizacao_id == org_id,
                    ChaveApi.organizacao_id.is_(None),
                ),
                ChaveApi.ativa.is_(True),
            )
        ).all()
    )
    mapa = {provedor: (provedor in tem) for provedor in PROVEDORES}
    return json.dumps({"provedores_com_chave": mapa}, ensure_ascii=False)


@_ferramenta
def consultar_conhecimento(sessao, usuario, topico) -> str:
    import conhecimento

    achados = conhecimento.buscar((topico or "").strip(), limite=3)
    if not achados:
        return (
            "Nada encontrado na Central de Conhecimento para esse tópico. "
            "Responda pelo que sabe, com honestidade — não invente regras."
        )
    return json.dumps(
        {
            "capitulos": [
                {"titulo": c.titulo, "slug": c.slug, "conteudo": c.corpo}
                for c in achados
            ]
        },
        ensure_ascii=False,
    )
