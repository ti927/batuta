"use client";

// Seletor do modelo da IA de conversa (criadora/companheira) de uma organização.
// Mostra só modelos cujo provedor tem chave (própria ou da consultoria); o padrão
// (valor vazio) deixa o cérebro usar o Opus. Salva em PUT /modelo-criadora.

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import {
  api,
  mensagemDeErro,
} from "@/lib/api";
import {
  MODELOS_POR_PROVEDOR,
  NOTA_MODELO_CONVERSA,
  provedorDoModelo,
  provedoresParaSeletor,
  ROTULO_PROVEDOR,
  type ProvedoresDisponiveis,
} from "@/lib/modelos";
import { Select } from "@/components/ui/select";

export function SeletorModeloConversa({
  organizacaoId,
  modeloAtual,
  disponiveis,
}: {
  organizacaoId: string;
  modeloAtual: string | null;
  disponiveis: ProvedoresDisponiveis;
}) {
  const router = useRouter();
  const [salvando, setSalvando] = useState(false);

  const provedores = provedoresParaSeletor(
    disponiveis,
    modeloAtual ? provedorDoModelo(modeloAtual) : null,
  );

  async function trocar(modelo: string) {
    setSalvando(true);
    try {
      await api.put(`/organizacoes/${organizacaoId}/modelo-criadora`, {
        modelo: modelo || null,
      });
      toast.success(
        modelo
          ? `Modelo da IA de conversa: ${modelo}`
          : "Modelo da IA de conversa: padrão (Claude Sonnet 5)",
      );
      router.refresh();
    } catch (e) {
      toast.error(
        mensagemDeErro(e, "Falha ao salvar o modelo"),
      );
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="mt-6 flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-foreground">
        Modelo da IA de conversa
      </h3>
      <Select
        className="w-auto self-start"
        value={modeloAtual ?? ""}
        disabled={salvando}
        onChange={(e) => trocar(e.target.value)}
      >
        <option value="">Padrão (Claude Sonnet 5)</option>
        {provedores.map((p) => (
          <optgroup key={p} label={ROTULO_PROVEDOR[p]}>
            {MODELOS_POR_PROVEDOR[p].map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </optgroup>
        ))}
      </Select>
      <p className="text-xs text-muted-foreground">{NOTA_MODELO_CONVERSA}</p>
    </div>
  );
}
