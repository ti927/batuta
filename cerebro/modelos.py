"""Modelos do core do Batuta (SQLAlchemy).

Vocabulário do produto em português (CLAUDE.md §14). Toda tabela de negócio
carrega, direta ou indiretamente, o vínculo com a organização, sustentando o
isolamento entre organizações e times do PRODUTO.md.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IdData:
    """Mixin: identificador único e datas de criação/atualização."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Usuario(IdData, Base):
    """Usuário do Batuta. Na Etapa 1 existe só o usuário fixo de testes;
    na Etapa 2 isto é substituído pelo Supabase Auth."""

    __tablename__ = "usuarios"
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    # Vínculo ao Supabase Auth (o `sub` do JWT). Nulo até o usuário aceitar o
    # convite e logar a primeira vez; é o que liga a identidade real ao registro.
    auth_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=True
    )
    # Desativação (MIGRACAO §3.7): um usuário inativo não acessa nada, mas o
    # registro e seu histórico permanecem.
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class Organizacao(IdData, Base):
    """A empresa. Espaço onde tudo daquela empresa vive."""

    __tablename__ = "organizacoes"
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    dono_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False
    )
    # Modelo de IA da conversa (criadora/companheira) desta organização. Nulo =
    # usa o padrão do código (Opus). O seletor da tela só oferece modelos cujo
    # provedor tem chave resolvível (própria ou da consultoria).
    modelo_criadora: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Logo/foto da organização, guardado como data URI (a imagem é encolhida no
    # navegador antes de salvar). Nulo = sem logo (a UI mostra a inicial do nome).
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class Time(IdData, Base):
    """A unidade de trabalho. Pertence a uma organização."""

    __tablename__ = "times"
    organizacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)


class Agente(IdData, Base):
    """Líder ou Agente. A distinção é o campo 'papel'. Cada time tem no
    máximo um agente com papel 'lider' (garantido por índice parcial)."""

    __tablename__ = "agentes"
    time_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("times.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    papel: Mapped[str] = mapped_column(String(20), nullable=False)  # "lider" | "agente"
    agent_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    tools_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    soul_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    modelo_ia: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index(
            "uq_um_lider_por_time",
            "time_id",
            unique=True,
            postgresql_where=text("papel = 'lider'"),
        ),
    )


class Instrumento(IdData, Base):
    """Uma capacidade que um agente invoca. Pertence a um time. A configuração
    é flexível (JSONB) porque cada tipo de instrumento pede campos diferentes."""

    __tablename__ = "instrumentos"
    time_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("times.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    configuracao: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Ícone escolhido pelo usuário (id no catálogo da UI, ex.: "fab:whatsapp").
    # NULL = sem escolha → a interface mostra o ícone genérico. Só apresentação.
    icone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Interruptor de aprovação humana por instância (sobrepõe a derivação por
    # tipo/config): NULL = automático; True = sempre exige portão; False = nunca.
    # A parede de ativação resolve via instrumentos.exige_portao().
    exige_aprovacao: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Caixa-forte de credenciais: aponta para uma credencial nomeada da central
    # (da organização ou da consultoria) em vez de guardar o segredo inline. NULL
    # = sem referência (usa segredo próprio inline / pool, como antes). A borda
    # mescla os campos da credencial na config ao executar (núcleo intocado).
    credencial_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("credenciais.id", ondelete="SET NULL"), nullable=True
    )


class AgenteInstrumento(Base):
    """Ligação N-para-N: instrumentos no cinto de um agente."""

    __tablename__ = "agente_instrumentos"
    agente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentes.id", ondelete="CASCADE"), primary_key=True
    )
    instrumento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instrumentos.id", ondelete="CASCADE"), primary_key=True
    )


class Automacao(IdData, Base):
    """A definição de um fluxo: o gatilho e a cadeia ordenada de agentes."""

    __tablename__ = "automacoes"
    time_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("times.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo_gatilho: Mapped[str] = mapped_column(String(50), nullable=False)
    configuracao_gatilho: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cadeia: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    ativa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Canal de aprovação: NÃO é mais por automação. A config de aprovação por canal
    # vive no NÓ com portão da `cadeia` (`no.aprovacao = {instrumento_id, destinatario}`,
    # construtor visual). A coluna antiga `aprovacao_instrumento_id` foi aposentada
    # (migração de drop pós-deploy).


class Execucao(IdData, Base):
    """O registro de cada vez que uma automação roda."""

    __tablename__ = "execucoes"
    automacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("automacoes.id", ondelete="CASCADE"), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'aguardando'")
    )  # aguardando | em_andamento | aguardando_humano | concluida | falhou
    entrada: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resultado: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    iniciada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finalizada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PassoExecucao(IdData, Base):
    """Cada passo de uma execução: o agente que processou, o que recebeu e
    produziu. É o que permite inspecionar a orquestração passo a passo.
    O agente é nullable com SET NULL para preservar o histórico mesmo que o
    agente seja removido depois (auditoria)."""

    __tablename__ = "passos_execucao"
    execucao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execucoes.id", ondelete="CASCADE"), nullable=False
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    agente_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agentes.id", ondelete="SET NULL"), nullable=True
    )
    # Id do NÓ do grafo onde este passo rodou (cadeia como grafo). Permite à
    # retomada localizar o nó pausado por id — necessário porque o mesmo agente
    # pode aparecer em vários nós. Nullable: passos antigos não o têm.
    no_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entrada: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    saida: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'aguardando'")
    )
    iniciado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finalizado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ───────────────────── Identidade e acesso (Etapa 2, Fase 6) ─────────────────


class Membro(IdData, Base):
    """Vínculo de um usuário a uma organização, com seu papel de acesso
    (admin | operador | observador). É a fonte de permissão da Etapa 2 — substitui,
    na prática, o antigo 'dono' único da organização. Um usuário pode ser membro de
    várias organizações, com papel distinto em cada (índice único do par)."""

    __tablename__ = "membros"
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    organizacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False
    )
    papel: Mapped[str] = mapped_column(String(20), nullable=False)  # admin|operador|observador

    __table_args__ = (
        Index("uq_membro_usuario_org", "usuario_id", "organizacao_id", unique=True),
    )


class Convite(IdData, Base):
    """Convite para um email entrar numa organização com um papel. Ninguém se
    autoinscreve (MIGRACAO §3.7): um admin emite o convite; o convidado aceita e
    vira Membro."""

    __tablename__ = "convites"
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    organizacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False
    )
    papel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pendente'")
    )  # pendente|aceito|expirado|revogado
    convidado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    expira_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (Index("ix_convite_email_org", "email", "organizacao_id"),)


class Auditoria(IdData, Base):
    """Registro nominal de uma ação sensível (quem, o quê, quando, em qual recurso).
    `usuario_id` é SET NULL para preservar o registro mesmo que o usuário seja
    removido (igual a PassoExecucao.agente_id). `recurso_id`/`organizacao_id` são
    UUID soltos (não FK) de propósito: a auditoria sobrevive à exclusão do recurso."""

    __tablename__ = "auditoria"
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    acao: Mapped[str] = mapped_column(String(60), nullable=False)
    recurso_tipo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    recurso_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    organizacao_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    detalhe: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


# ───────────────────── Cofre de chaves (Etapa 2, Fase 7) ─────────────────────


class ChaveApi(IdData, Base):
    """Cofre criptografado de chaves de API de IA (PRODUTO §26, MIGRACAO Viradas 4/5).

    Cada chave pertence a uma organização (o cliente). Quando `organizacao_id` é
    nulo, é a CHAVE-MÃE DA CONSULTORIA — o fallback usado quando o cliente não tem
    chave própria. O valor fica sempre cifrado em `valor_cifrado` e NUNCA é
    reexibido (PRODUTO §26): a interface mostra apenas `ultimos4`.

    A chave é UMA por provedor (unificação 2026-06-15): a antiga dimensão de
    papel (`tipo_ia`: executora/criadora) saiu — basta "este provedor tem
    credencial?". A escolha de QUAL IA roda vive no modelo (da conversa e de cada
    agente), não na chave. Some o cadastro em dobro e a pegadinha da imagem.

    Há no máximo uma chave por (organização, provedor) — inclusive para a
    chave-mãe (índice com NULLS NOT DISTINCT, pois `organizacao_id` é nulo nela).
    Trocar a chave atualiza a linha existente; `ativa` permite desligá-la sem
    apagar o registro."""

    __tablename__ = "chaves_api"
    organizacao_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=True
    )
    provedor: Mapped[str] = mapped_column(String(40), nullable=False)  # anthropic|openai|google|...
    valor_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    ultimos4: Mapped[str | None] = mapped_column(String(8), nullable=True)
    apelido: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ativa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    # Só relevante na chave-mãe da consultoria (organizacao_id nulo): se True, a
    # chave entra na reserva automática (fallback) das organizações; se False, é
    # privada da consultoria. Nas chaves próprias da organização é irrelevante.
    # Nasce True para NÃO mudar o comportamento das chaves já cadastradas
    # (retrocompatível); o maestro desmarca o que quiser tornar privado.
    compartilhavel: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    __table_args__ = (
        Index(
            "uq_chave_org_provedor",
            "organizacao_id",
            "provedor",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )


class SegredoInstrumento(IdData, Base):
    """Cofre criptografado das credenciais de um instrumento (Fase 7-B, PRODUTO §26).

    Cada linha é UM campo secreto de UM instrumento (ex.: a senha de app do
    WordPress, a chave da busca web, o token de um webhook). O valor fica sempre
    cifrado em `valor_cifrado` e NUNCA é reexibido — a interface mostra só
    `ultimos4`. Vive separado da `instrumentos.configuracao` (JSONB em claro), que
    guarda apenas os campos não-secretos. É per-organização por herança
    (instrumento → time → organização). Há no máximo um segredo por
    (instrumento, campo)."""

    __tablename__ = "segredos_instrumento"
    instrumento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instrumentos.id", ondelete="CASCADE"), nullable=False
    )
    campo: Mapped[str] = mapped_column(String(80), nullable=False)
    valor_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    ultimos4: Mapped[str | None] = mapped_column(String(8), nullable=True)

    __table_args__ = (
        Index(
            "uq_segredo_instrumento_campo",
            "instrumento_id",
            "campo",
            unique=True,
        ),
    )


class Credencial(IdData, Base):
    """Caixa-forte de credenciais nomeadas (PRODUTO §26).

    Uma credencial é um SACO tipado e cifrado de campos (ex.: WordPress =
    usuario+senha_app; SQL = usuario+senha; ou um token solto). Um instrumento
    APONTA para uma credencial (via `instrumentos.credencial_id`) em vez de
    guardar o segredo inline — trocá-la num lugar só vale para todos os
    instrumentos que a usam. O saco inteiro é cifrado num único blob JSON
    (`dados_cifrado`, reusa o `cofre.py`); `resumo` guarda só os últimos 4 de cada
    campo, para exibição (o valor pleno nunca volta à interface, PRODUTO §26).

    Pertence a uma organização; quando `organizacao_id` é nulo, é uma credencial
    DA CONSULTORIA, disponível às organizações só se `compartilhavel` — e por
    ESCOLHA EXPLÍCITA no seletor do instrumento (credencial nomeada nunca cai por
    fallback automático, pois aponta para um sistema específico). `compartilhavel`
    nasce False: uma credencial nova é privada do seu escopo até ser liberada.

    `expira_em` (nulo agora) abre espaço para credenciais OAuth no futuro (token
    que se renova), sem mudar o schema."""

    __tablename__ = "credenciais"
    organizacao_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=True
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    dados_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    resumo: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    compartilhavel: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    expira_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index(
            "uq_credencial_org_nome",
            "organizacao_id",
            "nome",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )


# ───────────────────── IA criadora (Etapa 2, Fase 9) ─────────────────────────


class ConversaCriacao(IdData, Base):
    """Conversa da IA criadora — UMA conversa que nunca termina (paradigma novo).

    A IA opera sobre o TIME REAL desde o começo: as ferramentas escrevem direto
    nas tabelas (Time/Agente/Instrumento/cinto/Automacao), pela porta validada de
    `criacao/servicos.py`. Não há mais rascunho-como-documento nem ritual de
    'aprovar e criar'. A proteção mudou de lugar: tudo é real mas DORME — a
    automação nasce inativa e nada roda até o consultor ATIVAR, e a parede de
    ativação exige portão humano antes de ação irreversível (ver portao_ativacao).

    O 'estado' do time (rascunho | ativo) é DERIVADO da automação (ativa?), não uma
    coluna. A conversa segue viva depois de ativar, para editar e consertar.

    Vínculo: nasce na ORGANIZAÇÃO (o time ainda não existe) e ganha `time_id` assim
    que a IA cria o time (preguiçosamente, no primeiro `definir_time`). `mensagens`
    é o histórico append-only."""

    __tablename__ = "conversas_criacao"
    organizacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False
    )
    criada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    titulo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mensagens: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # O time que esta conversa cria e mantém. Nulo até o primeiro `definir_time`.
    # SET NULL para a conversa sobreviver à exclusão do time.
    time_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("times.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (Index("ix_conversa_criacao_org", "organizacao_id"),)


class MemoriaProjeto(IdData, Base):
    """Memória de LONGO PRAZO da IA sobre um projeto (Fase 10).

    O que a IA aprende e deve lembrar entre sessões: fatos do cliente, decisões
    tomadas com o consultor, preferências de tom/forma. A própria IA cura o que vale
    guardar (ferramenta `lembrar`) e pode corrigir o que mudou (`esquecer`).

    Abordagem DESTILADA, não vetorial (decisão do maestro 2026-06-07): um projeto
    acumula dezenas de memórias, não milhares — cabem no contexto do modelo, então a
    recuperação é por recência/filtro simples, sem embeddings nem busca semântica.

    Isolamento estrito: presa à CONVERSA (o fio eterno do projeto, 1:1 com o time) e
    carregando `organizacao_id` como parede dura — uma organização nunca vê a memória
    de outra. Sobrevive à exclusão do time (a conversa sobrevive)."""

    __tablename__ = "memorias_projeto"
    conversa_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversas_criacao.id", ondelete="CASCADE"), nullable=False
    )
    organizacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False
    )
    # 'fato' | 'decisao' | 'preferencia' — o tipo da memória, para o painel agrupar.
    categoria: Mapped[str] = mapped_column(String(20), nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_memoria_projeto_conversa", "conversa_id"),)


# ───────────────────── Mensageria de mão dupla (Fase 1) ──────────────────────


class Conversa(IdData, Base):
    """Uma conversa (sessão) entre um contato externo e o time, por um canal.

    É o objeto de 1ª classe que coordena a mão dupla: agrupa as mensagens de um
    contato, o estado da conversa e o vínculo com a execução do motor. NÃO é um
    "ambiente de canais" da organização (essa abstração foi rejeitada e revertida)
    — a IDENTIDADE do canal é o `instrumento` (`enviar_telegram`/`enviar_whatsapp`):
    cada instância de instrumento (com seu próprio bot/número) recebe e envia.

    Nasce quando o contato manda a 1ª mensagem (inbound-first). `destino_tipo` +
    `destino_id` dizem quem atende: um agente (modo conversacional) ou uma
    automação (modo fluxo); não é FK porque aponta para tabelas diferentes.
    `execucao_id` é a execução viva que esta conversa conduz (modo fluxo).

    Camada de borda — o núcleo de orquestração não conhece esta tabela. Ver
    `docs/MENSAGERIA-PLANO.md`."""

    __tablename__ = "conversas"
    instrumento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instrumentos.id", ondelete="CASCADE"), nullable=False
    )
    canal: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'telegram'")
    )
    # Identificador do contato no canal (chat_id do Telegram; depois, telefone do
    # WhatsApp). É a chave de roteamento — o id cru, não um conceito de identidade.
    contato_chave: Mapped[str] = mapped_column(String(120), nullable=False)
    # Nome de exibição do contato (vem no webhook). Conveniência para o operador.
    contato_nome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'aberta'")
    )  # aberta | bot_respondendo | aguardando_resposta | humano_assumiu | fechada
    destino_tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)  # agente|automacao
    destino_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    execucao_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("execucoes.id", ondelete="SET NULL"), nullable=True
    )
    # Prazo de inatividade: quando vence, o vigia (sweeper) cutuca e depois encerra.
    aguardando_ate: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    nudge_enviado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Operador que assumiu a conversa (takeover). Nulo = bot no comando.
    atribuida_a: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    custo_acumulado_usd: Mapped[float] = mapped_column(
        Numeric(12, 6), nullable=False, server_default=text("0")
    )
    turnos: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    ultima_entrada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # No máximo UMA conversa viva por (canal/bot, contato); fechadas acumulam.
        Index(
            "uq_conversa_viva",
            "instrumento_id",
            "contato_chave",
            unique=True,
            postgresql_where=text("estado <> 'fechada'"),
        ),
        Index("ix_conversa_instrumento", "instrumento_id"),
    )


class MensagemConversa(IdData, Base):
    """Uma mensagem na thread de uma conversa (contato, agente, operador ou
    sistema). Guarda o texto e, opcionalmente, metadados de mídia (ex.: áudio
    transcrito). `entregue` registra o status de entrega ao contato."""

    __tablename__ = "mensagens_conversa"
    conversa_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversas.id", ondelete="CASCADE"), nullable=False
    )
    papel: Mapped[str] = mapped_column(String(20), nullable=False)  # contato|agente|operador|sistema
    conteudo: Mapped[str | None] = mapped_column(Text, nullable=True)
    midia: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Medição de uso de IA do turno (só na mensagem do AGENTE): a LISTA de entradas
    # {modelo, tokens_entrada, tokens_saida, origem, categoria, custo_usd?} das
    # chamadas pagas do turno — o turno do agente (categoria 'mensageria') e as
    # transcrições de áudio (categoria 'transcricao'). Espelha PassoExecucao.saida.uso
    # para a mensageria entrar nos painéis de uso. Ver `docs/MENSAGERIA-PLANO.md`.
    uso: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    entregue: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    __table_args__ = (Index("ix_mensagem_conversa", "conversa_id", "criado_em"),)
