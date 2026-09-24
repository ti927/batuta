"""Leitura de um quadro DE FORA, por um link de leitura — sem login.

É o que um painel usa: o Google Planilhas com `=IMPORTDATA("<link>")` (e dali o Looker
Studio), o Power BI e o Excel ("dados da web"), ou um painel próprio (JSON).

    GET /publico/quadros/{link}             → as linhas (CSV por padrão; ?formato=json)
    GET /publico/quadros/{link}/totais      → contas feitas pelo Batuta

Parâmetros (todos opcionais):
- `filtro=Coluna|operador|valor` (repetível). Operadores: eq, ne, gt, gte, lt, lte,
  contem, vazio, nao_vazio. Datas aceitam "hoje", "hoje-90", "hoje+7".
- `recente=Coluna` — só as linhas com o maior valor desta coluna (a rodada mais recente).
- `ordem=Coluna` ou `ordem=-Coluna` (repetível) · `colunas=A,B,C` · `busca=texto`
- `limite=N` (até 10.000) · `decimal=virgula` (números como 1234,5 — Planilhas em português)
- totais: `agrupar=Coluna` (até 3) e `metrica=funcao|Coluna` (contar, soma, media,
  minimo, maximo; `metrica=contar` sozinho conta linhas).

Só leitura, só aquele quadro. Toda leitura conta no link (`usos`) e vira evento no banco
de logs. Resposta com `Access-Control-Allow-Origin: *` (um painel no navegador consegue
ler) e sem cache.
"""

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy.orm import Session

from observabilidade.escritor import registrar_evento
from quadros import links
from quadros import servico as qs
from quadros.servico import ErroQuadro
from sessao import obter_sessao

rotas = APIRouter(tags=["quadros-publico"])

MAX_LINHAS = 10_000
_CABECALHOS = {"Access-Control-Allow-Origin": "*", "Cache-Control": "no-store"}


def _erro(mensagem: str, status: int, formato: str) -> Response:
    if formato == "json":
        return JSONResponse({"erro": mensagem}, status_code=status, headers=_CABECALHOS)
    return PlainTextResponse(mensagem, status_code=status, headers=_CABECALHOS)


def _celula(v, decimal_virgula: bool):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "sim" if v else "não"
    if isinstance(v, float) and decimal_virgula:
        return str(v).replace(".", ",")
    return v


def _csv(colunas: list[str], linhas: list[list], decimal_virgula: bool) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(colunas)
    for ln in linhas:
        w.writerow([_celula(v, decimal_virgula) for v in ln])
    return Response(
        content=buf.getvalue(), media_type="text/csv; charset=utf-8", headers=_CABECALHOS
    )


def _registrar(link, tipo: str, n: int) -> None:
    registrar_evento(
        categoria="quadro", acao="quadro.link_lido", nivel="info", resultado="ok",
        recurso_tipo="quadro", recurso_id=link.quadro_id, organizacao_id=link.organizacao_id,
        detalhe={"link": link.nome, "final": link.token_final, "leitura": tipo, "linhas": n},
    )


@rotas.get("/publico/quadros/{token}")
def ler(
    token: str,
    formato: str = "csv",
    filtro: list[str] = Query(default=[]),
    ordem: list[str] = Query(default=[]),
    recente: str | None = None,
    colunas: str | None = None,
    busca: str | None = None,
    limite: int = MAX_LINHAS,
    decimal: str | None = None,
    sessao: Session = Depends(obter_sessao),
):
    formato = "json" if formato.lower() == "json" else "csv"
    try:
        link = links.abrir(sessao, token)
        sessao.commit()
    except links.LinkRecusado as e:
        return _erro(str(e), e.status, formato)
    try:
        q = qs.obter_quadro(sessao, link.organizacao_id, link.quadro_id)
        teto = qs.limites_mod.efetivos(q)["linhas_por_consulta"]
        pedidas = max(1, min(int(limite or MAX_LINHAS), MAX_LINHAS))
        so = [c.strip() for c in colunas.split(",")] if colunas else None
        filtros = links.filtros_da_url(filtro)
        linhas, desloc, total, nomes = [], 0, 0, None
        while len(linhas) < pedidas:
            r = qs.consultar(
                sessao, link.organizacao_id, q.id, filtros=filtros, ordem=ordem or ["_criado_em"],
                colunas=so, busca=busca, so_o_mais_recente_de=recente,
                limite=min(teto, pedidas - len(linhas)), deslocamento=desloc,
            )
            total, nomes = r["total"], r["colunas"]
            linhas += r["linhas"]
            if r["proximo"] is None:
                break
            desloc = r["proximo"]
    except ErroQuadro as e:
        return _erro(e.mensagem, 422, formato)
    _registrar(link, "linhas", len(linhas))
    sessao.commit()
    if formato == "json":
        return JSONResponse(
            {
                "quadro": q.nome,
                "total": total,
                "devolvidas": len(linhas),
                "colunas": nomes,
                "linhas": [ln["valores"] for ln in linhas],
            },
            headers=_CABECALHOS,
        )
    return _csv(nomes or [], [[ln["valores"].get(c) for c in nomes] for ln in linhas], decimal == "virgula")


@rotas.get("/publico/quadros/{token}/totais")
def totais(
    token: str,
    formato: str = "csv",
    agrupar: list[str] = Query(default=[]),
    metrica: list[str] = Query(default=[]),
    filtro: list[str] = Query(default=[]),
    recente: str | None = None,
    decimal: str | None = None,
    sessao: Session = Depends(obter_sessao),
):
    formato = "json" if formato.lower() == "json" else "csv"
    try:
        link = links.abrir(sessao, token)
        sessao.commit()
    except links.LinkRecusado as e:
        return _erro(str(e), e.status, formato)
    try:
        metricas = []
        for m in metrica or ["contar"]:
            funcao, _, coluna = m.partition("|")
            metricas.append({"funcao": funcao.strip(), **({"coluna": coluna.strip()} if coluna.strip() else {})})
        r = qs.totais(
            sessao, link.organizacao_id, link.quadro_id, metricas=metricas,
            agrupar_por=agrupar or None, filtros=links.filtros_da_url(filtro),
            so_o_mais_recente_de=recente,
        )
    except ErroQuadro as e:
        return _erro(e.mensagem, 422, formato)
    _registrar(link, "totais", len(r["resultados"]))
    sessao.commit()
    if formato == "json":
        return JSONResponse(r, headers=_CABECALHOS)
    grupo = r["agrupado_por"]
    rotulos = list(r["resultados"][0]["valores"]) if r["resultados"] else []
    return _csv(
        grupo + rotulos,
        [[g.get("grupo", {}).get(c) for c in grupo] + [g["valores"][k] for k in rotulos] for g in r["resultados"]],
        decimal == "virgula",
    )
