"""Teste de regressão dos prompts da IA criadora (Fase 9 + refatoração em modos).

A criadora opera em TRÊS modos, cada um com seu prompt. Estes testes travam os marcos
de cada modo e — importante — o GATE no nível do texto: o prompt de investigação não
fala de montar (nem traz catálogo/gatilho); o de montagem traz as fases de criação e
os formatos. Se alguém afrouxar isso e voltar ao prompt único, o teste pega."""

from criacao.prompt import montar_prompt_criadora
from criacao.rascunho import Rascunho


def test_prompt_investigacao_incorpora_o_oficio_e_nao_monta():
    """O coração do modo: incorporar o ofício do profissional dono da função, uma
    pergunta por vez, sem propor estrutura nem montar."""
    p = montar_prompt_criadora(modo="investigacao")
    assert "MODO INVESTIGAÇÃO" in p
    assert "QUAL OFÍCIO" in p
    # exemplos de ofícios distintos (generaliza além de blog)
    assert "Marketing de conteúdo" in p
    assert "Tesouraria" in p
    # disciplina de conversa
    assert "Uma pergunta por mensagem" in p
    # pede passagem em vez de montar
    assert "solicitar_modo_projeto" in p
    assert "Não propõe estrutura de time" in p
    # NÃO injeta catálogo nem formato de gatilho em investigação (seria ruído)
    assert "publicar_wordpress" not in p
    assert "frequencia" not in p


def test_prompt_projeto_descreve_sem_criar():
    p = montar_prompt_criadora(modo="projeto")
    assert "MODO PROJETO" in p
    assert "Posso montar" in p
    assert "solicitar_modo_montagem" in p
    # em projeto a IA tem o catálogo (para falar de viabilidade), mas não cria
    assert "publicar_wordpress" in p
    assert "não criando o time" in p


def test_prompt_montagem_tem_fases_de_criacao_e_formatos():
    p = montar_prompt_criadora(modo="montagem")
    assert "MODO MONTAGEM" in p
    # ferramentas de criação citadas na ordem
    assert "definir_time" in p
    assert "adicionar_agente" in p
    # regra de ouro dos markdowns (agentes agem, repassam limpo)
    assert "AGE, não pergunta" in p
    assert "REPASSE LIMPO" in p
    # portão e modelo por papel
    assert "pausa_humano" in p
    assert "claude-haiku-4-5" in p
    # formatos injetados (gatilho) + catálogo
    assert "frequencia" in p
    assert "publicar_wordpress" in p


def test_prompt_injeta_rascunho_atual():
    p = montar_prompt_criadora(Rascunho(time_nome="X"), modo="montagem")
    assert "time_nome" in p and '"X"' in p


def test_modo_desconhecido_cai_em_investigacao():
    # robustez: um modo inesperado não quebra; cai no prompt mais seguro
    assert montar_prompt_criadora(modo="zzz") == montar_prompt_criadora(
        modo="investigacao"
    )
