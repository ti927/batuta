"""Conectar um instrumento MCP por login com a conta (OAuth código + PKCE).

Três pontas:
- POST /instrumentos/{id}/mcp/oauth/iniciar (operador+): descobre o servidor de login,
  registra o Batuta como cliente (CIMD ou registro dinâmico) e devolve `{url}`. A tela
  abre essa URL num pop-up (ou na página inteira, se o pop-up for bloqueado).
- GET /mcp/oauth/callback (PÚBLICA — quem chama é o navegador na volta do login):
  valida o `state` (curto; o login pendente mora no instrumento), confere de novo o papel de quem pediu, troca o código por
  tokens, guarda no cofre do instrumento e devolve uma página mínima que avisa a tela
  (postMessage) e se fecha — ou redireciona para a tela, se não houver quem avisar.
- GET /mcp/oauth/cliente.json (PÚBLICA): o documento do Batuta como cliente OAuth
  (CIMD). O servidor de autorização o baixa quando o client_id é esta URL.

Lógica em `instrumentos/mcp_oauth.py`. Padrão do Google/Instagram (state cifrado com
prazo), com o `code_verifier` do PKCE dentro do state.
"""

import html
import json
import os
import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

import auditoria
import segredos_instrumento as segredos
from auth import usuario_atual
from instrumentos import mcp_oauth
from instrumentos.base import FalhaInstrumento
from instrumentos.mcp import ConfigMCP
from modelos import Instrumento, Time, Usuario
from auth import exigir_papel
from rotas._comum import instrumento_acessivel
from sessao import obter_sessao

rotas = APIRouter(tags=["mcp-oauth"])


def _front_base() -> str:
    origens = os.environ.get("INTERFACE_ORIGINS", "http://localhost:3000")
    return origens.split(",")[0].strip().rstrip("/")


@rotas.post("/instrumentos/{instrumento_id}/mcp/oauth/iniciar")
def iniciar(
    instrumento_id: uuid.UUID,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
):
    inst = instrumento_acessivel(sessao, usuario, instrumento_id, minimo="operador")
    if inst.tipo != "conectar_mcp":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Este instrumento não é MCP.")
    cofre_inst = segredos.decifrar(sessao, inst.id)
    config = ConfigMCP.model_validate({**(inst.configuracao or {}), **cofre_inst})
    if config.auth_modo != "oauth_login":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Escolha “Entrar com a conta” em “Como o Batuta se conecta” e salve antes de conectar.",
        )
    try:
        url, oauth, novos = mcp_oauth.iniciar_login(inst, config, cofre_inst, usuario.id)
    except FalhaInstrumento as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
    if novos:
        segredos.salvar_segredos(sessao, inst.id, novos)
    conexao = dict(inst.conexao or {})
    antigo = dict(conexao.get("oauth") or {})
    # Guarda o que o login vai precisar na volta; o estado só vira "conectado" lá.
    conexao["oauth"] = {**antigo, **oauth, "estado": antigo.get("estado") or "precisa_conectar"}
    inst.conexao = conexao
    sessao.commit()
    return {"url": url}


def _pagina(ok: bool, mensagem: str, inst_id: str | None, time_id: str | None, motivo: str = "") -> HTMLResponse:
    """Página mínima da volta do login: avisa a tela que abriu o pop-up e se fecha. Sem
    pop-up (bloqueado → página inteira), leva o navegador de volta aos instrumentos."""
    front = _front_base()
    consulta = urlencode({k: v for k, v in {
        "mcp_oauth": "ok" if ok else "erro", "instrumento": inst_id or "", "motivo": motivo,
    }.items() if v})
    destino = f"{front}/times/{time_id}/instrumentos?{consulta}" if time_id else front
    dados = {"tipo": "batuta-mcp-oauth", "ok": ok, "instrumento": inst_id, "motivo": motivo}
    corpo = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Batuta</title></head>
<body style="font-family:system-ui,sans-serif;padding:32px;color:#1A1730">
<p>{html.escape(mensagem)}</p>
<script>
var d = {json.dumps(dados)};
try {{
  if (window.opener && !window.opener.closed) {{
    window.opener.postMessage(d, {json.dumps(front)});
    window.close();
  }} else {{ location.replace({json.dumps(destino)}); }}
}} catch (e) {{ location.replace({json.dumps(destino)}); }}
</script></body></html>"""
    return HTMLResponse(corpo)


@rotas.get("/mcp/oauth/callback")
def callback(
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    sessao: Session = Depends(obter_sessao),
):
    try:
        inst = sessao.get(Instrumento, mcp_oauth.instrumento_do_state(state or ""))
    except FalhaInstrumento as e:
        return _pagina(False, str(e), None, None, "state")
    if inst is None:
        return _pagina(False, "Instrumento não encontrado.", None, None, "instrumento")
    time = sessao.get(Time, inst.time_id)
    inst_id, time_id = str(inst.id), str(inst.time_id)
    conexao = dict(inst.conexao or {})
    oauth = dict(conexao.get("oauth") or {})
    try:
        usuario_id, verificador = mcp_oauth.conferir_state(state or "", oauth)
    except FalhaInstrumento as e:
        return _pagina(False, str(e), inst_id, time_id, "state")
    # Uso único: a partir daqui o login pendente some, dê certo ou não.
    oauth.pop("pendente", None)
    conexao["oauth"] = oauth
    inst.conexao = conexao
    sessao.commit()
    usuario = sessao.get(Usuario, uuid.UUID(usuario_id))
    if usuario is None:
        return _pagina(False, "Quem pediu o login não existe mais.", inst_id, time_id, "usuario")
    try:
        # Quem pediu ainda pode mexer neste instrumento? (o papel pode ter mudado)
        exigir_papel(sessao, usuario, time.organizacao_id, "operador")
    except HTTPException:
        return _pagina(False, "Você não tem mais permissão para mexer neste instrumento.",
                       inst_id, time_id, "permissao")
    if error or not code:
        motivo = (error or "sem_codigo")[:60]
        return _pagina(False, "O login não foi concluído"
                       + (f" ({error_description[:120]})." if error_description else "."),
                       inst_id, time_id, motivo)
    cofre_inst = segredos.decifrar(sessao, inst.id)
    client_secret = cofre_inst.get(mcp_oauth.CAMPO_CLIENT_SECRET) or cofre_inst.get("auth_segredo") or ""
    try:
        novos, oauth_novo = mcp_oauth.trocar_codigo(oauth, code, verificador, client_secret)
    except (FalhaInstrumento, KeyError) as e:
        conexao["oauth"] = {**oauth, "estado": "precisa_conectar", "motivo": str(e)[:200]}
        inst.conexao = conexao
        sessao.commit()
        return _pagina(False, f"Não deu para conectar: {e}", inst_id, time_id, "token")
    segredos.salvar_segredos(sessao, inst.id, novos)
    conexao["oauth"] = oauth_novo
    inst.conexao = conexao
    auditoria.registrar(
        sessao, usuario=usuario, acao="instrumento.conectado", recurso_tipo="instrumento",
        recurso_id=inst.id, organizacao_id=time.organizacao_id,
        detalhe={"modo": "oauth_login", "registro": oauth_novo.get("registro")},
    )
    sessao.commit()
    return _pagina(True, "Conta conectada. Pode fechar esta janela.", inst_id, time_id)


@rotas.get("/mcp/oauth/cliente.json")
def documento_cliente():
    return JSONResponse(mcp_oauth.documento_cliente())
