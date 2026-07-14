"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Brain, Pencil, Plus, Trash2 } from "lucide-react";

import { api, ErroDaApi, type Agente, type MemoriaAgente } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

// Painel "Memórias do agente" (no drawer do agente): o agente aprende com o próprio
// trabalho em FICHAS POR ASSUNTO; aqui o humano supervisiona — vê, cria, edita e apaga.
// Ilha cliente: busca sob demanda. Some (com dica) quando a memória está desligada.

const FMT = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

type Edicao = { id: string | null; assunto: string; conteudo: string };

function FormFicha({
  edicao,
  setEdicao,
  onSalvar,
  ocupado,
}: {
  edicao: Edicao;
  setEdicao: (e: Edicao | null) => void;
  onSalvar: () => void;
  ocupado: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Input
        placeholder="Assunto (ex.: Cliente: Padaria do João)"
        value={edicao.assunto}
        onChange={(e) => setEdicao({ ...edicao, assunto: e.target.value })}
      />
      <Textarea
        className="min-h-16 font-mono text-sm"
        placeholder="O que lembrar sobre esse assunto (resumo enxuto)…"
        value={edicao.conteudo}
        onChange={(e) => setEdicao({ ...edicao, conteudo: e.target.value })}
      />
      <div className="flex gap-2">
        <Button size="sm" onClick={onSalvar} disabled={ocupado}>
          Salvar
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setEdicao(null)}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}

export function MemoriaAgentePainel({
  agente,
  podeOperar,
}: {
  agente: Agente;
  podeOperar: boolean;
}) {
  const [itens, setItens] = useState<MemoriaAgente[]>([]);
  // Só carrega quando a memória está ligada (evita setState síncrono no effect).
  const [carregando, setCarregando] = useState(agente.memoria_ativa);
  const [edicao, setEdicao] = useState<Edicao | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    if (!agente.memoria_ativa) return;
    let vivo = true;
    api
      .get<MemoriaAgente[]>(`/agentes/${agente.id}/memorias`)
      .then((d) => {
        if (vivo) setItens(d);
      })
      .catch(() => {
        /* silencioso */
      })
      .finally(() => {
        if (vivo) setCarregando(false);
      });
    return () => {
      vivo = false;
    };
  }, [agente.id, agente.memoria_ativa]);

  async function salvar() {
    if (!edicao) return;
    const assunto = edicao.assunto.trim();
    const conteudo = edicao.conteudo.trim();
    if (!assunto || !conteudo) {
      toast.error("Assunto e conteúdo são obrigatórios.");
      return;
    }
    setOcupado(true);
    try {
      if (edicao.id) {
        const m = await api.put<MemoriaAgente>(`/memorias-agente/${edicao.id}`, {
          assunto,
          conteudo,
        });
        setItens((l) => l.map((x) => (x.id === m.id ? m : x)));
      } else {
        const m = await api.post<MemoriaAgente>(
          `/agentes/${agente.id}/memorias`,
          { assunto, conteudo },
        );
        setItens((l) => [m, ...l.filter((x) => x.id !== m.id)]);
      }
      setEdicao(null);
      toast.success("Memória salva.");
    } catch (e) {
      toast.error(e instanceof ErroDaApi ? e.message : "Falha ao salvar.");
    } finally {
      setOcupado(false);
    }
  }

  async function apagar(id: string) {
    if (!confirm("Apagar esta ficha de memória?")) return;
    try {
      await api.delete(`/memorias-agente/${id}`);
      setItens((l) => l.filter((x) => x.id !== id));
      toast.success("Ficha apagada.");
    } catch (e) {
      toast.error(e instanceof ErroDaApi ? e.message : "Falha ao apagar.");
    }
  }

  return (
    <div>
      <div className="mb-1.5 flex items-center gap-2">
        <Brain className="size-4 text-primary" />
        <span className="text-sm font-medium text-foreground">
          Memórias (aprendizado)
        </span>
      </div>

      {!agente.memoria_ativa ? (
        <p className="text-sm text-muted-foreground">
          Memória desligada. Ligue em “Editar” para o agente aprender com o próprio
          trabalho e lembrar entre execuções.
        </p>
      ) : carregando ? (
        <p className="text-sm text-muted-foreground">Carregando…</p>
      ) : (
        <>
          {itens.length === 0 && !edicao && (
            <p className="text-sm text-muted-foreground">
              Nenhuma ficha ainda — o agente aprende sozinho ao trabalhar, ou crie uma.
            </p>
          )}
          {itens.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {itens.map((m) => (
                <li
                  key={m.id}
                  className="rounded-md border border-border bg-background px-3 py-2"
                >
                  {edicao?.id === m.id ? (
                    <FormFicha
                      edicao={edicao}
                      setEdicao={setEdicao}
                      onSalvar={salvar}
                      ocupado={ocupado}
                    />
                  ) : (
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                          {m.assunto}
                        </span>
                        {podeOperar && (
                          <>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                setEdicao({
                                  id: m.id,
                                  assunto: m.assunto,
                                  conteudo: m.conteudo,
                                })
                              }
                              aria-label="Editar"
                            >
                              <Pencil className="size-3.5" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => apagar(m.id)}
                              aria-label="Apagar"
                            >
                              <Trash2 className="size-3.5" />
                            </Button>
                          </>
                        )}
                      </div>
                      <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                        {m.conteudo}
                      </p>
                      <span className="text-[11px] text-muted-foreground/70">
                        {FMT.format(new Date(m.atualizado_em))}
                      </span>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {podeOperar &&
            (edicao && edicao.id === null ? (
              <div className="mt-2 rounded-md border border-border bg-background px-3 py-2">
                <FormFicha
                  edicao={edicao}
                  setEdicao={setEdicao}
                  onSalvar={salvar}
                  ocupado={ocupado}
                />
              </div>
            ) : (
              !edicao && (
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-2"
                  onClick={() => setEdicao({ id: null, assunto: "", conteudo: "" })}
                >
                  <Plus className="size-4" /> Nova ficha
                </Button>
              )
            ))}
        </>
      )}
    </div>
  );
}
