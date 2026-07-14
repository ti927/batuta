"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Maximize2,
  Minimize2,
  Pencil,
  Sparkles,
  Trash2,
  Wrench,
  X,
} from "lucide-react";

import {
  api,
  ErroDaApi,
  type Agente,
  type Instrumento,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { useConversaTime } from "@/components/conversa-ia/painel-time";
import { FormularioAgente } from "@/components/formulario-agente";
import { IconeInstrumento } from "@/components/icone-instrumento";
import { MemoriaAgentePainel } from "@/components/memoria-agente";
import { RobotFace } from "@/components/robot-face";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Select } from "@/components/ui/select";

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
  conversaId,
  onFechar,
}: {
  agente: Agente | null;
  indice: number;
  cinto: Instrumento[];
  instrumentosTime: Instrumento[];
  time: Time;
  meuPapel: PapelAcesso | null;
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
  const [selecionado, setSelecionado] = useState("");
  // Só a edição/criação pode virar popup amplo (80%×80%); a leitura fica no drawer.
  const [amplo, setAmplo] = useState(false);
  const ampliado = amplo && (editando || criando);

  // Esc fecha o drawer; no modo amplo, primeiro volta ao drawer (protege a edição).
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (ampliado) setAmplo(false);
      else onFechar();
    };
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [onFechar, ampliado]);

  const disponiveis = instrumentosTime.filter(
    (i) => !cinto.some((c) => c.id === i.id),
  );

  async function pendurar() {
    if (!selecionado || !agente) return;
    setOcupado(true);
    setErro(null);
    try {
      await api.post(`/agentes/${agente.id}/instrumentos`, {
        instrumento_id: selecionado,
      });
      setSelecionado("");
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao pendurar instrumento");
    } finally {
      setOcupado(false);
    }
  }

  async function tirar(instrumentoId: string) {
    if (!agente) return;
    setOcupado(true);
    setErro(null);
    try {
      await api.delete(`/agentes/${agente.id}/instrumentos/${instrumentoId}`);
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao tirar instrumento");
    } finally {
      setOcupado(false);
    }
  }

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
        onClick={() => (ampliado ? setAmplo(false) : onFechar())}
        aria-label="Fechar"
      />
      <aside
        className={
          "relative flex flex-col overflow-hidden border-border bg-card shadow-xl " +
          (ampliado
            ? "h-[80vh] w-[80vw] max-w-[1200px] rounded-xl border"
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
          <Button size="icon" variant="ghost" onClick={onFechar} aria-label="Fechar">
            <X className="size-4" />
          </Button>
        </header>

        {editando || criando ? (
          <div className="flex min-h-0 flex-1 flex-col p-4">
            <FormularioAgente
              time={time}
              agente={agente}
              amplo={ampliado}
              onSalvo={() => {
                toast.success(criando ? "Agente criado" : "Agente salvo");
                setAmplo(false);
                if (criando) onFechar();
                else setEditando(false);
                router.refresh();
              }}
              onCancelar={() => {
                setAmplo(false);
                if (criando) onFechar();
                else setEditando(false);
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

              {/* Cinto de instrumentos */}
              <div>
                <div className="mb-1.5 flex items-center gap-2">
                  <Wrench className="size-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">
                    Cinto de instrumentos
                  </span>
                </div>
                {cinto.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Nenhum instrumento pendurado.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-1.5">
                    {cinto.map((i) => (
                      <li
                        key={i.id}
                        className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm"
                      >
                        <IconeInstrumento
                          icone={i.icone}
                          className="size-3.5 text-muted-foreground"
                        />
                        <span className="min-w-0 flex-1 truncate text-foreground">
                          {i.nome}
                        </span>
                        <span className="text-xs text-muted-foreground">{i.tipo}</span>
                        {souOperador && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => tirar(i.id)}
                            disabled={ocupado}
                          >
                            Tirar
                          </Button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {souOperador && disponiveis.length > 0 && (
                  <div className="mt-2 flex gap-2">
                    <Select
                      value={selecionado}
                      onChange={(e) => setSelecionado(e.target.value)}
                      className="flex-1"
                    >
                      <option value="">Pendurar um instrumento…</option>
                      {disponiveis.map((i) => (
                        <option key={i.id} value={i.id}>
                          {i.nome} ({i.tipo})
                        </option>
                      ))}
                    </Select>
                    <Button
                      variant="outline"
                      onClick={pendurar}
                      disabled={!selecionado || ocupado}
                    >
                      Pendurar
                    </Button>
                  </div>
                )}
              </div>

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
