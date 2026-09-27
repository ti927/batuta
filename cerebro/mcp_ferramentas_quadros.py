"""Ferramentas do Batuta-MCP para os QUADROS do cérebro da organização
(docs/CEREBRO-PLANO.md §7).

A flexibilidade vem de quatro princípios, não de muitas funções:
1. **Uma linguagem de filtro só** (`quadros.filtros`) — a mesma dos agentes e da tela.
2. **`simular` em toda escrita** — devolve o que aconteceria, sem gravar. Apagar linhas
   e excluir quadro vão além: SEM `confirmar=true` eles SÓ simulam.
3. **Paginação e contagem sempre** — toda leitura diz o total e o próximo deslocamento.
4. **Erro que ensina** — toda recusa diz o quê, onde e como corrigir.

Papéis (os mesmos guardas das rotas): observador lê; operador cria/altera quadros e
grava/edita/apaga linhas; admin exclui quadro. Tudo passa pelo MESMO `quadros.servico`
que agente, tela e IA criadora usam, com o carimbo `origem=mcp` + o consultor.
"""

import csv
import io
import json

from mcp_escopo import organizacao_acessivel
from mcp_ferramentas import _ferramenta, _uuid
from mcp_ferramentas_escrita import _ferramenta_escrita
from quadros import importacao
from quadros import servico as qs
from quadros.servico import Autor, ErroQuadro

MAX_EXPORTAR = 5000


def _json(dados) -> str:
    return json.dumps(dados, ensure_ascii=False, default=str)


def _recusa(e: ErroQuadro) -> str:
    corpo = {"ok": False, "erro": e.mensagem}
    if e.detalhes:
        corpo["detalhes"] = e.detalhes
    return _json(corpo)


def _org(sessao, usuario, organizacao_id, papel):
    oid = _uuid(organizacao_id)
    if oid is None:
        raise ErroQuadro(f"Id de organização inválido: {organizacao_id}.")
    organizacao_acessivel(sessao, usuario, oid, papel)
    return oid


def _autor(usuario) -> Autor:
    return Autor(origem="mcp", usuario_id=usuario.id)


def _rodar(fn) -> str:
    try:
        return _json({"ok": True, **fn()})
    except ErroQuadro as e:
        return _recusa(e)


# ───────────────────────────── leitura (observador) ─────────────────────────────


@_ferramenta
def listar_quadros(sessao, usuario, organizacao_id) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "observador")
        return {"quadros": [
            {
                "quadro_id": str(q.id), "nome": q.nome, "descricao": q.descricao,
                "linhas": qs.contar_linhas(sessao, q.id),
                "atualizado_em": q.atualizado_em,
                "usado_por": qs.quem_usa(sessao, org, q.id),
            }
            for q in qs.listar_quadros(sessao, org)
        ]}
    return _rodar(fn)


@_ferramenta
def ver_quadro(sessao, usuario, organizacao_id, quadro) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "observador")
        q = qs.obter_quadro(sessao, org, quadro)
        amostra = qs.consultar(sessao, org, q.id, limite=5)
        return {
            "quadro": qs.descrever_quadro(q, qs.contar_linhas(sessao, q.id)),
            "ultimas_linhas": amostra["linhas"],
            "usado_por": qs.quem_usa(sessao, org, q.id),
        }
    return _rodar(fn)


@_ferramenta
def consultar_quadro(
    sessao, usuario, organizacao_id, quadro, filtros, ordem, colunas, limite,
    deslocamento, so_o_mais_recente_de, execucao_id,
) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "observador")
        return qs.consultar(
            sessao, org, quadro, filtros=filtros, ordem=ordem, colunas=colunas,
            limite=limite, deslocamento=deslocamento or 0,
            so_o_mais_recente_de=so_o_mais_recente_de, execucao_id=execucao_id,
        )
    return _rodar(fn)


@_ferramenta
def totais_quadro(
    sessao, usuario, organizacao_id, quadro, metricas, agrupar_por, filtros,
    so_o_mais_recente_de,
) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "observador")
        return qs.totais(
            sessao, org, quadro, metricas=metricas, agrupar_por=agrupar_por,
            filtros=filtros, so_o_mais_recente_de=so_o_mais_recente_de,
        )
    return _rodar(fn)


@_ferramenta
def historico_linha(sessao, usuario, organizacao_id, quadro, linha_id) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "observador")
        return qs.historico_linha(sessao, org, quadro, linha_id)
    return _rodar(fn)


@_ferramenta
def exportar_quadro(sessao, usuario, organizacao_id, quadro, filtros) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "observador")
        q = qs.obter_quadro(sessao, org, quadro)
        passo = 200
        linhas, deslocamento, total = [], 0, None
        while True:
            r = qs.consultar(
                sessao, org, q.id, filtros=filtros, ordem=["_criado_em"],
                limite=min(passo, qs.limites_mod.efetivos(q)["linhas_por_consulta"]),
                deslocamento=deslocamento,
            )
            total = r["total"]
            linhas += r["linhas"]
            if r["proximo"] is None or len(linhas) >= MAX_EXPORTAR:
                break
            deslocamento = r["proximo"]
        buf = io.StringIO()
        escritor = csv.writer(buf)
        escritor.writerow(r["colunas"])
        for ln in linhas[:MAX_EXPORTAR]:
            escritor.writerow(["" if ln["valores"].get(c) is None else ln["valores"][c] for c in r["colunas"]])
        saida = {"quadro": q.nome, "total": total, "exportadas": min(len(linhas), MAX_EXPORTAR), "csv": buf.getvalue()}
        if total > MAX_EXPORTAR:
            saida["aviso"] = f"O quadro tem {total} linhas; exportei as {MAX_EXPORTAR} primeiras. Use filtros para exportar em partes."
        return saida
    return _rodar(fn)


# ───────────────────────────── escrita (operador) ─────────────────────────────


@_ferramenta_escrita
def criar_quadro(sessao, usuario, organizacao_id, nome, colunas, chave, descricao, limites, simular) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "operador")
        return qs.criar_quadro(
            sessao, org, nome=nome, colunas=colunas, chave=chave, descricao=descricao,
            limites=limites, criado_por_id=usuario.id, simular=bool(simular),
        )
    return _rodar(fn)


@_ferramenta_escrita
def alterar_quadro(sessao, usuario, organizacao_id, quadro, operacoes, simular) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "operador")
        return qs.alterar_quadro(sessao, org, quadro, operacoes, simular=bool(simular))
    return _rodar(fn)


@_ferramenta_escrita
def gravar_linhas(sessao, usuario, organizacao_id, quadro, linhas, modo, simular) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "operador")
        return qs.gravar_linhas(
            sessao, org, quadro, linhas, autor=_autor(usuario), modo=modo or "acrescentar",
            simular=bool(simular),
        )
    return _rodar(fn)


@_ferramenta_escrita
def editar_linhas(sessao, usuario, organizacao_id, quadro, campos, ids, filtros, simular) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "operador")
        return qs.editar_linhas(
            sessao, org, quadro, campos=campos, ids=ids, filtros=filtros,
            autor=_autor(usuario), simular=bool(simular),
        )
    return _rodar(fn)


_CONFIRMAR = (
    "Isto foi só uma PRÉVIA — nada foi apagado. Mostre ao consultor o que sairia e, com o "
    "aval dele, chame de novo com confirmar=true."
)


@_ferramenta_escrita
def apagar_linhas(sessao, usuario, organizacao_id, quadro, ids, filtros, execucao_id, confirmar) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "operador")
        r = qs.apagar_linhas(
            sessao, org, quadro, ids=ids, filtros=filtros, execucao_id=execucao_id,
            autor=_autor(usuario), simular=not confirmar,
        )
        return {**r, "aviso": _CONFIRMAR} if not confirmar else r
    return _rodar(fn)


@_ferramenta_escrita
def importar_csv(
    sessao, usuario, organizacao_id, csv_texto, quadro, criar_com_nome, chave,
    mapeamento, ignorar_colunas_extras, modo, simular,
) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "operador")
        if criar_com_nome:
            sugestao = importacao.sugerir_colunas(csv_texto)
            criado = qs.criar_quadro(
                sessao, org, nome=criar_com_nome, colunas=sugestao["colunas"], chave=chave,
                criado_por_id=usuario.id, simular=bool(simular),
            )
            if simular:
                return {"simulado": True, "colunas_sugeridas": sugestao["colunas"],
                        "linhas_no_csv": sugestao["linhas_no_csv"],
                        "proximo_passo": "Confira as colunas com o consultor. Se precisar "
                        "de outro tipo/chave, crie o quadro com criar_quadro e importe com "
                        "`quadro`; senão, chame de novo com simular=false."}
            alvo = criado["quadro_id"]
        elif quadro:
            alvo = quadro
        else:
            raise ErroQuadro("Diga o `quadro` de destino ou `criar_com_nome`.")
        return importacao.importar_csv(
            sessao, org, alvo, csv_texto, autor=Autor(origem="importacao", usuario_id=usuario.id),
            mapeamento=mapeamento, ignorar_colunas_extras=bool(ignorar_colunas_extras),
            modo=modo or "acrescentar", simular=bool(simular),
        )
    return _rodar(fn)


# ───────────────────────────── links de leitura ─────────────────────────────
# O MCP lista, revoga, CRIA e TESTA. Criar entrega o link (uma senha) à conversa da IA —
# por isso é só para ADMIN, com prévia antes, e fica na auditoria. SEM validade, por
# decisão do maestro (2026-09-27): o link serve automações, e um link que vence para a
# automação em silêncio. Trocar continua sendo pela tela.


@_ferramenta
def listar_links_quadro(sessao, usuario, organizacao_id, quadro) -> str:
    from quadros import links as links_mod

    def fn():
        org = _org(sessao, usuario, organizacao_id, "observador")
        return {"links": [links_mod.serializar(link) for link in links_mod.listar(sessao, org, quadro)]}
    return _rodar(fn)


@_ferramenta_escrita
def criar_link_quadro(sessao, usuario, organizacao_id, quadro, nome, limite_por_minuto, confirmar) -> str:
    import auditoria
    from mcp_ferramentas_escrita import _url_cerebro
    from quadros import links as links_mod

    def fn():
        # Um link expõe o quadro para fora da empresa: é decisão de admin (igual à tela).
        org = _org(sessao, usuario, organizacao_id, "admin")
        q = qs.obter_quadro(sessao, org, quadro)
        nome_link = (nome or "").strip()
        if not nome_link:
            raise ErroQuadro("Dê um nome ao link (ex.: “Painel do Looker”), para saber quem o usa.")
        if not confirmar:
            return {"simulado": True, "quadro": q.nome, "linhas": qs.contar_linhas(sessao, q.id),
                    "colunas": [c.get("nome") for c in (q.colunas or [])],
                    "aviso": (
                        "Isto foi só uma PRÉVIA. O link dá leitura deste quadro a QUALQUER um que o "
                        "tenha, sem login e sem validade, até ser revogado. Confirme com o consultor "
                        "e chame de novo com confirmar=true."
                    )}
        link, token = links_mod.criar(
            sessao, org, q.id, nome=f"{nome_link} (criado pela IA)",
            limite_por_minuto=limite_por_minuto, expira_em=None, criado_por_id=usuario.id,
        )
        auditoria.registrar(
            sessao, usuario=usuario, acao="quadro.link_criado", recurso_tipo="quadro",
            recurso_id=q.id, organizacao_id=org,
            detalhe={"nome": link.nome, "final": link.token_final, "origem": "mcp"},
        )
        url = _url_cerebro() + links_mod.caminho_publico(token)
        return {
            "link": links_mod.serializar(link),
            "url": url,
            "formula_planilhas": f'=IMPORTDATA("{url}?decimal=virgula")',
            "aviso": (
                "Entregue o link ao consultor AGORA: ele não aparece de novo (o Batuta guarda só "
                "o final). Teste o que o painel vai receber com testar_link_quadro."
            ),
        }
    return _rodar(fn)


@_ferramenta
def testar_link_quadro(sessao, usuario, organizacao_id, quadro, link_id, url, consulta_url, totais_url) -> str:
    from urllib.parse import parse_qs, urlsplit

    from observabilidade.escritor import registrar_evento
    from quadros import links as links_mod
    from rotas.quadros_publico import ler_linhas, ler_totais

    def fn():
        consulta: dict = {}
        totais = False
        if url:
            partes = urlsplit(url.strip())
            caminho = partes.path.rstrip("/")
            totais = caminho.endswith("/totais")
            if totais:
                caminho = caminho[: -len("/totais")]
            token = caminho.rsplit("/", 1)[-1]
            consulta = parse_qs(partes.query, keep_blank_values=True)
            link = links_mod.localizar(sessao, token)
            # O link autoriza o PAINEL; a IA ainda precisa poder ver aquela organização.
            _org(sessao, usuario, str(link.organizacao_id), "observador")
        elif link_id:
            org = _org(sessao, usuario, organizacao_id, "observador")
            link = next((ln for ln in links_mod.listar(sessao, org, quadro) if str(ln.id) == str(link_id)), None)
            if link is None:
                raise ErroQuadro("Não achei esse link neste quadro (veja listar_links_quadro).")
            links_mod.verificar_ativo(link)
            consulta = parse_qs((consulta_url or "").lstrip("?"), keep_blank_values=True)
            totais = bool(totais_url)
        else:
            raise ErroQuadro("Passe a `url` do link (com os filtros) ou o `link_id` + `quadro`.")

        def um(chave, padrao=None):
            v = consulta.get(chave)
            return v[-1] if v else padrao

        if totais:
            r = ler_totais(sessao, link, agrupar=consulta.get("agrupar", []),
                           metrica=consulta.get("metrica", []), filtro=consulta.get("filtro", []),
                           recente=um("recente"))
        else:
            r = ler_linhas(sessao, link, filtro=consulta.get("filtro", []),
                           ordem=consulta.get("ordem", []), recente=um("recente"),
                           colunas=um("colunas"), busca=um("busca"),
                           limite=int(um("limite", "10000") or 10000))
            mostradas = r["linhas"][:20]
            r = {**r, "linhas": mostradas,
                 "nota": f"Mostrando {len(mostradas)} de {r['devolvidas']} linhas que o painel recebe."}
        registrar_evento(
            categoria="quadro", acao="quadro.link_testado_pela_ia", nivel="info", resultado="ok",
            persistir=True,  # "quadro" não é categoria persistida por padrão
            usuario_id=str(usuario.id), recurso_tipo="quadro", recurso_id=link.quadro_id,
            organizacao_id=link.organizacao_id, origem="mcp",
            detalhe={"link": link.nome, "final": link.token_final, "totais": totais},
        )
        return {"link": links_mod.serializar(link), "totais": totais, "resultado": r}

    try:
        return _rodar(fn)
    except links_mod.LinkRecusado as e:
        return _json({"ok": False, "erro": str(e)})


@_ferramenta_escrita
def revogar_link_quadro(sessao, usuario, organizacao_id, quadro, link_id, confirmar) -> str:
    from quadros import links as links_mod

    def fn():
        org = _org(sessao, usuario, organizacao_id, "admin")
        if not confirmar:
            atual = next((link for link in links_mod.listar(sessao, org, quadro) if str(link.id) == str(link_id)), None)
            if atual is None:
                raise ErroQuadro("Não achei esse link neste quadro.")
            return {"simulado": True, "link": links_mod.serializar(atual), "aviso": (
                "Isto foi só uma PRÉVIA. Revogar corta o link na hora: o painel que o usa para de "
                "receber dados. Confirme com o consultor e chame de novo com confirmar=true."
            )}
        return {"link": links_mod.serializar(links_mod.revogar(sessao, org, quadro, link_id))}
    return _rodar(fn)


# ───────────────────────────── admin ─────────────────────────────


@_ferramenta_escrita
def excluir_quadro(sessao, usuario, organizacao_id, quadro, confirmar) -> str:
    def fn():
        org = _org(sessao, usuario, organizacao_id, "admin")
        r = qs.excluir_quadro(sessao, org, quadro, simular=not confirmar)
        return {**r, "aviso": _CONFIRMAR} if not confirmar else r
    return _rodar(fn)
