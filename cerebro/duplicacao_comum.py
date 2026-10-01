"""Peças comuns às duas duplicações: de TIME (`duplicacao_time.py`) e de AUTOMAÇÃO
(`rotas/automacoes.py::duplicar`). Fonte de verdade ÚNICA para não divergirem.

Uma automação copiada carrega o `configuracao_gatilho` inteiro. Para gatilhos de
ENTRADA — que dependem de uma conexão externa a uma fonte — a cópia precisa nascer
"a conectar", como os canais (Telegram) nascem sem token: senão dois fluxos brigam
pela MESMA fonte e o aviso dispara em dobro. Valia para o gatilho de comentário
do Instagram (saiu em 2026-10-01); hoje nenhum gatilho precisa — o mecanismo fica
para o próximo que depender de uma conta conectada.
"""

import copy

# Gatilhos de entrada cuja cópia nasce "a conectar": estes campos somem na cópia.
_CAMPOS_A_ZERAR: dict[str, tuple[str, ...]] = {}


def sanear_gatilho_duplicado(tipo_gatilho: str | None, config: dict | None) -> dict:
    """Copia o `configuracao_gatilho` para a automação DUPLICADA, zerando a conexão
    externa para a cópia não disparar na conta do original. Filtros são preservados."""
    saida = copy.deepcopy(config or {})
    for campo in _CAMPOS_A_ZERAR.get(tipo_gatilho or "", ()):
        saida.pop(campo, None)
    return saida
