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
