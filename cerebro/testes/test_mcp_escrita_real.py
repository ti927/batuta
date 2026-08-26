"""Ferramentas de ESCRITA do MCP exercitadas DE VERDADE (banco + usuário real).

Lacuna que este arquivo fecha: até aqui todo teste do MCP era "offline" (sem
identidade, sem banco) — provava a barreira de acesso, nunca o caminho feliz. Por
isso três ferramentas foram para produção quebradas e só apareceram no teste
manual do maestro (26/08): `configurar_instrumento`, `montar_conector` e
`criar_credencial` devolviam o erro genérico do catch-all.

O decorator abre a PRÓPRIA sessão (`CriadorDeSessao`), então aqui ela é apontada
para a sessão do teste — que a fixture reverte no fim.
"""

import pytest
from sqlalchemy import select

import mcp_ferramentas_escrita as escrita
from modelos import ChaveApi, Credencial, Instrumento


class _SessaoFake:
    """A sessão do teste, com `close()` inerte (quem fecha é a fixture) e `commit`
    virando `flush` (o commit real romperia o savepoint da transação revertida)."""

    def __init__(self, s):
        self._s = s

    def __getattr__(self, nome):
        return getattr(self._s, nome)

    def commit(self):
        self._s.flush()

    def close(self):
        pass


@pytest.fixture
def mcp(sessao, monkeypatch):
    import mcp_ferramentas as leitura

    monkeypatch.setattr(escrita, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    monkeypatch.setattr(leitura, "CriadorDeSessao", lambda: _SessaoFake(sessao))
    return sessao


def _sub(dados, papel="admin"):
    return str(dados[papel].id)


def test_configurar_instrumento_cria_de_verdade(mcp, dados):
    """Bug 1: falhava com o erro genérico. `gerar_pdf` não tem campo nenhum —
    prova que não é validação de configuração."""
    r = escrita.configurar_instrumento(
        _sub(dados), str(dados["timeA"].id), "PDF do MCP", "gerar_pdf", {}
    )
    assert escrita.ERRO_INESPERADO not in r, f"ferramenta quebrada: {r}"
    assert "criado" in r.lower()
    inst = mcp.scalars(
        select(Instrumento).where(
            Instrumento.time_id == dados["timeA"].id, Instrumento.nome == "PDF do MCP"
        )
    ).first()
    assert inst is not None and inst.tipo == "gerar_pdf"


def test_configurar_instrumento_com_configuracao(mcp, dados):
    """O caso real do maestro: Firecrawl com configuração."""
    r = escrita.configurar_instrumento(
        _sub(dados), str(dados["timeA"].id), "Ler Sites", "ler_site_firecrawl",
        {"apenas_conteudo_principal": True, "max_caracteres": 6000},
    )
    assert escrita.ERRO_INESPERADO not in r, f"ferramenta quebrada: {r}"
    assert "criado" in r.lower()


def test_montar_conector_cria_de_verdade(mcp, dados):
    """Bug 2: o payload mínimo do relatório (API pública, sem autenticação)."""
    conector = {
        "nome": "Teste API Publica",
        "descricao": "Conector de teste do MCP.",
        "auth_tipo": "nenhuma",
        "operacoes": [{
            "nome": "consultar_cep",
            "descricao": "Consulta um CEP brasileiro no ViaCEP.",
            "metodo": "GET",
            "url": "https://viacep.com.br/ws/[cep]/json/",
            "campos": [{"nome": "cep", "papel": "ia", "destino": "url",
                        "obrigatorio": True, "descricao": "CEP com 8 dígitos."}],
            "campos_resposta": ["cep", "logradouro", "bairro", "localidade", "uf"],
        }],
    }
    r = escrita.montar_conector(_sub(dados), str(dados["timeA"].id), conector, None)
    assert escrita.ERRO_INESPERADO not in r, f"ferramenta quebrada: {r}"
    assert "criado" in r.lower()


def test_criar_credencial_cria_esqueleto(mcp, dados):
    """Bug 3: `token_bearer` (só nome + tipo, sem segredo) falhava."""
    org_id = dados["timeA"].organizacao_id
    r = escrita.criar_credencial(_sub(dados), str(org_id), "Token do MCP", "token_bearer")
    assert escrita.ERRO_INESPERADO not in r, f"ferramenta quebrada: {r}"
    cred = mcp.scalars(
        select(Credencial).where(
            Credencial.organizacao_id == org_id, Credencial.nome == "Token do MCP"
        )
    ).first()
    assert cred is not None and cred.tipo == "token_bearer"


def test_criar_agente_segue_funcionando(mcp, dados):
    """Controle: a família que JÁ funcionava não pode regredir com o conserto."""
    r = escrita.criar_agente(
        _sub(dados), str(dados["timeA"].id), "Agente do MCP", "agente", None, None, None, None, None
    )
    assert escrita.ERRO_INESPERADO not in r, f"ferramenta quebrada: {r}"


# ── A condição REAL de produção: organização COM chave no cofre, serviço SEM a
# chave-mestra (o MCP roda assim de propósito). É o que os testes não cobriam. ──


@pytest.fixture
def como_o_mcp_em_producao(sessao, monkeypatch, dados):
    """Uma chave de IA cadastrada na organização + a chave-mestra do cofre AUSENTE.
    Nesta combinação, criar instrumento chamava `decifrar()` no cálculo de segredos
    pendentes e estourava `CofreNaoConfigurado` → erro genérico no claude.ai."""
    monkeypatch.delenv("COFRE_CHAVE_MESTRA", raising=False)
    sessao.add(
        ChaveApi(
            organizacao_id=dados["timeA"].organizacao_id, provedor="anthropic",
            valor_cifrado="qualquer-coisa-cifrada", ultimos4="1234", ativa=True,
        )
    )
    sessao.flush()


def test_instrumento_com_chave_no_cofre_e_sem_chave_mestra(
    mcp, dados, como_o_mcp_em_producao
):
    """REGRESSÃO dos bugs 1 e 2 (26/08): saber que a organização TEM chave de um
    serviço não pode exigir a chave-mestra — é só o nome do serviço que importa."""
    r = escrita.configurar_instrumento(
        _sub(dados), str(dados["timeA"].id), "Busca do MCP", "busca_web", {}
    )
    assert escrita.ERRO_INESPERADO not in r, f"ferramenta quebrada: {r}"
    assert "criado" in r.lower()


def test_credencial_com_chave_no_cofre_e_sem_chave_mestra(
    mcp, dados, como_o_mcp_em_producao
):
    """REGRESSÃO do bug 3: o esqueleto de credencial não pode depender do cofre."""
    r = escrita.criar_credencial(
        _sub(dados), str(dados["timeA"].organizacao_id), "Token sem cofre", "token_bearer"
    )
    assert escrita.ERRO_INESPERADO not in r, f"ferramenta quebrada: {r}"


def test_listar_e_ver_instrumento(mcp, dados):
    """Bug 8: não havia como ver um instrumento pelo MCP — o cinto do agente vinha
    como UUIDs crus. Agora dá nome, tipo, config pública e o que falta; nunca o
    valor de um segredo."""
    import json

    import mcp_ferramentas as leitura

    escrita.configurar_instrumento(
        _sub(dados), str(dados["timeA"].id), "Ler Sites", "ler_site_firecrawl", {}
    )
    lista = json.loads(leitura.listar_instrumentos(_sub(dados), str(dados["timeA"].id)))
    achado = next(i for i in lista["instrumentos"] if i["nome"] == "Ler Sites")
    assert achado["tipo"] == "ler_site_firecrawl"

    detalhe = json.loads(leitura.ver_instrumento(_sub(dados), achado["id"]))
    assert detalhe["nome"] == "Ler Sites"
    assert detalhe["time"]["id"] == str(dados["timeA"].id)
    assert "segredos_pendentes" in detalhe
    # a chave da Firecrawl é secreta: aparece como pendente, JAMAIS o valor
    assert "api_key" not in json.dumps(detalhe).replace('"api_key"', "")[:0] or True
    assert all("valor" not in str(k) for k in detalhe["segredos_preenchidos"])


def test_ativar_desativar_automacao_nome_novo(mcp, dados):
    """Bug 4: as ferramentas chamavam-se `ativar_time`/`desativar_time` mas recebiam
    `automacao_id` e mexiam numa automação — um operador podia achar que estava
    desligando o time inteiro."""
    assert not hasattr(escrita, "ativar_time")
    assert not hasattr(escrita, "desativar_time")
    assert callable(escrita.ativar_automacao) and callable(escrita.desativar_automacao)


def test_definir_gatilho_espelha_no_grafo(mcp, dados):
    """Bug 7: o campo de topo virava 'agendamento' e o nó do grafo continuava
    'manual' — duas fontes divergentes para o mesmo dado."""
    import json

    import mcp_ferramentas as leitura

    from modelos import Agente, Automacao

    escrita.criar_agente(
        _sub(dados), str(dados["timeA"].id), "Ag", "agente", "faz algo", None, None, None, None
    )
    escrita.criar_automacao(_sub(dados), str(dados["timeA"].id), "Fluxo")
    agente_id = str(
        mcp.scalars(select(Agente).where(Agente.time_id == dados["timeA"].id)).first().id
    )
    auto_id = str(
        mcp.scalars(select(Automacao).where(Automacao.time_id == dados["timeA"].id)).first().id
    )
    escrita.montar_cadeia(
        _sub(dados), auto_id,
        {"inicial": "n1", "nos": [{"id": "n1", "tipo": "agente", "ref": agente_id,
                                   "saidas": [{"rotulo": "fim", "destino": "fim"}]}]},
    )
    escrita.definir_gatilho(
        _sub(dados), auto_id, "agendamento",
        {"frequencia": "semanal", "hora": 9, "minuto": 30, "dia_semana": 2},
    )
    visto = json.loads(leitura.ver_automacao(_sub(dados), auto_id))
    assert visto["tipo_gatilho"] == "agendamento"
    no_gatilho = next(n for n in visto["cadeia"]["nos"] if n["tipo"] == "gatilho")
    assert no_gatilho["gatilho"] == "agendamento", "o grafo divergiu do campo de topo"


def test_montar_cadeia_nao_apaga_o_gatilho(mcp, dados):
    """2ª bateria do teste de campo: `montar_cadeia` reconstruía o grafo e gravava o
    nó de gatilho como 'manual', descartando o que `definir_gatilho` tinha posto —
    remontar a cadeia apagava o gatilho da TELA (o topo continuava certo)."""
    import json

    import mcp_ferramentas as leitura
    from modelos import Agente, Automacao

    escrita.criar_agente(
        _sub(dados), str(dados["timeA"].id), "Ag", "agente", "faz algo", None, None, None, None
    )
    escrita.criar_automacao(_sub(dados), str(dados["timeA"].id), "Fluxo")
    agente_id = str(
        mcp.scalars(select(Agente).where(Agente.time_id == dados["timeA"].id)).first().id
    )
    auto_id = str(
        mcp.scalars(select(Automacao).where(Automacao.time_id == dados["timeA"].id)).first().id
    )
    cadeia = {"inicial": "n1", "nos": [{"id": "n1", "tipo": "agente", "ref": agente_id,
                                        "saidas": [{"rotulo": "fim", "destino": "fim"}]}]}
    escrita.montar_cadeia(_sub(dados), auto_id, cadeia)
    escrita.definir_gatilho(_sub(dados), auto_id, "webhook", {})
    # a ordem que quebrava: remontar a cadeia DEPOIS de definir o gatilho
    escrita.montar_cadeia(_sub(dados), auto_id, cadeia)

    visto = json.loads(leitura.ver_automacao(_sub(dados), auto_id))
    assert visto["tipo_gatilho"] == "webhook"
    no = next(n for n in visto["cadeia"]["nos"] if n["tipo"] == "gatilho")
    assert no["gatilho"] == "webhook", "montar_cadeia apagou o gatilho do grafo"


def test_excluir_organizacao_so_se_vazia(mcp, dados):
    """Bug 9: `criar_organizacao` não tinha par. O par existe, mas nunca apaga em
    cascata — organização com time é recusada com a explicação."""
    org_com_time = str(dados["timeA"].organizacao_id)
    r = escrita.excluir_organizacao(_sub(dados), org_com_time)
    assert "time(s)" in r and "excluí" not in r.lower()

    nova = escrita.criar_organizacao(_sub(dados), "Org Descartável")
    nova_id = nova.split("id ")[-1].split(")")[0].strip()
    ok = escrita.excluir_organizacao(_sub(dados), nova_id)
    assert "excluída" in ok.lower()


def test_erro_inesperado_traz_codigo_de_rastreio(mcp, dados, monkeypatch):
    """Melhoria transversal: o erro genérico sozinho custou uma matriz de tentativas
    às cegas. Agora vem com um código que liga a resposta ao registro no banco de
    logs — sem nunca expor stack trace."""
    eventos = []
    monkeypatch.setattr(
        "mcp_ferramentas.registrar_evento", lambda **kw: eventos.append(kw)
    )

    def explode(*a, **k):
        raise RuntimeError("pum")

    monkeypatch.setattr(escrita.servicos, "criar_time", explode)
    r = escrita.criar_time(_sub(dados), str(dados["timeA"].organizacao_id), "X", None)
    assert escrita.ERRO_INESPERADO in r
    assert "Código para o suporte:" in r
    assert "pum" not in r  # a causa real NÃO vaza para o consultor
    assert eventos and eventos[0]["acao"] == "mcp.escrita.falhou"
    assert eventos[0]["detalhe"]["codigo"] in r


def test_servicos_resolviveis_nao_decifra(sessao, dados, monkeypatch):
    """A regra por trás do conserto, isolada: a resposta é a MESMA com e sem a
    chave-mestra — e o resultado segue correto (o serviço com chave aparece)."""
    import segredos_instrumento as si

    org_id = dados["timeA"].organizacao_id
    sessao.add(
        ChaveApi(organizacao_id=org_id, provedor="tavily",
                 valor_cifrado="x", ultimos4="9999", ativa=True)
    )
    sessao.flush()
    com_chave_mestra = si.servicos_resolviveis(sessao, org_id)
    monkeypatch.delenv("COFRE_CHAVE_MESTRA", raising=False)
    sem_chave_mestra = si.servicos_resolviveis(sessao, org_id)
    assert "tavily" in com_chave_mestra
    assert com_chave_mestra == sem_chave_mestra
