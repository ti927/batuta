"""Porta INTERNA serviço-a-serviço — hoje com um único uso: deixar a IA testar um
conector sem nunca ver o segredo dele.

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
3. **Escopo mínimo.** Esta porta faz UMA coisa (testar uma operação de conector). Não é
   proxy genérico, não executa instrumento arbitrário, não devolve configuração nem
   segredo — só `{ok, status, corpo, erro, campos_detectados}`, o mesmo que a tela mostra.

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
from esquemas import TestarOperacaoInterno
from instrumentos.base import FalhaInstrumento
from modelos import Usuario
from observabilidade.escritor import registrar_evento
from rotas._comum import instrumento_acessivel
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

    try:
        usuario_id = uuid.UUID(str(dados.usuario_id))
        instrumento_id = uuid.UUID(str(dados.instrumento_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ids inválidos.")

    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")

    # O guarda de SEMPRE. O segredo interno provou quem CHAMA; quem AUTORIZA é o papel
    # do usuário na organização — igual à tela, sem atalho.
    inst = instrumento_acessivel(sessao, usuario, instrumento_id, minimo="operador")
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
        detalhe={"operacao": dados.operacao, "status": resultado.get("status")},
    )
    return resultado
