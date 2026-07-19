"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2, Power, RotateCcw, Send, Sparkles, X } from "lucide-react";

import { type MensagemConversa, type SnapshotTime } from "@/lib/api";
import { Button } from "@/components/ui/button";

/**
 * O chat com a IA (criadora/companheira): cabeçalho, mensagens, bloco de ativar/
 * desativar (quando há automação), chips de sugestão e o campo de resposta. É puro
 * de apresentação — o estado e as ações vêm do hook `usarConversaCriacao`. Reusado
 * pela tela de criação e pelo painel do time.
 */
export function ChatCriacao({
  mensagens,
  enviando,
  erro,
  time,
  ativando,
  podeConversar,
  enviar,
  alternarAtivacao,
  atividadeAtual,
  turnoIniciadoEm,
  reconectando,
  reenviar,
  titulo = "IA criadora",
  subtitulo = "Monta e cuida do seu time por conversa",
  aoFechar,
  topo,
}: {
  mensagens: MensagemConversa[];
  enviando: boolean;
  erro: string | null;
  time: SnapshotTime | null;
  ativando: boolean;
  podeConversar: boolean;
  enviar: (conteudo: string) => void;
  alternarAtivacao: () => Promise<boolean | undefined>;
  /** Feedback ao vivo: o que a IA está fazendo agora + quando o turno começou. */
  atividadeAtual?: string | null;
  turnoIniciadoEm?: string | null;
  reconectando?: boolean;
  /** Reenvia a última fala do usuário que falhou. */
  reenviar?: () => void;
  titulo?: string;
  subtitulo?: string;
  aoFechar?: () => void;
  /** Conteúdo opcional entre o cabeçalho e as mensagens (ex.: memória recolhível). */
  topo?: React.ReactNode;
}) {
  const [texto, setTexto] = useState("");
  const automacao = time?.automacao ?? null;
  const ativo = automacao?.ativa ?? false;
  const ultimaIA = [...mensagens].reverse().find((m) => m.papel === "ia");
  const chips = !enviando ? (ultimaIA?.chips ?? []) : [];

  // Campo que cresce com as linhas (até um teto) e volta a uma linha ao enviar.
  const campoRef = useRef<HTMLTextAreaElement>(null);
  function ajustarAltura() {
    const el = campoRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }
  function submeter(conteudo: string) {
    const limpo = conteudo.trim();
    if (!limpo) return;
    enviar(limpo);
    setTexto("");
    if (campoRef.current) campoRef.current.style.height = "auto";
  }

  const fimDoChat = useRef<HTMLDivElement>(null);
  useEffect(() => {
    fimDoChat.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensagens, enviando]);

  async function aoAtivar() {
    const novo = await alternarAtivacao();
    if (typeof novo === "boolean") {
      toast.success(novo ? "Time ativado" : "Time em repouso");
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-card">
      <header className="flex flex-none items-center gap-3 border-b border-border px-4 py-3">
        <span
          className="flex size-9 items-center justify-center rounded-md text-white"
          style={{ background: "linear-gradient(135deg,#6D4AFF,#8A6BFF)" }}
        >
          <Sparkles className="size-4.5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{titulo}</p>
          <p className="truncate text-xs text-muted-foreground">{subtitulo}</p>
        </div>
        {aoFechar && (
          <Button size="icon" variant="ghost" onClick={aoFechar} aria-label="Fechar">
            <X className="size-4" />
          </Button>
        )}
      </header>

      {topo}

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {mensagens.length === 0 && !enviando && (
          <p className="text-sm text-muted-foreground">
            Conte o que você quer que esse time faça. Eu pergunto, monto, e fico por
            aqui para ajustar quando precisar.
          </p>
        )}
        {mensagens.map((m, i) => (
          <Bolha key={i} mensagem={m} />
        ))}
        {enviando && (
          <Digitando
            atividade={reconectando ? "Reconectando…" : (atividadeAtual ?? "Pensando…")}
            desde={turnoIniciadoEm}
          />
        )}
        {erro && (
          <div className="space-y-1.5 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <p>{erro}</p>
            {reenviar && (
              <button
                type="button"
                onClick={reenviar}
                className="inline-flex items-center gap-1.5 rounded-md border border-destructive/30 px-2 py-1 text-xs font-medium text-destructive transition-colors hover:bg-destructive/10"
              >
                <RotateCcw className="size-3" /> Reenviar
              </button>
            )}
          </div>
        )}
        <div ref={fimDoChat} />
      </div>

      {/* Ativar / desativar — só quando há automação montada */}
      {podeConversar && automacao && (
        <div
          className="flex-none border-t border-[#E6DEFB] px-4 py-3"
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
            onClick={aoAtivar}
            disabled={ativando}
          >
            {ativando ? <Loader2 className="animate-spin" /> : <Power />}
            {ativando ? "Aplicando…" : ativo ? "Desativar o time" : "Ativar o time"}
          </Button>
        </div>
      )}

      {/* Chips */}
      {chips.length > 0 && (
        <div className="flex flex-none flex-wrap gap-2 px-4 pb-2">
          {chips.map((c, i) => (
            <button
              key={i}
              onClick={() => submeter(c)}
              className="rounded-full border border-[#D6D3E8] bg-card px-3 py-1 text-xs text-[#3D2A99] transition-colors hover:border-primary hover:bg-[#F4F1FE]"
            >
              {c}
            </button>
          ))}
        </div>
      )}

      {/* Campo de resposta */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submeter(texto);
        }}
        className="flex flex-none items-end gap-2 border-t border-border px-3 py-3"
      >
        <textarea
          ref={campoRef}
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value);
            ajustarAltura();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submeter(texto);
            }
          }}
          rows={1}
          disabled={!podeConversar || enviando}
          placeholder={
            podeConversar
              ? "Conversar com a IA…  (Enter envia, Shift+Enter quebra linha)"
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
    </div>
  );
}

function Bolha({ mensagem }: { mensagem: MensagemConversa }) {
  const ehIA = mensagem.papel === "ia";
  const falhou = mensagem.estado === "falhou";
  return (
    <div className={ehIA ? "flex flex-col items-start" : "flex flex-col items-end"}>
      <p
        className="max-w-[88%] whitespace-pre-wrap px-3.5 py-2 text-sm leading-relaxed"
        style={{
          ...(ehIA
            ? { background: "#F4F1FE", color: "#2A2150", borderRadius: "4px 14px 14px 14px" }
            : { background: "#1A1730", color: "#fff", borderRadius: "14px 14px 4px 14px" }),
          ...(falhou ? { opacity: 0.55 } : {}),
        }}
      >
        {mensagem.conteudo}
      </p>
      {falhou && (
        <span className="mt-0.5 text-xs text-destructive">não enviada</span>
      )}
    </div>
  );
}

// Status ao vivo do turno: "o que a IA está fazendo agora" + um cronômetro correndo, no
// lugar das três bolinhas mudas — a prova visual de que NÃO travou num turno longo.
function Digitando({
  atividade,
  desde,
}: {
  atividade: string;
  desde?: string | null;
}) {
  return (
    <div className="flex">
      <span
        className="flex items-center gap-2 px-3.5 py-2.5 text-sm text-[#5B4B9E]"
        style={{ background: "#F4F1FE", borderRadius: "4px 14px 14px 14px" }}
      >
        <span className="flex items-center gap-1">
          {[0, 0.15, 0.3].map((d) => (
            <span
              key={d}
              className="size-1.5 animate-bounce rounded-full"
              style={{ background: "#B7A8F0", animationDelay: `${d}s` }}
            />
          ))}
        </span>
        <span>{atividade}</span>
        <Cronometro desde={desde} />
      </span>
    </div>
  );
}

// Cronômetro ao vivo ("· 12s") desde `desde`, a cada segundo. Só este pedaço re-renderiza.
function Cronometro({ desde }: { desde?: string | null }) {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  if (!desde) return null;
  const ms = agora - new Date(desde).getTime();
  if (Number.isNaN(ms) || ms < 0) return null;
  const s = Math.floor(ms / 1000);
  const txt =
    s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
  return <span className="tabular-nums text-xs text-[#8A7BC8]">· {txt}</span>;
}
