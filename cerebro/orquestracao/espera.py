"""O prazo de uma espera por humano — e o vigia que ela nunca teve (§4.2 de
`docs/FALHAS-DO-MOTOR.md`).

A lei §12-A diz que nenhum estado "em andamento" pode ficar sem quem o varra. Havia uma
exceção, e ninguém tinha percebido: `aguardando_humano`.

Todos os outros estados têm vigia. `em_andamento` tem dois (o do boot e o das presas).
`aguardando_tempo` tem `fila.soltar_esperas_vencidas`. `aguardando_sub_fluxo` tem
`sub_fluxo.soltar_chamadores_concluidos`. Uma conversa parada tem o sweeper de mensageria.
Mas a espera por aprovação em si não tinha nenhum — porque o relógio dela morava na
CONVERSA (`conversas.aguardando_ate`), e não na execução. Consequência: uma aprovação
pedida só pela tela, sem canal amarrado, ficava parada **para sempre, em silêncio**. E
mesmo com canal, a ação padrão de abandono é "estacionar" — que mantém a execução parada
de propósito, retomável, e também sem ninguém para notar que ela envelheceu.

O que este vigia faz — e o que ele deliberadamente NÃO faz. Ele **não encerra** a
execução. Esperar dias por uma aprovação é legítimo: quem aprova viaja, dorme, tem
segunda-feira de manhã. Matar o trabalho por isso seria trocar um silêncio por um
prejuízo. O que ele faz é acabar com o silêncio: um evento de erro no banco de logs e um
recado no canal do time, uma vez, dizendo há quanto tempo aquilo está parado e onde
resolver. Depois disso a execução continua exatamente onde estava, respondível.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from modelos import Automacao, Execucao
from observabilidade.escritor import registrar_evento

logger = logging.getLogger("batuta.espera")


def prazo_min(automacao: Automacao | None) -> int:
    """Minutos parada até esta espera virar alarme. Zero = nunca avisar.

    Lê a MESMA cascata do resto do comportamento do fluxo (global < perfil < ajustes do
    fluxo), para não virar mais uma fonte de verdade — e para o limite ficar VISÍVEL no
    painel de configuração, como manda a lei dos limites (teto secreto é proibido)."""
    from mensageria.config import config_da_automacao

    try:
        return max(0, int(config_da_automacao(automacao).get("teto_espera_humano_min") or 0))
    except (TypeError, ValueError):
        return 0  # valor estragado na config não pode cegar o vigia nem derrubar a pausa


def marcar(sessao: Session, execucao: Execucao) -> None:
    """Carimba quando ESTA espera vira motivo de alarme. Chamada em todo caminho que põe
    a execução em `aguardando_humano` — a apresentação inicial, a re-apresentação pela
    tela e a pelo canal. Não comita.

    À prova de falha: uma exceção aqui não pode derrubar a pausa (o trabalho já foi feito,
    e perder a execução por causa do relógio dela seria absurdo)."""
    try:
        auto = sessao.get(Automacao, execucao.automacao_id)
        minutos = prazo_min(auto)
        execucao.espera_ate = (
            datetime.now(timezone.utc) + timedelta(minutes=minutos) if minutos else None
        )
    except Exception:
        logger.exception("Falha ao marcar o prazo da espera de %s", execucao.id)


def _texto(execucao: Execucao, automacao: Automacao | None, parada_min: int) -> str:
    horas = parada_min / 60
    ha_quanto = f"{horas:.0f} h" if horas >= 1 else f"{parada_min} min"
    return (
        f"⏳ A automação *{(automacao.nome if automacao else 'sem nome')}* está parada há "
        f"{ha_quanto} esperando uma aprovação que ninguém respondeu.\n\n"
        "Nada se perdeu e nada foi encerrado — o trabalho já feito está guardado e o "
        "fluxo continua de onde parou assim que alguém responder.\n\n"
        f"Abra a execução no batuta.team para aprovar, reprovar ou cancelar."
    )


def varrer_esquecidas(sessao: Session) -> int:
    """Avisa, UMA vez, sobre cada espera por humano que passou do prazo. Devolve quantas.

    Depois de avisar, zera `espera_ate`: um alarme honesto, não um despertador que toca a
    cada dois minutos para sempre. Alarme que repete sem novidade é alarme que ninguém
    lê — e aí a página de status perde a única serventia que tem."""
    agora = datetime.now(timezone.utc)
    esquecidas = sessao.scalars(
        select(Execucao).where(
            Execucao.estado == "aguardando_humano",
            Execucao.espera_ate.is_not(None),
            Execucao.espera_ate <= agora,
        )
    ).all()
    if not esquecidas:
        # Nada a fazer: NÃO damos rollback. A sessão pode não ser nossa (nos testes é a do
        # caso, numa transação que ainda continua) — mesmo cuidado de `soltar_esperas`.
        return 0

    from mensageria import aviso

    for ex in esquecidas:
        auto = sessao.get(Automacao, ex.automacao_id)
        desde = ex.espera_ate - timedelta(minutes=prazo_min(auto) or 0)
        parada_min = max(0, int((agora - desde).total_seconds() // 60))
        registrar_evento(
            categoria="execucao",
            acao="espera.esquecida",
            nivel="error",
            resultado="falha",
            persistir=True,
            recurso_tipo="execucao",
            recurso_id=ex.id,
            detalhe={
                "automacao": auto.nome if auto else None,
                "parada_min": parada_min,
                "efeito": "a execução segue viva e respondível; só o silêncio acabou",
            },
        )
        try:
            aviso.avisar_time(
                sessao, ex, _texto(ex, auto, parada_min), acao="espera_esquecida"
            )
        except Exception:  # o aviso nunca derruba o vigia — mas também não some
            logger.exception("Falha ao avisar a espera esquecida de %s", ex.id)
        ex.espera_ate = None  # avisado uma vez; a execução continua onde estava
    sessao.commit()
    logger.warning("%d espera(s) esquecida(s) avisada(s).", len(esquecidas))
    return len(esquecidas)


def varrer_esquecidas_job() -> None:
    """Entrada do agendador: abre a própria sessão e carimba o batimento no FIM — sem o
    carimbo, um vigia que passasse a levantar exceção a cada volta continuaria parecendo
    saudável (`vigias.py`)."""
    import vigias
    from sessao import CriadorDeSessao

    sessao = CriadorDeSessao()
    try:
        varrer_esquecidas(sessao)
        vigias.bateu("esperas_humanas")
    finally:
        sessao.close()
