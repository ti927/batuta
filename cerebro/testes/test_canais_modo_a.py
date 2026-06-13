"""Modo A — a resposta que chega pelo canal retoma a execução pausada (Passo 6).

Coração do trabalho: a espera-por-humano (já validada) passa a poder ser
respondida pelo Telegram, não só pela tela. Aqui, sem LLM: o nó da pausa tem uma
única saída com destino=fim, então a retomada conclui direto (não roda cadeia).
Também testa o gancho que MANDA a pergunta pelo canal quando o fluxo pausa.
"""

from sqlalchemy import select

import canais.telegram as tg
from canais.servico import enviar_pelo_canal  # noqa: F401 (garante import do módulo)
from orquestracao import disparo
from modelos import Agente, Automacao, Canal, Execucao, MensagemCanal, PassoExecucao
from segredos_canal import salvar_segredos


class _RespOK:
    status_code = 200

    def json(self):
        return {"ok": True, "result": {"message_id": 1}}


class _ClienteCaptura:
    chamadas = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json=None, **k):
        _ClienteCaptura.chamadas.append((url, json))
        return _RespOK()


def _cenario_pausa(sessao, dados, *, canal_no_no=True, com_origem=False):
    """Monta um time/agente/automação/execução pausada + canal. O nó da pausa tem
    uma saída única para 'fim' (retomar conclui sem rodar cadeia/LLM)."""
    canal = Canal(
        organizacao_id=dados["orgA"].id, tipo="telegram", nome="Tg", config={}, ativo=True
    )
    sessao.add(canal)
    sessao.flush()
    salvar_segredos(sessao, canal.id, {"token": "BOT:TK"})

    agente = Agente(time_id=dados["timeA"].id, nome="Aprovador", papel="agente")
    sessao.add(agente)
    sessao.flush()

    no = {"pausa_humano": True, "saidas": [{"rotulo": "ok", "quando": "qualquer", "destino": None}]}
    if canal_no_no:
        no["canal_id"] = str(canal.id)
        no["destinatario"] = "5175"
    cadeia = {"inicio": str(agente.id), "nos": {str(agente.id): no}}

    auto = Automacao(
        time_id=dados["timeA"].id, nome="Fluxo", tipo_gatilho="manual", cadeia=cadeia, ativa=True
    )
    sessao.add(auto)
    sessao.flush()

    execucao = Execucao(
        automacao_id=auto.id,
        estado="aguardando_humano",
        entrada={"texto": "início"},
        aguardando_canal_id=canal.id if not com_origem else None,
        aguardando_identificador="5175" if not com_origem else None,
    )
    if com_origem:
        execucao.origem_canal_id = canal.id
        execucao.origem_identificador = "5175"
    sessao.add(execucao)
    sessao.flush()

    passo = PassoExecucao(
        execucao_id=execucao.id,
        ordem=0,
        agente_id=agente.id,
        saida={"texto": "Posso aprovar?"},
        estado="concluido",
    )
    sessao.add(passo)
    sessao.flush()
    return canal, auto, execucao


# ─────────────────────── Modo A pela borda (webhook) ─────────────────────────


def test_resposta_do_telegram_retoma_execucao_pausada(cliente, sessao, dados):
    canal, _auto, execucao = _cenario_pausa(sessao, dados)
    r = cliente.post(
        f"/canais/{canal.id}/webhook",
        json={"update_id": 9001, "message": {"chat": {"id": "5175"}, "text": "sim, aprovado"}},
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["modo"] == "A" and corpo["execucao_id"] == str(execucao.id)

    sessao.refresh(execucao)
    # Destino=fim → conclui com o trabalho + a resposta do humano.
    assert execucao.estado == "concluida"
    assert "sim, aprovado" in execucao.resultado["texto"]
    # A espera foi limpa.
    assert execucao.aguardando_canal_id is None
    assert execucao.aguardando_identificador is None
    # A mensagem recebida ficou ligada à execução.
    entrada = sessao.scalars(
        select(MensagemCanal).where(
            MensagemCanal.canal_id == canal.id, MensagemCanal.direcao == "entrada"
        )
    ).first()
    assert entrada is not None and entrada.execucao_id == execucao.id


def test_mensagem_de_outro_contato_nao_retoma(cliente, sessao, dados):
    canal, _auto, execucao = _cenario_pausa(sessao, dados)
    # Mensagem de um chat_id diferente do esperado → não casa (sem Modo A).
    r = cliente.post(
        f"/canais/{canal.id}/webhook",
        json={"update_id": 9002, "message": {"chat": {"id": "999"}, "text": "oi"}},
    )
    assert "modo" not in r.json()
    sessao.refresh(execucao)
    assert execucao.estado == "aguardando_humano"  # segue pausada


# ─────────────────── gancho de envio da pausa (unidade) ──────────────────────


def test_notificar_pausa_manda_pergunta_e_marca_espera(monkeypatch, sessao, dados):
    monkeypatch.setattr(tg.httpx, "Client", _ClienteCaptura)
    _ClienteCaptura.chamadas = []
    canal, _auto, execucao = _cenario_pausa(sessao, dados)
    # Simula recém-pausado: limpa a espera para o gancho preenchê-la.
    execucao.aguardando_canal_id = None
    execucao.aguardando_identificador = None
    sessao.flush()

    disparo._notificar_pausa(sessao, execucao, "Posso aprovar?")

    url, corpo = _ClienteCaptura.chamadas[-1]
    assert "botBOT:TK/sendMessage" in url
    assert corpo == {"chat_id": "5175", "text": "Posso aprovar?"}
    assert execucao.aguardando_canal_id == canal.id
    assert execucao.aguardando_identificador == "5175"
    # Registrou a saída no log.
    saida = sessao.scalars(
        select(MensagemCanal).where(
            MensagemCanal.canal_id == canal.id, MensagemCanal.direcao == "saida"
        )
    ).first()
    assert saida is not None and saida.execucao_id == execucao.id


def test_alvo_da_pausa_no_no_tem_precedencia(sessao, dados):
    canal, _auto, execucao = _cenario_pausa(sessao, dados)
    canal_id, dest = disparo._alvo_da_pausa(sessao, execucao)
    assert canal_id == canal.id and dest == "5175"


def test_alvo_da_pausa_cai_na_origem(sessao, dados):
    # Sem canal no nó, mas a execução nasceu de um canal (Modo B): responde à origem.
    canal, _auto, execucao = _cenario_pausa(sessao, dados, canal_no_no=False, com_origem=True)
    canal_id, dest = disparo._alvo_da_pausa(sessao, execucao)
    assert canal_id == canal.id and dest == "5175"


def test_alvo_da_pausa_sem_canal_e_vazio(sessao, dados):
    _canal, _auto, execucao = _cenario_pausa(sessao, dados, canal_no_no=False)
    execucao.aguardando_canal_id = None
    execucao.aguardando_identificador = None
    sessao.flush()
    assert disparo._alvo_da_pausa(sessao, execucao) == (None, None)
