"""Testes da Fatia 4 — a IA criadora MONTA o conector.

Provam que as ferramentas `montar_conector`/`testar_operacao_conector` da IA criadora
criam e editam um conector no time real, que a IA NUNCA pluga o token (fica pendente
no cofre), que o teste de operação roda a chamada e detecta os campos (unindo os
esparsos, como o Bubble exige), e que a Central tem o capítulo que ensina o formato.
Sem rede: o `httpx.Client` do conector é interceptado."""

import json
import uuid

import conhecimento
import segredos_instrumento as segredos
from criacao.ferramentas import ContextoCriacao, ferramenta_por_nome
from modelos import ConversaCriacao, Instrumento


# ─────────────────────────── fixtures / helpers ───────────────────────────


def _setup(sessao, dados):
    conversa = ConversaCriacao(
        organizacao_id=dados["orgA"].id, criada_por_id=dados["admin"].id
    )
    sessao.add(conversa)
    sessao.flush()
    ctx = ContextoCriacao(sessao=sessao, conversa=conversa, usuario=dados["admin"])
    return ctx, ferramenta_por_nome(ctx)


def _chamar(f, ferramenta, **kwargs):
    return json.loads(f[ferramenta].func(**kwargs))


class _Resp:
    def __init__(self, status=200, dados=None):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self._dados = dados
        self.text = ""

    def json(self):
        if self._dados is None:
            raise ValueError("sem json")
        return self._dados


def _mock_http(monkeypatch, resp, capturas):
    class _Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def request(self, metodo, url, headers=None, params=None, json=None):
            capturas.append(
                {"metodo": metodo, "url": url, "headers": headers, "params": params, "json": json}
            )
            return resp

    monkeypatch.setattr("instrumentos.conector.httpx.Client", _Cliente)


def _conector_bubble():
    return {
        "nome": "Gestão Lure",
        "descricao": "Integração com o app de gestão",
        "auth_tipo": "bearer",
        "operacoes": [
            {
                "nome": "Busca Projetos",
                "descricao": "Lista projetos do consultor",
                "metodo": "GET",
                "url": "https://lure.com/api/1.1/obj/Projeto",
                "campos": [
                    {"nome": "constraints", "papel": "ia", "destino": "query",
                     "descricao": "filtro JSON do Bubble"}
                ],
                "campos_resposta": ["_id", "cpo.NomeCliente"],
            }
        ],
    }


# ─────────────────────────── montar_conector ───────────────────────────


def test_montar_conector_cria_com_segredo_pendente(sessao, dados):
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="Reembolsos")
    r = _chamar(f, "montar_conector", conector=_conector_bubble())
    assert r["ok"] and r["id"]
    assert r["segredos_pendentes"] == ["auth_segredo"]  # o token fica pro cofre
    assert "cofre" in r["lembrete"].lower()

    inst = sessao.get(Instrumento, uuid.UUID(r["id"]))
    assert inst.tipo == "conector"
    assert [o["nome"] for o in inst.configuracao["operacoes"]] == ["Busca Projetos"]
    assert inst.configuracao["operacoes"][0]["campos_resposta"] == ["_id", "cpo.NomeCliente"]
    assert "auth_segredo" not in inst.configuracao  # segredo nunca em claro


def test_montar_conector_nao_pluga_o_token(sessao, dados):
    """Mesmo se a IA teimar e passar o token, ele é descartado (não vira segredo)."""
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    conector = {**_conector_bubble(), "auth_segredo": "tok-que-a-ia-nao-devia-mandar"}
    r = _chamar(f, "montar_conector", conector=conector)
    assert r["ok"]
    inst = sessao.get(Instrumento, uuid.UUID(r["id"]))
    assert "auth_segredo" not in inst.configuracao
    assert segredos.decifrar(sessao, inst.id) == {}  # nada foi guardado no cofre


def test_montar_conector_sem_auth_nao_marca_pendente(sessao, dados):
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    conector = {"nome": "API pública", "auth_tipo": "nenhuma",
                "operacoes": [{"nome": "listar", "url": "https://x/i", "metodo": "GET"}]}
    r = _chamar(f, "montar_conector", conector=conector)
    assert r["ok"]
    assert r["segredos_pendentes"] == []  # sem auth, nada pendente
    assert "sem autentica" in r["lembrete"].lower()


def test_montar_conector_edita_por_id(sessao, dados):
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    cid = _chamar(f, "montar_conector", conector=_conector_bubble())["id"]
    # edita: acrescenta uma segunda operação (de escrita)
    novo = _conector_bubble()
    novo["operacoes"].append(
        {"nome": "Cria Reembolso", "metodo": "POST", "url": "https://lure.com/api/1.1/obj/Reembolso",
         "campos": [{"nome": "cpo.Valor", "papel": "ia", "destino": "corpo"}]}
    )
    r = _chamar(f, "montar_conector", conector=novo, conector_id=cid)
    assert r["ok"] and r["id"] == cid
    inst = sessao.get(Instrumento, uuid.UUID(cid))
    assert [o["nome"] for o in inst.configuracao["operacoes"]] == ["Busca Projetos", "Cria Reembolso"]


def test_montar_conector_exige_nome_e_time(sessao, dados):
    ctx, f = _setup(sessao, dados)
    # sem time ainda
    assert _chamar(f, "montar_conector", conector=_conector_bubble())["ok"] is False
    _chamar(f, "definir_time", nome="T")
    # sem nome
    sem_nome = {k: v for k, v in _conector_bubble().items() if k != "nome"}
    assert _chamar(f, "montar_conector", conector=sem_nome)["ok"] is False


def test_montar_conector_id_inexistente(sessao, dados):
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    r = _chamar(f, "montar_conector", conector=_conector_bubble(),
                conector_id="00000000-0000-0000-0000-000000000000")
    assert r["ok"] is False


# ─────────────────────────── testar_operacao_conector ───────────────────────────


def test_testar_operacao_conector_detecta_campos(sessao, dados, monkeypatch):
    """A IA testa a operação e recebe os campos detectados — unindo os esparsos
    (o Bubble omite campos vazios de cada registro)."""
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    cid = _chamar(f, "montar_conector", conector=_conector_bubble())["id"]

    capturas: list = []
    _mock_http(
        monkeypatch,
        _Resp(200, {"response": {"results": [
            {"_id": "1", "cpo.NomeCliente": "Maria"},   # 1º: sem cpo.Valor
            {"_id": "2", "cpo.Valor": 99},              # 2º: sem NomeCliente
        ]}}),
        capturas,
    )
    r = _chamar(f, "testar_operacao_conector", conector_id=cid, operacao="Busca Projetos",
                valores={"constraints": "[]"})
    assert r["ok"]
    res = r["resultado"]
    assert res["ok"] is True
    assert [c["nome"] for c in res["campos_detectados"]] == ["_id", "cpo.NomeCliente", "cpo.Valor"]
    # o valor da IA foi para a query, sob o nome real do campo
    assert capturas[0]["params"] == {"constraints": "[]"}


def test_testar_operacao_conector_operacao_inexistente(sessao, dados):
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    cid = _chamar(f, "montar_conector", conector=_conector_bubble())["id"]
    r = _chamar(f, "testar_operacao_conector", conector_id=cid, operacao="Nao Existe")
    assert r["ok"] is False


def test_testar_operacao_conector_so_conector(sessao, dados):
    """Um instrumento que não é conector recusa o teste."""
    ctx, f = _setup(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    iid = _chamar(f, "configurar_instrumento", nome="Busca", tipo="busca_web")["id"]
    r = _chamar(f, "testar_operacao_conector", conector_id=iid, operacao="x")
    assert r["ok"] is False


# ─────────────────────────── Central ───────────────────────────


def test_central_tem_capitulo_construir_conector():
    conhecimento.recarregar()
    cap = conhecimento.obter("instrumentos/construir-conector")
    assert cap is not None
    # o capítulo ensina o ponto que gerou o erro real (o nome do campo do Bubble)
    assert "constraints" in cap.corpo
    # e é encontrável pela busca que a IA usa (consultar_conhecimento)
    achados = conhecimento.buscar("construir conector bubble constraints", limite=3)
    assert "instrumentos/construir-conector" in [c.slug for c in achados]
