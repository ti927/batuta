"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Brain, ChevronDown, Loader2, Sparkles } from "lucide-react";

import {
  api,
  mensagemDeErro,
  type ConversaCriacao,
  type Execucao,
} from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { ChatCriacao } from "@/components/conversa-ia/chat";
import { PainelConhecimento } from "@/components/conversa-ia/painel-conhecimento";
import { PainelSobreTime } from "@/components/conversa-ia/painel-sobre-time";
import { useConversaCriacao } from "@/components/conversa-ia/usar-conversa";

// ───────── Contexto: estado do painel da IA, compartilhado pelo time ─────────
// Vive no layout do time (não remonta ao trocar de aba) → a conversa persiste
// enquanto o consultor navega entre Início/Agentes/Automações/etc.

type ConversaTimeCtx = {
  conversaId: string | null;
  timeId: string;
  podeConversar: boolean;
  aberto: boolean;
  abrir: () => void;
  fechar: () => void;
  alternar: () => void;
};

const Ctx = createContext<ConversaTimeCtx | null>(null);

export function useConversaTime(): ConversaTimeCtx {
  return (
    useContext(Ctx) ?? {
      conversaId: null,
      timeId: "",
      podeConversar: false,
      aberto: false,
      abrir: () => {},
      fechar: () => {},
      alternar: () => {},
    }
  );
}

export function ProvedorConversaTime({
  conversaId,
  timeId,
  podeConversar,
  children,
}: {
  conversaId: string | null;
  timeId: string;
  podeConversar: boolean;
  children: React.ReactNode;
}) {
  // Abre já aberto quando se chega pela conversa (ex.: vindo de "Continuar um
  // projeto" / redirect de /criar com ?ia=1). A página do time é dinâmica, então
  // useSearchParams não exige Suspense aqui.
  const aberturaInicial = useSearchParams().get("ia") === "1";
  const [aberto, setAberto] = useState(aberturaInicial && podeConversar);
  return (
    <Ctx.Provider
      value={{
        conversaId,
        timeId,
        podeConversar,
        aberto,
        abrir: () => setAberto(true),
        fechar: () => setAberto(false),
        alternar: () => setAberto((a) => !a),
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

/** Botão do cabeçalho do time que abre/fecha o painel da IA. */
export function BotaoConversarIA() {
  const { podeConversar, aberto, alternar } = useConversaTime();
  if (!podeConversar) return null;
  return (
    <Button variant="outline" onClick={alternar}>
      <Sparkles className="size-4 text-primary" />
      {aberto ? "Fechar a conversa" : "Conversar sobre o projeto"}
    </Button>
  );
}

/**
 * Envolve o conteúdo do time: quando o painel está aberto, renderiza o chat fixo à
 * ESQUERDA (não-modal, sobre o backdrop dos drawers da direita, para o consultor ver
 * a conversa + a aba + o editor de agente/instrumento ao mesmo tempo) e empurra o
 * conteúdo para a direita.
 */
export function AreaConversa({ children }: { children: React.ReactNode }) {
  const { aberto, podeConversar } = useConversaTime();
  const mostrar = aberto && podeConversar;
  return (
    <>
      {mostrar && <PainelConversaTime />}
      <div className={mostrar ? "md:pl-[400px] lg:pl-[420px]" : ""}>{children}</div>
    </>
  );
}

function PainelConversaTime() {
  const { conversaId, timeId, podeConversar, fechar } = useConversaTime();
  const [conversa, setConversa] = useState<ConversaCriacao | null>(null);
  const [execucoes, setExecucoes] = useState<Execucao[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  // Carrega a conversa do time só quando o painel abre (lazy, fora do SSR da aba).
  // Se o time ainda não tem conversa (criado pelo CRUD manual), cria uma amarrada.
  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const c = conversaId
          ? await api.get<ConversaCriacao>(`/conversas-criacao/${conversaId}`)
          : await api.post<ConversaCriacao>(`/times/${timeId}/conversa`, {});
        if (!vivo) return;
        setConversa(c);
        const autoId = c.time?.automacao?.id;
        if (autoId) {
          try {
            const ex = await api.get<Execucao[]>(`/automacoes/${autoId}/execucoes`);
            if (vivo) setExecucoes(ex.slice(0, 5));
          } catch {
            /* execuções são complemento; ignora falha */
          }
        }
      } catch (e) {
        if (vivo) {
          setErro(mensagemDeErro(e, "Não consegui carregar a conversa. Tente de novo."));
        }
      } finally {
        if (vivo) setCarregando(false);
      }
    })();
    return () => {
      vivo = false;
    };
  }, [conversaId, timeId]);

  return (
    <aside className="fixed inset-y-0 left-0 z-[60] flex w-full flex-col border-r border-border bg-card shadow-xl md:left-[246px] md:w-[400px] lg:w-[420px]">
      {carregando ? (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      ) : erro || !conversa ? (
        <div className="flex flex-1 flex-col">
          <div className="flex flex-none items-center justify-between border-b border-border px-4 py-3">
            <span className="text-sm font-medium text-foreground">IA do time</span>
            <Button size="sm" variant="ghost" onClick={fechar}>
              Fechar
            </Button>
          </div>
          <div className="p-4">
            <Aviso>{erro ?? "Não foi possível carregar a conversa."}</Aviso>
          </div>
        </div>
      ) : (
        <ConversaCarregada
          conversa={conversa}
          execucoesIniciais={execucoes}
          podeConversar={podeConversar}
          fechar={fechar}
        />
      )}
    </aside>
  );
}

function ConversaCarregada({
  conversa,
  execucoesIniciais,
  podeConversar,
  fechar,
}: {
  conversa: ConversaCriacao;
  execucoesIniciais: Execucao[];
  podeConversar: boolean;
  fechar: () => void;
}) {
  const router = useRouter();
  const [mostrarMemoria, setMostrarMemoria] = useState(false);

  const c = useConversaCriacao({
    conversaId: conversa.id,
    mensagensIniciais: conversa.mensagens,
    timeInicial: conversa.time,
    memoriaInicial: conversa.memoria ?? [],
    podeConversar,
    turnoInicial: conversa.turno_em_andamento,
    // Cada turno pode ter mexido no time → atualiza o dashboard/cadeia da aba ao vivo.
    aoMudar: () => router.refresh(),
  });

  const memoria = c.time ? (
    <div className="flex-none border-b border-border">
      <button
        onClick={() => setMostrarMemoria((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-accent/50"
      >
        <Brain className="size-4 text-primary" />
        <span className="flex-1 text-left">O que eu sei deste projeto</span>
        <ChevronDown
          className={`size-4 text-muted-foreground transition-transform ${
            mostrarMemoria ? "rotate-180" : ""
          }`}
        />
      </button>
      {mostrarMemoria && (
        <div className="max-h-72 overflow-y-auto px-3 pb-3">
          <PainelSobreTime
            conversaId={conversa.id}
            resumoInicial={conversa.resumo}
            podeEditar={podeConversar}
          />
          <div className="mt-4">
            <PainelConhecimento
              time={c.time}
              execucoes={execucoesIniciais}
              memoria={c.memoria}
              comTitulo={false}
            />
          </div>
        </div>
      )}
    </div>
  ) : null;

  return (
    <ChatCriacao
      mensagens={c.mensagens}
      enviando={c.enviando}
      erro={c.erro}
      time={c.time}
      ativando={c.ativando}
      podeConversar={podeConversar}
      enviar={c.enviar}
      alternarAtivacao={c.alternarAtivacao}
      atividadeAtual={c.atividadeAtual}
      turnoIniciadoEm={c.turnoIniciadoEm}
      reconectando={c.reconectando}
      reenviar={c.reenviar}
      titulo="IA do time"
      subtitulo="Converse para ajustar este time"
      aoFechar={fechar}
      topo={memoria}
    />
  );
}
