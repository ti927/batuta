"""Resumo rolante da conversa da IA criadora (Frente B, Parte A).

Em vez de reenviar a conversa INTEIRA todo turno, a criadora envia `resumo` + a janela
dos últimos turnos (`mensagens[resumo_ate:]`). Este módulo MANTÉM o resumo: quando a
janela estoura, dobra os turnos que saíram dela num resumo incremental, feito por um
modelo barato (Haiku).

Roda em SEGUNDO PLANO, DEPOIS que a resposta do turno já foi entregue (`fila_turnos`),
best-effort: se falhar, a conversa segue — só não encolheu desta vez (nada se perde: o
histórico inteiro continua em `conversa.mensagens`; o iceberg/busca é a Parte C).
"""

import logging

from orquestracao.llm import construir_modelo, texto_da_resposta, usar_chaves

logger = logging.getLogger("batuta.criacao.resumo")

# Modelo do resumidor: barato e suficiente para condensar histórico.
MODELO_RESUMIDOR = "claude-haiku-4-5"
# Quantas MENSAGENS recentes ficam SEMPRE na íntegra (a janela). Par, pois cada turno =
# uma mensagem do consultor + uma da IA → ~8 turnos.
JANELA_MSGS = 16

_INSTRUCAO = (
    "Você mantém um RESUMO de trabalho de uma conversa entre um consultor e uma IA que "
    "constrói um time de agentes de IA. Atualize o resumo abaixo incorporando os NOVOS "
    "TRECHOS (partes mais antigas da conversa, que vão sair da janela recente). Capture o "
    "que IMPORTA lembrar: o que o time é e faz, decisões tomadas, preferências do "
    "consultor e pontas em aberto. Seja fiel e conciso; NÃO invente. Escreva em português, "
    "em tópicos curtos. Devolva APENAS o resumo atualizado, sem preâmbulo."
)


def _texto_dos_turnos(mensagens: list) -> str:
    """Serializa turnos (dicts do histórico) em 'Papel: conteúdo' — só o que interessa ao
    resumo (ignora `lc`/chips/uso)."""
    linhas = []
    for m in mensagens:
        papel = "Consultor" if m.get("papel") == "usuario" else "IA"
        conteudo = (m.get("conteudo") or "").strip()
        if conteudo:
            linhas.append(f"{papel}: {conteudo}")
    return "\n".join(linhas)


def _resumir(resumo_atual: str | None, saindo: list, modelo) -> str:
    entrada = (
        f"{_INSTRUCAO}\n\n# Resumo atual\n{resumo_atual or '(ainda não há resumo)'}\n\n"
        f"# Novos trechos a incorporar (mais antigos primeiro)\n{_texto_dos_turnos(saindo)}"
    )
    return texto_da_resposta(modelo.invoke(entrada)).strip()


def manter_resumo(conversa, *, chaves: dict | None = None) -> bool:
    """Se a janela estourou, dobra os turnos que saíram dela no `resumo` e avança
    `resumo_ate`. Muta a conversa (SEM commit — quem chama controla a transação). Devolve
    se resumiu. NUNCA levanta: é auxiliar; a falha volta como False e a conversa segue
    exatamente como está (nada se perde — o histórico completo continua em `mensagens`)."""
    try:
        msgs = conversa.mensagens or []
        inicio = conversa.resumo_ate or 0
        # Corte na fronteira de PAR (turno = consultor+IA), para não partir um turno.
        corte = len(msgs) - JANELA_MSGS
        corte -= corte % 2
        if corte <= inicio:
            return False  # a janela ainda não estourou — nada a dobrar
        saindo = msgs[inicio:corte]
        with usar_chaves(chaves):
            modelo = construir_modelo(MODELO_RESUMIDOR)
            novo = _resumir(conversa.resumo, saindo, modelo)
        if not novo:
            return False
        conversa.resumo = novo
        conversa.resumo_ate = corte
        return True
    except Exception:
        logger.exception(
            "Manutenção do resumo falhou (conversa %s) — ignorado",
            getattr(conversa, "id", "?"),
        )
        return False
