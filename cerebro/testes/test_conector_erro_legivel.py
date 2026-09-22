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
