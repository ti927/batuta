"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  Brain,
  ChevronLeft,
  Clock,
  ExternalLink,
  GitBranch,
  Layers,
  Loader2,
  MessageSquare,
  Power,
  Send,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";

import { RobotFace } from "@/components/robot-face";
import { UrlCopiavel } from "@/components/url-copiavel";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { podeOperar } from "@/lib/permissoes";
import {
  api,
  URL_CEREBRO,
  ErroDaApi,
  type AgenteTime,
  type Cadeia,
  type ConversaCriacao,
  type Execucao,
  type MemoriaProjeto,
  type MensagemConversa,
  type PapelAcesso,
  type SnapshotTime,
  type RespostaTurno,
} from "@/lib/api";

export function CriacaoCliente({
  conversaInicial,
  meuPapel,
  primeiraMensagem,
  execucoesRecentes,
}: {
  conversaInicial: ConversaCriacao;
  meuPapel: PapelAcesso | null;
  primeiraMensagem?: string;
  execucoesRecentes: Execucao[];
}) {
  const [mensagens, setMensagens] = useState<MensagemConversa[]>(
    conversaInicial.mensagens,
  );
  const [time, setTime] = useState<SnapshotTime | null>(conversaInicial.time);
  const [memoria, setMemoria] = useState<MemoriaProjeto[]>(
    conversaInicial.memoria ?? [],
  );
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [ativando, setAtivando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [agenteAberto, setAgenteAberto] = useState<AgenteTime | null>(null);

  // O campo de resposta cresce conforme as linhas (até um teto) e volta ao tamanho
  // de uma linha ao enviar.
  const campoRef = useRef<HTMLTextAreaElement>(null);
  function ajustarAltura() {
    const el = campoRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }
  function resetarAltura() {
    if (campoRef.current) campoRef.current.style.height = "auto";
  }

  const fimDoChat = useRef<HTMLDivElement>(null);
  useEffect(() => {
    fimDoChat.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensagens, enviando]);

  // Primeira mensagem (vinda da tela de início via ?primeira=): enviada uma vez,
  // já dentro do chat, para a abertura ser instantânea mesmo com o Opus lento.
  const primeiraEnviada = useRef(false);
  useEffect(() => {
    if (
      primeiraMensagem &&
      !primeiraEnviada.current &&
      conversaInicial.mensagens.length === 0 &&
      podeOperar(meuPapel)
    ) {
      primeiraEnviada.current = true;
      void enviar(primeiraMensagem);
    }
    // só na montagem
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const podeConversar = podeOperar(meuPapel); // a conversa nunca termina
  const agentes = time?.agentes ?? [];
  const instrumentos = time?.instrumentos ?? [];
  const automacao = time?.automacao ?? null;
  const ativo = automacao?.ativa ?? false;
  const montou = time != null;
  const pendentes = instrumentos.flatMap((i) => i.segredos_pendentes);
  const ultimaIA = [...mensagens].reverse().find((m) => m.papel === "ia");
  const chips = !enviando ? (ultimaIA?.chips ?? []) : [];

  async function enviar(conteudo: string) {
    const limpo = conteudo.trim();
    if (!limpo || enviando || !podeConversar) return;
    setTexto("");
    resetarAltura();
    setErro(null);
    setMensagens((m) => [...m, { papel: "usuario", conteudo: limpo }]);
    setEnviando(true);
    try {
      const r = await api.post<RespostaTurno>(
        `/conversas-criacao/${conversaInicial.id}/mensagens`,
        { mensagem: limpo },
      );
      setMensagens((m) => [...m, { papel: "ia", conteudo: r.resposta, chips: r.chips }]);
      setTime(r.time);
      setMemoria(r.memoria ?? []);
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao enviar a mensagem.");
    } finally {
      setEnviando(false);
    }
  }

  async function alternarAtivacao() {
    if (!automacao || ativando || !podeConversar) return;
    setAtivando(true);
    setErro(null);
    try {
      await api.put(`/automacoes/${automacao.id}`, {
        nome: automacao.nome,
        tipo_gatilho: automacao.tipo_gatilho,
        configuracao_gatilho: automacao.configuracao_gatilho ?? {},
        cadeia: automacao.cadeia,
        ativa: !ativo,
      });
      setTime((t) =>
        t && t.automacao
          ? { ...t, automacao: { ...t.automacao, ativa: !ativo } }
          : t,
      );
      toast.success(!ativo ? "Time ativado" : "Time em repouso");
    } catch (e) {
      setErro(traduzirErroParede(e));
    } finally {
      setAtivando(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden md:flex-row">
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
            <p className="truncate text-sm font-medium text-foreground">IA criadora</p>
            <p className="truncate text-xs text-muted-foreground">
              Monta e cuida do seu time por conversa
            </p>
          </div>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {mensagens.length === 0 && !enviando && (
            <p className="text-sm text-muted-foreground">
              Conte o que você quer que esse time faça. Eu pergunto, monto do lado
              direito, e fico por aqui para ajustar quando precisar.
            </p>
          )}
          {mensagens.map((m, i) => (
            <Bolha key={i} mensagem={m} />
          ))}
          {enviando && <Digitando />}

          {erro && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {erro}
            </p>
          )}
          <div ref={fimDoChat} />
        </div>

        {/* Ativar / desativar — só quando há automação montada */}
        {podeConversar && automacao && (
          <div
            className="border-t border-[#E6DEFB] px-4 py-3"
            style={{ background: "linear-gradient(135deg,#F4F1FE,#FBF7EF)" }}
          >
            <p className="text-sm text-[#2A2150]">
              {ativo
                ? "O time está ativo — a automação pode disparar. Você pode continuar ajustando aqui."
                : "Tudo pronto e em repouso. Ative quando quiser que a automação comece a valer."}
            </p>
            <Button
              className="mt-2.5 w-full"
              variant={ativo ? "outline" : "default"}
              onClick={alternarAtivacao}
              disabled={ativando}
            >
              {ativando ? <Loader2 className="animate-spin" /> : <Power />}
              {ativando
                ? "Aplicando…"
                : ativo
                  ? "Desativar o time"
                  : "Ativar o time"}
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
          className="flex items-end gap-2 border-t border-border px-3 py-3"
        >
          <textarea
            ref={campoRef}
            value={texto}
            onChange={(e) => {
              setTexto(e.target.value);
              ajustarAltura();
            }}
            onKeyDown={(e) => {
              // Enter envia; Shift+Enter quebra linha. (isComposing: não envia no
              // meio de um acento/IME.)
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                enviar(texto);
              }
            }}
            rows={1}
            disabled={!podeConversar || enviando}
            placeholder={
              podeConversar
                ? "Responder à IA criadora…  (Enter envia, Shift+Enter quebra linha)"
                : "Somente leitura"
            }
            className="max-h-[200px] min-h-10 flex-1 resize-none overflow-y-auto rounded-md border border-input bg-background px-3 py-2 text-sm leading-relaxed outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25 disabled:opacity-60"
          />
          <Button
            type="submit"
            size="icon"
            className="size-9 shrink-0"
            disabled={!podeConversar || enviando || !texto.trim()}
            aria-label="Enviar"
          >
            <Send className="size-4" />
          </Button>
        </form>
      </section>

      {/* ───────────── Direita: canvas do time ───────────── */}
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
                Conforme você conversa com a IA criadora, o time vai se montando neste
                painel — peça por peça. Nada dispara até você ativar.
              </p>
            </div>
          ) : (
            <Canvas
              time={time!}
              ativo={ativo}
              onAbrirAgente={setAgenteAberto}
            />
          )}

          {montou && pendentes.length > 0 && (
            <div className="mt-6 flex items-start gap-2 rounded-lg border border-[#F3D9A8] bg-[#FDF6EA] px-4 py-3 text-sm text-[#8A5A12]">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <span>
                Faltam {pendentes.length} segredo(s) para os instrumentos funcionarem
                (senhas/tokens). Cadastre em <strong>Chaves e credenciais</strong> (no
                menu lateral) ou direto no instrumento, na tela do time.
              </span>
            </div>
          )}

          {montou && time?.time.id && (
            <Link
              href={`/times/${time.time.id}`}
              className={buttonVariants({
                size: "sm",
                variant: "outline",
                className: "mt-6",
              })}
            >
              <ExternalLink className="size-4" /> Abrir a tela do time
            </Link>
          )}

          {montou && time && (
            <PainelConhecimento
              time={time}
              execucoes={execucoesRecentes}
              memoria={memoria}
            />
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
            ? { background: "#F4F1FE", color: "#2A2150", borderRadius: "4px 14px 14px 14px" }
            : { background: "#1A1730", color: "#fff", borderRadius: "14px 14px 4px 14px" }
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
  time,
  ativo,
  onAbrirAgente,
}: {
  time: SnapshotTime;
  ativo: boolean;
  onAbrirAgente: (a: AgenteTime) => void;
}) {
  const agentes = time.agentes ?? [];
  const instrumentos = time.instrumentos ?? [];
  const automacao = time.automacao;
  const nomePorId = (id: string) =>
    instrumentos.find((i) => i.id === id)?.nome ?? "instrumento";

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <h1 className="font-heading text-2xl font-semibold text-foreground">
          {time.time.nome ?? "Time sem nome"}
        </h1>
        <Badge variant={ativo ? "success" : "neutral"}>
          {ativo ? "ativo" : "em repouso"}
        </Badge>
      </div>
      {time.time.descricao && (
        <p className="mt-1 text-sm text-muted-foreground">{time.time.descricao}</p>
      )}

      {agentes.length > 0 && (
        <>
          <RotuloSecao Icone={Sparkles}>Agentes · {agentes.length}</RotuloSecao>
          <div className="space-y-2.5">
            {agentes.map((a, i) => (
              <button
                key={a.id}
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
                    {a.cinto.map((id) => (
                      <span
                        key={id}
                        className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-accent-foreground"
                      >
                        <Wrench className="size-3" />
                        {nomePorId(id)}
                      </span>
                    ))}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      {automacao && (
        <>
          <RotuloSecao Icone={Clock}>Gatilho</RotuloSecao>
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
            <span className="flex size-9 items-center justify-center rounded-md bg-accent text-accent-foreground">
              <Clock className="size-4.5" />
            </span>
            <span className="text-sm text-foreground">
              {rotuloGatilho(automacao.tipo_gatilho)}
            </span>
          </div>
          {automacao.tipo_gatilho === "webhook" && (
            <div className="mt-2.5">
              <UrlCopiavel
                url={`${URL_CEREBRO}/webhooks/automacoes/${automacao.id}`}
                aviso={
                  ativo
                    ? "Dispare um POST nessa URL para acionar o fluxo."
                    : "A URL só aceita chamadas com o time ativo."
                }
              />
            </div>
          )}
        </>
      )}

      {automacao?.cadeia?.inicio && (
        <>
          <RotuloSecao Icone={GitBranch}>Cadeia</RotuloSecao>
          <CadeiaVertical cadeia={automacao.cadeia} agentes={agentes} />
        </>
      )}
    </div>
  );
}

function CadeiaVertical({
  cadeia,
  agentes,
}: {
  cadeia: Cadeia;
  agentes: AgenteTime[];
}) {
  const nome = (id: string | null | undefined) =>
    agentes.find((a) => a.id === id)?.nome ?? "—";
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
      {ordem.map((id, i) => {
        const no = cadeia.nos?.[id];
        const pausa = no?.pausa_humano;
        return (
          <div key={id}>
            <div className="flex items-center gap-3">
              <RobotFace
                size={28}
                indice={agentes.findIndex((a) => a.id === id)}
                lider={agentes.find((a) => a.id === id)?.papel === "lider"}
              />
              <span className="text-sm text-foreground">{nome(id)}</span>
              {pausa && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#FDF1E3] px-2 py-0.5 text-xs text-[#A05E16]">
                  <MessageSquare className="size-3" /> portão de aprovação
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

// ──────────────── O que eu sei deste projeto (3 camadas) ────────────────
// Painel de conhecimento da IA companheira (handoff §6.6): estado atual
// (consultado ao vivo), últimas execuções (histórico) e decisões lembradas
// (memória de longo prazo destilada).

const ROTULO_CATEGORIA: Record<MemoriaProjeto["categoria"], string> = {
  fato: "Fato",
  decisao: "Decisão",
  preferencia: "Preferência",
};

const ESTADO_EXEC: Record<string, string> = {
  aguardando: "na fila",
  em_andamento: "em andamento",
  aguardando_humano: "aguardando você",
  concluida: "concluída",
  falhou: "falhou",
  cancelada: "cancelada",
};

function dataCurta(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "short",
    });
  } catch {
    return "";
  }
}

function Bolinha() {
  return (
    <span
      className="mt-1.5 size-1.5 shrink-0 rounded-full"
      style={{ background: "#B19CD9" }}
    />
  );
}

function Camada({
  Icone,
  titulo,
  origem,
  vazio,
  children,
}: {
  Icone: typeof Layers;
  titulo: string;
  origem: string;
  vazio?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-3.5">
      <div className="flex items-center gap-2">
        <Icone className="size-4 text-primary" />
        <span className="text-sm font-medium text-foreground">{titulo}</span>
      </div>
      <p className="mb-2.5 mt-0.5 text-[11px] text-muted-foreground">{origem}</p>
      {vazio ? (
        <p className="text-sm text-muted-foreground/70">{children}</p>
      ) : (
        <ul className="space-y-2">{children}</ul>
      )}
    </div>
  );
}

function PainelConhecimento({
  time,
  execucoes,
  memoria,
}: {
  time: SnapshotTime;
  execucoes: Execucao[];
  memoria: MemoriaProjeto[];
}) {
  const automacao = time.automacao;
  const fatos: string[] = [
    `${time.agentes.length} agente(s)`,
    `${time.instrumentos.length} instrumento(s)`,
  ];
  if (automacao) {
    fatos.push(
      automacao.ativa ? "automação ativa" : "automação em repouso",
      `gatilho: ${rotuloGatilho(automacao.tipo_gatilho)}`,
    );
  } else {
    fatos.push("sem automação ainda");
  }

  return (
    <div className="mt-8">
      <RotuloSecao Icone={Brain}>O que eu sei deste projeto</RotuloSecao>
      <div className="flex flex-col gap-2.5">
        {/* Estado atual */}
        <Camada
          Icone={Layers}
          titulo="Estado atual"
          origem="consultado ao vivo no banco"
        >
          {fatos.map((f) => (
            <li key={f} className="flex items-start gap-2.5 text-sm">
              <Bolinha />
              <span className="min-w-0 text-foreground">{f}</span>
            </li>
          ))}
        </Camada>

        {/* Últimas execuções */}
        <Camada
          Icone={Activity}
          titulo="Últimas execuções"
          origem="histórico do projeto"
          vazio={execucoes.length === 0}
        >
          {execucoes.length === 0
            ? "Nenhuma execução ainda."
            : execucoes.map((e) => (
                <li key={e.id} className="flex items-start gap-2.5 text-sm">
                  <Bolinha />
                  <span className="min-w-0 flex-1 text-foreground">
                    <span className="text-[#3D2A99]">
                      {ESTADO_EXEC[e.estado] ?? e.estado}
                    </span>
                    {e.entrada?.texto && (
                      <span className="text-muted-foreground">
                        {" "}
                        — {e.entrada.texto}
                      </span>
                    )}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {dataCurta(e.criado_em)}
                  </span>
                </li>
              ))}
        </Camada>

        {/* Decisões lembradas */}
        <Camada
          Icone={Sparkles}
          titulo="Decisões lembradas"
          origem="memória de longo prazo"
          vazio={memoria.length === 0}
        >
          {memoria.length === 0
            ? "Ainda não registrei nada — peça para eu lembrar de algo."
            : memoria.map((m) => (
                <li key={m.id} className="flex items-start gap-2.5 text-sm">
                  <Bolinha />
                  <span className="min-w-0 text-foreground">
                    <span className="mr-1.5 text-xs font-medium text-[#3D2A99]">
                      {ROTULO_CATEGORIA[m.categoria] ?? "Memória"}
                    </span>
                    {m.conteudo}
                  </span>
                </li>
              ))}
        </Camada>
      </div>
    </div>
  );
}

// ───────────────────────── Drawer do agente ─────────────────────────

const MARKDOWNS: { campo: keyof AgenteTime; rotulo: string; arquivo: string }[] = [
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
  agente: AgenteTime;
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
            </div>
            {agente.modelo_ia && (
              <p className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Sparkles className="size-3 text-primary" />
                {agente.modelo_ia}
              </p>
            )}
          </div>
          <Button size="icon" variant="ghost" onClick={onFechar} aria-label="Fechar">
            <X className="size-4" />
          </Button>
        </header>

        <div className="space-y-5 p-4">
          {MARKDOWNS.map(({ campo, rotulo, arquivo }) => {
            const valor = agente[campo] as string | null;
            return (
              <div key={campo}>
                <div className="mb-1.5 flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">{rotulo}</span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {arquivo}
                  </span>
                </div>
                <p className="whitespace-pre-wrap rounded-md bg-background p-3 text-sm text-foreground">
                  {valor?.trim() || (
                    <span className="text-muted-foreground/70">(ainda não escrito)</span>
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

function rotuloGatilho(tipo: string): string {
  const mapa: Record<string, string> = {
    manual: "Manual (você dispara quando quiser)",
    agendamento: "Por horário (agendado)",
    webhook: "Por webhook (chamada externa)",
  };
  return mapa[tipo] ?? tipo;
}

function traduzirErroParede(e: unknown): string {
  if (e instanceof ErroDaApi) {
    try {
      const corpo = JSON.parse(e.message);
      if (Array.isArray(corpo?.problemas)) {
        return "Não dá para ativar ainda: " + corpo.problemas.join(" ");
      }
    } catch {
      // mensagem não era JSON
    }
    return e.message;
  }
  return "Falha ao ativar o time.";
}
