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
from langchain.agents.middleware import HumanInTheLoopMiddleware, SummarizationMiddleware
from langgraph.types import Command
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

# --- Janela/resumo da memória do chat (Fatia 4.3 / P2b) --------------------------
# O checkpoint (P2a) guarda o fio inteiro do agente — sem isso ele crescia sem fim e
# cada turno reenviava tudo (custo alto). Aqui um `SummarizationMiddleware` nativo
# DOBRA os trechos antigos num resumo e mantém só a JANELA recente, de forma durável
# no próprio checkpoint. Nada se perde: o histórico completo continua na thread humana
# (`MensagemConversa`) e na timeline (`PassoExecucao`) — o checkpoint é a memória de
# TRABALHO. Mesmo espírito do resumo rolante da Frente B (`criacao/resumo.py`):
# resumidor barato (Haiku), best-effort. Valores tunáveis — calibrados na fumaça.
MODELO_RESUMIDOR_CHAT = "claude-haiku-4-5"
# Dispara o resumo quando o fio de trabalho passa disto (tokens do fio; o middleware
# também olha o total reportado pelo provedor). Acima disso, dobra o antigo.
RESUMO_GATILHO = ("tokens", 20000)
# Quanto do fim do fio fica SEMPRE cru (a janela) depois de resumir. O resto vira resumo.
RESUMO_JANELA = ("tokens", 8000)


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


def _registrar_resposta_com_falha(
    dados, *, ferramenta: str, tipo: str, instrumento_id: str,
    irreversivel: bool, erros: list[dict],
) -> None:
    """Se o RESULTADO da ferramenta veio com `ok: false` (falha devolvida como DADO
    para a IA decidir — ex.: HTTP 4xx do REST/conector), registra no rastro cru.

    Sem isto, a falha só existe na narração do agente e a execução parece limpa —
    foi assim que um lançamento que falhou no Bubble ficou invisível (2026-08-25):
    o agente disse "lancei" e nenhum rastro dizia o contrário. `origem="resposta"`
    distingue do erro por exceção (`FalhaInstrumento`), que já era registrado."""
    if not isinstance(dados, dict) or dados.get("ok") is not False:
        return
    erro = dados.get("erro")
    if not erro:
        status = dados.get("status")
        erro = f"resposta com falha (HTTP {status})" if status else "resposta com ok=false"
        corpo = dados.get("corpo")
        if corpo:
            erro += f": {str(corpo)[:200]}"
    erros.append({
        "ferramenta": ferramenta,
        "tipo": tipo,
        "instrumento_id": instrumento_id,
        "erro": str(erro)[:500],
        "retentavel": None,
        "irreversivel": irreversivel,
        "origem": "resposta",
    })


def _com_rastro_de_resposta(
    ferramenta: StructuredTool, inst, tipo_nome: str, irreversivel: bool,
    erros: list[dict],
) -> StructuredTool:
    """Embrulha uma ferramenta EXPANDIDA (conector/MCP) para que uma resposta com
    `ok: false` também entre no rastro — essas ferramentas tratam a própria falha
    e devolvem-na como dado, sem passar pelo registro de `_ferramenta_unica`."""

    def _observar(retorno):
        dados = retorno
        if isinstance(retorno, str):
            try:
                dados = json.loads(retorno)
            except ValueError:
                return retorno
        _registrar_resposta_com_falha(
            dados, ferramenta=ferramenta.name, tipo=tipo_nome,
            instrumento_id=str(inst.id), irreversivel=irreversivel, erros=erros,
        )
        return retorno

    original_func = ferramenta.func
    original_coro = ferramenta.coroutine
    func = None
    coro = None
    if original_func is not None:
        def func(*args, **kwargs):
            return _observar(original_func(*args, **kwargs))
    if original_coro is not None:
        async def coro(*args, **kwargs):
            return _observar(await original_coro(*args, **kwargs))
    return ferramenta.model_copy(update={"func": func, "coroutine": coro})


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
        # Falha devolvida como DADO (`ok: false`, ex.: HTTP 4xx que não levanta
        # exceção): entra no rastro também — a execução não pode parecer limpa.
        _registrar_resposta_com_falha(
            resultado, ferramenta=inst.nome, tipo=tipo.tipo,
            instrumento_id=str(inst.id), irreversivel=irreversivel, erros=erros,
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
        irrev = acao_irreversivel(inst.tipo, inst.configuracao or {})
        return [
            _com_rastro_de_resposta(f, inst, tipo.tipo, irrev, erros)
            for f in expandidas
        ]
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


def _middlewares_de_memoria() -> list:
    """Os middlewares do agente COM memória (só o chat). Hoje: o `SummarizationMiddleware`
    que dobra o fio antigo num resumo e mantém a janela recente (P2b). À prova de falha:
    se o resumidor não puder ser montado, devolve `[]` — a memória segue sem compactar
    (fio maior naquele turno, nada quebra; lei §12-A). A garantia HITL/portão NÃO passa por
    aqui — o portão continua na borda (P3 é quem o levará ao `interrupt()` nativo)."""
    try:
        return [
            SummarizationMiddleware(
                model=construir_modelo(MODELO_RESUMIDOR_CHAT),
                trigger=RESUMO_GATILHO,
                keep=RESUMO_JANELA,
                # NÃO trimar o trecho antes de resumir. O trim nativo usa
                # `start_on="human"`: quando o trecho antigo é dominado por um resultado
                # GIGANTE de ferramenta e não tem fala humana (o caso do Reembolsos), ele
                # devolve VAZIO e o resumo vira o placeholder inútil "too long to
                # summarize" — descartando o histórico sem resumo real. Sem trim, o trecho
                # inteiro (já limitado por gatilho−janela) vai ao resumidor Haiku → resumo
                # de verdade. É barato e raro.
                trim_tokens_to_summarize=None,
            )
        ]
    except Exception:
        return []


def _middleware_portao(irreversivel_por_ferramenta: dict[str, bool]) -> list:
    """O middleware do PORTÃO NATIVO (Fatia 4.3 / P3): o HITL SELETIVO que interrompe
    ANTES de executar uma ferramenta IRREVERSÍVEL (publicar/enviar/gravar), deixando as
    de leitura correrem livres. O `interrupt_on` é derivado da MESMA regra da parede de
    ativação (`instrumentos/base.py::acao_irreversivel`) — uma fonte de verdade só, não
    uma segunda lista. Ao pausar, o estado é salvo no checkpoint (por isso o portão
    nativo EXIGE checkpointer) e a decisão do humano volta como `Command(resume=…)`.

    Achado do protótipo P3 (custo zero): o middleware pausa numa FRONTEIRA limpa (depois
    que o agente decide chamar a ferramenta, ANTES de executá-la) — então o que já rodou
    no turno NÃO re-executa ao retomar (contém o caveat do re-run do `interrupt()` cru) e
    a garantia congelada de nunca disparar irreversível 2× fica protegida.

    À prova de falha: sem ferramenta irreversível no cinto, devolve `[]` (nada a gatear);
    se o middleware não puder ser montado, `[]` também — o turno segue sem portão nativo
    (a lei §12-A: a borda nunca quebra por causa disto)."""
    gatear = {nome: True for nome, irr in irreversivel_por_ferramenta.items() if irr}
    if not gatear:
        return []
    try:
        return [HumanInTheLoopMiddleware(interrupt_on=gatear)]
    except Exception:
        return []


def executar_agente(
    agente: Agente,
    cinto: list[Instrumento],
    entrada: str,
    *,
    saidas: list[dict] | None = None,
    gate: bool = False,
    texto_portao: str | None = None,
    checkpointer=None,
    thread_id: str | None = None,
    preambulo_sistema: str | None = None,
    portao_nativo: bool = False,
    retomar: dict | None = None,
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
    # Constrói as ferramentas do cinto e, em paralelo, o mapa nome→irreversível (a MESMA
    # regra da parede: `acao_irreversivel(tipo, config)`) — é o que o portão nativo (P3)
    # usa para saber QUAIS ferramentas exigem aprovação antes de executar. As ferramentas
    # de controle/memória (seguir_para, registrar/pesquisar_memoria), adicionadas abaixo,
    # não entram no mapa → nunca são gateadas.
    ferramentas: list = []
    irreversivel_por_ferramenta: dict[str, bool] = {}
    for i in cinto:
        fs = _ferramentas_de_instrumento(
            i, falhas, mensagens_enviadas, erros_instrumentos
        )
        irrev = acao_irreversivel(i.tipo, i.configuracao or {})
        for f in fs:
            ferramentas.append(f)
            irreversivel_por_ferramenta[f.name] = irrev
    saidas = saidas or []
    instrucoes = montar_instrucoes(agente)
    # Enquadramento do transporte (P2a): a mensageria passa o "você atende X pelo Telegram…
    # segurança…" como PREÂMBULO DE SISTEMA (persistente e cacheado). Com memória, a entrada
    # do turno é só a fala NOVA — então o enquadramento não pode ir na entrada (repetiria a
    # cada turno e empilharia no fio). Sem preâmbulo (orquestração/tarefa), nada muda.
    if preambulo_sistema:
        instrucoes += "\n\n" + preambulo_sistema
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
    # Memória entre turnos (P2a): SÓ a conversa passa `checkpointer` + `thread_id` — aí o
    # agente RETOMA o fio salvo (mensagens + resultados de ferramenta) em vez de re-derivar
    # do texto (fim da re-busca). A orquestração/tarefa e o portão NÃO passam → grafo
    # efêmero e entrada = texto completo, exatamente como antes.
    memoria = checkpointer is not None and thread_id is not None
    extra: dict = {}
    if memoria:
        extra["checkpointer"] = checkpointer
        # P2b: só o chat (com memória) ganha o resumo/janela; a orquestração/tarefa e o
        # portão seguem sem middleware — grafo efêmero, byte-idêntico à P1.
        mids = _middlewares_de_memoria()
        # Portão NATIVO (P3): HITL seletivo que interrompe ANTES de executar uma
        # ferramenta IRREVERSÍVEL. Opt-in (`portao_nativo`) — hoje ligado por NINGUÉM em
        # produção (P3a "no escuro"); precisa de checkpointer (o interrupt salva o estado).
        if portao_nativo:
            mids = mids + _middleware_portao(irreversivel_por_ferramenta)
        extra["middleware"] = mids
    app = create_agent(modelo, ferramentas, system_prompt=prompt_sistema, **extra)
    config = {"configurable": {"thread_id": thread_id}} if memoria else None
    # IDs das mensagens que já existiam no fio ANTES deste turno — para medir só o DELTA
    # por IDENTIDADE (não por posição). Com checkpointer o `invoke` devolve o estado
    # ACUMULADO; e o resumo (P2b) pode ENCOLHER o fio (troca antigas por 1 resumo) — então
    # `mensagens[n_antes:]` mediria errado (até zero). Comparar por id é robusto ao encolher:
    # o que sobrou de turnos anteriores mantém o mesmo id; o resumo e a fala nova têm ids
    # novos. Sem memória, o conjunto é vazio → conta o fio inteiro, como sempre.
    ids_antes: set = set()
    if memoria:
        try:
            st = app.get_state(config)
            msgs_antes = (getattr(st, "values", None) or {}).get("messages") or []
            ids_antes = {m.id for m in msgs_antes if getattr(m, "id", None) is not None}
        except Exception:
            ids_antes = set()
    # Feedback ao vivo: o turno de LLM pode demorar; avisa que o agente está pensando.
    atividade.registrar(f"{agente.nome}: pensando…")
    if retomar is not None:
        # Retomada do portão NATIVO (P3): a decisão do humano volta como
        # `Command(resume=…)` no MESMO thread_id — o agente continua de onde parou, sem
        # re-derivar do texto. Precisa de checkpointer/config (garantido pelo chamador).
        resultado = app.invoke(Command(resume=retomar), config)
    elif memoria:
        resultado = app.invoke({"messages": [{"role": "user", "content": entrada}]}, config)
    else:
        resultado = app.invoke({"messages": [{"role": "user", "content": entrada}]})

    # Não confiamos na narração do agente: se uma ação IRREVERSÍVEL falhou,
    # a execução falha de forma determinística e visível (nunca em silêncio).
    if falhas:
        raise FalhaInstrumento(falhas[0])

    mensagens = resultado["messages"]
    # DELTA do turno POR IDENTIDADE: o que NÃO estava no fio antes. Sem memória, ids_antes é
    # vazio → o fio inteiro (como sempre). Com memória, exclui os turnos anteriores mesmo
    # que o resumo tenha reordenado/encolhido o fio; o resumo injetado (HumanMessage, sem
    # uso nem tool_calls) entra no delta mas não afeta a medição. Uso e instrumentos deste
    # turno contam só as mensagens novas.
    mensagens_turno = [m for m in mensagens if getattr(m, "id", None) not in ids_antes]
    acionados = [
        chamada.get("name")
        for m in mensagens_turno
        for chamada in (getattr(m, "tool_calls", None) or [])
    ]

    # Uso (Tarefa 5.4): soma os tokens de cada turno do modelo. Num laço de
    # tool-calling há vários AIMessage; cada turno reenvia o contexto, então a
    # soma reflete o que foi de fato consumido.
    tokens_entrada = tokens_saida = 0
    cache_read = cache_write = 0
    for m in mensagens_turno:
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
    uso = [
        {
            "modelo": modelo_usado,
            "tokens_entrada": tokens_entrada,
            "tokens_saida": tokens_saida,
            "tokens_cache_read": cache_read,
            "tokens_cache_write": cache_write,
        }
    ]

    # Portão NATIVO pausou? (P3) O HITL interrompe ANTES de executar a ferramenta
    # irreversível → o estado volta com `__interrupt__` (o pedido de aprovação: nome +
    # args da ação), em vez de concluir. A ação irreversível NÃO rodou. Devolvemos o
    # pedido para a borda apresentar ao humano e, depois, retomar com `retomar=`
    # (Command resume). `pausado=False` no caminho normal — chave aditiva, chamadores
    # atuais leem por chave e não quebram.
    interrupcoes = resultado.get("__interrupt__") if isinstance(resultado, dict) else None
    if interrupcoes:
        pend = interrupcoes[0]
        return {
            "pausado": True,
            "acao_pendente": getattr(pend, "value", pend),
            "saida": None,
            # O que o agente ESCREVEU no passo em que decidiu agir (ex.: "vou lançar o
            # reembolso de R$320…"). A borda apresenta ISSO como o pedido de confirmação —
            # na VOZ do agente — em vez de um texto genérico (evita a confirmação em dobro
            # quando o agente já explica a ação; P3d). Pode vir vazio → a borda usa o
            # genérico.
            "texto_pendente": texto_da_resposta(mensagens[-1]),
            "instrumentos_acionados": acionados,
            "mensagens_enviadas": mensagens_enviadas,
            "erros_instrumentos": erros_instrumentos,
            "ramo_escolhido": None,
            "uso": uso,
            "memoria": "duravel" if memoria else "legado",
        }

    return {
        "pausado": False,
        "saida": texto_da_resposta(mensagens[-1]),
        "instrumentos_acionados": acionados,
        "mensagens_enviadas": mensagens_enviadas,
        "erros_instrumentos": erros_instrumentos,
        "ramo_escolhido": escolha.get("rotulo"),
        "uso": uso,
        # De onde veio o contexto deste turno: "duravel" = fio do checkpointer;
        # "legado" = reconstruído do texto. Na CONVERSA, "legado" é modo degradado
        # (o carimbo no rastro é o que denuncia — ver a queda de 2026-08-22).
        "memoria": "duravel" if memoria else "legado",
    }
