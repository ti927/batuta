"""O disjuntor: a automação que falha sozinha várias vezes seguidas se desliga.

Onda 4, fatia 3 — lacuna 27. Até aqui, cada falha avisava (Onda 1), mas ninguém
SOMAVA as falhas. Uma automação agendada podia falhar todo dia, avisando todo dia, e
seguir queimando dinheiro e enchendo o canal para sempre — ou, pior, ninguém abria o
aviso e ela falhava em silêncio. Foi o susto de 2026-09-02: cinco automações de blog
que disparam sozinhas quase passaram a falhar diariamente sem que nada as parasse.

A regra: **três falhas seguidas e a automação sai do ar**, com recado honesto pelo
canal do time (o que quebrou, desde quando, o que fazer). É o mesmo espírito do vigia
dos elos — só que aqui o que se protege é o dinheiro e a paciência de quem opera.

Duas decisões que valem explicação, porque são o que separa um disjuntor útil de um
que atrapalha:

1. **Só conta o que falha SOZINHO.** Disparo manual não entra na conta e nunca desliga
   nada: quem clicou está olhando a tela e vê a falha na hora — desligar a automação
   por baixo dele, no meio de um teste, seria hostil. Conta agendamento, webhook e
   comentário do Instagram, que rodam sem ninguém por perto (`ORIGENS_SOZINHA`).

2. **Falha NOSSA não conta.** Execução morta por reinício do servidor (deploy) ou
   recolhida pelo vigia de execuções presas carrega `interrompida_pelo_batuta` no
   resultado. Sem essa exceção, três deploys em dias seguidos desligariam as
   automações do cliente — e o defeito não era delas.

A contagem é **derivada** das execuções, não um contador guardado. Assim não existe
contador para dessincronizar quando um caminho de falha novo aparecer (o motor tem
três), e o pior caso de esquecer de chamar o disjuntor é ele disparar um pouco mais
tarde — nunca desligar o que não devia. O marco zero é `falhas_contam_desde`, gravado
ao (re)ativar: sem ele, religar uma automação recém-desligada a derrubaria na primeira
falha seguinte, porque as três falhas velhas continuam no histórico.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from modelos import Automacao, Execucao
from observabilidade.escritor import registrar_evento

# Quantas falhas seguidas derrubam a automação.
FALHAS_PARA_DESLIGAR = 3

# Origens em que a automação roda SEM ninguém olhando — as únicas que contam.
ORIGENS_SOZINHA = ("agendamento", "webhook", "comentario_instagram")

# Estados em que a execução já deu seu veredito. `aguardando_humano` fica de fora de
# propósito: ela ainda pode terminar bem.
ESTADOS_COM_VEREDITO = ("concluida", "falhou")

# Quantas execuções recentes basta olhar para decidir (o dobro do teto, com folga).
JANELA = FALHAS_PARA_DESLIGAR * 2


def marcar_interrompida_pelo_batuta(resultado: dict) -> dict:
    """Carimba um resultado de falha como causada pelo próprio Batuta (reinício do
    servidor, vigia de execuções presas). O disjuntor pula essas: o defeito não é da
    automação, e três deploys seguidos não podem desligar o time do cliente."""
    return {**resultado, "interrompida_pelo_batuta": True}


def _foi_nossa_culpa(execucao: Execucao) -> bool:
    return bool((execucao.resultado or {}).get("interrompida_pelo_batuta"))


def falhas_seguidas(sessao: Session, automacao: Automacao) -> int:
    """Quantas execuções automáticas falharam em sequência, da mais recente para trás.

    Para no primeiro sucesso. Ignora o que rodou por disparo manual (tem gente
    olhando) e o que o próprio Batuta interrompeu (deploy/vigia)."""
    recentes = sessao.scalars(
        select(Execucao)
        .where(Execucao.automacao_id == automacao.id)
        .where(Execucao.modo == "fluxo")
        .where(Execucao.estado.in_(ESTADOS_COM_VEREDITO))
        .where(Execucao.origem.in_(ORIGENS_SOZINHA))
        .where(
            Execucao.criado_em > automacao.falhas_contam_desde
            if automacao.falhas_contam_desde is not None
            else True
        )
        .order_by(Execucao.criado_em.desc())
        .limit(JANELA)
    ).all()
    seguidas = 0
    for execucao in recentes:
        if execucao.estado != "falhou":
            break  # um sucesso zera a conta — é o "seguidas" da regra
        if _foi_nossa_culpa(execucao):
            continue  # nem conta nem interrompe a sequência: essa falha não é dela
        seguidas += 1
    return seguidas


def zerar(automacao: Automacao) -> None:
    """Recomeça a contagem. Chamado ao (re)ativar a automação: quem religou já sabe
    das falhas velhas e merece as três chances de novo."""
    automacao.falhas_contam_desde = datetime.now(timezone.utc)
    automacao.desligada_por_falhas_em = None


def _desligar(sessao: Session, automacao: Automacao, quantas: int) -> None:
    automacao.ativa = False
    automacao.desligada_por_falhas_em = datetime.now(timezone.utc)
    sessao.flush()
    registrar_evento(
        categoria="execucao",
        acao="automacao.desligada_por_falhas",
        nivel="error",
        recurso_tipo="automacao",
        recurso_id=automacao.id,
        detalhe={
            "automacao": automacao.nome,
            "falhas_seguidas": quantas,
            "teto": FALHAS_PARA_DESLIGAR,
            "porque": "falhou sozinha vezes demais seguidas — desligada para não "
            "repetir o erro e gastar à toa",
        },
    )


def apos_falha(sessao: Session, execucao: Execucao, erro: str) -> bool:
    """O funil único do caminho de erro do motor: avisa e, se for o caso, desliga.

    Os três lugares onde uma execução termina em `falhou` (a rodada normal, a rodada
    pós-aprovação e a retomada) chamam SÓ esta função — assim aviso e disjuntor nunca
    se separam. Devolve True se a automação foi desligada agora.

    Nunca levanta: quem chama já está no caminho de erro e não pode quebrar por causa
    do aviso ou da contagem. Uma falha AQUI vira evento, nunca silêncio (§12-A)."""
    from mensageria.aviso import avisar_desligada, avisar_falha

    avisar_falha(sessao, execucao, erro)
    try:
        if execucao is None or execucao.modo == "conversa":
            return False
        if execucao.origem not in ORIGENS_SOZINHA:
            return False  # disparo manual: quem clicou está vendo a falha
        automacao = sessao.get(Automacao, execucao.automacao_id)
        if automacao is None or not automacao.ativa:
            return False
        quantas = falhas_seguidas(sessao, automacao)
        if quantas < FALHAS_PARA_DESLIGAR:
            return False
        _desligar(sessao, automacao, quantas)
        avisar_desligada(sessao, execucao, automacao, quantas)
        return True
    except Exception as e:  # o disjuntor nunca derruba o caminho de erro que o chamou
        registrar_evento(
            categoria="execucao",
            acao="disjuntor.quebrou",
            nivel="error",
            resultado="falha",
            erro=e,
            recurso_tipo="execucao",
            recurso_id=getattr(execucao, "id", None),
        )
        return False
