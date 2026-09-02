"""As ferramentas da IA criadora — conversa eterna sobre o TIME REAL.

Mesmo encaixe de tool-use do motor (`orquestracao.agente`): cada operação é uma
`StructuredTool` que a IA aciona. No paradigma novo, elas NÃO mexem mais num
rascunho JSON — escrevem direto nas tabelas reais, pela porta única e validada de
`criacao.servicos`. O time é criado preguiçosamente no primeiro `definir_time` e
fica vinculado à conversa (`conversa.time_id`). Tudo nasce inativo e DORME até o
consultor `ativar_time` — a parede de ativação recusa ligar uma ação irreversível
sem portão humano antes. Erros de regra viram texto de volta para a IA corrigir.

`montar_ferramentas(ctx)` constrói as ferramentas fechadas sobre um
`ContextoCriacao` (sessão + conversa + usuário + chips), sempre TODAS disponíveis
(sem modos): a IA investiga, monta, ativa e conserta na mesma conversa.
"""

import functools
import json
import threading
import uuid
from dataclasses import dataclass, field

from langchain_core.tools import StructuredTool
from sqlalchemy import select
from sqlalchemy.orm import Session

import diagnostico_execucao
import instrumentos as encaixe
import memoria_agente
import precos
import segredos_instrumento as segredos
import tipos_credencial
from criacao import memoria, servicos
from criacao.servicos import ConflitoDominio
from orquestracao import atividade, grafo
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    ConversaCriacao,
    Credencial,
    Execucao,
    Instrumento,
    SegredoInstrumento,
    Time,
    Usuario,
)
from orquestracao.llm import MODELO_PADRAO


@dataclass
class ContextoCriacao:
    """O que as ferramentas precisam para agir no time real durante um turno: a
    sessão (transação do turno), a conversa (de onde sai o time e a organização),
    o usuário que age (auditoria) e os chips sugeridos."""

    sessao: Session
    conversa: ConversaCriacao
    usuario: Usuario | None = None
    chips: list[str] = field(default_factory=list)

    def time(self) -> Time | None:
        if self.conversa.time_id is None:
            return None
        return self.sessao.get(Time, self.conversa.time_id)


def _opcoes_do_campo(prop: dict) -> list | None:
    """Valores fixos de um campo (enum/Literal), inclusive dentro de anyOf
    (Optional). Espelha o `opcoesDoCampo` da interface."""
    if isinstance(prop.get("enum"), list):
        return prop["enum"]
    for p in prop.get("anyOf") or []:
        if isinstance(p.get("enum"), list):
            return p["enum"]
    return None


def catalogo_de_instrumentos() -> list[dict]:
    """O catálogo de tipos de instrumento COM os campos de configuração de cada um.

    É o que destrava a IA criadora: sem saber que o WordPress precisa de `site_url`
    e `usuario`, ela não tem como PERGUNTAR ao consultor por eles. Para cada tipo,
    lista os campos da `Config` marcando `obrigatorio`, `secreto` e — quando o campo
    é um conjunto fechado — as `opcoes` válidas; e, no nível do tipo, as
    `dependencias` (campos cujas opções dependem de outro, ex.: gerar_imagem filtra
    tamanho/qualidade pelo modelo) e se o tipo faz `acao_irreversivel` (a IA precisa
    pôr portão humano antes na cadeia)."""
    catalogo: list[dict] = []
    for tipo in encaixe.tipos_disponiveis():
        # Tipos ocultos no catálogo (ex.: o conector) têm ferramenta PRÓPRIA de
        # criação (montar_conector) — não entram no catálogo genérico do
        # configurar_instrumento, para não dar sinal misto à IA.
        if getattr(tipo, "oculto_no_catalogo", False):
            continue
        esquema = tipo.Config.model_json_schema()
        obrigatorios = set(esquema.get("required", []))
        secretos = set(tipo.campos_secretos)
        campos = []
        for nome, prop in (esquema.get("properties") or {}).items():
            campo = {
                "nome": nome,
                "descricao": prop.get("description", ""),
                "obrigatorio": nome in obrigatorios,
                "secreto": nome in secretos,
            }
            opcoes = _opcoes_do_campo(prop)
            if opcoes is not None:
                campo["opcoes"] = opcoes
            campos.append(campo)
        catalogo.append(
            {
                "tipo": tipo.tipo,
                "nome": tipo.nome_exibicao,
                "descricao": tipo.descricao,
                "campos": campos,
                "dependencias": tipo.dependencias_ui(),
                "acao_irreversivel": tipo.acao_irreversivel,
            }
        )
    return catalogo


def _ok(mensagem: str, **extra) -> str:
    return json.dumps({"ok": True, "mensagem": mensagem, **extra}, ensure_ascii=False)


def _erro(mensagem: str) -> str:
    return json.dumps({"ok": False, "erro": mensagem}, ensure_ascii=False)


def _uuid(valor: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        return None


# Tipos de gatilho e o formato EXATO da config de agendamento que o `agendador`
# espera. A IA erra por não conhecer este formato — por isso ele é documentado
# aqui, injetado no prompt e validado em definir_gatilho.
TIPOS_GATILHO = ("manual", "agendamento", "webhook", "comentario_instagram")
FORMATO_GATILHO = (
    "Tipos de gatilho:\n"
    "- 'manual': sem config. Você dispara quando quiser.\n"
    "- 'webhook': sem config. Uma chamada externa (URL pública) dispara o fluxo.\n"
    "- 'agendamento': roda no relógio. config = {frequencia: 'diaria'|'semanal'|"
    "'mensal', hora: 0-23, minuto: 0-59, dia_semana: 0-6 (0=segunda, SÓ p/ semanal), "
    "dia_mes: 1-31 (SÓ p/ mensal), entrada?: texto que vira a entrada do fluxo}. "
    "Ex. semanal: {frequencia:'semanal', dia_semana:0, hora:8, minuto:0}.\n"
    "- 'comentario_instagram': cada comentário num post de uma conta conectada "
    "dispara o fluxo. config = {midias: 'todas' (padrão) ou lista de ids de post "
    "(media_id); palavra_chave?: só dispara se o texto contém (ignora maiúsc.); "
    "teto_por_hora?: teto de disparos/hora por automação (padrão 50, protege custo)}. "
    "A CONTA em si (credencial do Instagram) é escolhida pelo humano na tela do "
    "gatilho — você NÃO a define; avise o consultor que falta escolher a conta lá."
)


def _inteiro_no_intervalo(valor, minimo: int, maximo: int) -> bool:
    try:
        return minimo <= int(valor) <= maximo
    except (TypeError, ValueError):
        return False


def _validar_gatilho(tipo: str, config: dict) -> str | None:
    """Devolve uma mensagem de erro se o gatilho estiver malformado (None = ok)."""
    if tipo not in TIPOS_GATILHO:
        return f"Gatilho desconhecido: '{tipo}'. Use um de: {', '.join(TIPOS_GATILHO)}."
    if tipo == "comentario_instagram":
        # A conta (credencial_id) é escolhida pelo HUMANO na tela (v1). Se a IA
        # mandar algo, validamos; ausência é OK (o gatilho fica "a conectar").
        cred = config.get("credencial_id")
        if cred not in (None, "") and _uuid(cred) is None:
            return "credencial_id, se informado, deve ser um id válido."
        midias = config.get("midias", "todas")
        if midias != "todas" and not (
            isinstance(midias, list) and all(isinstance(m, str) for m in midias)
        ):
            return "midias deve ser 'todas' ou uma lista de ids de post (media_id)."
        pc = config.get("palavra_chave")
        if pc is not None and not isinstance(pc, str):
            return "palavra_chave, se informada, deve ser um texto."
        teto = config.get("teto_por_hora")
        if teto is not None and not _inteiro_no_intervalo(teto, 1, 100000):
            return "teto_por_hora, se informado, deve ser um inteiro positivo."
        return None
    if tipo != "agendamento":
        return None
    freq = config.get("frequencia")
    if freq not in ("diaria", "semanal", "mensal"):
        return "Agendamento exige frequencia 'diaria', 'semanal' ou 'mensal'."
    if not _inteiro_no_intervalo(config.get("hora", 0), 0, 23):
        return "Agendamento exige 'hora' inteiro de 0 a 23."
    if not _inteiro_no_intervalo(config.get("minuto", 0), 0, 59):
        return "Agendamento exige 'minuto' inteiro de 0 a 59."
    if freq == "semanal" and not _inteiro_no_intervalo(config.get("dia_semana"), 0, 6):
        return "Agendamento semanal exige 'dia_semana' inteiro de 0 (segunda) a 6 (domingo)."
    if freq == "mensal" and not _inteiro_no_intervalo(config.get("dia_mes"), 1, 31):
        return "Agendamento mensal exige 'dia_mes' inteiro de 1 a 31."
    return None


def _snapshot_time(ctx: ContextoCriacao) -> dict:
    """Fotografia do time REAL para a IA se situar (e o front redesenhar): agentes
    com seus markdowns e cinto, instrumentos com config e segredos pendentes, e a
    automação (cadeia + gatilho + se está ativa)."""
    sess, time = ctx.sessao, ctx.time()
    if time is None:
        return {}
    agentes = sess.scalars(
        select(Agente).where(Agente.time_id == time.id).order_by(Agente.criado_em)
    ).all()
    cinto: dict[str, list[str]] = {}
    for aid, iid in sess.execute(
        select(AgenteInstrumento.agente_id, AgenteInstrumento.instrumento_id)
        .join(Agente, Agente.id == AgenteInstrumento.agente_id)
        .where(Agente.time_id == time.id)
    ).all():
        cinto.setdefault(str(aid), []).append(str(iid))
    instrumentos = sess.scalars(
        select(Instrumento).where(Instrumento.time_id == time.id).order_by(Instrumento.criado_em)
    ).all()
    guardados: dict[str, set[str]] = {}
    for iid, campo in sess.execute(
        select(SegredoInstrumento.instrumento_id, SegredoInstrumento.campo)
        .join(Instrumento, Instrumento.id == SegredoInstrumento.instrumento_id)
        .where(Instrumento.time_id == time.id)
    ).all():
        guardados.setdefault(str(iid), set()).add(campo)
    # Cobertura de segredos pelas OUTRAS fontes além do inline: credenciais nomeadas
    # apontadas pelos instrumentos (campos do tipo da credencial) e chaves de serviço
    # compartilhadas resolvíveis pelo pool. Tudo para o cálculo honesto de pendentes.
    cred_ids = {i.credencial_id for i in instrumentos if i.credencial_id}
    tipo_por_credencial: dict[uuid.UUID, str] = (
        {
            c.id: c.tipo
            for c in sess.scalars(select(Credencial).where(Credencial.id.in_(cred_ids)))
        }
        if cred_ids
        else {}
    )
    servicos_resolviveis = segredos.servicos_resolviveis(sess, time.organizacao_id)

    def _cobertos_por_credencial(i: Instrumento) -> set[str]:
        tipo = tipo_por_credencial.get(i.credencial_id) if i.credencial_id else None
        tc = tipos_credencial.obter_tipo(tipo) if tipo else None
        return set(tc.nomes_campos) if tc else set()

    autos = sess.scalars(
        select(Automacao).where(Automacao.time_id == time.id).order_by(Automacao.criado_em)
    ).all()

    def _auto_dict(a: Automacao) -> dict:
        return {
            "id": str(a.id), "nome": a.nome, "tipo_gatilho": a.tipo_gatilho,
            "configuracao_gatilho": a.configuracao_gatilho,
            # cadeia no formato canônico de grafo (lista de nós tipados).
            "cadeia": grafo.normalizar(a.cadeia or {}),
            "ativa": a.ativa,
        }

    automacoes = [_auto_dict(a) for a in autos]
    return {
        "time": {"id": str(time.id), "nome": time.nome, "descricao": time.descricao},
        "agentes": [
            {
                "id": str(a.id), "nome": a.nome, "papel": a.papel, "modelo_ia": a.modelo_ia,
                "agent_md": a.agent_md, "skill_md": a.skill_md, "tools_md": a.tools_md,
                "soul_md": a.soul_md, "cinto": cinto.get(str(a.id), []),
            }
            for a in agentes
        ],
        "instrumentos": [
            {
                "id": str(i.id), "nome": i.nome, "tipo": i.tipo,
                "configuracao": i.configuracao,
                # Resolvido por tipo+config: diz se a IA precisa pôr portão antes
                # deste instrumento. Consulta = False. (A parede liga/desliga por
                # organização; aqui é só a classificação do instrumento.)
                "acao_irreversivel": encaixe.acao_irreversivel(
                    i.tipo, i.configuracao
                ),
                "segredos_pendentes": segredos.pendentes(
                    i.tipo,
                    guardados=guardados.get(str(i.id), set()),
                    cobertos_por_credencial=_cobertos_por_credencial(i),
                    servicos_resolviveis=servicos_resolviveis,
                ),
            }
            for i in instrumentos
        ],
        # TODAS as automações do time — a IA edita cada uma pelo seu `id`.
        "automacoes": automacoes,
        # Compat: a PRIMEIRA (o canvas de /criar lê `automacao`). None se não há.
        "automacao": automacoes[0] if automacoes else None,
    }


def snapshot_time(sessao: Session, conversa: ConversaCriacao) -> dict | None:
    """Fotografia do time real de uma conversa (ou None se ainda não há time).
    Conveniência pública para o loop e as rotas redesenharem o canvas."""
    return _snapshot_time(ContextoCriacao(sessao=sessao, conversa=conversa)) or None


def enxugar_snapshot(snap: dict | None) -> dict | None:
    """Projeção ENXUTA da foto do time, só para o PROMPT da IA criadora (Parte E da
    economia de tokens). Mantém a ESTRUTURA — o que existe e os `id` para agir — e tira
    o que é PESADO e raramente muda por turno: os 4 markdowns de cada agente e a `cadeia`
    de cada automação. A IA puxa esse detalhe sob demanda com `ver_agente`/`ver_automacao`,
    só do que o turno realmente toca. Num time grande isso corta muito o custo fixo.

    IMPORTANTE: isto é SÓ para o contexto do modelo. A foto CHEIA continua indo para o
    front (redesenhar o canvas, `rotas/criacao.py` e a resposta do turno) e para o
    `ver_time` — esta função não altera aquela. Instrumentos ficam INTEIROS (config,
    `acao_irreversivel`, `segredos_pendentes` são pequenos e guiam a decisão da IA)."""
    if not snap:
        return snap
    enxuto = dict(snap)
    enxuto["agentes"] = [
        {
            "id": a.get("id"), "nome": a.get("nome"), "papel": a.get("papel"),
            "modelo_ia": a.get("modelo_ia"), "cinto": a.get("cinto", []),
        }
        for a in snap.get("agentes") or []
    ]

    def _auto_enxuta(a: dict | None) -> dict | None:
        if not a:
            return a
        return {k: v for k, v in a.items() if k != "cadeia"}

    enxuto["automacoes"] = [_auto_enxuta(a) for a in snap.get("automacoes") or []]
    enxuto["automacao"] = _auto_enxuta(snap.get("automacao"))
    return enxuto


# Frase de atividade ao vivo por ferramenta ("o que a IA está fazendo agora"), para a
# tela mostrar durante um turno longo — mesmo espírito de atividade.MENSAGENS_ATIVIDADE.
# Ferramenta sem entrada aqui cai no fallback genérico.
MENSAGENS_CRIADORA: dict[str, str] = {
    "definir_time": "Definindo o time…",
    "adicionar_agente": "Adicionando um agente…",
    "editar_agente": "Ajustando o agente…",
    "remover_agente": "Removendo um agente…",
    "configurar_instrumento": "Configurando um instrumento…",
    "editar_instrumento": "Ajustando um instrumento…",
    "montar_conector": "Montando o conector…",
    "testar_operacao_conector": "Testando a operação do conector…",
    "encaixar_instrumento": "Encaixando o instrumento no agente…",
    "desencaixar_instrumento": "Removendo o instrumento do agente…",
    "criar_automacao": "Criando a automação…",
    "renomear_automacao": "Renomeando a automação…",
    "montar_cadeia": "Montando o fluxo da automação…",
    "definir_gatilho": "Definindo o gatilho…",
    "estimar_custo": "Estimando o custo…",
    "ativar_time": "Ativando o time…",
    "desativar_time": "Desativando o time…",
    "ver_time": "Revendo o time…",
    "ver_agente": "Lendo o agente…",
    "ver_automacao": "Lendo o fluxo da automação…",
    "listar_tipos_instrumento": "Consultando os instrumentos disponíveis…",
    "listar_execucoes": "Consultando as execuções…",
    "diagnosticar_execucao": "Diagnosticando a execução…",
    "ver_memoria_agente": "Consultando a memória do agente…",
    "sugerir_proximos_passos": "Pensando nos próximos passos…",
    "atualizar_resumo": "Atualizando o resumo do projeto…",
    "lembrar": "Anotando o que aprendi…",
    "recordar": "Consultando o que sei do projeto…",
    "esquecer": "Atualizando o que sei…",
    "consultar_conhecimento": "Consultando a base de conhecimento…",
    "buscar_no_historico": "Procurando no histórico da conversa…",
}

# Parte C (iceberg): teto de resultados e de tamanho por trecho na busca do histórico —
# a busca existe para ECONOMIA, então nunca despeja tudo de volta no contexto.
_MAX_ACHADOS_HISTORICO = 8
_MAX_CHARS_ACHADO = 1200


def montar_ferramentas(ctx: ContextoCriacao) -> list[StructuredTool]:
    """As ferramentas da IA criadora ligadas a `ctx`, TODAS disponíveis. Cada uma
    escreve no time real (via `criacao.servicos`) e devolve um JSON com o resultado;
    erros de regra voltam como texto para a IA corrigir."""
    sess = ctx.sessao

    def _exigir_time() -> Time | None:
        return ctx.time()

    def _agente(agente_id: str) -> Agente | None:
        aid = _uuid(agente_id)
        ag = sess.get(Agente, aid) if aid else None
        return ag if ag and ag.time_id == ctx.conversa.time_id else None

    def _instrumento(instrumento_id: str) -> Instrumento | None:
        iid = _uuid(instrumento_id)
        inst = sess.get(Instrumento, iid) if iid else None
        return inst if inst and inst.time_id == ctx.conversa.time_id else None

    def _execucao_do_time(ex: Execucao) -> bool:
        auto = sess.get(Automacao, ex.automacao_id)
        return auto is not None and auto.time_id == ctx.conversa.time_id

    _ESTADOS_PROBLEMA = ("falhou", "aguardando_humano", "em_andamento", "aguardando")

    def definir_time(nome: str, descricao: str | None = None) -> str:
        """Define o nome e a descrição do time. Na PRIMEIRA vez cria o time (ainda
        inativo, em construção); depois atualiza nome/descrição."""
        time = ctx.time()
        if time is None:
            time = servicos.criar_time(
                sess, ctx.conversa.organizacao_id, nome, descricao, usuario=ctx.usuario
            )
            ctx.conversa.time_id = time.id
            sess.flush()
            return _ok(f"Time '{nome}' criado.", time_id=str(time.id))
        servicos.editar_time(sess, time, nome=nome, descricao=descricao)
        return _ok(f"Time '{nome}' atualizado.", time_id=str(time.id))

    def adicionar_agente(
        nome: str, papel: str = "agente", agent_md: str | None = None,
        skill_md: str | None = None, tools_md: str | None = None,
        soul_md: str | None = None, modelo_ia: str | None = None,
    ) -> str:
        """Adiciona um agente ao time. `papel` é 'lider' ou 'agente' (no máximo um
        líder). Os quatro markdowns documentam o agente: agent_md (quem é), skill_md
        (habilidades), tools_md (cinto), soul_md (personalidade). Devolve o `id` do
        agente — use-o no cinto e na cadeia. Defina o time antes (definir_time)."""
        time = _exigir_time()
        if time is None:
            return _erro("Defina o time primeiro, com definir_time.")
        try:
            agente = servicos.adicionar_agente(
                sess, time, nome=nome, papel=papel, agent_md=agent_md, skill_md=skill_md,
                tools_md=tools_md, soul_md=soul_md, modelo_ia=modelo_ia, usuario=ctx.usuario,
            )
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok(f"Agente '{nome}' adicionado.", id=str(agente.id))

    def editar_agente(
        agente_id: str, nome: str | None = None, papel: str | None = None,
        agent_md: str | None = None, skill_md: str | None = None,
        tools_md: str | None = None, soul_md: str | None = None,
        modelo_ia: str | None = None,
    ) -> str:
        """Edita um agente já existente (pelo `id`). Só os campos informados mudam.

        Os 4 markdowns são lidos JUNTOS. Se a mudança troca o JEITO de fazer algo (outro
        instrumento, outro caminho), leia os quatro com `ver_agente` e APAGUE a instrução
        antiga no mesmo movimento — regra nova num campo com a velha em outro faz o agente
        seguir a velha, calado."""
        agente = _agente(agente_id)
        if agente is None:
            return _erro(f"Não há agente com id {agente_id} neste time.")
        try:
            servicos.editar_agente(
                sess, agente, usuario=ctx.usuario, nome=nome, papel=papel,
                agent_md=agent_md, skill_md=skill_md, tools_md=tools_md,
                soul_md=soul_md, modelo_ia=modelo_ia,
            )
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok(f"Agente '{agente.nome}' atualizado.")

    def remover_agente(agente_id: str) -> str:
        """Remove um agente do time (pelo `id`) e o tira da cadeia."""
        agente = _agente(agente_id)
        if agente is None:
            return _erro(f"Não há agente com id {agente_id} neste time.")
        nome = agente.nome
        servicos.remover_agente(sess, agente, usuario=ctx.usuario)
        return _ok(f"Agente '{nome}' removido.")

    def configurar_instrumento(
        nome: str, tipo: str, configuracao: dict | None = None
    ) -> str:
        """Configura um instrumento para o time. `tipo` precisa ser do catálogo (use
        listar_tipos_instrumento para ver os CAMPOS). Em `configuracao` passe os
        campos PÚBLICOS que você coletou do consultor (ex.: WordPress → site_url,
        usuario). NÃO passe segredos (senhas, tokens): ficam pendentes para o cofre.
        Para uma INTEGRAÇÃO com uma API (um conjunto de chamadas GET/POST de um mesmo
        serviço), use montar_conector — não este. Devolve o `id` (para o cinto) e os
        segredos pendentes."""
        time = _exigir_time()
        if time is None:
            return _erro("Defina o time primeiro, com definir_time.")
        try:
            inst, pendentes = servicos.configurar_instrumento(
                sess, time, nome=nome, tipo=tipo, configuracao=configuracao, usuario=ctx.usuario
            )
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok(
            f"Instrumento '{nome}' configurado.", id=str(inst.id), segredos_pendentes=pendentes
        )

    def editar_instrumento(
        instrumento_id: str, nome: str | None = None, configuracao: dict | None = None
    ) -> str:
        """Edita um instrumento (pelo `id`): nome e/ou configuração pública. O tipo é
        fixo."""
        inst = _instrumento(instrumento_id)
        if inst is None:
            return _erro(f"Não há instrumento com id {instrumento_id} neste time.")
        try:
            servicos.editar_instrumento(
                sess, inst, nome=nome, configuracao=configuracao, usuario=ctx.usuario
            )
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok(f"Instrumento '{inst.nome}' atualizado.")

    def montar_conector(conector: dict, conector_id: str | None = None) -> str:
        """Cria (ou edita, se passar `conector_id`) um CONECTOR — um instrumento que
        reúne VÁRIAS operações de uma mesma API, cada uma virando uma ação no cinto do
        agente (ex.: "Busca Projetos", "Cria Reembolso"). É como dar ao time uma
        integração nova SEM código. Em dúvida do formato — sobretudo para APIs do
        Bubble —, consulte a Central antes (consultar_conhecimento "construir conector").

        Formato de `conector`:
        {"nome": "Gestão Lure", "descricao": "para que serve (referência humana)",
         "categoria": "opcional (só agrupa)",
         "auth_tipo": "nenhuma|bearer|cabecalho|query",
         "auth_nome": "nome do cabeçalho/parâmetro (só p/ 'cabecalho'/'query')",
         "operacoes": [
           {"nome": "Busca Projetos", "descricao": "o que faz / quando o agente usa",
            "metodo": "GET|POST|PATCH|PUT|DELETE",
            "url": "https://.../obj/Projeto  (use [colchete] p/ trecho variável)",
            "campos": [
              {"nome": "constraints", "papel": "ia|fixo", "destino": "query|corpo|url",
               "valor": "(só quando papel='fixo')",
               "descricao": "(ajuda p/ a IA, quando papel='ia')", "obrigatorio": true}
            ],
            "campos_resposta": ["_id", "cpo.NomeCliente"]}
         ]}

        Regras que importam:
        - VOCÊ NÃO PLUGA O TOKEN. Só declara `auth_tipo`/`auth_nome`; o segredo fica
          PENDENTE e o CONSULTOR o cola no cofre. Nunca ponha o token aqui.
        - `papel`: "ia" = a IA preenche na hora de acionar (vira argumento — dê uma
          `descricao` boa); "fixo" = valor constante que VOCÊ define em `valor`.
        - `destino`: "query" (na URL depois do ?), "corpo" (JSON, p/ POST/PATCH/PUT)
          ou "url" (substitui [colchete] na URL).
        - `campos_resposta`: liste só os campos que o agente usa (nome EXATO da API) —
          corta MUITO custo em buscas que voltam listas. Vazio = resposta inteira.
        - Se QUALQUER operação escreve (POST/PUT/PATCH/DELETE), o conector inteiro conta
          como AÇÃO IRREVERSÍVEL. Não há portão no desenho: dê ao agente que o usa o
          instrumento `pedir_aprovacao` e escreva no skill_md dele que ele confirma com
          uma pessoa antes de escrever no sistema externo.
        Depois de montar, TESTE cada operação com testar_operacao_conector — confere se
        funciona e revela os campos da resposta (para escolher `campos_resposta`)."""
        time = _exigir_time()
        if time is None:
            return _erro("Defina o time primeiro, com definir_time.")
        dados = {k: v for k, v in (conector or {}).items() if k != "nome"}
        nome = str((conector or {}).get("nome") or "").strip()
        dados.pop("auth_segredo", None)  # a IA nunca pluga o token (fica pendente no cofre)
        auth = str(dados.get("auth_tipo") or "nenhuma")
        lembrete = (
            "Peça ao consultor para colar o token no cofre (você não pluga segredo); "
            "depois teste as operações com testar_operacao_conector."
            if auth != "nenhuma"
            else "Sem autenticação. Teste as operações com testar_operacao_conector."
        )
        if conector_id:
            inst = _instrumento(conector_id)
            if inst is None or inst.tipo != "conector":
                return _erro(f"Não há conector com id {conector_id} neste time.")
            try:
                servicos.editar_instrumento(
                    sess, inst, nome=(nome or None), configuracao=dados, usuario=ctx.usuario
                )
            except ConflitoDominio as e:
                return _erro(str(e))
            return _ok(f"Conector '{inst.nome}' atualizado.", id=str(inst.id), lembrete=lembrete)
        if not nome:
            return _erro("O conector precisa de um nome (campo 'nome' no objeto).")
        try:
            inst, pendentes = servicos.configurar_instrumento(
                sess, time, nome=nome, tipo="conector", configuracao=dados, usuario=ctx.usuario
            )
        except ConflitoDominio as e:
            return _erro(str(e))
        # Sem autenticação, `auth_segredo` não é um pendente de verdade (o cálculo
        # estático dos campos secretos não conhece o auth_tipo) — não confunda a IA.
        if auth == "nenhuma":
            pendentes = [p for p in pendentes if p != "auth_segredo"]
        return _ok(
            f"Conector '{nome}' criado.", id=str(inst.id),
            segredos_pendentes=pendentes, lembrete=lembrete,
        )

    def testar_operacao_conector(
        conector_id: str, operacao: str, valores: dict | None = None
    ) -> str:
        """Testa UMA operação de um conector com valores de exemplo — roda a chamada
        REAL e devolve a resposta + os CAMPOS detectados (para você escolher
        `campos_resposta`). É como você confere que a operação funciona e descobre o que
        a API devolve, sem envolver o consultor. `operacao` = o nome da operação;
        `valores` = {nome_do_campo: valor} para os campos de papel 'ia' (ex.:
        {"constraints": "[{...}]"}). Se a API pede token e ele ainda não foi colado no
        cofre, a resposta volta com ok=false (autenticação) — nesse caso, peça o token
        ao consultor e teste de novo. DICA: se uma busca devolve o lote inteiro sem
        filtrar, confira o NOME do campo do filtro (ex.: Bubble usa 'constraints')."""
        inst = _instrumento(conector_id)
        if inst is None or inst.tipo != "conector":
            return _erro(f"Não há conector com id {conector_id} neste time.")
        from instrumentos.base import FalhaInstrumento, obter_tipo

        tipo = obter_tipo("conector")
        secretos = segredos.decifrar(sess, inst.id)
        config = tipo.Config.model_validate({**(inst.configuracao or {}), **secretos})
        try:
            resultado = tipo.testar_operacao(config, operacao, valores or {})
        except FalhaInstrumento as e:
            return _erro(str(e))
        return _ok("Teste executado.", resultado=resultado)

    def encaixar_instrumento(agente_id: str, instrumento_id: str) -> str:
        """Pendura um instrumento no cinto de um agente (ambos pelo `id`)."""
        agente = _agente(agente_id)
        if agente is None:
            return _erro(f"Não há agente com id {agente_id} neste time.")
        inst = _instrumento(instrumento_id)
        if inst is None:
            return _erro(f"Não há instrumento com id {instrumento_id} neste time.")
        try:
            servicos.encaixar(sess, agente, inst)
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok(f"Instrumento encaixado no cinto de '{agente.nome}'.")

    def desencaixar_instrumento(agente_id: str, instrumento_id: str) -> str:
        """Tira um instrumento do cinto de um agente (ambos pelo `id`)."""
        agente = _agente(agente_id)
        if agente is None:
            return _erro(f"Não há agente com id {agente_id} neste time.")
        iid = _uuid(instrumento_id)
        servicos.desencaixar(sess, agente.id, iid) if iid else None
        return _ok("Instrumento tirado do cinto.")

    def montar_cadeia(cadeia: dict, automacao_id: str | None = None) -> str:
        """Define a cadeia (o fluxo) de UMA automação como um GRAFO de nós:
        {"inicial": "<id do nó inicial>", "nos": [
          {"id": "<id do nó>", "tipo": "agente", "ref": "<id do agente>",
           "saidas": [
             {"rotulo": "rótulo curto da decisão", "quando": "quando seguir por aqui",
              "destino": "<id de outro nó, ou \\"fim\\" para encerrar>"}]},
          ...
        ]}.
        Regras: cada nó-agente tem `ref` = id do agente (o MESMO agente pode aparecer
        em vários nós, com `id` diferentes). `destino` aponta para o `id` de outro nó
        (pode ser um nó anterior = LOOP) ou "fim" para encerrar. Não precisa informar
        posições, nem criar os nós "gatilho"/"fim" — o sistema completa.

        EXECUÇÕES JÁ DISPARADAS NÃO MUDAM: cada uma roda o desenho fotografado no
        disparo, inclusive ao retomar uma aprovação em aberto. O que você montar aqui
        vale da PRÓXIMA execução em diante — não conserta nem quebra uma execução que
        já está no meio do caminho.

        BIFURCAÇÃO (mais de uma saída no nó) — leia com atenção:
        - O "quando" é OBRIGATÓRIO em cada saída quando o nó tem 2+ saídas
          condicionais. É a frase que o agente lê para decidir ("siga por aqui
          quando a pessoa aprovar a capa"). Sem ela a cadeia é RECUSADA.
        - O fluxo segue TODAS as saídas cuja condição for atendida, não só uma. Duas
          saídas com a MESMA condição e destinos diferentes = os dois destinos rodam.
          É assim que se desenha "aprovou → faz o carrossel E o story".
        - Cada saída pode declarar um "tipo": "condicional" (padrão),
          "erro" (percorrida SÓ se o passo falhar — o fluxo segue por ela levando a
          mensagem do erro, em vez de a automação morrer) ou "senao" (rede de
          segurança: só roda se nenhuma condicional for atendida). As saídas "erro" e
          "senao" NÃO levam "quando".
        - Se nenhuma condição for atendida e não houver saída "senao", aquele ramo
          termina ali, com o motivo gravado no rastro.

        REGRA EXATA (opcional, numa saída condicional):
        "regra": {"campo": "total", "operador": "entre", "valor": "1", "valor2": "10"}.
        Quando existe, quem confere é o MOTOR contra a ficha da execução — não a IA.
        Operadores: igual, diferente, contem, nao_contem, maior, maior_ou_igual, menor,
        menor_ou_igual, entre (inclusivo), preenchido, vazio. Use para decisão numérica
        ou de correspondência exata, onde um modelo erra a borda; deixe com o agente o
        que for julgamento. O `campo` precisa ser algo que algum passo ANTERIOR guarde
        na ficha com `anotar` (ou "entrada", o que o gatilho trouxe).

        NÓ "PARA CADA ITEM":
        {"id": "...", "tipo": "cada", "lista": "<campo da ficha>",
         "item_em": "item", "acumular_em": "<campo, opcional>", "saidas": [...]}.
        Lê uma lista da ficha e repete o trecho seguinte UMA VEZ POR ITEM, cada
        repetição como caminho próprio. Não roda IA. Teto de 20 itens.

        APROVAÇÃO HUMANA: não existe portão no desenho. Quem para o fluxo é o AGENTE,
        chamando o instrumento `pedir_aprovacao` porque o markdown dele manda — então
        dê o instrumento ao agente e escreva a regra no skill_md dele. Um nó pode
        trazer "config": {...} para ajustar SÓ nele regras do Tipo de fluxo (ex.:
        {"timeout_min": 30}); opcional, sem isso valem os padrões.

        Se o time tem MAIS DE UMA automação, informe `automacao_id` (pegue no retrato,
        em `automacoes`); com uma só, pode omitir. NÃO adivinhe qual — se estiver na
        dúvida, pergunte ao consultor."""
        time = _exigir_time()
        if time is None:
            return _erro("Defina o time primeiro, com definir_time.")
        try:
            servicos.definir_cadeia(
                sess, time, cadeia, automacao_id=automacao_id, usuario=ctx.usuario
            )
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok("Cadeia montada.")

    def definir_gatilho(
        tipo_gatilho: str, configuracao_gatilho: dict | None = None,
        automacao_id: str | None = None,
    ) -> str:
        """Define o gatilho de UMA automação. Tipos e formato EXATO:
        - 'manual': sem config (o consultor dispara quando quiser).
        - 'webhook': sem config (uma chamada externa dispara).
        - 'agendamento': config = {frequencia: 'diaria'|'semanal'|'mensal',
          hora: 0-23, minuto: 0-59, dia_semana: 0-6 (0=segunda, só semanal),
          dia_mes: 1-31 (só mensal), entrada?: texto}. Use INTEIROS.
        Se o time tem mais de uma automação, informe `automacao_id` (do retrato); com
        uma só, pode omitir."""
        time = _exigir_time()
        if time is None:
            return _erro("Defina o time primeiro, com definir_time.")
        config = configuracao_gatilho or {}
        erro = _validar_gatilho(tipo_gatilho, config)
        if erro:
            return _erro(erro)
        try:
            servicos.definir_gatilho(
                sess, time, tipo_gatilho=tipo_gatilho, configuracao_gatilho=config,
                automacao_id=automacao_id, usuario=ctx.usuario,
            )
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok(f"Gatilho '{tipo_gatilho}' definido.")

    def estimar_custo(
        execucoes_por_mes: int, tokens_entrada_por_execucao: int,
        tokens_saida_por_execucao: int, modelo: str | None = None,
    ) -> str:
        """Estima o custo do time, em dólares, por execução e por mês. Informe sua
        estimativa de tokens de entrada e de saída por execução (somando a cadeia) e
        quantas execuções por mês. O `modelo` padrão é o do líder. Só calcula e
        informa — não grava nada."""
        time = _exigir_time()
        if time is None:
            return _erro("Defina o time primeiro, com definir_time.")
        if modelo is None:
            lider = sess.scalars(
                select(Agente).where(Agente.time_id == time.id, Agente.papel == "lider")
            ).first()
            modelo = (lider.modelo_ia if lider else None) or MODELO_PADRAO
        por_execucao = precos.custo_usd(
            modelo, tokens_entrada_por_execucao, tokens_saida_por_execucao
        )
        return _ok(
            "Custo estimado.",
            por_execucao_usd=round(por_execucao, 4),
            por_mes_usd=round(por_execucao * execucoes_por_mes, 2),
        )

    def criar_automacao(nome: str) -> str:
        """Cria uma automação NOVA (vazia, desligada) no time — para o time ter MAIS DE
        UMA. Dê um NOME claro (ex.: 'Postar no Instagram', 'Responder comentários') para
        distinguir. Não mexe nas outras. Depois monte a cadeia/gatilho passando o
        `automacao_id` desta (o id volta aqui)."""
        time = _exigir_time()
        if time is None:
            return _erro("Defina o time primeiro, com definir_time.")
        try:
            auto = servicos.criar_automacao(sess, time, nome=nome, usuario=ctx.usuario)
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok(f"Automação '{auto.nome}' criada.", id=str(auto.id))

    def renomear_automacao(automacao_id: str, nome: str) -> str:
        """Renomeia uma automação do time (pegue o `id` no retrato, em `automacoes`).
        Útil para dar nomes claros quando há várias."""
        time = _exigir_time()
        if time is None:
            return _erro("Defina o time primeiro, com definir_time.")
        try:
            auto = servicos.renomear_automacao(
                sess, time, automacao_id=automacao_id, nome=nome, usuario=ctx.usuario
            )
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok(f"Automação renomeada para '{auto.nome}'.", id=str(auto.id))

    def ativar_time(automacao_id: str | None = None) -> str:
        """LIGA UMA automação do time (passa a poder disparar). Se o time tem mais de
        uma automação, informe `automacao_id` (do retrato, em `automacoes`); com uma só,
        pode omitir. A PAREDE: se algum agente com instrumento de ação irreversível
        (publicar/enviar/gravar) não tiver portão de aprovação humana antes na cadeia, a
        ativação é RECUSADA com a explicação — ajuste a cadeia e tente de novo."""
        time = _exigir_time()
        if time is None:
            return _erro("Defina o time primeiro, com definir_time.")
        try:
            auto = servicos.resolver_automacao(
                sess, time, automacao_id, permitir_criar=False
            )
            servicos.ativar(sess, auto, usuario=ctx.usuario)
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok(f"Automação '{auto.nome}' ativada (ligada).")

    def desativar_time(automacao_id: str | None = None) -> str:
        """DESLIGA UMA automação do time (para de disparar). Se há mais de uma, informe
        `automacao_id`. Use para pausar ou ajustar com calma; religa com ativar_time."""
        time = _exigir_time()
        if time is None:
            return _erro("Defina o time primeiro, com definir_time.")
        try:
            auto = servicos.resolver_automacao(
                sess, time, automacao_id, permitir_criar=False
            )
            servicos.desativar(sess, auto, usuario=ctx.usuario)
        except ConflitoDominio as e:
            return _erro(str(e))
        return _ok(f"Automação '{auto.nome}' desativada (desligada).")

    def ver_time() -> str:
        """Mostra o time REAL inteiro (agentes com seus textos e cinto, instrumentos,
        automação, se está ativa) — para você se situar e conferir os `id`s."""
        if ctx.time() is None:
            return _ok("Ainda não há time. Comece com definir_time.", time=None)
        return json.dumps(_snapshot_time(ctx), ensure_ascii=False)

    def ver_agente(agente_id: str) -> str:
        """Mostra os TEXTOS completos de um agente (os 4 markdowns: agent_md/skill_md/
        tools_md/soul_md), o modelo e o cinto. A foto do time no seu contexto traz só a
        ESTRUTURA (nome, papel, id, cinto) para economizar tokens — chame isto quando
        precisar LER ou EDITAR o conteúdo de um agente específico (ex.: antes de ajustar
        o skill_md, veja o que já está escrito)."""
        agente = _agente(agente_id)
        if agente is None:
            return _erro(f"Não há agente com id {agente_id} neste time.")
        cinto = [
            str(iid)
            for (iid,) in sess.execute(
                select(AgenteInstrumento.instrumento_id).where(
                    AgenteInstrumento.agente_id == agente.id
                )
            ).all()
        ]
        return json.dumps(
            {
                "id": str(agente.id), "nome": agente.nome, "papel": agente.papel,
                "modelo_ia": agente.modelo_ia,
                "agent_md": agente.agent_md, "skill_md": agente.skill_md,
                "tools_md": agente.tools_md, "soul_md": agente.soul_md,
                "cinto": cinto,
            },
            ensure_ascii=False,
        )

    def ver_automacao(automacao_id: str) -> str:
        """Mostra a CADEIA completa (o fluxo/grafo de nós) de uma automação, com o
        gatilho e se está ativa. A foto do time no seu contexto traz só nome/gatilho/
        ativa/id de cada automação para economizar tokens — chame isto quando precisar
        LER ou EDITAR o fluxo de uma automação específica."""
        aid = _uuid(automacao_id)
        auto = sess.get(Automacao, aid) if aid else None
        if auto is None or auto.time_id != ctx.conversa.time_id:
            return _erro(f"Não há automação com id {automacao_id} neste time.")
        return json.dumps(
            {
                "id": str(auto.id), "nome": auto.nome, "tipo_gatilho": auto.tipo_gatilho,
                "configuracao_gatilho": auto.configuracao_gatilho,
                "cadeia": grafo.normalizar(auto.cadeia or {}),
                "ativa": auto.ativa,
            },
            ensure_ascii=False,
        )

    def listar_tipos_instrumento() -> str:
        """Lista os tipos de instrumento disponíveis, com o que cada um faz, os
        CAMPOS de configuração (obrigatório/secreto) e se a ação é irreversível.
        Use para saber o que PERGUNTAR ao consultor (públicos você coleta; secretos
        ele cadastra no cofre) e o que precisa de portão de aprovação."""
        return json.dumps(catalogo_de_instrumentos(), ensure_ascii=False)

    def sugerir_proximos_passos(chips: list[str]) -> str:
        """Sugere de 1 a 4 respostas curtas que o consultor pode escolher para seguir
        a conversa (os 'chips'). Chame ao fim de cada turno."""
        ctx.chips = list(chips)[:4]
        return _ok("Sugestões registradas.")

    def atualizar_resumo(resumo: str) -> str:
        """Escreve o RESUMO DO PROJETO — o que aparece no painel 'Sobre este time': a
        síntese viva do que este time É e FAZ, das decisões tomadas, das preferências do
        consultor e das pontas em aberto. É DIFERENTE da descrição do time (definir_time,
        o texto público curto) e da memória de longo prazo (lembrar, fatos avulsos): o
        resumo é a síntese corrida de todo o projeto. Chame quando o consultor pedir para
        atualizar/editar o resumo do projeto, ou quando algo importante for decidido/mudar.
        Escreva em português, em tópicos curtos; o texto SUBSTITUI o resumo atual (o
        consultor pode corrigir por cima, no painel)."""
        ctx.conversa.resumo = (resumo or "").strip() or None
        return _ok("Resumo do projeto atualizado.")

    def lembrar(categoria: str, conteudo: str) -> str:
        """Guarda na MEMÓRIA de longo prazo deste projeto algo que você deve lembrar
        nas próximas conversas. Use para fatos do cliente, decisões tomadas com o
        consultor e preferências dele (tom, forma, restrições) — não para detalhes
        triviais nem para o que já está no time (isso você vê com ver_time).
        `categoria` é 'fato', 'decisao' ou 'preferencia'. Escreva `conteudo` curto e
        autossuficiente (ex.: 'O público do blog é o decisor, não o analista')."""
        memoria.lembrar(sess, ctx.conversa, categoria=categoria, conteudo=conteudo)
        return _ok("Memória guardada.")

    def recordar(busca: str | None = None) -> str:
        """Lembra o que você já sabe deste projeto (a memória de longo prazo). Sem
        `busca`, devolve as memórias mais recentes; com `busca`, filtra por uma
        palavra/trecho. As memórias recentes já vêm no seu contexto — use isto para
        buscar algo específico ou conferir o id de uma memória antes de esquecê-la."""
        itens = [
            memoria.serializar(m)
            for m in memoria.listar(sess, ctx.conversa, busca=busca)
        ]
        return json.dumps({"ok": True, "memorias": itens}, ensure_ascii=False)

    def buscar_no_historico(consulta: str) -> str:
        """Procura nos turnos ANTIGOS desta conversa (os que já saíram da janela recente e
        foram dobrados no resumo) por uma palavra ou trecho, e devolve os que casarem —
        no texto original. Use quando o consultor mencionar algo que vocês combinaram HÁ
        MUITO e que talvez não esteja no resumo (ex.: 'procura no histórico o que ficou
        decidido sobre X'). O resumo é uma síntese; isto recupera o detalhe antigo. Os
        turnos RECENTES já estão no seu contexto — esta busca é só para o que ficou para
        trás. Nada é apagado: o histórico completo fica guardado."""
        termo = (consulta or "").strip().lower()
        if not termo:
            return _erro("Diga o que procurar no histórico (uma palavra ou um trecho).")
        msgs = ctx.conversa.mensagens or []
        ate = ctx.conversa.resumo_ate or 0
        achados = []
        for m in msgs[:ate]:  # só os turnos já dobrados (o recente já está no contexto)
            conteudo = m.get("conteudo") or ""
            if termo in conteudo.lower():
                papel = "Consultor" if m.get("papel") == "usuario" else "Você"
                achados.append(
                    {"papel": papel, "conteudo": conteudo[:_MAX_CHARS_ACHADO]}
                )
        if not achados:
            return _ok(
                f"Nada nos turnos antigos casou com '{consulta}'. Pode estar no resumo "
                "(já no seu contexto) ou nos turnos recentes.",
                achados=[],
            )
        # Teto: os mais recentes entre os que casaram (economia — não despeja tudo).
        achados = achados[-_MAX_ACHADOS_HISTORICO:]
        return _ok(
            f"{len(achados)} trecho(s) antigo(s) casaram com '{consulta}'.",
            achados=achados,
        )

    def esquecer(memoria_id: str) -> str:
        """Apaga uma memória de longo prazo que ficou ERRADA ou que o consultor mudou
        (ex.: ele revisou uma decisão). Pegue o `id` com recordar. Não apague memória
        ainda válida."""
        mid = _uuid(memoria_id)
        if mid and memoria.esquecer(sess, ctx.conversa, mid):
            return _ok("Memória apagada.")
        return _erro(f"Não há memória com id {memoria_id} neste projeto.")

    def ver_memoria_agente(agente_id: str) -> str:
        """Mostra as MEMÓRIAS que um agente aprendeu com o próprio trabalho (fichas por
        assunto — ex.: sobre um cliente, decisões, preferências). É LEITURA: use para
        SUPERVISIONAR e EXPLICAR ao consultor o que o agente já sabe. Para EDITAR ou
        APAGAR uma ficha, você NÃO faz aqui — oriente o consultor a abrir o agente na
        tela (aba Agentes → o agente → seção Memórias). Pegue o `agente_id` no ver_time."""
        ag = _agente(agente_id)
        if ag is None:
            return _erro(f"Não encontrei o agente {agente_id} neste time.")
        if not ag.memoria_ativa:
            return _ok(
                f"O agente '{ag.nome}' está com a memória desligada.", memorias=[]
            )
        fichas = memoria_agente.pesquisar(sess, ag.id)
        return _ok(
            f"{len(fichas)} ficha(s) na memória de '{ag.nome}'.", memorias=fichas
        )

    def listar_execucoes(
        automacao_id: str | None = None, apenas_problemas: bool = False,
        limite: int = 10,
    ) -> str:
        """Lista as execuções recentes deste time, para você ACHAR a que o consultor
        relata como problema. Devolve, por execução, o `execucao_id`, a automação, o
        estado, quando rodou e um resumo curto. Filtre por uma automação
        (`automacao_id`) e/ou só as com problema (`apenas_problemas=true`: falhou,
        parada esperando humano, presa ou na fila). Use isto ANTES de diagnosticar
        quando o consultor não der o id da execução."""
        if ctx.conversa.time_id is None:
            return _erro("Este projeto ainda não tem time, então não há execuções.")
        aid = _uuid(automacao_id) if automacao_id else None
        if automacao_id and aid is None:
            return _erro(f"Id de automação inválido: {automacao_id}.")
        q = (
            select(Execucao, Automacao.nome)
            .join(Automacao, Automacao.id == Execucao.automacao_id)
            .where(Automacao.time_id == ctx.conversa.time_id)
        )
        if aid is not None:
            q = q.where(Execucao.automacao_id == aid)
        if apenas_problemas:
            q = q.where(Execucao.estado.in_(_ESTADOS_PROBLEMA))
        q = q.order_by(Execucao.criado_em.desc()).limit(max(1, min(int(limite or 10), 30)))
        itens = [
            {
                "execucao_id": str(ex.id),
                "automacao": nome,
                "estado": ex.estado,
                "quando": ex.criado_em.isoformat() if ex.criado_em else None,
                "resumo": diagnostico_execucao.resumo_estado(ex.estado, ex.resultado),
            }
            for ex, nome in sess.execute(q).all()
        ]
        return _ok(f"{len(itens)} execução(ões) encontrada(s).", execucoes=itens)

    def diagnosticar_execucao(execucao_id: str | None = None) -> str:
        """Investiga UMA execução a fundo e devolve o diagnóstico para você EXPLICAR
        ao consultor por que ela falhou ou ficou parada. Sem `execucao_id`, pega a
        execução com problema mais recente deste time. LIDERE pelos `avisos` (cada um
        traz `titulo`, `detalhe` e `acao_sugerida`): traduza em linguagem simples,
        conte a história na ordem (o que iniciou, rodou, onde parou e por quê) e
        proponha o próximo passo. Se `webhook_alvo` vier preenchido, continue a
        história nele — o webhook iniciou outra automação. Nunca exponha segredos (o
        diagnóstico só diz se um canal 'tem token', nunca o valor)."""
        if ctx.conversa.time_id is None:
            return _erro("Este projeto ainda não tem time, então não há execuções.")
        if execucao_id:
            eid = _uuid(execucao_id)
            if eid is None:
                return _erro(f"Id de execução inválido: {execucao_id}.")
            ex = sess.get(Execucao, eid)
            if ex is None or not _execucao_do_time(ex):
                return _erro(f"Não encontrei a execução {execucao_id} neste time.")
        else:
            ex = sess.scalars(
                select(Execucao)
                .join(Automacao, Automacao.id == Execucao.automacao_id)
                .where(Automacao.time_id == ctx.conversa.time_id)
                .where(Execucao.estado.in_(_ESTADOS_PROBLEMA))
                .order_by(Execucao.criado_em.desc())
            ).first()
            if ex is None:
                return _ok(
                    "Nenhuma execução com problema neste time agora.", diagnostico=None
                )
        diag = diagnostico_execucao.diagnosticar(sess, ex.id)
        return _ok("Diagnóstico pronto.", diagnostico=diag)

    def consultar_conhecimento(topico: str) -> str:
        """Consulta a Central de Conhecimento do Batuta — o manual dos recursos
        (instrumentos, automações, gatilhos, portão de aprovação, chaves, credenciais,
        mensageria/Telegram, memória do agente, etc.). USE quando não souber COMO um
        recurso funciona ou COMO orientar o consultor sobre ele — em vez de adivinhar de
        memória. Devolve os capítulos mais relevantes ao `topico`; cada um traz uma seção
        'Para a IA' com as regras operacionais e como orientar o usuário."""
        import conhecimento

        achados = conhecimento.buscar(topico, limite=3)
        if not achados:
            return _ok(
                "Nada encontrado na Central para esse tópico. Responda pelo que já sabe, "
                "com honestidade — não invente regras.",
                capitulos=[],
            )
        return _ok(
            "Capítulos da Central encontrados.",
            capitulos=[
                {"titulo": c.titulo, "slug": c.slug, "conteudo": c.corpo}
                for c in achados
            ],
        )

    funcoes = [
        definir_time, adicionar_agente, editar_agente, remover_agente,
        configurar_instrumento, editar_instrumento, montar_conector,
        testar_operacao_conector, encaixar_instrumento,
        desencaixar_instrumento, criar_automacao, renomear_automacao,
        montar_cadeia, definir_gatilho, estimar_custo,
        ativar_time, desativar_time, ver_time, ver_agente, ver_automacao,
        listar_tipos_instrumento,
        listar_execucoes, diagnosticar_execucao, ver_memoria_agente,
        sugerir_proximos_passos, atualizar_resumo, lembrar, recordar, esquecer,
        consultar_conhecimento, buscar_no_historico,
    ]

    # O react agent do LangGraph roda as ferramentas de UM turno EM PARALELO (pool de
    # threads). Como todas mexem na MESMA sessão do banco (não thread-safe), dois
    # flush() concorrentes quebram com "Session is already flushing". Serializamos as
    # chamadas com uma trava por turno — elas continuam todas rodando, uma de cada vez.
    trava = threading.Lock()

    def _serial(f):
        # Feedback ao vivo: antes de rodar a ferramenta, publica 'o que a IA faz agora'.
        # NO-OP fora de um bloco `usar_atividade` (testes chamam a ferramenta direto).
        frase = MENSAGENS_CRIADORA.get(f.__name__, "Trabalhando no time…")

        @functools.wraps(f)  # preserva nome/assinatura (StructuredTool infere o schema)
        def wrapper(*args, **kwargs):
            atividade.registrar(frase)
            with trava:
                return f(*args, **kwargs)
        return wrapper

    return [
        StructuredTool.from_function(func=_serial(f), name=f.__name__, description=f.__doc__)
        for f in funcoes
    ]


def ferramenta_por_nome(ctx: ContextoCriacao) -> dict[str, StructuredTool]:
    """Conveniência para os testes: as ferramentas indexadas por nome."""
    return {t.name: t for t in montar_ferramentas(ctx)}
