"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronLeft,
  CircleHelp,
  Clock,
  Gauge,
  ListChecks,
  Loader2,
  MessageSquare,
  ShieldCheck,
  Wrench,
  XCircle,
  Zap,
} from "lucide-react";

import {
  api,
  URL_CEREBRO,
  ErroDaApi,
  type Agente,
  type Automacao,
  type Execucao,
  type ExecucaoComPassos,
  type MensagemCanalLer,
  type PapelAcesso,
  type PassoExecucao,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { rotuloOrigem } from "@/lib/uso";
import { Rise } from "@/components/rise";
import { RobotFace } from "@/components/robot-face";
import { UrlCopiavel } from "@/components/url-copiavel";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

// Estados em que a execução parou de avançar (não há mais o que acompanhar).
const ESTADOS_TERMINAIS = ["concluida", "falhou", "aguardando_humano", "cancelada"];

type VarianteBadge = "neutral" | "info" | "success" | "warning" | "error";
const ESTADO: Record<string, { label: string; variante: VarianteBadge }> = {
  aguardando: { label: "na fila", variante: "neutral" },
  em_andamento: { label: "em andamento", variante: "warning" },
  aguardando_humano: { label: "aguardando você", variante: "info" },
  concluida: { label: "concluída", variante: "success" },
  falhou: { label: "falhou", variante: "error" },
  cancelada: { label: "cancelada", variante: "neutral" },
};

const ROTULO_GATILHO: Record<string, string> = {
  manual: "Manual",
  agendamento: "Por horário",
  webhook: "Por webhook",
  mensagem_recebida: "Por mensagem (canal)",
};

function formatarData(iso: string | null): string {
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
  const mapa: Record<TomDot, { bg: string; fg: string; Icone: typeof Check; spin?: boolean }> = {
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

// ─────────────────────── Passo da timeline ───────────────────────

function PassoNo({
  passo,
  indice,
  agente,
  ultimo,
  tom,
}: {
  passo: PassoExecucao;
  indice: number; // posição do agente (cor do RobotFace)
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

// ─────────────────── Conversa do canal (Telegram etc.) ───────────────────

function ConversaCanal({ mensagens }: { mensagens: MensagemCanalLer[] }) {
  if (mensagens.length === 0) return null;
  return (
    <div className="mt-4">
      <p className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-foreground">
        <MessageSquare className="size-4 text-primary" />
        Conversa do canal
      </p>
      <ul className="flex flex-col gap-1.5">
        {mensagens.map((m) => {
          const entrada = m.direcao === "entrada";
          const temImagem = (m.anexos ?? []).length > 0;
          return (
            <li
              key={m.id}
              className={`flex ${entrada ? "justify-start" : "justify-end"}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                  entrada
                    ? "rounded-bl-sm bg-accent text-accent-foreground"
                    : "rounded-br-sm bg-primary/10 text-foreground"
                }`}
              >
                <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">
                  {entrada ? "recebido" : "enviado"}
                </span>
                {m.texto && <span className="whitespace-pre-wrap">{m.texto}</span>}
                {temImagem && (
                  <span className="mt-0.5 block text-xs italic text-muted-foreground">
                    {m.texto ? "" : "(sem texto) "}📎 imagem anexada
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// Nó final derivado do estado geral da execução (os passos só viram linha quando
// concluídos; o "rodando/aguardando/falhou" é o que vem depois do último passo).
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
        // O último passo de uma execução pausada é o ponto da espera (laranja).
        const tom: TomDot = ehUltimo && pausado ? "espera" : "ok";
        const idx = agentes.findIndex((a) => a.id === p.agente_id);
        return (
          <PassoNo
            key={p.id}
            passo={p}
            indice={idx >= 0 ? idx : i}
            agente={agentes[idx]}
            ultimo={ehUltimo && !["em_andamento", "aguardando", "concluida", "falhou"].includes(execucao.estado)}
            tom={tom}
          />
        );
      })}
      <NoFinal execucao={execucao} />
    </ol>
  );
}

// ─────────────────── Legenda das 3 formas de espera ───────────────────

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
        <div
          key={i.titulo}
          className="rounded-lg border border-border bg-card/60 p-2.5"
        >
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

// ─────────────────── Painel de espera-por-humano ───────────────────

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
  const saidasPausa = ultimo?.agente_id
    ? automacao.cadeia?.nos?.[ultimo.agente_id]?.saidas ?? []
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
                <Button
                  size="sm"
                  disabled={respondendo}
                  onClick={() => onResponder(s.rotulo)}
                >
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

// ───────────────────────── Tela ─────────────────────────

export function AutomacaoDetalheCliente({
  automacao,
  execucoes,
  agentes,
  meuPapel,
}: {
  automacao: Automacao;
  execucoes: Execucao[];
  agentes: Agente[];
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const souOperador = podeOperar(meuPapel);
  const [erro, setErro] = useState<string | null>(null);
  const [entrada, setEntrada] = useState("");
  const [rodando, setRodando] = useState(false);

  const [aberta, setAberta] = useState<ExecucaoComPassos | null>(null);
  const [resposta, setResposta] = useState("");
  const [respondendo, setRespondendo] = useState(false);

  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function pararPoll() {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }

  useEffect(() => pararPoll, []);

  function acompanhar(id: string) {
    pollRef.current = setTimeout(async () => {
      try {
        const r = await api.get<ExecucaoComPassos>(`/execucoes/${id}`);
        setAberta(r);
        if (ESTADOS_TERMINAIS.includes(r.estado)) {
          pararPoll();
          setRodando(false);
          router.refresh();
          return;
        }
      } catch {
        // erro transitório — tenta de novo no próximo ciclo
      }
      acompanhar(id);
    }, 1500);
  }

  const nomeAgente = (id: string | null) =>
    id === null ? "(agente removido)" : agentes.find((a) => a.id === id)?.nome ?? id;

  async function disparar() {
    if (!entrada.trim()) return;
    pararPoll();
    setRodando(true);
    setErro(null);
    try {
      const r = await api.post<ExecucaoComPassos>(
        `/automacoes/${automacao.id}/disparar`,
        { entrada: entrada.trim() },
      );
      setAberta(r);
      setEntrada("");
      if (ESTADOS_TERMINAIS.includes(r.estado)) {
        setRodando(false);
        router.refresh();
      } else {
        acompanhar(r.id);
      }
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao disparar");
      setRodando(false);
    }
  }

  async function abrir(id: string) {
    setErro(null);
    pararPoll();
    try {
      const r = await api.get<ExecucaoComPassos>(`/execucoes/${id}`);
      setAberta(r);
      if (!ESTADOS_TERMINAIS.includes(r.estado)) {
        setRodando(true);
        acompanhar(id);
      }
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao abrir execução");
    }
  }

  async function responder(decisao?: string) {
    const fb = resposta.trim();
    const texto = decisao ? (fb ? `${decisao}: ${fb}` : decisao) : fb;
    if (!aberta || !texto) return;
    setRespondendo(true);
    setErro(null);
    try {
      const r = await api.post<ExecucaoComPassos>(
        `/execucoes/${aberta.id}/responder`,
        { resposta: texto },
      );
      setAberta(r);
      setResposta("");
      toast.success("Decisão enviada");
      if (!ESTADOS_TERMINAIS.includes(r.estado)) {
        setRodando(true);
        acompanhar(r.id);
      }
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao responder");
    } finally {
      setRespondendo(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-[820px] px-4 py-8 sm:px-6">
      <Rise>
      <Link
        href={`/times/${automacao.time_id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Voltar ao time
      </Link>
      <h1 className="mt-2 font-heading text-2xl font-medium text-foreground">
        {automacao.nome}
      </h1>
      <p className="mb-4 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Zap className="size-3.5" />
          {ROTULO_GATILHO[automacao.tipo_gatilho] ?? automacao.tipo_gatilho}
        </span>
        <span className="inline-flex items-center gap-1">
          início: {nomeAgente(automacao.cadeia?.inicio ?? null)}
        </span>
      </p>

      {automacao.tipo_gatilho === "webhook" && (
        <div className="mb-6">
          <p className="mb-1.5 text-sm font-medium text-foreground">URL do webhook</p>
          <UrlCopiavel
            url={`${URL_CEREBRO}/webhooks/automacoes/${automacao.id}`}
            aviso={
              automacao.ativa
                ? "Dispare um POST nessa URL para acionar o fluxo."
                : "A URL só aceita chamadas com o time ativo."
            }
          />
        </div>
      )}

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {souOperador && (
        <div className="mb-6 flex flex-col gap-2 rounded-xl border border-border bg-card p-5">
          <Label>Disparar (teste manual)</Label>
          <Textarea
            className="min-h-20"
            placeholder="Mensagem/tarefa de entrada"
            value={entrada}
            onChange={(e) => setEntrada(e.target.value)}
          />
          <Button className="self-start" onClick={disparar} disabled={rodando}>
            {rodando ? "Executando…" : "Disparar"}
          </Button>
        </div>
      )}

      {aberta && (
        <div className="mb-6 rounded-xl border border-border bg-card p-5">
          {/* Cabeçalho da execução */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h2 className="font-heading text-lg font-medium text-foreground">
              Execução{" "}
              <span className="font-mono text-base text-muted-foreground">
                #{aberta.id.slice(0, 8)}
              </span>
            </h2>
            <Badge variant={ESTADO[aberta.estado]?.variante ?? "neutral"}>
              {ESTADO[aberta.estado]?.label ?? aberta.estado}
            </Badge>
          </div>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Clock className="size-3.5" />
              {formatarData(aberta.criado_em)}
            </span>
            {aberta.uso && aberta.uso.custo_usd > 0 && (
              <span className="inline-flex items-center gap-1">
                <Gauge className="size-3.5" />~US$ {aberta.uso.custo_usd.toFixed(4)}
              </span>
            )}
          </p>

          {/* Painel de aprovação (espera-por-humano) */}
          {aberta.estado === "aguardando_humano" && (
            <PainelAprovacao
              aberta={aberta}
              automacao={automacao}
              resposta={resposta}
              setResposta={setResposta}
              respondendo={respondendo}
              onResponder={responder}
            />
          )}

          {/* Timeline */}
          <div className="mt-4">
            <Timeline execucao={aberta} agentes={agentes} />
          </div>

          {/* Conversa do canal (quando a execução trocou mensagens por um canal) */}
          <ConversaCanal mensagens={aberta.mensagens_canal ?? []} />

          {/* Uso */}
          {aberta.uso && aberta.uso.tokens_entrada + aberta.uso.tokens_saida > 0 && (
            <div className="mt-2 rounded-lg border border-border bg-background p-2.5 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Uso (estimado):</span>{" "}
              {aberta.uso.tokens_entrada.toLocaleString("pt-BR")} entrada +{" "}
              {aberta.uso.tokens_saida.toLocaleString("pt-BR")} saída tokens · ~US${" "}
              {aberta.uso.custo_usd.toFixed(4)}
              {Object.keys(aberta.uso.por_origem ?? {}).length > 0 && (
                <span>
                  {" · "}
                  {Object.entries(aberta.uso.por_origem)
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
      )}

      <h2 className="mb-2 text-sm font-medium text-foreground">
        Execuções anteriores
      </h2>
      {execucoes.length === 0 ? (
        <EstadoVazio icone={ListChecks} titulo="Nenhuma execução ainda.">
          Dispare a automação acima para ver o passo a passo aqui.
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
          {execucoes.map((e) => (
            <li key={e.id} className="flex items-center gap-3 p-3 text-sm">
              <Badge variant={ESTADO[e.estado]?.variante ?? "neutral"}>
                {ESTADO[e.estado]?.label ?? e.estado}
              </Badge>
              <span className="min-w-0 flex-1 truncate text-muted-foreground">
                {e.entrada?.texto}
              </span>
              <span className="hidden whitespace-nowrap text-xs text-muted-foreground sm:block">
                {formatarData(e.criado_em)}
              </span>
              <Button size="sm" variant="outline" onClick={() => abrir(e.id)}>
                Ver passos
              </Button>
            </li>
          ))}
        </ul>
      )}
      </Rise>
    </main>
  );
}
