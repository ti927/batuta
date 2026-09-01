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
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.errors import GraphRecursionError
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
from orquestracao import ficha as ficha_mod
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

# Teto de idas-e-voltas do laço de ferramentas de UM turno de agente (`recursion_limit`
# do LangGraph; cada chamada de ferramenta gasta ~2). Corta o agente em laço antes de
# queimar tokens. O padrão da biblioteca (25) é baixo para um cinto grande.
MAX_ITERACOES_AGENTE = 60


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
    irreversivel: bool, erros: list[dict], falhas: list[str] | None = None,
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
    # AÇÃO IRREVERSÍVEL que respondeu `ok: false` NÃO aconteceu. Antes isso só ia para
    # o rastro e a execução seguia "concluída" com o agente narrando sucesso (o
    # lançamento perdido no Bubble, 2026-08-25). Agora entra em `falhas`: o passo falha
    # de forma visível, como já falhava quando o instrumento levantava exceção.
    # Não retentamos: uma ação irreversível pode ter acontecido pela metade.
    if irreversivel and falhas is not None:
        falhas.append(f"O instrumento '{ferramenta}' não completou a ação: {erro}")


def _turno_interrompido(falhas: list[str], pedido: dict | None = None) -> str | None:
    """Resposta curta que substitui QUALQUER ação depois que o turno já acabou — por
    falha ou por espera. Nos dois casos, deixar o agente continuar agindo é como a
    execução faz meio trabalho e narra sucesso.

    - Falhou uma ação IRREVERSÍVEL: o turno já está condenado (`raise` no fim).
    - Pediu APROVAÇÃO: o agente está esperando uma pessoa; agir agora seria fazer
      justamente o que ele foi mandado confirmar antes."""
    if falhas:
        return json.dumps(
            {
                "ok": False,
                "erro": "Este passo já falhou numa ação irreversível e foi "
                "interrompido. Não execute mais nenhuma ação; encerre relatando a "
                "falha.",
            },
            ensure_ascii=False,
        )
    if pedido:
        return json.dumps(
            {
                "ok": False,
                "erro": "Você já pediu aprovação e está aguardando a resposta da "
                "pessoa. Não execute mais nenhuma ação agora — encerre este turno; "
                "você continua quando ela responder.",
            },
            ensure_ascii=False,
        )
    return None


def _com_rastro_de_resposta(
    ferramenta: StructuredTool, inst, tipo_nome: str, irreversivel: bool,
    erros: list[dict], falhas: list[str], pedido: dict,
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
            falhas=falhas,
        )
        return retorno

    original_func = ferramenta.func
    original_coro = ferramenta.coroutine
    func = None
    coro = None
    if original_func is not None:
        def func(*args, **kwargs):
            parado = _turno_interrompido(falhas, pedido)
            return parado if parado else _observar(original_func(*args, **kwargs))
    if original_coro is not None:
        async def coro(*args, **kwargs):
            parado = _turno_interrompido(falhas, pedido)
            return parado if parado else _observar(await original_coro(*args, **kwargs))
    return ferramenta.model_copy(update={"func": func, "coroutine": coro})


def _ferramenta_unica(
    inst, tipo, config, falhas: list[str], mensagens_enviadas: dict[str, list[str]],
    erros: list[dict], pedido: dict,
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
    `mensagens_enviadas` (por id de instrumento). É o que carrega adiante exatamente
    o que a pessoa viu (e não o status que o agente narra depois).

    Quando o instrumento PARA para uma pessoa (`tipo.pausa_para_humano`, hoje só o
    `pedir_aprovacao`), o pedido é registrado em `pedido` e, daí em diante, nenhuma
    outra ação roda no turno: o agente está esperando, não trabalhando."""

    # Derivado por instância (REST pelo método, SQL pelo somente_leitura). É o
    # mesmo critério da parede de ativação — uma fonte de verdade só.
    irreversivel = acao_irreversivel(tipo.tipo, inst.configuracao or {})
    campo_msg = getattr(tipo, "campo_mensagem", None)

    def executar(**kwargs) -> str:
        # Uma ação irreversível já falhou neste turno, ou o agente já pediu aprovação
        # e está esperando: nada mais roda (ver `_turno_interrompido`).
        parado = _turno_interrompido(falhas, pedido)
        if parado:
            return parado
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
            falhas=falhas,
        )
        # O instrumento PAROU para uma pessoa: guarda o pedido (a borda o transforma
        # em `aguardando_humano`) e o turno acaba aqui — nada mais é acionado.
        if getattr(tipo, "pausa_para_humano", False) and resultado.get("ok"):
            pedido.update(
                {
                    "mensagem": (getattr(args, campo_msg, None) or "") if campo_msg else "",
                    "instrumento_id": str(inst.id),
                    "canal_instrumento_id": resultado.get("canal_instrumento_id"),
                    "destinatario": resultado.get("destinatario"),
                }
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
    erros: list[dict], pedido: dict,
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
            _com_rastro_de_resposta(f, inst, tipo.tipo, irrev, erros, falhas, pedido)
            for f in expandidas
        ]
    return [
        _ferramenta_unica(
            inst, tipo, config, falhas, mensagens_enviadas, erros, pedido
        )
    ]


def _opcoes_das_saidas(saidas: list[dict]) -> str:
    """As saídas do nó como uma lista legível 'rótulo — siga por aqui quando…'.

    A CONDIÇÃO (`quando`) é o que o agente de fato avalia; o rótulo é só o nome da
    seta. Até 2026-08-31 o editor não tinha caixa para a condição, então isto vinha
    sempre "(sem descrição)" e o agente escolhia no escuro."""
    linhas = []
    for s in saidas:
        if not s.get("rotulo"):
            continue
        quando = (s.get("quando") or "").strip()
        linhas.append(
            f'- "{s["rotulo"]}" — siga por aqui quando: {quando}'
            if quando
            else f'- "{s["rotulo"]}" — (esta saída não diz quando seguir por ela; '
            "use o rótulo como pista)"
        )
        # Regra exata (Onda 2): quem compara é o MOTOR, contra a ficha. O agente
        # precisa saber disso — senão ele "decide" um caminho que não é dele decidir e
        # narra uma escolha que o código já tinha tomado.
        regra = ficha_mod.descrever_regra(s.get("regra"))
        if regra:
            linhas.append(
                f"    (esta saída tem regra exata: {regra} — quem confere é o sistema, "
                "não você; garanta só que o campo esteja anotado na ficha)"
            )
    return "\n".join(linhas)


class _AnotarArgs(BaseModel):
    campo: str = Field(
        description="Nome curto e claro do valor, como você o chamaria numa planilha "
        "(ex.: 'url_da_capa', 'total', 'cliente'). Reuse o MESMO nome para corrigir um "
        "valor já guardado."
    )
    valor: str = Field(
        description="O valor a guardar, já pronto para o próximo passo usar. Guarde o "
        "dado em si (a URL, o número, o nome) — não uma frase sobre ele."
    )


def _ferramenta_anotar(anotacoes: dict) -> StructuredTool:
    """Ferramenta de VARIÁVEL DE FLUXO: o agente guarda um valor na ficha da execução,
    e ele chega a todos os passos seguintes.

    Existe porque entre nós só trafega texto: sem isto, um dado só sobrevive se o
    agente lembrar de repeti-lo no texto final — e ele esquece (2026-09-01, o Carrossel
    que recebeu "Aprovado. Seguindo para publicação" em vez do título e da URL). Com
    `anotar`, o dado viaja pela ficha, não pela prosa.

    As anotações do turno ficam no dict do closure e o motor as funde na ficha depois
    (mesmo padrão de `mensagens_enviadas` e `escolha`)."""

    def guardar(campo: str, valor: str) -> str:
        nome = ficha_mod.normalizar_nome(campo)
        if not nome:
            return json.dumps(
                {"ok": False, "erro": "nome de campo vazio"}, ensure_ascii=False
            )
        anotacoes[nome] = valor
        return json.dumps({"ok": True, "campo": nome}, ensure_ascii=False)

    return StructuredTool.from_function(
        func=guardar,
        name="anotar",
        description=(
            "Guarda um valor na ficha desta execução, com um nome. O que você guardar "
            "fica disponível para TODOS os passos seguintes da automação, sem você "
            "precisar repeti-lo no texto. Use para tudo que o próximo passo vai "
            "precisar: uma URL que você gerou, um total que apurou, uma decisão que "
            "tomou. Chamar de novo com o mesmo nome substitui o valor."
        ),
        args_schema=_AnotarArgs,
    )


def _ferramenta_seguir_para(saidas: list[dict], escolha: dict) -> StructuredTool:
    """Ferramenta de DECISÃO DE FLUXO: o PRÓPRIO agente declara por quais saídas do
    nó o fluxo segue — em vez de uma LLM roteadora separada adivinhar pela prosa.

    `rotulos` é uma LISTA (o grafo faz fan-out: se três condições foram atendidas,
    os três caminhos rodam). Cada item é um enum dos rótulos das saídas — a IA não
    inventa caminho. A escolha é registrada no dict `escolha` do closure (mesmo
    padrão de `mensagens_enviadas`)."""
    rotulos = [s["rotulo"] for s in saidas if s.get("rotulo")]
    Args = create_model(
        "SeguirParaArgs",
        rotulos=(
            list[Literal[tuple(rotulos)]],  # type: ignore[valid-type]
            Field(
                description="TODOS os caminhos cuja condição foi atendida — não só um. "
                "Se duas condições se aplicam, liste as duas: os dois caminhos rodam."
            ),
        ),
        motivo=(
            str,
            Field(
                default="",
                description="Uma frase curta dizendo por que estes caminhos, e não "
                "os outros. Fica no rastro da execução.",
            ),
        ),
    )
    descricao = (
        "Decide por quais caminhos o fluxo segue depois deste passo. Chame UMA vez, "
        "ao concluir, listando TODOS os caminhos cuja condição foi atendida (pode "
        "ser mais de um — eles rodam todos).\nCaminhos:\n"
        f"{_opcoes_das_saidas(saidas)}"
    )

    def seguir(**kwargs) -> str:
        args = Args.model_validate(kwargs)
        escolhidos = list(dict.fromkeys(args.rotulos))  # sem repetir, na ordem
        escolha["rotulos"] = escolhidos
        escolha["motivo"] = args.motivo or None
        return json.dumps({"ok": True, "rotulos": escolhidos}, ensure_ascii=False)

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
    # A regra que vale em TODOS os casos: o fluxo é um grafo — vários caminhos podem
    # ser atendidos ao mesmo tempo, e então todos rodam.
    regra_fanout = (
        "Avalie a condição de CADA caminho de forma independente e liste TODOS os "
        "que foram atendidos — não escolha só o melhor. Dois caminhos com a mesma "
        "condição significam 'faça os dois'. Se nenhum foi atendido, não chame a "
        "ferramenta."
    )
    if gate:
        if (texto_portao or "").strip():
            return (
                "## Caminhos do fluxo (este passo aguarda uma pessoa)\n"
                f"{texto_portao.strip()}\n\n"
                "IMPORTANTE (mecânica do fluxo): para o fluxo AVANÇAR você PRECISA "
                "declarar o caminho chamando a ferramenta `seguir_para` com os "
                "rótulos abaixo. Enquanto não chamar `seguir_para`, o fluxo continua "
                "aguardando a pessoa (use isso quando ainda precisar falar com ela).\n"
                f"{regra_fanout}\n"
                f"Caminhos:\n{opcoes}"
            )
        return (
            "## Caminhos do fluxo (este passo aguarda uma pessoa)\n"
            "Quando você tiver a decisão da pessoa, chame a ferramenta `seguir_para` "
            "com os rótulos dos caminhos escolhidos E escreva também uma frase curta "
            "para ela, confirmando o que vai acontecer — essa frase será enviada a "
            "ela. Se ainda precisar de algo dela (perguntar, esclarecer), apenas "
            "responda normalmente, SEM chamar `seguir_para` — o fluxo segue "
            "aguardando a resposta dela.\n"
            f"{regra_fanout}\n"
            f"Caminhos:\n{opcoes}"
        )
    return (
        "## Caminhos do fluxo\n"
        "Ao terminar este passo, declare por quais caminhos o fluxo segue: chame a "
        "ferramenta `seguir_para`.\n"
        f"{regra_fanout}\n"
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


def executar_agente(
    agente: Agente,
    cinto: list[Instrumento],
    entrada: str,
    *,
    saidas: list[dict] | None = None,
    ficha: dict | None = None,
    gate: bool = False,
    texto_portao: str | None = None,
    checkpointer=None,
    thread_id: str | None = None,
    preambulo_sistema: str | None = None,
    interativo: bool = False,
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
    # `interativo` = tem gente esperando (atendimento por mensageria): a chamada de IA
    # usa os limites CURTOS, para a falha chegar em ~1 min em vez de meia hora. Sem ele
    # (automação de fundo), nada muda.
    modelo = construir_modelo(agente.modelo_ia, interativo=interativo)
    falhas: list[str] = []
    # Por instrumento (id → textos): o que o agente APRESENTOU a um humano por canal
    # neste turno. O portão de aprovação usa isto para carregar adiante o que a
    # pessoa viu, em vez do status que o agente narra depois.
    mensagens_enviadas: dict[str, list[str]] = {}
    # Erros CRUS dos instrumentos neste turno (para o diagnóstico, não só a narração
    # da IA) — inclui falhas de leitura/geração que não derrubam a execução.
    erros_instrumentos: list[dict] = []
    # Os ramos que o agente declarar via `seguir_para` ({"rotulos": [...], "motivo": ...}).
    escolha: dict = {}
    # O pedido de aprovação, quando o agente aciona um instrumento que PARA para uma
    # pessoa (`pausa_para_humano`). Preenchido = o turno terminou numa espera.
    pedido_aprovacao: dict = {}
    # O que o agente guardou na FICHA da execução neste turno (ferramenta `anotar`).
    # O motor funde isto na ficha e leva adiante — é a variável de fluxo (Onda 2).
    anotacoes: dict = {}
    # Constrói as ferramentas do cinto e, em paralelo, o mapa nome→irreversível (a MESMA
    # regra da parede: `acao_irreversivel(tipo, config)`) — é o que o portão nativo (P3)
    # usa para saber QUAIS ferramentas exigem aprovação antes de executar. As ferramentas
    # de controle/memória (seguir_para, registrar/pesquisar_memoria), adicionadas abaixo,
    # não entram no mapa → nunca são gateadas.
    ferramentas: list = []
    irreversivel_por_ferramenta: dict[str, bool] = {}
    for i in cinto:
        fs = _ferramentas_de_instrumento(
            i, falhas, mensagens_enviadas, erros_instrumentos, pedido_aprovacao
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
    # A FICHA da execução (Onda 2): só a ORQUESTRAÇÃO a passa (a conversa da mensageria
    # não — lá a memória entre turnos já faz esse papel). Presente = o agente ganha a
    # ferramenta `anotar` e o bloco da ficha na entrada do turno (não no prompt de
    # sistema: a ficha muda a cada passo e ali ela invalidaria o cache do Anthropic,
    # que é o que segura o custo — ver Frente B).
    tem_ficha = ficha is not None
    if tem_ficha:
        ferramentas.append(_ferramenta_anotar(anotacoes))
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
        extra["middleware"] = _middlewares_de_memoria()
    app = create_agent(modelo, ferramentas, system_prompt=prompt_sistema, **extra)
    # Teto de iterações do laço de ferramentas: um agente em laço (chama a mesma
    # ferramenta sem parar) para aqui, com mensagem legível, em vez de queimar tokens
    # até o timeout. O padrão do LangGraph é 25 — baixo para agentes com muitos
    # instrumentos —, então subimos e passamos SEMPRE (com ou sem memória), para o
    # limite ser explícito e o mesmo nos dois caminhos.
    config: dict = {"recursion_limit": MAX_ITERACOES_AGENTE}
    if memoria:
        config["configurable"] = {"thread_id": thread_id}
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
    # A ficha vai na MENSAGEM do turno, à frente da entrada: ela muda a cada passo, e no
    # prompt de sistema invalidaria o cache. Fica antes do texto porque é a fonte — o
    # texto que vem do nó anterior é o que o agente anterior *narrou*, e a lição de
    # 2026-09-01 é que a narração perde dado; a ficha, não.
    bloco_ficha = ficha_mod.para_o_prompt(ficha) if tem_ficha else ""
    conteudo = f"{bloco_ficha}\n\n---\n\n{entrada}" if bloco_ficha else entrada
    try:
        resultado = app.invoke(
            {"messages": [{"role": "user", "content": conteudo}]}, config
        )
    except GraphRecursionError as e:
        # Laço de ferramentas sem fim. Erro honesto (§12-A), com o nome do agente e o
        # que fazer — em vez do `GraphRecursionError` cru, que não diz nada a ninguém.
        raise FalhaInstrumento(
            f"O agente '{agente.nome}' ficou repetindo ações sem concluir "
            f"({MAX_ITERACOES_AGENTE} idas e voltas) e foi interrompido. Revise a "
            "documentação dele (o que fazer quando um instrumento falha) ou reduza o "
            "tamanho da tarefa deste passo."
        ) from e

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

    # O agente PEDIU APROVAÇÃO e está esperando uma pessoa (instrumento
    # `pedir_aprovacao`, `tipo.pausa_para_humano`). Quem decide que este momento
    # precisa de gente é o AGENTE — não um interruptor no desenho, como era o portão.
    # A borda transforma isto em `aguardando_humano`; `pausado=False` no caminho
    # normal, chave aditiva.
    if pedido_aprovacao:
        return {
            "pausado": True,
            "aprovacao": dict(pedido_aprovacao),
            # O que a pessoa vai ler e aprovar é a MENSAGEM que o agente escreveu ao
            # pedir — não o que ele narrou depois ("enviei, aguardando").
            "saida": pedido_aprovacao.get("mensagem") or texto_da_resposta(mensagens[-1]),
            "instrumentos_acionados": acionados,
            "mensagens_enviadas": mensagens_enviadas,
            "erros_instrumentos": erros_instrumentos,
            "ramo_escolhido": None,
            "ramos_escolhidos": [],
            "motivo_ramo": None,
            # O que ele anotou ANTES de pedir aprovação não pode se perder na pausa:
            # a espera pode durar horas, e ao voltar o dado precisa estar na ficha.
            "anotacoes": dict(anotacoes),
            "uso": uso,
            "memoria": "duravel" if memoria else "legado",
        }

    ramos = list(escolha.get("rotulos") or [])
    return {
        "pausado": False,
        "saida": texto_da_resposta(mensagens[-1]),
        "instrumentos_acionados": acionados,
        "mensagens_enviadas": mensagens_enviadas,
        "erros_instrumentos": erros_instrumentos,
        # `ramos_escolhidos` é a verdade (o grafo faz fan-out); `ramo_escolhido`
        # (singular, o primeiro) fica para quem ainda lê um caminho só.
        "ramos_escolhidos": ramos,
        "ramo_escolhido": ramos[0] if ramos else None,
        "motivo_ramo": escolha.get("motivo"),
        # O que ele guardou na ficha neste turno (ferramenta `anotar`). O motor funde
        # na ficha da execução e leva a todos os passos seguintes.
        "anotacoes": dict(anotacoes),
        "uso": uso,
        # De onde veio o contexto deste turno: "duravel" = fio do checkpointer;
        # "legado" = reconstruído do texto. Na CONVERSA, "legado" é modo degradado
        # (o carimbo no rastro é o que denuncia — ver a queda de 2026-08-22).
        "memoria": "duravel" if memoria else "legado",
    }
