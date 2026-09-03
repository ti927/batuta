"""Serviços de domínio: a porta ÚNICA e validada que escreve no TIME REAL.

No paradigma de conversa eterna, a IA criadora opera sobre as linhas reais
(Time/Agente/Instrumento/cinto/Automacao) desde o começo — não mais sobre um
rascunho JSON. Estas funções concentram a regra (líder único, validação de
config/cadeia, limpeza de referências) num só lugar, para a IA e as rotas REST
escreverem pela MESMA porta.

Transação: estas funções NÃO fazem commit — fazem `flush` para o id existir e as
leituras seguintes enxergarem. Quem chama controla a transação (a rota commita por
requisição; o laço da IA commita ao fim do turno). Erros de regra de negócio viram
`ConflitoDominio` (o chamador traduz para 409/texto).

Segurança (parede de ativação): `ativar` exige portão humano antes de agente com
ação irreversível — ver `portao_ativacao`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

import auditoria
import instrumentos as encaixe
import segredos_instrumento as segredos
from mensageria.config import PERFIL_PADRAO
from modelos import Agente, AgenteInstrumento, Automacao, Instrumento, Time, Usuario
from orquestracao import grafo
from orquestracao.cadeia import validar_cadeia


class ConflitoDominio(Exception):
    """Uma regra de negócio impediu a operação (líder duplicado, cadeia inválida,
    instrumento de outro time, etc.). Mensagem em português, pronta para o humano."""


def _audit(sessao, usuario, acao, recurso_tipo, recurso_id, organizacao_id, **detalhe):
    auditoria.registrar(
        sessao, usuario=usuario, acao=acao, recurso_tipo=recurso_tipo,
        recurso_id=recurso_id, organizacao_id=organizacao_id,
        detalhe=detalhe or None,
    )


# ─────────────────────────────── Time ───────────────────────────────

def criar_time(
    sessao: Session, organizacao_id: uuid.UUID, nome: str,
    descricao: str | None = None, *, usuario: Usuario | None = None,
) -> Time:
    time = Time(organizacao_id=organizacao_id, nome=nome, descricao=descricao)
    sessao.add(time)
    sessao.flush()
    _audit(sessao, usuario, "time.criado", "time", time.id, organizacao_id)
    return time


def editar_time(
    sessao: Session, time: Time, *, nome: str | None = None,
    descricao: str | None = None,
) -> Time:
    if nome is not None:
        time.nome = nome
    if descricao is not None:
        time.descricao = descricao
    sessao.flush()
    return time


# ────────────────────────────── Agente ──────────────────────────────

def _tem_lider(sessao: Session, time_id: uuid.UUID, ignorar: uuid.UUID | None = None) -> bool:
    consulta = select(Agente.id).where(Agente.time_id == time_id, Agente.papel == "lider")
    if ignorar is not None:
        consulta = consulta.where(Agente.id != ignorar)
    return sessao.scalars(consulta).first() is not None


def adicionar_agente(
    sessao: Session, time: Time, *, nome: str, papel: str = "agente",
    agent_md: str | None = None, skill_md: str | None = None,
    tools_md: str | None = None, soul_md: str | None = None,
    modelo_ia: str | None = None, usuario: Usuario | None = None,
) -> Agente:
    if papel not in ("lider", "agente"):
        raise ConflitoDominio("O papel precisa ser 'lider' ou 'agente'.")
    if papel == "lider" and _tem_lider(sessao, time.id):
        raise ConflitoDominio("Este time já tem um Líder. Cada time pode ter apenas um.")
    agente = Agente(
        time_id=time.id, nome=nome, papel=papel, agent_md=agent_md, skill_md=skill_md,
        tools_md=tools_md, soul_md=soul_md, modelo_ia=modelo_ia,
    )
    sessao.add(agente)
    sessao.flush()
    _audit(sessao, usuario, "agente.criado", "agente", agente.id, time.organizacao_id)
    return agente


def editar_agente(
    sessao: Session, agente: Agente, *, usuario: Usuario | None = None, **campos
) -> Agente:
    """Atualiza só os campos passados (não-None). Valida líder único se o papel mudar."""
    if campos.get("papel") == "lider" and _tem_lider(sessao, agente.time_id, ignorar=agente.id):
        raise ConflitoDominio("Este time já tem um Líder. Cada time pode ter apenas um.")
    permitidos = ("nome", "papel", "agent_md", "skill_md", "tools_md", "soul_md", "modelo_ia")
    md = ("agent_md", "skill_md", "tools_md", "soul_md")
    md_alterados = [
        c for c in md if c in campos and campos[c] is not None and getattr(agente, c) != campos[c]
    ]
    for campo in permitidos:
        if campo in campos and campos[campo] is not None:
            setattr(agente, campo, campos[campo])
    sessao.flush()
    if md_alterados:
        _audit(
            sessao, usuario, "agente.markdown_alterado", "agente", agente.id,
            auditoria.org_do_time(sessao, agente.time_id), campos=md_alterados,
        )
    return agente


def remover_agente(sessao: Session, agente: Agente, *, usuario: Usuario | None = None) -> None:
    org_id = auditoria.org_do_time(sessao, agente.time_id)
    _limpar_agente_das_cadeias(sessao, agente.time_id, str(agente.id))
    _audit(sessao, usuario, "agente.removido", "agente", agente.id, org_id)
    sessao.delete(agente)
    sessao.flush()


def _limpar_agente_das_cadeias(sessao: Session, time_id: uuid.UUID, agente_id: str) -> None:
    """Tira um agente removido das cadeias das automações do time: apaga TODO nó cujo
    `ref` é esse agente (ele pode aparecer em vários nós), as saídas que apontavam
    para esses nós, e reconcilia o inicial/gatilho (evita cadeia órfã). Grava no
    formato canônico de grafo."""
    autos = sessao.scalars(select(Automacao).where(Automacao.time_id == time_id)).all()
    for auto in autos:
        cadeia = grafo.normalizar(auto.cadeia or {})
        nos = cadeia.get("nos") or []
        ids_remover = {
            n["id"] for n in nos
            if n.get("tipo") == "agente" and str(n.get("ref")) == agente_id
        }
        if not ids_remover:
            continue
        nos = [n for n in nos if n["id"] not in ids_remover]
        # Se não sobra agente, a cadeia volta a rascunho vazio.
        if not any(n.get("tipo") == "agente" for n in nos):
            auto.cadeia = {}
            continue
        inicial = cadeia.get("inicial")
        if inicial in ids_remover:
            inicial = next((n["id"] for n in nos if n.get("tipo") == "agente"), None)
        for n in nos:
            n["saidas"] = [
                s for s in (n.get("saidas") or []) if s.get("destino") not in ids_remover
            ]
            # o gatilho passa a apontar para o novo inicial
            if n.get("tipo") == "gatilho" and inicial:
                base = n["saidas"][0] if n["saidas"] else {"rotulo": "inicia o fluxo"}
                n["saidas"] = [{**base, "destino": inicial}]
        # reatribui (o ORM detecta a troca do JSONB), renormalizando para reconciliar.
        auto.cadeia = grafo.normalizar({"inicial": inicial, "nos": nos})


# ──────────────────────────── Instrumento ───────────────────────────

def configurar_instrumento(
    sessao: Session, time: Time, *, nome: str, tipo: str, configuracao: dict | None = None,
    usuario: Usuario | None = None,
) -> tuple[Instrumento, list[str]]:
    """Cria um instrumento, separando os segredos (cifrados no cofre) da config
    pública. Devolve `(instrumento, segredos_pendentes)` — os pendentes são campos
    secretos que o consultor ainda precisa preencher no cofre."""
    try:
        config_publica, segredos_novos = encaixe.preparar_config(tipo, configuracao or {})
    except ValueError as e:
        raise ConflitoDominio(str(e))
    inst = Instrumento(time_id=time.id, nome=nome, tipo=tipo, configuracao=config_publica)
    sessao.add(inst)
    sessao.flush()
    if segredos_novos:
        segredos.salvar_segredos(sessao, inst.id, segredos_novos)
    _audit(sessao, usuario, "instrumento.criado", "instrumento", inst.id, time.organizacao_id)
    # Pendentes = só os segredos que NENHUMA fonte cobre. Recém-criado pela IA não
    # tem credencial apontada; a chave compartilhada (Tavily/OpenAI) já vem do pool.
    pendentes = segredos.pendentes(
        tipo,
        guardados=set(segredos_novos),
        servicos_resolviveis=segredos.servicos_resolviveis(sessao, time.organizacao_id),
    )
    return inst, pendentes


def editar_instrumento(
    sessao: Session, inst: Instrumento, *, nome: str | None = None,
    configuracao: dict | None = None, usuario: Usuario | None = None,
) -> Instrumento:
    if nome is not None:
        inst.nome = nome
    if configuracao is not None:
        try:
            config_publica, segredos_novos = encaixe.preparar_config(inst.tipo, configuracao)
        except ValueError as e:
            raise ConflitoDominio(str(e))
        inst.configuracao = config_publica
        if segredos_novos:
            segredos.salvar_segredos(sessao, inst.id, segredos_novos)
    sessao.flush()
    return inst


# ─────────────────────────────── Cinto ──────────────────────────────

def encaixar(sessao: Session, agente: Agente, instrumento: Instrumento) -> None:
    if instrumento.time_id != agente.time_id:
        raise ConflitoDominio("O instrumento é de outro time.")
    if sessao.get(AgenteInstrumento, (agente.id, instrumento.id)) is not None:
        return  # idempotente: já está no cinto
    sessao.add(AgenteInstrumento(agente_id=agente.id, instrumento_id=instrumento.id))
    sessao.flush()


def desencaixar(sessao: Session, agente_id: uuid.UUID, instrumento_id: uuid.UUID) -> None:
    vinculo = sessao.get(AgenteInstrumento, (agente_id, instrumento_id))
    if vinculo is not None:
        sessao.delete(vinculo)
        sessao.flush()


# ───────────────────────────── Automação ────────────────────────────

def _ids_agentes(sessao: Session, time_id: uuid.UUID) -> set[str]:
    return {
        str(i) for i in sessao.scalars(select(Agente.id).where(Agente.time_id == time_id)).all()
    }


def _obter_ou_criar_automacao(sessao: Session, time: Time) -> Automacao:
    """A automação única do time (no fluxo da IA). Cria uma inativa e vazia se não
    houver — gatilho 'manual', cadeia vazia, nome derivado do time."""
    auto = sessao.scalars(
        select(Automacao).where(Automacao.time_id == time.id).order_by(Automacao.criado_em)
    ).first()
    if auto is None:
        auto = Automacao(
            time_id=time.id, nome=f"Automação de {time.nome}", tipo_gatilho="manual",
            configuracao_gatilho={}, cadeia={}, ativa=False,
            configuracao={"perfil": PERFIL_PADRAO},  # nasce com um tipo de fluxo sensato
        )
        sessao.add(auto)
        sessao.flush()
    return auto


def resolver_automacao(
    sessao: Session, time: Time, automacao_id: "uuid.UUID | str | None" = None,
    *, permitir_criar: bool = True,
) -> Automacao:
    """FONTE ÚNICA de "qual automação" a IA vai editar (um time pode ter N):
    - com `automacao_id`: a automação daquele id (recusa se não for deste time);
    - sem id e só UMA automação: essa;
    - sem id e NENHUMA: cria a primeira se `permitir_criar` (conveniência de montar a
      primeira); senão recusa (ex.: ativar não deve criar automação vazia);
    - sem id e VÁRIAS: recusa com `ConflitoDominio` listando nome+id — a IA deve
      PERGUNTAR ao consultor em qual mexer (não adivinha)."""
    autos = sessao.scalars(
        select(Automacao).where(Automacao.time_id == time.id).order_by(Automacao.criado_em)
    ).all()
    if automacao_id is not None:
        try:
            aid = (
                automacao_id if isinstance(automacao_id, uuid.UUID)
                else uuid.UUID(str(automacao_id))
            )
        except (ValueError, AttributeError, TypeError):
            raise ConflitoDominio(f"Id de automação inválido: {automacao_id}.")
        alvo = next((a for a in autos if a.id == aid), None)
        if alvo is None:
            raise ConflitoDominio(f"Não há automação com id {automacao_id} neste time.")
        return alvo
    if len(autos) == 1:
        return autos[0]
    if not autos:
        if permitir_criar:
            return _obter_ou_criar_automacao(sessao, time)
        raise ConflitoDominio("Monte a automação primeiro (cadeia e gatilho).")
    lista = "; ".join(f"'{a.nome}' (id {a.id})" for a in autos)
    raise ConflitoDominio(
        f"Este time tem {len(autos)} automações — diga em qual mexer (passe automacao_id). "
        f"As automações são: {lista}."
    )


def criar_automacao(
    sessao: Session, time: Time, *, nome: str, usuario: Usuario | None = None
) -> Automacao:
    """Cria uma automação NOVA (inativa, gatilho 'manual', cadeia vazia) — para o time
    ter MAIS DE UMA. Nasce com o tipo de fluxo padrão ('interno'). Não mexe nas outras."""
    nome = (nome or "").strip() or f"Automação de {time.nome}"
    auto = Automacao(
        time_id=time.id, nome=nome, tipo_gatilho="manual",
        configuracao_gatilho={}, cadeia={}, ativa=False,
        configuracao={"perfil": PERFIL_PADRAO},
    )
    sessao.add(auto)
    sessao.flush()
    _audit(sessao, usuario, "automacao.criada", "automacao", auto.id, time.organizacao_id)
    return auto


def renomear_automacao(
    sessao: Session, time: Time, *, automacao_id: "uuid.UUID | str", nome: str,
    usuario: Usuario | None = None,
) -> Automacao:
    """Renomeia uma automação do time (para distinguir quando há várias)."""
    auto = resolver_automacao(sessao, time, automacao_id)
    novo = (nome or "").strip()
    if not novo:
        raise ConflitoDominio("O nome da automação não pode ser vazio.")
    auto.nome = novo
    sessao.flush()
    _audit(sessao, usuario, "automacao.renomeada", "automacao", auto.id, time.organizacao_id)
    return auto


def definir_cadeia(
    sessao: Session, time: Time, cadeia: dict, *,
    automacao_id: "uuid.UUID | str | None" = None, usuario: Usuario | None = None,
) -> Automacao:
    """Define a CADEIA de UMA automação do time, validando contra os agentes reais.
    `automacao_id` escolhe qual (via `resolver_automacao`); mantém gatilho e nome. Se
    ativar uma cadeia que tira o portão de um agente irreversível, a ativação (à parte)
    é que vai recusar."""
    try:
        validar_cadeia(cadeia or {}, _ids_agentes(sessao, time.id))
    except ValueError as e:
        raise ConflitoDominio(f"Cadeia inválida: {e}")
    auto = resolver_automacao(sessao, time, automacao_id)
    # A cadeia que chega normalmente NÃO traz o nó `gatilho` (quem monta descreve só os
    # nós de agente) — a normalização então cria um com o default "manual". Sem espelhar
    # o gatilho REAL da automação aqui, remontar a cadeia apagava o gatilho do grafo:
    # o topo dizia "webhook" e a tela mostrava "manual". Fonte única com `definir_gatilho`.
    auto.cadeia = grafo.sincronizar_gatilho(
        grafo.normalizar(cadeia or {}), auto.tipo_gatilho
    )
    flag_modified(auto, "cadeia")
    sessao.flush()
    _audit(sessao, usuario, "automacao.definida", "automacao", auto.id, time.organizacao_id)
    return auto


def definir_gatilho(
    sessao: Session, time: Time, *, tipo_gatilho: str,
    configuracao_gatilho: dict | None = None,
    automacao_id: "uuid.UUID | str | None" = None, usuario: Usuario | None = None,
) -> Automacao:
    """Define o GATILHO de UMA automação do time (`automacao_id` escolhe qual). Mantém
    a cadeia e o nome."""
    auto = resolver_automacao(sessao, time, automacao_id)
    auto.tipo_gatilho = tipo_gatilho
    auto.configuracao_gatilho = configuracao_gatilho or {}
    # O nó `gatilho` do grafo é projeção deste campo — sem espelhar aqui, a tela
    # continuava mostrando o gatilho antigo (duas fontes para o mesmo dado).
    auto.cadeia = grafo.sincronizar_gatilho(auto.cadeia, tipo_gatilho)
    flag_modified(auto, "cadeia")
    sessao.flush()
    _audit(sessao, usuario, "automacao.definida", "automacao", auto.id, time.organizacao_id)
    return auto


def definir_automacao(
    sessao: Session, time: Time, *, nome: str, tipo_gatilho: str,
    configuracao_gatilho: dict | None = None, cadeia: dict | None = None,
    usuario: Usuario | None = None,
) -> Automacao:
    """Cria OU atualiza a automação do time (no fluxo da IA, uma por time). Valida a
    cadeia contra os agentes reais. Nasce/segue INATIVA — ativar é passo à parte."""
    cadeia = cadeia or {}
    try:
        validar_cadeia(cadeia, _ids_agentes(sessao, time.id))
    except ValueError as e:
        raise ConflitoDominio(f"Cadeia inválida: {e}")
    cadeia = grafo.normalizar(cadeia)  # grava no formato canônico de grafo
    # O nó `gatilho` do grafo espelha o tipo (fonte única com o campo de topo).
    cadeia = grafo.sincronizar_gatilho(cadeia, tipo_gatilho)
    auto = sessao.scalars(
        select(Automacao).where(Automacao.time_id == time.id).order_by(Automacao.criado_em)
    ).first()
    if auto is None:
        auto = Automacao(
            time_id=time.id, nome=nome, tipo_gatilho=tipo_gatilho,
            configuracao_gatilho=configuracao_gatilho or {}, cadeia=cadeia, ativa=False,
            configuracao={"perfil": PERFIL_PADRAO},  # nasce com um tipo de fluxo sensato
        )
        sessao.add(auto)
    else:
        auto.nome = nome
        auto.tipo_gatilho = tipo_gatilho
        auto.configuracao_gatilho = configuracao_gatilho or {}
        auto.cadeia = cadeia
    sessao.flush()
    _audit(sessao, usuario, "automacao.definida", "automacao", auto.id, time.organizacao_id)
    return auto


def ativar(sessao: Session, auto: Automacao, *, usuario: Usuario | None = None) -> Automacao:
    """Liga a automação (passa a poder disparar).

    Não há mais parede: até 2026-08-31 esta função recusava ativar quando um agente
    de ação irreversível não tinha portão humano antes na cadeia. Quem segura uma
    ação que precisa de gente é o próprio agente, chamando o instrumento
    `pedir_aprovacao` — decisão do maestro, ver `PRODUTO §19`.

    Religar ZERA a contagem do disjuntor (Onda 4, fatia 3): quem ativou já sabe das
    falhas velhas e merece as três chances de novo. Sem isso, uma automação recém-
    desligada cairia de novo na primeira falha seguinte."""
    from orquestracao import circuito

    if not auto.ativa:
        circuito.zerar(auto)
    auto.ativa = True
    sessao.flush()
    _audit(sessao, usuario, "automacao.ativada", "automacao", auto.id,
           auditoria.org_do_time(sessao, auto.time_id))
    return auto


def desativar(sessao: Session, auto: Automacao, *, usuario: Usuario | None = None) -> Automacao:
    auto.ativa = False
    sessao.flush()
    _audit(sessao, usuario, "automacao.desativada", "automacao", auto.id,
           auditoria.org_do_time(sessao, auto.time_id))
    return auto
