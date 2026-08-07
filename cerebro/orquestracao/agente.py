"""Execução de um agente sozinho (Tarefa 4.2).

Um agente recebe uma entrada, raciocina com sua documentação (os quatro
markdowns) e seus instrumentos (o cinto), e produz uma saída. O laço de
tool-calling é o `create_react_agent` do LangGraph; cada instrumento do cinto
vira uma ferramenta da IA pelo encaixe (instrumentos/base.py).
"""

import json
import re
import unicodedata
import uuid
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain.agents import create_agent
from pydantic import BaseModel, Field, create_model

import instrumentos as encaixe
import memoria_agente
from instrumentos.base import (
    FalhaInstrumento,
    acao_irreversivel,
    acionar_com_retentativa,
)
from modelos import Agente, Instrumento
from orquestracao import atividade
from orquestracao.llm import MODELO_PADRAO, construir_modelo, texto_da_resposta
from orquestracao.modelos_ia import PROVEDOR_ANTHROPIC, provedor_do_modelo_seguro
from sessao import CriadorDeSessao


def montar_instrucoes(agente: Agente) -> str:
    """Compõe o prompt de sistema a partir dos quatro markdowns do agente."""
    secoes = [
        ("Quem você é", agente.agent_md),
        ("Suas habilidades", agente.skill_md),
        ("Seus instrumentos", agente.tools_md),
        ("Sua personalidade e tom", agente.soul_md),
    ]
    partes = [
        f"## {titulo}\n{conteudo.strip()}"
        for titulo, conteudo in secoes
        if conteudo and conteudo.strip()
    ]
    if not partes:
        return "Você é um agente do Batuta. Cumpra a tarefa recebida com clareza."
    return "\n\n".join(partes)


def _nome_de_ferramenta(inst: Instrumento, tipo_fallback: str) -> str:
    """Nome válido para a IA (^[a-zA-Z0-9_-]{1,64}$), único por instrumento."""
    base = unicodedata.normalize("NFKD", inst.nome).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-zA-Z0-9_-]+", "_", base).strip("_")[:40]
    return f"{base or tipo_fallback}_{inst.id.hex[:8]}"


def _ferramenta_unica(
    inst, tipo, config, falhas: list[str], mensagens_enviadas: dict[str, list[str]],
    erros: list[dict],
) -> StructuredTool:
    """A ferramenta única derivada do `executar` de um instrumento (o caso comum).

    Em falha definitiva (esgotadas as retentativas, ou falha não retentável), o
    erro SEMPRE volta para a IA. A diferença é o que acontece com a EXECUÇÃO:

    - Instrumento de AÇÃO IRREVERSÍVEL (publicar/enviar/gravar): a falha é
      registrada em `falhas` e a orquestração, ao fim do laço, transforma isso
      numa falha VISÍVEL — nunca fingir que a ação aconteceu (PRODUTO §16).
    - Instrumento de LEITURA (busca, consulta, gerar artefato): a falha NÃO
      derruba o fluxo — o agente recebe o erro e decide pela sua documentação
      (tentar de novo, ajustar a entrada, ou seguir sem o dado). Assim uma busca
      instável não joga fora todo o trabalho dos passos anteriores.

    Quando o instrumento APRESENTA uma mensagem a um humano (`tipo.campo_mensagem`,
    ex.: um canal de mensageria), o texto enviado COM SUCESSO é acumulado em
    `mensagens_enviadas` (por id de instrumento). É o que o portão de aprovação usa
    para carregar adiante exatamente o que a pessoa viu (e não o status que o agente
    narra depois)."""

    # Derivado por instância (REST pelo método, SQL pelo somente_leitura). É o
    # mesmo critério da parede de ativação — uma fonte de verdade só.
    irreversivel = acao_irreversivel(tipo.tipo, inst.configuracao or {})
    campo_msg = getattr(tipo, "campo_mensagem", None)

    def executar(**kwargs) -> str:
        args = tipo.Args.model_validate(kwargs)
        # Feedback ao vivo: publica "o que está acontecendo agora" ANTES da chamada —
        # é o que evita a tela parecer travada enquanto um instrumento lento roda.
        atividade.registrar(atividade.mensagem_para(tipo.tipo, inst.nome))
        try:
            resultado = acionar_com_retentativa(tipo, config, args)
        except FalhaInstrumento as e:
            msg = f"O instrumento '{inst.nome}' falhou: {e}"
            # Registra o erro CRU (não só o que a IA vai narrar depois): é o que
            # permite ao diagnóstico dizer EXATAMENTE o que aconteceu, mesmo quando a
            # falha é de leitura/geração e o fluxo segue (execução "concluída").
            erros.append({
                "ferramenta": inst.nome,
                "tipo": tipo.tipo,
                "instrumento_id": str(inst.id),
                "erro": str(e),
                "retentavel": e.retentavel,
                "irreversivel": irreversivel,
            })
            if irreversivel:
                falhas.append(msg)
                return json.dumps({"ok": False, "erro": msg}, ensure_ascii=False)
            return json.dumps(
                {
                    "ok": False,
                    "erro": msg,
                    "dica": "Falha numa ação de leitura — tente de novo com outra "
                    "entrada ou siga sem este resultado; não invente o dado.",
                },
                ensure_ascii=False,
            )
        # Envio bem-sucedido por um canal: registra o texto apresentado ao humano.
        if campo_msg:
            texto = getattr(args, campo_msg, None)
            if texto:
                mensagens_enviadas.setdefault(str(inst.id), []).append(str(texto))
        return json.dumps(resultado, ensure_ascii=False, default=str)

    return StructuredTool.from_function(
        func=executar,
        name=_nome_de_ferramenta(inst, tipo.tipo),
        description=f"{tipo.descricao} (instrumento configurado: {inst.nome})",
        args_schema=tipo.Args,
    )


def _ferramentas_de_instrumento(
    inst: Instrumento, falhas: list[str], mensagens_enviadas: dict[str, list[str]],
    erros: list[dict],
) -> list:
    """As ferramentas que um instrumento do cinto oferece à IA pelo encaixe.

    O caso comum é UMA ferramenta (derivada do `executar`). Um instrumento
    MULTI-FERRAMENTA (MCP) devolve VÁRIAS, via `expandir_ferramentas`. Tipo
    desconhecido → nenhuma (instrumento ignorado)."""
    tipo = encaixe.obter_tipo(inst.tipo)
    if tipo is None:
        return []
    # Fase 7-B: mescla os segredos decifrados (anexados ao carregar o cinto) na
    # config; ficam só em memória, nunca no banco em claro.
    config = tipo.Config.model_validate(
        {**(inst.configuracao or {}), **getattr(inst, "segredos_decifrados", {})}
    )
    expandidas = tipo.expandir_ferramentas(config)
    if expandidas is not None:
        return expandidas
    return [_ferramenta_unica(inst, tipo, config, falhas, mensagens_enviadas, erros)]


def _opcoes_das_saidas(saidas: list[dict]) -> str:
    """As saídas do nó como uma lista legível 'rótulo: quando' (para a IA escolher)."""
    return "\n".join(
        f'- "{s["rotulo"]}": {s.get("quando") or "(sem descrição)"}'
        for s in saidas
        if s.get("rotulo")
    )


def _ferramenta_seguir_para(saidas: list[dict], escolha: dict) -> StructuredTool:
    """Ferramenta de DECISÃO DE FLUXO: o PRÓPRIO agente declara por qual saída do nó
    o fluxo segue — em vez de uma LLM roteadora separada adivinhar pela prosa. O
    `rotulo` é um enum dos rótulos das saídas (a IA não inventa caminho); a escolha
    é registrada no dict `escolha` do closure (mesmo padrão de `mensagens_enviadas`)."""
    rotulos = [s["rotulo"] for s in saidas if s.get("rotulo")]
    Args = create_model(
        "SeguirParaArgs",
        rotulo=(
            Literal[tuple(rotulos)],  # type: ignore[valid-type]
            Field(description="O rótulo exato do caminho a seguir."),
        ),
    )
    descricao = (
        "Decide por qual caminho o fluxo segue depois deste passo. Chame UMA vez, ao "
        f"concluir, com o rótulo do caminho escolhido.\nCaminhos:\n{_opcoes_das_saidas(saidas)}"
    )

    def seguir(**kwargs) -> str:
        args = Args.model_validate(kwargs)
        escolha["rotulo"] = args.rotulo
        return json.dumps({"ok": True, "rotulo": args.rotulo}, ensure_ascii=False)

    return StructuredTool.from_function(
        func=seguir, name="seguir_para", description=descricao, args_schema=Args
    )


def _instrucao_de_fluxo(
    saidas: list[dict], gate: bool, texto_portao: str | None = None
) -> str:
    """Apêndice do nó: quais saídas existem e como declarar a escolha. É a topologia
    que antes ficava ESCONDIDA do agente.

    O TRILHO MECÂNICO — declarar um caminho com `seguir_para` — é SEMPRE anexado; sem
    ele o fluxo não anda. Num portão (`gate`), a parte COMPORTAMENTAL (como conduzir a
    aprovação) vem do `texto_portao` editável (as instruções de portão do nó, o
    "portao.md") quando houver; senão, do texto padrão de hoje (fallback → portões
    existentes não mudam). Assim o criador controla o que o agente FAZ/diz na abertura e
    no fechamento do portão, sem poder remover o trilho que faz o grafo andar."""
    opcoes = _opcoes_das_saidas(saidas)
    if gate:
        if (texto_portao or "").strip():
            return (
                "## Caminhos do fluxo (este passo aguarda uma pessoa)\n"
                f"{texto_portao.strip()}\n\n"
                "IMPORTANTE (mecânica do fluxo): para o fluxo AVANÇAR você PRECISA "
                "declarar o caminho chamando a ferramenta `seguir_para` com um dos "
                "rótulos abaixo. Enquanto não chamar `seguir_para`, o fluxo continua "
                "aguardando a pessoa (use isso quando ainda precisar falar com ela).\n"
                f"Caminhos:\n{opcoes}"
            )
        return (
            "## Caminhos do fluxo (este passo aguarda uma pessoa)\n"
            "Quando você tiver a decisão da pessoa, chame a ferramenta `seguir_para` "
            "com o rótulo do caminho escolhido E escreva também uma frase curta para "
            "ela, confirmando o que vai acontecer — essa frase será enviada a ela. Se "
            "ainda precisar de algo dela (perguntar, esclarecer), apenas responda "
            "normalmente, SEM chamar `seguir_para` — o fluxo segue aguardando a "
            "resposta dela.\n"
            f"Caminhos:\n{opcoes}"
        )
    return (
        "## Caminhos do fluxo\n"
        "Ao terminar este passo, escolha por qual caminho o fluxo segue: chame a "
        "ferramenta `seguir_para` com o rótulo do caminho.\n"
        f"Caminhos:\n{opcoes}"
    )


class _RegistrarMemoriaArgs(BaseModel):
    assunto: str = Field(
        description="Título curto e ESTÁVEL da ficha (ex.: 'Cliente: Padaria do João'). "
        "Uma ficha por assunto — reuse o mesmo título para ATUALIZAR."
    )
    conteudo: str = Field(
        description="O que lembrar sobre esse assunto — um resumo enxuto, não um documento."
    )


class _PesquisarMemoriaArgs(BaseModel):
    assunto: str | None = Field(
        default=None,
        description="Assunto/termo a buscar. Vazio devolve todas as fichas.",
    )


def _ferramentas_de_memoria(
    agente_id: uuid.UUID, escritas: dict
) -> list[StructuredTool]:
    """As 2 ferramentas de MEMÓRIA do agente (injetadas quando `memoria_ativa`), no
    mesmo molde do `seguir_para`. Cada uma abre a PRÓPRIA sessão e COMITA — o
    aprendizado persiste mesmo se o run falhar depois. NUNCA levantam: memória é
    auxiliar; a falha volta como resultado suave, não derruba a execução. `escritas` é
    um contador no closure (anti-loop: teto de gravações por execução)."""

    def registrar(**kwargs) -> str:
        args = _RegistrarMemoriaArgs.model_validate(kwargs)
        if escritas["n"] >= memoria_agente.MAX_ESCRITAS_POR_RUN:
            return json.dumps(
                {"ok": False, "erro": "limite de anotações desta execução atingido."},
                ensure_ascii=False,
            )
        atividade.registrar("Anotando na memória…")
        s = CriadorDeSessao()
        try:
            m, status = memoria_agente.registrar(
                s, agente_id, args.assunto, args.conteudo
            )
            s.commit()
        except Exception:
            s.rollback()
            return json.dumps(
                {"ok": False, "erro": "não foi possível gravar a memória agora."},
                ensure_ascii=False,
            )
        finally:
            s.close()
        if m is None:
            motivo = (
                "memória cheia — edite ou remova fichas na tela do agente."
                if status == "recusada:teto"
                else "assunto e conteúdo são obrigatórios."
            )
            return json.dumps({"ok": False, "erro": motivo}, ensure_ascii=False)
        escritas["n"] += 1
        return json.dumps(
            {"ok": True, "status": status, "assunto": m.assunto}, ensure_ascii=False
        )

    def pesquisar(**kwargs) -> str:
        args = _PesquisarMemoriaArgs.model_validate(kwargs)
        atividade.registrar("Consultando a memória…")
        s = CriadorDeSessao()
        try:
            fichas = memoria_agente.pesquisar(s, agente_id, args.assunto)
        except Exception:
            # Falha de LEITURA não derruba nada: segue sem memória (lista vazia).
            fichas = []
        finally:
            s.close()
        return json.dumps({"ok": True, "memorias": fichas}, ensure_ascii=False)

    return [
        StructuredTool.from_function(
            func=registrar,
            name="registrar_memoria",
            description=(
                "Guarda ou ATUALIZA uma ficha da sua memória (uma por assunto). Use para "
                "lembrar do cliente, de decisões e de fatos entre execuções — não repita o "
                "que já sabe."
            ),
            args_schema=_RegistrarMemoriaArgs,
        ),
        StructuredTool.from_function(
            func=pesquisar,
            name="pesquisar_memoria",
            description=(
                "Lembra o que você já aprendeu. Sem 'assunto' devolve tudo; com 'assunto', "
                "filtra. Se vier vazio, é a primeira vez — siga normalmente."
            ),
            args_schema=_PesquisarMemoriaArgs,
        ),
    ]


def _instrucao_de_memoria(agente: Agente) -> str:
    """Apêndice MECÂNICO (não comportamental) da memória: diz que as ferramentas existem
    e, no modo 'sempre', injeta as fichas atuais (com índice do excedente, p/ não inchar
    o prompt). A POLÍTICA — o que guardar, quando buscar, criar vs editar — é do markdown
    do agente (o comportamento vem dos markdowns)."""
    texto = (
        "\n\n## Sua memória (aprendizado do próprio trabalho)\n"
        "Você tem memória entre execuções, em fichas por assunto. Use "
        "`registrar_memoria(assunto, conteudo)` para guardar/ATUALIZAR uma ficha (uma por "
        "assunto — edite, não duplique) e `pesquisar_memoria(assunto)` para lembrar. Busca "
        "vazia = primeira vez."
    )
    if getattr(agente, "memoria_recall", "sempre") != "sempre":
        return texto
    s = CriadorDeSessao()
    try:
        dados = memoria_agente.para_o_prompt(s, agente.id)
    finally:
        s.close()
    if dados["fichas"]:
        texto += "\nO que você já sabe (fichas):\n" + json.dumps(
            dados["fichas"], ensure_ascii=False
        )
    if dados["indice_extra"]:
        texto += (
            "\nOutros assuntos que você conhece (use pesquisar_memoria para o conteúdo): "
            + ", ".join(dados["indice_extra"])
        )
    if not dados["fichas"] and not dados["indice_extra"]:
        texto += "\n(Você ainda não tem fichas — comece a aprender.)"
    return texto


def _prompt_de_sistema(instrucoes: str, modelo_id: str) -> "SystemMessage | str":
    """O prompt de sistema no formato certo para o PROVEDOR do modelo.

    Na **Anthropic**, um `SystemMessage` com PONTO DE CACHE (`cache_control: ephemeral`):
    o `create_react_agent` reenvia [ferramentas + prompt de sistema] a CADA passo do laço
    de tool-calling (e a cada turno de uma conversa), então marcar o cache faz esses
    reenvios repetidos custarem ~10% — economia grande em turnos com muitas chamadas de
    ferramenta (medido: a entrada de um turno chega a 13–18× o conteúdo real). Em
    **OpenAI/Google** (ou modelo desconhecido), texto puro — `cache_control` é específico
    da Anthropic e quebraria/seria ignorado nos outros. Mesmo padrão da IA criadora
    (`criacao/prompt.prompt_criadora`). Ponto único que evita o cache vazar para um
    provedor que não o entende."""
    if provedor_do_modelo_seguro(modelo_id) == PROVEDOR_ANTHROPIC:
        return SystemMessage(
            content=[
                {"type": "text", "text": instrucoes, "cache_control": {"type": "ephemeral"}}
            ]
        )
    return instrucoes


def executar_agente(
    agente: Agente,
    cinto: list[Instrumento],
    entrada: str,
    *,
    saidas: list[dict] | None = None,
    gate: bool = False,
    texto_portao: str | None = None,
) -> dict:
    """Roda um agente sozinho sobre uma entrada. Devolve a saída em texto e a
    lista de instrumentos que ele acionou (para inspeção).

    Quando o nó tem 2+ saídas, o agente recebe a ferramenta `seguir_para` e o
    apêndice de caminhos: é ELE quem declara o ramo (devolvido em `ramo_escolhido`),
    em vez de uma LLM roteadora adivinhar pela prosa. Nó de 1 saída segue direto.

    Se um instrumento de AÇÃO IRREVERSÍVEL falhar de vez, levanta
    `FalhaInstrumento` ao fim do laço — a execução fica num estado de falha claro
    e visível (Tarefa 5.1). Falha de instrumento de LEITURA não derruba o fluxo:
    volta para o agente decidir (ver `_ferramenta_unica`)."""
    modelo = construir_modelo(agente.modelo_ia)
    falhas: list[str] = []
    # Por instrumento (id → textos): o que o agente APRESENTOU a um humano por canal
    # neste turno. O portão de aprovação usa isto para carregar adiante o que a
    # pessoa viu, em vez do status que o agente narra depois.
    mensagens_enviadas: dict[str, list[str]] = {}
    # Erros CRUS dos instrumentos neste turno (para o diagnóstico, não só a narração
    # da IA) — inclui falhas de leitura/geração que não derrubam a execução.
    erros_instrumentos: list[dict] = []
    escolha: dict[str, str] = {}  # o ramo que o agente declarar via `seguir_para`
    ferramentas = [
        f
        for i in cinto
        for f in _ferramentas_de_instrumento(i, falhas, mensagens_enviadas, erros_instrumentos)
    ]
    saidas = saidas or []
    instrucoes = montar_instrucoes(agente)
    # Memória do agente (quando ligada): 2 ferramentas injetadas + (modo "sempre") as
    # fichas no prompt. `agente.id` já está aqui; núcleo de cadeia intocado.
    if getattr(agente, "memoria_ativa", False):
        escritas = {"n": 0}
        ferramentas += _ferramentas_de_memoria(agente.id, escritas)
        instrucoes += _instrucao_de_memoria(agente)
    if len(saidas) >= 2:
        ferramentas.append(_ferramenta_seguir_para(saidas, escolha))
        instrucoes += "\n\n" + _instrucao_de_fluxo(saidas, gate, texto_portao)
    # Cache de prompt (Anthropic): o prompt e as ferramentas são reenviados a cada passo
    # do laço/turno; marcar o cache corta o custo desses reenvios (economia de tokens).
    prompt_sistema = _prompt_de_sistema(instrucoes, agente.modelo_ia or MODELO_PADRAO)
    # `create_agent` (LangChain 1.x) é a sucessora oficial do `create_react_agent`
    # (deprecado na V1.0). Aceita `system_prompt: str | SystemMessage` e usa o
    # `SystemMessage` COMO ESTÁ — então o `cache_control` (cache de prompt Anthropic)
    # sobrevive intacto. Fatia 4.3/P1: só a troca do construtor; laço/entrada/uso iguais.
    app = create_agent(modelo, ferramentas, system_prompt=prompt_sistema)
    # Feedback ao vivo: o turno de LLM pode demorar; avisa que o agente está pensando.
    atividade.registrar(f"{agente.nome}: pensando…")
    resultado = app.invoke({"messages": [{"role": "user", "content": entrada}]})

    # Não confiamos na narração do agente: se uma ação IRREVERSÍVEL falhou,
    # a execução falha de forma determinística e visível (nunca em silêncio).
    if falhas:
        raise FalhaInstrumento(falhas[0])

    mensagens = resultado["messages"]
    acionados = [
        chamada.get("name")
        for m in mensagens
        for chamada in (getattr(m, "tool_calls", None) or [])
    ]

    # Uso (Tarefa 5.4): soma os tokens de cada turno do modelo. Num laço de
    # tool-calling há vários AIMessage; cada turno reenvia o contexto, então a
    # soma reflete o que foi de fato consumido.
    tokens_entrada = tokens_saida = 0
    cache_read = cache_write = 0
    for m in mensagens:
        if isinstance(m, AIMessage):
            u = m.usage_metadata or {}
            tokens_entrada += u.get("input_tokens", 0)
            tokens_saida += u.get("output_tokens", 0)
            # Cache de prompt (Anthropic): `input_tokens` INCLUI o que veio do cache a
            # preço cheio; guardamos leitura/criação para a medição cobrar ~10% (releitura)
            # e ~1,25× (criação), como no `criacao/loop.py`. Sem cache, ambos ficam 0.
            det = u.get("input_token_details") or {}
            cache_read += det.get("cache_read", 0) or 0
            cache_write += det.get("cache_creation", 0) or 0
    modelo_usado = agente.modelo_ia or MODELO_PADRAO

    return {
        "saida": texto_da_resposta(mensagens[-1]),
        "instrumentos_acionados": acionados,
        "mensagens_enviadas": mensagens_enviadas,
        "erros_instrumentos": erros_instrumentos,
        "ramo_escolhido": escolha.get("rotulo"),
        "uso": [
            {
                "modelo": modelo_usado,
                "tokens_entrada": tokens_entrada,
                "tokens_saida": tokens_saida,
                "tokens_cache_read": cache_read,
                "tokens_cache_write": cache_write,
            }
        ],
    }
