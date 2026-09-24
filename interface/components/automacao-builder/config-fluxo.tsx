"use client";

// O CAMPO de uma regra do fluxo (tempo, limite, sim/não…), com "padrão do Batuta" ×
// "ajustado" e o "voltar ao padrão". Usado pelo painel de regras do Estúdio e pela aba
// "Ritmo e espera" do agente. Os grupos, rótulos e opções vêm de /config/fluxo (fonte
// única no cérebro) — nada é duplicado aqui.
//
// A janela antiga das regras (o botão "Fluxo" da tela clássica) saiu com a tela, em
// 2026-09-24: as regras moram no painel da direita do Estúdio.

import { RotateCcw } from "lucide-react";

import {
  type CampoConfigFluxo,
  type ConfiguracaoFluxo,
  type PainelConfigFluxo,
} from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

// A base de tudo é o PADRÃO DO BATUTA. O "Tipo de fluxo" era uma camada acima disto e
// morreu em 2026-09-22: ele guardava uma etiqueta cujos números moravam no cérebro, e
// era por isso que a tela mostrava valores que não estavam no dado da automação. Um
// modelo agora só CARIMBA os números nos ajustes e sai de cena.
export function defaultsDoBatuta(
  painel: PainelConfigFluxo,
): Record<string, unknown> {
  return painel.padrao_global ?? {};
}

// O valor EFETIVO de uma chave no nível do fluxo: o ajuste da automação, ou o padrão do
// Batuta. É o "herdado" que o agente sobrepõe na aba "Ritmo e espera" dele.
export function efetivoDoFluxo(
  painel: PainelConfigFluxo,
  configFluxo: ConfiguracaoFluxo,
  chave: string,
): unknown {
  const ajustes = configFluxo.ajustes ?? {};
  if (chave in ajustes) return ajustes[chave];
  return defaultsDoBatuta(painel)[chave];
}

export function CampoConfig({
  campo,
  valor,
  ajustado,
  podeEditar,
  onChange,
  onReset,
  rotuloHerdado = "padrão do Batuta",
}: {
  campo: CampoConfigFluxo;
  valor: unknown;
  ajustado: boolean;
  podeEditar: boolean;
  onChange: (v: unknown) => void;
  onReset: () => void;
  rotuloHerdado?: string;
}) {
  // Marcador "herdado" / "ajustado — voltar ao padrão" (o afinado vence o herdado;
  // deixamos isso visível e reversível).
  const marcador =
    ajustado && podeEditar ? (
      <button
        type="button"
        onClick={onReset}
        className="flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
      >
        <RotateCcw className="size-3" /> ajustado — voltar ao padrão
      </button>
    ) : ajustado ? (
      <span className="text-[11px] text-primary">ajustado</span>
    ) : (
      <span className="text-[11px] text-muted-foreground/60">{rotuloHerdado}</span>
    );

  if (campo.tipo === "bool") {
    return (
      <div className="flex items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-[13px] text-foreground">
          <input
            type="checkbox"
            className="accent-primary"
            disabled={!podeEditar}
            checked={!!valor}
            onChange={(e) => onChange(e.target.checked)}
          />
          {campo.rotulo}
        </label>
        {marcador}
      </div>
    );
  }
  return (
    <Label className="flex-col items-start gap-1 text-[12px] text-muted-foreground">
      <span className="flex w-full items-center justify-between gap-2">
        <span>
          {campo.rotulo}
          {campo.sufixo ? ` (${campo.sufixo})` : ""}
        </span>
        {marcador}
      </span>
      {campo.tipo === "escolha" ? (
        <Select
          value={String(valor ?? "")}
          disabled={!podeEditar}
          onChange={(e) => onChange(e.target.value)}
          className="w-full"
        >
          {(campo.opcoes ?? []).map((o) => (
            <option key={o.valor} value={o.valor}>
              {o.rotulo}
            </option>
          ))}
        </Select>
      ) : campo.tipo === "int" || campo.tipo === "valor" ? (
        <Input
          type="number"
          step={campo.tipo === "valor" ? "0.01" : "1"}
          disabled={!podeEditar}
          value={valor === undefined || valor === null ? "" : String(valor)}
          onChange={(e) =>
            onChange(
              campo.tipo === "valor"
                ? Number(e.target.value)
                : parseInt(e.target.value || "0", 10),
            )
          }
          className="w-full"
        />
      ) : campo.tipo === "hora" ? (
        <Input
          type="time"
          disabled={!podeEditar}
          value={String(valor ?? "")}
          onChange={(e) => onChange(e.target.value)}
          className="w-full"
        />
      ) : (
        <Input
          type="text"
          disabled={!podeEditar}
          value={String(valor ?? "")}
          onChange={(e) => onChange(e.target.value)}
          className="w-full"
        />
      )}
    </Label>
  );
}
