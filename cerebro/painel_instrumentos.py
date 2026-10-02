"""O que a LISTA de instrumentos de um time precisa saber de cada um — de uma vez.

A aba Instrumentos separa PERSONALIZADOS (Construtor: API e servidor MCP) de PRONTOS,
mostra selos (alcance, tipo de ligação, efeito, situação, custo) e filtra. Antes a tela
montava o "usado por" com uma consulta por agente; aqui é tudo em poucas consultas,
para a lista inteira (o COF Post Blog tem 37 instrumentos).

Anexa atributos transitórios aos objetos `Instrumento` (não mapeados: o SQLAlchemy
não os grava), que o `InstrumentoLer` devolve.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import instrumentos as encaixe
import segredos_instrumento as segredos
import tipos_credencial as tc
from medicao_instrumentos import TIPOS_PAGOS
from modelos import Agente, AgenteInstrumento, Credencial, Instrumento, SegredoInstrumento, Time

# Situações que pedem a atenção de quem cuida do time (o selo laranja).
FALTA_CHAVE = "falta_chave"
RECONECTAR = "reconectar"
FALHOU = "falhou"
MODELO_SAI = "modelo_sai"  # a empresa da IA desliga (ou já desligou) o modelo escolhido


def _qtd_acoes(inst: Instrumento) -> int | None:
    """Quantas ações o instrumento põe no cinto: operações do conector, ferramentas
    escolhidas do servidor MCP. None nos prontos (uma ação só, por definição)."""
    cfg = inst.configuracao or {}
    if inst.tipo == "conector":
        return len(cfg.get("operacoes") or [])
    if inst.tipo == "conectar_mcp":
        return sum(1 for f in (cfg.get("ferramentas") or []) if f.get("usar", True))
    return None


# Os que chamam uma IA paga por fora e medem o gasto REAL (ver `gasto_instrumentos`):
# não entram em TIPOS_PAGOS (lá é a estimativa por configuração), mas são pagos.
_PAGOS_PELO_USO = {"pesquisar_web", "ler_pagina", "ler_documento"}


def _pago(inst: Instrumento) -> bool:
    if inst.tipo in TIPOS_PAGOS or inst.tipo in _PAGOS_PELO_USO:
        return True
    if inst.tipo == "conector":
        return any(
            float(op.get("custo_por_chamada_usd") or 0) > 0
            for op in (inst.configuracao or {}).get("operacoes") or []
        )
    return False


# O nome do campo secreto em palavras de quem usa (a tela não mostra nome de variável).
_O_QUE_FALTA = {"url": "o endereço", "certificado": "o certificado", "chave_privada": "o certificado"}


def _situacao(inst: Instrumento, pendentes: list[str]) -> tuple[str | None, str | None]:
    """(código, frase) do que impede o instrumento de funcionar — None = nada."""
    if pendentes:
        partes = list(dict.fromkeys(_O_QUE_FALTA.get(c, "a chave") for c in pendentes))
        return FALTA_CHAVE, "Falta preencher " + " e ".join(partes) + "."
    conexao = inst.conexao or {}
    if (conexao.get("oauth") or {}).get("estado") == "precisa_reconectar":
        return RECONECTAR, "A conexão da conta caiu: abra e clique em Conectar."
    if conexao.get("estado") == "falhou":
        return FALHOU, conexao.get("mensagem") or "A última conexão falhou."
    from orquestracao import ciclo_modelos

    aviso = ciclo_modelos.alerta((inst.configuracao or {}).get("modelo"))
    if aviso:
        return MODELO_SAI, aviso
    return None, None


def enriquecer(sessao: Session, time: Time, lista: list[Instrumento]) -> None:
    """Anexa a cada instrumento da lista o que o cartão mostra."""
    if not lista:
        return
    ids = [i.id for i in lista]

    # Quem usa: os agentes DESTE time pelo nome; os de outros times, só contados
    # (instrumento da organização usado em vários times).
    usos: dict[uuid.UUID, tuple[list[str], set[uuid.UUID]]] = {i: ([], set()) for i in ids}
    for inst_id, nome, time_id in sessao.execute(
        select(AgenteInstrumento.instrumento_id, Agente.nome, Agente.time_id)
        .join(Agente, Agente.id == AgenteInstrumento.agente_id)
        .where(AgenteInstrumento.instrumento_id.in_(ids))
        .order_by(Agente.nome)
    ):
        nomes, outros = usos[inst_id]
        if time_id == time.id:
            nomes.append(nome)
        else:
            outros.add(time_id)

    # Segredos guardados, em lote (o cálculo do que falta é o mesmo da IA externa).
    guardados: dict[uuid.UUID, set[str]] = {i: set() for i in ids}
    for inst_id, campo in sessao.execute(
        select(SegredoInstrumento.instrumento_id, SegredoInstrumento.campo).where(
            SegredoInstrumento.instrumento_id.in_(ids)
        )
    ):
        guardados[inst_id].add(campo)
    creds = {
        c.id: frozenset(t.nomes_campos) if (t := tc.obter_tipo(c.tipo)) else frozenset()
        for c in sessao.scalars(
            select(Credencial).where(
                Credencial.id.in_({i.credencial_id for i in lista if i.credencial_id})
            )
        )
    }
    resolviveis = segredos.servicos_resolviveis(sessao, time.organizacao_id)

    # De onde vem o instrumento da organização que mora em outro time.
    outras_casas = {i.time_id for i in lista if i.time_id != time.id}
    nomes_times = (
        dict(sessao.execute(select(Time.id, Time.nome).where(Time.id.in_(outras_casas))).all())
        if outras_casas else {}
    )

    for inst in lista:
        nomes, outros = usos[inst.id]
        inst.usado_por_agentes = nomes
        inst.usado_em_outros_times = len(outros)
        inst.personalizado = encaixe.eh_personalizado(inst.tipo)
        inst.ligacao = {"conector": "api", "conectar_mcp": "mcp", "banco_sql": "banco"}.get(inst.tipo)
        inst.qtd_acoes = _qtd_acoes(inst)
        inst.pago = _pago(inst)
        inst.time_casa_nome = nomes_times.get(inst.time_id)
        pend = segredos.pendentes(
            inst.tipo,
            guardados=guardados[inst.id],
            cobertos_por_credencial=creds.get(inst.credencial_id, frozenset()),
            servicos_resolviveis=resolviveis,
            configuracao=inst.configuracao,
        )
        inst.situacao, inst.situacao_motivo = _situacao(inst, pend)
