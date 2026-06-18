"""Testes do endpoint POST /times/{id}/conversa (obter-ou-criar a conversa do time).

É o que o painel da IA dentro de `/times/[id]` usa quando o time ainda não tem uma
conversa (caminho de borda: time criado pelo CRUD manual). Garante: cria amarrada ao
time, é idempotente (não duplica), devolve a existente, e respeita a matriz de acesso.
Roda na transação revertida do conftest.
"""

from modelos import ConversaCriacao


def test_cria_conversa_amarrada_ao_time(cliente, entrar, dados):
    entrar(dados["operador"])
    time = dados["timeA"]
    r = cliente.post(f"/times/{time.id}/conversa")
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["time_id"] == str(time.id)
    assert corpo["organizacao_id"] == str(dados["orgA"].id)


def test_idempotente_nao_duplica(cliente, entrar, dados):
    entrar(dados["operador"])
    time = dados["timeA"]
    a = cliente.post(f"/times/{time.id}/conversa").json()
    b = cliente.post(f"/times/{time.id}/conversa").json()
    assert a["id"] == b["id"]  # a 2ª chamada devolve a mesma conversa


def test_devolve_conversa_existente(cliente, entrar, dados, sessao):
    # uma conversa já amarrada ao time (como a IA faria no 1º definir_time)
    conversa = ConversaCriacao(
        organizacao_id=dados["orgA"].id,
        criada_por_id=dados["admin"].id,
        titulo="Já existe",
        time_id=dados["timeA"].id,
    )
    sessao.add(conversa)
    sessao.flush()

    entrar(dados["operador"])
    r = cliente.post(f"/times/{dados['timeA'].id}/conversa")
    assert r.status_code == 201
    assert r.json()["id"] == str(conversa.id)


def test_observador_403(cliente, entrar, dados):
    entrar(dados["observador"])
    r = cliente.post(f"/times/{dados['timeA'].id}/conversa")
    assert r.status_code == 403


def test_estranho_404(cliente, entrar, dados):
    entrar(dados["estranho"])  # de outra organização
    r = cliente.post(f"/times/{dados['timeA'].id}/conversa")
    assert r.status_code == 404
