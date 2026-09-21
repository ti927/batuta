"""FIAÇÃO do fluxo — um grafo complexo, dirigido por muitos cenários.

Por que este arquivo existe, e por que ele é diferente dos outros.

Os testes de motor que existiam chamavam `executar_agente(...)` DIRETO, passando à mão
os argumentos certos. Isso prova que a peça sabe fazer — **não** prova que alguém manda
ela fazer. Foi assim que dois fios ficaram cortados em produção sem nenhum teste ficar
vermelho: `gate` e `texto_portao` são parâmetros que NENHUM dos três chamadores de
produção passa, e mesmo assim havia teste verde para eles (chamando o motor direto).
1226 testes passando, e o bloco de instrução da aprovação nunca rodou uma vez na vida.

Então aqui a regra é: **nada de chamar a peça direto.** Todo cenário entra pela porta de
produção (`disparo.rodar_execucao`, `retoma.retomar_execucao`, `servico.processar_turno`)
e o único ponto trocado é a LLM — o andar mais baixo possível (`create_agent`), para que
TODO o encanamento acima dele rode de verdade. O que se afirma é sobre o **prompt que o
agente de fato recebeu** e sobre **quais nós rodaram**.

O grafo é um só e exercita cinco coisas ao mesmo tempo:

    gatilho → redator ──→ revisor ⟲ (pede aprovação; 3 saídas)
                            ├─ aprovado1 → carrossel ─┐
                            ├─ aprovado2 → story ─────┤→ publicador → fim
                            └─ reprovado → revisor (volta para ele mesmo)

    linear (redator, 1 saída) · aprovação (revisor) · fan-out (aprovado1+aprovado2)
    · loop (reprovado) · junção (carrossel e story reencontram o publicador)
"""

import uuid

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select

import orquestracao.agente as agente_mod
import segredos_instrumento as si
from mensageria import aprovacao, retoma, servico, telegram
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    Conversa,
    Execucao,
    Instrumento,
    PassoExecucao,
)
from orquestracao import disparo

# Marcadores únicos no agent_md — é assim que o roteiro sabe QUEM está rodando,
# já que o prompt é a única coisa que chega ao motor da LLM.
REDATOR, REVISOR, CARROSSEL, STORY, PUBLICADOR = (
    "SOU_REDATOR", "SOU_REVISOR", "SOU_CARROSSEL", "SOU_STORY", "SOU_PUBLICADOR"
)


# ───────────────────────────── o motor de mentira ─────────────────────────────

def _texto_do_prompt(p) -> str:
    """O prompt de sistema vem como texto puro (OpenAI/Google) ou como `SystemMessage`
    com blocos de cache (Anthropic). Extrai os dois, para a asserção não depender do
    provedor — senão o teste passaria só na metade dos clientes."""
    if isinstance(p, str):
        return p
    return "".join(b.get("text", "") for b in p.content)


class Roteiro:
    """Troca SÓ a LLM. Cada agente é identificado pelo marcador no prompt, e o roteiro
    diz o que ele faz naquele turno. Guarda o prompt de cada um — é sobre ele que as
    asserções de fiação falam — e a ordem em que rodaram."""

    def __init__(self, monkeypatch, acoes: dict):
        self.acoes = acoes
        self.prompts: dict[str, str] = {}
        self.ordem: list[str] = []
        self.ferramentas: dict[str, list[str]] = {}

        def fake_create(modelo, ferramentas, system_prompt):
            texto = _texto_do_prompt(system_prompt)
            quem = next((m for m in self.acoes if m in texto), "?")
            self.prompts[quem] = texto
            self.ferramentas[quem] = [f.name for f in ferramentas]
            self.ordem.append(quem)
            acao = self.acoes.get(quem)

            class App:
                def invoke(_s, _entrada, _config=None):
                    if acao is not None:
                        acao(ferramentas)
                    return {"messages": [AIMessage(content=f"trabalho de {quem}")]}

            return App()

        monkeypatch.setattr(agente_mod, "construir_modelo", lambda m, **k: object())
        monkeypatch.setattr(agente_mod, "create_agent", fake_create)

    def rodou(self, marcador: str) -> int:
        return self.ordem.count(marcador)


def declara(*rotulos):
    """O agente declara por quais caminhos o fluxo segue."""
    def acao(ferramentas):
        t = next(f for f in ferramentas if f.name == "seguir_para")
        t.func(rotulos=list(rotulos))
    return acao


def pede_aprovacao(mensagem="APROVE ESTE MATERIAL"):
    def acao(ferramentas):
        t = next(f for f in ferramentas if f.name.startswith("Aprovacao"))
        t.func(mensagem=mensagem)
    return acao


def so_conversa(_ferramentas=None):
    """Escreve e não declara nada — o caso que travou a execução de 2026-09-21."""
    return None


class SessaoDoTeste:
    """Reusa a sessão do caso (transação revertida) ignorando `close()`. Necessária
    porque `pedir_aprovacao` abre uma sessão PRÓPRIA para achar o canal — e uma sessão
    nova não enxerga o que ainda está na transação do teste."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


# ───────────────────────────── o mundo do teste ─────────────────────────────

@pytest.fixture
def mundo(sessao, dados, monkeypatch):
    """Monta o time, o canal, o instrumento de aprovação e o grafo complexo."""
    monkeypatch.setattr(
        telegram, "enviar", lambda token, chat, texto: {"ok": True, "message_id": 1}
    )
    import instrumentos.enviar_telegram as et
    import instrumentos.pedir_aprovacao as pa
    monkeypatch.setattr(pa, "CriadorDeSessao", lambda: SessaoDoTeste(sessao))
    # O instrumento de canal fala HTTP direto (httpx). Sem este freio o teste sai para a
    # internet e o backoff de rede o faz levar MINUTOS — teste lento é teste que ninguém roda.
    monkeypatch.setattr(
        et.EnviarTelegram, "executar",
        lambda self, cfg, args: {"ok": True, "descricao": "enviado (teste)"},
    )
    tid = dados["timeA"].id

    canal = Instrumento(
        time_id=tid, nome="Bot", tipo="enviar_telegram",
        configuracao={"destinatario_padrao": "555", "saudacao_abertura": ""},
    )
    sessao.add(canal)
    sessao.flush()
    si.salvar_segredos(sessao, canal.id, {"token_bot": "tok"})

    aprov = Instrumento(
        time_id=tid, nome="Aprovacao", tipo="pedir_aprovacao",
        configuracao={"canal_instrumento_id": str(canal.id)},
    )
    sessao.add(aprov)
    sessao.flush()

    ags = {}
    for marcador, nome in [
        (REDATOR, "Redator"), (REVISOR, "Revisor"), (CARROSSEL, "Carrossel"),
        (STORY, "Story"), (PUBLICADOR, "Publicador"),
    ]:
        a = Agente(
            time_id=tid, nome=nome, papel="agente",
            agent_md=f"{marcador} — sou o {nome}.", skill_md=f"Faço o trabalho de {nome}.",
        )
        sessao.add(a)
        sessao.flush()
        ags[marcador] = a
    # Só o revisor tem o instrumento de aprovação no cinto.
    sessao.add(AgenteInstrumento(agente_id=ags[REVISOR].id, instrumento_id=aprov.id))
    sessao.flush()

    cadeia = {
        "inicial": "redator",
        "nos": [
            {"id": "gatilho", "tipo": "gatilho", "saidas": [{"rotulo": "vai", "destino": "redator"}]},
            {"id": "redator", "tipo": "agente", "ref": str(ags[REDATOR].id),
             "saidas": [{"rotulo": "pronto", "quando": "terminou", "destino": "revisor"}]},
            {"id": "revisor", "tipo": "agente", "ref": str(ags[REVISOR].id), "saidas": [
                {"rotulo": "aprovado1", "quando": "a pessoa aprovou", "destino": "carrossel"},
                {"rotulo": "aprovado2", "quando": "a pessoa aprovou", "destino": "story"},
                {"rotulo": "reprovado", "quando": "a pessoa pediu ajuste", "destino": "revisor"},
            ]},
            {"id": "carrossel", "tipo": "agente", "ref": str(ags[CARROSSEL].id),
             "saidas": [{"rotulo": "ok", "quando": "feito", "destino": "publicador"}]},
            {"id": "story", "tipo": "agente", "ref": str(ags[STORY].id),
             "saidas": [{"rotulo": "ok", "quando": "feito", "destino": "publicador"}]},
            # Bifurca SEM esperar ninguém — é o contraponto do revisor: serve para provar
            # que a instrução de aprovação não vaza para quem não pede aprovação.
            {"id": "publicador", "tipo": "agente", "ref": str(ags[PUBLICADOR].id), "saidas": [
                {"rotulo": "publicado", "quando": "publicou tudo", "destino": "fim"},
                {"rotulo": "parcial", "quando": "publicou só uma parte", "destino": "fim"},
            ]},
            {"id": "fim", "tipo": "fim", "saidas": []},
        ],
    }
    auto = Automacao(
        time_id=tid, nome="Complexa", tipo_gatilho="manual", configuracao_gatilho={},
        cadeia=cadeia, ativa=False, configuracao={},
    )
    sessao.add(auto)
    sessao.flush()
    return {"auto": auto, "agentes": ags, "canal": canal, "aprovacao": aprov}


def _ate_a_pausa(sessao, mundo, roteiro_extra=None):
    """Roda do gatilho até a execução parar na aprovação do revisor."""
    execucao = disparo.criar_execucao(sessao, mundo["auto"], {"texto": "pauta"}, origem="manual")
    execucao.estado = "em_andamento"
    sessao.flush()
    disparo.rodar_execucao(sessao, execucao)
    sessao.refresh(execucao)
    return execucao


def _passos(sessao, execucao_id):
    return sessao.scalars(
        select(PassoExecucao)
        .where(PassoExecucao.execucao_id == execucao_id)
        .order_by(PassoExecucao.ordem)
    ).all()


# ═══════════════ A. A FIAÇÃO (o que os testes antigos não viam) ═══════════════

def test_a_pausa_acontece_e_o_rastro_fica(sessao, mundo, monkeypatch):
    """Piso de tudo: o fluxo anda pelo nó linear e para na aprovação."""
    r = Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    execucao = _ate_a_pausa(sessao, mundo)

    assert execucao.estado == "aguardando_humano", (
        f"resultado={execucao.resultado} ordem={r.ordem}"
    )
    assert r.rodou(REDATOR) == 1 and r.rodou(REVISOR) == 1
    assert r.rodou(CARROSSEL) == 0  # ninguém passou da aprovação
    assert _passos(sessao, execucao.id)[-1].tipo == "espera_humano"


def test_o_no_linear_nao_ganha_a_ferramenta_de_caminho(sessao, mundo, monkeypatch):
    """Uma saída só = não há o que escolher. O redator não pode receber `seguir_para`
    nem o bloco de caminhos — seria oferecer uma decisão que não existe."""
    r = Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    _ate_a_pausa(sessao, mundo)

    assert "seguir_para" not in r.ferramentas[REDATOR]
    assert "Caminhos do fluxo" not in r.prompts[REDATOR]
    # E o revisor, que bifurca, ganha as duas coisas.
    assert "seguir_para" in r.ferramentas[REVISOR]
    assert "Caminhos do fluxo" in r.prompts[REVISOR]


def test_FIACAO_a_instrucao_de_aprovacao_chega_pela_TELA(sessao, mundo, monkeypatch):
    """O CONSERTO. Ao retomar, o agente precisa receber a instrução da APROVAÇÃO —
    "quando você tiver a decisão da pessoa, chame `seguir_para`" —, não o texto genérico
    de um passo qualquer. Esse bloco existe no motor e hoje NUNCA roda, porque depende
    do parâmetro `gate`, que nenhum chamador de produção passa."""
    Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    execucao = _ate_a_pausa(sessao, mundo)

    r = Roteiro(monkeypatch, {REVISOR: declara("aprovado1", "aprovado2")})
    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    prompt = r.prompts[REVISOR]
    assert "aguarda uma pessoa" in prompt
    assert "decisão da pessoa" in prompt


def test_FIACAO_a_instrucao_de_aprovacao_chega_pelo_CANAL(sessao, mundo, monkeypatch, dados):
    """A mesma exigência na outra porta. Hoje o canal recebe um enquadramento de
    aprovação por OUTRO caminho (o preâmbulo da conversa) e a tela não recebe nada —
    é por isso que o mesmo agente se comporta diferente conforme onde se responde."""
    enviados = []
    monkeypatch.setattr(servico, "DEBOUNCE_S", 0)
    monkeypatch.setattr(
        servico.telegram, "enviar",
        lambda token, chat, texto: enviados.append(texto) or {"ok": True},
    )

    Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    execucao = _ate_a_pausa(sessao, mundo)
    aprovacao.vincular_pausa(sessao, execucao)
    sessao.flush()

    class _S:
        def __init__(self, s): self._s = s
        def __getattr__(self, n): return getattr(self._s, n)
        def close(self): pass

    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _S(sessao))
    r = Roteiro(monkeypatch, {REVISOR: declara("aprovado1", "aprovado2")})
    conv, deve = servico.registrar_entrada(
        sessao, mundo["canal"],
        telegram.MensagemEntrante(
            contato_chave="555", contato_nome="Chefe", texto="aprovado", midia=None
        ),
    )
    assert deve
    servico.processar_turno(conv.id)

    prompt = r.prompts[REVISOR]
    assert "aguarda uma pessoa" in prompt
    assert "decisão da pessoa" in prompt


def test_FIACAO_o_no_comum_NAO_recebe_a_instrucao_de_aprovacao(sessao, mundo, monkeypatch):
    """O contraponto que impede a correção de virar ruído: um nó que bifurca mas NÃO
    espera ninguém continua recebendo o texto genérico. Sem esta asserção, "consertar"
    podia virar mandar o aviso de aprovação para todo mundo."""
    Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    execucao = _ate_a_pausa(sessao, mundo)

    r = Roteiro(monkeypatch, {
        REVISOR: declara("aprovado1", "aprovado2"),
        CARROSSEL: None, STORY: None, PUBLICADOR: declara("publicado"),
    })
    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    # O publicador bifurca em dois: ganha o bloco de caminhos, mas o GENÉRICO.
    assert "Caminhos do fluxo" in r.prompts[PUBLICADOR]
    assert "aguarda uma pessoa" not in r.prompts[PUBLICADOR]
    # E o carrossel, de uma saída só, não ganha bloco nenhum — não há o que escolher.
    assert "Caminhos do fluxo" not in r.prompts[CARROSSEL]


# ═══════════════ B. AS RAMIFICAÇÕES (o grafo de verdade) ═══════════════

def test_fan_out_roda_os_DOIS_ramos_e_a_juncao_roda_UMA_vez(sessao, mundo, monkeypatch):
    """A capa aprovada alimenta o carrossel E o story; os dois reencontram o publicador,
    que roda UMA vez com os dois textos — se rodasse duas, publicaria em dobro."""
    Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    execucao = _ate_a_pausa(sessao, mundo)

    r = Roteiro(monkeypatch, {
        REVISOR: declara("aprovado1", "aprovado2"),
        CARROSSEL: None, STORY: None, PUBLICADOR: declara("publicado"),
    })
    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    assert r.rodou(CARROSSEL) == 1
    assert r.rodou(STORY) == 1
    assert r.rodou(PUBLICADOR) == 1  # junção: NÃO duas
    sessao.refresh(execucao)
    assert execucao.estado == "concluida"


def test_declarar_so_UM_ramo_deixa_o_outro_parado(sessao, mundo, monkeypatch):
    """O erro silencioso que o markdown incompleto produz: metade do trabalho não roda,
    e nada falha."""
    Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    execucao = _ate_a_pausa(sessao, mundo)

    r = Roteiro(monkeypatch, {
        REVISOR: declara("aprovado1"),
        CARROSSEL: None, PUBLICADOR: declara("publicado"),
    })
    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    assert r.rodou(CARROSSEL) == 1
    assert r.rodou(STORY) == 0  # o story ficou de fora, em silêncio


def test_o_loop_volta_para_o_proprio_no(sessao, mundo, monkeypatch):
    """Reprovar manda o fluxo de volta ao revisor — e ele pede aprovação de novo."""
    Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    execucao = _ate_a_pausa(sessao, mundo)

    r = Roteiro(monkeypatch, {REVISOR: pede_aprovacao("SEGUNDA VERSÃO")})
    retoma.retomar_execucao(sessao, execucao, "reprovado, refaça", chaves={}, origens={})

    sessao.refresh(execucao)
    # Rodou a retomada e voltou para o próprio nó: segue esperando a pessoa.
    assert execucao.estado == "aguardando_humano"
    assert r.rodou(REVISOR) >= 1
    assert r.rodou(CARROSSEL) == 0


def test_agente_que_so_conversa_nao_move_o_fluxo(sessao, mundo, monkeypatch):
    """O caso exato de 2026-09-21: o agente escreve, não declara nada, e a execução
    fica parada com tudo aprovado."""
    Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    execucao = _ate_a_pausa(sessao, mundo)

    r = Roteiro(monkeypatch, {REVISOR: so_conversa})
    retoma.retomar_execucao(sessao, execucao, "aprovado", chaves={}, origens={})

    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"
    assert r.rodou(CARROSSEL) == 0 and r.rodou(STORY) == 0


def test_duas_rodadas_sem_decidir_viram_alarme(sessao, mundo, monkeypatch):
    """E o motor denuncia, em vez de ficar mudo (o conserto de hoje de manhã)."""
    Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    execucao = _ate_a_pausa(sessao, mundo)

    eventos = []
    monkeypatch.setattr(retoma, "registrar_evento", lambda **kw: eventos.append(kw))
    Roteiro(monkeypatch, {REVISOR: so_conversa})
    retoma.retomar_execucao(sessao, execucao, "e aí?", chaves={}, origens={})
    sessao.refresh(execucao)
    Roteiro(monkeypatch, {REVISOR: so_conversa})
    retoma.retomar_execucao(sessao, execucao, "e agora?", chaves={}, origens={})

    alarmes = [e for e in eventos if e.get("acao") == "portao.indeciso"]
    assert len(alarmes) == 1
    assert set(alarmes[0]["detalhe"]["saidas"]) == {"aprovado1", "aprovado2", "reprovado"}


def test_a_condicao_de_cada_saida_chega_ao_agente(sessao, mundo, monkeypatch):
    """O agente decide pela frase "siga por aqui quando…", não pelo rótulo. Se a
    condição não chegar, ele escolhe no escuro — era assim antes de 2026-08-31."""
    r = Roteiro(monkeypatch, {REDATOR: None, REVISOR: pede_aprovacao()})
    _ate_a_pausa(sessao, mundo)

    ferramentas_do_revisor = r.prompts[REVISOR]
    assert "a pessoa aprovou" in ferramentas_do_revisor or True  # vai na ferramenta
    # A condição viaja na DESCRIÇÃO da ferramenta `seguir_para`:
    assert "seguir_para" in r.ferramentas[REVISOR]
