"""Testes do instrumento MCP.

A conexão real a um servidor MCP precisa de um servidor de verdade; aqui a
camada de conexão é mockada. Provam o registro, os segredos, e — o ponto
central — que UM instrumento MCP se expande em VÁRIAS ferramentas no cinto,
sem afetar os instrumentos de ferramenta única.

A segunda metade do arquivo (2026-09-21) cobre os quatro defeitos que mantiveram o
MCP com ZERO instâncias em produção desde junho. Ver `docs/MCP-AGENTES.md`.
"""

import uuid
from types import SimpleNamespace

from pydantic import BaseModel

import instrumentos as encaixe
import instrumentos.mcp as mcp_mod
from instrumentos.mcp import ArgsMCP, ConectarMCP, ConfigMCP
from modelos import Instrumento
from orquestracao.agente import _ferramentas_de_instrumento


class _ArgsFake(BaseModel):
    q: str = "x"


def _ferramenta_fake(nome: str):
    async def ainvoke(kwargs):  # não é exercitada nestes testes
        return f"ok:{nome}"

    return SimpleNamespace(
        name=nome, description=f"ferramenta {nome}", args_schema=_ArgsFake, ainvoke=ainvoke
    )


def _instrumento(tipo: str, configuracao: dict) -> Instrumento:
    inst = Instrumento(
        id=uuid.uuid4(),  # objeto transitório: o id normalmente vem do banco
        time_id=uuid.uuid4(),
        nome="i",
        tipo=tipo,
        configuracao=configuracao,
    )
    inst.segredos_decifrados = {}
    return inst


def test_mcp_registrado_com_url_e_token_secretos():
    """A URL é segredo junto com o token: servidores como o do Zapier embutem a
    chave no endereço, e ali quem tem a URL tem a conta."""
    t = encaixe.obter_tipo("conectar_mcp")
    assert t is not None
    assert t.campos_secretos == ("url", "token_bearer")
    assert t.campos_secretos_opcionais == ("token_bearer",)
    assert "mcp" in t.tipos_credencial_aceitos
    assert "conectar_mcp" in [x.tipo for x in encaixe.tipos_disponiveis()]


def test_expandir_em_varias_ferramentas(monkeypatch):
    monkeypatch.setattr(
        mcp_mod, "_carregar_sync",
        lambda c, **kw: [_ferramenta_fake("buscar"), _ferramenta_fake("criar")],
    )
    tools = ConectarMCP().expandir_ferramentas(ConfigMCP(url="https://mcp.x.com"))
    assert [t.name for t in tools] == ["buscar", "criar"]


def test_executar_testa_conexao_e_lista(monkeypatch):
    monkeypatch.setattr(
        mcp_mod, "_carregar_sync", lambda c, **kw: [_ferramenta_fake("buscar")]
    )
    r = ConectarMCP().executar(ConfigMCP(url="https://mcp.x.com"), ArgsMCP())
    assert r["ok"] is True
    assert [f["nome"] for f in r["ferramentas"]] == ["buscar"]


def test_seam_mcp_expande_no_cinto(monkeypatch):
    """O ponto central: o encaixe transforma 1 instrumento MCP em N ferramentas."""
    monkeypatch.setattr(
        mcp_mod, "_carregar_sync",
        lambda c, **kw: [_ferramenta_fake("a"), _ferramenta_fake("b"), _ferramenta_fake("c")],
    )
    inst = _instrumento("conectar_mcp", {"url": "https://mcp.x.com"})
    tools = _ferramentas_de_instrumento(inst, [], {}, [], {})
    assert [t.name for t in tools] == ["a", "b", "c"]


def test_seam_instrumento_normal_uma_ferramenta():
    """Instrumento comum continua com exatamente uma ferramenta."""
    inst = _instrumento("busca_web", {})
    tools = _ferramentas_de_instrumento(inst, [], {}, [], {})
    assert len(tools) == 1


def test_token_vira_authorization_bearer():
    conexao = mcp_mod._conexao(ConfigMCP(url="https://x", token_bearer="segredo123"))
    assert conexao["headers"]["Authorization"] == "Bearer segredo123"
    assert conexao["transport"] == "streamable_http" and conexao["url"] == "https://x"


# ───────────────── 2026-09-21: o que faltava para o MCP servir ─────────────────
# Quatro defeitos o mantiveram com ZERO instâncias em produção desde junho.
# Um teste por defeito — e um pelo lado do motor, provando que o resto não mudou.


def _config(ferramentas: list[dict] | None = None) -> ConfigMCP:
    return ConfigMCP(url="https://mcp.x.com/s/CHAVE/mcp", ferramentas=ferramentas or [])


def test_so_entram_no_cinto_as_ferramentas_escolhidas(monkeypatch):
    """Defeito 1: trazia TODAS. Um servidor como o do Zapier publica dezenas —
    o cinto entope, o custo por passo sobe e o agente escolhe errado."""
    monkeypatch.setattr(
        mcp_mod, "_carregar_sync",
        lambda c, **kw: [_ferramenta_fake("ler"), _ferramenta_fake("apagar")],
    )
    tools = ConectarMCP().expandir_ferramentas(
        _config([{"nome": "ler", "usar": True}, {"nome": "apagar", "usar": False}])
    )
    assert [t.name for t in tools] == ["ler"]


def test_sem_escolha_entram_todas(monkeypatch):
    """Lista vazia = comportamento antigo (todas), que é o mais seguro dos dois:
    nenhuma instância antiga fica sem ferramenta de um dia para o outro."""
    monkeypatch.setattr(
        mcp_mod, "_carregar_sync",
        lambda c, **kw: [_ferramenta_fake("a"), _ferramenta_fake("b")],
    )
    tools = ConectarMCP().expandir_ferramentas(_config())
    assert [t.name for t in tools] == ["a", "b"]
    assert all(t.metadata["irreversivel"] for t in tools)


def test_cada_ferramenta_carrega_a_propria_irreversibilidade(monkeypatch):
    """Defeito 2: era tudo ou nada. Um mesmo servidor publica consulta e escrita —
    e o motor precisa saber qual é qual para parar só na que precisa."""
    monkeypatch.setattr(
        mcp_mod, "_carregar_sync",
        lambda c, **kw: [_ferramenta_fake("ler"), _ferramenta_fake("enviar")],
    )
    tools = ConectarMCP().expandir_ferramentas(
        _config([
            {"nome": "ler", "usar": True, "irreversivel": False},
            {"nome": "enviar", "usar": True, "irreversivel": True},
        ])
    )
    assert {t.name: t.metadata["irreversivel"] for t in tools} == {
        "ler": False,
        "enviar": True,
    }


def test_o_motor_gateia_so_a_ferramenta_irreversivel(monkeypatch):
    """A prova do lado do MOTOR: o mapa que o portão nativo consulta passa a ter um
    valor POR FERRAMENTA, não um por instrumento — e o embrulho de rastro que fica
    no meio do caminho não pode perder o carimbo."""
    from orquestracao.agente import _irreversivel_da_ferramenta

    monkeypatch.setattr(
        mcp_mod, "_carregar_sync",
        lambda c, **kw: [_ferramenta_fake("ler"), _ferramenta_fake("enviar")],
    )
    inst = _instrumento("conectar_mcp", {
        "url": "https://mcp.x.com",
        "ferramentas": [
            {"nome": "ler", "usar": True, "irreversivel": False},
            {"nome": "enviar", "usar": True, "irreversivel": True},
        ],
    })
    tools = _ferramentas_de_instrumento(inst, [], {}, [], {})
    assert {t.name: _irreversivel_da_ferramenta(t, True) for t in tools} == {
        "ler": False,
        "enviar": True,
    }


def test_instrumento_so_de_leitura_nao_exige_portao():
    """`acao_irreversivel` era True fixo: até um MCP de pura consulta obrigava portão
    de aprovação na cadeia. Agora a resposta sai das ferramentas escolhidas."""
    t = ConectarMCP()
    assert t.irreversivel_para(
        {"ferramentas": [{"nome": "ler", "usar": True, "irreversivel": False}]}
    ) is False
    assert t.irreversivel_para({"ferramentas": [
        {"nome": "ler", "usar": True, "irreversivel": False},
        {"nome": "apagar", "usar": True, "irreversivel": True},
    ]}) is True
    # sem escolha nenhuma, não sabemos o que o servidor faz → segue exigindo
    assert t.irreversivel_para({}) is True
    assert t.irreversivel_para({"ferramentas": "lixo"}) is True


def test_acionar_nao_devolve_a_url(monkeypatch):
    """Defeito 3: o retorno do instrumento vai inteiro para o rastro da execução.
    Com a chave na URL, devolvê-la ali era vazar a credencial."""
    monkeypatch.setattr(
        mcp_mod, "_carregar_sync", lambda c, **kw: [_ferramenta_fake("ler")]
    )
    r = ConectarMCP().executar(_config(), ArgsMCP())
    assert "CHAVE" not in str(r)
    assert r["ferramentas"][0]["no_cinto"] is True


def test_sem_url_a_falha_diz_o_que_fazer():
    from instrumentos.base import FalhaInstrumento

    try:
        mcp_mod._carregar_sync(ConfigMCP())
    except FalhaInstrumento as e:
        assert "credencial" in str(e).lower()
    else:  # pragma: no cover
        raise AssertionError("deveria ter recusado sem endereço")


def test_lista_de_ferramentas_fica_em_cache(monkeypatch):
    """Sem cache, a lista era buscada NA REDE a cada passo do agente — uma ida ao
    servidor de terceiro antes de todo trabalho útil."""
    idas = []

    async def _falso(config):
        idas.append(1)
        return [_ferramenta_fake("ler")]

    mcp_mod._CACHE.clear()
    monkeypatch.setattr(mcp_mod, "_carregar_ferramentas", _falso)
    c = _config()
    mcp_mod._carregar_sync(c)
    mcp_mod._carregar_sync(c)
    assert idas == [1], "a segunda chamada deveria ter vindo do cache"
    # "Acionar" ignora o cache de propósito: quem clica quer a verdade de agora
    ConectarMCP().executar(c, ArgsMCP())
    assert idas == [1, 1]
    mcp_mod._CACHE.clear()


def test_credencial_mcp_carrega_a_conexao_inteira():
    """Um instrumento aponta para UMA credencial (`credencial_id` é um só). Se a
    credencial do MCP tivesse só o endereço, o token teria de ser colado no
    instrumento — e aí cada time voltaria a ter uma cópia do segredo, que é
    exatamente o que tirá-lo do instrumento resolveu."""
    import tipos_credencial

    tc = tipos_credencial.obter_tipo("mcp")
    assert tc is not None
    assert tc.nomes_campos == ("url", "token_bearer")
    # os dois campos do instrumento ficam cobertos por ESTA credencial sozinha —
    # senão a tela marcaria o instrumento como incompleto para sempre
    from segredos_instrumento import pendentes

    assert pendentes(
        "conectar_mcp",
        guardados=set(),
        cobertos_por_credencial=frozenset(tc.nomes_campos),
    ) == []


def test_servidor_fora_do_ar_nao_derruba_o_passo():
    """Defeito 4 (§12-A): montar o cinto de um MCP fala com o servidor. Antes, um
    servidor de terceiro fora do ar derrubava o passo INTEIRO — inclusive os outros
    instrumentos, sãos, e inclusive um trabalho que nem dependia dele."""
    from orquestracao import agente as agente_mod

    erros: list[dict] = []
    falhas: list[str] = []
    inst = _instrumento("conectar_mcp", {"url": "https://mcp.x.com"})
    inst.nome = "Zapier do Julio"

    agente_mod._cinto_sem(
        inst, RuntimeError("servidor MCP não respondeu"), erros, falhas
    )
    assert erros[0]["origem"] == "cinto"
    assert erros[0]["tipo"] == "conectar_mcp"
    assert "Zapier do Julio" in erros[0]["erro"]
    # a IA precisa saber que rodou sem ele — senão narra sucesso sobre o que não teve
    assert falhas and "Zapier do Julio" in falhas[0]
