"""Esquemas de entrada e saída da API (Pydantic v2).

Separam o que a API recebe e devolve dos modelos do banco (SQLAlchemy).
Vocabulário do produto em português (CLAUDE.md §14).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Papel = Literal["lider", "agente"]

# ───────────────────────── Organizações ─────────────────────────


class OrganizacaoCriar(BaseModel):
    """Dados para criar uma organização."""

    nome: str = Field(min_length=1, max_length=200)


class OrganizacaoEditar(BaseModel):
    """Dados para editar uma organização."""

    nome: str = Field(min_length=1, max_length=200)


class OrganizacaoLer(BaseModel):
    """Organização como a API a devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    dono_id: uuid.UUID
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
    esquema do tipo (o encaixe), não aqui."""

    nome: str = Field(min_length=1, max_length=200)
    tipo: str = Field(min_length=1, max_length=50)
    configuracao: dict = Field(default_factory=dict)


class InstrumentoEditar(BaseModel):
    """Edita um instrumento. O tipo é fixo após a criação; muda-se nome e
    configuração."""

    nome: str = Field(min_length=1, max_length=200)
    configuracao: dict = Field(default_factory=dict)


class InstrumentoLer(BaseModel):
    """Instrumento como a API o devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    time_id: uuid.UUID
    nome: str
    tipo: str
    configuracao: dict | None
    criado_em: datetime
    atualizado_em: datetime


class TipoInstrumentoLer(BaseModel):
    """Um tipo de instrumento disponível no encaixe, para a interface montar
    o formulário de configuração e de acionamento."""

    tipo: str
    nome_exibicao: str
    descricao: str
    esquema_config: dict
    esquema_args: dict


class AcionarInstrumento(BaseModel):
    """Argumentos para acionar um instrumento isoladamente (teste/Fase 4).
    Validados contra o esquema de Args do tipo."""

    argumentos: dict = Field(default_factory=dict)


class VincularInstrumento(BaseModel):
    """Pendura um instrumento no cinto de um agente."""

    instrumento_id: uuid.UUID


# ─────────────────────────── Execução ────────────────────────────


class ExecutarAgente(BaseModel):
    """Entrada para acionar um agente isoladamente (Tarefa 4.2)."""

    entrada: str = Field(min_length=1)


# ───────────────────────── Automações ────────────────────────────


class AutomacaoCriar(BaseModel):
    """Cria uma automação. A `cadeia` é o grafo de caminhos (ver
    orquestracao/cadeia.py); validada contra os agentes do time na rota.
    Na Etapa 1, o gatilho padrão é 'manual' (disparado pelo maestro)."""

    nome: str = Field(min_length=1, max_length=200)
    tipo_gatilho: str = Field(default="manual", max_length=50)
    configuracao_gatilho: dict = Field(default_factory=dict)
    cadeia: dict = Field(default_factory=dict)
    ativa: bool = False


class AutomacaoEditar(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    tipo_gatilho: str = Field(default="manual", max_length=50)
    configuracao_gatilho: dict = Field(default_factory=dict)
    cadeia: dict = Field(default_factory=dict)
    ativa: bool = False


class AutomacaoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    time_id: uuid.UUID
    nome: str
    tipo_gatilho: str
    configuracao_gatilho: dict | None
    cadeia: dict | None
    ativa: bool
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

# Os três tipos de IA (MIGRACAO Virada 4). Nesta fase só a 'executora' é
# consumida pelo motor; as outras já são modeladas para as Fases 9/10.
TipoIA = Literal["executora", "criadora", "companheira"]


class ChaveApiCriar(BaseModel):
    """Cadastra ou troca uma chave de IA. O `valor` é o segredo: entra cifrado
    no cofre e NUNCA volta numa leitura (PRODUTO §26)."""

    tipo_ia: TipoIA = "executora"
    provedor: str = Field(default="anthropic", min_length=1, max_length=40)
    valor: str = Field(min_length=1)
    apelido: str | None = Field(default=None, max_length=200)


class ChaveApiLer(BaseModel):
    """Uma chave do cofre como a API a devolve: só metadados e os últimos 4
    dígitos. O valor cifrado nunca é reexibido (PRODUTO §26)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organizacao_id: uuid.UUID | None
    tipo_ia: str
    provedor: str
    ultimos4: str | None
    apelido: str | None
    ativa: bool
    criado_em: datetime
    atualizado_em: datetime
