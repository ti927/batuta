"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Maximize2, Minimize2, Pencil, Sparkles, Trash2, X } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Agente,
  type Instrumento,
  type PapelAcesso,
  type Time,
  type TipoInstrumento,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { chaveRascunho, limparRascunho } from "@/lib/rascunho-agente";
import { useConversaTime } from "@/components/conversa-ia/painel-time";
import { FormularioAgente } from "@/components/formulario-agente";
import { MemoriaAgentePainel } from "@/components/memoria-agente";
import { PainelCinto } from "@/components/painel-cinto";
import { RobotFace } from "@/components/robot-face";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";

const MARKDOWNS: { campo: keyof Agente; rotulo: string; arquivo: string }[] = [
  { campo: "agent_md", rotulo: "Quem é", arquivo: "agent.md" },
  { campo: "skill_md", rotulo: "Habilidades", arquivo: "skill.md" },
  { campo: "tools_md", rotulo: "Cinto de instrumentos", arquivo: "tools.md" },
  { campo: "soul_md", rotulo: "Personalidade", arquivo: "soul.md" },
];

/**
 * Editor de agente em drawer (sobre a aba, sem navegar): vê os 4 markdowns,
 * o modelo e o cinto; edita com o FormularioAgente; "Ajustar com a IA" abre a
 * conversa companheira. `Esc` fecha. Reusado pela aba Agentes e pela aba Início.
 */
export function DrawerAgente({
  agente,
  indice,
  cinto,
  instrumentosTime,
  time,
  meuPapel,
  tipos,
  conversaId,
  onFechar,
}: {
  agente: Agente | null;
  indice: number;
  cinto: Instrumento[];
  instrumentosTime: Instrumento[];
  time: Time;
  meuPapel: PapelAcesso | null;
  // Catálogo de tipos de instrumento: quando presente, o cinto vira clicável para
  // editar a config do instrumento (no popup e na leitura). Opcional (degradação).
  tipos?: TipoInstrumento[];
  conversaId: string | null;
  onFechar: () => void;
}) {
  const router = useRouter();
  const { timeId: timeDoPainel, abrir: abrirConversa } = useConversaTime();
  const temPainelDeConversa = timeDoPainel !== "";
  const souOperador = podeOperar(meuPapel);
  const souAdmin = podeAdmin(meuPapel);
  const criando = agente === null;

  const [editando, setEditando] = useState(criando);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  // Só a edição/criação pode virar popup amplo (90%×90%); a leitura fica no drawer.
  const [amplo, setAmplo] = useState(false);
  const ampliado = amplo && (editando || criando);
  // Um drawer de instrumento aberto POR CIMA (via PainelCinto). Enquanto isso, o Esc
  // e o clique no fundo do popup ficam suspensos — o de cima fecha primeiro.
  const [subAberto, setSubAberto] = useState(false);
  // Há texto/básicos editados e NÃO salvos no formulário? (reportado pelo form.)
  const [sujo, setSujo] = useState(false);
  // Cópia de trabalho do cinto: DONO ÚNICO aqui (sobrevive à troca de abas e ao
  // toggle leitura/edição). O PainelCinto (leitura e aba Instrumentos) é controlado
  // por ela; mutações são otimistas + API, sem refresh. Ver Pilar 1/2 do plano.
  const [cintoLocal, setCintoLocal] = useState(cinto);

  // Fecha DE FATO: sincroniza o pai (cards/lista) com a verdade do servidor uma única
  // vez — durante a sessão nada dá refresh (Pilar 2), então isto acontece só aqui.
  // Fechar a partir do EDITOR apaga o rascunho (a sessão terminou de propósito); fechar
  // a LEITURA não apaga (pode haver rascunho ainda não visto de uma sessão anterior).
  function fecharComSync() {
    if (editando || criando) {
      limparRascunho(chaveRascunho(agente?.id ?? null, time.id));
    }
    router.refresh();
    onFechar();
  }

  // Fecha protegendo a edição: se está editando com alterações não salvas, confirma
  // antes de descartar (o botão Salvar é o único caminho que persiste). Cobre X,
  // Esc e clique no fundo — antes só o botão Cancelar avisava.
  function fecharGuardado() {
    if (
      (editando || criando) &&
      sujo &&
      !confirm("Você tem alterações não salvas. Fechar e descartar?")
    ) {
      return;
    }
    fecharComSync();
  }

  // Esc: se há drawer por cima, ele trata; no amplo, só volta ao drawer (não perde a
  // edição); senão, fecha protegendo a edição não salva (mesma guarda do X/fundo).
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (subAberto) return;
      if (ampliado) {
        setAmplo(false);
        return;
      }
      if (
        (editando || criando) &&
        sujo &&
        !confirm("Você tem alterações não salvas. Fechar e descartar?")
      ) {
        return;
      }
      router.refresh();
      onFechar();
    };
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [router, onFechar, ampliado, subAberto, editando, criando, sujo]);

  async function remover() {
    if (!agente) return;
    if (!confirm(`Remover o agente "${agente.nome}"?`)) return;
    setOcupado(true);
    setErro(null);
    try {
      await api.delete(`/agentes/${agente.id}`);
      toast.success("Agente removido");
      onFechar();
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao remover agente");
      setOcupado(false);
    }
  }

  return (
    <div
      className={
        "fixed inset-0 z-50 flex " +
        (ampliado ? "items-center justify-center p-4 sm:p-6" : "justify-end")
      }
    >
      <button
        className="absolute inset-0 bg-foreground/20"
        onClick={() => {
          if (subAberto) return;
          if (ampliado) setAmplo(false);
          else fecharGuardado();
        }}
        aria-label="Fechar"
      />
      <aside
        className={
          "relative flex flex-col overflow-hidden border-border bg-card shadow-xl " +
          (ampliado
            ? "h-[90vh] w-[90vw] max-w-[1400px] rounded-xl border"
            : "h-full w-full max-w-[460px] border-l")
        }
      >
        <header className="flex flex-none items-start gap-3 border-b border-border p-4">
          <RobotFace size={44} indice={indice} lider={agente?.papel === "lider"} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="font-medium text-foreground">
                {criando ? "Novo agente" : agente.nome}
              </h2>
              {agente?.papel === "lider" && (
                <Badge variant="neutral" className="text-[10px]">
                  líder
                </Badge>
              )}
            </div>
            {agente?.modelo_ia && (
              <p className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Sparkles className="size-3 text-primary" />
                {agente.modelo_ia}
              </p>
            )}
          </div>
          {(editando || criando) && (
            <Button
              size="icon"
              variant="ghost"
              onClick={() => setAmplo((v) => !v)}
              aria-label={amplo ? "Minimizar" : "Maximizar"}
            >
              {amplo ? (
                <Minimize2 className="size-4" />
              ) : (
                <Maximize2 className="size-4" />
              )}
            </Button>
          )}
          <Button
            size="icon"
            variant="ghost"
            onClick={fecharGuardado}
            aria-label="Fechar"
          >
            <X className="size-4" />
          </Button>
        </header>

        {editando || criando ? (
          <div className="flex min-h-0 flex-1 flex-col p-4">
            <FormularioAgente
              time={time}
              agente={agente}
              abas={ampliado}
              cinto={cintoLocal}
              onCintoChange={setCintoLocal}
              instrumentosTime={instrumentosTime}
              tipos={tipos}
              meuPapel={meuPapel}
              onSubDrawer={setSubAberto}
              onDirtyChange={setSujo}
              // O formulário só chama onSalvo na CRIAÇÃO (one-shot: fecha + sincroniza).
              // Na edição ele fica aberto, reseta o baseline e não dá refresh (Pilar 2).
              onSalvo={() => {
                toast.success("Agente criado");
                setSujo(false);
                fecharComSync();
              }}
              // Cancelar/fechar o editor: o formulário já confirma se há pendência.
              onCancelar={() => {
                setSujo(false);
                fecharComSync();
              }}
            />
          </div>
        ) : (
          <>
            {/* conteúdo de leitura rola por dentro; rodapé fica fixo embaixo */}
            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
              {(souOperador || souAdmin) && (
              <div className="flex gap-2 border-b border-border p-4">
                {souOperador && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setEditando(true)}
                  >
                    <Pencil className="size-4" /> Editar
                  </Button>
                )}
                {souAdmin && (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={remover}
                    disabled={ocupado}
                  >
                    <Trash2 className="size-4" /> Remover
                  </Button>
                )}
              </div>
            )}

            {erro && (
              <div className="px-4 pt-4">
                <Aviso>{erro}</Aviso>
              </div>
            )}

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

              {/* Cinto de instrumentos (fonte única, igual à aba do popup amplo) */}
              <PainelCinto
                agente={agente}
                cinto={cintoLocal}
                onCintoChange={setCintoLocal}
                instrumentosTime={instrumentosTime}
                time={time}
                meuPapel={meuPapel}
                tipos={tipos}
                onSubDrawer={setSubAberto}
              />

              {/* Memórias (aprendizado do próprio trabalho) */}
              <MemoriaAgentePainel agente={agente} podeOperar={souOperador} />
            </div>
            </div>

            {souOperador && (
              <div className="flex-none border-t border-border p-4">
                {temPainelDeConversa ? (
                  // Dentro do time: abre o painel da IA à esquerda (sem sair da aba).
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => {
                      onFechar();
                      abrirConversa();
                    }}
                  >
                    <Sparkles className="size-4 text-primary" /> Ajustar com a IA
                  </Button>
                ) : (
                  // Fallback (fora do time): leva à conversa em /criar.
                  <Link
                    href={conversaId ? `/criar/${conversaId}` : "/criar"}
                    className={buttonVariants({
                      variant: "outline",
                      className: "w-full",
                    })}
                  >
                    <Sparkles className="size-4 text-primary" /> Ajustar com a IA
                  </Link>
                )}
              </div>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
