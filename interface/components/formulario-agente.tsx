"use client";

import { useEffect, useState } from "react";

import {
  api,
  ErroDaApi,
  type Agente,
  type ModelosDisponiveis,
  type Papel,
  type RecallMemoria,
  type Time,
} from "@/lib/api";
import {
  MODELOS_POR_PROVEDOR,
  provedorDoModelo,
  provedoresParaSeletor,
  ROTULO_PROVEDOR,
  type ProvedoresDisponiveis,
} from "@/lib/modelos";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

// Formulário de agente, compartilhado entre a tela "Gerenciar agentes"
// (/times/[id]/agentes) e o drawer editável do dashboard. `agente=null` cria;
// com `agente` edita. Salva pela mesma porta de sempre (POST/PUT) e devolve o
// agente salvo em `onSalvo` — o pai decide o que fazer (fechar, router.refresh).

type Campos = {
  nome: string;
  papel: Papel;
  modelo_ia: string;
  agent_md: string;
  skill_md: string;
  tools_md: string;
  soul_md: string;
  memoria_ativa: boolean;
  memoria_recall: RecallMemoria;
};

const VAZIO: Campos = {
  nome: "",
  papel: "agente",
  modelo_ia: "",
  agent_md: "",
  skill_md: "",
  tools_md: "",
  soul_md: "",
  memoria_ativa: false,
  memoria_recall: "sempre",
};

function deAgente(a: Agente): Campos {
  return {
    nome: a.nome,
    papel: a.papel,
    modelo_ia: a.modelo_ia ?? "",
    agent_md: a.agent_md ?? "",
    skill_md: a.skill_md ?? "",
    tools_md: a.tools_md ?? "",
    soul_md: a.soul_md ?? "",
    memoria_ativa: a.memoria_ativa,
    memoria_recall: a.memoria_recall ?? "sempre",
  };
}

type ChaveMd = "agent_md" | "skill_md" | "tools_md" | "soul_md";

const MARKDOWNS: [ChaveMd, string][] = [
  ["agent_md", "agent.md — quem o agente é, o que faz"],
  ["skill_md", "skill.md — as habilidades dele"],
  ["tools_md", "tools.md — os instrumentos do cinto"],
  ["soul_md", "soul.md — personalidade, tom, jeito de falar"],
];

export function FormularioAgente({
  time,
  agente,
  amplo = false,
  onSalvo,
  onCancelar,
}: {
  time: Time;
  agente: Agente | null;
  // No popup amplo (80%×80%), os 4 markdowns vão numa grade 2×2 em vez de empilhados.
  amplo?: boolean;
  onSalvo: (salvo: Agente) => void;
  onCancelar: () => void;
}) {
  const [form, setForm] = useState<Campos>(agente ? deAgente(agente) : VAZIO);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  // Disponibilidade de provedores por chave: só oferecemos modelos cujo provedor
  // tem chave — escolher um sem chave quebraria na execução. A chave é por
  // provedor (unificação 2026-06-15): o mapa já vem achatado.
  const [disponiveis, setDisponiveis] = useState<ProvedoresDisponiveis>();

  useEffect(() => {
    let vivo = true;
    api
      .get<ModelosDisponiveis>(
        `/organizacoes/${time.organizacao_id}/modelos-disponiveis`,
      )
      .then((d) => {
        if (vivo) setDisponiveis(d);
      })
      .catch(() => {
        /* sem disponibilidade: o seletor mostra todos (fallback seguro) */
      });
    return () => {
      vivo = false;
    };
  }, [time.organizacao_id]);

  // Provedores a exibir: os com chave, mais o do modelo já escolhido (para não
  // sumir um valor existente cujo provedor perdeu a chave).
  const provedoresVisiveis = provedoresParaSeletor(
    disponiveis,
    form.modelo_ia ? provedorDoModelo(form.modelo_ia) : null,
  );

  function campo<K extends keyof Campos>(chave: K, valor: Campos[K]) {
    setForm((f) => ({ ...f, [chave]: valor }));
  }

  function corpo() {
    return {
      nome: form.nome.trim(),
      papel: form.papel,
      modelo_ia: form.modelo_ia || null,
      agent_md: form.agent_md || null,
      skill_md: form.skill_md || null,
      tools_md: form.tools_md || null,
      soul_md: form.soul_md || null,
      memoria_ativa: form.memoria_ativa,
      memoria_recall: form.memoria_recall,
    };
  }

  async function salvar() {
    if (!form.nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    setSalvando(true);
    try {
      const salvo = agente
        ? await api.put<Agente>(`/agentes/${agente.id}`, corpo())
        : await api.post<Agente>(`/times/${time.id}/agentes`, corpo());
      setErro(null);
      onSalvo(salvo);
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao salvar agente");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {erro && <Aviso>{erro}</Aviso>}

      <div className="flex flex-wrap gap-3">
        <Label className="min-w-40 flex-1 flex-col items-start gap-1">
          Nome
          <Input
            value={form.nome}
            onChange={(e) => campo("nome", e.target.value)}
            autoFocus
          />
        </Label>
        <Label className="flex-col items-start gap-1">
          Papel
          <Select
            value={form.papel}
            onChange={(e) => campo("papel", e.target.value as Papel)}
          >
            <option value="agente">Agente</option>
            <option value="lider">Líder</option>
          </Select>
        </Label>
        <Label className="flex-col items-start gap-1">
          Modelo de IA
          <Select
            value={form.modelo_ia}
            onChange={(e) => campo("modelo_ia", e.target.value)}
          >
            <option value="">(não definido)</option>
            {provedoresVisiveis.map((p) => (
              <optgroup key={p} label={ROTULO_PROVEDOR[p]}>
                {MODELOS_POR_PROVEDOR[p].map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
        </Label>
      </div>

      {/* Memória do agente: aprende com o próprio trabalho e lembra entre execuções.
          A POLÍTICA (o que guardar/quando buscar) vai nos markdowns; aqui só liga e
          escolhe como lembra. Sem memória, o agente é stateless (como sempre foi). */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-card px-3 py-2">
        <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-foreground">
          <input
            type="checkbox"
            checked={form.memoria_ativa}
            onChange={(e) => campo("memoria_ativa", e.target.checked)}
            className="size-4 accent-[#6D4AFF]"
          />
          Memória ativa
        </label>
        {form.memoria_ativa && (
          <Label className="flex-row items-center gap-2 text-sm">
            Como lembrar
            <Select
              value={form.memoria_recall}
              onChange={(e) =>
                campo("memoria_recall", e.target.value as RecallMemoria)
              }
            >
              <option value="sempre">Sempre visível (atendimento)</option>
              <option value="sob_demanda">Sob demanda (busca quando orientado)</option>
            </Select>
          </Label>
        )}
        <span className="w-full text-xs text-muted-foreground">
          O agente guarda fichas por assunto e lembra entre execuções.{" "}
          {form.memoria_ativa && form.memoria_recall === "sempre"
            ? "“Sempre visível” injeta a memória no prompt toda vez (mais tokens por execução)."
            : "“Sob demanda” só busca quando o markdown orientar (mais barato)."}{" "}
          Edite as fichas na seção “Memórias” do agente.
        </span>
      </div>

      {/* Os 4 markdowns DIVIDEM IGUALMENTE o espaço que sobra (cada Label flex-1),
          cada textarea rola por dentro quando o texto passa da sua fatia.
          No popup amplo, vão numa grade 2×2 (cada um bem maior); no drawer estreito,
          empilhados. Salvar/Cancelar (abaixo) ficam sempre visíveis. */}
      <div
        className={
          amplo
            ? "grid min-h-0 flex-1 grid-cols-2 grid-rows-2 gap-3"
            : "flex min-h-0 flex-1 flex-col gap-3"
        }
      >
        {MARKDOWNS.map(([chave, rotulo]) => (
          <Label key={chave} className="min-h-0 flex-1 flex-col items-start gap-1">
            {rotulo}
            <Textarea
              className="min-h-0 w-full flex-1 resize-none font-mono"
              value={form[chave]}
              onChange={(e) => campo(chave, e.target.value)}
            />
          </Label>
        ))}
      </div>

      <div className="flex gap-2">
        <Button onClick={salvar} disabled={salvando}>
          {salvando ? "Salvando…" : "Salvar"}
        </Button>
        <Button variant="ghost" onClick={onCancelar} disabled={salvando}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
