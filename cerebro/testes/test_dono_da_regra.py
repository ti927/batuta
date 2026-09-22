"""Cada regra tem UM dono — e isso é lei de código, não convenção de tela.

Até 2026-09-22 qualquer camada da cascata podia escrever qualquer chave. O resultado
era que quem vencia mudava campo a campo: `PERFIS["interno"]` fixava
`saudacao_abertura: ""` e apagava em silêncio a saudação escrita no bot, enquanto
`PERFIS["atendimento"]`, que não declara horário, deixava o canal vencer nessas
outras. Ninguém conseguia prever, e a tela mostrava as MESMAS opções em dois níveis
sem dizer qual era qual.

Estes testes são a trava. Eles não provam um comportamento novo — provam que a
partição continua íntegra no dia em que alguém acrescentar uma chave, mover um campo
de grupo ou recopiar um default num instrumento de canal. É o tipo de erro que passa
despercebido em revisão e só aparece meses depois, como "configurei e não funcionou".
"""

import pytest

import instrumentos  # noqa: F401  (efeito colateral: registra os tipos)
from instrumentos.base import obter_tipo
from instrumentos.pedir_aprovacao import CANAIS_TIPOS
from mensageria.config import (
    CAMPOS,
    CHAVES,
    CHAVES_DA_AUTOMACAO,
    CHAVES_DO_AGENTE,
    CHAVES_DO_CANAL,
    CHAVES_DO_FLUXO,
    GLOBAL,
    PRESETS,
)


def _chaves_de_campos() -> set[str]:
    return {c["chave"] for g in CAMPOS for c in g["campos"]}


def test_a_particao_cobre_tudo_e_nao_se_sobrepoe():
    """Toda chave de `GLOBAL` tem exatamente um dono.

    Uma chave nova sem dono faz a suíte falhar aqui, em vez de ficar órfã — que é como
    `mensagem_limite`, `mensagem_nudge` e `mensagem_despedida` ficaram meses sendo
    enviadas a pessoas reais sem tela nenhuma para mudá-las.
    """
    assert CHAVES_DO_CANAL | CHAVES_DO_AGENTE | CHAVES_DO_FLUXO == CHAVES
    assert not (CHAVES_DO_CANAL & CHAVES_DO_AGENTE)
    assert not (CHAVES_DO_CANAL & CHAVES_DO_FLUXO)
    assert not (CHAVES_DO_AGENTE & CHAVES_DO_FLUXO)
    assert CHAVES_DA_AUTOMACAO == CHAVES - CHAVES_DO_CANAL


def test_a_tela_do_fluxo_nao_mostra_o_que_e_do_canal():
    """`CAMPOS` é o que a tela do fluxo oferece. Nada de canal pode aparecer ali.

    Era exatamente essa a duplicação: saudação e horário no bot E no fluxo, com o
    fluxo vencendo. Se alguém devolver um desses campos ao painel do fluxo, aqui quebra.
    """
    da_tela = _chaves_de_campos()
    assert not (da_tela & CHAVES_DO_CANAL), (
        "campo de canal reapareceu na tela do fluxo: "
        f"{sorted(da_tela & CHAVES_DO_CANAL)}"
    )
    assert da_tela <= CHAVES_DA_AUTOMACAO


def test_todo_grupo_da_tela_declara_de_quem_e_a_regra():
    """Sem o `nivel`, a tela volta a mostrar dois níveis sem dizer qual é qual — que é
    a queixa que originou esta arrumação."""
    for grupo in CAMPOS:
        assert grupo.get("nivel") in ("fluxo", "agente"), grupo["grupo"]
        nivel = grupo["nivel"]
        for campo in grupo["campos"]:
            esperado = CHAVES_DO_AGENTE if nivel == "agente" else CHAVES_DO_FLUXO
            assert campo["chave"] in esperado, (
                f"{campo['chave']} está no grupo '{grupo['grupo']}' (nível {nivel}), "
                "mas o dono dela é outro"
            )


def test_o_preset_nao_escreve_chave_de_canal():
    """Um modelo de partida não pode ter opinião sobre a voz do bot.

    É a regressão concreta: o `saudacao_abertura: ""` do preset "interno" apagava a
    saudação personalizada do canal. Agora o preset só SEMEIA ajustes — mas semear uma
    chave de canal seria o mesmo estrago, com um passo a mais.
    """
    for pid, preset in PRESETS.items():
        intrusas = set(preset) & CHAVES_DO_CANAL
        assert not intrusas, f"preset '{pid}' escreve chave do canal: {sorted(intrusas)}"


def test_o_preset_so_semeia_o_que_a_automacao_pode_guardar():
    """O que um modelo carimba tem de caber em `configuracao.ajustes` — senão ele
    escreveria no nascimento algo que a leitura descarta, e a automação nasceria
    mentindo sobre o que faz."""
    for pid, preset in PRESETS.items():
        fora = set(preset) - CHAVES_DA_AUTOMACAO
        assert not fora, f"preset '{pid}' semeia chave que ninguém lê: {sorted(fora)}"


@pytest.mark.parametrize("tipo_nome", CANAIS_TIPOS)
def test_o_canal_nao_deriva_do_padrao_global(tipo_nome):
    """O default declarado no instrumento de canal tem de bater com o `GLOBAL`.

    São duas cópias do mesmo texto em arquivos diferentes; sem esta trava elas derivam
    com o tempo e a pessoa vê uma coisa na tela e outra chega no Telegram. Vale para
    TODO canal — quando o WhatsApp entrar, ele já nasce cobrado aqui.
    """
    tipo = obter_tipo(tipo_nome)
    assert tipo is not None, f"canal '{tipo_nome}' não está registrado"
    campos = tipo.Config.model_fields
    comuns = set(campos) & CHAVES
    assert comuns, f"{tipo_nome} deixou de declarar qualquer chave de conversa"
    for chave in sorted(comuns):
        assert campos[chave].default == GLOBAL[chave], (
            f"{tipo_nome}.{chave} derivou do padrão global"
        )
    # E o canal não pode invadir o que não é dele: um bot não decide quantos passos
    # uma execução tem.
    intrusas = comuns - CHAVES_DO_CANAL
    assert not intrusas, f"{tipo_nome} escreve chave que não é do canal: {sorted(intrusas)}"


@pytest.mark.parametrize("tipo_nome", CANAIS_TIPOS)
def test_o_canal_e_dono_do_que_diz_ao_contato(tipo_nome):
    """As mensagens que o bot envia precisam ser editáveis onde o bot é editado."""
    campos = set(obter_tipo(tipo_nome).Config.model_fields)
    for chave in ("mensagem_limite", "mensagem_nudge", "mensagem_despedida"):
        assert chave in campos, f"{tipo_nome}: {chave} voltou a não ter tela nenhuma"
