"""Instrumento PERSONALIZADO × NATIVO (decisão do maestro de 12/08, reafirmada em 29/09).

O que só chama um serviço de fora é personalizado: nasce e se edita no Construtor.
A chamada de API avulsa (`chamar_api_rest`) foi substituída na CRIAÇÃO pelo conector —
criar uma nova é recusado em todo caminho, e as que já existem seguem funcionando e
editáveis. O servidor MCP é personalizado com Construtor próprio (fora da lista de
prontos da tela), e as IAs seguem criando-o normalmente.
"""

from modelos import Instrumento


def test_tela_nao_cria_chamada_de_api_nova(cliente, entrar, dados):
    entrar(dados["operador"])
    r = cliente.post(f"/times/{dados['timeA'].id}/instrumentos", json={
        "nome": "API", "tipo": "chamar_api_rest", "configuracao": {"url": "https://x/y"}})
    assert r.status_code == 422 and "Construtor" in r.json()["detail"]


def test_chamada_de_api_que_ja_existe_segue_editavel(cliente, entrar, dados, sessao):
    inst = Instrumento(time_id=dados["timeA"].id, nome="Data de hoje", tipo="chamar_api_rest",
                       configuracao={"url": "https://x/y", "metodo": "GET"})
    sessao.add(inst)
    sessao.flush()
    entrar(dados["operador"])
    r = cliente.put(f"/instrumentos/{inst.id}", json={
        "nome": "Data de hoje (SP)", "configuracao": {"url": "https://x/z", "metodo": "GET"}})
    assert r.status_code == 200 and r.json()["nome"] == "Data de hoje (SP)"


def test_catalogo_da_tela_marca_personalizado_e_substituido(cliente, entrar, dados):
    entrar(dados["operador"])
    tipos = {t["tipo"]: t for t in cliente.get("/instrumentos/tipos").json()}
    assert tipos["conectar_mcp"]["criado_no_construtor"] is True
    assert tipos["chamar_api_rest"]["substituido_por"] == "conector"
    assert tipos["agendar_automacao"]["criado_no_construtor"] is False
    assert tipos["agendar_automacao"]["substituido_por"] is None


def test_servidor_mcp_segue_criavel_pelas_ias(sessao, dados):
    from criacao import servicos

    inst, _ = servicos.configurar_instrumento(
        sessao, dados["timeA"], nome="Zernio", tipo="conectar_mcp",
        configuracao={"auth_modo": "bearer"},
    )
    assert inst.tipo == "conectar_mcp"


# ── Reorganização dos prontos (2026-10-01) ──────────────────────────────────────
# Pronto do Batuta = o que é do Batuta por dentro + o que vem das IAs. Integração de
# mercado (Instagram, busca/leitura de sites, WordPress, Search Console, fal.ai) e o
# webhook de saída viraram personalizado: criar NOVO é recusado em toda porta; o que
# já existe segue rodando. O banco de dados virou personalizado com Construtor.

APOSENTADOS = (
    "instagram_insights", "instagram_ler_comentarios", "instagram_ler_post",
    "instagram_responder_comentario", "publicar_instagram", "busca_web", "busca_exa",
    "ler_site", "ler_site_firecrawl", "publicar_wordpress", "search_console",
    "gerar_video_fal", "disparar_webhook",
)
PRONTOS = (
    "agendar_automacao", "arquivar_imagem", "descrever_imagem", "enviar_telegram",
    "gerar_imagem", "gerar_pdf", "gerar_video", "montar_imagem", "pedir_aprovacao",
    "quadro",
)


def test_integracoes_de_mercado_nao_se_criam_mais_como_pronto():
    import instrumentos as encaixe

    for tipo in APOSENTADOS:
        motivo = encaixe.motivo_para_nao_criar(tipo)
        assert motivo and "Construtor" in motivo, tipo
    for tipo in PRONTOS:
        assert encaixe.motivo_para_nao_criar(tipo) is None, tipo
        assert not encaixe.eh_personalizado(tipo), tipo


def test_catalogo_das_ias_so_traz_prontos_e_personalizados_criaveis():
    from criacao.ferramentas import catalogo_de_instrumentos

    tipos = {t["tipo"] for t in catalogo_de_instrumentos()}
    assert not (tipos & set(APOSENTADOS))
    assert set(PRONTOS) <= tipos
    assert {"conectar_mcp", "banco_sql"} <= tipos  # personalizados que as IAs criam


def test_ia_criadora_recusa_tipo_aposentado(sessao, dados):
    import pytest
    from criacao import servicos
    from criacao.servicos import ConflitoDominio

    with pytest.raises(ConflitoDominio, match="personalizado"):
        servicos.configurar_instrumento(
            sessao, dados["timeA"], nome="Busca", tipo="busca_web", configuracao={}
        )


def test_tela_recusa_tipo_aposentado(cliente, entrar, dados):
    entrar(dados["operador"])
    r = cliente.post(f"/times/{dados['timeA'].id}/instrumentos", json={
        "nome": "Ler site", "tipo": "ler_site", "configuracao": {}})
    assert r.status_code == 422 and "personalizado" in r.json()["detail"]


def test_instrumento_aposentado_que_ja_existe_segue_editavel(cliente, entrar, dados, sessao):
    inst = Instrumento(time_id=dados["timeA"].id, nome="Ler site", tipo="ler_site",
                       configuracao={})
    sessao.add(inst)
    sessao.flush()
    entrar(dados["operador"])
    r = cliente.put(f"/instrumentos/{inst.id}", json={"nome": "Ler site (Tavily)"})
    assert r.status_code == 200 and r.json()["nome"] == "Ler site (Tavily)"


def test_banco_de_dados_e_personalizado_com_construtor(cliente, entrar, dados, sessao):
    import instrumentos as encaixe
    from criacao import servicos

    assert encaixe.eh_personalizado("banco_sql")
    entrar(dados["operador"])
    tipos = {t["tipo"]: t for t in cliente.get("/instrumentos/tipos").json()}
    assert tipos["banco_sql"]["criado_no_construtor"] is True
    inst, pendentes = servicos.configurar_instrumento(
        sessao, dados["timeA"], nome="ERP", tipo="banco_sql",
        configuracao={"host": "db.x", "banco": "erp", "usuario": "leitor",
                      "somente_leitura": True},
    )
    assert inst.tipo == "banco_sql" and "senha" in pendentes


def test_gatilho_de_comentario_do_instagram_nao_se_define_mais():
    from criacao.ferramentas import FORMATO_GATILHO, _validar_gatilho

    erro = _validar_gatilho("comentario_instagram", {})
    assert erro and "webhook" in erro
    assert "comentario_instagram" not in FORMATO_GATILHO


# ── A chave de IA libera os instrumentos daquela IA (2026-10-01, Fase 2) ─────────


def _chave(sessao, org_id, provedor):
    import cofre
    from modelos import ChaveApi

    sessao.add(ChaveApi(organizacao_id=org_id, provedor=provedor,
                        valor_cifrado=cofre.cifrar("k-teste"), ativa=True))
    sessao.flush()


def test_instrumentos_de_ia_declaram_a_ia():
    import instrumentos as encaixe

    for tipo in ("gerar_imagem", "montar_imagem", "gerar_video"):
        assert encaixe.obter_tipo(tipo).provedores_ia == ("openai",), tipo
    assert set(encaixe.obter_tipo("descrever_imagem").provedores_ia) == {
        "anthropic", "openai", "google"}
    for tipo in ("agendar_automacao", "pedir_aprovacao", "quadro", "gerar_pdf"):
        assert encaixe.obter_tipo(tipo).provedores_ia == (), tipo


def test_sem_chave_da_openai_nao_cria_imagem(sessao, dados):
    import pytest
    from criacao import servicos
    from criacao.servicos import ConflitoDominio

    with pytest.raises(ConflitoDominio, match="chave da OpenAI"):
        servicos.configurar_instrumento(sessao, dados["timeA"], nome="Arte",
                                        tipo="gerar_imagem")


def test_com_chave_da_openai_cria_imagem(sessao, dados):
    from criacao import servicos

    _chave(sessao, dados["orgA"].id, "openai")
    inst, pendentes = servicos.configurar_instrumento(
        sessao, dados["timeA"], nome="Arte", tipo="gerar_imagem")
    assert inst.tipo == "gerar_imagem" and pendentes == []


def test_tela_recusa_imagem_sem_chave_e_diz_onde_cadastrar(cliente, entrar, dados):
    entrar(dados["operador"])
    r = cliente.post(f"/times/{dados['timeA'].id}/instrumentos", json={
        "nome": "Arte", "tipo": "gerar_imagem", "configuracao": {}})
    assert r.status_code == 422 and "Organização › Chaves" in r.json()["detail"]


def test_ler_imagem_serve_a_qualquer_ia(sessao, dados, monkeypatch):
    from criacao import servicos

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _chave(sessao, dados["orgA"].id, "google")
    inst, _ = servicos.configurar_instrumento(
        sessao, dados["timeA"], nome="Visão", tipo="descrever_imagem")
    assert inst.tipo == "descrever_imagem"


def test_catalogo_diz_qual_ia_libera(cliente, entrar, dados):
    from criacao.ferramentas import catalogo_de_instrumentos

    ia = {c["tipo"]: c for c in catalogo_de_instrumentos()}
    assert ia["gerar_video"]["precisa_chave_de_ia"] == ["openai"]
    assert ia["quadro"]["precisa_chave_de_ia"] == []
    entrar(dados["operador"])
    tela = {t["tipo"]: t for t in cliente.get("/instrumentos/tipos").json()}
    assert tela["montar_imagem"]["provedores_ia"] == ["openai"]
