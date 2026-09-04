"""Batimento dos vigias periódicos — quem vigia os vigias.

As Ondas 3 e 4 do motor criaram um padrão: **execução que pausa e é solta por um
vigia**. Uma execução parada num passo "Esperar" volta porque
`fila.soltar_esperas_vencidas` a devolve à fila; uma parada num "Chamar outra
automação" volta porque `sub_fluxo.soltar_chamadores_concluidos` a devolve. São jobs
periódicos do agendador.

O buraco que este módulo fecha: **`agendador.esta_saudavel()` só diz que o relógio
está girando** (`_scheduler.running`) — não que um job específico esteja disparando.
Se um deles passar a levantar exceção a cada volta, o `/saude` continua respondendo
`agendador: true`, a página `/status` fica verde, e execuções se acumulam paradas para
sempre. Falha silenciosa clássica, e das caras: o usuário vê "aguardando o tempo" numa
tela que promete que ela volta sozinha.

É a §12-A aplicada um nível acima. A lei diz que nenhum estado "em andamento" pode
ficar sem quem o varra; quando a varredura vira a peça de que tudo depende, **nenhum
vigia pode ficar sem quem o vigie**.

O mecanismo é o mesmo que já provou valor no vigia das conversas
(`mensageria/sweeper.py::ULTIMA_VARREDURA_EM`), só que generalizado: cada job carimba
a hora em que rodou, e uma sonda de `saude_elos` compara com o que se espera dele.
Um mecanismo, três carimbadores, uma sonda — em vez de três timestamps soltos que um
dia divergem.
"""

from datetime import datetime, timezone

# Quando cada vigia rodou pela última vez. Vazio no boot: até a primeira volta, a
# sonda reporta "aguardando", não "quebrado" — um app que acabou de subir não tem
# atraso nenhum a explicar.
BATIMENTOS: dict[str, datetime] = {}

# O que se espera de cada vigia: (nome legível, de quanto em quanto tempo roda, e a
# partir de quanto tempo sem bater ele está quebrado — em segundos).
#
# A tolerância é FOLGADA de propósito (ordens de grandeza acima do período): o que
# queremos pegar é o vigia MORTO, não o que atrasou meio minuto porque o banco estava
# lento. Alarme que dispara à toa é alarme que ninguém lê — e aí a página de status
# perde a única serventia que tem.
VIGIAS: dict[str, tuple[str, int, int]] = {
    "esperas": ("as esperas do passo Esperar", 30, 300),
    "sub_fluxos": ("os sub-fluxos do passo Chamar outra automação", 30, 300),
    "presas": ("as execuções travadas", 120, 600),
}


def bateu(nome: str) -> None:
    """Carimba que este vigia acabou de rodar. Chamado no FIM do job — bater na
    entrada diria só que ele começou, e um job que trava no meio continuaria
    parecendo saudável, que é exatamente o modo de falha que isto persegue."""
    BATIMENTOS[nome] = datetime.now(timezone.utc)


def atraso_s(nome: str) -> float | None:
    """Há quantos segundos este vigia não roda. `None` = nunca rodou desde o boot."""
    ultima = BATIMENTOS.get(nome)
    if ultima is None:
        return None
    return (datetime.now(timezone.utc) - ultima).total_seconds()


def quebrados() -> list[tuple[str, float]]:
    """Os vigias que passaram da tolerância: [(nome, atraso em segundos)], do mais
    atrasado para o menos. Vazio quando está tudo em dia."""
    fora = [
        (nome, a)
        for nome, (_, _, tolerancia) in VIGIAS.items()
        if (a := atraso_s(nome)) is not None and a > tolerancia
    ]
    return sorted(fora, key=lambda x: x[1], reverse=True)


def nunca_rodaram() -> list[str]:
    """Os vigias que ainda não rodaram nenhuma vez desde o boot."""
    return [nome for nome in VIGIAS if nome not in BATIMENTOS]


def frase_do_atraso(nome: str, atraso: float) -> str:
    """O recado sobre UM vigia atrasado, dizendo o que parou de funcionar por causa
    dele — quem lê a página de status precisa saber a consequência, não o nome
    interno de um job."""
    rotulo, periodo, _ = VIGIAS.get(nome, (nome, 0, 0))
    quanto = f"{int(atraso // 60)} min" if atraso >= 120 else f"{int(atraso)} s"
    return f"o vigia que solta {rotulo} não roda há {quanto} (deveria ser a cada {periodo} s)"


def resumo_em_dia() -> str:
    """A frase do elo quando está tudo certo: o vigia mais atrasado dos três, que é o
    pior caso do conjunto."""
    atrasos = [(n, a) for n in VIGIAS if (a := atraso_s(n)) is not None]
    if not atrasos:
        return "aguardando a primeira volta"
    nome, pior = max(atrasos, key=lambda x: x[1])
    rotulo = VIGIAS[nome][0]
    return f"todos em dia (o mais antigo: {rotulo}, há {int(pior)} s)"
