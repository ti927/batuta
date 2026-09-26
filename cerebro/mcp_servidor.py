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

# Orçamento de conexões DESTE serviço (ver db.py): o MCP atende poucas pessoas e divide o
# pooler do Supabase com o cérebro — fica com uma fatia pequena. Precisa vir ANTES de
# qualquer import que carregue `db` (o engine lê isto ao nascer). Uma variável definida no
# Railway continua mandando.
os.environ.setdefault("DB_POOL_SIZE", "2")
os.environ.setdefault("DB_MAX_OVERFLOW", "4")

import anyio  # noqa: E402
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import mcp_escopo
import mcp_ferramentas
import mcp_ferramentas_escrita as escrita
import mcp_ferramentas_quadros as quadros_mcp
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
        "ação irreversível, confira isso ANTES de sugerir ativar. E o markdown desse agente "
        "precisa dizer o que ele DECLARA depois da decisão, com os rótulos exatos das saídas "
        "do nó: sem isso o fluxo fica parado para sempre mesmo com tudo aprovado — é a causa "
        "nº 1 de 'aprovei e não aconteceu nada'. (3) Ações IRREVERSÍVEIS (`excluir_*`) apagam de verdade — confirme "
        "com o consultor antes de chamar; `ativar_automacao`/`desativar_automacao` mexem "
        "numa AUTOMAÇÃO (nunca no time), então diga o nome dela ao confirmar.\n"
        "QUADROS (o cérebro da organização): quando agentes precisam passar informação uns "
        "aos outros — inclusive entre times —, use um quadro (`listar_quadros`, "
        "`criar_quadro`) e dê o instrumento tipo \"quadro\" a quem grava e a quem lê; nunca "
        "planilha improvisada nem a memória do agente. Toda escrita aceita `simular=true` "
        "(use antes e mostre ao consultor); apagar/excluir só simulam sem `confirmar=true`. "
        "Para saber o que uma execução GRAVOU de fato, `diagnosticar_execucao` lista as "
        "linhas por quadro — a narração do agente não é prova.\n"
        "TESTAR (antes de entregar): criou ou mudou um instrumento? Teste VOCÊ mesmo — "
        "`testar_operacao_conector` para cada operação de um conector, `testar_instrumento` "
        "para os outros tipos — em vez de pedir ao consultor que teste. O teste é REAL, "
        "inclusive o que grava: pode testar a operação que cria, envia ou publica, mas TUDO "
        "que um teste criar precisa ser reconhecível como teste: ponha a palavra TESTES nos "
        "campos de texto que aparecem lá fora (nome, título, assunto, descrição, mensagem — "
        "ex.: \"TESTES — pedido de exemplo\"), prefira rascunho/privado quando a API "
        "permitir, e ao terminar diga ao consultor o que foi criado e onde, para ele apagar "
        "se quiser. Leia o `erro`/`corpo` da resposta antes de concluir que funcionou.\n"
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
    falhou, parada esperando humano, presa ou na fila).

    ATENÇÃO ao "era para rodar e não rodou": se NÃO HÁ execução no horário reclamado, não
    conclua que o motor falhou nem mande recriar a automação — o disparo pode nunca ter
    nascido. Um disparo AGENDADO POR UM AGENTE (instrumento "Agendar automação") é
    CANCELADO se, na hora marcada, a automação-alvo estiver desativada ou removida; ele
    não fica esperando ela voltar. Você não tem ferramenta para ler agendamentos: peça ao
    consultor a aba **Agendadas** das Execuções, seção "Não dispararam (últimos 7 dias)",
    onde a linha traz o motivo escrito. Isso é RECUPERÁVEL na própria linha — **Disparar
    agora** (roda na hora, com o texto que o agente tinha montado) ou **Reagendar** —, e
    reativar a automação é o que impede a repetição. O trabalho não se perdeu."""
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

    Se o rastro mostrar que uma APROVAÇÃO atingiu o limite de idas-e-vindas (evento
    `portao.limite_atingido`), também não é bug e o fluxo NÃO ficou parado: passado o teto
    (*Máx. de idas-e-vindas na aprovação*, 8 por padrão), o agente avisa a pessoa e a
    resposta dela segue direto pelo caminho que indicar. O canal continua funcionando —
    não diga que a conversa morreu nem mande reiniciar. Se o consultor precisa de mais
    rodadas de ajuste, o número é dele: Fluxo › Aprovação humana.

    ATENÇÃO a uma confusão comum: o teto de custo da CONVERSA não conta geração de imagem
    ou vídeo — isso é trabalho do fluxo e responde ao teto por EXECUÇÃO. Se o consultor
    disser que "o carrossel estourou o teto da conversa", o dado está errado (era assim
    até 2026-09-14, e era justamente o defeito).

    NEM TODA EXECUÇÃO PARADA ESTÁ COM PROBLEMA. São TRÊS as pausas legítimas, e só a
    primeira pede algo de alguém:
    - `aguardando_humano` — o agente chamou `pedir_aprovacao` e espera uma pessoa.
    - `aguardando_tempo` — está num passo "Esperar"; volta SOZINHA na data de `retomar_em`.
    - `aguardando_sub_fluxo` — está num passo "Chamar outra automação", esperando a
      automação chamada terminar; o rastro dela fica no passo. A execução chamada carrega
      `chamada_por_execucao_id`, e a falha dela NÃO conta para o disjuntor da automação
      chamada (quem rodou foi o chamador).
    Nas duas últimas, não diga ao consultor que travou nem mande reiniciar nada.

    SOBRE `aguardando_humano`: desde 2026-09-21 ela tem PRAZO PRÓPRIO (`espera_ate`). Ao
    vencer, um vigia avisa o time UMA vez (evento `espera.esquecida`) e NÃO encerra nada —
    esperar dias por uma aprovação é legítimo. Se o consultor diz "aprovei e não aconteceu
    nada" e a execução segue em `aguardando_humano` rodada após rodada, procure o evento
    `portao.indeciso`: significa que o agente conversou sem declarar caminho nenhum, e a
    causa quase sempre é o markdown dele não citar os rótulos das saídas daquele nó — o
    conserto é no agente, não no motor. E se o evento for `retomada.entrada_recusada` ou
    `portao.entrada_recusada`, a mesma aprovação foi respondida por dois lugares ao mesmo
    tempo: não é falha, a espera continua de pé e basta responder de novo.

    A EXCEÇÃO: se a data de `retomar_em` já passou faz tempo, ou se a automação chamada
    já terminou e mesmo assim o chamador segue parado, aí sim há problema — e ele NÃO
    está na automação: é o vigia que solta essas execuções que morreu. Mande o consultor
    abrir a página `/status` e olhar o elo **"Vigia das execuções"**; se estiver vermelho,
    o conserto é o botão Reconectar de lá. Não proponha mexer no fluxo nesse caso.

    E se o consultor reclama de um horário em que NÃO EXISTE execução nenhuma, esta
    ferramenta não se aplica — veja a orientação em `listar_execucoes`: um disparo
    agendado por agente é cancelado quando a automação-alvo está desativada na hora
    marcada, e isso se recupera pela tela."""
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
    vez do instrumento `pedir_aprovacao`, e a execução terminou sem ninguém aprovar.

    SE ESTE AGENTE PEDE APROVAÇÃO e o nó dele tem 2+ saídas, o markdown PRECISA citar os
    rótulos exatos dessas saídas e dizer que declará-los é a última coisa que ele faz
    depois da decisão. Use `ver_automacao` para ler os rótulos do nó antes de escrever —
    não invente nomes. Sem isso o agente conversa, refaz o material, publica e nunca
    declara caminho: a execução fica parada para sempre com tudo aprovado (incidente de
    2026-09-21). Se o nó faz fan-out (dois destinos com a mesma condição), mande declarar
    OS DOIS rótulos — declarar um só deixa metade do trabalho sem rodar, em silêncio."""
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
    de API com várias operações, use `montar_conector`. Depois de criar, TESTE você mesmo
    com `testar_instrumento`."""
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
    auth_tipo: 'nenhuma|bearer|cabecalho|query|basic|oauth2|google_conta_servico',
    auth_nome, auth_usuario (usuário no basic / Client ID no oauth2), url_token (oauth2),
    escopo (oauth2 se pedir; OBRIGATÓRIO na conta de serviço), operacoes: [{nome,
    descricao, metodo, url (use [colchete] p/ trecho variável), campos: [{nome,
    papel: 'ia|fixo', destino: 'query|corpo|url', valor, descricao, obrigatorio}],
    campos_resposta: [...], somente_leitura: false, custo_por_chamada_usd: 0}]}.
    API PAGA (ex.: Gemini): informe `custo_por_chamada_usd` (US$ por chamada) na
    operação — é o único jeito de esse custo entrar no custo do time.
    APIs do GOOGLE: use 'google_conta_servico', não 'oauth2' — identidade de máquina, sem
    consentimento, sem app verificado, sem expirar; o segredo é o JSON da chave e o
    consultor precisa dar acesso ao E-MAIL da conta de serviço no serviço de destino.
    NEM TODO POST ESCREVE: API que consulta por POST (o searchAnalytics/query do Search
    Console) leva `somente_leitura: true` NAQUELA operação, senão cada consulta para e
    pede aprovação. A aprovação é por OPERAÇÃO, não pelo conector inteiro.
    No destino 'corpo', texto começando com [ ou { (JSON válido) e true/false/null viram
    lista/objeto/booleano; número NÃO converte (ids viram outra coisa).
    Em dúvida do formato (sobretudo Bubble), chame consultar_conhecimento 'construir
    conector'. Depois TESTE você mesmo cada operação com `testar_operacao_conector` —
    inclusive as que gravam, marcando com TESTES o que o teste criar."""
    return await anyio.to_thread.run_sync(
        escrita.montar_conector, _sub(), time_id, conector, conector_id
    )


@mcp.tool()
async def testar_operacao_conector(
    conector_id: str, operacao: str, valores: dict | None = None
) -> str:
    """Testa UMA operação de um conector com valores de exemplo — roda a chamada REAL e
    devolve a resposta (para você conferir que funciona e escolher os `campos_resposta`).
    `valores` = {nome_do_campo: valor} para os campos de papel 'ia'.
    O teste é REAL também quando a operação GRAVA (cria, altera, envia, apaga): pode
    testar, mas marque o que criar com a palavra TESTES nos campos de texto (ex.: nome
    "TESTES — cliente de exemplo") e, ao terminar, diga ao consultor o que foi criado e
    onde. A resposta traz `escreve: true` e um campo `atencao` quando a chamada mexeu em
    algo lá fora. Para ALTERAR ou APAGAR, use um registro que você mesmo criou no teste
    — nunca um registro real do cliente.
    Funciona TAMBÉM em conector com segredo: este serviço roda sem a chave do cofre (a
    IA nunca recebe segredo), então o teste é pedido ao cérebro, que decifra, chama a
    API e devolve só a resposta. Se a ponte não estiver ligada no ambiente, a ferramenta
    diz isso e manda pedir o teste ao consultor — não fique retentando.
    Quando a API recusa, a resposta traz o MOTIVO que o serviço deu (campos `erro` e
    `corpo`) — leia-o em vez de adivinhar a causa: é ali que está "startDate field is
    required" ou "User does not have sufficient permission for site"."""
    return await anyio.to_thread.run_sync(
        escrita.testar_operacao_conector, _sub(), conector_id, operacao, valores
    )


@mcp.tool()
async def testar_instrumento(instrumento_id: str, argumentos: dict | None = None) -> str:
    """Testa um instrumento que NÃO é conector (REST, SQL, WordPress, Telegram, busca,
    gerar imagem, webhook…) acionando-o de verdade, como o botão de testar da tela.
    `argumentos` = os argumentos que o agente passaria (veja os campos do tipo em
    `listar_tipos_instrumento`). Conector se testa por operação, com
    `testar_operacao_conector`.
    O teste é REAL: se o instrumento envia, publica ou grava, isso ACONTECE. Pode
    testar, mas ponha a palavra TESTES no conteúdo (título, mensagem, texto — ex.:
    "TESTES — post de exemplo"), prefira rascunho/privado quando o instrumento permitir,
    e ao terminar diga ao consultor o que foi criado/enviado e onde. A resposta traz
    `escreve: true` e um campo `atencao` nesse caso. Geração de vídeo custa caro: só
    teste se o consultor pedir.
    Funciona com instrumento que tem segredo: o teste é pedido ao cérebro, que decifra
    lá e devolve só o resultado. Se a ponte não estiver ligada, a ferramenta diz isso —
    não fique retentando. Falha volta com `ok: false` e o motivo em `erro`: leia-o."""
    return await anyio.to_thread.run_sync(
        escrita.testar_instrumento, _sub(), instrumento_id, argumentos
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
    Confira JUNTO uma segunda coisa, que é a causa nº 1 de "aprovei e não aconteceu nada":
    se o nó desse agente tem 2+ saídas, o markdown dele precisa citar os rótulos exatos
    delas e mandar declará-los depois da decisão. Ativar um time com esse buraco entrega
    um fluxo que para no meio, aprovado e parado.

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
async def configurar_ritmo_agente(agente_id: str, ajustes: dict | None = None) -> str:
    """Define o RITMO e a ESPERA de um agente — o que ele sobrepõe das regras do fluxo.

    O fluxo dá o padrão; isto aqui é a exceção DESTE trabalhador, e vale em todos os
    fluxos onde ele aparece. Chave ausente = herda. Passe `{}` para voltar a herdar tudo.

    Só entram regras que são propriedade de UM ATO dele:
    - `teto_min_passo` — minutos que ele pode trabalhar num passo (0 = sem teto). Um
      agente que gera vídeo precisa de muito mais que um que escreve um parágrafo.
    - `timeout_min`, `nudge_timeout_min`, `encerrar_por_inatividade` — quanto esta espera
      tolera silêncio.
    - `portao_forma`, `portao_acao_abandono`, `portao_max_rodadas`,
      `teto_espera_humano_min` — como ele conduz uma aprovação e o que faz se a pessoa
      some. Só fazem efeito se ele tiver `pedir_aprovacao` no cinto.

    USE ISTO quando dois passos do mesmo fluxo esperam pessoas diferentes: confirmar um
    detalhe com quem pediu (cutucar em 10 min) e pedir a um diretor que aprove uma compra
    (esperar 24 h e NUNCA cancelar) são a mesma automação com réguas opostas. Com uma
    regra só por fluxo, esse fluxo não é construível.

    NÃO entram aqui `max_turnos` nem `teto_usd`: são contadores da conversa INTEIRA, só
    podem ter um teto, e ficam no fluxo. Passá-los aqui é recusado."""
    return await anyio.to_thread.run_sync(
        escrita.configurar_ritmo_agente, _sub(), agente_id, ajustes
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


# ───────────────────── Quadros do cérebro da organização ─────────────────────
# docs/CEREBRO-PLANO.md §7. Os textos abaixo são o que a IA externa LÊ para usar os
# quadros — por isso listam tipos, operadores e modos por extenso (a lição de agosto:
# a IA lê a docstring, não o capítulo da Central).

_FILTROS_DOC = (
    "`filtros`: lista de {\"coluna\": <nome>, \"operador\": <op>, \"valor\": <valor>}, todos "
    "valendo juntos. Operadores: = · != · > · >= · < · <= · contem (texto) · em (valor é "
    "lista) · vazio · nao_vazio (sem valor). O valor passa pela mesma conversão da "
    "gravação (\"21/09/2026\" filtra data). Também dá para filtrar pelo carimbo: "
    "_criado_em, _atualizado_em, _origem (agente|pessoa|ia_criadora|mcp|importacao), "
    "_execucao_id, _agente_id."
)


def _doc(texto: str):
    """Prende a descrição à função ANTES do `@mcp.tool()` lê-la. Necessário quando o
    texto é montado (com `_FILTROS_DOC`): uma string montada no corpo NÃO é docstring
    em Python — a ferramenta iria para a IA externa sem descrição nenhuma."""

    def aplicar(fn):
        fn.__doc__ = texto
        return fn

    return aplicar


@mcp.tool()
async def listar_quadros(organizacao_id: str) -> str:
    """Lista os QUADROS do cérebro de uma organização — dados em colunas que os agentes
    (e pessoas) escrevem e leem, inclusive entre times diferentes. Por quadro: linhas,
    descrição e QUEM USA (instrumento, time, acesso ler|ler_e_escrever, agentes)."""
    return await anyio.to_thread.run_sync(quadros_mcp.listar_quadros, _sub(), organizacao_id)


@mcp.tool()
async def ver_quadro(organizacao_id: str, quadro: str) -> str:
    """Mostra um quadro (por nome ou id): colunas com tipo/obrigatória/opções/descrição,
    a CHAVE (colunas que identificam cada linha), os LIMITES (valor, padrão, teto), as 5
    linhas mais recentes (com o carimbo de quem gravou) e quem usa o quadro."""
    return await anyio.to_thread.run_sync(quadros_mcp.ver_quadro, _sub(), organizacao_id, quadro)


@mcp.tool()
@_doc(
    "Lê linhas de um quadro. Sempre devolve o `total` que casa e, se veio só parte, o "
    "`proximo` deslocamento para continuar (paginação). Cada linha traz `id`, `valores` "
    "(por nome de coluna) e `carimbo` (origem, agente, execução, usuário, versão, datas). "
    + _FILTROS_DOC
    + " `ordem`: nomes de coluna, \"-\" na frente = decrescente (padrão: mais recentes "
    "primeiro). `colunas`: só estas na resposta. `limite`: padrão 50, teto do quadro. "
    "`so_o_mais_recente_de`: só as linhas com o MAIOR valor desta coluna (ex.: \"Data\" = "
    "a rodada mais recente). `execucao_id`: só o que aquela execução gravou."
)
async def consultar_quadro(
    organizacao_id: str, quadro: str, filtros: list[dict] | None = None,
    ordem: list[str] | None = None, colunas: list[str] | None = None,
    limite: int | None = None, deslocamento: int = 0,
    so_o_mais_recente_de: str | None = None, execucao_id: str | None = None,
) -> str:
    return await anyio.to_thread.run_sync(
        quadros_mcp.consultar_quadro, _sub(), organizacao_id, quadro, filtros, ordem,
        colunas, limite, deslocamento, so_o_mais_recente_de, execucao_id,
    )


@mcp.tool()
@_doc(
    "Totais calculados PELO BANCO (não some de cabeça): `metricas` = lista de "
    "{\"funcao\": contar|soma|media|minimo|maximo, \"coluna\": <nome>} (sem = contar "
    "linhas; soma/média só em número/dinheiro). `agrupar_por`: até 3 colunas. "
    "`so_o_mais_recente_de`: como na consulta. " + _FILTROS_DOC
)
async def totais_quadro(
    organizacao_id: str, quadro: str, metricas: list[dict] | None = None,
    agrupar_por: list[str] | None = None, filtros: list[dict] | None = None,
    so_o_mais_recente_de: str | None = None,
) -> str:
    return await anyio.to_thread.run_sync(
        quadros_mcp.totais_quadro, _sub(), organizacao_id, quadro, metricas, agrupar_por,
        filtros, so_o_mais_recente_de,
    )


@mcp.tool()
async def historico_linha(organizacao_id: str, quadro: str, linha_id: str) -> str:
    """Todas as mudanças de uma linha (inclusive se já foi apagada): criou/mudou/apagou,
    o valor ANTES e DEPOIS, quando, e quem (origem, agente, execução, usuário)."""
    return await anyio.to_thread.run_sync(
        quadros_mcp.historico_linha, _sub(), organizacao_id, quadro, linha_id
    )


@mcp.tool()
@_doc(
    "Exporta o quadro (ou o que casa com os filtros) como texto CSV, até 5.000 linhas. "
    + _FILTROS_DOC
)
async def exportar_quadro(organizacao_id: str, quadro: str, filtros: list[dict] | None = None) -> str:
    return await anyio.to_thread.run_sync(
        quadros_mcp.exportar_quadro, _sub(), organizacao_id, quadro, filtros
    )


@mcp.tool()
async def criar_quadro(
    organizacao_id: str, nome: str, colunas: list[dict], chave: list[str] | None = None,
    descricao: str | None = None, limites: dict | None = None, simular: bool = False,
) -> str:
    """Cria um QUADRO no cérebro da organização. Use quando agentes precisam deixar
    informação para OUTROS agentes (outro time, outro dia) — no lugar de planilha. NÃO use
    para o que já mora num sistema oficial da empresa (ERP, Bubble): lá o agente lê e
    escreve por instrumento. Não guarde CPF, salário nem dados de saúde.

    `colunas`: lista de {"nome", "tipo", "obrigatoria"?, "opcoes"?, "descricao"?}. Tipos:
    texto (até 500 caracteres) · texto_longo · numero · dinheiro · data · data_hora ·
    sim_nao · opcao (exige "opcoes": [...]; use para estados). `chave`: nomes das colunas
    que identificam cada linha (UMA linha por tema/cliente/semana); vazio = só acumula.
    `descricao`: para que serve (o agente lê — escreva bem). `limites` (opcional):
    {colunas, linhas_por_gravacao, linhas_por_consulta, linhas_no_quadro,
    tamanho_texto_longo}. `simular=true` mostra sem criar. Exige operador.
    Depois, dê o instrumento tipo "quadro" (configurar_instrumento, configuracao
    {"quadro": <nome>, "acesso": "ler" | "ler_e_escrever"}) a quem produz e a quem lê."""
    return await anyio.to_thread.run_sync(
        quadros_mcp.criar_quadro, _sub(), organizacao_id, nome, colunas, chave, descricao,
        limites, simular,
    )


@mcp.tool()
async def alterar_quadro(
    organizacao_id: str, quadro: str, operacoes: list[dict], simular: bool = False
) -> str:
    """Muda a ESTRUTURA de um quadro — lista de operações aplicadas na ordem, tudo ou
    nada. Cada uma tem "acao": renomear{nome} · descrever{descricao} ·
    adicionar_coluna{coluna:{nome,tipo,...}} · renomear_coluna{coluna,nome} ·
    descrever_coluna{coluna,descricao} · trocar_tipo{coluna,tipo,opcoes?,
    esvaziar_invalidos?} · mudar_opcoes{coluna,opcoes,esvaziar_invalidos?} ·
    obrigatoria{coluna,valor} · remover_coluna{coluna} (APAGA os valores dela) ·
    mudar_chave{colunas:[...]} · ajustar_limite{limite,valor (null = padrão)}.
    Trocar tipo CONVERTE os valores existentes: o que não converte recusa a mudança
    (com a lista), a menos que esvaziar_invalidos=true. Rode com `simular=true` antes e
    mostre ao consultor. Exige operador."""
    return await anyio.to_thread.run_sync(
        quadros_mcp.alterar_quadro, _sub(), organizacao_id, quadro, operacoes, simular
    )


@mcp.tool()
async def gravar_linhas(
    organizacao_id: str, quadro: str, linhas: list[dict], modo: str = "acrescentar",
    simular: bool = False,
) -> str:
    """Grava linhas num quadro — TUDO OU NADA: se qualquer linha tiver problema, nada é
    gravado e a resposta lista linha, coluna e motivo. `linhas`: lista de
    {"<nome da coluna>": valor}. Datas como 2026-09-21 ou 21/09/2026; números sem
    separador de milhar ("1.000" é recusado como ambíguo). `modo`: "acrescentar" (chave
    repetida é recusada) ou "pela_chave" (cria se não existe; se existe, muda só as
    colunas informadas; valor "" apaga o campo). `simular=true` diz o que aconteceria.
    O carimbo registra que foi você (MCP) em nome do consultor. Exige operador."""
    return await anyio.to_thread.run_sync(
        quadros_mcp.gravar_linhas, _sub(), organizacao_id, quadro, linhas, modo, simular
    )


@mcp.tool()
@_doc(
    "Muda as colunas de `campos` ({\"<coluna>\": novo valor}) nas linhas achadas por "
    "`ids` OU `filtros` (um dos dois é obrigatório — não existe \"mudar tudo\" sem "
    "querer). Use `simular=true` para ver quantas mudariam. Exige operador. " + _FILTROS_DOC
)
async def editar_linhas(
    organizacao_id: str, quadro: str, campos: dict, ids: list[str] | None = None,
    filtros: list[dict] | None = None, simular: bool = False,
) -> str:
    return await anyio.to_thread.run_sync(
        quadros_mcp.editar_linhas, _sub(), organizacao_id, quadro, campos, ids, filtros, simular
    )


@mcp.tool()
@_doc(
    "Apaga linhas achadas por `ids`, `filtros` e/ou `execucao_id` (desfazer TUDO o que "
    "uma execução gravou — ex.: uma rodada de teste). SEM `confirmar=true` é só uma "
    "PRÉVIA (quantas sairiam); mostre ao consultor e só então confirme. O histórico "
    "guarda o que existia. Exige operador. " + _FILTROS_DOC
)
async def apagar_linhas(
    organizacao_id: str, quadro: str, ids: list[str] | None = None,
    filtros: list[dict] | None = None, execucao_id: str | None = None,
    confirmar: bool = False,
) -> str:
    return await anyio.to_thread.run_sync(
        quadros_mcp.apagar_linhas, _sub(), organizacao_id, quadro, ids, filtros,
        execucao_id, confirmar,
    )


@mcp.tool()
async def importar_csv(
    organizacao_id: str, csv_texto: str, quadro: str | None = None,
    criar_com_nome: str | None = None, chave: list[str] | None = None,
    mapeamento: dict | None = None, ignorar_colunas_extras: bool = False,
    modo: str = "acrescentar", simular: bool = True,
) -> str:
    """Importa uma planilha (texto CSV, separado por vírgula, ponto e vírgula ou tab) —
    o caminho para migrar de uma planilha do Google. Para um quadro EXISTENTE passe
    `quadro`: o cabeçalho casa com as colunas pelo nome, ou pelo `mapeamento`
    {"<cabeçalho>": "<coluna>"}; colunas a mais recusam a importação, a menos que
    `ignorar_colunas_extras=true`. Para CRIAR o quadro a partir do CSV passe
    `criar_com_nome` (+ `chave`): as colunas e tipos são SUGERIDOS pelos valores.
    `simular` é TRUE por padrão: primeiro veja a sugestão/o que entraria, confira com o
    consultor, depois chame com simular=false. Tudo ou nada; até 5.000 linhas por vez.
    `modo`: acrescentar | pela_chave. Exige operador."""
    return await anyio.to_thread.run_sync(
        quadros_mcp.importar_csv, _sub(), organizacao_id, csv_texto, quadro, criar_com_nome,
        chave, mapeamento, ignorar_colunas_extras, modo, simular,
    )


@mcp.tool()
async def listar_links_quadro(organizacao_id: str, quadro: str) -> str:
    """Lista os LINKS DE LEITURA de um quadro — os endereços que painéis de fora (Google
    Planilhas com IMPORTDATA, Looker Studio, Power BI, painel próprio) usam para ler o
    quadro sem login. Por link: nome, os 4 últimos caracteres, estado (ativo/revogado/
    expirado), limite de leituras por minuto, validade, quantas leituras e a última.
    Você NÃO recebe o link inteiro nem pode criar um: ele é uma senha, e quem cria é um
    admin pela tela (quadro › Quem usa › Acesso de fora). Oriente o consultor a fazer lá."""
    return await anyio.to_thread.run_sync(
        quadros_mcp.listar_links_quadro, _sub(), organizacao_id, quadro
    )


@mcp.tool()
async def revogar_link_quadro(
    organizacao_id: str, quadro: str, link_id: str, confirmar: bool = False
) -> str:
    """REVOGA um link de leitura de um quadro: o painel que o usa para de receber dados na
    hora. SEM `confirmar=true` é só uma PRÉVIA (qual link e quem o usa). Exige admin."""
    return await anyio.to_thread.run_sync(
        quadros_mcp.revogar_link_quadro, _sub(), organizacao_id, quadro, link_id, confirmar
    )


@mcp.tool()
async def excluir_quadro(organizacao_id: str, quadro: str, confirmar: bool = False) -> str:
    """EXCLUI um quadro com todas as linhas e o histórico. AÇÃO IRREVERSÍVEL. SEM
    `confirmar=true` é só uma PRÉVIA (quantas linhas e QUAIS instrumentos/agentes usam o
    quadro — eles deixam de funcionar). Confirme com o consultor. Exige admin."""
    return await anyio.to_thread.run_sync(
        quadros_mcp.excluir_quadro, _sub(), organizacao_id, quadro, confirmar
    )


# O app ASGI standalone (com o próprio lifespan que roda o session manager).
asgi_app = mcp.streamable_http_app()


if __name__ == "__main__":
    # Ponto de entrada para o Railway: `uv run python mcp_servidor.py`.
    import uvicorn

    mcp_login.preparar()  # garante a tabela de clientes OAuth (idempotente)
    uvicorn.run(asgi_app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
