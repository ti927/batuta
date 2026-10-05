"""Aprovação sob COMBINAÇÕES de eventos — tela, Telegram, fila, em qualquer ordem.

Os testes de exemplo testam um cenário de cada vez; o motor quebra quando duas coisas
acontecem juntas (execução f941b1b1, 2026-10-05: quatro mensagens no Telegram em 30 s,
a quarta re-rodou o agente que já tinha decidido). Aqui o Hypothesis SORTEIA sequências
de eventos e confere, depois de cada um, as regras que nunca podem quebrar.

A concorrência é emulada separando o que acontece em dois tempos na vida real:
- a mensagem do Telegram CHEGA (`registrar_entrada`, no request) e só depois é
  PROCESSADA (`_turno_de_portao`, em segundo plano) — entre as duas, qualquer outro
  evento pode acontecer;
- o clique na tela ENFILEIRA (rota `responder`) e só depois o trabalhador RODA.

Cada resposta leva um número (`APROVO#3`); o modelo anota, no instante em que ela foi
dada, QUAL passo a pessoa estava vendo. A regra central:

    uma resposta só pode ser aplicada à pergunta que a pessoa viu ao responder,
    e no máximo uma vez.

O grafo é o do caso real: Capa (aprovação) → Carrossel (outra aprovação) + Story.
`executar_agente` é falso — sem LLM; o resto (borda, motor, banco) é o de verdade.
"""

import itertools
import os
import re
import uuid

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)
from sqlalchemy import func, select

import segredos_instrumento as si
from mensageria import aprovacao, retoma, servico, telegram
from modelos import Agente, Automacao, Execucao, Instrumento, PassoExecucao, PedidoAprovacao
from orquestracao import cadeia as cadeia_mod
from orquestracao import disparo, dono

CONTATO = "555"
DECISOES = ["APROVO", "REPROVO", "PERGUNTA"]


def _montar(sessao, dados):
    canal = Instrumento(
        time_id=dados["timeA"].id, nome="Bot", tipo="enviar_telegram",
        configuracao={"destinatario_padrao": CONTATO, "saudacao_abertura": ""},
    )
    sessao.add(canal)
    sessao.flush()
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})
    capa = Agente(time_id=dados["timeA"].id, nome="Capa", papel="agente")
    carr = Agente(time_id=dados["timeA"].id, nome="Carrossel", papel="agente")
    story = Agente(time_id=dados["timeA"].id, nome="Story", papel="agente")
    sessao.add_all([capa, carr, story])
    sessao.flush()
    cadeia = {
        "inicial": "capa",
        "nos": [
            {"id": "capa", "tipo": "agente", "ref": str(capa.id), "saidas": [
                {"rotulo": "aprovado1", "quando": "aprovou", "destino": "carr"},
                {"rotulo": "aprovado2", "quando": "aprovou", "destino": "story"},
                {"rotulo": "reprovado", "quando": "pediu ajuste", "destino": "capa"},
            ]},
            {"id": "carr", "tipo": "agente", "ref": str(carr.id), "saidas": [
                {"rotulo": "aprovado", "quando": "aprovou", "destino": "fim"},
                {"rotulo": "reprovado", "quando": "pediu ajuste", "destino": "carr"},
            ]},
            {"id": "story", "tipo": "agente", "ref": str(story.id), "saidas": [
                {"rotulo": "ok", "destino": "fim"},
            ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    auto = Automacao(
        time_id=dados["timeA"].id, nome="Posts", tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia=cadeia, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    return canal, auto, {str(capa.id): "capa", str(carr.id): "carr", str(story.id): "story"}


class _Cenario:
    """O estado compartilhado entre o agente falso e a máquina de estados."""

    def __init__(self, canal_id, nos_por_agente):
        self.canal_id = canal_id
        self.nos_por_agente = nos_por_agente
        self.contador = itertools.count(1)
        self.execucoes_do_agente: list[tuple[str, int]] = []  # (nó, nº da resposta)

    def agente(self, *, resposta: bool):
        def fake(agente, cinto, entrada, **kwargs):
            no = self.nos_por_agente[str(agente.id)]
            texto = str(entrada)
            if not resposta:
                if no == "story":
                    return _sem_pausa("STORY")
                return self._pausa(no)
            achados = list(re.finditer(r"(APROVO|REPROVO|PERGUNTA)#(\d+)", texto))
            decisao, n = (achados[-1].group(1), int(achados[-1].group(2))) if achados else (None, 0)
            self.execucoes_do_agente.append((no, n))
            if decisao == "APROVO":
                return _sem_pausa("ok", ["aprovado1", "aprovado2"] if no == "capa" else ["aprovado"])
            if decisao == "REPROVO":
                return self._pausa(no)
            return _sem_pausa("Pode explicar melhor?")
        return fake

    def _pausa(self, no):
        n = next(self.contador)
        return {
            "saida": f"MATERIAL {no} v{n}", "instrumentos_acionados": ["pedir_aprovacao"],
            "uso": [], "mensagens_enviadas": {}, "pausado": True,
            "aprovacao": {
                "mensagem": f"MATERIAL {no} v{n}", "codigo": uuid.uuid4().hex[:12],
                "canal_instrumento_id": str(self.canal_id), "destinatario": CONTATO,
                "mensagem_id": 1000 + n,
            },
        }


def _sem_pausa(texto, ramos=None):
    return {"saida": texto, "instrumentos_acionados": [], "uso": [],
            "mensagens_enviadas": {}, "ramos_escolhidos": list(ramos or [])}


def _maquina(sessao, cliente, entrar, dados, monkeypatch):
    enviados: list[str] = []
    monkeypatch.setattr(telegram, "enviar", lambda token, chat, texto: enviados.append(texto) or {"ok": True})
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)

    class Aprovacoes(RuleBasedStateMachine):
        def __init__(self):
            super().__init__()
            self.canal, self.auto, nos = _montar(sessao, dados)
            self.c = _Cenario(self.canal.id, nos)
            monkeypatch.setattr(cadeia_mod, "executar_agente", self.c.agente(resposta=False))
            monkeypatch.setattr(retoma, "executar_agente", self.c.agente(resposta=True))
            monkeypatch.setattr(servico, "executar_agente", self.c.agente(resposta=True))
            entrar(dados["operador"])
            self.ex = Execucao(automacao_id=self.auto.id, estado="em_andamento", entrada={"texto": "pauta"})
            sessao.add(self.ex)
            sessao.commit()
            disparo.rodar_execucao(sessao, self.ex)
            self.n = itertools.count(1)
            self.viu: dict[int, int | None] = {}   # nº da resposta → id do passo que a pessoa via
            self.no_que_viu: dict[int, str | None] = {}
            self.telegram_na_fila: list[uuid.UUID] = []

        # ── o que a pessoa via ao responder ─────────────────────────────────────
        def _o_que_esta_na_tela(self):
            sessao.expire_all()
            ex = sessao.get(Execucao, self.ex.id)
            if ex.estado != "aguardando_humano":
                return None, None
            p = aprovacao.passo_pausado(sessao, ex)
            return (p.id if p else None), (p.no_id if p else None)

        def _resposta(self, decisao):
            n = next(self.n)
            self.viu[n], self.no_que_viu[n] = self._o_que_esta_na_tela()
            return n, f"{decisao}#{n}"

        # ── eventos ─────────────────────────────────────────────────────────────
        @rule(decisao=st.sampled_from(DECISOES))
        def chega_mensagem_no_telegram(self, decisao):
            n, texto = self._resposta(decisao)
            conv, deve = servico.registrar_entrada(
                sessao, self.canal,
                telegram.MensagemEntrante(contato_chave=CONTATO, contato_nome="Julio", texto=texto, midia=None),
            )
            if deve:
                self.telegram_na_fila.append(conv.id)

        @precondition(lambda self: self.telegram_na_fila)
        @rule()
        def telegram_processa_a_mais_antiga(self):
            conv_id = self.telegram_na_fila.pop(0)
            sessao.expire_all()
            from modelos import Conversa

            conversa = sessao.get(Conversa, conv_id)
            if conversa is None or conversa.estado in ("humano_assumiu", "fechada"):
                return
            execucao = servico._execucao_pausada(sessao, conversa)
            if execucao is not None:
                servico._turno_de_portao(sessao, conversa, self.canal, "tok", execucao)

        @rule(decisao=st.sampled_from(DECISOES))
        def clica_na_tela(self, decisao):
            _, texto = self._resposta(decisao)
            cliente.post(f"/execucoes/{self.ex.id}/responder", json={"resposta": texto})

        @rule()
        def abre_a_pagina(self):
            """A página carrega e fica parada na tela enquanto o fluxo anda por fora."""
            self.pagina = self._o_que_esta_na_tela()

        @precondition(lambda self: getattr(self, "pagina", (None, None))[0] is not None)
        @rule(decisao=st.sampled_from(DECISOES))
        def clica_na_pagina_aberta(self, decisao):
            n = next(self.n)
            self.viu[n], self.no_que_viu[n] = self.pagina
            cliente.post(
                f"/execucoes/{self.ex.id}/responder",
                json={"resposta": f"{decisao}#{n}", "passo_id": str(self.pagina[0])},
            )

        @rule()
        def trabalhador_da_fila(self):
            sessao.expire_all()
            ex = sessao.get(Execucao, self.ex.id)
            if ex.estado == "aguardando" and ex.retomada_resposta:
                ex.estado = "em_andamento"
                sessao.commit()
                disparo.rodar_retomada(sessao, ex)

        # ── as regras que nunca podem quebrar ───────────────────────────────────
        @invariant()
        def resposta_so_vale_para_a_pergunta_que_a_pessoa_viu(self):
            for no, n in self.c.execucoes_do_agente:
                assert n in self.viu, f"o agente rodou com uma resposta desconhecida (#{n})"
                assert self.no_que_viu[n] == no, (
                    f"a resposta #{n} foi dada vendo '{self.no_que_viu[n]}' e foi aplicada "
                    f"a '{no}'"
                )

        @invariant()
        def cada_resposta_roda_o_agente_no_maximo_uma_vez(self):
            ns = [n for _, n in self.c.execucoes_do_agente]
            repetidas = {n for n in ns if ns.count(n) > 1}
            assert not repetidas, f"respostas aplicadas mais de uma vez: {sorted(repetidas)}"

        @invariant()
        def numeros_de_passo_nao_se_repetem(self):
            dup = sessao.execute(
                select(PassoExecucao.ordem, func.count())
                .where(PassoExecucao.execucao_id == self.ex.id)
                .group_by(PassoExecucao.ordem).having(func.count() > 1)
            ).all()
            assert not dup, f"dois passos com o mesmo número: {dup}"

        @invariant()
        def ninguem_fica_com_a_trava_depois_de_terminar(self):
            sessao.expire_all()
            ex = sessao.get(Execucao, self.ex.id)
            if ex.estado != "aguardando":  # entre o clique e o trabalhador, a tela é dona
                assert dono.quem_tem(sessao, ex.id) is None, f"trava esquecida: {ex.dono}"

        @invariant()
        def espera_aponta_um_passo_que_ainda_nao_decidiu(self):
            sessao.expire_all()
            ex = sessao.get(Execucao, self.ex.id)
            if ex.estado != "aguardando_humano":
                return
            p = aprovacao.passo_pausado(sessao, ex)
            assert p is not None
            assert not (p.saida or {}).get("saidas_escolhidas"), (
                f"a execução espera no passo {p.ordem} ({p.no_id}), que já decidiu"
            )

        @invariant()
        def pedido_pelo_telegram_fica_registrado(self):
            sessao.expire_all()
            ex = sessao.get(Execucao, self.ex.id)
            if ex.estado != "aguardando_humano":
                return
            pedido = ((aprovacao.passo_pausado(sessao, ex).saida or {}).get("aprovacao") or {})
            if pedido.get("codigo"):
                ativo = sessao.scalars(
                    select(PedidoAprovacao).where(PedidoAprovacao.codigo == pedido["codigo"])
                ).first()
                assert ativo is not None and ativo.ativo, (
                    "a execução espera um pedido feito pelo Telegram que não foi registrado — "
                    "a resposta no Telegram não teria para onde ir"
                )

    return Aprovacoes


# Quantos cenários sortear. O padrão cabe na suíte; para uma busca funda (antes de mexer
# no motor), rode com BATUTA_COMBINACOES=1000.
CENARIOS = int(os.environ.get("BATUTA_COMBINACOES", "120"))


def test_aprovacao_sob_combinacoes(sessao, cliente, entrar, dados, monkeypatch):
    maquina = _maquina(sessao, cliente, entrar, dados, monkeypatch)
    run_state_machine_as_test(
        maquina,
        settings=settings(
            max_examples=CENARIOS, stateful_step_count=10, deadline=None,
            suppress_health_check=list(HealthCheck), database=None,
        ),
    )


# ── As sequências que já acharam defeito, fixas (rápidas e sem sorteio) ──────────

def _replay(maquina, passos):
    m = maquina()
    try:
        for nome, kw in passos:
            getattr(m, nome)(**kw)
            for inv in (
                m.resposta_so_vale_para_a_pergunta_que_a_pessoa_viu,
                m.cada_resposta_roda_o_agente_no_maximo_uma_vez,
                m.numeros_de_passo_nao_se_repetem,
                m.ninguem_fica_com_a_trava_depois_de_terminar,
                m.espera_aponta_um_passo_que_ainda_nao_decidiu,
                m.pedido_pelo_telegram_fica_registrado,
            ):
                inv()
    finally:
        m.teardown()


def test_reprovar_pelo_telegram_registra_o_pedido_novo(sessao, cliente, entrar, dados, monkeypatch):
    _replay(_maquina(sessao, cliente, entrar, dados, monkeypatch), [
        ("chega_mensagem_no_telegram", {"decisao": "REPROVO"}),
        ("telegram_processa_a_mais_antiga", {}),
    ])


def test_dois_aprovados_seguidos_nao_aprovam_o_pedido_seguinte(sessao, cliente, entrar, dados, monkeypatch):
    """O desenho da execução f941b1b1: a 2ª mensagem não pode aprovar o Carrossel."""
    _replay(_maquina(sessao, cliente, entrar, dados, monkeypatch), [
        ("chega_mensagem_no_telegram", {"decisao": "APROVO"}),
        ("chega_mensagem_no_telegram", {"decisao": "APROVO"}),
        ("telegram_processa_a_mais_antiga", {}),
        ("telegram_processa_a_mais_antiga", {}),
    ])


def test_clique_em_pagina_atrasada_nao_vale_para_o_pedido_seguinte(sessao, cliente, entrar, dados, monkeypatch):
    _replay(_maquina(sessao, cliente, entrar, dados, monkeypatch), [
        ("abre_a_pagina", {}),
        ("chega_mensagem_no_telegram", {"decisao": "APROVO"}),
        ("telegram_processa_a_mais_antiga", {}),
        ("clica_na_pagina_aberta", {"decisao": "APROVO"}),
        ("trabalhador_da_fila", {}),
    ])
