"use client";

// Switch da parede de aprovação (primeira config global da organização). Liga/
// desliga via PUT /organizacoes/{id}/parede-ativacao. Otimista, com reversão em erro.

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import {
  api,
  mensagemDeErro,
} from "@/lib/api";

export function ParedeSwitch({
  organizacaoId,
  ativada,
}: {
  organizacaoId: string;
  ativada: boolean;
}) {
  const router = useRouter();
  const [on, setOn] = useState(ativada);
  const [salvando, setSalvando] = useState(false);

  async function alternar() {
    if (salvando) return;
    const novo = !on;
    setOn(novo);
    setSalvando(true);
    try {
      await api.put(`/organizacoes/${organizacaoId}/parede-ativacao`, {
        ativada: novo,
      });
      toast.success(
        novo ? "Parede de aprovação ligada." : "Parede de aprovação desligada.",
      );
      router.refresh();
    } catch (e) {
      setOn(!novo); // reverte o otimista
      toast.error(mensagemDeErro(e, "Falha ao salvar"));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex-1">
        <h3 className="text-sm font-medium text-foreground">
          Parede de aprovação
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Ao desligar a parede, instrumentos com ações irreversíveis (postar,
          salvar, etc.) poderão ser executados <strong>sem aprovação</strong>.
          Desligue somente se tiver certeza do risco.
        </p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label="Parede de aprovação"
        disabled={salvando}
        onClick={alternar}
        className="relative mt-0.5 h-[23px] w-10 flex-none rounded-full transition-colors disabled:opacity-60"
        style={{ background: on ? "#6D4AFF" : "#D6D3E8" }}
      >
        <span
          className="absolute top-0.5 size-[19px] rounded-full bg-white shadow transition-all"
          style={{ left: on ? "18px" : "2px" }}
        />
      </button>
    </div>
  );
}
