"use client";

import { useEffect, useState } from "react";
import {
  Brain,
  BookOpen,
  IdCard,
  Smile,
  Sparkles,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import {
  api,
  ErroDaApi,
  type Agente,
  type Instrumento,
  type ModelosDisponiveis,
  type Papel,
  type PapelAcesso,
  type RecallMemoria,
  type Time,
  type TipoInstrumento,
} from "@/lib/api";
import {
  MODELOS_POR_PROVEDOR,
  provedorDoModelo,
  provedoresParaSeletor,
  ROTULO_PROVEDOR,
  type ProvedoresDisponiveis,
} from "@/lib/modelos";
import { podeOperar } from "@/lib/permissoes";
import { cn } from "@/lib/utils";
import { MemoriaAgentePainel } from "@/components/memoria-agente";
import { PainelCinto } from "@/components/painel-cinto";
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

// Abas do popup amplo (layout `abas`): uma por markdown + Instrumentos (o cinto real)
// + Memórias. O rótulo "Uso dos instrumentos" (tools.md, texto) é distinto da aba
// "Instrumentos" (o cinto) de propósito, para não confundir os dois conceitos.
type AbaChave = ChaveMd | "instrumentos" | "memorias";

const ABAS_MD: {
  chave: ChaveMd;
  rotulo: string;
  descricao: string;
  Icone: LucideIcon;
}[] = [
  {
    chave: "agent_md",
    rotulo: "Quem é",
    descricao: "agent.md — quem o agente é, o que faz",
    Icone: IdCard,
  },
  {
    chave: "skill_md",
    rotulo: "Habilidades",
    descricao: "skill.md — as habilidades dele",
    Icone: Sparkles,
  },
  {
    chave: "tools_md",
    rotulo: "Uso dos instrumentos",
    descricao: "tools.md — como o agente usa os instrumentos do cinto",
    Icone: BookOpen,
  },
  {
    chave: "soul_md",
    rotulo: "Personalidade",
    descricao: "soul.md — personalidade, tom, jeito de falar",
    Icone: Smile,
  },
];

// `live`: aba que muta ao vivo e precisa do agente já criado (desabilitada ao criar).
const ABAS: { chave: AbaChave; rotulo: string; Icone: LucideIcon; live?: boolean }[] =
  [
    ...ABAS_MD.map((a) => ({ chave: a.chave, rotulo: a.rotulo, Icone: a.Icone })),
    { chave: "instrumentos", rotulo: "Instrumentos", Icone: Wrench, live: true },
    { chave: "memorias", rotulo: "Memórias", Icone: Brain, live: true },
  ];

export function FormularioAgente({
  time,
  agente,
  abas = false,
  cinto,
  instrumentosTime,
  tipos,
  meuPapel,
  onSubDrawer,
  onSalvo,
  onCancelar,
}: {
  time: Time;
  agente: Agente | null;
  // Layout `abas` (popup amplo 90×90): cabeçalho fixo + abas (uma por markdown +
  // Instrumentos + Memórias). As props abaixo só são usadas nesse modo.
  abas?: boolean;
  cinto?: Instrumento[];
  instrumentosTime?: Instrumento[];
  tipos?: TipoInstrumento[];
  meuPapel?: PapelAcesso | null;
  onSubDrawer?: (aberto: boolean) => void;
  onSalvo: (salvo: Agente) => void;
  onCancelar: () => void;
}) {
  const [form, setForm] = useState<Campos>(agente ? deAgente(agente) : VAZIO);
  // Snapshot inicial estável para detectar "alterações não salvas" (guarda ao cancelar).
  const [inicial] = useState<Campos>(() => (agente ? deAgente(agente) : VAZIO));
  const [aba, setAba] = useState<AbaChave>("agent_md");
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const souOperador = podeOperar(meuPapel ?? null);
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

  // Guarda anti-perda: básicos + 4 markdowns + config de memória salvam pelo botão
  // (o cinto e as fichas salvam ao vivo, à parte). Ao cancelar com texto alterado e
  // não salvo, confirma antes de descartar.
  const sujo = JSON.stringify(form) !== JSON.stringify(inicial);
  function cancelar() {
    if (sujo && !confirm("Descartar as alterações não salvas dos textos e básicos?")) {
      return;
    }
    onCancelar();
  }

  // Bloco de configuração da memória (liga/desliga + modo). Aparece antes dos markdowns
  // no drawer estreito; dentro da aba "Memórias" no popup amplo.
  const caixaMemoria = (
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
        {abas
          ? "Lembre de Salvar para valer para as execuções."
          : "Edite as fichas na seção “Memórias” do agente."}
      </span>
    </div>
  );

  // Painel da aba ativa (só no modo `abas`). Markdown = editor de altura cheia;
  // Instrumentos = o cinto ao vivo; Memórias = config + fichas.
  function painelAtivo() {
    const md = ABAS_MD.find((a) => a.chave === aba);
    if (md) {
      return (
        <Label className="min-h-0 flex-1 flex-col items-start gap-1">
          <span className="text-xs text-muted-foreground">{md.descricao}</span>
          <Textarea
            className="min-h-0 w-full flex-1 resize-none font-mono"
            value={form[md.chave]}
            onChange={(e) => campo(md.chave, e.target.value)}
          />
        </Label>
      );
    }
    if (!agente) {
      return (
        <p className="text-sm text-muted-foreground">
          Salve o agente primeiro para gerir isto.
        </p>
      );
    }
    if (aba === "instrumentos") {
      return (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <PainelCinto
            agente={agente}
            cinto={cinto ?? []}
            instrumentosTime={instrumentosTime ?? []}
            time={time}
            meuPapel={meuPapel ?? null}
            tipos={tipos}
            onSubDrawer={onSubDrawer}
          />
        </div>
      );
    }
    return (
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
        {caixaMemoria}
        <MemoriaAgentePainel
          agente={agente}
          podeOperar={souOperador}
          memoriaAtiva={form.memoria_ativa}
        />
      </div>
    );
  }

  const cabecalho = (
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
  );

  const barraBotoes = (
    <div className="flex gap-2">
      <Button onClick={salvar} disabled={salvando}>
        {salvando ? "Salvando…" : "Salvar"}
      </Button>
      <Button variant="ghost" onClick={cancelar} disabled={salvando}>
        Cancelar
      </Button>
    </div>
  );

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {erro && <Aviso>{erro}</Aviso>}

      {cabecalho}

      {abas ? (
        <>
          {/* Barra de abas: uma por markdown + Instrumentos + Memórias. Em "criar",
              as abas ao vivo (cinto/memórias) ficam desabilitadas (sem agente ainda). */}
          <nav
            aria-label="Seções do agente"
            className="-mb-px flex gap-1 overflow-x-auto border-b border-border"
          >
            {ABAS.map((a) => {
              const ativa = aba === a.chave;
              const desabilitada = !agente && !!a.live;
              return (
                <button
                  key={a.chave}
                  type="button"
                  disabled={desabilitada}
                  onClick={() => setAba(a.chave)}
                  aria-current={ativa ? "page" : undefined}
                  title={desabilitada ? "Salve o agente primeiro" : undefined}
                  className={cn(
                    "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition-colors",
                    ativa
                      ? "border-primary font-medium text-primary"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                    desabilitada &&
                      "cursor-not-allowed opacity-40 hover:text-muted-foreground",
                  )}
                >
                  <a.Icone className="size-4" />
                  {a.rotulo}
                </button>
              );
            })}
          </nav>

          <div className="flex min-h-0 flex-1 flex-col">{painelAtivo()}</div>
        </>
      ) : (
        <>
          {caixaMemoria}

          {/* Os 4 markdowns DIVIDEM IGUALMENTE o espaço que sobra (cada Label flex-1),
              cada textarea rola por dentro. Salvar/Cancelar ficam sempre visíveis. */}
          <div className="flex min-h-0 flex-1 flex-col gap-3">
            {MARKDOWNS.map(([chave, rotulo]) => (
              <Label
                key={chave}
                className="min-h-0 flex-1 flex-col items-start gap-1"
              >
                {rotulo}
                <Textarea
                  className="min-h-0 w-full flex-1 resize-none font-mono"
                  value={form[chave]}
                  onChange={(e) => campo(chave, e.target.value)}
                />
              </Label>
            ))}
          </div>
        </>
      )}

      {barraBotoes}
    </div>
  );
}
