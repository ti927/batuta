"""Disparo de uma automação — onde uma execução nasce e como ela roda.

Todos os gatilhos (botão manual, agendamento/CRON, webhook) **enfileiram**: criam
a execução no estado `aguardando` (`criar_execucao`) e devolvem na hora. Quem de
fato roda a cadeia é o pool de trabalhadores da fila (`fila.py`), que chama
`rodar_execucao`. Assim muitas execuções simultâneas são organizadas sem travar
(PRODUTO §18, Tarefa 5.3).
"""

import base64
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import storage
from chaves import resolver_chaves_por_time
from modelos import Automacao, Canal, Execucao, PassoExecucao
from orquestracao.agente import usar_imagem_entrada
from orquestracao.cadeia import _DESTINOS_FIM, _escolher_saida, executar_cadeia
from orquestracao.llm import usar_chaves
from orquestracao.modelos_ia import provedor_do_modelo_seguro


def _imagem_da_entrada(execucao: Execucao) -> str | None:
    """Se a execução tem uma imagem anexada (ex.: recibo que chegou pelo canal),
    baixa do Storage e devolve como data URI para o agente ler. None se não há,
    ou se o download falhar (a execução segue só com o texto)."""
    img = (execucao.entrada or {}).get("imagem")
    if not img or not img.get("storage_path"):
        return None
    try:
        conteudo = storage.baixar(img["storage_path"])
    except Exception:
        return None
    media = img.get("media_type", "image/jpeg")
    return f"data:{media};base64,{base64.b64encode(conteudo).decode()}"


def _entrada_retomada(saida_pausada: str, resposta: str) -> str:
    """A entrada do próximo nó ao retomar uma pausa: o trabalho que o agente
    produziu + a decisão/feedback do humano, separados e rotulados."""
    return f"{saida_pausada}\n\n---\n[Resposta do humano]\n{resposta}"


def _fazer_registrador(
    sessao: Session, execucao_id: uuid.UUID, origens: dict[str, str] | None = None
):
    """Callback que grava cada passo da cadeia em `passos_execucao`. `origens`
    (Fases 7.6/7-A) mapeia provedor → origem da chave; cada entrada de `uso` é
    carimbada com a origem do PROVEDOR do seu modelo, registrando de qual chave
    (cliente/consultoria/legado) saiu o consumo — por provedor, já que agentes
    da mesma cadeia podem usar provedores diferentes."""

    def registrar(passo: dict, ordem: int) -> None:
        uso = passo.get("uso") or []
        if origens:
            for e in uso:
                provedor = provedor_do_modelo_seguro(e.get("modelo") or "")
                origem = origens.get(provedor) if provedor else None
                if origem:
                    e.setdefault("origem", origem)
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


def _alvo_da_pausa(
    sessao: Session, execucao: Execucao
) -> tuple[uuid.UUID | None, str | None]:
    """Para onde mandar a pergunta de uma pausa: o nó da pausa pode declarar um
    canal + destinatário fixos (precedência); senão, responde à ORIGEM da execução
    (quando ela nasceu de uma mensagem de canal — Modo B). (None, None) = sem
    canal: a pausa é respondida só pela tela, como sempre."""
    automacao = sessao.get(Automacao, execucao.automacao_id)
    cadeia = (automacao.cadeia if automacao else None) or {}
    ultimo = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()
    if ultimo is not None and ultimo.agente_id is not None:
        no = (cadeia.get("nos") or {}).get(str(ultimo.agente_id)) or {}
        canal_id, destinatario = no.get("canal_id"), no.get("destinatario")
        if canal_id and destinatario:
            try:
                return uuid.UUID(str(canal_id)), str(destinatario)
            except ValueError:
                pass
    if execucao.origem_canal_id and execucao.origem_identificador:
        return execucao.origem_canal_id, execucao.origem_identificador
    return None, None


def _notificar_pausa(sessao: Session, execucao: Execucao, pergunta: str) -> None:
    """Quando um fluxo pausa esperando humano, manda a pergunta pelo canal (se há
    alvo) e registra em quem/por onde a resposta é esperada (Modo A). Best-effort:
    uma falha de canal NÃO derruba a pausa — ela segue respondível pela tela."""
    canal_id, destinatario = _alvo_da_pausa(sessao, execucao)
    if not canal_id or not destinatario:
        return
    canal = sessao.get(Canal, canal_id)
    if canal is None or not canal.ativo:
        return
    from canais import servico as servico_canal  # import tardio: evita ciclo

    try:
        servico_canal.enviar_pelo_canal(
            sessao, canal, destinatario, pergunta, execucao_id=execucao.id
        )
        execucao.aguardando_canal_id = canal_id
        execucao.aguardando_identificador = destinatario
    except Exception:
        pass  # a pergunta não saiu pelo canal; a pausa continua válida (tela)


def _aplicar_resultado(sessao: Session, execucao: Execucao, r: dict) -> None:
    """Aplica à execução o que a cadeia devolveu: pausa, cancelamento ou
    conclusão. Numa pausa, avisa o canal (se houver alvo)."""
    if r["estado"] == "aguardando_humano":
        execucao.estado = "aguardando_humano"  # sem finalizada_em: ainda viva
        _notificar_pausa(sessao, execucao, r.get("pergunta", ""))
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
    imagem = _imagem_da_entrada(execucao)
    try:
        with usar_chaves(chaves), usar_imagem_entrada(imagem):
            r = executar_cadeia(
                sessao,
                (automacao.cadeia if automacao else None) or {},
                entrada,
                registrar_passo=_fazer_registrador(sessao, execucao.id, origens),
                cancelado=lambda: _esta_cancelada(sessao, execucao.id),
            )
        _aplicar_resultado(sessao, execucao, r)
    except Exception as e:  # falha de LLM/rede/cadeia inválida — registra e segue
        execucao.estado = "falhou"
        execucao.resultado = {"erro": str(e)}
        execucao.finalizada_em = datetime.now(timezone.utc)
    sessao.commit()
    sessao.refresh(execucao)
    return execucao


def retomar_execucao(sessao: Session, execucao: Execucao, resposta: str) -> Execucao:
    """Retoma uma execução pausada (espera-por-humano): a RESPOSTA do humano
    escolhe a saída do portão (PRODUTO §14) e a cadeia continua de onde parou.

    Extraído da rota `responder` para ser reusado também pelo canal (Modo A): a
    resposta pode vir da tela OU de uma mensagem que chegou pelo Telegram. Assume
    `execucao.estado == 'aguardando_humano'` (o chamador garante). Levanta
    `ValueError` se não há passo de pausa para retomar. Não audita nem checa papel
    — isso é do chamador."""
    automacao = sessao.get(Automacao, execucao.automacao_id)
    chaves, origens = resolver_chaves_por_time(
        sessao, automacao.time_id if automacao else None
    )

    # Ponto de retomada: derivado do último passo (onde pausou) + a cadeia.
    ultimo = sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao.id)
        .order_by(PassoExecucao.ordem.desc())
    ).first()
    if ultimo is None or ultimo.agente_id is None:
        raise ValueError("Não foi possível retomar: passo de pausa ausente.")

    cadeia = (automacao.cadeia if automacao else None) or {}
    no = (cadeia.get("nos") or {}).get(str(ultimo.agente_id)) or {}
    saidas = no.get("saidas") or []

    # A resposta do humano escolhe o caminho (portão de aprovação).
    if len(saidas) == 0:
        escolhida = None
    elif len(saidas) == 1:
        escolhida = saidas[0]
    else:
        with usar_chaves(chaves):
            escolhida, _ = _escolher_saida(resposta, saidas)
    destino = escolhida.get("destino") if escolhida else None
    proximo = None if destino in _DESTINOS_FIM else destino

    entrada_proxima = _entrada_retomada((ultimo.saida or {}).get("texto", ""), resposta)

    # A pausa foi respondida: limpa a expectativa de resposta por canal.
    execucao.aguardando_canal_id = None
    execucao.aguardando_identificador = None

    # Sem próximo agente (destino fim): encerra com o trabalho + a decisão.
    if proximo is None:
        execucao.estado = "concluida"
        execucao.resultado = {"texto": entrada_proxima}
        execucao.finalizada_em = datetime.now(timezone.utc)
        sessao.commit()
        sessao.refresh(execucao)
        return execucao

    execucao.estado = "em_andamento"
    sessao.commit()
    try:
        with usar_chaves(chaves):
            r = executar_cadeia(
                sessao,
                cadeia,
                entrada_proxima,
                no_inicial=proximo,
                ordem_inicial=ultimo.ordem,
                registrar_passo=_fazer_registrador(sessao, execucao.id, origens),
            )
        _aplicar_resultado(sessao, execucao, r)
    except Exception as e:
        execucao.estado = "falhou"
        execucao.resultado = {"erro": str(e)}
        execucao.finalizada_em = datetime.now(timezone.utc)
    sessao.commit()
    sessao.refresh(execucao)
    return execucao
