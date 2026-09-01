"""A espera por uma pessoa carrega adiante o que foi APRESENTADO a ela.

Conserto 2026-06-18 (execução `7f020c5a`): ao parar para um humano, o conteúdo que
segue — e o que fica no passo — não pode ser o status que o agente narra ("Enviei
para aprovação, aguardando…"), e sim o que a pessoa de fato viu. Sem isto o conteúdo
aprovado se perdia (o artigo ficava só no Telegram) e o próximo agente recebia só
"aviso + aprovado".

Desde 2026-08-31 quem apresenta é o INSTRUMENTO `pedir_aprovacao`, chamado pelo
agente: a mensagem que ele passa ali É o apresentado, então o conteúdo certo segue
por construção. Cobre os três níveis:
- agente: a captura por canal (`_ferramenta_unica` registra a mensagem enviada) e a
  pausa registrada quando o instrumento para para uma pessoa;
- cadeia: a execução vira `aguardando_humano` com a mensagem do pedido;
- retomada: o conteúdo apresentado + a resposta seguem para o próximo nó.
"""

import uuid

import instrumentos as encaixe
import orquestracao.agente as agente_mod
import orquestracao.cadeia as motor
from mensageria import retoma
from modelos import Agente, Automacao, Execucao, Instrumento, PassoExecucao


# ───────────────────── nível do agente: a captura por canal ─────────────────────

def test_envio_por_canal_registra_a_mensagem_apresentada(monkeypatch):
    tg = encaixe.obter_tipo("enviar_telegram")
    inst = Instrumento(
        time_id=uuid.uuid4(), nome="Canal", tipo="enviar_telegram",
        configuracao={"token_bot": "x"},
    )
    inst.id = uuid.uuid4()
    # Não falamos com o Telegram de verdade: o acionar devolve sucesso.
    monkeypatch.setattr(
        agente_mod, "acionar_com_retentativa", lambda t, c, a: {"ok": True, "status": 200}
    )
    enviadas: dict[str, list[str]] = {}
    tool = agente_mod._ferramenta_unica(
        inst, tg, tg.Config.model_validate({"token_bot": "x"}), [], enviadas, [], {}
    )
    tool.func(destinatario="123", mensagem="ARTIGO COMPLETO REVISADO")
    assert enviadas == {str(inst.id): ["ARTIGO COMPLETO REVISADO"]}


def test_instrumento_sem_campo_mensagem_nao_registra(monkeypatch):
    # busca_web não apresenta mensagem a humano (campo_mensagem None) → nada a carregar.
    busca = encaixe.obter_tipo("busca_web")
    inst = Instrumento(
        time_id=uuid.uuid4(), nome="Busca", tipo="busca_web", configuracao={}
    )
    inst.id = uuid.uuid4()
    monkeypatch.setattr(
        agente_mod, "acionar_com_retentativa", lambda t, c, a: {"resultados": []}
    )
    enviadas: dict[str, list[str]] = {}
    tool = agente_mod._ferramenta_unica(inst, busca, busca.Config(), [], enviadas, [], {})
    tool.func(consulta="reforma tributária")
    assert enviadas == {}


def test_pedir_aprovacao_registra_a_pausa_e_o_apresentado(monkeypatch):
    """O instrumento que PARA para uma pessoa registra o pedido — é o que a borda lê
    para transformar o turno numa espera."""
    tipo = encaixe.obter_tipo("pedir_aprovacao")
    inst = Instrumento(
        time_id=uuid.uuid4(), nome="Aprovação", tipo="pedir_aprovacao",
        configuracao={"canal_instrumento_id": ""},
    )
    inst.id = uuid.uuid4()
    monkeypatch.setattr(
        agente_mod, "acionar_com_retentativa",
        lambda t, c, a: {
            "ok": True, "aguardando_aprovacao": True, "onde": "canal",
            "mensagem": a.mensagem, "canal_instrumento_id": "c1", "destinatario": "999",
        },
    )
    pedido: dict = {}
    tool = agente_mod._ferramenta_unica(
        inst, tipo, tipo.Config(), [], {}, [], pedido
    )
    tool.func(mensagem="ARTIGO COMPLETO REVISADO")
    assert pedido["mensagem"] == "ARTIGO COMPLETO REVISADO"
    assert pedido["canal_instrumento_id"] == "c1"
    assert pedido["destinatario"] == "999"


def test_depois_de_pedir_aprovacao_nada_mais_roda(monkeypatch):
    """O agente pediu e está esperando: agir agora seria fazer justamente o que ele
    foi mandado confirmar antes."""
    tg = encaixe.obter_tipo("enviar_telegram")
    inst = Instrumento(
        time_id=uuid.uuid4(), nome="Canal", tipo="enviar_telegram",
        configuracao={"token_bot": "x"},
    )
    inst.id = uuid.uuid4()
    chamou = {"n": 0}

    def acionar(t, c, a):
        chamou["n"] += 1
        return {"ok": True}

    monkeypatch.setattr(agente_mod, "acionar_com_retentativa", acionar)
    tool = agente_mod._ferramenta_unica(
        inst, tg, tg.Config.model_validate({"token_bot": "x"}), [], {}, [],
        {"mensagem": "já pedi"},
    )
    import json
    assert json.loads(tool.func(destinatario="1", mensagem="oi"))["ok"] is False
    assert chamou["n"] == 0


# ───────────── nível da cadeia: o pedido do agente vira a espera ─────────────

def _ag(sessao, dados, nome):
    a = Agente(time_id=dados["timeA"].id, nome=nome, papel="agente")
    sessao.add(a)
    sessao.flush()
    return a


def _mock_pediu_aprovacao(monkeypatch, *, mensagem, canal_id=None, saida=None):
    """`executar_agente` que devolve um turno terminado em PEDIDO DE APROVAÇÃO."""
    def fake(agente, cinto, entrada, **kwargs):
        return {
            "pausado": True,
            "aprovacao": {
                "mensagem": mensagem,
                "instrumento_id": "i1",
                "canal_instrumento_id": canal_id,
                "destinatario": "999" if canal_id else None,
            },
            "saida": saida or mensagem,
            "instrumentos_acionados": ["pedir_aprovacao"],
            "uso": [],
            "mensagens_enviadas": {},
            "ramos_escolhidos": [],
        }
    monkeypatch.setattr(motor, "executar_agente", fake)


def _cadeia_simples(ref):
    return {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": ref,
             "saidas": [
                 {"rotulo": "aprovado", "quando": "aprovou", "destino": "fim"},
                 {"rotulo": "reprovado", "quando": "pediu ajuste", "destino": "rev"},
             ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }


def test_pedido_do_agente_pausa_a_execucao(sessao, dados, monkeypatch):
    rev = _ag(sessao, dados, "Revisor")
    _mock_pediu_aprovacao(
        monkeypatch, mensagem="ARTIGO COMPLETO REVISADO", canal_id="c1",
        # o agente ainda narra um status — que NÃO pode ser o que segue adiante
        saida="ARTIGO COMPLETO REVISADO",
    )
    r = motor.executar_cadeia(sessao, _cadeia_simples(str(rev.id)), "vai")
    assert r["estado"] == "aguardando_humano"
    assert r["pergunta"] == "ARTIGO COMPLETO REVISADO"
    assert r["passos"][-1]["saida"] == "ARTIGO COMPLETO REVISADO"
    # o passo é uma espera por humano e leva o canal por onde o pedido saiu
    assert r["passos"][-1]["tipo"] == "espera_humano"
    assert r["passos"][-1]["aprovacao"]["canal_instrumento_id"] == "c1"
    # e NÃO decidiu caminho nenhum: quem decide é a resposta da pessoa
    assert r["passos"][-1]["saidas_escolhidas"] == []


def test_pedido_so_de_tela_tambem_pausa(sessao, dados, monkeypatch):
    """Sem canal configurado, a aprovação acontece na tela da execução."""
    rev = _ag(sessao, dados, "RevisorTela")
    _mock_pediu_aprovacao(monkeypatch, mensagem="Proposta exibida na tela")
    r = motor.executar_cadeia(sessao, _cadeia_simples(str(rev.id)), "vai")
    assert r["estado"] == "aguardando_humano"
    assert r["pergunta"] == "Proposta exibida na tela"
    assert r["passos"][-1]["aprovacao"]["canal_instrumento_id"] is None


def test_sem_pedido_o_fluxo_nao_para(sessao, dados, monkeypatch):
    """O contraste que prova a regra: sem o agente pedir, ninguém segura o fluxo —
    não existe mais interruptor no desenho que pause por ele."""
    rev = _ag(sessao, dados, "RevisorSemPedido")

    def fake(agente, cinto, entrada, **kwargs):
        return {
            "pausado": False, "saida": "pronto", "instrumentos_acionados": [],
            "uso": [], "mensagens_enviadas": {}, "ramos_escolhidos": ["aprovado"],
        }

    monkeypatch.setattr(motor, "executar_agente", fake)
    r = motor.executar_cadeia(sessao, _cadeia_simples(str(rev.id)), "vai")
    assert r["estado"] == "concluida"


# ───────────────────── retomada ponta-a-ponta ─────────────────────

def test_retomada_entrega_o_conteudo_apresentado_mais_a_resposta(sessao, dados):
    """Com o passo da espera guardando o conteúdo apresentado (como a cadeia agora
    produz), retomar com 'aprovado' faz esse conteúdo + a resposta seguirem adiante."""
    ag = _ag(sessao, dados, "RevisorRetoma")
    cadeia = {
        "inicial": "rev",
        "nos": [
            {"id": "rev", "tipo": "agente", "ref": str(ag.id),
             "saidas": [{"rotulo": "ok", "destino": "fim"}]},  # destino fim → conclui
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia=cadeia, ativa=False,
    )
    sessao.add(auto)
    sessao.flush()
    execucao = Execucao(
        automacao_id=auto.id, estado="aguardando_humano", entrada={"texto": "x"}
    )
    sessao.add(execucao)
    sessao.flush()
    sessao.add(
        PassoExecucao(
            execucao_id=execucao.id, ordem=1, agente_id=ag.id, no_id="rev",
            entrada={"texto": "x"},
            saida={
                "texto": "ARTIGO COMPLETO REVISADO",  # o que a cadeia agora carrega
                "instrumentos_acionados": [], "saida_escolhida": None, "uso": [],
            },
            estado="concluido",
        )
    )
    sessao.flush()

    retoma.retomar_execucao(
        sessao, execucao, "aprovado", chaves={}, origens={}, permitir_conversa=False
    )

    sessao.refresh(execucao)
    assert execucao.estado == "concluida"
    texto = execucao.resultado["texto"]
    assert "ARTIGO COMPLETO REVISADO" in texto  # o conteúdo aprovado seguiu
    assert "aprovado" in texto  # com a resposta do humano anexada
