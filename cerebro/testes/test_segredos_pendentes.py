"""Cálculo HONESTO de segredos pendentes (fix do falso-alerta de 'faltam segredos').

Antes, um segredo só não era 'pendente' se estivesse preenchido inline no próprio
instrumento — ignorando as outras duas fontes que a borda usa de verdade: a
credencial nomeada apontada e a chave de serviço compartilhada do pool
(org → consultoria). Resultado: a tela /criar e a fala da IA acusavam falta de
chave Tavily / senha do WordPress mesmo com o cofre cobrindo. Estes testes fixam o
comportamento correto: pendente = o que NENHUMA das três fontes cobre.
"""

import json
import uuid

import cofre
import credenciais_cofre
import segredos_instrumento as segredos
from criacao.ferramentas import ContextoCriacao, ferramenta_por_nome
from modelos import ChaveApi, ConversaCriacao, Credencial, Instrumento


# ───────────────────────── unidade: pendentes() ─────────────────────────
# Função pura (sem banco): combina as três fontes de cobertura.

def test_pendentes_sem_nenhuma_fonte_acusa_o_secreto():
    assert segredos.pendentes("busca_web", guardados=set()) == ["chave_api"]


def test_pendentes_inline_cobre():
    assert segredos.pendentes("busca_web", guardados={"chave_api"}) == []


def test_pendentes_chave_compartilhada_coberta_pelo_pool():
    # busca_web reusa a Tavily do pool: se o serviço é resolvível, não é pendente.
    assert (
        segredos.pendentes(
            "busca_web", guardados=set(), servicos_resolviveis={"tavily"}
        )
        == []
    )


def test_pendentes_compartilhada_sem_pool_continua_pendente():
    assert (
        segredos.pendentes(
            "busca_web", guardados=set(), servicos_resolviveis={"openai"}
        )
        == ["chave_api"]
    )


def test_pendentes_wordpress_sem_fonte():
    assert segredos.pendentes("publicar_wordpress", guardados=set()) == ["senha_app"]


def test_pendentes_wordpress_credencial_cobre():
    assert (
        segredos.pendentes(
            "publicar_wordpress",
            guardados=set(),
            cobertos_por_credencial={"usuario", "senha_app"},
        )
        == []
    )


# ──────────────────── unidade: servicos_resolviveis() ───────────────────

def test_servicos_resolviveis_pelo_env_legado(sessao, dados, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tav-env")
    res = segredos.servicos_resolviveis(sessao, dados["orgA"].id)
    assert "tavily" in res


def test_servicos_resolviveis_vazio_sem_chave(sessao, dados, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    res = segredos.servicos_resolviveis(sessao, dados["orgA"].id)
    assert "tavily" not in res


def test_servicos_resolviveis_pela_chave_da_org(sessao, dados, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    sessao.add(
        ChaveApi(
            organizacao_id=dados["orgA"].id,
            provedor="tavily",
            valor_cifrado=cofre.cifrar("tav-cofre"),
            ativa=True,
        )
    )
    sessao.flush()
    res = segredos.servicos_resolviveis(sessao, dados["orgA"].id)
    assert "tavily" in res


# ─────────────── integração: snapshot do time (ver_time) ────────────────

def _ferramentas(sessao, dados):
    conversa = ConversaCriacao(
        organizacao_id=dados["orgA"].id, criada_por_id=dados["admin"].id
    )
    sessao.add(conversa)
    sessao.flush()
    ctx = ContextoCriacao(sessao=sessao, conversa=conversa, usuario=dados["admin"])
    return ctx, ferramenta_por_nome(ctx)


def _chamar(f, ferramenta, **kw):
    return json.loads(f[ferramenta].func(**kw))


def test_busca_web_nao_pendente_com_tavily_no_cofre(sessao, dados, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    sessao.add(
        ChaveApi(
            organizacao_id=dados["orgA"].id,
            provedor="tavily",
            valor_cifrado=cofre.cifrar("tav-cofre"),
            ativa=True,
        )
    )
    sessao.flush()
    _ctx, f = _ferramentas(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    r = _chamar(f, "configurar_instrumento", nome="Busca", tipo="busca_web")
    # Retorno imediato à IA: nada pendente (a Tavily vem do pool).
    assert r["segredos_pendentes"] == []
    # E o snapshot que vai ao front e ao prompt concorda.
    visto = _chamar(f, "ver_time")
    inst = next(i for i in visto["instrumentos"] if i["id"] == r["id"])
    assert inst["segredos_pendentes"] == []


def test_wordpress_pendente_sem_fonte(sessao, dados, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    _ctx, f = _ferramentas(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    r = _chamar(
        f,
        "configurar_instrumento",
        nome="WP",
        tipo="publicar_wordpress",
        configuracao={"site_url": "https://x.com", "usuario": "u"},
    )
    assert r["segredos_pendentes"] == ["senha_app"]


def test_wordpress_nao_pendente_apontando_credencial(sessao, dados, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    _ctx, f = _ferramentas(sessao, dados)
    _chamar(f, "definir_time", nome="T")
    r = _chamar(
        f,
        "configurar_instrumento",
        nome="WP",
        tipo="publicar_wordpress",
        configuracao={"site_url": "https://x.com", "usuario": "u"},
    )
    # Cria uma credencial WordPress na central e aponta o instrumento para ela.
    cred = Credencial(
        organizacao_id=dados["orgA"].id, nome="WP central", tipo="wordpress"
    )
    credenciais_cofre.gravar(cred, {"usuario": "u", "senha_app": "s"})
    sessao.add(cred)
    sessao.flush()
    inst = sessao.get(Instrumento, uuid.UUID(r["id"]))
    inst.credencial_id = cred.id
    sessao.flush()

    visto = _chamar(f, "ver_time")
    wp = next(i for i in visto["instrumentos"] if i["id"] == r["id"])
    assert wp["segredos_pendentes"] == []
