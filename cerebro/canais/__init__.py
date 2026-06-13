"""O encaixe de canais de mensageria do Batuta.

Um canal é uma capacidade de mensageria plugável que pende da organização
(PRODUTO.md §10). Todos os tipos se encaixam do mesmo jeito: cada um declara
como manda mensagem (`enviar`) e como traduz o que recebe (`normalizar`) para um
formato interno único (`MensagemNormalizada`). A borda da orquestração — não o
motor — usa esse encaixe sem conhecer o tipo concreto.

Importar este pacote registra os tipos disponíveis.
"""

from canais.base import (
    Anexo,
    MensagemNormalizada,
    TipoCanal,
    campos_secretos,
    obter_tipo,
    preparar_config,
    registrar,
    tipos_disponiveis,
)

# Os tipos concretos (Telegram etc.) se registram aqui ao serem importados — a
# implementação concreta entra nos próximos passos.

__all__ = [
    "Anexo",
    "MensagemNormalizada",
    "TipoCanal",
    "campos_secretos",
    "obter_tipo",
    "preparar_config",
    "registrar",
    "tipos_disponiveis",
]
