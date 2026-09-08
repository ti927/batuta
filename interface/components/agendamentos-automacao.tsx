"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Pencil, X } from "lucide-react";
import { toast } from "sonner";

import {
  api,
  mensagemDeErro,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  DialogoAgendamento,
  TextoDoAgente,
} from "@/components/dialogo-agendamento";

// Seção "Próximas execuções agendadas" da automação: lista os agendamentos PENDENTES
// (disparos futuros criados por um agente pelo instrumento "Agendar automação") e
// permite ver o texto que o agente montou, corrigi-lo e cancelar. Some quando não há
// nenhum. Ilha cliente: busca sob demanda.
//
// A aba "Agendadas" das Execuções é a visão CENTRAL (o time inteiro, incluindo os que
// não dispararam e o resgate deles); aqui é a visão de UMA automação. As duas mostram
// e editam o texto pela mesma regra — o que a camada permite, permite nas duas.

type Agendamento = {
  id: string;
  quando_executar: string;
  entrada: string | null;
  criado_em: string;
};

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
  const [editando, setEditando] = useState<Agendamento | null>(null);

  const buscar = useCallback(
    (primeiraVez = false) =>
      api
        .get<Agendamento[]>(`/automacoes/${automacaoId}/agendamentos`)
        .then(setItens)
        .catch(() => {
          /* silencioso: a seção some */
        })
        .finally(() => primeiraVez && setCarregando(false)),
    [automacaoId],
  );

  useEffect(() => {
    buscar(true);
  }, [buscar]);

  async function cancelar(id: string) {
    setCancelando(id);
    try {
      await api.delete(`/agendamentos/${id}`);
      setItens((l) => l.filter((a) => a.id !== id));
      toast.success("Agendamento cancelado.");
    } catch (e) {
      toast.error(mensagemDeErro(e, "Não consegui cancelar o agendamento."));
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
            className="flex items-start justify-between gap-3 rounded-lg border border-border px-3 py-1.5 text-sm"
          >
            <span className="min-w-0 flex-1">
              <span className="block text-foreground">
                {FMT.format(new Date(a.quando_executar))}
              </span>
              <TextoDoAgente entrada={a.entrada} />
            </span>
            {podeOperar && (
              <span className="flex shrink-0 items-center">
                <Button size="sm" variant="ghost" onClick={() => setEditando(a)}>
                  <Pencil className="size-4" /> Editar
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => cancelar(a.id)}
                  disabled={cancelando === a.id}
                >
                  <X className="size-4" /> Cancelar
                </Button>
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">
        Disparos futuros criados por um agente (instrumento “Agendar automação”). O
        texto entre aspas é o que ele escreveu como entrada — dá para corrigir.
        Horário de Brasília.
      </p>

      {editando && (
        <DialogoAgendamento
          modo="editar"
          agendamentoId={editando.id}
          entradaInicial={editando.entrada}
          quandoInicial={editando.quando_executar}
          onFechar={() => setEditando(null)}
          onPronto={() => {
            buscar();
            toast.success("Agendamento atualizado.");
          }}
        />
      )}
    </section>
  );
}
