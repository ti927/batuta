"""O prompt único da IA criadora (conversa eterna sobre o time real).

Sem modos: um só prompt que investiga, monta, ativa e mantém. Garante que as peças
essenciais estão lá (investigação do ofício, vocabulário, a PAREDE do portão no nó,
regra dos markdowns) e que o catálogo e o time atual são injetados."""

from criacao.prompt import montar_prompt_criadora


def test_prompt_tem_as_pecas_essenciais():
    p = montar_prompt_criadora()
    # conversa que não termina
    assert "nunca termina" in p.lower()
    # as DUAS lentes: engenheiro de processos + profissional do ofício
    assert "Engenheiro de processos" in p
    assert "Profissional do ofício" in p
    # investiga ANTES de propor estrutura, uma pergunta por vez
    assert "uma pergunta por vez" in p
    assert "ANTES de propor" in p
    # vocabulário e regra dos 4 textos
    assert "agent_md" in p and "soul_md" in p
    assert "AGE, não pergunta" in p and "REPASSE LIMPO" in p
    # a PAREDE: portão no NÓ anterior (não na saída)
    assert "gate" in p
    assert "NÓ" in p
    # sinaliza ativação (não decide sozinha) e modelos válidos por papel
    assert "SINALIZE" in p and "nunca ativa sozinho" in p.lower()
    assert "claude-haiku-4-5" in p
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
