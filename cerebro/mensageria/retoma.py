"""Miolo de retoma de uma execução pausada (espera-por-humano), reutilizável.

Uma execução para quando o AGENTE pede aprovação (instrumento `pedir_aprovacao`).
Retomar é religar esse mesmo agente com a resposta da pessoa: ele continua de onde
parou — não recomeça —, faz o que tinha para fazer e declara por quais caminhos o
fluxo segue. Duas superfícies retomam:

- TELA (`rotas/automacoes.py::responder`): `retomar_execucao`.
- CANAL (`mensageria/servico.py`): o turno roda pela BORDA (entrega + ciclo de vida de
  mensageria) e usa `avancar_apos_gate` direto.

NÃO toca o núcleo (`cadeia.py`); só o usa. `avancar_apos_gate` e `localizar_no_pausado`
são o que tela e canal compartilham.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mensageria.config import com_ajuste_do_no, config_da_automacao
from modelos import Agente, Automacao, Execucao, PassoExecucao
from observabilidade.escritor import registrar_evento
from orquestracao import ficha as ficha_mod
from orquestracao import grafo, memoria_conversa
from orquestracao.agente import executar_agente
from orquestracao.cadeia import _carregar_cinto, _escolher_saida, executar_cadeia
from orquestracao.disparo import _aplicar_resultado, _esta_cancelada, _fazer_registrador
from orquestracao.llm import usar_chaves

# Anti-loop do portão NA TELA (a tela não tem teto de conversa). No CANAL, quem
# limita as rodadas é o teto de turnos/custo da conversa (regra geral de mensageria).
MAX_RODADAS_GATE = 8


def entrada_retomada(saida_pausada: str, resposta: str) -> str:
    """A entrada do próximo nó ao retomar uma pausa: o trabalho que o agente
    produziu + a decisão/feedback do humano, separados e rotulados."""
    return f"{saida_pausada}\n\n---\n[Resposta do humano]\n{resposta}"


def localizar_no_pausado(sessao: Session, execucao: Execucao):
    """Acha (último passo, nó do grafo, no_id, cadeia normalizada, índice) do ponto
    onde a execução pausou. Levanta ValueError se não há passo de pausa."""
    auto = sessao.get(Automacao, execucao.automacao_id)
    ultimo = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()
    no_id = (ultimo.no_id if ultimo else None) or (
        str(ultimo.agente_id) if ultimo and ultimo.agente_id else None
    )
    if no_id is None:
        raise ValueError("passo de pausa ausente")
    # O desenho DESTA execução, não o vivo (Onda 4, lacuna 29): editar a automação com
    # uma aprovação em aberto não muda mais o caminho no meio da corrida.
    cadeia = grafo.desenho_que_roda(execucao.desenho, auto.cadeia if auto else None)
    idx = grafo.indexar(cadeia)
    no = idx.no(no_id) or {}
    return ultimo, no, no_id, cadeia, idx


def rodadas_no_gate(sessao: Session, execucao_id, no_id: str) -> int:
    """Quantos passos já rodaram neste nó de gate (apresentação inicial + cada
    pergunta de volta na TELA). Base do anti-loop da tela."""
    return (
        sessao.scalar(
            select(func.count(PassoExecucao.id))
            .where(PassoExecucao.execucao_id == execucao_id)
            .where(PassoExecucao.no_id == no_id)
        )
        or 0
    )


def avancar_apos_gate(
    sessao: Session,
    execucao: Execucao,
    *,
    idx,
    cadeia: dict,
    escolhidas: list[dict] | None,
    entrada_proxima: str,
    ordem_inicial: int,
    chaves: dict,
    origens: dict,
) -> Execucao:
    """Decisão tomada: o fluxo ANDA por TODOS os ramos escolhidos (o grafo faz
    fan-out — aprovar uma capa pode alimentar o Carrossel E o Story). Ramo que aponta
    para o fim vira resultado; os demais viram a próxima onda, junto com as
    PENDÊNCIAS guardadas quando a execução pausou. Re-vincula se pausar em outro
    portão. Compartilhado por TELA e CANAL."""
    escolhidas = list(escolhidas or [])
    frente: list[dict] = []
    for s in escolhidas:
        destino = s.get("destino")
        if destino is not None and not idx.eh_fim(destino):
            frente.append({"no": destino, "entradas": [entrada_proxima]})
    # Ramos que ficaram esperando quando o portão pausou no meio de uma onda.
    frente += [
        {"no": p["no"], "entradas": list(p.get("entradas") or [])}
        for p in (execucao.pendencias or [])
        if p.get("no")
    ]
    execucao.pendencias = None

    if not frente:
        execucao.estado = "concluida"
        execucao.resultado = {"texto": entrada_proxima}
        execucao.finalizada_em = datetime.now(timezone.utc)
        sessao.commit()
        sessao.refresh(execucao)
        return execucao

    execucao.estado = "em_andamento"
    # Reinicia o relógio de inatividade do sweeper. A execução pode ter ficado HORAS em
    # `aguardando_humano` e só AGORA volta a rodar os passos pós-portão. `iniciada_em` é o
    # piso do heartbeat em `fila.recuperar_execucoes_presas`: sem reiniciá-lo aqui, o sweeper
    # mede o tempo desde ANTES da espera e mata a execução no instante da retomada. O caminho
    # por CANAL (Telegram) roda INLINE, sem passar pelo `_reivindicar` da fila (que já
    # reinicia no worker) — e este é o ponto ÚNICO por onde toda retomada entra em
    # `em_andamento` (mecânico e conversacional, canal e tela). FONTE ÚNICA com o sweeper.
    execucao.iniciada_em = datetime.now(timezone.utc)
    sessao.commit()
    try:
        with usar_chaves(chaves):
            r = executar_cadeia(
                sessao,
                cadeia,
                entrada_proxima,
                frente_inicial=frente,
                # A FICHA atravessa a espera (Onda 2): o que o gatilho trouxe e o que os
                # agentes anotaram ANTES da aprovação continuam valendo depois dela. Era
                # justamente aqui que o dado se perdia — o nó seguinte recebia só o
                # transcript da conversa de aprovação.
                ficha=dict(execucao.dados or {}),
                ordem_inicial=ordem_inicial,
                registrar_passo=_fazer_registrador(sessao, execucao.id, origens),
                # Cancelar voltou a valer DEPOIS do portão: sem este callback, o
                # trecho pós-aprovação era o único do sistema que ignorava o botão
                # "cancelar" (e ele é justamente o trecho que publica).
                cancelado=lambda: _esta_cancelada(sessao, execucao.id),
            )
        _aplicar_resultado(execucao, r)
        if execucao.estado == "aguardando_humano":
            from mensageria import aprovacao
            aprovacao.vincular_pausa(sessao, execucao)
    except Exception as e:
        execucao.estado = "falhou"
        execucao.resultado = {"erro": str(e)}
        execucao.finalizada_em = datetime.now(timezone.utc)
        # Simetria com `disparo.rodar_execucao`: a falha do trecho PÓS-PORTÃO também
        # vai ao banco de logs com stack. Antes ela só existia no `resultado` da
        # execução — invisível para o diagnóstico.
        registrar_evento(
            categoria="execucao", acao="execucao.falhou", nivel="error",
            resultado="falha", erro=e, recurso_tipo="execucao", recurso_id=execucao.id,
            detalhe={"trecho": "pos_portao"},
        )
    sessao.commit()
    sessao.refresh(execucao)
    if execucao.estado == "falhou":
        # Funil único do caminho de erro (Onda 4, fatia 3): avisa e, se for a terceira
        # falha seguida de uma automação que roda sozinha, desliga a automação.
        from orquestracao import circuito

        circuito.apos_falha(
            sessao, execucao, str((execucao.resultado or {}).get("erro") or "")
        )
        sessao.commit()
    return execucao


def retomar_execucao(
    sessao: Session,
    execucao: Execucao,
    resposta: str,
    *,
    chaves: dict,
    origens: dict,
    permitir_conversa: bool = True,
) -> Execucao:
    """Retoma uma execução em `aguardando_humano`.

    O normal é RELIGAR O AGENTE do nó com a resposta da pessoa: ele pediu a aprovação,
    ele continua o trabalho. Se ele pedir de novo (ainda precisa de algo), a execução
    segue esperando; quando concluir, declara os caminhos e o fluxo anda.

    `permitir_conversa=False` (ou nó sem agente, ou teto de idas-e-vindas estourado)
    cai no caminho MECÂNICO: a resposta escolhe a saída sem re-rodar o agente — é o que
    resolve execuções paradas de antes desta virada. Pré-condição: o chamador garantiu
    o estado `aguardando_humano`. Levanta ValueError se não há passo de pausa.
    """
    ultimo, no, no_id, cadeia, idx = localizar_no_pausado(sessao, execucao)
    # Só as saídas CONDICIONAIS entram na decisão: as de erro e "senão" são do MOTOR
    # (uma é acionada pela falha do nó, a outra pela ausência de condição atendida) e
    # não podem virar opção de escolha para a pessoa nem para o agente do portão.
    saidas, _, _ = grafo.separar_saidas(no.get("saidas"))

    # Teto de idas-e-vindas com a pessoa neste passo: DERIVADO da config (Tipo de
    # fluxo < ajuste do nó), com o fixo `MAX_RODADAS_GATE` como default. Sem teto, um
    # agente que pede aprovação a cada rodada conversaria para sempre.
    auto = sessao.get(Automacao, execucao.automacao_id)
    max_rodadas = com_ajuste_do_no(config_da_automacao(auto), no).get(
        "portao_max_rodadas", MAX_RODADAS_GATE
    )

    if (
        permitir_conversa
        and no.get("ref")
        and rodadas_no_gate(sessao, execucao.id, no_id) < max_rodadas
    ):
        return _retomar_conversando_tela(
            sessao, execucao, resposta,
            ultimo=ultimo, cadeia=cadeia, idx=idx, no=no, saidas=saidas,
            chaves=chaves, origens=origens,
        )

    # Mecânico: a RESPOSTA escolhe a saída.
    if len(saidas) == 0:
        escolhida = None
    elif len(saidas) == 1:
        escolhida = saidas[0]
    else:
        with usar_chaves(chaves):
            escolhida, _ = _escolher_saida(resposta, saidas)
    entrada_proxima = entrada_retomada((ultimo.saida or {}).get("texto", ""), resposta)
    return avancar_apos_gate(
        sessao, execucao, idx=idx, cadeia=cadeia,
        escolhidas=[escolhida] if escolhida else [],
        entrada_proxima=entrada_proxima, ordem_inicial=ultimo.ordem,
        chaves=chaves, origens=origens,
    )


def _retomar_conversando_tela(
    sessao: Session,
    execucao: Execucao,
    resposta: str,
    *,
    ultimo: PassoExecucao,
    cadeia: dict,
    idx,
    no: dict,
    saidas: list[dict],
    chaves: dict,
    origens: dict,
) -> Execucao:
    """Religa o agente do nó com a resposta da pessoa (encadeando o histórico do
    passo). Três desfechos: ele PEDE APROVAÇÃO de novo (segue esperando, com o novo
    pedido no rastro), ele declara um ou mais ramos (o fluxo anda), ou ele não declara
    nada (segue esperando — está conversando)."""
    agente = sessao.get(Agente, uuid.UUID(str(no.get("ref"))))
    no_id = ultimo.no_id or (str(ultimo.agente_id) if ultimo.agente_id else None)
    entrada_rerun = (
        f"{(ultimo.entrada or {}).get('texto', '')}\n\n"
        f"{(ultimo.saida or {}).get('texto', '')}\n\n"
        f"---\n[Resposta do humano]\n{resposta}"
    ).strip()

    # MEMÓRIA da espera: o agente não "renasce" a cada rodada. Um checkpointer +
    # thread próprio da execução (`execucao:nó`) guarda o fio. Na 1ª retomada (sem
    # estado) SEMEIA com o `entrada_rerun` (o apresentado + a resposta); nas rodadas
    # seguintes a entrada é SÓ a resposta da pessoa — o agente lembra o resto, então
    # NÃO refaz o que já fez antes de pedir a aprovação. Sem checkpointer → modo
    # LEGADO (sempre `entrada_rerun`), com o risco de repetição que o carimbo denuncia.
    ckpt = memoria_conversa.obter()
    memoria = ckpt is not None and no_id is not None
    tid = f"{execucao.id}:{no_id}" if memoria else None
    if memoria and memoria_conversa.tem_estado(tid):
        entrada = f"---\n[Resposta do humano]\n{resposta}"
    else:
        entrada = entrada_rerun
    kwargs_mem = {"checkpointer": ckpt, "thread_id": tid} if memoria else {}

    iniciado = datetime.now(timezone.utc)
    # A ficha da execução acompanha a retomada: o agente a lê (é a fonte que sobreviveu
    # à espera) e pode anotar nela antes de liberar o fluxo.
    ficha_exec = dict(execucao.dados or {})
    with usar_chaves(chaves):
        cinto = _carregar_cinto(sessao, agente.id)
        resultado = executar_agente(
            agente, cinto, entrada, saidas=saidas, ficha=ficha_exec, **kwargs_mem
        )
    finalizado = datetime.now(timezone.utc)
    anotou = [
        nome for nome, _ in (
            ficha_mod.anotar(ficha_exec, campo, valor)
            for campo, valor in (resultado.get("anotacoes") or {}).items()
        ) if nome
    ]
    execucao.dados = dict(ficha_exec)
    # Ele pediu aprovação DE NOVO: a execução continua esperando, agora por este novo
    # pedido (é o canal/destinatário dele que a borda vai amarrar).
    pausa = (resultado.get("aprovacao") or None) if resultado.get("pausado") else None

    saida_texto = resultado["saida"]
    # Fan-out também na retomada: o agente do portão pode liberar VÁRIOS caminhos
    # (aprovar a capa alimenta o Carrossel E o Story). `ramos_escolhidos` é a lista;
    # `ramo_escolhido` fica só como retrocompat de quem devolve um caminho só.
    ramos = list(resultado.get("ramos_escolhidos") or [])
    if not ramos and resultado.get("ramo_escolhido"):
        ramos = [resultado["ramo_escolhido"]]
    por_rotulo = {s["rotulo"]: s for s in saidas if s.get("rotulo")}
    escolhidas = [por_rotulo[r] for r in ramos if r in por_rotulo]
    ordem = ultimo.ordem + 1

    passo = {
        "no_id": ultimo.no_id or (str(ultimo.agente_id) if ultimo.agente_id else None),
        # Espera por humano enquanto ele não decide o caminho (pediu de novo, ou
        # conversou); no turno que decide, é um passo de agente como qualquer outro.
        "tipo": "espera_humano" if (pausa or not escolhidas) else "agente",
        "aprovacao": pausa,
        "agente_id": str(agente.id),
        "agente_nome": agente.nome,
        "entrada": entrada_rerun,
        "saida": saida_texto,
        "instrumentos_acionados": resultado.get("instrumentos_acionados") or [],
        "saida_escolhida": escolhidas[0]["rotulo"] if escolhidas else None,
        "saidas_escolhidas": [s["rotulo"] for s in escolhidas],
        "motivo_ramo": resultado.get("motivo_ramo"),
        "anotou": sorted(anotou),
        "ficha": dict(ficha_exec),
        "uso": list(resultado.get("uso") or []),
        "iniciado_em": iniciado,
        "finalizado_em": finalizado,
    }
    _fazer_registrador(sessao, execucao.id, origens)(passo, ordem)

    if pausa or not escolhidas:
        execucao.estado = "aguardando_humano"
        sessao.commit()
        from mensageria import aprovacao
        aprovacao.vincular_pausa(sessao, execucao)
        sessao.commit()
        sessao.refresh(execucao)
        return execucao

    # O que segue ao próximo nó é SEMPRE o conteúdo APRESENTADO no portão — o que a
    # pessoa viu e aprovou (`ultimo.saida`, o passo pausado) — somado à resposta dela.
    # NUNCA o texto que o agente narra DEPOIS de aprovar ("aprovado, seguindo…"), ainda
    # que ele mande essa confirmação por um canal nesta rodada: a pessoa aprovou o que
    # já estava na tela, não a confirmação. Unifica o critério com o caminho mecânico
    # (acima) e o por canal (`servico._turno_de_portao`, que repassa o histórico — o
    # apresentado está nele). Sem isto, aprovar pela TELA um agente que também confirma
    # pelo Telegram perdia o conteúdo: descia "aprovado!" no lugar do artigo (a falha da
    # execução 132bcaa6, 2026-06-23 — agente que aprova E tagarela no canal na mesma
    # rodada).
    apresentado_aprovado = (ultimo.saida or {}).get("texto", "")
    return avancar_apos_gate(
        sessao, execucao, idx=idx, cadeia=cadeia, escolhidas=escolhidas,
        entrada_proxima=entrada_retomada(apresentado_aprovado, resposta),
        ordem_inicial=ordem, chaves=chaves, origens=origens,
    )
