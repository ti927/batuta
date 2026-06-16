"use client";

import { Sparkles, Wrench } from "lucide-react";

import { type Agente, type Instrumento } from "@/lib/api";
import { RobotFace } from "@/components/robot-face";
import { Badge } from "@/components/ui/badge";

/**
 * Card de agente (clique abre o editor em drawer). Mostra rosto, nome, badge de
 * líder, resumo (agent.md), modelo e os instrumentos do cinto. Reusado pela aba
 * Agentes e pela aba Início.
 */
export function CardAgente({
  agente,
  indice,
  cinto,
  onAbrir,
}: {
  agente: Agente;
  indice: number;
  cinto: Instrumento[];
  onAbrir: () => void;
}) {
  return (
    <button
      onClick={onAbrir}
      className="flex w-full items-start gap-3 rounded-xl border border-border bg-card p-3.5 text-left transition-all hover:border-[#D6D3E8] hover:shadow-sm"
    >
      <RobotFace size={40} indice={indice} lider={agente.papel === "lider"} />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="font-medium text-foreground">{agente.nome}</span>
          {agente.papel === "lider" && (
            <Badge variant="neutral" className="text-[10px]">
              líder
            </Badge>
          )}
        </span>
        {agente.agent_md && (
          <span className="mt-0.5 line-clamp-2 block text-sm text-muted-foreground">
            {agente.agent_md}
          </span>
        )}
        <span className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          {agente.modelo_ia && (
            <span className="inline-flex items-center gap-1">
              <Sparkles className="size-3 text-primary" />
              {agente.modelo_ia}
            </span>
          )}
          {cinto.map((i) => (
            <span
              key={i.id}
              className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-accent-foreground"
            >
              <Wrench className="size-3" />
              {i.nome}
            </span>
          ))}
        </span>
      </span>
    </button>
  );
}
