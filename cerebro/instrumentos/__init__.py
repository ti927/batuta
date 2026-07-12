"""O encaixe de instrumentos do Batuta.

Um instrumento é uma capacidade que um agente aciona (PRODUTO.md §13). Todos os
tipos se encaixam do mesmo jeito: cada um declara como se descreve para a IA e
como executa. A orquestração (Fase 4) lê o cinto do agente e oferece cada
instrumento à IA por este mesmo encaixe — sem conhecer o tipo concreto.

Importar este pacote registra os tipos disponíveis.
"""

from instrumentos.base import (
    TipoInstrumento,
    acao_irreversivel,
    campos_secretos,
    obter_tipo,
    preparar_config,
    tipos_disponiveis,
    validar_configuracao,
)

# Registra os tipos concretos ao importar o pacote.
from instrumentos import busca_exa  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import busca_web  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import descrever_imagem  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import enviar_telegram  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import gerar_imagem  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import gerar_pdf  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import instagram_insights  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import instagram_ler_comentarios  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import instagram_ler_post  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import instagram_responder_comentario  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import ler_site  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import ler_site_firecrawl  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import mcp  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import montar_imagem  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import publicar_instagram  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import rest  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import sql  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import webhook_saida  # noqa: E402, F401  (efeito colateral: registro)
from instrumentos import wordpress  # noqa: E402, F401  (efeito colateral: registro)

__all__ = [
    "TipoInstrumento",
    "acao_irreversivel",
    "campos_secretos",
    "obter_tipo",
    "preparar_config",
    "tipos_disponiveis",
    "validar_configuracao",
]
