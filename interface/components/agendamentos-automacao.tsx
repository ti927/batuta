"use client";

import { useEffect, useState } from "react";
import { CalendarClock, X } from "lucide-react";
import { toast } from "sonner";

import {
  api,
  mensagemDeErro,
} from "@/lib/api";
import { Button } from "@/components/ui/button";

// Seção "Próximas execuções agendadas" da automação: lista os agendamentos PENDENTES
// (disparos futuros criados por um agente pelo instrumento "Agendar automação") e
// permite cancelar. Some quando não há nenhum. Ilha cliente: busca sob demanda.

type Agendamento = { id: string; quando_executar: string; criado_em: string };

const FMT = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo",
  dateStyle: "short",
  timeStyle: "short",
});

export function AgendamentosAutomacao({
  automacaoId,
  podeOperar,
}: {
  automacaoId: string;
  podeOperar: boolean;
}) {
  const [itens, setItens] = useState<Agendamento[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [cancelando, setCancelando] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    api
      .get<Agendamento[]>(`/automacoes/${automacaoId}/agendamentos`)
      .then((d) => {
        if (vivo) setItens(d);
      })
      .catch(() => {
        /* silencioso: a seção some */
      })
      .finally(() => {
        if (vivo) setCarregando(false);
      });
    return () => {
      vivo = false;
    };
  }, [automacaoId]);

  async function cancelar(id: string) {
    setCancelando(id);
    try {
      await api.delete(`/agendamentos/${id}`);
      setItens((l) => l.filter((a) => a.id !== id));
      toast.success("Agendamento cancelado.");
    } catch (e) {
      toast.error(mensagemDeErro(e, "Falha ao cancelar."));
    } finally {
      setCancelando(null);
    }
  }

  if (carregando || itens.length === 0) return null;

  return (
    <section className="mt-3 rounded-xl border border-border bg-card p-4">
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-foreground">
        <CalendarClock className="size-4" /> Próximas execuções agendadas
      </h3>
      <ul className="flex flex-col gap-1.5">
        {itens.map((a) => (
          <li
            key={a.id}
            className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-1.5 text-sm"
          >
            <span className="text-foreground">
              {FMT.format(new Date(a.quando_executar))}
            </span>
            {podeOperar && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => cancelar(a.id)}
                disabled={cancelando === a.id}
              >
                <X className="size-4" /> Cancelar
              </Button>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">
        Disparos futuros criados por um agente (instrumento “Agendar automação”).
        Horário de Brasília.
      </p>
    </section>
  );
}
