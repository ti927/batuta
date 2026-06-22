"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  Check,
  CircleHelp,
  Clock,
  Gauge,
  Loader2,
  MessageSquare,
  Pencil,
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
  type Instrumento,
  type PapelAcesso,
  type PassoExecucao,
  type Time,
  type TipoInstrumento,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { rotuloOrigem } from "@/lib/uso";
import { DrawerAgente } from "@/components/drawer-agente";
import { DrawerInstrumento } from "@/components/drawer-instrumento";
import { IconeInstrumento } from "@/components/icone-instrumento";
import { RobotFace } from "@/components/robot-face";

// Quantos instrumentos do cinto cabem na linha do passo antes de virar "+X mais".
const MAX_BADGES_PASSO = 3;
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

// Estados terminais "de exibição": a execução não está avançando sozinha (encerrou
// ou pausou no portão). Usado para avisar o pai (refresh de lista) numa transição.
export const ESTADOS_TERMINAIS = [
  "concluida",
  "falhou",
  "aguardando_humano",
  "cancelada",
];

// Estados FINAIS: a execução encerrou de vez — não há retomada possível. Diferente de
// `aguardando_humano`, que é uma PAUSA: o portão pode ser resolvido POR FORA (ex.:
// resposta pelo Telegram), então a tela CONTINUA acompanhando, para refletir a retomada
// em tempo real — sem precisar de refresh manual.
export const ESTADOS_FINAIS = ["concluida", "falhou", "cancelada"];

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

// ─────────────────────── Two-column: passos + detalhe ───────────────────────
// Lista de passos à esquerda; ao clicar, o detalhe do passo aparece à direita
// (igual à aba Conversas). O "passo final" entra como um item: concluída mostra a
// entrega; FALHOU mostra o erro — assim a falha NÃO some da timeline (mesmo quando
// o passo que quebrou não chegou a ser gravado).

type ItemPasso =
  | {
      tipo: "passo";
      chave: string;
      tom: TomDot;
      indice: number;
      agente: Agente | undefined;
      cinto: Instrumento[];
      passo: PassoExecucao;
    }
  | { tipo: "final"; chave: string; tom: TomDot; rotulo: string };

function construirItens(
  execucao: ExecucaoComPassos,
  agentes: Agente[],
  cintos: Record<string, Instrumento[]>,
): ItemPasso[] {
  const pausado = execucao.estado === "aguardando_humano";
  const itens: ItemPasso[] = execucao.passos.map((p, i) => {
    const ehUltimo = i === execucao.passos.length - 1;
    const idx = agentes.findIndex((a) => a.id === p.agente_id);
    const agente = agentes[idx];
    return {
      tipo: "passo",
      chave: p.id,
      tom: (ehUltimo && pausado ? "espera" : "ok") as TomDot,
      indice: idx >= 0 ? idx : i,
      agente,
      cinto: agente ? (cintos[agente.id] ?? []) : [],
      passo: p,
    };
  });
  const finalPorEstado: Record<string, { tom: TomDot; rotulo: string }> = {
    em_andamento: { tom: "rodando", rotulo: "Rodando o próximo agente…" },
    aguardando: { tom: "fila", rotulo: "Na fila…" },
    concluida: { tom: "ok", rotulo: "Entrega concluída" },
    falhou: { tom: "falha", rotulo: "Falhou" },
  };
  const f = finalPorEstado[execucao.estado];
  if (f) itens.push({ tipo: "final", chave: "final", ...f });
  return itens;
}

function LinhaPasso({
  item,
  selecionado,
  onSelecionar,
  onEditarAgente,
  onEditarInstrumento,
}: {
  item: ItemPasso;
  selecionado: boolean;
  onSelecionar: () => void;
  onEditarAgente?: (agenteId: string) => void;
  onEditarInstrumento?: (instrumentoId: string) => void;
}) {
  const base =
    "flex w-full items-center gap-2.5 px-3 py-2.5 text-left transition-colors";
  const fundo = selecionado ? "bg-accent/60" : "hover:bg-accent/30";
  if (item.tipo === "final") {
    return (
      <button onClick={onSelecionar} className={`${base} ${fundo}`}>
        <Dot tom={item.tom} />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
          {item.rotulo}
        </span>
      </button>
    );
  }
  const { passo, agente, indice, tom } = item;
  const dur = duracao(passo);
  const toks = tokensDoPasso(passo);
  // Cinto do agente deste passo, como badges (mesmo padrão do nó): até
  // MAX_BADGES_PASSO; o excedente vira "+X mais" (abre o drawer do agente).
  const cinto = item.cinto;
  const mostrados =
    cinto.length <= MAX_BADGES_PASSO ? cinto : cinto.slice(0, MAX_BADGES_PASSO - 1);
  const resto = cinto.length - mostrados.length;
  // É um `div` (não `button`) para poder conter o botão do lápis; teclado preservado.
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelecionar}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelecionar();
        }
      }}
      className={`${base} ${fundo} cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40`}
    >
      {/* Lápis: edita o agente deste passo sem sair da execução (flagrou erro,
          corrige ali). Só para passos com agente resolvido. */}
      {agente && onEditarAgente && (
        <button
          type="button"
          title={`Editar o agente “${agente.nome}”`}
          aria-label={`Editar o agente ${agente.nome}`}
          onClick={(e) => {
            e.stopPropagation();
            onEditarAgente(agente.id);
          }}
          className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
        >
          <Pencil className="size-3.5" />
        </button>
      )}
      <span className="relative">
        <RobotFace size={28} indice={indice} lider={agente?.papel === "lider"} />
        {tom === "espera" && (
          <Clock className="absolute -right-1 -top-1 size-3.5 rounded-full bg-background text-[#E89638]" />
        )}
      </span>
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
        {/* Cinto do agente: badges clicáveis (corrige um instrumento sem sair da
            execução), um por linha como no nó da automação. "+X mais" abre o
            drawer do agente (cinto completo). */}
        {cinto.length > 0 && onEditarInstrumento && (
          <span className="mt-1.5 flex flex-col gap-1">
            {mostrados.map((inst) => (
              <button
                key={inst.id}
                type="button"
                title={`Editar o instrumento “${inst.nome}”`}
                onClick={(e) => {
                  e.stopPropagation();
                  onEditarInstrumento(inst.id);
                }}
                className="flex items-center gap-1.5 rounded-md border border-[#ECEAF4] bg-[#FAFAF7] px-1.5 py-1 text-left transition-colors hover:border-[#D9D2F7] hover:bg-[#F4F1FE]"
              >
                <IconeInstrumento
                  icone={inst.icone}
                  className="size-3 flex-none text-[#6D4AFF]"
                />
                <span className="truncate text-[11px] text-[#4A4860]">
                  {inst.nome}
                </span>
              </button>
            ))}
            {resto > 0 && agente && onEditarAgente && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onEditarAgente(agente.id);
                }}
                className="rounded-md px-1.5 py-0.5 text-left text-[11px] font-medium text-[#6D4AFF] hover:underline"
              >
                +{resto} mais…
              </button>
            )}
          </span>
        )}
      </span>
    </div>
  );
}

function DetalheItem({
  item,
  execucao,
}: {
  item: ItemPasso;
  execucao: ExecucaoComPassos;
}) {
  if (item.tipo === "final") {
    if (item.tom === "falha") {
      return (
        <div>
          <p className="text-sm font-medium text-[#C0353A]">Falhou</p>
          <p className="mt-2 whitespace-pre-wrap rounded-lg border border-[#F3C6C8] bg-[#FDECEC] p-3 text-sm text-[#8A2B2F]">
            {execucao.resultado?.erro ||
              "O fluxo falhou. Nada foi entregue pela metade — o erro está registrado."}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            A falha aconteceu no passo seguinte ao último concluído acima — por isso
            ele não aparece como um passo próprio.
          </p>
        </div>
      );
    }
    if (item.tom === "ok") {
      return (
        <div>
          <p className="text-sm font-medium text-foreground">Entrega concluída</p>
          {execucao.resultado?.texto && (
            <p className="mt-2 whitespace-pre-wrap rounded-lg border border-border bg-background p-3 text-sm text-foreground">
              {execucao.resultado.texto}
            </p>
          )}
        </div>
      );
    }
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        {item.tom === "rodando" && <Loader2 className="size-4 animate-spin" />}
        {item.rotulo}
      </p>
    );
  }

  const { passo, agente } = item;
  const dur = duracao(passo);
  const toks = tokensDoPasso(passo);
  const instrumentos = passo.saida?.instrumentos_acionados ?? [];
  return (
    <div className="flex flex-col gap-3">
      <div>
        <h3 className="text-sm font-medium text-foreground">
          {passo.ordem}. {agente?.nome ?? "(agente removido)"}
        </h3>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
          {passo.saida?.saida_escolhida && (
            <span className="text-[#3D2A99]">→ {passo.saida.saida_escolhida}</span>
          )}
          {dur && <span>{dur}</span>}
          {toks > 0 && <span>{toks.toLocaleString("pt-BR")} tok</span>}
        </p>
      </div>
      <Bloco rotulo="Recebeu">{passo.entrada?.texto || "—"}</Bloco>
      {instrumentos.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            Usou instrumentos
          </p>
          <div className="flex flex-wrap gap-1.5">
            {instrumentos.map((n, i) => (
              <span
                key={`${n}-${i}`}
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
  );
}

function Passos({
  execucao,
  agentes,
  cintos,
  onEditarAgente,
  onEditarInstrumento,
}: {
  execucao: ExecucaoComPassos;
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  onEditarAgente?: (agenteId: string) => void;
  onEditarInstrumento?: (instrumentoId: string) => void;
}) {
  const itens = construirItens(execucao, agentes, cintos);
  // Começa no último item (o desfecho — entrega ou falha): é o que o usuário quer
  // ver primeiro ao abrir uma execução encerrada.
  const [sel, setSel] = useState<string | null>(null);
  const selecionado =
    itens.find((i) => i.chave === sel) ?? itens[itens.length - 1] ?? null;

  if (itens.length === 0) {
    return (
      <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
        Esta execução ainda não tem passos.
      </p>
    );
  }

  return (
    <div className="grid gap-3 lg:h-[60vh] lg:grid-cols-[300px_1fr]">
      <div className="overflow-y-auto rounded-lg border border-border bg-card">
        <ul className="divide-y divide-border">
          {itens.map((it) => (
            <li key={it.chave}>
              <LinhaPasso
                item={it}
                selecionado={selecionado?.chave === it.chave}
                onSelecionar={() => setSel(it.chave)}
                onEditarAgente={onEditarAgente}
                onEditarInstrumento={onEditarInstrumento}
              />
            </li>
          ))}
        </ul>
      </div>
      <div className="overflow-y-auto rounded-lg border border-border bg-card p-4">
        {selecionado && <DetalheItem item={selecionado} execucao={execucao} />}
      </div>
    </div>
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
  onCancelar,
  cancelando,
  podeCancelar,
  cintos,
  onEditarAgente,
  onEditarInstrumento,
}: {
  execucao: ExecucaoComPassos;
  automacao: Automacao;
  agentes: Agente[];
  resposta: string;
  setResposta: (v: string) => void;
  respondendo: boolean;
  onResponder: (decisao?: string) => void;
  onCancelar: () => void;
  cancelando: boolean;
  podeCancelar: boolean;
  cintos?: Record<string, Instrumento[]>;
  onEditarAgente?: (agenteId: string) => void;
  onEditarInstrumento?: (instrumentoId: string) => void;
}) {
  // Só dá para cancelar enquanto a execução não encerrou de vez (a fila/portão
  // ainda a tem viva). O backend recusa (409) se já encerrou.
  const cancelavel = !ESTADOS_FINAIS.includes(execucao.estado);
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
        {podeCancelar && cancelavel && (
          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            disabled={cancelando}
            onClick={onCancelar}
          >
            {cancelando ? "Cancelando…" : "Cancelar execução"}
          </Button>
        )}
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
        <Passos
          execucao={execucao}
          agentes={agentes}
          cintos={cintos ?? {}}
          onEditarAgente={onEditarAgente}
          onEditarInstrumento={onEditarInstrumento}
        />
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
  cintos,
  instrumentosTime,
  tipos,
  time,
  conversaId,
}: {
  execucaoId: string;
  automacao: Automacao;
  agentes: Agente[];
  meuPapel: PapelAcesso | null;
  inicial?: ExecucaoComPassos;
  onTerminal?: () => void;
  // Para editar o agente/instrumento de um passo pelo lápis e pelos badges
  // (drawers), sem sair da execução. Opcionais: sem eles, não aparecem.
  cintos?: Record<string, Instrumento[]>;
  instrumentosTime?: Instrumento[];
  tipos?: TipoInstrumento[];
  time?: Time;
  conversaId?: string | null;
}) {
  // O portão (responder) está aberto a observador também; CANCELAR exige operador.
  const podeCancelar = podeOperar(meuPapel);
  // Lápis no passo: só quando temos os dados que o DrawerAgente exige.
  const podeEditarAgente = !!(time && cintos && instrumentosTime);
  // Badge clicável: só quando temos o catálogo de tipos (DrawerInstrumento).
  const podeEditarInstrumento = !!(time && tipos);
  const [editAgenteId, setEditAgenteId] = useState<string | null>(null);
  const [editInstrumentoId, setEditInstrumentoId] = useState<string | null>(null);
  const agenteEdit = editAgenteId
    ? (agentes.find((a) => a.id === editAgenteId) ?? null)
    : null;
  const instrumentoEdit = editInstrumentoId
    ? ((instrumentosTime ?? []).find((i) => i.id === editInstrumentoId) ?? null)
    : null;
  const [execucao, setExecucao] = useState<ExecucaoComPassos | null>(inicial ?? null);
  const [erro, setErro] = useState<string | null>(null);
  const [resposta, setResposta] = useState("");
  const [respondendo, setRespondendo] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Último estado já comunicado ao pai — para avisar (refresh de lista) UMA vez por
  // transição terminal (pausa/encerramento), sem repetir a cada ciclo de poll.
  const ultimoEstadoRef = useRef<string | null>(null);

  function pararPoll() {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }

  function avisarPaiSeTransicao(estado: string) {
    if (ESTADOS_TERMINAIS.includes(estado) && ultimoEstadoRef.current !== estado) {
      onTerminal?.();
    }
    ultimoEstadoRef.current = estado;
  }

  function acompanhar(id: string) {
    pararPoll(); // garante um único laço de poll, venha de onde vier a chamada
    pollRef.current = setTimeout(async () => {
      try {
        const r = await api.get<ExecucaoComPassos>(`/execucoes/${id}`);
        setExecucao(r);
        avisarPaiSeTransicao(r.estado);
        // Para SÓ quando a execução encerra de vez. `aguardando_humano` é uma PAUSA
        // (o portão pode ser resolvido por fora, ex.: Telegram) → segue acompanhando.
        if (ESTADOS_FINAIS.includes(r.estado)) {
          pararPoll();
          return;
        }
      } catch {
        // erro transitório — tenta de novo no próximo ciclo
      }
      acompanhar(id);
    }, 1500);
  }

  // (Re)carrega ao trocar de execução; acompanha enquanto não encerrar de vez (inclui
  // a pausa no portão, que pode ser retomada por fora → atualiza em tempo real).
  useEffect(() => {
    let vivo = true;
    pararPoll();
    (async () => {
      try {
        const r = await api.get<ExecucaoComPassos>(`/execucoes/${execucaoId}`);
        if (!vivo) return;
        setExecucao(r);
        setErro(null);
        ultimoEstadoRef.current = r.estado; // prime: abrir a tela não dispara refresh
        if (!ESTADOS_FINAIS.includes(r.estado)) acompanhar(r.id);
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
      avisarPaiSeTransicao(r.estado);
      if (!ESTADOS_FINAIS.includes(r.estado)) acompanhar(r.id);
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao responder");
    } finally {
      setRespondendo(false);
    }
  }

  async function cancelar() {
    if (!execucao) return;
    setCancelando(true);
    setErro(null);
    try {
      const r = await api.post<ExecucaoComPassos>(
        `/execucoes/${execucao.id}/cancelar`,
        {},
      );
      setExecucao(r);
      pararPoll(); // encerrou de vez — não precisa mais acompanhar
      toast.success("Execução cancelada");
      avisarPaiSeTransicao(r.estado);
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao cancelar");
    } finally {
      setCancelando(false);
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
    <>
      <PainelExecucao
        execucao={execucao}
        automacao={automacao}
        agentes={agentes}
        resposta={resposta}
        setResposta={setResposta}
        respondendo={respondendo}
        onResponder={responder}
        onCancelar={cancelar}
        cancelando={cancelando}
        podeCancelar={podeCancelar}
        cintos={cintos}
        onEditarAgente={
          podeEditarAgente ? (id) => setEditAgenteId(id) : undefined
        }
        onEditarInstrumento={
          podeEditarInstrumento ? (id) => setEditInstrumentoId(id) : undefined
        }
      />

      {/* Editor do agente aberto pelo lápis de um passo — corrigir sem sair daqui. */}
      {agenteEdit && time && (
        <DrawerAgente
          key={agenteEdit.id}
          agente={agenteEdit}
          indice={agentes.findIndex((a) => a.id === agenteEdit.id)}
          cinto={cintos?.[agenteEdit.id] ?? []}
          instrumentosTime={instrumentosTime ?? []}
          time={time}
          meuPapel={meuPapel}
          conversaId={conversaId ?? null}
          onFechar={() => setEditAgenteId(null)}
        />
      )}

      {/* Editor do instrumento aberto por um badge — corrigir sem sair daqui. */}
      {instrumentoEdit && time && tipos && (
        <DrawerInstrumento
          key={instrumentoEdit.id}
          instrumento={instrumentoEdit}
          tipos={tipos}
          time={time}
          meuPapel={meuPapel}
          onFechar={() => setEditInstrumentoId(null)}
          onSalvou={(salvo) => setEditInstrumentoId(salvo.id)}
        />
      )}
    </>
  );
}
