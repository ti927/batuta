"use client";

import Image from "next/image";
import Link from "next/link";
import {
  AlertTriangle,
  ChevronLeft,
  Clock,
  ExternalLink,
  GitBranch,
  MessageSquare,
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
  URL_CEREBRO,
  caminhoPrincipal,
  inicialDaCadeia,
  type AgenteTime,
  type InstrumentoTime,
  type Cadeia,
  type ConversaCriacao,
  type Execucao,
  type PapelAcesso,
  type SnapshotTime,
} from "@/lib/api";
import { ChatCriacao } from "@/components/conversa-ia/chat";
import { PainelConhecimento } from "@/components/conversa-ia/painel-conhecimento";
import { PainelSobreTime } from "@/components/conversa-ia/painel-sobre-time";
import { RotuloSecao, rotuloGatilho } from "@/components/conversa-ia/comum";
import { useConversaCriacao } from "@/components/conversa-ia/usar-conversa";
import { useState } from "react";

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
  const podeConversar = podeOperar(meuPapel); // a conversa nunca termina
  const [agenteAberto, setAgenteAberto] = useState<AgenteTime | null>(null);

  const conversa = useConversaCriacao({
    conversaId: conversaInicial.id,
    mensagensIniciais: conversaInicial.mensagens,
    timeInicial: conversaInicial.time,
    memoriaInicial: conversaInicial.memoria ?? [],
    podeConversar,
    primeiraMensagem,
    turnoInicial: conversaInicial.turno_em_andamento,
  });

  const time = conversa.time;
  const agentes = time?.agentes ?? [];
  const instrumentos = time?.instrumentos ?? [];
  const automacao = time?.automacao ?? null;
  const ativo = automacao?.ativa ?? false;
  const montou = time != null;
  const pendentes = instrumentos.flatMap((i) => i.segredos_pendentes);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden md:flex-row">
      {/* ───────────── Esquerda: chat ───────────── */}
      <section className="flex h-1/2 w-full flex-col border-b border-border md:h-full md:w-[440px] md:shrink-0 md:border-r md:border-b-0">
        <ChatCriacao
          mensagens={conversa.mensagens}
          enviando={conversa.enviando}
          erro={conversa.erro}
          time={time}
          ativando={conversa.ativando}
          podeConversar={podeConversar}
          enviar={conversa.enviar}
          alternarAtivacao={conversa.alternarAtivacao}
          atividadeAtual={conversa.atividadeAtual}
          turnoIniciadoEm={conversa.turnoIniciadoEm}
          reconectando={conversa.reconectando}
          reenviar={conversa.reenviar}
        />
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
            <Canvas time={time!} ativo={ativo} onAbrirAgente={setAgenteAberto} />
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
            <>
              <PainelSobreTime
                conversaId={conversaInicial.id}
                resumoInicial={conversaInicial.resumo}
                podeEditar={podeConversar}
              />
              <PainelConhecimento
                time={time}
                execucoes={execucoesRecentes}
                memoria={conversa.memoria}
              />
            </>
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

// ───────────────────────── Canvas ─────────────────────────

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

      {automacao?.cadeia && inicialDaCadeia(automacao.cadeia) && (
        <>
          <RotuloSecao Icone={GitBranch}>Cadeia</RotuloSecao>
          <CadeiaVertical
            cadeia={automacao.cadeia}
            agentes={agentes}
            instrumentos={instrumentos}
          />
        </>
      )}
    </div>
  );
}

function CadeiaVertical({
  cadeia,
  agentes,
  instrumentos,
}: {
  cadeia: Cadeia;
  agentes: AgenteTime[];
  instrumentos: InstrumentoTime[];
}) {
  const nome = (id: string | null | undefined) =>
    agentes.find((a) => a.id === id)?.nome ?? "—";
  const ordem = caminhoPrincipal(cadeia);

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      {ordem.map((no, i) => {
        // Pode parar para uma pessoa: derivado do CINTO do agente (o instrumento de
        // pedir aprovação), não de um interruptor no desenho.
        const pausa = (agentes.find((a) => a.id === no.ref)?.cinto ?? []).some(
          (id) => instrumentos.find((i) => i.id === id)?.tipo === "pedir_aprovacao",
        );
        const rotulo =
          no.tipo === "roteador" ? (no.nome ?? "Roteador") : nome(no.ref);
        return (
          <div key={no.id}>
            <div className="flex items-center gap-3">
              <RobotFace
                size={28}
                indice={agentes.findIndex((a) => a.id === no.ref)}
                lider={agentes.find((a) => a.id === no.ref)?.papel === "lider"}
              />
              <span className="text-sm text-foreground">{rotulo}</span>
              {pausa && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#FDF1E3] px-2 py-0.5 text-xs text-[#A05E16]">
                  <MessageSquare className="size-3" /> pode esperar você
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

// ───────────────────────── Drawer do agente (leitura) ─────────────────────────

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
