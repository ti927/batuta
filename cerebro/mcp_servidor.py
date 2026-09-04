"""Batuta-MCP profissional — servidor MCP que o claude.ai do consultor aciona.

Diferente da prova descartável (login auto-aprovado, um time fixo, já aposentada),
este servidor tem **login real por consultor** (`mcp_login`) e **escopo por
organização/papel** (`mcp_escopo`): cada ferramenta descobre QUEM está falando pelo
token e só enxerga/mexe no que aquele consultor pode, pelos MESMOS guardas das rotas
REST. A IA roda na assinatura do consultor (claude.ai); o Batuta só oferece as
ferramentas.

Este módulo é a camada FINA de registro: monta o `FastMCP`, liga a telinha de login e
declara as tools (async) que leem o `sub` do token e delegam a lógica para
`mcp_ferramentas` numa thread. Fatias entregues:
- Fatia 0: fundação de login + escopo.
- Fatia 1: LEITURA completa + diagnóstico (agentes, automações, execuções, conversas,
  memórias, custo, catálogo de instrumentos, Central de Conhecimento).

Roda como serviço próprio na RAIZ de um domínio (as `.well-known` do OAuth ficam na
raiz). Sobe com: `uv run python mcp_servidor.py`.
"""

import os

import anyio
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import mcp_escopo
import mcp_ferramentas
import mcp_ferramentas_escrita as escrita
import mcp_login

# ───────────────────────────── Servidor ─────────────────────────────

mcp = FastMCP(
    "Batuta",
    instructions=(
        "Ferramentas para operar o Batuta — a plataforma onde se montam TIMES de agentes "
        "de IA que executam tarefas de uma empresa. Modelo mental: uma ORGANIZAÇÃO tem "
        "TIMES; um time tem AGENTES (um deles é o líder), INSTRUMENTOS (as ferramentas do "
        "cinto de cada agente) e AUTOMAÇÕES (o fluxo que encadeia os agentes, disparado "
        "por um gatilho). Você opera em nome do consultor autenticado e só enxerga/mexe no "
        "que ele pode, conforme o papel dele (observador lê; operador cria/edita; admin "
        "cria organização/time e exclui).\n"
        "FLUXO: comece sempre LENDO o contexto (`listar_organizacoes`, `listar_times`, "
        "`descrever_time`, `listar_agentes`, `ver_agente`) antes de agir. O `cinto` de um "
        "agente vem como ids — use `listar_instrumentos`/`ver_instrumento` para saber o que "
        "cada um é (nome, tipo, configuração, segredos que faltam) em vez de deduzir pelo "
        "nome. Para diagnosticar, use `listar_execucoes` (apenas_problemas) e "
        "`diagnosticar_execucao`, que já aponta o instrumento culpado, o agente e a ação "
        "sugerida — e traz avisos que o texto do agente esconde (ex.: uma ferramenta que "
        "respondeu falha e o agente narrou sucesso). Em dúvida de COMO um recurso funciona, "
        "use `consultar_conhecimento` em vez de adivinhar; para montar conector, consulte antes.\n"
        "SEGURANÇA (respeite sempre): (1) você NUNCA pluga segredo — ao criar credenciais/"
        "conectores, deixa o segredo pendente e orienta o consultor a colá-lo no cofre do "
        "Batuta pela tela. (2) APROVAÇÃO é do AGENTE: não há trava de ativação nem portão no "
        "desenho — quem segura uma ação até uma pessoa confirmar é o agente, com o instrumento "
        "`pedir_aprovacao` no cinto e a regra escrita no markdown dele. Ao montar um time com "
        "ação irreversível, confira isso ANTES de sugerir ativar. (3) Ações IRREVERSÍVEIS (`excluir_*`) apagam de verdade — confirme "
        "com o consultor antes de chamar; `ativar_automacao`/`desativar_automacao` mexem "
        "numa AUTOMAÇÃO (nunca no time), então diga o nome dela ao confirmar.\n"
        "ERRO: se uma ferramenta devolver falha com um CÓDIGO, repasse o código ao consultor "
        "— ele localiza o erro exato no servidor. Não invente causa nem repita a chamada às "
        "cegas."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path=mcp_login.CAMINHO_MCP,
    auth_server_provider=mcp_login.ProvedorLoginBatuta(),
    auth=AuthSettings(
        issuer_url=mcp_login.BASE_URL,
        resource_server_url=f"{mcp_login.BASE_URL}{mcp_login.CAMINHO_MCP}",
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[mcp_login.ESCOPO],
            default_scopes=[mcp_login.ESCOPO],
        ),
        required_scopes=[],  # basta um token válido; a autorização real é por org/papel
    ),
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

# Telinha de login (rotas públicas /login GET+POST).
mcp_login.registrar_rotas_login(mcp)


def _sub() -> str | None:
    return mcp_escopo.sub_do_token()


# ───────────────────────────── Ferramentas (Fatia 0 + 1) ─────────────────────────────
# Cada tool lê a identidade do token (contexto async) e delega o banco a uma thread.

@mcp.tool()
async def listar_organizacoes() -> str:
    """Lista as organizações do Batuta em que você (o consultor autenticado) participa,
    com o seu papel em cada uma. Comece por aqui para saber onde pode trabalhar."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_organizacoes, _sub())


@mcp.tool()
async def listar_times(organizacao_id: str | None = None) -> str:
    """Lista os times que você pode ver — de todas as suas organizações ou, se informar
    `organizacao_id`, só daquela organização."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_times, _sub(), organizacao_id)


@mcp.tool()
async def descrever_time(time_id: str) -> str:
    """Mostra um time seu (nome, id, organização e quantos agentes tem)."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.descrever_time, _sub(), time_id)


@mcp.tool()
async def listar_agentes(time_id: str) -> str:
    """Lista os agentes de um time seu (nome, papel, id, modelo de IA e se a memória está
    ligada). Use os ids em `ver_agente`."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_agentes, _sub(), time_id)


@mcp.tool()
async def ver_agente(agente_id: str) -> str:
    """Mostra os textos completos de um agente (os 4 markdowns: agent_md/skill_md/
    tools_md/soul_md), o modelo, se a memória está ligada e o cinto de instrumentos."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ver_agente, _sub(), agente_id)


@mcp.tool()
async def ver_memoria_agente(agente_id: str) -> str:
    """Mostra o que um agente aprendeu com o próprio trabalho (fichas de memória por
    assunto). Só leitura — para supervisionar e explicar ao consultor."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ver_memoria_agente, _sub(), agente_id)


@mcp.tool()
async def listar_automacoes(time_id: str) -> str:
    """Lista as automações de um time seu (nome, id, gatilho e se está ativa)."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_automacoes, _sub(), time_id)


@mcp.tool()
async def ver_automacao(automacao_id: str) -> str:
    """Mostra a cadeia completa (o fluxo/grafo de nós) de uma automação, com o gatilho e
    se está ativa."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ver_automacao, _sub(), automacao_id)


@mcp.tool()
async def listar_execucoes(
    time_id: str,
    automacao_id: str | None = None,
    apenas_problemas: bool = False,
    limite: int = 10,
) -> str:
    """Lista as execuções recentes de um time — para achar a que o consultor relata como
    problema. Filtre por automação e/ou só as com problema (`apenas_problemas=true`:
    falhou, parada esperando humano, presa ou na fila)."""
    return await anyio.to_thread.run_sync(
        mcp_ferramentas.listar_execucoes, _sub(), time_id, automacao_id, apenas_problemas, limite
    )


@mcp.tool()
async def diagnosticar_execucao(execucao_id: str) -> str:
    """Investiga UMA execução a fundo e devolve o diagnóstico: estado, linha do tempo dos
    passos e AVISOS (cada um com título, detalhe e ação sugerida). Use para explicar ao
    consultor por que uma execução falhou ou ficou parada e propor o próximo passo. Nunca
    expõe segredos (só diz se um canal 'tem token', nunca o valor).

    Quando um fluxo longo morreu no meio, o próximo passo raramente é "rode tudo de
    novo": na tela da execução existe **"Rodar de novo a partir daqui"**, que cria uma
    execução nova começando no passo escolhido, com a mesma entrada e a mesma ficha.
    Você NÃO tem ferramenta para isso — oriente o consultor, e avise que repetir um
    passo repete o que ele faz (se publica, publica de novo).

    Para AJUSTAR um agente sem rodar tudo, a tela do construtor tem **"Testar este
    passo"**: roda um passo só, com um texto escrito à mão. Também é ação de tela, e os
    instrumentos são REAIS (testar um passo que publica publica de verdade). Uma execução
    marcada como TESTE rodou um passo só de propósito — não a diagnostique como um fluxo
    que morreu no primeiro passo.

    Se o erro disser "passou do teto de custo do fluxo", NÃO é bug: é o teto por execução
    que o consultor ligou, funcionando. Diga quanto gastou e qual era o teto, e ofereça as
    duas saídas — subir o teto (Fluxo › Limites da execução) se o fluxo é caro por
    natureza, ou achar o passo caro com `ver_uso`.

    O mesmo vale para "passou do tempo máximo": há teto de tempo por PASSO e pela EXECUÇÃO,
    ambos desligados por padrão. Duas ressalvas ao explicar: o teto do passo barra o agente
    ENTRE ações (a chamada em andamento termina), e o da execução conta tempo de TRABALHO —
    a espera por uma aprovação humana não consome o teto.

    NEM TODA EXECUÇÃO PARADA ESTÁ COM PROBLEMA. São TRÊS as pausas legítimas, e só a
    primeira pede algo de alguém:
    - `aguardando_humano` — o agente chamou `pedir_aprovacao` e espera uma pessoa.
    - `aguardando_tempo` — está num passo "Esperar"; volta SOZINHA na data de `retomar_em`.
    - `aguardando_sub_fluxo` — está num passo "Chamar outra automação", esperando a
      automação chamada terminar; o rastro dela fica no passo. A execução chamada carrega
      `chamada_por_execucao_id`, e a falha dela NÃO conta para o disjuntor da automação
      chamada (quem rodou foi o chamador).
    Nas duas últimas, não diga ao consultor que travou nem mande reiniciar nada."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.diagnosticar_execucao, _sub(), execucao_id)


@mcp.tool()
async def listar_conversas(time_id: str, estado: str | None = None) -> str:
    """Lista as conversas de mensageria de um time (contato, canal, estado, nº de turnos).
    Filtro opcional por estado."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_conversas, _sub(), time_id, estado)


@mcp.tool()
async def ler_conversa(conversa_id: str) -> str:
    """Lê a thread completa de uma conversa de mensageria (as mensagens entre o contato e
    o agente/operador)."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ler_conversa, _sub(), conversa_id)


@mcp.tool()
async def ver_uso(time_id: str) -> str:
    """Mostra o custo de IA (US$) de um time — execuções + mensageria — com a quebra por
    categoria e os tokens. (O custo da IA criadora é por organização, não por time.)

    Serve também para escolher o TETO DE CUSTO POR EXECUÇÃO de uma automação (Fluxo ›
    Limites da execução, na tela — você não tem ferramenta para defini-lo): veja aqui
    quanto uma execução saudável custa e recomende um teto com FOLGA. Teto colado no custo
    real transforma qualquer variação (um texto mais longo, uma retentativa) em falha, e a
    execução que estoura o teto conta para o disjuntor."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ver_uso, _sub(), time_id)


@mcp.tool()
async def listar_tipos_instrumento() -> str:
    """Lista os tipos de instrumento disponíveis, com o que cada um faz, os campos de
    configuração (obrigatório/secreto) e se a ação é irreversível. Use para saber o que é
    possível montar e o que merece uma aprovação humana antes."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_tipos_instrumento, _sub())


@mcp.tool()
async def listar_instrumentos(time_id: str) -> str:
    """Lista os instrumentos JÁ CRIADOS num time — id, nome, tipo, configuração pública,
    quais segredos estão preenchidos e se a ação é irreversível. Use para saber o que
    cada id do `cinto` de um agente é, e para conferir um instrumento feito pela tela.
    (Diferente de `listar_tipos_instrumento`, que mostra o catálogo do que dá para criar.)"""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_instrumentos, _sub(), time_id)


@mcp.tool()
async def ver_instrumento(instrumento_id: str) -> str:
    """Mostra um instrumento a fundo: configuração pública, credencial apontada, segredos
    preenchidos e os que ainda FALTAM para ele funcionar. Nunca devolve o valor de um
    segredo."""
    return await anyio.to_thread.run_sync(
        mcp_ferramentas.ver_instrumento, _sub(), instrumento_id
    )


@mcp.tool()
async def consultar_conhecimento(topico: str) -> str:
    """Consulta a Central de Conhecimento do Batuta — o manual dos recursos (instrumentos,
    automações, gatilhos, condições e ramos, aprovação, chaves, credenciais, mensageria, memória do
    agente, etc.). Use quando não souber COMO um recurso funciona, em vez de adivinhar."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.consultar_conhecimento, _sub(), topico)


@mcp.tool()
async def listar_tipos_credencial() -> str:
    """Lista os tipos de credencial nomeada e seus campos (quais são de identidade e quais
    são secretos). Use para saber o que uma credencial de cada tipo precisa."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_tipos_credencial, _sub())


@mcp.tool()
async def listar_credenciais(organizacao_id: str) -> str:
    """Lista as credenciais nomeadas de uma organização (mascaradas — segredos só aparecem
    com os 4 últimos dígitos), com o tipo, se já está preenchida e quantos instrumentos a
    usam."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.listar_credenciais, _sub(), organizacao_id)


@mcp.tool()
async def ver_chaves_de_ia(organizacao_id: str) -> str:
    """Mostra quais provedores de IA (Anthropic/OpenAI/Google/…) já têm chave configurada
    para a organização (só sim/não por provedor — nenhum segredo). Use para saber com quais
    modelos os agentes podem rodar."""
    return await anyio.to_thread.run_sync(mcp_ferramentas.ver_chaves_de_ia, _sub(), organizacao_id)


# ───────────────────────── Ferramentas de ESCRITA (Fatia 2) ─────────────────────────
# Criam/editam de verdade, reusando a porta validada `criacao/servicos.py`. Escopadas por
# papel (a maioria exige 'operador'; criar time exige 'admin'). O commit é do decorator.

@mcp.tool()
async def criar_time(organizacao_id: str, nome: str, descricao: str | None = None) -> str:
    """Cria um TIME novo numa organização sua (exige que você seja admin da organização).
    Um time reúne agentes, instrumentos e automações."""
    return await anyio.to_thread.run_sync(escrita.criar_time, _sub(), organizacao_id, nome, descricao)


@mcp.tool()
async def editar_time(time_id: str, nome: str | None = None, descricao: str | None = None) -> str:
    """Renomeia e/ou muda a descrição de um time seu."""
    return await anyio.to_thread.run_sync(escrita.editar_time, _sub(), time_id, nome, descricao)


@mcp.tool()
async def criar_agente(
    time_id: str,
    nome: str,
    papel: str = "agente",
    agent_md: str | None = None,
    skill_md: str | None = None,
    tools_md: str | None = None,
    soul_md: str | None = None,
    modelo_ia: str | None = None,
) -> str:
    """Cria um agente num time. `papel` é 'agente' (padrão) ou 'lider' (um por time). O
    comportamento do agente vem dos 4 textos (markdowns): `agent_md` (quem ele é e faz),
    `skill_md` (o passo a passo), `tools_md` (como usar os instrumentos), `soul_md` (tom/
    voz). `modelo_ia` é opcional (senão usa o padrão)."""
    return await anyio.to_thread.run_sync(
        escrita.criar_agente, _sub(), time_id, nome, papel,
        agent_md, skill_md, tools_md, soul_md, modelo_ia,
    )


@mcp.tool()
async def editar_agente(
    agente_id: str,
    nome: str | None = None,
    papel: str | None = None,
    agent_md: str | None = None,
    skill_md: str | None = None,
    tools_md: str | None = None,
    soul_md: str | None = None,
    modelo_ia: str | None = None,
) -> str:
    """Edita um agente (só os campos informados). Para ver o que já está escrito antes de
    reescrever, use `ver_agente`.

    Os quatro markdowns são lidos JUNTOS pelo agente. Ao trocar o JEITO de fazer algo
    (outro instrumento, outro caminho), leia todos antes e APAGUE a instrução antiga no
    mesmo movimento — regra nova num campo com a velha em outro faz o agente seguir a
    velha, em silêncio. Foi assim que um time voltou a pedir aprovação pelo canal cru em
    vez do instrumento `pedir_aprovacao`, e a execução terminou sem ninguém aprovar."""
    return await anyio.to_thread.run_sync(
        escrita.editar_agente, _sub(), agente_id, nome, papel,
        agent_md, skill_md, tools_md, soul_md, modelo_ia,
    )


@mcp.tool()
async def remover_agente(agente_id: str) -> str:
    """Remove um agente do time (e o tira das cadeias em que aparece)."""
    return await anyio.to_thread.run_sync(escrita.remover_agente, _sub(), agente_id)


@mcp.tool()
async def configurar_instrumento(
    time_id: str, nome: str, tipo: str, configuracao: dict | None = None
) -> str:
    """Cria um instrumento (uma ferramenta do cinto) de um `tipo` do catálogo (veja
    `listar_tipos_instrumento` para os tipos e campos). Os campos secretos NÃO são
    plugados aqui — ficam pendentes para o consultor colar no cofre. Para uma integração
    de API com várias operações, use `montar_conector`."""
    return await anyio.to_thread.run_sync(
        escrita.configurar_instrumento, _sub(), time_id, nome, tipo, configuracao
    )


@mcp.tool()
async def editar_instrumento(
    instrumento_id: str, nome: str | None = None, configuracao: dict | None = None
) -> str:
    """Edita o nome e/ou a configuração pública de um instrumento (o tipo não muda)."""
    return await anyio.to_thread.run_sync(
        escrita.editar_instrumento, _sub(), instrumento_id, nome, configuracao
    )


@mcp.tool()
async def montar_conector(
    time_id: str, conector: dict, conector_id: str | None = None
) -> str:
    """Cria (ou edita, se passar `conector_id`) um CONECTOR — um instrumento que reúne
    VÁRIAS operações de uma mesma API (cada operação vira uma ação no cinto), montado a
    partir de uma documentação de API, SEM código. Você declara auth_tipo/auth_nome mas
    NÃO pluga o token (fica pendente no cofre). Formato do `conector`: {nome, descricao,
    auth_tipo: 'nenhuma|bearer|cabecalho|query', auth_nome, operacoes: [{nome, descricao,
    metodo, url (use [colchete] p/ trecho variável), campos: [{nome, papel: 'ia|fixo',
    destino: 'query|corpo|url', valor, descricao, obrigatorio}], campos_resposta: [...]}]}.
    Em dúvida do formato (sobretudo Bubble), chame consultar_conhecimento 'construir
    conector'. Depois teste cada operação com `testar_operacao_conector`."""
    return await anyio.to_thread.run_sync(
        escrita.montar_conector, _sub(), time_id, conector, conector_id
    )


@mcp.tool()
async def testar_operacao_conector(
    conector_id: str, operacao: str, valores: dict | None = None
) -> str:
    """Testa UMA operação de um conector com valores de exemplo — roda a chamada REAL e
    devolve a resposta (para você conferir que funciona e escolher os `campos_resposta`).
    `valores` = {nome_do_campo: valor} para os campos de papel 'ia'."""
    return await anyio.to_thread.run_sync(
        escrita.testar_operacao_conector, _sub(), conector_id, operacao, valores
    )


@mcp.tool()
async def encaixar_instrumento(agente_id: str, instrumento_id: str) -> str:
    """Pendura um instrumento no cinto de um agente (ambos do mesmo time)."""
    return await anyio.to_thread.run_sync(
        escrita.encaixar_instrumento, _sub(), agente_id, instrumento_id
    )


@mcp.tool()
async def desencaixar_instrumento(agente_id: str, instrumento_id: str) -> str:
    """Tira um instrumento do cinto de um agente."""
    return await anyio.to_thread.run_sync(
        escrita.desencaixar_instrumento, _sub(), agente_id, instrumento_id
    )


@mcp.tool()
async def criar_automacao(time_id: str, nome: str) -> str:
    """Cria uma automação nova (vazia, desligada) num time. Depois monte o fluxo com
    `montar_cadeia` e o gatilho com `definir_gatilho`, passando o `automacao_id` que volta
    aqui."""
    return await anyio.to_thread.run_sync(escrita.criar_automacao, _sub(), time_id, nome)


@mcp.tool()
async def renomear_automacao(automacao_id: str, nome: str) -> str:
    """Renomeia uma automação."""
    return await anyio.to_thread.run_sync(escrita.renomear_automacao, _sub(), automacao_id, nome)


@mcp.tool()
async def montar_cadeia(automacao_id: str, cadeia: dict) -> str:
    """Define a cadeia (o fluxo) de uma automação como um GRAFO de nós: {"inicial": "<id
    do nó inicial>", "nos": [{"id": "<id do nó>", "tipo": "agente", "ref": "<id do
    agente>", "saidas": [{"rotulo": "...", "quando": "...", "tipo":
    "condicional", "destino": "<id de outro nó, ou \\"fim\\">"}]}]}.

    BIFURCAÇÃO: o `quando` (a condição que o agente lê para decidir) é OBRIGATÓRIO em
    cada saída quando o nó tem 2+ saídas condicionais — sem ele a cadeia é recusada. O
    fluxo segue TODAS as saídas cuja condição for atendida, não só uma: duas saídas com
    a MESMA condição e destinos diferentes fazem os dois destinos rodarem (é assim que
    se desenha "aprovou → faz o carrossel E o story"). Se dois ramos reencontram o
    mesmo nó, ele roda uma vez só, com os dois textos juntos.
    A saída pode ter "tipo": "condicional" (padrão), "erro" (percorrida SÓ se o passo
    falhar — o fluxo segue por ela com a mensagem do erro em vez de a automação morrer)
    ou "senao" (só quando nenhuma condicional foi atendida). "erro" e "senao" não levam
    "quando". Sem "senao", nada casando = aquele ramo termina, com o motivo no rastro.

    FICHA DA EXECUÇÃO: os dados NÃO trafegam só no texto. O que o gatilho trouxe
    (`entrada`) e o que os agentes guardarem com a ferramenta `anotar` ficam na ficha e
    chegam a TODOS os passos — não instrua um agente a "repassar os inputs adiante".
    Uma saída condicional pode ter "regra": {"campo","operador","valor","valor2"}, e aí
    quem confere é o MOTOR contra a ficha (operadores: igual, diferente, contem,
    nao_contem, maior, maior_ou_igual, menor, menor_ou_igual, entre, preenchido, vazio).
    Use para decisão numérica/exata; deixe com o agente o que for julgamento.
    Há também o nó {"tipo": "cada", "lista": "<campo>", "item_em": "item",
    "acumular_em": "<campo>"}: repete o trecho seguinte uma vez por item da lista.

    ESPERAR: o nó {"tipo": "esperar", "espera": {"quanto": 2, "unidade": "dias"}}
    (minutos|horas|dias) segura o fluxo e o solta depois, PRESERVANDO a ficha e o ponto do
    grafo — a execução volta exatamente dali. Use para "publique 24h depois", "cobre o lead
    em 2 dias". NÃO use `agendar_automacao` para isso: aquilo dispara um fluxo NOVO, que
    começa do zero e sem a ficha. Teto de 60 dias; sem tempo definido o fluxo passa direto
    avisando.

    CHAMAR OUTRA AUTOMAÇÃO: o nó
    {"tipo": "chamar", "chamar": {"automacao_id": "<id>"}} roda outra automação INTEIRA e
    espera o resultado dela — ela recebe a ficha desta execução e devolve o que produziu,
    que vira a entrada do passo seguinte. Use para "passa pelo time X e usa o parecer".
    NÃO use `agendar_automacao` para isso: aquilo é fogo-e-esquece e nunca fica sabendo o
    resultado. Sem `automacao_id` o fluxo não salva; máximo de 3 automações encadeadas e
    nenhum laço (A→B→A é recusado). A automação chamada NÃO precisa estar ativa: chamar
    funciona com ela desativada (quem só existe para ser chamada não tem gatilho próprio),
    e o rastro registra o aviso — inclusive dizendo quando quem a desligou foi o
    DISJUNTOR, caso em que ela já falhou 3 vezes seguidas. Ao diagnosticar, `aguardando_sub_fluxo` não é
    travamento: é a espera pela automação chamada, cujo rastro fica no passo.

    APROVAÇÃO: não existe `gate` no nó (foi removido em 2026-08-31). Para um passo esperar
    uma pessoa, dê ao AGENTE dele o instrumento `pedir_aprovacao` e escreva no markdown
    quando usá-lo. Não precisa criar os nós 'gatilho'/'fim' — o sistema completa.

    EXECUÇÕES JÁ DISPARADAS NÃO MUDAM: cada execução roda o desenho fotografado no
    disparo (inclusive ao retomar uma aprovação em aberto). O que você montar aqui vale
    da PRÓXIMA execução em diante — não conserta uma execução parada, e também não a
    quebra. Para consertar uma execução presa, aja sobre ela, não sobre o desenho."""
    return await anyio.to_thread.run_sync(escrita.montar_cadeia, _sub(), automacao_id, cadeia)


@mcp.tool()
async def definir_gatilho(
    automacao_id: str, tipo_gatilho: str, configuracao_gatilho: dict | None = None
) -> str:
    """Define o gatilho de uma automação. Tipos: 'manual' (sem config), 'webhook' (sem
    config — uma chamada externa dispara), 'agendamento' (config = {frequencia:
    'diaria'|'semanal'|'mensal', hora: 0-23, minuto: 0-59, dia_semana: 0-6 só semanal,
    dia_mes: 1-31 só mensal, entrada?: texto}), 'comentario_instagram'."""
    return await anyio.to_thread.run_sync(
        escrita.definir_gatilho, _sub(), automacao_id, tipo_gatilho, configuracao_gatilho
    )


@mcp.tool()
async def ativar_automacao(automacao_id: str) -> str:
    """LIGA uma AUTOMAÇÃO (passa a poder disparar) — não mexe no time.

    Não há mais trava: o Batuta NÃO recusa mais ativar uma automação com ação
    irreversível sem aprovação humana. A responsabilidade é sua: antes de ativar um time
    que publica/envia/lança, confira se o agente que faz isso tem o instrumento
    `pedir_aprovacao` no cinto e a regra escrita no markdown — e diga isso ao consultor.

    Se a automação estiver inativa com `desligada_por_falhas_em` preenchido, quem a
    desligou foi o DISJUNTOR: ela falhou 3 vezes seguidas rodando sozinha. Não religue de
    cara — veja antes o que quebrou (`listar_execucoes` com apenas_problemas +
    `diagnosticar_execucao`) e conserte a causa. Ativar zera a contagem e dá três chances
    novas, então religar sem consertar só adia o mesmo desligamento."""
    return await anyio.to_thread.run_sync(escrita.ativar_automacao, _sub(), automacao_id)


@mcp.tool()
async def desativar_automacao(automacao_id: str) -> str:
    """DESLIGA uma AUTOMAÇÃO (para de disparar) — não mexe no time nem nos agentes."""
    return await anyio.to_thread.run_sync(escrita.desativar_automacao, _sub(), automacao_id)


@mcp.tool()
async def criar_credencial(organizacao_id: str, nome: str, tipo: str) -> str:
    """Cria o ESQUELETO de uma credencial nomeada (nome + tipo) numa organização. NÃO
    recebe segredos: o consultor cola a senha/token no cofre do Batuta pela tela. Veja os
    tipos e campos em `listar_tipos_credencial`. Depois um instrumento pode apontar para
    esta credencial. (A IA nunca pluga o segredo.)"""
    return await anyio.to_thread.run_sync(escrita.criar_credencial, _sub(), organizacao_id, nome, tipo)


@mcp.tool()
async def remover_credencial(credencial_id: str) -> str:
    """Remove uma credencial da organização (bloqueada se algum instrumento ainda a usa)."""
    return await anyio.to_thread.run_sync(escrita.remover_credencial, _sub(), credencial_id)


# ───────────────────────── Fatia 3b: config, referência, exclusão, duplicação, org ─────────────────────────

@mcp.tool()
async def configurar_memoria_agente(agente_id: str, ativa: bool, recall: str = "sempre") -> str:
    """Liga ou desliga a MEMÓRIA de um agente (aprender com o próprio trabalho). `ativa`
    = true/false; `recall` = 'sempre' (injeta as fichas no contexto, ideal p/ atendimento)
    ou 'sob_demanda' (só busca quando as instruções mandarem)."""
    return await anyio.to_thread.run_sync(
        escrita.configurar_memoria_agente, _sub(), agente_id, ativa, recall
    )


@mcp.tool()
async def apontar_credencial(instrumento_id: str, credencial_id: str | None = None) -> str:
    """Faz um instrumento USAR uma credencial nomeada (por id) — o jeito de ligar um
    conector/instrumento ao segredo que o consultor colou no cofre. Passe `credencial_id`
    vazio para desvincular. A credencial precisa existir, ser da organização e de um tipo
    que o instrumento aceita."""
    return await anyio.to_thread.run_sync(
        escrita.apontar_credencial, _sub(), instrumento_id, credencial_id
    )


@mcp.tool()
async def duplicar_time(time_id: str, novo_nome: str) -> str:
    """Cria uma cópia independente de um time inteiro (agentes, instrumentos, automações)
    na mesma organização, com um novo nome. Exige ser admin da organização."""
    return await anyio.to_thread.run_sync(escrita.duplicar_time, _sub(), time_id, novo_nome)


@mcp.tool()
async def excluir_time(time_id: str) -> str:
    """EXCLUI um time inteiro — junto com seus agentes, instrumentos e automações. AÇÃO
    IRREVERSÍVEL. Exige ser admin da organização. Confirme com o consultor antes."""
    return await anyio.to_thread.run_sync(escrita.excluir_time, _sub(), time_id)


@mcp.tool()
async def excluir_automacao(automacao_id: str) -> str:
    """EXCLUI uma automação (o fluxo). AÇÃO IRREVERSÍVEL. Exige ser admin. Confirme antes."""
    return await anyio.to_thread.run_sync(escrita.excluir_automacao, _sub(), automacao_id)


@mcp.tool()
async def excluir_instrumento(instrumento_id: str) -> str:
    """EXCLUI um instrumento. AÇÃO IRREVERSÍVEL. Exige ser admin. Confirme antes."""
    return await anyio.to_thread.run_sync(escrita.excluir_instrumento, _sub(), instrumento_id)


@mcp.tool()
async def criar_organizacao(nome: str) -> str:
    """Cria uma organização nova (ex.: para um novo cliente da consultoria). Você vira
    admin dela automaticamente. Depois crie times dentro com `criar_time`."""
    return await anyio.to_thread.run_sync(escrita.criar_organizacao, _sub(), nome)


@mcp.tool()
async def excluir_organizacao(organizacao_id: str) -> str:
    """Exclui uma organização VAZIA (sem nenhum time) — o par de `criar_organizacao`,
    útil para desfazer uma criação. Com times dentro, recusa e diz o que precisa sair
    antes: nunca apaga times/execuções/credenciais em cascata. Exige admin."""
    return await anyio.to_thread.run_sync(
        escrita.excluir_organizacao, _sub(), organizacao_id
    )


# O app ASGI standalone (com o próprio lifespan que roda o session manager).
asgi_app = mcp.streamable_http_app()


if __name__ == "__main__":
    # Ponto de entrada para o Railway: `uv run python mcp_servidor.py`.
    import uvicorn

    mcp_login.preparar()  # garante a tabela de clientes OAuth (idempotente)
    uvicorn.run(asgi_app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
