"""Testes do instrumento MCP (Fase adicional).

A conexão real a um servidor MCP precisa de um servidor de verdade; aqui a
camada de conexão é mockada. Provam o registro, o segredo (token), e — o ponto
central — que UM instrumento MCP se expande em VÁRIAS ferramentas no cinto,
sem afetar os instrumentos de ferramenta única.
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


def test_mcp_registrado_com_token_secreto():
    t = encaixe.obter_tipo("conectar_mcp")
    assert t is not None
    assert t.campos_secretos == ("token_bearer",)
    assert "conectar_mcp" in [x.tipo for x in encaixe.tipos_disponiveis()]


def test_expandir_em_varias_ferramentas(monkeypatch):
    monkeypatch.setattr(
        mcp_mod, "_carregar_sync",
        lambda c: [_ferramenta_fake("buscar"), _ferramenta_fake("criar")],
    )
    tools = ConectarMCP().expandir_ferramentas(ConfigMCP(url="https://mcp.x.com"))
    assert [t.name for t in tools] == ["buscar", "criar"]


def test_executar_testa_conexao_e_lista(monkeypatch):
    monkeypatch.setattr(
        mcp_mod, "_carregar_sync", lambda c: [_ferramenta_fake("buscar")]
    )
    r = ConectarMCP().executar(ConfigMCP(url="https://mcp.x.com"), ArgsMCP())
    assert r["ok"] is True
    assert [f["nome"] for f in r["ferramentas"]] == ["buscar"]


def test_seam_mcp_expande_no_cinto(monkeypatch):
    """O ponto central: o encaixe transforma 1 instrumento MCP em N ferramentas."""
    monkeypatch.setattr(
        mcp_mod, "_carregar_sync",
        lambda c: [_ferramenta_fake("a"), _ferramenta_fake("b"), _ferramenta_fake("c")],
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
