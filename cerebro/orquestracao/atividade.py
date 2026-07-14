"""Sinal de ATIVIDADE ao vivo de uma execução ("o que está acontecendo agora").

Um instrumento lento (ex.: `montar_imagem` bloqueia até 10 min; `gerar_video_fal`
faz *poll* de minutos) prende o trabalhador SEM gravar passo nenhum — e a tela, que
só mostra passos concluídos, parece TRAVADA. Este módulo dá à borda um jeito de
publicar, a cada momento, uma frase curta do que o agente está fazendo, para a tela
exibir isso + um cronômetro correndo.

Mesmo padrão do `usar_chaves` (llm.py): um ContextVar atravessa o stack do motor sem
mudar a assinatura de nenhuma função do grafo. A fronteira (`disparo.rodar_execucao`)
fixa um ESCRITOR com `usar_atividade(...)`; o agente, lá no fundo, chama `registrar(...)`
antes de cada passo/instrumento. O escritor grava numa transação PRÓPRIA e minúscula
(como um heartbeat), sem tocar a transação da cadeia. Fora de um bloco `usar_atividade`
(testes, chamadas soltas), `registrar` é NO-OP. É best-effort: um erro ao publicar o
feedback NUNCA derruba a execução.
"""

import contextvars
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Callable

logger = logging.getLogger(__name__)

# O escritor fixado para a execução em curso: recebe o texto e o persiste. None fora
# de um bloco `usar_atividade` → `registrar` não faz nada.
_sink: contextvars.ContextVar[Callable[[str], None] | None] = contextvars.ContextVar(
    "atividade_sink", default=None
)


@contextmanager
def usar_atividade(escritor: Callable[[str], None] | None) -> Iterator[None]:
    """Fixa o ESCRITOR de atividade durante o bloco. Sai sempre limpando o contexto
    (try/finally), para um trabalhador reutilizado não vazar o escritor de uma
    execução para a próxima."""
    token = _sink.set(escritor)
    try:
        yield
    finally:
        _sink.reset(token)


def registrar(texto: str) -> None:
    """Publica a atividade atual, se há um escritor no contexto. Best-effort: engole
    qualquer erro (o feedback é acessório; não pode interromper a orquestração)."""
    escritor = _sink.get()
    if escritor is None:
        return
    try:
        escritor(texto)
    except Exception:  # feedback é acessório — nunca derruba a execução
        logger.debug("Falha ao publicar atividade (ignorada).", exc_info=True)


# Frase amigável por TIPO de instrumento — o usuário lê "o que está acontecendo",
# não o nome técnico. Fonte única; tipo desconhecido cai no fallback com o nome dado.
MENSAGENS_ATIVIDADE: dict[str, str] = {
    "montar_imagem": "Montando a imagem — pode levar alguns minutos…",
    "gerar_imagem": "Gerando a imagem…",
    "gerar_video": "Gerando o vídeo — pode levar minutos…",
    "gerar_video_fal": "Gerando o vídeo — pode levar minutos…",
    "gerar_pdf": "Gerando o PDF…",
    "publicar_instagram": "Publicando no Instagram…",
    "publicar_wordpress": "Publicando no WordPress…",
    "instagram_responder_comentario": "Respondendo o comentário no Instagram…",
    "instagram_ler_comentarios": "Lendo os comentários no Instagram…",
    "instagram_ler_post": "Lendo o post do Instagram…",
    "instagram_insights": "Consultando as métricas do Instagram…",
    "descrever_imagem": "Analisando a imagem…",
    "enviar_telegram": "Enviando no Telegram…",
    "busca_web": "Pesquisando na web…",
    "busca_exa": "Pesquisando na web…",
    "ler_site": "Lendo a página…",
    "ler_site_firecrawl": "Lendo a página…",
    "banco_sql": "Consultando o banco de dados…",
    "disparar_webhook": "Acionando outra automação…",
    "agendar_automacao": "Agendando o próximo disparo…",
}


def mensagem_para(tipo: str, nome: str) -> str:
    """A frase de atividade de um instrumento: a do mapa por tipo, ou um fallback
    com o nome do instrumento."""
    return MENSAGENS_ATIVIDADE.get(tipo, f"Usando {nome}…")
