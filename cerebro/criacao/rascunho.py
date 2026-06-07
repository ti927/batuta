"""O documento de rascunho da IA criadora (Fase 9).

Modo rascunho (MIGRACAO §6.4): as ferramentas da IA montam ESTE documento — um
objeto Pydantic em memória, serializado como JSONB na coluna `conversas_criacao.
rascunho` — e NUNCA tocam as tabelas de negócio. Só `materializar` (após a
aprovação humana explícita) o transforma em linhas reais. A separação 'a IA
propõe / o consultor confirma' é, por isso, uma garantia estrutural.

Agentes e instrumentos carregam um `ref` (id local estável) para a cadeia e o
cinto se referenciarem por nome lógico, sobrevivendo a edições/remoções no meio
da conversa; `materializar` traduz cada `ref` no uuid real criado. Segredos de
instrumento NUNCA entram no rascunho (PRODUTO §26): ficam só como
`segredos_pendentes`, preenchidos pelo humano depois, na tela do instrumento.

O formato da `cadeia` é o MESMO grafo de `orquestracao.cadeia` (inicio/nos/
saidas, com `pausa_humano` marcando o portão de aprovação), só que com `ref`s de
agente no lugar dos uuids — a tradução acontece em `materializar`.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field


def _novo_ref() -> str:
    """Id local curto e estável para um agente/instrumento dentro do rascunho."""
    return uuid.uuid4().hex[:8]


class InstrumentoRascunho(BaseModel):
    """Um instrumento proposto. `configuracao` guarda só os campos PÚBLICOS; os
    campos secretos do tipo ficam listados em `segredos_pendentes` (o humano os
    preenche depois — segredo nunca trafega no rascunho)."""

    ref: str = Field(default_factory=_novo_ref)
    nome: str
    tipo: str
    configuracao: dict = Field(default_factory=dict)
    segredos_pendentes: list[str] = Field(default_factory=list)


class AgenteRascunho(BaseModel):
    """Um agente proposto, com seus quatro markdowns e o cinto (refs de
    instrumento). `papel` 'lider' ou 'agente' — no máximo um líder por time."""

    ref: str = Field(default_factory=_novo_ref)
    nome: str
    papel: Literal["lider", "agente"] = "agente"
    agent_md: str | None = None
    skill_md: str | None = None
    tools_md: str | None = None
    soul_md: str | None = None
    modelo_ia: str | None = None
    cinto: list[str] = Field(default_factory=list)  # refs de InstrumentoRascunho


class GatilhoRascunho(BaseModel):
    """O gatilho da automação (manual, agendado, webhook…)."""

    tipo_gatilho: str = "manual"
    configuracao_gatilho: dict = Field(default_factory=dict)


class AutomacaoRascunho(BaseModel):
    """A automação proposta: a cadeia (grafo por refs) e o gatilho."""

    nome: str | None = None
    cadeia: dict = Field(default_factory=dict)  # grafo por refs (formato de cadeia.py)
    gatilho: GatilhoRascunho = Field(default_factory=GatilhoRascunho)


class CustoEstimado(BaseModel):
    """Estimativa de custo (PRODUTO §21): mostrada antes de aprovar."""

    por_execucao_usd: float | None = None
    por_mes_usd: float | None = None
    detalhe: dict = Field(default_factory=dict)


class Rascunho(BaseModel):
    """O documento inteiro do time proposto. Tudo opcional: um rascunho parcial é
    válido — a IA o vai preenchendo turno a turno. A completude para materializar
    é checada à parte (em `materializar`)."""

    time_nome: str | None = None
    time_descricao: str | None = None
    agentes: list[AgenteRascunho] = Field(default_factory=list)
    instrumentos: list[InstrumentoRascunho] = Field(default_factory=list)
    automacao: AutomacaoRascunho | None = None
    custo_estimado: CustoEstimado | None = None

    def agente_por_ref(self, ref: str) -> AgenteRascunho | None:
        return next((a for a in self.agentes if a.ref == ref), None)

    def instrumento_por_ref(self, ref: str) -> InstrumentoRascunho | None:
        return next((i for i in self.instrumentos if i.ref == ref), None)

    def tem_lider(self, exceto_ref: str | None = None) -> bool:
        return any(
            a.papel == "lider" and a.ref != exceto_ref for a in self.agentes
        )
