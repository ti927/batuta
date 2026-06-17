"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  CircleHelp,
  Clock,
  Gauge,
  Loader2,
  MessageSquare,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";

import {
  api,
  ErroDaApi,
  indexarCadeia,
  type Agente,
  type Automacao,
  type ExecucaoComPassos,
  type PapelAcesso,
  type PassoExecucao,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { rotuloOrigem } from "@/lib/uso";
import { RobotFace } from "@/components/robot-face";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

// Estados em que a execução parou de avançar (não há mais o que acompanhar).
export const ESTADOS_TERMINAIS = [
  "concluida",
  "falhou",
  "aguardando_humano",
  "cancelada",
];

type VarianteBadge = "neutral" | "info" | "success" | "warning" | "error";
export const ESTADO: Record<string, { label: string; variante: VarianteBadge }> = {
  aguardando: { label: "na fila", variante: "neutral" },
  em_andamento: { label: "em andamento", variante: "warning" },
  aguardando_humano: { label: "aguardando você", variante: "info" },
  concluida: { label: "concluída", variante: "success" },
  falhou: { label: "falhou", variante: "error" },
  cancelada: { label: "cancelada", variante: "neutral" },
};

export function formatarData(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function duracao(p: PassoExecucao): string | null {
  if (!p.iniciado_em || !p.finalizado_em) return null;
  const ms = new Date(p.finalizado_em).getTime() - new Date(p.iniciado_em).getTime();
  if (Number.isNaN(ms) || ms < 0) return null;
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function tokensDoPasso(p: PassoExecucao): number {
  return (p.saida?.uso ?? []).reduce(
    (s, u) => s + u.tokens_entrada + u.tokens_saida,
    0,
  );
}

// ─────────────────────── Ponto da timeline (dot) ───────────────────────

type TomDot = "ok" | "rodando" | "espera" | "falha" | "fila";

function Dot({ tom }: { tom: TomDot }) {
  const mapa: Record<
    TomDot,
    { bg: string; fg: string; Icone: typeof Check; spin?: boolean }
  > = {
    ok: { bg: "#E6F4EA", fg: "#3DAA5C", Icone: Check },
    rodando: { bg: "#EFEAFF", fg: "#6D4AFF", Icone: Loader2, spin: true },
    espera: { bg: "#FDF1E3", fg: "#E89638", Icone: Clock },
    falha: { bg: "#FDECEC", fg: "#E5484D", Icone: XCircle },
    fila: { bg: "#EEEDF3", fg: "#8A86A6", Icone: Clock },
  };
  const { bg, fg, Icone, spin } = mapa[tom];
  return (
    <span
      className="z-10 flex size-7 shrink-0 items-center justify-center rounded-full ring-4 ring-background"
      style={{ background: bg }}
    >
      <Icone className={`size-4 ${spin ? "animate-spin" : ""}`} style={{ color: fg }} />
    </span>
  );
}

function Bloco({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-muted-foreground">{rotulo}</p>
      <p className="whitespace-pre-wrap rounded-md bg-card p-2.5 text-sm text-foreground">
        {children}
      </p>
    </div>
  );
}

function PassoNo({
  passo,
  indice,
  agente,
  ultimo,
  tom,
}: {
  passo: PassoExecucao;
  indice: number;
  agente: Agente | undefined;
  ultimo: boolean;
  tom: TomDot;
}) {
  const [aberto, setAberto] = useState(false);
  const toks = tokensDoPasso(passo);
  const dur = duracao(passo);
  return (
    <li className="relative flex gap-3 pb-4">
      {!ultimo && (
        <span className="absolute left-3.5 top-7 -ml-px h-full w-0.5 bg-[#EDEBF4]" />
      )}
      <Dot tom={tom} />
      <div className="min-w-0 flex-1">
        <button
          onClick={() => setAberto((v) => !v)}
          className="flex w-full items-center gap-2.5 rounded-lg border border-border bg-card px-3 py-2 text-left transition-colors hover:bg-accent/40"
        >
          <RobotFace size={26} indice={indice} lider={agente?.papel === "lider"} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-foreground">
              {passo.ordem}. {agente?.nome ?? "(agente removido)"}
            </span>
            <span className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
              {passo.saida?.saida_escolhida && (
                <span className="text-[#3D2A99]">→ {passo.saida.saida_escolhida}</span>
              )}
              {dur && <span>{dur}</span>}
              {toks > 0 && <span>{toks.toLocaleString("pt-BR")} tok</span>}
            </span>
          </span>
          {(passo.saida?.instrumentos_acionados ?? []).length > 0 && (
            <Wrench className="size-3.5 shrink-0 text-muted-foreground" />
          )}
          <ChevronDown
            className={`size-4 shrink-0 text-muted-foreground/60 transition-transform ${aberto ? "" : "-rotate-90"}`}
          />
        </button>

        {aberto && (
          <div className="mt-1.5 flex flex-col gap-2.5 rounded-lg border border-border bg-background p-3 text-sm">
            <Bloco rotulo="Recebeu">{passo.entrada?.texto || "—"}</Bloco>
            {(passo.saida?.instrumentos_acionados ?? []).length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">
                  Usou instrumentos
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {passo.saida!.instrumentos_acionados!.map((n) => (
                    <span
                      key={n}
                      className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-xs text-accent-foreground"
                    >
                      <Wrench className="size-3" />
                      {n}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <Bloco rotulo="Produziu">{passo.saida?.texto || "—"}</Bloco>
          </div>
        )}
      </div>
    </li>
  );
}

function NoFinal({ execucao }: { execucao: ExecucaoComPassos }) {
  const e = execucao.estado;
  if (e === "em_andamento" || e === "aguardando") {
    return (
      <li className="flex items-center gap-3">
        <Dot tom={e === "em_andamento" ? "rodando" : "fila"} />
        <span className="text-sm text-muted-foreground">
          {e === "em_andamento"
            ? "Rodando o próximo agente…"
            : "Na fila, aguardando um trabalhador…"}
        </span>
      </li>
    );
  }
  if (e === "concluida") {
    return (
      <li className="flex items-start gap-3">
        <Dot tom="ok" />
        <div className="min-w-0 flex-1">
          <p className="pt-1 text-sm font-medium text-foreground">Entrega concluída</p>
          {execucao.resultado?.texto && (
            <p className="mt-1.5 whitespace-pre-wrap rounded-lg border border-border bg-card p-3 text-sm text-foreground">
              {execucao.resultado.texto}
            </p>
          )}
        </div>
      </li>
    );
  }
  if (e === "falhou") {
    return (
      <li className="flex items-start gap-3">
        <Dot tom="falha" />
        <div className="min-w-0 flex-1">
          <p className="pt-1 text-sm font-medium text-[#C0353A]">Falhou</p>
          <p className="mt-1.5 rounded-lg border border-[#F3C6C8] bg-[#FDECEC] p-3 text-sm text-[#8A2B2F]">
            {execucao.resultado?.erro ||
              "O fluxo falhou. Nada foi entregue pela metade — o erro está registrado."}
          </p>
        </div>
      </li>
    );
  }
  return null;
}

function Timeline({
  execucao,
  agentes,
}: {
  execucao: ExecucaoComPassos;
  agentes: Agente[];
}) {
  const pausado = execucao.estado === "aguardando_humano";
  return (
    <ol className="mt-1">
      {execucao.passos.map((p, i) => {
        const ehUltimo = i === execucao.passos.length - 1;
        const tom: TomDot = ehUltimo && pausado ? "espera" : "ok";
        const idx = agentes.findIndex((a) => a.id === p.agente_id);
        return (
          <PassoNo
            key={p.id}
            passo={p}
            indice={idx >= 0 ? idx : i}
            agente={agentes[idx]}
            ultimo={
              ehUltimo &&
              !["em_andamento", "aguardando", "concluida", "falhou"].includes(
                execucao.estado,
              )
            }
            tom={tom}
          />
        );
      })}
      <NoFinal execucao={execucao} />
    </ol>
  );
}

function LegendaEsperas() {
  const itens: { Icone: typeof CircleHelp; titulo: string; texto: string }[] = [
    {
      Icone: CircleHelp,
      titulo: "Pergunta pontual",
      texto: "o agente precisa de um dado e pergunta.",
    },
    {
      Icone: ShieldCheck,
      titulo: "Portão de aprovação",
      texto: "uma ação importante espera o seu ok.",
    },
    {
      Icone: AlertTriangle,
      titulo: "Baixa confiança",
      texto: "o agente não tem certeza e confirma antes.",
    },
  ];
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-3">
      {itens.map((i) => (
        <div key={i.titulo} className="rounded-lg border border-border bg-card/60 p-2.5">
          <p className="flex items-center gap-1.5 text-xs font-medium text-foreground">
            <i.Icone className="size-3.5 text-primary" />
            {i.titulo}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">{i.texto}</p>
        </div>
      ))}
    </div>
  );
}

function PainelAprovacao({
  aberta,
  automacao,
  resposta,
  setResposta,
  respondendo,
  onResponder,
}: {
  aberta: ExecucaoComPassos;
  automacao: Automacao;
  resposta: string;
  setResposta: (v: string) => void;
  respondendo: boolean;
  onResponder: (decisao?: string) => void;
}) {
  const ultimo = aberta.passos[aberta.passos.length - 1];
  // O nó pausado é localizado por id de nó (fallback ao agente, p/ execuções antigas).
  const noPausado = ultimo?.no_id ?? ultimo?.agente_id ?? null;
  const saidasPausa = noPausado
    ? (indexarCadeia(automacao.cadeia)[noPausado]?.saidas ?? [])
    : [];
  return (
    <div className="mt-4">
      <div
        className="flex flex-col gap-3 rounded-xl border border-[#F0E2C0] p-4"
        style={{ background: "linear-gradient(180deg,#FDF6EA 0%,#FBF1FE 100%)" }}
      >
        <span className="flex items-center gap-2 text-sm font-medium text-[#8A5A12]">
          <MessageSquare className="size-4" />O fluxo está esperando você
        </span>
        <p className="whitespace-pre-wrap rounded-lg border border-[#EFE4C8] bg-white/70 p-3 text-sm text-foreground">
          {ultimo?.saida?.texto}
        </p>
        <Textarea
          className="min-h-16 bg-white/70"
          placeholder={
            saidasPausa.length > 0
              ? "Feedback (opcional) — acompanha a decisão que você escolher"
              : "Sua resposta"
          }
          value={resposta}
          onChange={(e) => setResposta(e.target.value)}
        />
        {saidasPausa.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            {saidasPausa.map((s) => (
              <div key={s.rotulo} className="flex items-center gap-2">
                <Button size="sm" disabled={respondendo} onClick={() => onResponder(s.rotulo)}>
                  {s.rotulo}
                </Button>
                <span className="text-xs text-muted-foreground">{s.quando}</span>
              </div>
            ))}
          </div>
        ) : (
          <Button
            className="self-start"
            onClick={() => onResponder()}
            disabled={respondendo}
          >
            {respondendo ? "Retomando…" : "Responder e retomar"}
          </Button>
        )}
      </div>
      <LegendaEsperas />
    </div>
  );
}

// ─────────────── Painel da execução (cabeçalho + portão + timeline + uso) ───────────────

export function PainelExecucao({
  execucao,
  automacao,
  agentes,
  resposta,
  setResposta,
  respondendo,
  onResponder,
}: {
  execucao: ExecucaoComPassos;
  automacao: Automacao;
  agentes: Agente[];
  resposta: string;
  setResposta: (v: string) => void;
  respondendo: boolean;
  onResponder: (decisao?: string) => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 className="font-heading text-lg font-medium text-foreground">
          Execução{" "}
          <span className="font-mono text-base text-muted-foreground">
            #{execucao.id.slice(0, 8)}
          </span>
        </h2>
        <Badge variant={ESTADO[execucao.estado]?.variante ?? "neutral"}>
          {ESTADO[execucao.estado]?.label ?? execucao.estado}
        </Badge>
      </div>
      <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Clock className="size-3.5" />
          {formatarData(execucao.criado_em)}
        </span>
        {execucao.uso && execucao.uso.custo_usd > 0 && (
          <span className="inline-flex items-center gap-1">
            <Gauge className="size-3.5" />~US$ {execucao.uso.custo_usd.toFixed(4)}
          </span>
        )}
      </p>

      {execucao.estado === "aguardando_humano" && (
        <PainelAprovacao
          aberta={execucao}
          automacao={automacao}
          resposta={resposta}
          setResposta={setResposta}
          respondendo={respondendo}
          onResponder={onResponder}
        />
      )}

      <div className="mt-4">
        <Timeline execucao={execucao} agentes={agentes} />
      </div>

      {execucao.uso && execucao.uso.tokens_entrada + execucao.uso.tokens_saida > 0 && (
        <div className="mt-2 rounded-lg border border-border bg-background p-2.5 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Uso (estimado):</span>{" "}
          {execucao.uso.tokens_entrada.toLocaleString("pt-BR")} entrada +{" "}
          {execucao.uso.tokens_saida.toLocaleString("pt-BR")} saída tokens · ~US${" "}
          {execucao.uso.custo_usd.toFixed(4)}
          {Object.keys(execucao.uso.por_origem ?? {}).length > 0 && (
            <span>
              {" · "}
              {Object.entries(execucao.uso.por_origem)
                .map(
                  ([origem, u]) =>
                    `${rotuloOrigem(origem)} ~US$${u.custo_usd.toFixed(4)}`,
                )
                .join(" · ")}
            </span>
          )}
          <div className="mt-1 text-muted-foreground/70">
            Custo aproximado, apenas informativo — não é cobrança.
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────── Inspeção autônoma (busca + poll + portão) ───────────────

/**
 * Inspeciona UMA execução, ao vivo: busca por id, acompanha (poll a cada 1,5s)
 * enquanto roda, e resolve o portão de aprovação (espera-por-humano). Reusado
 * pela aba Execuções do time e pela tela da automação. `onTerminal` avisa o pai
 * (ex.: para `router.refresh()` listas) quando a execução encerra.
 */
export function InspecaoExecucao({
  execucaoId,
  automacao,
  agentes,
  meuPapel,
  inicial,
  onTerminal,
}: {
  execucaoId: string;
  automacao: Automacao;
  agentes: Agente[];
  meuPapel: PapelAcesso | null;
  inicial?: ExecucaoComPassos;
  onTerminal?: () => void;
}) {
  // souOperador não muda o portão (observador também responde), mas mantém a
  // assinatura coerente caso uma futura ação peça operador.
  void podeOperar(meuPapel);
  const [execucao, setExecucao] = useState<ExecucaoComPassos | null>(inicial ?? null);
  const [erro, setErro] = useState<string | null>(null);
  const [resposta, setResposta] = useState("");
  const [respondendo, setRespondendo] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function pararPoll() {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }

  function acompanhar(id: string) {
    pollRef.current = setTimeout(async () => {
      try {
        const r = await api.get<ExecucaoComPassos>(`/execucoes/${id}`);
        setExecucao(r);
        if (ESTADOS_TERMINAIS.includes(r.estado)) {
          pararPoll();
          onTerminal?.();
          return;
        }
      } catch {
        // erro transitório — tenta de novo no próximo ciclo
      }
      acompanhar(id);
    }, 1500);
  }

  // (Re)carrega ao trocar de execução; inicia o poll se ainda estiver viva.
  useEffect(() => {
    let vivo = true;
    pararPoll();
    (async () => {
      try {
        const r = await api.get<ExecucaoComPassos>(`/execucoes/${execucaoId}`);
        if (!vivo) return;
        setExecucao(r);
        setErro(null);
        if (!ESTADOS_TERMINAIS.includes(r.estado)) acompanhar(r.id);
      } catch (e) {
        if (vivo) setErro(e instanceof ErroDaApi ? e.message : "Falha ao carregar a execução");
      }
    })();
    return () => {
      vivo = false;
      pararPoll();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [execucaoId]);

  async function responder(decisao?: string) {
    const fb = resposta.trim();
    const texto = decisao ? (fb ? `${decisao}: ${fb}` : decisao) : fb;
    if (!execucao || !texto) return;
    setRespondendo(true);
    setErro(null);
    try {
      const r = await api.post<ExecucaoComPassos>(
        `/execucoes/${execucao.id}/responder`,
        { resposta: texto },
      );
      setExecucao(r);
      setResposta("");
      toast.success("Decisão enviada");
      if (!ESTADOS_TERMINAIS.includes(r.estado)) acompanhar(r.id);
      onTerminal?.();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao responder");
    } finally {
      setRespondendo(false);
    }
  }

  if (erro) return <Aviso>{erro}</Aviso>;
  if (!execucao)
    return (
      <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Carregando a execução…
      </div>
    );

  return (
    <PainelExecucao
      execucao={execucao}
      automacao={automacao}
      agentes={agentes}
      resposta={resposta}
      setResposta={setResposta}
      respondendo={respondendo}
      onResponder={responder}
    />
  );
}
