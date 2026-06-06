"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  Check,
  ChevronLeft,
  Clock,
  GitBranch,
  Loader2,
  MessageSquare,
  Send,
  Sparkles,
  Trash2,
  Wrench,
  X,
} from "lucide-react";

import { RobotFace } from "@/components/robot-face";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import {
  api,
  ErroDaApi,
  type AgenteRascunho,
  type ConversaCriacao,
  type MaterializacaoResultado,
  type MensagemConversa,
  type PapelAcesso,
  type Rascunho,
  type RespostaTurno,
} from "@/lib/api";

export function CriacaoCliente({
  conversaInicial,
  meuPapel,
}: {
  conversaInicial: ConversaCriacao;
  meuPapel: PapelAcesso | null;
}) {
  const [mensagens, setMensagens] = useState<MensagemConversa[]>(
    conversaInicial.mensagens,
  );
  const [rascunho, setRascunho] = useState<Rascunho>(conversaInicial.rascunho);
  const [estado, setEstado] = useState(conversaInicial.estado);
  const [timeId, setTimeId] = useState(conversaInicial.time_id);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [aprovando, setAprovando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [agenteAberto, setAgenteAberto] = useState<AgenteRascunho | null>(null);
  const [resultado, setResultado] = useState<MaterializacaoResultado | null>(null);

  const fimDoChat = useRef<HTMLDivElement>(null);
  useEffect(() => {
    fimDoChat.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensagens, enviando]);

  const agentes = rascunho.agentes ?? [];
  const montou = Boolean(rascunho.time_nome) || agentes.length > 0;
  const emRascunho = estado === "rascunho";
  const podeConversar = podeOperar(meuPapel) && emRascunho;
  const podeAprovar = podeAdmin(meuPapel) && emRascunho && agentes.length > 0;
  const ultimaIA = [...mensagens].reverse().find((m) => m.papel === "ia");
  const chips = emRascunho && !enviando ? (ultimaIA?.chips ?? []) : [];

  async function enviar(conteudo: string) {
    const limpo = conteudo.trim();
    if (!limpo || enviando || !podeConversar) return;
    setTexto("");
    setErro(null);
    setMensagens((m) => [...m, { papel: "usuario", conteudo: limpo }]);
    setEnviando(true);
    try {
      const r = await api.post<RespostaTurno>(
        `/conversas-criacao/${conversaInicial.id}/mensagens`,
        { mensagem: limpo },
      );
      setMensagens((m) => [
        ...m,
        { papel: "ia", conteudo: r.resposta, chips: r.chips },
      ]);
      setRascunho(r.rascunho);
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao enviar a mensagem.");
    } finally {
      setEnviando(false);
    }
  }

  async function aprovar() {
    if (!podeAprovar || aprovando) return;
    setAprovando(true);
    setErro(null);
    try {
      const r = await api.post<MaterializacaoResultado>(
        `/conversas-criacao/${conversaInicial.id}/aprovar`,
        {},
      );
      setResultado(r);
      setEstado("materializada");
      setTimeId(r.time_id);
    } catch (e) {
      setErro(traduzirErroAprovacao(e));
    } finally {
      setAprovando(false);
    }
  }

  async function descartar() {
    if (!podeConversar) return;
    if (!confirm("Descartar este rascunho? Nada foi criado; a conversa será encerrada."))
      return;
    try {
      await api.post(`/conversas-criacao/${conversaInicial.id}/descartar`, {});
      setEstado("descartada");
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao descartar.");
    }
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-1 flex-col overflow-hidden md:flex-row">
      {/* ───────────── Esquerda: chat ───────────── */}
      <section className="flex h-1/2 w-full flex-col border-b border-border bg-card md:h-full md:w-[440px] md:shrink-0 md:border-r md:border-b-0">
        <header className="flex items-center gap-3 border-b border-border px-4 py-3">
          <span
            className="flex size-9 items-center justify-center rounded-md text-white"
            style={{ background: "linear-gradient(135deg,#6D4AFF,#8A6BFF)" }}
          >
            <Sparkles className="size-4.5" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">
              IA criadora
            </p>
            <p className="truncate text-xs text-muted-foreground">
              Monta seu time por conversa — tudo em rascunho
            </p>
          </div>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {mensagens.length === 0 && !enviando && (
            <p className="text-sm text-muted-foreground">
              Conte o que você quer que esse time faça. Eu proponho a estrutura e
              vou montando do lado direito.
            </p>
          )}
          {mensagens.map((m, i) => (
            <Bolha key={i} mensagem={m} />
          ))}
          {enviando && <Digitando />}

          {estado === "materializada" && (
            <CardSucesso resultado={resultado} timeId={timeId} />
          )}
          {estado === "descartada" && (
            <div className="rounded-lg border border-border bg-muted px-4 py-3 text-sm text-muted-foreground">
              Rascunho descartado. Nada foi criado.{" "}
              <Link href="/criar" className="text-primary hover:underline">
                Começar de novo
              </Link>
            </div>
          )}

          {erro && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {erro}
            </p>
          )}
          <div ref={fimDoChat} />
        </div>

        {/* Card de aprovação */}
        {podeAprovar && (
          <div
            className="border-t border-[#E6DEFB] px-4 py-3"
            style={{ background: "linear-gradient(135deg,#F4F1FE,#FBF7EF)" }}
          >
            <p className="text-sm text-[#2A2150]">
              Tudo em rascunho. Ao aprovar, eu crio o time, os{" "}
              {agentes.length} agente{agentes.length > 1 ? "s" : ""}
              {rascunho.automacao?.cadeia?.inicio ? ", o gatilho e a cadeia" : ""} de
              uma vez.
            </p>
            <Button className="mt-2.5 w-full" onClick={aprovar} disabled={aprovando}>
              {aprovando ? <Loader2 className="animate-spin" /> : <Check />}
              {aprovando ? "Criando o time…" : "Aprovar e criar time"}
            </Button>
          </div>
        )}

        {/* Chips */}
        {chips.length > 0 && (
          <div className="flex flex-wrap gap-2 px-4 pb-2">
            {chips.map((c, i) => (
              <button
                key={i}
                onClick={() => enviar(c)}
                className="rounded-full border border-[#D6D3E8] bg-card px-3 py-1 text-xs text-[#3D2A99] transition-colors hover:border-primary hover:bg-[#F4F1FE]"
              >
                {c}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            enviar(texto);
          }}
          className="flex items-center gap-2 border-t border-border px-3 py-3"
        >
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            disabled={!podeConversar || enviando}
            placeholder={
              estado === "materializada"
                ? "Time criado ✨"
                : podeConversar
                  ? "Responder à IA criadora…"
                  : "Conversa encerrada"
            }
            className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25 disabled:opacity-60"
          />
          <Button
            type="submit"
            size="icon"
            className="size-9"
            disabled={!podeConversar || enviando || !texto.trim()}
            aria-label="Enviar"
          >
            <Send className="size-4" />
          </Button>
        </form>
      </section>

      {/* ───────────── Direita: canvas do rascunho ───────────── */}
      <section className="flex-1 overflow-y-auto bg-background">
        <div className="mx-auto w-full max-w-2xl px-5 py-8 sm:px-8">
          <Link
            href="/criar"
            className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ChevronLeft className="size-4" /> Criação
          </Link>

          {!montou ? (
            <div className="flex flex-col items-center pt-6 pb-2 text-center">
              <Image
                src="/mascote.png"
                alt=""
                width={260}
                height={260}
                className="h-auto w-56"
              />
              <p className="mt-4 text-base font-medium text-foreground">
                O time aparece aqui
              </p>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                Conforme você conversa com a IA criadora, o time vai se montando
                neste painel — peça por peça, em rascunho.
              </p>
            </div>
          ) : (
            <Canvas
              rascunho={rascunho}
              estado={estado}
              onAbrirAgente={setAgenteAberto}
            />
          )}

          {podeConversar && montou && (
            <button
              onClick={descartar}
              className="mt-8 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="size-3.5" /> Descartar rascunho
            </button>
          )}
        </div>
      </section>

      {agenteAberto && (
        <DrawerAgente
          agente={agenteAberto}
          indice={agentes.indexOf(agenteAberto)}
          onFechar={() => setAgenteAberto(null)}
        />
      )}
    </div>
  );
}

// ───────────────────────── Chat ─────────────────────────

function Bolha({ mensagem }: { mensagem: MensagemConversa }) {
  const ehIA = mensagem.papel === "ia";
  return (
    <div className={ehIA ? "flex" : "flex justify-end"}>
      <p
        className="max-w-[88%] whitespace-pre-wrap px-3.5 py-2 text-sm leading-relaxed"
        style={
          ehIA
            ? {
                background: "#F4F1FE",
                color: "#2A2150",
                borderRadius: "4px 14px 14px 14px",
              }
            : {
                background: "#1A1730",
                color: "#fff",
                borderRadius: "14px 14px 4px 14px",
              }
        }
      >
        {mensagem.conteudo}
      </p>
    </div>
  );
}

function Digitando() {
  return (
    <div className="flex">
      <span
        className="flex items-center gap-1 px-3.5 py-3"
        style={{ background: "#F4F1FE", borderRadius: "4px 14px 14px 14px" }}
      >
        {[0, 0.15, 0.3].map((d) => (
          <span
            key={d}
            className="size-1.5 animate-bounce rounded-full"
            style={{ background: "#B7A8F0", animationDelay: `${d}s` }}
          />
        ))}
      </span>
    </div>
  );
}

function CardSucesso({
  resultado,
  timeId,
}: {
  resultado: MaterializacaoResultado | null;
  timeId: string | null;
}) {
  return (
    <div className="rounded-lg border border-[#BBE3C6] bg-[#E6F4EA] px-4 py-3">
      <p className="text-sm font-medium text-[#256B3A]">Time criado! ✨</p>
      <p className="mt-0.5 text-sm text-[#2F7A45]">
        {resultado
          ? `${resultado.agentes} agente(s), ${resultado.instrumentos} instrumento(s)${
              resultado.automacao ? " e a automação" : ""
            }.`
          : "Tudo pronto."}
      </p>
      {timeId && (
        <Link
          href={`/times/${timeId}`}
          className={buttonVariants({ size: "sm", variant: "outline", className: "mt-2.5" })}
        >
          Abrir o time
        </Link>
      )}
    </div>
  );
}

// ───────────────────────── Canvas ─────────────────────────

function RotuloSecao({
  Icone,
  children,
}: {
  Icone: typeof Clock;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-7 mb-3 flex items-center gap-2">
      <Icone className="size-4 text-primary" />
      <span className="text-sm font-medium text-foreground">{children}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

function Canvas({
  rascunho,
  estado,
  onAbrirAgente,
}: {
  rascunho: Rascunho;
  estado: ConversaCriacao["estado"];
  onAbrirAgente: (a: AgenteRascunho) => void;
}) {
  const agentes = rascunho.agentes ?? [];
  const instrumentos = rascunho.instrumentos ?? [];
  const custo = rascunho.custo_estimado;
  const automacao = rascunho.automacao;
  const nomePorRef = (ref: string) =>
    instrumentos.find((i) => i.ref === ref)?.nome ?? "instrumento";

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <h1 className="font-heading text-2xl font-semibold text-foreground">
          {rascunho.time_nome ?? "Time sem nome"}
        </h1>
        <Badge variant={estado === "materializada" ? "success" : "neutral"}>
          {estado === "materializada" ? "ativo" : "rascunho"}
        </Badge>
      </div>
      {rascunho.time_descricao && (
        <p className="mt-1 text-sm text-muted-foreground">
          {rascunho.time_descricao}
        </p>
      )}

      {agentes.length > 0 && (
        <>
          <RotuloSecao Icone={Sparkles}>Agentes · {agentes.length}</RotuloSecao>
          <div className="space-y-2.5">
            {agentes.map((a, i) => (
              <button
                key={a.ref}
                onClick={() => onAbrirAgente(a)}
                className="flex w-full items-start gap-3 rounded-lg border border-border bg-card p-3 text-left transition-all hover:border-[#D6D3E8] hover:shadow-sm"
              >
                <RobotFace size={40} indice={i} lider={a.papel === "lider"} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="font-medium text-foreground">{a.nome}</span>
                    {a.papel === "lider" && (
                      <Badge variant="neutral" className="text-[10px]">
                        líder
                      </Badge>
                    )}
                  </span>
                  {a.agent_md && (
                    <span className="mt-0.5 line-clamp-2 block text-sm text-muted-foreground">
                      {a.agent_md}
                    </span>
                  )}
                  <span className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                    {a.modelo_ia && (
                      <span className="inline-flex items-center gap-1">
                        <Sparkles className="size-3 text-primary" />
                        {a.modelo_ia}
                      </span>
                    )}
                    {a.cinto.map((ref) => (
                      <span
                        key={ref}
                        className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-accent-foreground"
                      >
                        <Wrench className="size-3" />
                        {nomePorRef(ref)}
                      </span>
                    ))}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      {automacao?.gatilho && (
        <>
          <RotuloSecao Icone={Clock}>Gatilho</RotuloSecao>
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
            <span className="flex size-9 items-center justify-center rounded-md bg-accent text-accent-foreground">
              <Clock className="size-4.5" />
            </span>
            <span className="text-sm text-foreground">
              {rotuloGatilho(automacao.gatilho.tipo_gatilho)}
            </span>
          </div>
        </>
      )}

      {automacao?.cadeia?.inicio && (
        <>
          <RotuloSecao Icone={GitBranch}>Cadeia</RotuloSecao>
          <CadeiaVertical cadeia={automacao.cadeia} agentes={agentes} />
        </>
      )}

      {custo && (custo.por_execucao_usd != null || custo.por_mes_usd != null) && (
        <>
          <RotuloSecao Icone={Clock}>Custo estimado</RotuloSecao>
          <div className="flex divide-x divide-border rounded-lg border border-border bg-card">
            <div className="flex-1 p-4 text-center">
              <p className="font-heading text-xl font-semibold text-foreground">
                {fmtUSD(custo.por_execucao_usd)}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">por execução</p>
            </div>
            <div className="flex-1 p-4 text-center">
              <p className="font-heading text-xl font-semibold text-foreground">
                {fmtUSD(custo.por_mes_usd)}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">por mês (est.)</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function CadeiaVertical({
  cadeia,
  agentes,
}: {
  cadeia: NonNullable<Rascunho["automacao"]>["cadeia"];
  agentes: AgenteRascunho[];
}) {
  const nome = (ref: string | null | undefined) =>
    agentes.find((a) => a.ref === ref)?.nome ?? "—";
  // ordem simples: começa no início e segue a primeira saída até o fim/repetição.
  const ordem: string[] = [];
  let atual = cadeia.inicio ?? null;
  const visto = new Set<string>();
  while (atual && cadeia.nos?.[atual] && !visto.has(atual)) {
    ordem.push(atual);
    visto.add(atual);
    const saidas = cadeia.nos[atual].saidas ?? [];
    atual = saidas[0]?.destino ?? null;
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      {ordem.map((ref, i) => {
        const no = cadeia.nos?.[ref];
        const pausa = no?.pausa_humano;
        return (
          <div key={ref}>
            <div className="flex items-center gap-3">
              <RobotFace
                size={28}
                indice={agentes.findIndex((a) => a.ref === ref)}
                lider={agentes.find((a) => a.ref === ref)?.papel === "lider"}
              />
              <span className="text-sm text-foreground">{nome(ref)}</span>
              {pausa && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#FDF1E3] px-2 py-0.5 text-xs text-[#A05E16]">
                  <MessageSquare className="size-3" /> espera você responder
                </span>
              )}
            </div>
            {i < ordem.length - 1 && (
              <span className="ml-3.5 block h-5 w-px bg-[#D6D3E8]" />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ───────────────────────── Drawer do agente ─────────────────────────

const MARKDOWNS: { campo: keyof AgenteRascunho; rotulo: string; arquivo: string }[] = [
  { campo: "agent_md", rotulo: "Quem é", arquivo: "agent.md" },
  { campo: "skill_md", rotulo: "Habilidades", arquivo: "skill.md" },
  { campo: "tools_md", rotulo: "Cinto de instrumentos", arquivo: "tools.md" },
  { campo: "soul_md", rotulo: "Personalidade", arquivo: "soul.md" },
];

function DrawerAgente({
  agente,
  indice,
  onFechar,
}: {
  agente: AgenteRascunho;
  indice: number;
  onFechar: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        className="absolute inset-0 bg-foreground/20"
        onClick={onFechar}
        aria-label="Fechar"
      />
      <aside className="relative flex h-full w-full max-w-[460px] flex-col overflow-y-auto border-l border-border bg-card shadow-xl">
        <header className="flex items-start gap-3 border-b border-border p-4">
          <RobotFace size={44} indice={indice} lider={agente.papel === "lider"} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="font-medium text-foreground">{agente.nome}</h2>
              {agente.papel === "lider" && (
                <Badge variant="neutral" className="text-[10px]">
                  líder
                </Badge>
              )}
              <Badge variant="neutral" className="text-[10px]">
                rascunho
              </Badge>
            </div>
            {agente.modelo_ia && (
              <p className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Sparkles className="size-3 text-primary" />
                {agente.modelo_ia}
              </p>
            )}
          </div>
          <Button
            size="icon"
            variant="ghost"
            onClick={onFechar}
            aria-label="Fechar"
          >
            <X className="size-4" />
          </Button>
        </header>

        <div className="space-y-5 p-4">
          {MARKDOWNS.map(({ campo, rotulo, arquivo }) => {
            const valor = agente[campo] as string | null;
            return (
              <div key={campo}>
                <div className="mb-1.5 flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">
                    {rotulo}
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {arquivo}
                  </span>
                </div>
                <p className="whitespace-pre-wrap rounded-md bg-background p-3 text-sm text-foreground">
                  {valor?.trim() || (
                    <span className="text-muted-foreground/70">
                      (ainda não escrito)
                    </span>
                  )}
                </p>
              </div>
            );
          })}
        </div>
      </aside>
    </div>
  );
}

// ───────────────────────── utilidades ─────────────────────────

function fmtUSD(v: number | null | undefined): string {
  if (v == null) return "—";
  return `US$ ${v.toFixed(v < 1 ? 4 : 2)}`;
}

function rotuloGatilho(tipo: string): string {
  const mapa: Record<string, string> = {
    manual: "Manual (você dispara quando quiser)",
    agendamento: "Por horário (agendado)",
    webhook: "Por webhook (chamada externa)",
  };
  return mapa[tipo] ?? tipo;
}

function traduzirErroAprovacao(e: unknown): string {
  if (e instanceof ErroDaApi) {
    try {
      const corpo = JSON.parse(e.message);
      if (Array.isArray(corpo?.problemas)) {
        return "Ainda falta para aprovar: " + corpo.problemas.join("; ");
      }
    } catch {
      // mensagem não era JSON
    }
    return e.message;
  }
  return "Falha ao aprovar.";
}
