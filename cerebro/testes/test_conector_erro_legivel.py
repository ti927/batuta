"""O "Testar e detectar" do Construtor não pode dizer só "a chamada falhou".

2026-09-22: o maestro montou o conector do Search Console, clicou em testar e leu
**"A chamada falhou."** — nada mais. A explicação do Google tinha chegado e sido
jogada fora: `_executar_operacao` devolve `ok:false` + `status` + `corpo` numa
resposta 4xx, SEM a chave `erro`, e quem lia só `erro` caía no texto genérico.

É a §12-A na tela feita justamente para ninguém ficar no escuro. Estes testes fixam
que o motivo volta, e que ele vem do CORPO — que é onde o serviço explica.
"""

from instrumentos.conector import _erro_legivel


def test_mensagem_do_google_chega_inteira():
    """Formato do Google: {"error": {"code": 400, "message": "..."}}."""
    texto = _erro_legivel({
        "ok": False,
        "status": 400,
        "corpo": {
            "error": {
                "code": 400,
                "message": "Invalid JSON payload received. Unknown name 'foo'.",
                "status": "INVALID_ARGUMENT",
            }
        },
    })
    assert "400" in texto
    assert "Invalid JSON payload" in texto


def test_permissao_negada_diz_o_motivo_real():
    """O erro mais provável da conta de serviço: a chave está certa, mas ninguém deu
    acesso a ela na propriedade. Sem esta frase, parece problema da chave."""
    texto = _erro_legivel({
        "ok": False,
        "status": 403,
        "corpo": {"error": {"message": "User does not have sufficient permission for site."}},
    })
    assert "403" in texto
    assert "sufficient permission" in texto


def test_corpo_em_texto_puro_tambem_aparece():
    """Nem toda API responde JSON — o texto cru serve igual."""
    texto = _erro_legivel({"ok": False, "status": 502, "corpo": "Bad Gateway"})
    assert "502" in texto and "Bad Gateway" in texto


def test_sem_corpo_ainda_diz_o_status():
    """Pior caso: corpo vazio. Ainda assim o status é informação — e o texto diz, em
    vez de fingir que não sabe nada."""
    texto = _erro_legivel({"ok": False, "status": 404, "corpo": None})
    assert "404" in texto
    assert "sem detalhe" in texto


def test_corpo_gigante_e_cortado():
    """O corpo vai para uma tela e para o rastro: um HTML de 2 MB não pode ir junto."""
    texto = _erro_legivel({"ok": False, "status": 400, "corpo": "x" * 5000})
    assert len(texto) < 500


def test_testar_operacao_devolve_o_erro_em_resposta_4xx(monkeypatch):
    """O caminho completo: o que a TELA recebe quando o serviço recusa."""
    import instrumentos.conector as mod
    from instrumentos.conector import Conector, ConfigConector, OperacaoConector

    monkeypatch.setattr(
        mod,
        "_executar_operacao",
        lambda *a, **k: {
            "ok": False,
            "status": 403,
            "corpo": {"error": {"message": "User does not have sufficient permission"}},
        },
    )
    config = ConfigConector(
        operacoes=[OperacaoConector(nome="consultar", metodo="POST", url="https://x/y")]
    )
    r = Conector().testar_operacao(config, "consultar", {})
    assert r["ok"] is False
    assert r["erro"], "voltou sem motivo — a tela diria 'a chamada falhou' de novo"
    assert "403" in r["erro"] and "permission" in r["erro"]
    # e o corpo continua vindo, para a tela poder mostrá-lo inteiro
    assert r["corpo"]["error"]["message"]


# ── O corpo JSON precisa dos TIPOS certos ───────────────────────────────────────
# 2026-09-22: o `searchAnalytics/query` do Google quer `"dimensions": ["query"]` —
# uma LISTA. Todo campo do Construtor é digitado como texto, e com `"query"` em texto
# o Google recusa. Sem isto, o Construtor só serviria para API de corpo todo-string.


def test_lista_digitada_vira_lista_de_verdade():
    from instrumentos.conector import _valor_json

    assert _valor_json('["query","page"]') == ["query", "page"]
    assert _valor_json('{"a": 1}') == {"a": 1}


def test_booleanos_e_nulo():
    from instrumentos.conector import _valor_json

    assert _valor_json("true") is True
    assert _valor_json("false") is False
    assert _valor_json("null") is None


def test_numero_NAO_e_convertido():
    """De propósito. "0055" e "17841400000000000" são identificadores que viram outra
    coisa ao virar número — e as APIs do Google aceitam número em texto. Trocar um id
    em silêncio seria pior que o incômodo que a conversão resolve."""
    from instrumentos.conector import _valor_json

    assert _valor_json("20") == "20"
    assert _valor_json("0055") == "0055"
    assert _valor_json("17841400000000000") == "17841400000000000"


def test_texto_que_so_PARECE_json_segue_texto():
    from instrumentos.conector import _valor_json

    assert _valor_json("[isso nao fecha") == "[isso nao fecha"
    assert _valor_json("2026-09-22") == "2026-09-22"
    assert _valor_json("") == ""


# ── Nem todo POST escreve ───────────────────────────────────────────────────────
# 2026-09-22: a consulta do Google Search Console é POST porque o filtro não cabe na
# URL — e só LÊ. Derivando do método, CADA consulta pararia para pedir aprovação, o
# que torna o instrumento inutilizável. Marcar "só consulta" é ato consciente de quem
# monta; o Batuta não tem como conferir se um POST escreve.


def _op(**kw):
    from instrumentos.conector import OperacaoConector

    return OperacaoConector(**{"nome": "o", "url": "https://x", **kw})


def test_get_nunca_escreve():
    from instrumentos.conector import _operacao_escreve

    assert _operacao_escreve(_op(metodo="GET")) is False


def test_post_escreve_por_padrao():
    """O padrão continua conservador: POST pede aprovação até alguém dizer o contrário."""
    from instrumentos.conector import _operacao_escreve

    assert _operacao_escreve(_op(metodo="POST")) is True


def test_post_marcado_como_consulta_nao_pede_aprovacao():
    from instrumentos.conector import _operacao_escreve

    assert _operacao_escreve(_op(metodo="POST", somente_leitura=True)) is False


def test_marcar_get_como_so_leitura_nao_muda_nada():
    from instrumentos.conector import _operacao_escreve

    assert _operacao_escreve(_op(metodo="GET", somente_leitura=True)) is False


def test_a_ferramenta_carrega_a_irreversibilidade_da_OPERACAO():
    """A prova que liga isto ao motor: cada operação vira uma ferramenta com o seu
    próprio carimbo, lido por `agente.py::_irreversivel_da_ferramenta`."""
    from instrumentos.conector import Conector, ConfigConector
    from orquestracao.agente import _irreversivel_da_ferramenta

    config = ConfigConector(
        operacoes=[
            _op(nome="consultar", metodo="POST", somente_leitura=True),
            _op(nome="publicar", metodo="POST"),
        ]
    )
    tools = Conector().expandir_ferramentas(config)
    mapa = {t.name: _irreversivel_da_ferramenta(t, True) for t in tools}
    assert list(mapa.values()) == [False, True], mapa


def test_instrumento_so_de_consulta_nao_exige_parede():
    """Antes, UM POST no conector obrigava portão para o instrumento inteiro."""
    from instrumentos.conector import Conector

    so_consulta = {"operacoes": [{"nome": "c", "metodo": "POST", "url": "https://x",
                                  "somente_leitura": True}]}
    assert Conector().irreversivel_para(so_consulta) is False
    com_escrita = {"operacoes": [
        {"nome": "c", "metodo": "POST", "url": "https://x", "somente_leitura": True},
        {"nome": "p", "metodo": "POST", "url": "https://x"},
    ]}
    assert Conector().irreversivel_para(com_escrita) is True
