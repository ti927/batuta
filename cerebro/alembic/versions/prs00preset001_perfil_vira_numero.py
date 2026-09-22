"""automacoes.configuracao: o "Tipo de fluxo" deixa de ser ETIQUETA e vira NUMERO

O que estava errado
-------------------
`automacao.configuracao` guardava `{"perfil": "interno"}` -- uma etiqueta. Os numeros
que essa etiqueta significava moravam no CODIGO (`mensageria/config.py::PERFIS`), e
eram aplicados a cada leitura, para sempre, como uma camada a mais da cascata.

Tres consequencias, todas causa direta da queixa "ate hoje nao entendi pra que serve o
botao FLUXO":

1. O valor efetivo nunca estava no dado do fluxo. Para saber o que uma automacao fazia
   era preciso perguntar a um endpoint. O botao precisou existir justamente para mostrar
   numeros que nao estavam em lugar nenhum -- e por isso ele nao se explicava sozinho.
2. Trocar o tipo mudava seis numeros de uma vez, em silencio, inclusive de fluxo em
   execucao.
3. Era uma camada a mais para disputar -- a origem da treta de "quem vence muda campo a
   campo" que a particao por dono (2026-09-22) acabou de curar.

O que esta migracao faz
-----------------------
Materializa os numeros do preset dentro de `configuracao.ajustes` e apaga a etiqueta.
O ajuste EXPLICITO continua vencendo (ele e aplicado por ultimo), entao por construcao
nada muda de comportamento: escrevemos exatamente os valores que o codigo ja aplicava.

Depois disto, `PERFIS` deixa de ser camada e vira `PRESETS`: um modelo de partida que
carimba valores no nascimento e sai de cena. A automacao passa a carregar os proprios
numeros, visiveis e editaveis -- que e o ponto inteiro.

As automacoes com `perfil` nulo (as legadas, anteriores ao preset padrao) nao sao
tocadas: elas ja caiam no GLOBAL e continuam caindo.

Verificacao exigida antes de considerar isto pronto: comparar `config_da_automacao` de
cada automacao real ANTES e DEPOIS. O diff tem de ser vazio.

Reversivel: o downgrade apaga dos ajustes as chaves cujo valor bate com o preset e
restaura a etiqueta.

Revision ID: prs00preset001
Revises: rte00ritmo0001
Create Date: 2026-09-22
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "prs00preset001"
down_revision = "rte00ritmo0001"
branch_labels = None
depends_on = None

# Copia CONGELADA dos presets no momento desta migracao. Nao importamos de
# `mensageria.config` de proposito: uma migracao tem de produzir o mesmo resultado
# daqui a um ano, mesmo que o codigo mude. Importar tornaria o passado dependente do
# presente -- e uma migracao que muda de efeito com o tempo e irreproduzivel.
PRESETS = {
    "interno": {
        "timeout_min": 30,
        "nudge_timeout_min": 15,
        "max_turnos": 20,
        "teto_usd": 0.5,
        "portao_forma": "conversa",
        "portao_acao_abandono": "estacionar",
    },
    "atendimento": {
        "timeout_min": 60,
        "nudge_timeout_min": 30,
        "max_turnos": 40,
        "teto_usd": 1.0,
        "portao_forma": "conversa",
        "portao_acao_abandono": "estacionar",
    },
}


def upgrade() -> None:
    con = op.get_bind()
    linhas = con.execute(
        sa.text(
            "SELECT id, configuracao FROM automacoes "
            "WHERE configuracao->>'perfil' IN ('interno', 'atendimento')"
        )
    ).fetchall()
    for aid, configuracao in linhas:
        cfg = dict(configuracao or {})
        preset = PRESETS[cfg["perfil"]]
        # O ajuste explicito vence: entra DEPOIS do preset no mesmo dicionario.
        cfg["ajustes"] = {**preset, **(cfg.get("ajustes") or {})}
        cfg.pop("perfil", None)
        con.execute(
            sa.text("UPDATE automacoes SET configuracao = :c WHERE id = :i"),
            {"c": json.dumps(cfg), "i": aid},
        )


def downgrade() -> None:
    con = op.get_bind()
    linhas = con.execute(
        # `jsonb_exists(...)` e nao o operador `?`: o `?` colide com o placeholder de
        # bind do SQLAlchemy e o downgrade estouraria justo na hora em que se precisa
        # dele.
        sa.text(
            "SELECT id, configuracao FROM automacoes "
            "WHERE jsonb_exists(configuracao, 'ajustes')"
        )
    ).fetchall()
    for aid, configuracao in linhas:
        cfg = dict(configuracao or {})
        ajustes = dict(cfg.get("ajustes") or {})
        for pid, preset in PRESETS.items():
            # Reconhece o preset pelos valores que sobreviveram intactos.
            if all(ajustes.get(k) == v for k, v in preset.items()):
                for k in preset:
                    ajustes.pop(k, None)
                cfg["perfil"] = pid
                break
        cfg["ajustes"] = ajustes
        con.execute(
            sa.text("UPDATE automacoes SET configuracao = :c WHERE id = :i"),
            {"c": json.dumps(cfg), "i": aid},
        )
