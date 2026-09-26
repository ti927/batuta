"""Porta INTERNA serviço-a-serviço — deixa a IA TESTAR um instrumento sem nunca ver o
segredo dele: uma operação de conector (`/interno/conector/testar-operacao`) ou o
acionamento de qualquer outro tipo (`/interno/instrumento/testar`, desde 2026-09-26).

**O problema.** O serviço MCP roda SEM a chave-mestra do cofre, de propósito (decisão
do maestro na Fatia 3a: *a IA nunca recebe segredo*). Isso tem um custo que só
apareceu em 2026-09-22, montando o conector do Search Console: a IA consegue MONTAR a
integração e não consegue TESTÁ-LA — e sem teste ela entrega no escuro, ou o consultor
vira o revisor manual de cada chamada.

**A saída que não quebra a regra.** Em vez de dar a chave ao MCP, o MCP PEDE ao cérebro
que rode o teste. O segredo é decifrado aqui, usado aqui e morre aqui; o que atravessa
a fronteira é só a resposta da API.

**Como isto se protege — três camadas, porque uma só não basta:**

1. **Segredo compartilhado** (`BATUTA_INTERNO_SECRET`), comparado em tempo constante.
   Ele prova que quem chama é um serviço NOSSO. **Ausente = a porta não existe**: sem a
   variável, toda chamada é recusada. Nada fica aberto por omissão.
2. **Autorização por USUÁRIO, com os guardas de sempre.** O segredo não autoriza nada
   sozinho: o corpo diz em nome de QUEM se age, e o pedido passa por
   `instrumento_acessivel(..., "operador")` — o mesmo guarda da tela. Um usuário que
   não pode mexer naquele instrumento continua não podendo, venha o pedido de onde vier.
3. **Escopo mínimo.** Esta porta TESTA um instrumento que JÁ EXISTE no escopo do
   usuário, exatamente como os botões da tela ("Testar e detectar" do conector, "Acionar"
   dos outros tipos). Não é proxy genérico (não chama URL arbitrária), não devolve
   configuração nem segredo — só o que a tela mostraria.

**O teste é REAL, inclusive quando grava** (decisão do maestro, 2026-09-26): a IA pode
testar a operação que cria um registro ou envia uma mensagem, marcando o que cria com
"TESTES". A resposta diz se a chamada mexeu em algo lá fora (`escreve`), e o evento no
banco de logs também — para ninguém ter de adivinhar depois o que um teste criou.

**O risco que fica, dito na cara:** quem tiver o segredo interno pode testar operações
de conector em nome de qualquer usuário — limitado ao que aquele usuário já poderia
fazer. É por isso que o escopo é mínimo e que toda chamada deixa evento no banco de
logs com quem agiu.
"""

import hmac
import os
import uuid

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy.orm import Session
from fastapi import Depends

import instrumentos as encaixe
from esquemas import TestarInstrumentoInterno, TestarOperacaoInterno
from instrumentos.base import FalhaInstrumento
from modelos import Usuario
from observabilidade.escritor import registrar_evento
from rotas._comum import instrumento_acessivel
from rotas.instrumentos import acionar_instrumento
from sessao import obter_sessao
import segredos_instrumento as segredos

rotas = APIRouter()

CABECALHO = "X-Batuta-Interno"


def _exigir_segredo(recebido: str | None) -> None:
    """A porta só existe se o segredo estiver configurado — e só abre com ele certo."""
    esperado = (os.environ.get("BATUTA_INTERNO_SECRET") or "").strip()
    if not esperado:
        # Sem a variável, a porta NÃO existe. 404 (e não 403) de propósito: um
        # ambiente que não usa esta ponte não anuncia que ela poderia existir.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    if not recebido or not hmac.compare_digest(recebido.strip(), esperado):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso interno negado.")


@rotas.post("/interno/conector/testar-operacao")
def testar_operacao_interno(
    dados: TestarOperacaoInterno,
    x_batuta_interno: str | None = Header(default=None, alias=CABECALHO),
    sessao: Session = Depends(obter_sessao),
):
    """Roda UMA operação de um conector em nome de um usuário e devolve a resposta.

    É a mesma coisa que o botão "Testar e detectar" da tela faz — e de propósito: se um
    dia divergirem, a IA testaria uma coisa e o consultor veria outra."""
    _exigir_segredo(x_batuta_interno)
    usuario, inst = _usuario_e_instrumento(sessao, dados.usuario_id, dados.instrumento_id)
    if inst.tipo != "conector":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Só um conector tem operações para testar.",
        )

    tipo = encaixe.obter_tipo("conector")
    secretos = segredos.decifrar(sessao, inst.id)  # em memória, nunca na resposta
    config = tipo.Config.model_validate({**(inst.configuracao or {}), **secretos})
    try:
        resultado = tipo.testar_operacao(config, dados.operacao, dados.valores or {})
    except FalhaInstrumento as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))

    # Rastro: quem agiu, em qual instrumento, por esta porta. Uma ponte de serviço sem
    # rastro é uma ponte que ninguém audita.
    registrar_evento(
        categoria="interno",
        acao="conector.testado_pela_ia",
        nivel="info",
        resultado="ok" if resultado.get("ok") else "falha",
        usuario_id=str(usuario.id),
        recurso_tipo="instrumento",
        recurso_id=str(inst.id),
        origem="mcp",
        detalhe={
            "operacao": dados.operacao,
            "status": resultado.get("status"),
            "escreve": bool(resultado.get("escreve")),
        },
    )
    return resultado


@rotas.post("/interno/instrumento/testar")
def testar_instrumento_interno(
    dados: TestarInstrumentoInterno,
    x_batuta_interno: str | None = Header(default=None, alias=CABECALHO),
    sessao: Session = Depends(obter_sessao),
):
    """Aciona um instrumento que NÃO é conector, em nome de um usuário — o mesmo que o
    "Acionar" da tela (`rotas.instrumentos.acionar_instrumento`, fonte única).

    A falha do instrumento volta como DADO (`ok: false` + o motivo), não como erro
    HTTP: a IA precisa ler o que o sistema de fora disse para consertar a montagem."""
    _exigir_segredo(x_batuta_interno)
    usuario, inst = _usuario_e_instrumento(sessao, dados.usuario_id, dados.instrumento_id)
    if inst.tipo == "conector":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Conector se testa por operação (testar_operacao_conector).",
        )

    escreve = encaixe.acao_irreversivel(inst.tipo, inst.configuracao or {})
    try:
        saida = {"ok": True, "resultado": acionar_instrumento(sessao, inst, dados.argumentos)}
    except ValueError as e:
        # Argumentos ou configuração que não fecham com o tipo — erro de quem montou.
        saida = {"ok": False, "erro": str(e)}
    except FalhaInstrumento as e:
        saida = {"ok": False, "erro": str(e)}
    saida["escreve"] = escreve

    registrar_evento(
        categoria="interno",
        acao="instrumento.testado_pela_ia",
        nivel="info",
        resultado="ok" if saida["ok"] else "falha",
        usuario_id=str(usuario.id),
        recurso_tipo="instrumento",
        recurso_id=str(inst.id),
        origem="mcp",
        detalhe={"tipo": inst.tipo, "escreve": escreve},
    )
    return saida


def _usuario_e_instrumento(sessao: Session, usuario_id, instrumento_id):
    """Quem age e sobre o quê — pelo guarda de SEMPRE. O segredo interno provou quem
    CHAMA; quem AUTORIZA é o papel do usuário na organização, igual à tela, sem atalho."""
    try:
        uid = uuid.UUID(str(usuario_id))
        iid = uuid.UUID(str(instrumento_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ids inválidos.")

    usuario = sessao.get(Usuario, uid)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    inst = instrumento_acessivel(sessao, usuario, iid, minimo="operador")
    return usuario, inst
