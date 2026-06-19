"""Esquemas de entrada e saída da API (Pydantic v2).

Separam o que a API recebe e devolve dos modelos do banco (SQLAlchemy).
Vocabulário do produto em português (CLAUDE.md §14).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Papel = Literal["lider", "agente"]

# ───────────────────────── Organizações ─────────────────────────

# Logo guardado como data URI (a imagem é encolhida no navegador). Teto generoso:
# ~750 KB em base64 — um logo de 128px cabe com folga; barra payload abusivo.
LOGO_MAX_CHARS = 1_000_000


def _validar_logo(valor: str | None) -> str | None:
    if valor is None:
        return None
    if not valor.startswith("data:image/"):
        raise ValueError("O logo deve ser um data URI de imagem (data:image/...).")
    if len(valor) > LOGO_MAX_CHARS:
        raise ValueError("Imagem grande demais; reduza o logo.")
    return valor


class OrganizacaoCriar(BaseModel):
    """Dados para criar uma organização."""

    nome: str = Field(min_length=1, max_length=200)
    logo_url: str | None = Field(default=None)

    @field_validator("logo_url")
    @classmethod
    def _logo(cls, v: str | None) -> str | None:
        return _validar_logo(v)


class OrganizacaoEditar(BaseModel):
    """Dados para editar uma organização."""

    nome: str = Field(min_length=1, max_length=200)
    logo_url: str | None = Field(default=None)

    @field_validator("logo_url")
    @classmethod
    def _logo(cls, v: str | None) -> str | None:
        return _validar_logo(v)


class ModeloCriadoraEditar(BaseModel):
    """Define o modelo de IA da conversa (criadora/companheira) de uma organização.
    `modelo` nulo volta ao padrão do código (Opus)."""

    modelo: str | None = Field(default=None, max_length=100)


class OrganizacaoLer(BaseModel):
    """Organização como a API a devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    dono_id: uuid.UUID
    modelo_criadora: str | None = None
    logo_url: str | None = None
    criado_em: datetime
    atualizado_em: datetime


# ───────────────────────────── Times ─────────────────────────────


class TimeCriar(BaseModel):
    """Dados para criar um time."""

    nome: str = Field(min_length=1, max_length=200)
    descricao: str | None = None


class TimeEditar(BaseModel):
    """Dados para editar um time."""

    nome: str = Field(min_length=1, max_length=200)
    descricao: str | None = None


class TimeLer(BaseModel):
    """Time como a API o devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organizacao_id: uuid.UUID
    nome: str
    descricao: str | None
    criado_em: datetime
    atualizado_em: datetime


class TimeResumoLer(BaseModel):
    """Visão de saúde do time para a barra de abas e a aba Início: contadores das
    coleções + agregados (gatilho, custo, taxa de sucesso, pendências). Só leitura
    e agregação — nada do núcleo de orquestração é tocado."""

    # contadores (alimentam as pílulas das abas)
    agentes: int
    instrumentos: int
    automacoes: int
    execucoes: int
    conversas: int
    # agregados da aba Início
    ativo: bool  # alguma automação ativa? (badge ativo/em repouso no cabeçalho)
    gatilho: str | None  # tipo_gatilho da automação principal (manual/agendamento/webhook)
    custo_acumulado_usd: float
    taxa_sucesso: float | None  # concluídas / (concluídas + falhou); None se nenhuma finalizou
    pendencias: int  # execuções aguardando_humano
    conversas_em_andamento: int  # conversas não fechadas (ponto de alerta)


# ──────────────────────────── Agentes ────────────────────────────


class AgenteCriar(BaseModel):
    """Dados para criar um agente (Líder ou Agente)."""

    nome: str = Field(min_length=1, max_length=200)
    papel: Papel
    agent_md: str | None = None
    skill_md: str | None = None
    tools_md: str | None = None
    soul_md: str | None = None
    modelo_ia: str | None = Field(default=None, max_length=100)


class AgenteEditar(BaseModel):
    """Dados para editar um agente."""

    nome: str = Field(min_length=1, max_length=200)
    papel: Papel
    agent_md: str | None = None
    skill_md: str | None = None
    tools_md: str | None = None
    soul_md: str | None = None
    modelo_ia: str | None = Field(default=None, max_length=100)


class AgenteLer(BaseModel):
    """Agente como a API o devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    time_id: uuid.UUID
    nome: str
    papel: Papel
    agent_md: str | None
    skill_md: str | None
    tools_md: str | None
    soul_md: str | None
    modelo_ia: str | None
    criado_em: datetime
    atualizado_em: datetime


# ────────────────────────── Instrumentos ─────────────────────────


class InstrumentoCriar(BaseModel):
    """Dados para criar um instrumento. A configuração é validada contra o
    esquema do tipo (o encaixe), não aqui. `exige_aprovacao` (interruptor de
    portão humano): NULL = automático; True = sempre; False = nunca."""

    nome: str = Field(min_length=1, max_length=200)
    tipo: str = Field(min_length=1, max_length=50)
    configuracao: dict = Field(default_factory=dict)
    exige_aprovacao: bool | None = None
    # Ícone escolhido na UI (ex.: "fab:whatsapp"). NULL = ícone genérico.
    icone: str | None = Field(default=None, max_length=60)
    # Caixa-forte: se preenchido, o instrumento usa uma credencial nomeada da
    # central em vez de segredo inline. NULL = inline/pool, como antes.
    credencial_id: uuid.UUID | None = None


class InstrumentoEditar(BaseModel):
    """Edita um instrumento. O tipo é fixo após a criação; muda-se nome,
    configuração e o interruptor de aprovação."""

    nome: str = Field(min_length=1, max_length=200)
    configuracao: dict = Field(default_factory=dict)
    exige_aprovacao: bool | None = None
    icone: str | None = Field(default=None, max_length=60)
    credencial_id: uuid.UUID | None = None


class InstrumentoLer(BaseModel):
    """Instrumento como a API o devolve. `segredos` (Fase 7-B) traz, por campo
    secreto já guardado, só os 4 últimos dígitos — o valor nunca é reexibido.
    `exige_aprovacao` é o interruptor (NULL/True/False); `acao_irreversivel` é o
    valor JÁ RESOLVIDO (tipo+config+interruptor), que a UI usa para mostrar se
    exige portão."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    time_id: uuid.UUID
    nome: str
    tipo: str
    configuracao: dict | None
    icone: str | None = None
    segredos: dict[str, str] = Field(default_factory=dict)
    exige_aprovacao: bool | None = None
    acao_irreversivel: bool = False
    credencial_id: uuid.UUID | None = None
    criado_em: datetime
    atualizado_em: datetime


class TipoInstrumentoLer(BaseModel):
    """Um tipo de instrumento disponível no encaixe, para a interface montar
    o formulário de configuração e de acionamento. `campos_secretos` (Fase 7-B)
    lista os campos da config que são segredos (cifrados, nunca reexibidos)."""

    tipo: str
    nome_exibicao: str
    descricao: str
    esquema_config: dict
    esquema_args: dict
    campos_secretos: list[str] = Field(default_factory=list)
    # Se o tipo reusa uma chave de serviço compartilhada da organização: o par
    # (campo_secreto, serviço), ex.: ["chave_api", "openai"]. O front mostra esse
    # campo como OPCIONAL ("usa a chave de IA da organização por padrão").
    chave_compartilhada: list[str] | None = None
    # Caixa-forte: tipos de credencial nomeada que este instrumento aceita
    # referenciar (filtra o seletor "usar uma credencial da central"). Vazio = não
    # aceita credencial da central.
    tipos_credencial_aceitos: list[str] = Field(default_factory=list)
    # Ação irreversível (publicar/enviar/gravar externo): o front mostra um aviso
    # e a parede de ativação exige portão humano antes de um agente que a use.
    acao_irreversivel: bool = False
    # Campos com OPÇÕES dependentes de outro campo (dropdown dependente): o front
    # filtra as opções conforme o controlador (ex.: gerar_imagem filtra tamanho/
    # qualidade pelo modelo). None = sem dependências. Ver TipoInstrumento.dependencias_ui.
    dependencias: dict | None = None


class AcionarInstrumento(BaseModel):
    """Argumentos para acionar um instrumento isoladamente (teste/Fase 4).
    Validados contra o esquema de Args do tipo."""

    argumentos: dict = Field(default_factory=dict)


class VincularInstrumento(BaseModel):
    """Pendura um instrumento no cinto de um agente."""

    instrumento_id: uuid.UUID


# ───────────────────────── Automações ────────────────────────────


class AutomacaoCriar(BaseModel):
    """Cria uma automação. A `cadeia` é o grafo de caminhos (ver
    orquestracao/cadeia.py); validada contra os agentes do time na rota.
    Na Etapa 1, o gatilho padrão é 'manual' (disparado pelo maestro)."""

    nome: str = Field(min_length=1, max_length=200)
    tipo_gatilho: str = Field(default="manual", max_length=50)
    configuracao_gatilho: dict = Field(default_factory=dict)
    # A `cadeia` é o grafo de nós tipados; a config de aprovação por canal vive no
    # nó com portão (`no.aprovacao`), não mais por automação.
    cadeia: dict = Field(default_factory=dict)
    ativa: bool = False
    # Comportamento do fluxo (perfil + ajustes finos): `{perfil, ajustes:{...}}`.
    # Resolvido na cascata global<canal<perfil<ajustes<nó (mensageria/config.py).
    configuracao: dict = Field(default_factory=dict)


class AutomacaoEditar(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    tipo_gatilho: str = Field(default="manual", max_length=50)
    configuracao_gatilho: dict = Field(default_factory=dict)
    cadeia: dict = Field(default_factory=dict)
    ativa: bool = False
    configuracao: dict = Field(default_factory=dict)


class DuplicarAutomacao(BaseModel):
    """Duplica uma automação existente: só o nome da cópia. O resto (gatilho,
    config, cadeia) é copiado da original; a cópia nasce inativa."""

    nome: str = Field(min_length=1, max_length=200)


class AutomacaoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    time_id: uuid.UUID
    nome: str
    tipo_gatilho: str
    configuracao_gatilho: dict | None
    cadeia: dict | None
    ativa: bool
    configuracao: dict | None
    criado_em: datetime
    atualizado_em: datetime


class DispararAutomacao(BaseModel):
    """Entrada para disparar uma automação manualmente (teste/Fase 4)."""

    entrada: str = Field(min_length=1)


class ResponderHumano(BaseModel):
    """Resposta do humano a uma execução pausada (espera-por-humano, 4.6)."""

    resposta: str = Field(min_length=1)


# ───────────────────────── Execuções ─────────────────────────────


class PassoExecucaoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ordem: int
    agente_id: uuid.UUID | None
    no_id: str | None = None
    entrada: dict | None
    saida: dict | None
    estado: str
    iniciado_em: datetime | None
    finalizado_em: datetime | None


class ExecucaoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    automacao_id: uuid.UUID
    estado: str
    entrada: dict | None
    resultado: dict | None
    iniciada_em: datetime | None
    finalizada_em: datetime | None
    criado_em: datetime


class ExecucaoNaLista(ExecucaoLer):
    """Uma execução na visão consolidada (gestão de execuções, Tarefa 5.5),
    com o nome da automação para dar contexto sem abrir cada uma, e a
    organização para a interface decidir o que cada papel pode fazer (I6.6)."""

    automacao_nome: str
    organizacao_id: uuid.UUID


class ExecucaoComPassos(ExecucaoLer):
    """Uma execução com seu rastro de passos, para a tela de inspeção."""

    passos: list[PassoExecucaoLer] = Field(default_factory=list)
    # Resumo de uso (tokens e custo aproximado) somado dos passos — Tarefa 5.4.
    uso: dict | None = None


# ───────────────── Identidade e acesso (Etapa 2, Fase 6) ─────────────────

# Papel de ACESSO (admin/operador/observador) — distinto do `Papel` do agente
# (lider/agente); são conceitos diferentes, não reusar.
PapelAcesso = Literal["admin", "operador", "observador"]


class UsuarioLer(BaseModel):
    """Um usuário do Batuta, como a API o devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    email: str | None
    ativo: bool


class MembroLer(BaseModel):
    """Um membro de uma organização, com os dados do usuário para exibição."""

    usuario_id: uuid.UUID
    papel: PapelAcesso
    nome: str
    email: str | None
    ativo: bool


class AlterarPapel(BaseModel):
    """Muda o papel de um membro na organização."""

    papel: PapelAcesso


class ConviteCriar(BaseModel):
    """Convida um email para a organização com um papel."""

    email: str = Field(min_length=3, max_length=320)
    papel: PapelAcesso


class ConviteLer(BaseModel):
    """Um convite, como a API o devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    organizacao_id: uuid.UUID
    papel: str
    status: str
    expira_em: datetime | None
    criado_em: datetime


class ConviteCriado(ConviteLer):
    """O que `criar_convite` devolve: o convite + se o e-mail saiu de fato.
    `email_enviado=False` quando a pessoa já tinha conta (o Supabase não reenvia);
    nesse caso ela verá o aviso dentro do Batuta ao entrar."""

    email_enviado: bool


class ConvitePendente(BaseModel):
    """Um convite pendente endereçado ao usuário logado, com o NOME da
    organização — para o banner de aviso na home. Montado por join, não vem
    direto de um ORM model, então é construído por keyword."""

    id: uuid.UUID
    organizacao_id: uuid.UUID
    organizacao_nome: str
    papel: str
    expira_em: datetime | None


class MeuAcesso(BaseModel):
    """O usuário atual + seus papéis por organização — para a interface decidir
    o que mostrar (UI ciente de papel) sem recalcular a cada tela."""

    id: uuid.UUID
    nome: str
    email: str | None
    ativo: bool
    papeis: dict[uuid.UUID, PapelAcesso] = Field(default_factory=dict)
    # Admin da consultoria (lista no .env) — habilita a gestão da chave-mãe na UI
    # (Fase 7.5). É distinto do papel 'admin' de uma organização.
    admin_consultoria: bool = False


# ───────────────────── Cofre de chaves (Etapa 2, Fase 7) ─────────────────────

# A chave é UMA por provedor (unificação 2026-06-15): não há mais dimensão de
# papel (executora/criadora). Quem escolhe a IA é o modelo, não a chave.


class ChaveApiCriar(BaseModel):
    """Cadastra ou troca uma chave de IA. O `valor` é o segredo: entra cifrado
    no cofre e NUNCA volta numa leitura (PRODUTO §26)."""

    provedor: str = Field(default="anthropic", min_length=1, max_length=40)
    valor: str = Field(min_length=1)
    apelido: str | None = Field(default=None, max_length=200)
    # Só faz efeito na chave-mãe da consultoria: se True, serve de reserva
    # automática às organizações; se False, é privada. Default True (nas chaves
    # próprias da organização é irrelevante).
    compartilhavel: bool = True


class ChaveApiLer(BaseModel):
    """Uma chave do cofre como a API a devolve: só metadados e os últimos 4
    dígitos. O valor cifrado nunca é reexibido (PRODUTO §26)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organizacao_id: uuid.UUID | None
    provedor: str
    ultimos4: str | None
    apelido: str | None
    ativa: bool
    compartilhavel: bool
    criado_em: datetime
    atualizado_em: datetime


# ─────────────────── Caixa-forte de credenciais nomeadas ───────────────────
# Credenciais nomeadas, tipadas e referenciadas pelos instrumentos (ver
# docs/CAIXA-FORTE-PLANO.md). Substitui o antigo "inventário por-instrumento".


class CampoCredencialLer(BaseModel):
    """Um campo de um tipo de credencial — para a interface montar o formulário."""

    nome: str
    rotulo: str
    secreto: bool


class TipoCredencialLer(BaseModel):
    """Um tipo de credencial disponível na caixa-forte (formato de uma conexão)."""

    tipo: str
    nome_exibicao: str
    campos: list[CampoCredencialLer]


class CredencialCriar(BaseModel):
    """Cria uma credencial nomeada. `dados` traz os campos do tipo (ex.:
    {usuario, senha_app}); os secretos entram cifrados e nunca voltam."""

    nome: str = Field(min_length=1, max_length=200)
    tipo: str = Field(min_length=1, max_length=50)
    dados: dict[str, str] = Field(default_factory=dict)
    compartilhavel: bool = False  # só faz efeito numa credencial da consultoria


class CredencialEditar(BaseModel):
    """Edita uma credencial. O tipo é fixo após a criação. Um campo secreto em
    branco preserva o valor atual; um campo de identidade em branco também."""

    nome: str = Field(min_length=1, max_length=200)
    dados: dict[str, str] = Field(default_factory=dict)
    compartilhavel: bool = False


class CredencialLer(BaseModel):
    """Uma credencial como a API a devolve: metadados + `resumo` mascarado
    (identidade visível, segredo só os últimos 4) + `usado_por`. O valor pleno de
    um segredo nunca é reexibido (PRODUTO §26). `organizacao_id` nulo = consultoria."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organizacao_id: uuid.UUID | None
    nome: str
    tipo: str
    resumo: dict | None
    compartilhavel: bool
    usado_por: int = 0
    criado_em: datetime
    atualizado_em: datetime


# ──────────────────── IA criadora (Fase 9) ───────────────────────


class IniciarConversaCriacao(BaseModel):
    """Abre uma conversa de criação. Se vier `mensagem_inicial`, o primeiro turno
    já roda."""

    mensagem_inicial: str | None = None
    titulo: str | None = Field(default=None, max_length=200)


class MensagemTurno(BaseModel):
    """Uma fala do consultor para a IA criadora."""

    mensagem: str = Field(min_length=1)


class RespostaTurno(BaseModel):
    """O resultado de um turno: a resposta da IA, os chips, e a fotografia do TIME
    REAL atualizado (para o canvas se redesenhar). `time_id`/`time` ficam nulos
    enquanto a IA ainda não criou o time."""

    resposta: str
    chips: list[str]
    time_id: str | None = None
    time: dict | None = None
    # Memória de longo prazo do projeto, recalculada após o turno (o painel atualiza).
    memoria: list = []
    uso: dict


class ConversaCriacaoResumo(BaseModel):
    """Uma conversa de criação na listagem (sem o histórico inteiro). `time_nome` é o
    nome do time que esta conversa mantém (nulo se ela ainda não criou um), para a
    tela de retomar projeto rotular cada conversa."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organizacao_id: uuid.UUID
    titulo: str | None
    time_id: uuid.UUID | None
    time_nome: str | None = None
    criado_em: datetime
    atualizado_em: datetime


class ConversaCriacaoLer(ConversaCriacaoResumo):
    """Uma conversa completa: histórico + a fotografia do time real + a memória de
    longo prazo do projeto (preenchidas pela rota, para o front desenhar o canvas e o
    painel 'O que eu sei deste projeto' sem mais idas ao servidor)."""

    mensagens: list
    time: dict | None = None
    memoria: list = []


# ─────────────────── Mensageria / Conversas (Fase 1) ─────────────────────────


class MensagemConversaLer(BaseModel):
    """Uma mensagem da thread de uma conversa, como a API a devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    papel: str  # contato | agente | operador | sistema
    conteudo: str | None
    midia: dict | None
    entregue: bool
    criado_em: datetime


class ConversaLer(BaseModel):
    """Uma conversa (sessão) na listagem da inbox."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrumento_id: uuid.UUID
    canal: str
    contato_chave: str
    contato_nome: str | None
    estado: str
    destino_tipo: str | None
    destino_id: uuid.UUID | None
    atribuida_a: uuid.UUID | None
    turnos: int
    aguardando_ate: datetime | None
    criado_em: datetime
    atualizado_em: datetime


class ConversaComMensagens(ConversaLer):
    """Uma conversa com sua thread completa, para a tela da conversa."""

    mensagens: list[MensagemConversaLer] = Field(default_factory=list)


class ResponderOperador(BaseModel):
    """Texto que o operador (humano) envia ao contato numa conversa assumida."""

    texto: str = Field(min_length=1)


class MetricasAtendimentoLer(BaseModel):
    """Métricas do atendimento por mensageria de um time (Fase K), num período.
    Tudo agregado/leitura — não expõe nenhum segredo."""

    periodo_dias: int
    total: int  # conversas iniciadas no período
    abertas: int  # ainda não fechadas
    com_humano: int  # foram transferidas para um humano (handoff)
    fechadas: int
    percent_humano: float  # 0..100 — fatia que precisou de humano
    turnos_total: int  # respostas do bot no período
    custo_total_usd: float  # custo aproximado de IA do atendimento
    tempo_resposta_medio_s: float | None  # 1ª resposta do bot; None se nenhuma
    por_estado: dict[str, int]
