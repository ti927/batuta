"""Peças comuns às duas duplicações: de TIME (`duplicacao_time.py`) e de AUTOMAÇÃO
(`rotas/automacoes.py::duplicar`). Fonte de verdade ÚNICA para não divergirem.

Uma automação copiada carrega o `configuracao_gatilho` inteiro. Para gatilhos de
ENTRADA — que dependem de uma conexão externa a uma fonte — a cópia precisa nascer
"a conectar", como os canais (Telegram) nascem sem token: senão dois fluxos brigam
pela MESMA fonte e o comentário dispara em dobro. Hoje isso vale para o
`comentario_instagram`: a cópia perde a CONTA (`credencial_id`) mas mantém os
filtros; o humano re-escolhe a conta de propósito (até lá, o receptor nunca casa).
"""

import copy

# Gatilhos de entrada cuja cópia nasce "a conectar": estes campos somem na cópia.
_CAMPOS_A_ZERAR = {"comentario_instagram": ("credencial_id",)}


def sanear_gatilho_duplicado(tipo_gatilho: str | None, config: dict | None) -> dict:
    """Copia o `configuracao_gatilho` para a automação DUPLICADA, zerando a conexão
    externa (ex.: `credencial_id` do comentário) para a cópia não disparar na conta
    do original. Filtros (midias/palavra_chave/teto) são preservados."""
    saida = copy.deepcopy(config or {})
    for campo in _CAMPOS_A_ZERAR.get(tipo_gatilho or "", ()):
        saida.pop(campo, None)
    return saida
