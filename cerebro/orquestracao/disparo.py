"""Disparo de uma automação — onde uma execução nasce e como ela roda.

Todos os gatilhos (botão manual, agendamento/CRON, webhook) **enfileiram**: criam
a execução no estado `aguardando` (`criar_execucao`) e devolvem na hora. Quem de
fato roda a cadeia é o pool de trabalhadores da fila (`fila.py`), que chama
`rodar_execucao`. Assim muitas execuções simultâneas são organizadas sem travar
(PRODUTO §18, Tarefa 5.3).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import medicao_instrumentos
from chaves import resolver_chaves_por_time
from modelos import Automacao, Execucao, PassoExecucao
from orquestracao.cadeia import executar_cadeia
from orquestracao.llm import usar_chaves
from orquestracao.modelos_ia import provedor_do_modelo_seguro


def _fazer_registrador(
    sessao: Session,
    execucao_id: uuid.UUID,
    origens: dict[str, str] | None = None,
    categoria: str = "execucao",
):
    """Callback que grava cada passo da cadeia em `passos_execucao`. `origens`
    (Fases 7.6/7-A) mapeia provedor → origem da chave; cada entrada de `uso` é
    carimbada com a origem do PROVEDOR do seu modelo, registrando de qual chave
    (cliente/consultoria/legado) saiu o consumo — por provedor, já que agentes
    da mesma cadeia podem usar provedores diferentes. `categoria` carimba em que
    FUNÇÃO a IA foi gasta (execução de agentes); o roteamento de bifurcação entra
    no mesmo passo, então fica contabilizado como execução. Carimbar aqui, na
    borda, não toca o núcleo congelado de orquestração."""

    def registrar(passo: dict, ordem: int) -> None:
        uso = passo.get("uso") or []
        for e in uso:
            e.setdefault("categoria", categoria)
            if origens:
                provedor = provedor_do_modelo_seguro(e.get("modelo") or "")
                origem = origens.get(provedor) if provedor else None
                if origem:
                    e.setdefault("origem", origem)
        # Instrumentos com IA paga (ex.: gerar_imagem) acionados neste passo: o
        # custo é contabilizado na borda (categoria 'instrumento'), sem tocar o
        # núcleo nem o contrato do instrumento.
        uso = uso + medicao_instrumentos.uso_de_instrumentos_pagos(
            sessao,
            passo.get("agente_id"),
            passo.get("instrumentos_acionados"),
            origens=origens,
        )
        sessao.add(
            PassoExecucao(
                execucao_id=execucao_id,
                ordem=ordem,
                agente_id=uuid.UUID(passo["agente_id"]),
                entrada={"texto": passo["entrada"]},
                saida={
                    "texto": passo["saida"],
                    "instrumentos_acionados": passo["instrumentos_acionados"],
                    "saida_escolhida": passo["saida_escolhida"],
                    "uso": uso,
                },
                estado="concluido",
                iniciado_em=passo["iniciado_em"],
                finalizado_em=passo["finalizado_em"],
            )
        )
        sessao.commit()

    return registrar


def _aplicar_resultado(execucao: Execucao, r: dict) -> None:
    """Aplica à execução o que a cadeia devolveu: pausa, cancelamento ou
    conclusão."""
    if r["estado"] == "aguardando_humano":
        execucao.estado = "aguardando_humano"  # sem finalizada_em: ainda viva
    elif r["estado"] == "cancelada":
        execucao.estado = "cancelada"
        if not execucao.resultado:
            execucao.resultado = {"texto": "Cancelada pelo operador."}
        execucao.finalizada_em = datetime.now(timezone.utc)
    else:
        execucao.estado = "concluida"
        execucao.resultado = {"texto": r["resultado"]}
        execucao.finalizada_em = datetime.now(timezone.utc)


def _esta_cancelada(sessao: Session, execucao_id: uuid.UUID) -> bool:
    """Relê o estado da execução no banco (vê o que outra sessão já gravou)."""
    return (
        sessao.execute(
            select(Execucao.estado).where(Execucao.id == execucao_id)
        ).scalar()
        == "cancelada"
    )


def criar_execucao(
    sessao: Session, automacao: Automacao, entrada: str
) -> Execucao:
    """Enfileira uma execução: cria o registro no estado `aguardando` e devolve
    já com id. Quem roda é o pool de trabalhadores (`fila.py`); por isso o
    disparo responde na hora e a tela mostra o progresso (Tarefas 5.2 e 5.3).
    `iniciada_em` fica nulo até um trabalhador pegar a execução."""
    execucao = Execucao(
        automacao_id=automacao.id,
        estado="aguardando",
        entrada={"texto": entrada},
    )
    sessao.add(execucao)
    sessao.commit()
    sessao.refresh(execucao)
    return execucao


def rodar_execucao(sessao: Session, execucao: Execucao) -> Execucao:
    """Roda a cadeia de uma execução já reivindicada pelo trabalhador, gravando
    cada passo e o estado final (concluida, aguardando_humano ou falhou).
    Devolve a execução."""
    automacao = sessao.get(Automacao, execucao.automacao_id)
    entrada = (execucao.entrada or {}).get("texto", "")
    # Fases 7.3/7.6/7-A: resolve as chaves de cada provedor da organização desta
    # automação (fallback chave-mãe da consultoria → .env legado p/ Anthropic),
    # com a ORIGEM por provedor para a medição, e fixa o mapa no contexto durante
    # toda a cadeia, sem tocar no motor de grafo.
    chaves, origens = resolver_chaves_por_time(
        sessao, automacao.time_id if automacao else None
    )
    try:
        with usar_chaves(chaves):
            r = executar_cadeia(
                sessao,
                (automacao.cadeia if automacao else None) or {},
                entrada,
                registrar_passo=_fazer_registrador(sessao, execucao.id, origens),
                cancelado=lambda: _esta_cancelada(sessao, execucao.id),
            )
        _aplicar_resultado(execucao, r)
        if execucao.estado == "aguardando_humano":
            # Pausou: se a automação tem canal de aprovação, amarra a conversa do
            # aprovador a esta execução (a resposta dele religa o fluxo). Borda.
            from mensageria import aprovacao
            aprovacao.vincular_pausa(sessao, execucao)
    except Exception as e:  # falha de LLM/rede/cadeia inválida — registra e segue
        execucao.estado = "falhou"
        execucao.resultado = {"erro": str(e)}
        execucao.finalizada_em = datetime.now(timezone.utc)
    sessao.commit()
    sessao.refresh(execucao)
    return execucao
