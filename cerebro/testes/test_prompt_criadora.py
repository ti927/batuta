"""O prompt único da IA criadora (conversa eterna sobre o time real).

Sem modos: um só prompt que investiga, monta, ativa e mantém. Garante que as peças
essenciais estão lá (investigação do ofício, vocabulário, a PAREDE do portão no nó,
regra dos markdowns) e que o catálogo e o time atual são injetados."""

from criacao.prompt import montar_prompt_criadora


def test_prompt_tem_as_pecas_essenciais():
    p = montar_prompt_criadora()
    # conversa que não termina + segurança por ativação (não por rascunho)
    assert "não termina" in p.lower() or "nunca termina" in p.lower()
    assert "dorme" in p.lower()
    # investiga incorporando o ofício, uma pergunta por vez
    assert "OFÍCIO" in p
    assert "Uma pergunta por mensagem" in p
    # vocabulário e regra dos markdowns
    assert "agent_md" in p and "soul_md" in p
    assert "AGE, não pergunta" in p and "REPASSE LIMPO" in p
    # a PAREDE: portão no NÓ anterior (não na saída)
    assert "pausa_humano" in p
    assert "NÓ" in p
    # modelos por papel e formato de gatilho injetado
    assert "claude-haiku-4-5" in p
    assert "frequencia" in p
    # catálogo de instrumentos injetado (com a marca de irreversível)
    assert "publicar_wordpress" in p
    assert "acao_irreversivel" in p


def test_prompt_injeta_o_time_atual():
    snap = {"time": {"id": "t1", "nome": "Blog SEO", "descricao": None}, "agentes": []}
    p = montar_prompt_criadora(snap)
    assert "Time atual" in p
    assert "Blog SEO" in p


def test_prompt_sem_time_nao_tem_secao_de_time():
    p = montar_prompt_criadora(None)
    assert "Time atual" not in p
