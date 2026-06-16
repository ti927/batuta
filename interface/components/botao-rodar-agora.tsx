"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Play, X } from "lucide-react";

import { api, ErroDaApi, type ExecucaoComPassos } from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

type AutomacaoOpcao = { id: string; nome: string };

/**
 * "Rodar agora" do cabeçalho do time: dispara uma automação manualmente. Se o
 * time tem uma só, vai direto; se tem várias, deixa escolher. Pede a entrada e,
 * ao disparar, leva para o detalhe da execução na aba Execuções. Só operador.
 */
export function BotaoRodarAgora({
  timeId,
  automacoes,
}: {
  timeId: string;
  automacoes: AutomacaoOpcao[];
}) {
  const router = useRouter();
  const [aberto, setAberto] = useState(false);
  const [automacaoId, setAutomacaoId] = useState(automacoes[0]?.id ?? "");
  const [entrada, setEntrada] = useState("");
  const [disparando, setDisparando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  if (automacoes.length === 0) return null;

  async function disparar() {
    if (!automacaoId || !entrada.trim()) return;
    setDisparando(true);
    setErro(null);
    try {
      const r = await api.post<ExecucaoComPassos>(
        `/automacoes/${automacaoId}/disparar`,
        { entrada: entrada.trim() },
      );
      setAberto(false);
      setEntrada("");
      router.push(`/times/${timeId}/execucoes/${r.id}`);
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao disparar");
    } finally {
      setDisparando(false);
    }
  }

  return (
    <>
      <Button onClick={() => setAberto(true)}>
        <Play className="size-4" /> Rodar agora
      </Button>

      {aberto && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            className="absolute inset-0 bg-foreground/20"
            onClick={() => setAberto(false)}
            aria-label="Fechar"
          />
          <div className="relative w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-heading text-lg font-medium text-foreground">
                Rodar agora
              </h2>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => setAberto(false)}
                aria-label="Fechar"
              >
                <X className="size-4" />
              </Button>
            </div>

            {erro && (
              <div className="mb-3">
                <Aviso>{erro}</Aviso>
              </div>
            )}

            <div className="flex flex-col gap-3">
              {automacoes.length > 1 && (
                <Label className="flex-col items-start gap-1">
                  Automação
                  <Select
                    value={automacaoId}
                    onChange={(e) => setAutomacaoId(e.target.value)}
                    className="w-full"
                  >
                    {automacoes.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.nome}
                      </option>
                    ))}
                  </Select>
                </Label>
              )}
              <Label className="flex-col items-start gap-1">
                Entrada (a tarefa/mensagem)
                <Textarea
                  className="min-h-24"
                  placeholder="O que esta execução deve fazer?"
                  value={entrada}
                  onChange={(e) => setEntrada(e.target.value)}
                />
              </Label>
              <Button
                className="self-start"
                onClick={disparar}
                disabled={disparando || !entrada.trim()}
              >
                {disparando ? "Disparando…" : "Disparar"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
