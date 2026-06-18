"""Aprovação de execução por canal (Telegram), coexistindo com a tela.

Quando uma execução pausa num portão (`pausa_humano`) e a automação tem um CANAL
DE APROVAÇÃO, a borda amarra a conversa do aprovador à execução
(`Conversa.execucao_id`); a resposta de entrada dele religa o fluxo pela MESMA
mecânica da tela (`retoma`). A tela continua valendo — vale a primeira resposta.

Estes testes cobrem o vínculo na pausa, o roteamento da resposta de entrada para
a retoma (em vez do modo conversacional) e a limpeza do vínculo. Núcleo de
orquestração intocado.
"""

from sqlalchemy import select

import segredos_instrumento as si
from mensageria import aprovacao, servico, telegram
from modelos import (
    Agente,
    Automacao,
    Conversa,
    Execucao,
    Instrumento,
    MensagemConversa,
    PassoExecucao,
)


class _SessaoFake:
    """Reusa a sessão do teste (transação revertida) mas ignora `close()`, para o
    `processar_turno` (que abre a própria sessão) operar sobre os mesmos dados."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


def _canal(sessao, dados, destinatario="555", nome="Bot aprovador"):
    inst = Instrumento(
        time_id=dados["timeA"].id,
        nome=nome,
        tipo="enviar_telegram",
        configuracao={"destinatario_padrao": destinatario, "saudacao_abertura": ""},
    )
    sessao.add(inst)
    sessao.flush()
    return inst


def _agente(sessao, dados, nome="Revisor"):
    ag = Agente(time_id=dados["timeA"].id, nome=nome, papel="agente")
    sessao.add(ag)
    sessao.flush()
    return ag


# Id do nó com portão usado nos testes (a config de aprovação vive nele).
NO_GATE = "rev"


def _automacao(sessao, dados, agente, *, canal=None, destino=None, destinatario="555"):
    """Automação de um nó com portão (gate) e uma única saída — destino None encerra
    ao retomar (sem rodar a cadeia/LLM). A config de aprovação por canal vive no NÓ
    (`no.aprovacao = {instrumento_id, destinatario}`), não mais na automação."""
    no = {
        "id": NO_GATE,
        "tipo": "agente",
        "ref": str(agente.id),
        "gate": True,
        "saidas": [{"id": "s0", "rotulo": "ok", "quando": "sempre", "destino": destino or "fim"}],
    }
    if canal is not None:
        no["aprovacao"] = {"instrumento_id": str(canal.id), "destinatario": destinatario}
    cadeia = {"inicial": NO_GATE, "nos": [no]}
    auto = Automacao(
        time_id=dados["timeA"].id,
        nome="Fluxo",
        tipo_gatilho="manual",
        configuracao_gatilho={},
        cadeia=cadeia,
        ativa=False,
    )
    sessao.add(auto)
    sessao.flush()
    return auto


def _conversa_da_execucao(sessao, execucao_id):
    """A conversa amarrada a uma execução (o banco de testes é o real e já tem
    outras conversas — por isso a busca é escopada por `execucao_id`)."""
    return sessao.scalars(
        select(Conversa).where(Conversa.execucao_id == execucao_id)
    ).first()


def _exec_pausada(sessao, auto, agente, texto="Artigo para aprovar"):
    execucao = Execucao(
        automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"}
    )
    sessao.add(execucao)
    sessao.flush()
    sessao.add(
        PassoExecucao(
            execucao_id=execucao.id,
            ordem=1,
            agente_id=agente.id,
            no_id=NO_GATE,  # a aprovação por canal é lida do nó pausado
            entrada={"texto": "x"},
            saida={
                "texto": texto,
                "instrumentos_acionados": [],
                "saida_escolhida": None,
                "uso": [],
            },
            estado="concluido",
        )
    )
    sessao.flush()
    return execucao


# ─────────────────────────── vínculo na pausa ───────────────────────────

def test_vincular_pausa_amarra_conversa_do_aprovador(sessao, dados):
    canal = _canal(sessao, dados, destinatario="555")
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal=canal)
    execucao = _exec_pausada(sessao, auto, ag)

    aprovacao.vincular_pausa(sessao, execucao)

    conv = sessao.scalars(
        select(Conversa).where(Conversa.instrumento_id == canal.id)
    ).first()
    assert conv is not None
    assert conv.contato_chave == "555"
    assert conv.execucao_id == execucao.id


def _msgs_agente(sessao, conversa_id):
    return sessao.scalars(
        select(MensagemConversa)
        .where(MensagemConversa.conversa_id == conversa_id)
        .where(MensagemConversa.papel == "agente")
    ).all()


def test_vincular_pausa_registra_o_apresentado_na_thread(sessao, dados):
    """O que o agente apresentou ao humano (o pedido de aprovação) passa a aparecer
    na thread de Conversas — antes só vivia em memória e sumia."""
    canal = _canal(sessao, dados, destinatario="555")
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal=canal)
    execucao = _exec_pausada(sessao, auto, ag, texto="Artigo para aprovar")

    aprovacao.vincular_pausa(sessao, execucao)

    conv = _conversa_da_execucao(sessao, execucao.id)
    msgs = _msgs_agente(sessao, conv.id)
    assert len(msgs) == 1
    assert msgs[0].conteudo == "Artigo para aprovar"


def test_vincular_pausa_nao_duplica_o_apresentado(sessao, dados):
    canal = _canal(sessao, dados, destinatario="555")
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal=canal)
    execucao = _exec_pausada(sessao, auto, ag)

    aprovacao.vincular_pausa(sessao, execucao)
    aprovacao.vincular_pausa(sessao, execucao)  # 2ª chamada (mesma pausa) não duplica

    conv = _conversa_da_execucao(sessao, execucao.id)
    assert len(_msgs_agente(sessao, conv.id)) == 1


def test_vincular_pausa_sem_canal_nao_grava_mensagem(sessao, dados):
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal=None)  # só tela
    execucao = _exec_pausada(sessao, auto, ag)

    aprovacao.vincular_pausa(sessao, execucao)

    # sem canal não há conversa, logo nada a gravar
    assert _conversa_da_execucao(sessao, execucao.id) is None


def test_vincular_pausa_sem_destinatario_nao_amarra(sessao, dados):
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal=canal, destinatario="")  # nó sem destinatário
    execucao = _exec_pausada(sessao, auto, ag)

    aprovacao.vincular_pausa(sessao, execucao)

    # Escopado à execução do teste: o banco de testes é o real e já tem conversas.
    assert _conversa_da_execucao(sessao, execucao.id) is None


def test_vincular_pausa_sem_canal_de_aprovacao_e_noop(sessao, dados):
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal=None)  # só tela
    execucao = _exec_pausada(sessao, auto, ag)

    aprovacao.vincular_pausa(sessao, execucao)

    assert _conversa_da_execucao(sessao, execucao.id) is None


def test_desvincular_limpa_o_vinculo(sessao, dados):
    canal = _canal(sessao, dados)
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal=canal)
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)
    assert _conversa_da_execucao(sessao, execucao.id) is not None

    aprovacao.desvincular(sessao, execucao.id)

    assert _conversa_da_execucao(sessao, execucao.id) is None
    # A conversa em si continua existindo, só sem o vínculo.
    conv = sessao.scalars(
        select(Conversa).where(Conversa.instrumento_id == canal.id)
    ).first()
    assert conv is not None and conv.execucao_id is None


# ──────────────────── roteamento da resposta de entrada ───────────────────

def test_registrar_entrada_roteia_resposta_para_aprovacao(sessao, dados):
    canal = _canal(sessao, dados, destinatario="555")
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal=canal)
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)

    msg = telegram.MensagemEntrante(
        contato_chave="555", contato_nome="Chefe", texto="aprovado", midia=None
    )
    conv, deve_processar = servico.registrar_entrada(sessao, canal, msg)

    # Mesmo sem agente atendente (destino_tipo != 'agente'), processa: é aprovação.
    assert deve_processar is True
    assert conv.execucao_id == execucao.id


def test_aprovacao_pelo_canal_religa_e_conclui_o_fluxo(sessao, dados, monkeypatch):
    enviados = []
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico.telegram,
        "enviar",
        lambda token, chat, texto: enviados.append(texto) or {"ok": True},
    )

    canal = _canal(sessao, dados, destinatario="555")
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok-x"})  # p/ o ack sair
    ag = _agente(sessao, dados)
    auto = _automacao(sessao, dados, ag, canal=canal, destino=None)  # 1 saída → fim
    execucao = _exec_pausada(sessao, auto, ag)
    aprovacao.vincular_pausa(sessao, execucao)

    msg = telegram.MensagemEntrante(
        contato_chave="555", contato_nome="Chefe", texto="aprovado", midia=None
    )
    conv, deve_processar = servico.registrar_entrada(sessao, canal, msg)
    assert deve_processar
    servico.processar_turno(conv.id)

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"  # a resposta religou e encerrou o fluxo
    assert enviados  # confirmação enviada ao aprovador
    sessao.refresh(conv)
    assert conv.execucao_id is None  # vínculo desfeito ao concluir
