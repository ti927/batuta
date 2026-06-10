"""Testes da fase Chaves & Contabilização:

- o uso da IA de conversa (criadora) entra no resumo de custo (antes invisível);
- o painel da consultoria soma só o que saiu da chave-mãe (consultoria/legado),
  quebrado por organização, e é restrito ao admin da consultoria;
- o endpoint de modelos disponíveis reflete as chaves por tipo de IA;
- o modelo da IA de conversa é selecionável e recusa modelo sem chave.
"""

from types import SimpleNamespace

import precos
from modelos import Automacao, ConversaCriacao, Execucao, PassoExecucao


# ───────────────────── precos: a conversa entra no resumo ─────────────────────


def _conversa_ns(usos):
    mensagens = [{"papel": "usuario", "conteudo": "oi"}]
    for u in usos:
        mensagens.append({"papel": "ia", "conteudo": "ok", "uso": u})
    return SimpleNamespace(mensagens=mensagens)


def test_resumir_uso_inclui_conversas():
    passos = [
        SimpleNamespace(
            saida={"uso": [{"modelo": "haiku", "tokens_entrada": 100, "tokens_saida": 50, "origem": "organizacao"}]}
        )
    ]
    conversas = [
        _conversa_ns(
            [{"modelo": "claude-opus-4-8", "tokens_entrada": 1000, "tokens_saida": 200, "origem": "consultoria"}]
        )
    ]
    r = precos.resumir_uso(passos, conversas)
    assert r["tokens_entrada"] == 1100 and r["tokens_saida"] == 250
    assert r["por_modelo"]["claude-opus-4-8"]["tokens_saida"] == 200
    assert r["por_origem"]["consultoria"]["tokens_entrada"] == 1000


def test_entradas_das_conversas_ignora_turnos_sem_uso():
    conversas = [
        SimpleNamespace(
            mensagens=[
                {"papel": "usuario", "conteudo": "x"},
                {"papel": "ia", "conteudo": "y"},  # turno da IA sem `uso`
                {"papel": "ia", "conteudo": "z", "uso": {"modelo": "haiku", "tokens_entrada": 5, "tokens_saida": 2}},
            ]
        )
    ]
    assert list(precos.entradas_das_conversas(conversas)) == [
        {"modelo": "haiku", "tokens_entrada": 5, "tokens_saida": 2}
    ]


# ──────────────────────────── helpers de banco ────────────────────────────


def _semear_passo(sessao, time_id, origem, te, ts):
    auto = Automacao(time_id=time_id, nome="Auto", tipo_gatilho="manual")
    sessao.add(auto)
    sessao.flush()
    ex = Execucao(automacao_id=auto.id, estado="concluida")
    sessao.add(ex)
    sessao.flush()
    sessao.add(
        PassoExecucao(
            execucao_id=ex.id,
            ordem=1,
            agente_id=None,
            saida={"uso": [{"modelo": "claude-haiku-4-5", "tokens_entrada": te, "tokens_saida": ts, "origem": origem}]},
            estado="concluido",
        )
    )
    sessao.flush()


def _semear_conversa(sessao, org_id, origem, te, ts, modelo="claude-opus-4-8"):
    c = ConversaCriacao(
        organizacao_id=org_id,
        mensagens=[
            {"papel": "usuario", "conteudo": "oi"},
            {"papel": "ia", "conteudo": "ok", "uso": {"modelo": modelo, "tokens_entrada": te, "tokens_saida": ts, "origem": origem}},
        ],
    )
    sessao.add(c)
    sessao.flush()
    return c


# ─────────────── /uso/resumo: org inclui conversa, time não ───────────────


def test_resumo_org_inclui_conversa_mas_time_nao(cliente, entrar, dados, sessao):
    _semear_conversa(sessao, dados["orgA"].id, "consultoria", 1000, 200)
    entrar(dados["admin"])
    org = dados["orgA"].id
    corpo_org = cliente.get(f"/uso/resumo?organizacao_id={org}").json()
    assert corpo_org["por_origem"]["consultoria"]["tokens_entrada"] == 1000
    # No nível de time, a conversa (que é da org) não entra.
    corpo_time = cliente.get(f"/uso/resumo?time_id={dados['timeA'].id}").json()
    assert corpo_time["tokens_entrada"] == 0


# ───────────────────────── /uso/consultoria (painel) ─────────────────────────


def test_uso_consultoria_soma_chave_mae_por_org_e_exige_admin(
    cliente, entrar, dados, sessao, monkeypatch
):
    # Consumo da consultoria na orgA: uma execução + uma conversa.
    _semear_passo(sessao, dados["timeA"].id, "consultoria", 100, 40)
    _semear_conversa(sessao, dados["orgA"].id, "consultoria", 1000, 200)
    # Consumo com chave PRÓPRIA não deve entrar no painel da consultoria.
    _semear_conversa(sessao, dados["orgA"].id, "organizacao", 9999, 9999)

    # Quem não é admin da consultoria leva 403.
    monkeypatch.setenv("CONSULTORIA_ADMINS", "")
    entrar(dados["admin"])
    assert cliente.get("/uso/consultoria").status_code == 403

    # Admin da consultoria enxerga o painel.
    monkeypatch.setenv("CONSULTORIA_ADMINS", dados["admin"].email)
    corpo = cliente.get("/uso/consultoria").json()
    linha = next(
        o for o in corpo["por_organizacao"] if o["organizacao_id"] == str(dados["orgA"].id)
    )
    # 100 (execução) + 1000 (conversa) na chave-mãe; o consumo próprio ficou de fora.
    assert linha["tokens_entrada"] == 1100 and linha["tokens_saida"] == 240


# ───────────────────── modelos disponíveis + modelo da conversa ─────────────


def test_modelos_disponiveis_refletem_chave_por_tipo(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    org = dados["orgA"].id
    # Chave OpenAI só para a executora.
    cliente.put(
        f"/organizacoes/{org}/chaves",
        json={"tipo_ia": "executora", "provedor": "openai", "valor": "sk-test-exec"},
    )
    corpo = cliente.get(f"/organizacoes/{org}/modelos-disponiveis").json()
    assert set(corpo.keys()) == {"executora", "criadora"}
    assert corpo["executora"]["openai"] is True
    # A chave era só de executora — a conversa (criadora) não a herda.
    assert corpo["criadora"]["openai"] is False


def test_definir_modelo_criadora_valida_chave(cliente, entrar, dados, sessao):
    entrar(dados["admin"])
    org = dados["orgA"].id
    # Com chave criadora OpenAI, pode escolher um modelo OpenAI.
    cliente.put(
        f"/organizacoes/{org}/chaves",
        json={"tipo_ia": "criadora", "provedor": "openai", "valor": "sk-test-cria"},
    )
    ok = cliente.put(f"/organizacoes/{org}/modelo-criadora", json={"modelo": "gpt-4o"})
    assert ok.status_code == 200 and ok.json()["modelo_criadora"] == "gpt-4o"

    # Modelo desconhecido → 422.
    assert (
        cliente.put(f"/organizacoes/{org}/modelo-criadora", json={"modelo": "zzz-nao-existe"}).status_code
        == 422
    )
    # Google sem chave (sem fallback de ambiente) → 422.
    assert (
        cliente.put(f"/organizacoes/{org}/modelo-criadora", json={"modelo": "gemini-1.5-pro"}).status_code
        == 422
    )
    # Voltar ao padrão (nulo) sempre passa.
    volta = cliente.put(f"/organizacoes/{org}/modelo-criadora", json={"modelo": None})
    assert volta.status_code == 200 and volta.json()["modelo_criadora"] is None
