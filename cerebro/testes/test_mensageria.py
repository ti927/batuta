"""Testes da camada de mensageria (Fase 1, modo conversacional).

Cobrem o roteamento (achar/criar a Conversa, gravar a thread, achar o agente
atendente pelo cinto), o filtro dos instrumentos de canal das ferramentas do
agente, e um turno completo com `executar_agente` e o envio mockados (sem bot
real). NÃO tocam o núcleo de orquestração.
"""

import segredos_instrumento as si
from sqlalchemy import select

from mensageria import servico, telegram
from modelos import (
    Agente,
    AgenteInstrumento,
    Conversa,
    Instrumento,
    MensagemConversa,
)


class _SessaoFake:
    """Proxy que reusa a sessão do teste (transação revertida ao fim) mas ignora
    o `close()` — assim o `processar_turno` (que abre a própria sessão) opera
    sobre os mesmos dados e o teste pode conferir o resultado depois."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def close(self):
        pass


def _bot(sessao, dados, nome="bot"):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome=nome, tipo="enviar_telegram", configuracao={}
    )
    sessao.add(inst)
    sessao.flush()
    return inst


def _agente_com(sessao, dados, *instrumentos, nome="Atendente"):
    ag = Agente(time_id=dados["timeA"].id, nome=nome, papel="agente")
    sessao.add(ag)
    sessao.flush()
    for inst in instrumentos:
        sessao.add(AgenteInstrumento(agente_id=ag.id, instrumento_id=inst.id))
    sessao.flush()
    return ag


def _msg(texto="oi", chave="555", nome="João"):
    return telegram.MensagemEntrante(
        contato_chave=chave, contato_nome=nome, texto=texto, midia=None
    )


# ───────────────────────── extrair_update (adaptador) ────────────────────────


def test_extrair_update_texto():
    m = telegram.extrair_update(
        {"message": {"chat": {"id": 555}, "from": {"first_name": "Ana"}, "text": "olá"}}
    )
    assert m and m.contato_chave == "555" and m.contato_nome == "Ana" and m.texto == "olá"


def test_extrair_update_voz_marca_midia():
    m = telegram.extrair_update(
        {"message": {"chat": {"id": 9}, "voice": {"file_id": "abc"}}}
    )
    assert m and m.texto is None and m.midia == {"tipo": "voz", "file_id": "abc"}


def test_extrair_update_ignora_nao_mensagem():
    assert telegram.extrair_update({"my_chat_member": {}}) is None
    assert telegram.extrair_update({}) is None


# ───────────────────────────── roteamento ────────────────────────────────────


def test_registrar_entrada_cria_conversa_e_roteia(sessao, dados):
    inst = _bot(sessao, dados)
    ag = _agente_com(sessao, dados, inst)

    conversa, deve = servico.registrar_entrada(sessao, inst, _msg("oi"))

    assert deve is True
    assert conversa.destino_tipo == "agente" and conversa.destino_id == ag.id
    assert conversa.estado == "bot_respondendo"
    assert conversa.contato_nome == "João"
    msgs = sessao.scalars(
        select(MensagemConversa).where(MensagemConversa.conversa_id == conversa.id)
    ).all()
    assert [(m.papel, m.conteudo) for m in msgs] == [("contato", "oi")]


def test_segunda_mensagem_reusa_a_mesma_conversa(sessao, dados):
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    c1, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))
    c2, _ = servico.registrar_entrada(sessao, inst, _msg("tudo bem?"))
    assert c1.id == c2.id
    msgs = sessao.scalars(
        select(MensagemConversa)
        .where(MensagemConversa.conversa_id == c1.id)
        .order_by(MensagemConversa.criado_em)
    ).all()
    assert [m.conteudo for m in msgs] == ["oi", "tudo bem?"]


def test_sem_agente_atendente_nao_processa(sessao, dados):
    inst = _bot(sessao, dados)  # nenhum agente tem este instrumento no cinto
    conversa, deve = servico.registrar_entrada(sessao, inst, _msg("oi"))
    assert deve is False
    assert conversa.destino_id is None
    assert conversa.estado == "aberta"


def test_humano_assumiu_nao_processa(sessao, dados):
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("oi"))
    conversa.estado = "humano_assumiu"
    sessao.commit()
    conversa2, deve = servico.registrar_entrada(sessao, inst, _msg("alguém aí?"))
    assert conversa2.id == conversa.id
    assert deve is False
    assert conversa2.estado == "humano_assumiu"


def test_cinto_sem_canais_filtra_o_instrumento_de_canal(sessao, dados):
    inst_canal = _bot(sessao, dados)
    inst_busca = Instrumento(
        time_id=dados["timeA"].id, nome="busca", tipo="busca_web", configuracao={}
    )
    sessao.add(inst_busca)
    sessao.flush()
    ag = _agente_com(sessao, dados, inst_canal, inst_busca)

    cinto = servico._cinto_sem_canais(sessao, ag.id)
    tipos = {i.tipo for i in cinto}
    assert tipos == {"busca_web"}  # o canal foi filtrado


# ─────────────────────────── turno completo (mock) ───────────────────────────


def test_processar_turno_envia_resposta_e_grava(sessao, dados, monkeypatch):
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "TOKEN"})
    _agente_com(sessao, dados, inst)
    conversa, _ = servico.registrar_entrada(sessao, inst, _msg("quanto custa?"))

    enviados = []
    monkeypatch.setattr(servico, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(
        servico, "executar_agente", lambda ag, cinto, entrada: {"saida": "Custa R$10."}
    )
    monkeypatch.setattr(
        servico.telegram,
        "enviar",
        lambda token, chat_id, texto: enviados.append((token, chat_id, texto)) or {"ok": True},
    )

    servico.processar_turno(conversa.id)

    assert enviados == [("TOKEN", "555", "Custa R$10.")]
    sessao.refresh(conversa)
    assert conversa.estado == "aguardando_resposta"
    assert conversa.turnos == 1
    # (não ordeno por criado_em: no teste tudo roda numa transação, então now() é
    # constante e os timestamps empatam; em produção cada commit tem o seu.)
    do_agente = sessao.scalars(
        select(MensagemConversa).where(
            MensagemConversa.conversa_id == conversa.id,
            MensagemConversa.papel == "agente",
        )
    ).all()
    assert len(do_agente) == 1
    assert do_agente[0].conteudo == "Custa R$10." and do_agente[0].entregue


# ─────────────────────── endpoint de entrada (HTTP) ──────────────────────────


def test_endpoint_entrada_agenda_turno(cliente, dados, sessao, monkeypatch):
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    agendados = []
    monkeypatch.setattr(servico, "processar_turno", lambda cid: agendados.append(cid))

    r = cliente.post(
        f"/mensageria/{inst.id}/entrada",
        json={"message": {"chat": {"id": 777}, "from": {"first_name": "Zé"}, "text": "oi"}},
    )
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert len(agendados) == 1
    conv = sessao.scalars(
        select(Conversa).where(Conversa.instrumento_id == inst.id)
    ).first()
    assert conv is not None and conv.contato_chave == "777"


def test_endpoint_entrada_404_para_instrumento_que_nao_e_canal(cliente, dados, sessao):
    inst = Instrumento(
        time_id=dados["timeA"].id, nome="busca", tipo="busca_web", configuracao={}
    )
    sessao.add(inst)
    sessao.flush()
    r = cliente.post(f"/mensageria/{inst.id}/entrada", json={"message": {}})
    assert r.status_code == 404


# ────────────────────────── conectar canal (Fase E) ──────────────────────────


def test_ativar_canal_seta_webhook_e_guarda_secret(cliente, entrar, dados, sessao, monkeypatch):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)
    si.salvar_segredos(sessao, inst.id, {"token_bot": "TOK"})
    chamada = {}
    monkeypatch.setattr(
        "mensageria.telegram.configurar_webhook",
        lambda token, url, secret: chamada.update(token=token, url=url, secret=secret)
        or {"ok": True},
    )
    r = cliente.post(f"/mensageria/{inst.id}/ativar-canal")
    assert r.status_code == 200
    assert chamada["token"] == "TOK"
    assert chamada["url"].endswith(f"/mensageria/{inst.id}/entrada")
    sessao.refresh(inst)
    assert inst.configuracao["webhook_secret"] == chamada["secret"]


def test_ativar_canal_sem_token_recusa(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    inst = _bot(sessao, dados)  # sem token_bot
    r = cliente.post(f"/mensageria/{inst.id}/ativar-canal")
    assert r.status_code == 422


def test_entrada_valida_secret_token(cliente, dados, sessao, monkeypatch):
    inst = _bot(sessao, dados)
    _agente_com(sessao, dados, inst)
    inst.configuracao = {"webhook_secret": "s3cr3t"}
    sessao.commit()
    monkeypatch.setattr(servico, "processar_turno", lambda cid: None)
    corpo = {"message": {"chat": {"id": 1}, "text": "oi"}}
    # sem o cabeçalho correto → 403
    assert cliente.post(f"/mensageria/{inst.id}/entrada", json=corpo).status_code == 403
    # com o cabeçalho correto → 200
    r = cliente.post(
        f"/mensageria/{inst.id}/entrada",
        json=corpo,
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"},
    )
    assert r.status_code == 200
