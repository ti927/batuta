"""O encaixe de instrumentos do Batuta.

Um instrumento é uma capacidade que um agente aciona (PRODUTO.md §13). Todos os
tipos se encaixam do mesmo jeito: cada um declara como se descreve para a IA e
como executa. A orquestração (Fase 4) lê o cinto do agente e oferece cada
instrumento à IA por este mesmo encaixe — sem conhecer o tipo concreto.

Importar este pacote registra os tipos disponíveis.
"""

from instrumentos.base import (
    TipoInstrumento,
    obter_tipo,
    tipos_disponiveis,
    validar_configuracao,
)

# Registra os tipos concretos ao importar o pacote.
from instrumentos import rest  # noqa: E402, F401  (efeito colateral: registro)

__all__ = [
    "TipoInstrumento",
    "obter_tipo",
    "tipos_disponiveis",
    "validar_configuracao",
]
