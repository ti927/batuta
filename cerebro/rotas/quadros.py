"""Endpoints dos QUADROS do cérebro da organização — a tela (Entrega 4 do
docs/CEREBRO-PLANO.md).

Tudo passa pelo MESMO `quadros.servico` que o agente, a IA criadora e o MCP usam.
Papéis (os guardas de sempre): observador lê; operador cria/altera quadros e grava/
edita/apaga linhas; admin exclui quadro.

Uma RECUSA do Batuta (dado que não serve, filtro inválido, limite) volta com status 200
e `{ok: false, erro, detalhes}` — é resposta para a pessoa ler e corrigir, com a lista
das linhas, e não um erro técnico. Status de erro fica para acesso (403) e quadro que
não existe (404).
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

import auditoria
from auth import usuario_atual
from modelos import Agente, Automacao, Execucao, Usuario
from quadros import importacao
from quadros import servico as qs
from quadros.servico import Autor, ErroQuadro
from rotas._comum import organizacao_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["quadros"])


# ───────────────────────────── corpos ─────────────────────────────


class QuadroCriar(BaseModel):
    nome: str
    colunas: list[dict]
    chave: list[str] | None = None
    descricao: str | None = None
    simular: bool = False


class EstruturaAlterar(BaseModel):
    operacoes: list[dict]
    simular: bool = False


class Consulta(BaseModel):
    filtros: list[dict] | None = None
    ordem: list[str] | None = None
    busca: str | None = None
    limite: int | None = None
    deslocamento: int = 0
    so_o_mais_recente_de: str | None = None
    execucao_id: str | None = None


class LinhasGravar(BaseModel):
    linhas: list[dict]
    modo: str = "acrescentar"


class LinhaEditar(BaseModel):
    campos: dict[str, Any]


class LinhasApagar(BaseModel):
    ids: list[str] | None = None
    execucao_id: str | None = None
    simular: bool = False


class Csv(BaseModel):
    csv: str
    mapeamento: dict[str, str | None] | None = None


class Importar(Csv):
    ignorar_colunas_extras: bool = False
    pular_linhas_com_problema: bool = False
    modo: str = "acrescentar"


class Exportar(BaseModel):
    filtros: list[dict] | None = None
    busca: str | None = None


# ───────────────────────────── apoio ─────────────────────────────


def _recusa(e: ErroQuadro) -> dict:
    corpo: dict = {"ok": False, "erro": e.mensagem}
    if e.detalhes:
        corpo["detalhes"] = e.detalhes
    return corpo


def _quadro_ou_404(sessao, org_id, quadro_id):
    try:
        return qs.obter_quadro(sessao, org_id, quadro_id)
    except ErroQuadro:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quadro não encontrado") from None


def _autor(usuario: Usuario) -> Autor:
    return Autor(origem="pessoa", usuario_id=usuario.id)


def _nomes_do_carimbo(sessao, linhas: list[dict]) -> None:
    """Troca os ids do carimbo por nomes que a pessoa reconhece (agente, pessoa,
    automação da execução) — em lote, sem uma consulta por linha."""
    ag_ids, us_ids, ex_ids = set(), set(), set()
    for ln in linhas:
        c = ln.get("carimbo") or ln
        for chave, alvo in (("agente_id", ag_ids), ("usuario_id", us_ids), ("execucao_id", ex_ids)):
            if c.get(chave):
                alvo.add(uuid.UUID(c[chave]))
    agentes = dict(sessao.execute(select(Agente.id, Agente.nome).where(Agente.id.in_(ag_ids))).all()) if ag_ids else {}
    pessoas = dict(sessao.execute(select(Usuario.id, Usuario.nome).where(Usuario.id.in_(us_ids))).all()) if us_ids else {}
    automacoes = dict(
        sessao.execute(
            select(Execucao.id, Automacao.nome)
            .outerjoin(Automacao, Automacao.id == Execucao.automacao_id)
            .where(Execucao.id.in_(ex_ids))
        ).all()
    ) if ex_ids else {}
    for ln in linhas:
        c = ln.get("carimbo") or ln
        if c.get("agente_id"):
            c["agente_nome"] = agentes.get(uuid.UUID(c["agente_id"]))
        if c.get("usuario_id"):
            c["usuario_nome"] = pessoas.get(uuid.UUID(c["usuario_id"]))
        if c.get("execucao_id"):
            c["automacao_nome"] = automacoes.get(uuid.UUID(c["execucao_id"]))


def _auditar(sessao, usuario, acao, q, org_id, detalhe=None):
    auditoria.registrar(
        sessao, usuario=usuario, acao=acao, recurso_tipo="quadro", recurso_id=q.id,
        organizacao_id=org_id, detalhe=detalhe,
    )


# ───────────────────────────── quadros ─────────────────────────────


@rotas.get("/organizacoes/{org_id}/quadros")
def listar(
    org_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id)
    quadros = qs.listar_quadros(sessao, org_id)
    resumo = qs.resumo_das_linhas(sessao, [q.id for q in quadros])
    usos = qs.quem_usa_por_quadro(sessao, org_id)
    return [
        {
            "id": str(q.id),
            "nome": q.nome,
            "descricao": q.descricao,
            "colunas": [c["nome"] for c in q.colunas or []],
            "linhas": resumo[q.id]["linhas"],
            "ultima_gravacao": resumo[q.id]["ultima_gravacao"],
            "criado_em": q.criado_em,
            "usado_por": usos.get(str(q.id), []),
        }
        for q in quadros
    ]


@rotas.post("/organizacoes/{org_id}/quadros")
def criar(
    org_id: uuid.UUID,
    dados: QuadroCriar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id, minimo="operador")
    try:
        r = qs.criar_quadro(
            sessao, org_id, nome=dados.nome, colunas=dados.colunas, chave=dados.chave,
            descricao=dados.descricao, criado_por_id=usuario.id, simular=dados.simular,
        )
    except ErroQuadro as e:
        return _recusa(e)
    if not dados.simular:
        _auditar(sessao, usuario, "quadro.criado", qs.obter_quadro(sessao, org_id, r["quadro_id"]), org_id)
        sessao.commit()
    return {"ok": True, **r}


@rotas.post("/organizacoes/{org_id}/quadros/sugerir-colunas")
def sugerir_colunas(
    org_id: uuid.UUID,
    dados: Csv,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id, minimo="operador")
    try:
        return {"ok": True, **importacao.sugerir_colunas(dados.csv)}
    except ErroQuadro as e:
        return _recusa(e)


@rotas.get("/organizacoes/{org_id}/quadros/{quadro_id}")
def ver(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id)
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    return {
        "quadro": qs.descrever_quadro(q, qs.contar_linhas(sessao, q.id)),
        "usado_por": qs.quem_usa(sessao, org_id, q.id),
        "execucoes_recentes": qs.execucoes_que_gravaram(sessao, org_id, q.id),
    }


@rotas.post("/organizacoes/{org_id}/quadros/{quadro_id}/estrutura")
def alterar(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    dados: EstruturaAlterar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id, minimo="operador")
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    try:
        r = qs.alterar_quadro(sessao, org_id, q.id, dados.operacoes, simular=dados.simular)
    except ErroQuadro as e:
        return _recusa(e)
    if not dados.simular:
        _auditar(sessao, usuario, "quadro.estrutura_alterada", q, org_id, {"feitas": r["feitas"]})
        sessao.commit()
    return {"ok": True, **r}


@rotas.delete("/organizacoes/{org_id}/quadros/{quadro_id}")
def excluir(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    simular: bool = False,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id, minimo="admin")
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    if not simular:
        _auditar(sessao, usuario, "quadro.excluido", q, org_id, {"nome": q.nome})
    r = qs.excluir_quadro(sessao, org_id, q.id, simular=simular)
    if not simular:
        sessao.commit()
    return {"ok": True, **r}


# ───────────────────────────── linhas ─────────────────────────────


@rotas.post("/organizacoes/{org_id}/quadros/{quadro_id}/consulta")
def consultar(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    dados: Consulta,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id)
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    try:
        r = qs.consultar(
            sessao, org_id, q.id, filtros=dados.filtros, ordem=dados.ordem, busca=dados.busca,
            limite=dados.limite, deslocamento=dados.deslocamento,
            so_o_mais_recente_de=dados.so_o_mais_recente_de, execucao_id=dados.execucao_id,
        )
    except ErroQuadro as e:
        return _recusa(e)
    _nomes_do_carimbo(sessao, r["linhas"])
    return {"ok": True, **r}


@rotas.post("/organizacoes/{org_id}/quadros/{quadro_id}/linhas")
def gravar(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    dados: LinhasGravar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id, minimo="operador")
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    try:
        r = qs.gravar_linhas(sessao, org_id, q.id, dados.linhas, autor=_autor(usuario), modo=dados.modo)
    except ErroQuadro as e:
        return _recusa(e)
    sessao.commit()
    return {"ok": True, **r}


@rotas.patch("/organizacoes/{org_id}/quadros/{quadro_id}/linhas/{linha_id}")
def editar_linha(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    linha_id: uuid.UUID,
    dados: LinhaEditar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id, minimo="operador")
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    try:
        r = qs.editar_linhas(
            sessao, org_id, q.id, campos=dados.campos, ids=[str(linha_id)], autor=_autor(usuario)
        )
    except ErroQuadro as e:
        return _recusa(e)
    if r["encontradas"] == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Linha não encontrada")
    sessao.commit()
    return {"ok": True, **r}


@rotas.post("/organizacoes/{org_id}/quadros/{quadro_id}/linhas/apagar")
def apagar_linhas(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    dados: LinhasApagar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id, minimo="operador")
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    try:
        r = qs.apagar_linhas(
            sessao, org_id, q.id, ids=dados.ids, execucao_id=dados.execucao_id,
            autor=_autor(usuario), simular=dados.simular,
        )
    except ErroQuadro as e:
        return _recusa(e)
    if not dados.simular:
        _auditar(sessao, usuario, "quadro.linhas_apagadas", q, org_id,
                 {"apagadas": r["apagadas"], "execucao_id": dados.execucao_id})
        sessao.commit()
    return {"ok": True, **r}


@rotas.get("/organizacoes/{org_id}/quadros/{quadro_id}/linhas/{linha_id}/historico")
def historico(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    linha_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id)
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    r = qs.historico_linha(sessao, org_id, q.id, linha_id)
    _nomes_do_carimbo(sessao, r["alteracoes"])
    return r


# ───────────────────────────── importar / exportar ─────────────────────────────


@rotas.post("/organizacoes/{org_id}/quadros/{quadro_id}/importar/previa")
def previa_importacao(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    dados: Csv,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id, minimo="operador")
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    try:
        return {"ok": True, **importacao.previa(sessao, org_id, q.id, dados.csv, mapeamento=dados.mapeamento)}
    except ErroQuadro as e:
        return _recusa(e)


@rotas.post("/organizacoes/{org_id}/quadros/{quadro_id}/importar")
def importar(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    dados: Importar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    organizacao_acessivel(sessao, usuario, org_id, minimo="operador")
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    try:
        r = importacao.importar_csv(
            sessao, org_id, q.id, dados.csv,
            autor=Autor(origem="importacao", usuario_id=usuario.id),
            mapeamento=dados.mapeamento, ignorar_colunas_extras=dados.ignorar_colunas_extras,
            pular_linhas_com_problema=dados.pular_linhas_com_problema, modo=dados.modo,
        )
    except ErroQuadro as e:
        return _recusa(e)
    _auditar(sessao, usuario, "quadro.importado", q, org_id,
             {"criadas": r["criadas"], "puladas": len(r["linhas_puladas"])})
    sessao.commit()
    return {"ok": True, **r}


@rotas.post("/organizacoes/{org_id}/quadros/{quadro_id}/exportar")
def exportar(
    org_id: uuid.UUID,
    quadro_id: uuid.UUID,
    dados: Exportar,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    """O quadro em CSV (até 5.000 linhas), com o que casa com a busca/filtros da tela."""
    import csv as csv_mod
    import io

    organizacao_acessivel(sessao, usuario, org_id)
    q = _quadro_ou_404(sessao, org_id, quadro_id)
    teto = qs.limites_mod.efetivos(q)["linhas_por_consulta"]
    linhas, desloc, total, colunas = [], 0, 0, [c["nome"] for c in q.colunas]
    try:
        while len(linhas) < 5000:
            r = qs.consultar(
                sessao, org_id, q.id, filtros=dados.filtros, busca=dados.busca,
                ordem=["_criado_em"], limite=teto, deslocamento=desloc,
            )
            total = r["total"]
            linhas += r["linhas"]
            if r["proximo"] is None:
                break
            desloc = r["proximo"]
    except ErroQuadro as e:
        return _recusa(e)
    buf = io.StringIO()
    w = csv_mod.writer(buf)
    w.writerow(colunas)
    for ln in linhas[:5000]:
        w.writerow(["" if ln["valores"].get(c) is None else ln["valores"][c] for c in colunas])
    return {"ok": True, "csv": buf.getvalue(), "total": total, "exportadas": min(len(linhas), 5000),
            "arquivo": f"{q.nome}.csv"}
